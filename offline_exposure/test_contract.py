"""Synthetic executable specifications. Never imports the application package."""
import unittest
import hashlib
import zipfile
from pathlib import Path
from dataclasses import replace
from threading import Barrier, Thread, Event as ThreadEvent
from itertools import permutations
from exposure_view import (Partition, Row, Policy, Snapshot, Coverage, Event,
                           evaluate, usd_direction)
from fake_coordinator import FakeCoordinator

A = Partition("synthetic", "offline", "A")
B = replace(A, account="B")
SYMBOLS = frozenset({"EUR_USD", "GBP_USD", "AUD_USD", "USD_JPY", "EUR_GBP"})
POLICY = Policy(10, True, True, SYMBOLS)
R = Row(A, "EUR_USD", "SELL", 2, ("T1",))
S = Snapshot(A, 1, 1, 0, 0, (R,), watermark=100, epoch="E", cut_verified=True, pending=())


def view(snapshot=S, **kw):
    return evaluate(A, snapshot, now=kw.pop("now", 0), policy=kw.pop("policy", POLICY), **kw)


class ContractTests(unittest.TestCase):
    def valid_count(self, snapshot=S, count=1, direction="LONG", **kw):
        result = view(snapshot, **kw)
        self.assertTrue(result.valid, result.reason)
        self.assertEqual(result.count(direction), count)
        return result

    def denied(self, snapshot=S, reason=None, **kw):
        result = view(snapshot, **kw)
        self.assertFalse(result.valid)
        self.assertIsNone(result.count("LONG"))
        if reason:
            self.assertEqual(result.reason, "EXPOSURE_" + reason)

    def test_01_usd_guard_counts_broker_discovery_without_management_authority(self):
        self.valid_count()
        self.assertTrue(R.observation_only)
        self.assertEqual(R.kind, "observation")

    def test_02_restart_window_paper_cannot_hide_live_broker_position(self):
        paper = replace(R, kind="window_paper", partition=B)
        before = repr(paper)
        self.valid_count(managed=(paper,))
        self.assertEqual(repr(paper), before)
        self.assertTrue(R.observation_only)

    def test_03_paper_only(self):
        for kind in ("paper", "window_paper", "simulated"):
            self.valid_count(replace(S, rows=()), count=0, managed=(replace(R, kind=kind),))

    def test_04_managed_dedup(self):
        result = self.valid_count(managed=(replace(R, kind="managed", observation_only=False),))
        self.assertIn("managed", result.provenance[0][2])

    def test_05_multiple_trades_and_slots(self):
        self.valid_count(replace(S, rows=(replace(R, trade_ids=("T1", "T2")),)))
        self.valid_count(replace(S, rows=(R, replace(R, symbol="GBP_USD", trade_ids=("T2",)))), count=2)

    def test_06_opposite_direction(self):
        s = replace(S, rows=(replace(R, side="BUY"),))
        self.valid_count(s, count=0)
        self.valid_count(s, direction="SHORT")

    def test_07_partition(self):
        for part in (B, replace(A, environment="other"), replace(A, venue="other")):
            self.denied(replace(S, partition=part), "PARTITION_MISMATCH")

    def test_08_aggregate_and_unknown_managed_id(self):
        self.valid_count(replace(S, rows=(replace(R, trade_ids=()),)))
        self.denied(managed=(replace(R, kind="managed", observation_only=False, trade_ids=("unknown",)),))

    def test_09_duplicate_and_identity(self):
        self.denied(replace(S, rows=(R, R)), "SNAPSHOT_MALFORMED")
        self.denied(replace(S, rows=(R, replace(R, symbol="GBP_USD"))), "IDENTITY_CONFLICT")

    def test_10_hedge_and_zero(self):
        self.denied(replace(S, rows=(R, replace(R, side="BUY"))))
        self.valid_count(replace(S, rows=(replace(R, units=0),)), count=0)

    def test_11_malformed(self):
        for row in (replace(R, units=float("nan")), replace(R, units=float("inf")),
                    replace(R, units=-2), replace(R, side="BAD"), replace(R, symbol="BAD"),
                    replace(R, units="not numeric"),
                    replace(R, partition=B)):
            with self.subTest(row=row):
                self.denied(replace(S, rows=(row,)))

    def test_12_age_boundaries(self):
        self.valid_count(now=10)
        for now in (10.00001, -1, float("nan")):
            self.denied(now=now)

    def test_13_slow_response(self):
        self.denied(replace(S, accepted=11), now=11)
        self.denied(replace(S, accepted=1), now=0)

    def test_14_snapshot_states(self):
        self.denied(None, "SNAPSHOT_MISSING")
        for status in ("INCOMPLETE", "MALFORMED", "FAILED", "REFRESHING"):
            self.denied(replace(S, status=status), "SNAPSHOT_" + status)

    def test_15_failed_refresh_retains_capacity(self):
        c = FakeCoordinator(view())
        c.reserve("i", "GBP_USD", "SELL", "x")
        g = c.refresh()
        self.assertFalse(c.publish(g))
        self.assertEqual(c.view.count("LONG"), 1)  # last-known, not usable
        self.assertFalse(c.reserve("j", "AUD_USD", "SELL", "x"))
        self.assertEqual(len(c.intents), 1)

    def test_16_flat_and_disagreement(self):
        flat = replace(S, rows=())
        self.valid_count(flat, count=0)
        self.denied(flat, managed=(replace(R, kind="managed", observation_only=False),))

    def test_17_latest_generation(self):
        self.denied(replace(S, latest_generation=2), "VIEW_CHANGED")
        c = FakeCoordinator(view())
        c.refresh()
        self.assertFalse(c.publish(1, view()))
        self.assertTrue(c.refreshing)

    def test_18_ordered_fill(self):
        new = replace(R, symbol="GBP_USD", trade_ids=("T2",))
        cov = Coverage((Event(A, "E", 101, "OPEN", new),), 101, True)
        self.valid_count(coverage=cov, count=2, managed=(replace(new, kind="managed", observation_only=False),))
        self.denied(coverage=replace(cov, verified=False))

    def test_19_revision(self):
        c = FakeCoordinator(view())
        c.reserve("i", "GBP_USD", "SELL", "x", revision=0)
        self.assertIsNone(c.reserve("j", "AUD_USD", "SELL", "x", revision=0))

    def test_20_disabled_cap_and_nonusd_invalid(self):
        for symbol in ("GBP_USD", "EUR_GBP"):
            c = FakeCoordinator(view(policy=Policy()), limit=0)
            self.assertIsNone(c.reserve("i", symbol, "SELL", "x"))

    def test_21_deterministic_pure(self):
        rows = (R, replace(R, symbol="GBP_USD", trade_ids=("T2",)))
        expected = view(replace(S, rows=rows))
        for order in permutations(rows):
            self.assertEqual(view(replace(S, rows=order)), expected)
        self.assertEqual(S.rows, (R,))

    def test_22_no_authority_surface(self):
        self.assertTrue(R.observation_only)
        for name in ("dispatch", "close", "adopt", "manage", "persist"):
            self.assertFalse(hasattr(view(), name))

    def test_23_racing_candidates(self):
        for first, second in (("GBP_USD", "AUD_USD"), ("AUD_USD", "GBP_USD")):
            c = FakeCoordinator(view())
            self.assertIsNotNone(c.reserve("a", first, "SELL", "x"))
            self.assertIsNone(c.reserve("b", second, "SELL", "x"))
            self.assertEqual(c.view.count("LONG"), 1)
        c = FakeCoordinator(view())
        gate = Barrier(3)
        results = []
        def worker(key, symbol):
            gate.wait()
            results.append(c.reserve(key, symbol, "SELL", "x"))
        workers = [Thread(target=worker, args=("a", "GBP_USD")), Thread(target=worker, args=("b", "AUD_USD"))]
        for t in workers:
            t.start()
        gate.wait()
        for t in workers:
            t.join(5)
            self.assertFalse(t.is_alive())
        self.assertEqual(sum(r is not None for r in results), 1)

    def test_24_idempotency_and_sides(self):
        c = FakeCoordinator(view())
        a = c.reserve("a", "GBP_USD", "SELL", "x")
        self.assertEqual(a, c.reserve("a", "GBP_USD", "SELL", "x"))
        self.assertIsNone(c.reserve("a", "GBP_USD", "SELL", "different"))
        self.assertIsNone(c.reserve("b", "GBP_USD", "SELL", "x"))
        self.assertIsNone(c.reserve("c", "GBP_USD", "BUY", "x"))

    def test_25_unavailable_and_unapproved_writer(self):
        c = FakeCoordinator(view())
        c.available = False
        self.assertIsNone(c.reserve("a", "GBP_USD", "SELL", "x"))
        self.denied(policy=replace(POLICY, single_writer_verified=False))

    def test_26_refresh_dispatch_serialization(self):
        for refresh_first in (False, True):
            c = FakeCoordinator(view())
            c.reserve("a", "GBP_USD", "SELL", "x")
            if refresh_first:
                c.refresh()
                self.assertFalse(c.dispatch("a"))
            else:
                self.assertTrue(c.dispatch("a"))
                c.refresh()
                self.assertEqual(c.intents['a'].state, 'DISPATCHING')
            self.assertIsNone(c.reserve("b", "AUD_USD", "SELL", "x"))

    def test_27_frozen_release_and_success(self):
        c = FakeCoordinator(view(), limit=0)
        c.reserve("a", "GBP_USD", "SELL", "x")
        c.reserve("b", "AUD_USD", "SELL", "x")
        c.dispatch("b")
        g = c.refresh()
        c.publish(g)
        self.assertFalse(c.release_unsent("b"))
        self.assertTrue(c.release_unsent("a"))
        g = c.refresh()
        self.assertTrue(c.publish(g, view(replace(S, generation=g, latest_generation=g))))
        self.assertEqual(c.intents['b'].state, 'DISPATCHING')

    def test_28_fill_transfer_and_no_ttl_release(self):
        c = FakeCoordinator(view())
        c.reserve("a", "GBP_USD", "SELL", "x")
        c.dispatch("a")
        self.assertFalse(c.release_unsent("a"))
        new = replace(R, symbol="GBP_USD", trade_ids=("T2",))
        self.assertTrue(c.transfer_fill("a", view(replace(S, rows=(R, new)))))
        self.assertEqual(len(c._slots()), 2)
        self.assertEqual(len(c.intents), 0)
        self.assertIsNone(c.reserve("b", "AUD_USD", "SELL", "x"))

    def test_29_watermark_and_close(self):
        new = replace(R, symbol="GBP_USD", trade_ids=("T2",))
        event = Event(A, "E", 101, "OPEN", new)
        cov = Coverage((event,), 101, True)
        for ev in (replace(event, sequence=100), replace(event, sequence=102), replace(event, epoch="other"), replace(event, partition=B)):
            self.denied(coverage=replace(cov, events=(ev,)))
        self.denied(replace(S, watermark=None), coverage=cov)
        self.denied(replace(S, cut_verified=False), coverage=cov)
        self.valid_count(coverage=Coverage((event, replace(event, sequence=102, action="CLOSE")), 102, True))

    def test_30_local_time_not_ordering(self):
        managed = replace(R, symbol="GBP_USD", kind="managed", observation_only=False)
        for now in (0, 5, 10):
            self.denied(now=now, managed=(managed,))

    def test_31_no_default_policy_or_continuity(self):
        self.denied(policy=Policy(), reason="FRESHNESS_POLICY_UNAPPROVED")
        self.denied(policy=replace(POLICY, continuity_verified=False), reason="ORDERING_UNPROVEN")

    def test_32_clock_and_scheduled_actions(self):
        clock = [0]
        c = FakeCoordinator(view(), clock=lambda: clock[0])
        c.reserve("a", "GBP_USD", "SELL", "x")
        clock[0] = 11
        self.assertFalse(c.dispatch("a"))
        self.assertIsNone(c.reserve("b", "AUD_USD", "SELL", "x"))
        for actions in permutations(("reserve", "refresh", "dispatch")):
            c = FakeCoordinator(view())
            for action in actions:
                if action == "reserve":
                    c.reserve("a", "GBP_USD", "SELL", "x")
                elif action == "refresh":
                    c.refresh()
                else:
                    c.dispatch("a")
                self.assertLessEqual(len(c._slots()), 2)

    def test_33_actual_source_seal_conflict_is_detected(self):
        # A passing conflict-detection test is NOT passing the operational seal.
        expected = "a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81"
        root = Path(__file__).resolve().parents[1]
        local = hashlib.sha256((root / 'forex_bot' / 'bot_loop.py').read_bytes()).hexdigest()
        self.assertEqual(local, "2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d")
        with zipfile.ZipFile(root / 'data/research/adaptive_ensemble/r86/R86_SOURCE_REVIEW.zip') as z:
            member = next(n for n in z.namelist() if n.endswith('forex_bot/bot_loop.py'))
            self.assertEqual(hashlib.sha256(z.read(member)).hexdigest(), expected)
        self.assertNotEqual(expected, local)

    def test_34_pending_unknown_and_external_pending_fail_closed(self):
        self.denied(replace(S, pending=None), 'PENDING_EXPOSURE_UNKNOWN')
        self.denied(replace(S, pending=(R,)), 'PENDING_EXPOSURE_UNRESOLVED')

    def test_35_default_direct_entry_denied(self):
        result = evaluate(A, S, now=0)
        self.assertFalse(result.valid)
        self.assertIsNone(result.count('LONG'))

    def test_36_cross_process_guarantee_not_claimed(self):
        # A counterexample: separate in-memory instances both admit. No real
        # processes or transports are launched; this proves the fake's limit.
        a, b = FakeCoordinator(view()), FakeCoordinator(view())
        self.assertIsNotNone(a.reserve('a', 'GBP_USD', 'SELL', 'x'))
        self.assertIsNotNone(b.reserve('b', 'AUD_USD', 'SELL', 'x'))
        combined = a._slots() | b._slots()
        self.assertEqual(len(combined), 3)

    def test_37_same_slot_open_then_close_cannot_erase_original_trade(self):
        t2 = replace(R, trade_ids=('T2',))
        opened = Event(A, 'E', 101, 'OPEN', t2)
        closed = replace(opened, sequence=102, action='CLOSE')
        original = view()
        for events in ((opened,), (opened, closed)):
            with self.subTest(actions=tuple(e.action for e in events)):
                result = view(coverage=Coverage(events, events[-1].sequence, True))
                self.assertFalse(result.valid)
                self.assertEqual(result.reason, 'EXPOSURE_IDENTITY_CONFLICT')
                self.assertIsNone(result.count('LONG'))
        self.assertEqual(S.rows, (R,))
        self.assertEqual(R.trade_ids, ('T1',))
        self.assertEqual(original.count('LONG'), 1)
        self.valid_count()

    def test_38_malformed_numeric_inputs_return_invalidity(self):
        invalid = ('not numeric', None, [], {}, True, complex(1, 2), 10 ** 1000,
                   float('nan'), float('inf'), float('-inf'))
        for value in invalid:
            for field in ('now', 'started', 'accepted', 'budget', 'units'):
                with self.subTest(value_type=type(value).__name__, field=field):
                    kwargs = {}
                    snapshot = S
                    if field == 'now':
                        kwargs['now'] = value
                    elif field == 'budget':
                        kwargs['policy'] = replace(POLICY, budget=value)
                    elif field == 'units':
                        snapshot = replace(S, rows=(replace(R, units=value),))
                    else:
                        snapshot = replace(S, **{field: value})
                    self.denied(snapshot, **kwargs)

    def test_39_malformed_revision_and_ordering_numbers(self):
        event = Event(A, 'E', 101, 'OPEN', replace(R, symbol='GBP_USD', trade_ids=('T2',)))
        coverage = Coverage((event,), 101, True)
        for value in ('101', [], {}, True, -1, 1.5, float('nan')):
            for field in ('generation', 'latest_generation', 'managed_revision',
                          'watermark', 'through', 'sequence'):
                with self.subTest(value_type=type(value).__name__, field=field):
                    kwargs = {}
                    snapshot = S
                    if field in ('generation', 'latest_generation', 'watermark'):
                        snapshot = replace(S, **{field: value})
                    elif field == 'managed_revision':
                        kwargs[field] = value
                    elif field == 'through':
                        kwargs['coverage'] = replace(coverage, through=value)
                    else:
                        kwargs['coverage'] = replace(coverage, events=(replace(event, sequence=value),))
                    self.denied(snapshot, **kwargs)

    def test_40_fill_transfer_cannot_drop_unrelated_occupied_slot(self):
        c = FakeCoordinator(view())
        c.reserve('fill', 'GBP_USD', 'SELL', 'x')
        c.dispatch('fill')
        incoming = view(replace(S, rows=(replace(R, symbol='GBP_USD', trade_ids=('T2',)),)),
                        managed_revision=1)
        before = (c.view, dict(c.intents), c.revision, c._slots())
        self.assertTrue(incoming.valid)
        self.assertFalse(c.transfer_fill('fill', incoming))
        self.assertEqual((c.view, c.intents, c.revision, c._slots()), before)
        self.assertEqual(c.intents['fill'].state, 'DISPATCHING')
        self.assertIsNone(c.reserve('third', 'AUD_USD', 'SELL', 'x'))

    def test_41_fill_transfer_rejects_managed_revision_rollback(self):
        c = FakeCoordinator(view(managed_revision=2))
        c.reserve('fill', 'GBP_USD', 'SELL', 'x')
        c.dispatch('fill')
        incoming = view(replace(S, rows=(R, replace(R, symbol='GBP_USD', trade_ids=('T2',)))),
                        managed_revision=1)
        before = (c.view, dict(c.intents), c.revision, c._slots())
        self.assertTrue(incoming.valid)
        self.assertFalse(c.transfer_fill('fill', incoming))
        self.assertEqual((c.view, c.intents, c.revision, c._slots()), before)

    def test_42_legitimate_fill_transfer_preserves_capacity_and_other_intents(self):
        for revision in (2, 3):
            with self.subTest(managed_revision=revision):
                c = FakeCoordinator(view(managed_revision=2))
                c.reserve('fill', 'GBP_USD', 'SELL', 'x')
                c.dispatch('fill')
                # A pending opposite-USD slot must also survive the transfer.
                self.assertIsNotNone(c.reserve('other', 'USD_JPY', 'SELL', 'y'))
                incoming = view(replace(S, rows=(R, replace(R, symbol='GBP_USD', trade_ids=('T2',)))),
                                managed_revision=revision)
                slots, old_revision = c._slots(), c.revision
                other = c.intents['other']
                self.assertTrue(c.transfer_fill('fill', incoming))
                self.assertEqual(c._slots(), slots)
                self.assertEqual(c.view.count('LONG'), 2)
                self.assertEqual(c.view.managed_revision, revision)
                self.assertEqual(c.revision, old_revision + 1)
                self.assertNotIn('fill', c.intents)
                self.assertEqual(c.intents['other'], other)
                self.assertIsNone(c.reserve('third', 'AUD_USD', 'SELL', 'x'))

    def test_43_fill_transfer_rejects_malformed_managed_revision(self):
        incoming = view(replace(S, rows=(R, replace(R, symbol='GBP_USD', trade_ids=('T2',)))))
        for revision in (True, None, '2', 2.0, -1):
            with self.subTest(revision=revision):
                c = FakeCoordinator(view())
                c.reserve('fill', 'GBP_USD', 'SELL', 'x')
                c.dispatch('fill')
                before = (c.view, dict(c.intents), c.revision, c._slots())
                # Guard against hand-constructed Decision objects bypassing evaluate.
                self.assertFalse(c.transfer_fill('fill', replace(incoming, managed_revision=revision)))
                self.assertEqual((c.view, c.intents, c.revision, c._slots()), before)

    def coordinator_state(self, c):
        return (c.view, dict(c.intents), c.generation, c.revision,
                c.refreshing, c.failed, c.available, c.deadline, c._slots(), c._valid())

    def test_44_publication_without_active_refresh_preserves_state(self):
        for incoming in (view(replace(S, rows=())), None):
            with self.subTest(success=incoming is not None):
                c = FakeCoordinator(view())
                c.reserve('a', 'GBP_USD', 'SELL', 'x')
                before = self.coordinator_state(c)
                self.assertFalse(c.publish(c.generation, incoming))
                self.assertEqual(self.coordinator_state(c), before)

    def test_45_success_completion_is_single_use(self):
        c = FakeCoordinator(view())
        c.reserve('a', 'GBP_USD', 'SELL', 'x')
        generation = c.refresh()
        accepted = view(replace(S, generation=generation, latest_generation=generation))
        self.assertTrue(c.publish(generation, accepted))
        before = self.coordinator_state(c)
        for incoming in (accepted, replace(accepted, slots=(), provenance=()), None):
            with self.subTest(success=incoming is not None):
                self.assertFalse(c.publish(generation, incoming))
                self.assertEqual(self.coordinator_state(c), before)

    def test_46_failure_completion_cannot_be_revived(self):
        for failure in (None, view(replace(S, status='FAILED'))):
            with self.subTest(failure=failure):
                c = FakeCoordinator(view())
                c.reserve('a', 'GBP_USD', 'SELL', 'x')
                generation = c.refresh()
                self.assertFalse(c.publish(generation, failure))
                self.assertTrue(c.failed)
                self.assertFalse(c.refreshing)
                before = self.coordinator_state(c)
                late = view(replace(S, generation=generation, latest_generation=generation))
                for incoming in (late, None):
                    self.assertFalse(c.publish(generation, incoming))
                    self.assertEqual(self.coordinator_state(c), before)
                self.assertFalse(c.dispatch('a'))

    def test_47_new_generation_can_complete_after_failed_generation(self):
        c = FakeCoordinator(view())
        c.reserve('a', 'GBP_USD', 'SELL', 'x')
        failed = c.refresh()
        self.assertFalse(c.publish(failed))
        generation = c.refresh()
        self.assertGreater(generation, failed)
        before = self.coordinator_state(c)
        old = view(replace(S, generation=failed, latest_generation=failed))
        self.assertFalse(c.publish(failed, old))
        self.assertEqual(self.coordinator_state(c), before)
        accepted = view(replace(S, generation=generation, latest_generation=generation))
        self.assertTrue(c.publish(generation, accepted))
        self.assertEqual(c.view, accepted)
        self.assertEqual(c.revision, before[3] + 1)
        self.assertFalse(c.refreshing)
        self.assertFalse(c.failed)
        self.assertTrue(c._valid())
        self.assertEqual(c.intents['a'].state, 'FROZEN')
        self.assertEqual(c._slots(), {('EUR_USD', 'SELL'), ('GBP_USD', 'SELL')})
        self.assertFalse(c.dispatch('a'))


class ConcurrencyTests(unittest.TestCase):
    """Bounded, explicitly scheduled thread tests; no timing sleeps or broker I/O."""

    def state(self, coordinator):
        return ContractTests.coordinator_state(self, coordinator)

    def workers(self, actions, first=None):
        gate = Barrier(len(actions) + 1)
        completed_first = ThreadEvent()
        results, errors = [None] * len(actions), [None] * len(actions)

        def run(index, action):
            try:
                gate.wait(timeout=5)
                if first is not None and index != first:
                    if not completed_first.wait(timeout=5):
                        raise TimeoutError('scheduled predecessor did not complete')
                results[index] = action()
            except BaseException as exc:
                errors[index] = exc
            finally:
                if index == first:
                    completed_first.set()

        threads = [Thread(target=run, args=(i, action), daemon=True)
                   for i, action in enumerate(actions)]
        try:
            for thread in threads:
                thread.start()
            gate.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=5)
            self.assertFalse(any(t.is_alive() for t in threads), 'worker deadlock/timeout')
            self.assertEqual(errors, [None] * len(actions), 'worker exception captured')
            return results
        finally:
            gate.abort()
            completed_first.set()

    def test_A_simultaneous_publications_and_both_serializations(self):
        for first in (None, 0, 1):
            with self.subTest(first=first):
                c = FakeCoordinator(view())
                c.reserve('pending', 'USD_JPY', 'SELL', 'x')
                generation = c.refresh()
                pending, revision = dict(c.intents), c.revision
                candidates = [view(replace(S, generation=generation, latest_generation=generation,
                              rows=(R, replace(R, symbol=symbol, trade_ids=(trade,)))))
                              for symbol, trade in (('GBP_USD', 'T2'), ('AUD_USD', 'T3'))]
                outcomes = self.workers([lambda i=i: c.publish(generation, candidates[i])
                                         for i in range(2)], first=first)
                self.assertEqual(sorted(outcomes), [False, True])
                winner = outcomes.index(True)
                if first is not None:
                    self.assertEqual(winner, first)
                self.assertIs(c.view, candidates[winner])
                self.assertEqual(c.revision, revision + 1)
                self.assertEqual(c.intents, pending)
                self.assertFalse(c.refreshing)
                self.assertFalse(c.failed)
                accepted_state = self.state(c)
                self.assertFalse(c.publish(generation, candidates[1 - winner]))
                self.assertEqual(self.state(c), accepted_state)

    def test_B_overlapping_refreshes_latest_generation_wins(self):
        for initially_failed in (False, True):
            with self.subTest(initially_failed=initially_failed):
                c = FakeCoordinator(view())
                c.reserve('pending', 'GBP_USD', 'SELL', 'x')
                if initially_failed:
                    self.assertFalse(c.publish(c.refresh()))
                before = self.state(c)
                older, newer = self.workers([c.refresh, c.refresh], first=0)
                self.assertEqual(newer, older + 1)
                self.assertEqual(c.generation, newer)
                self.assertEqual(c.revision, before[3] + 2)
                self.assertTrue(c.refreshing)
                self.assertEqual(c.failed, initially_failed)
                self.assertEqual(c.view, before[0])
                self.assertEqual(c._slots(), before[8])
                self.assertEqual(c.intents['pending'].state, 'FROZEN')
                superseded = self.state(c)
                old_view = view(replace(S, generation=older, latest_generation=older, rows=()))
                for candidate in (old_view, None):
                    self.assertFalse(c.publish(older, candidate))
                    self.assertEqual(self.state(c), superseded)
                latest = view(replace(S, generation=newer, latest_generation=newer))
                self.assertTrue(c.publish(newer, latest))
                self.assertEqual(c.revision, superseded[3] + 1)
                self.assertEqual(c.view, latest)
                self.assertEqual(c._slots(), before[8])
                self.assertEqual(c.intents, superseded[1])
                self.assertFalse(c.refreshing)
                self.assertFalse(c.failed)
                completed = self.state(c)
                self.assertFalse(c.publish(newer, old_view))
                self.assertEqual(self.state(c), completed)

    def test_C_failure_precedes_late_success_in_two_threads(self):
        c = FakeCoordinator(view())
        c.reserve('pending', 'GBP_USD', 'SELL', 'x')
        generation = c.refresh()
        original_view, original_slots, revision = c.view, c._slots(), c.revision
        late = view(replace(S, generation=generation, latest_generation=generation, rows=()))
        after_failure = []

        def fail():
            result = c.publish(generation)
            after_failure.append(self.state(c))
            return result

        self.assertEqual(self.workers([fail, lambda: c.publish(generation, late)], first=0),
                         [False, False])
        self.assertEqual(self.state(c), after_failure[0])
        self.assertEqual(c.revision, revision + 1)
        self.assertIs(c.view, original_view)
        self.assertEqual(c._slots(), original_slots)
        self.assertTrue(c.failed)
        self.assertFalse(c.refreshing)
        self.assertFalse(c._valid())
        failed_state = self.state(c)
        self.assertFalse(c.dispatch('pending'))
        self.assertIsNone(c.reserve('other', 'AUD_USD', 'SELL', 'x'))
        self.assertEqual(self.state(c), failed_state)
        newer = c.refresh()
        accepted = view(replace(S, generation=newer, latest_generation=newer))
        self.assertTrue(c.publish(newer, accepted))
        self.assertEqual(c.revision, revision + 3)
        self.assertFalse(c.failed)
        self.assertTrue(c._valid())
        self.assertEqual(c._slots(), original_slots)
        self.assertEqual(c.intents['pending'].state, 'FROZEN')

    def test_D_refresh_and_dispatch_both_lock_orders(self):
        for first in (0, 1):
            with self.subTest(first=first):
                c = FakeCoordinator(view())
                c.reserve('intent', 'GBP_USD', 'SELL', 'x')
                slots, revision = c._slots(), c.revision
                dispatched, generation = self.workers([lambda: c.dispatch('intent'), c.refresh], first=first)
                self.assertEqual(dispatched, first == 0)
                self.assertEqual(c.revision, revision + (2 if first == 0 else 1))
                self.assertEqual(c.intents['intent'].state, 'DISPATCHING' if first == 0 else 'FROZEN')
                self.assertEqual(c._slots(), slots)
                self.assertTrue(c.refreshing)
                self.assertEqual(c.generation, generation)
                before = self.state(c)
                self.assertFalse(c.dispatch('intent'))
                self.assertEqual(self.state(c), before)
                self.assertFalse(c.publish(generation))
                before = self.state(c)
                self.assertFalse(c.dispatch('intent'))
                self.assertEqual(self.state(c), before)
                self.assertEqual(c._slots(), slots)
                self.assertIn('intent', c.intents)

    def test_E_refresh_and_reservation_both_lock_orders(self):
        for first in (0, 1):
            with self.subTest(first=first):
                c = FakeCoordinator(view())
                before = self.state(c)
                reserved, generation = self.workers([
                    lambda: c.reserve('intent', 'GBP_USD', 'SELL', 'x'), c.refresh], first=first)
                self.assertEqual(reserved is not None, first == 0)
                self.assertEqual(c.revision, before[3] + (2 if first == 0 else 1))
                self.assertEqual(c.view, before[0])
                self.assertEqual(c.generation, generation)
                self.assertTrue(c.refreshing)
                self.assertIn(('EUR_USD', 'SELL'), c._slots())
                self.assertEqual(len(c._slots()), 2 if first == 0 else 1)
                if first == 0:
                    self.assertEqual(c.intents['intent'].state, 'FROZEN')
                else:
                    self.assertEqual(c.intents, {})
                active = self.state(c)
                self.assertIsNone(c.reserve('new', 'AUD_USD', 'SELL', 'y'))
                self.assertEqual(self.state(c), active)

    def test_F_rollover_stale_and_duplicate_completions(self):
        c = FakeCoordinator(view())
        c.reserve('sent', 'GBP_USD', 'SELL', 'x')
        c.dispatch('sent')
        initial_slots = c._slots()
        responses = []
        for fail, overlap in ((False, False), (True, False), (False, True), (False, False)):
            with self.subTest(fail=fail, overlap=overlap, prior_generation=c.generation):
                before = self.state(c)
                generation = c.refresh()
                issued = 1
                if overlap:
                    superseded = generation
                    generation = c.refresh()
                    issued += 1
                    responses.append((superseded, view(replace(S, generation=superseded,
                                                               latest_generation=superseded, rows=()))))
                active = self.state(c)
                for old_generation, old_view in responses:
                    self.assertFalse(c.publish(old_generation, old_view))
                    self.assertEqual(self.state(c), active)
                latest = view(replace(S, generation=generation, latest_generation=generation))
                self.assertEqual(c.publish(generation, None if fail else latest), not fail)
                self.assertEqual(c.revision, before[3] + issued + 1)
                self.assertFalse(c.refreshing)
                self.assertEqual(c.failed, fail)
                self.assertEqual(c._slots(), initial_slots)
                self.assertEqual(c.intents['sent'].state, 'DISPATCHING')
                responses.append((generation, latest))
                completed = self.state(c)
                for old_generation, old_view in responses:
                    self.assertFalse(c.publish(old_generation, old_view))
                    self.assertEqual(self.state(c), completed)

    def test_G_malformed_publish_generations_leave_active_refresh_unchanged(self):
        for malformed in (1.0, '1', True, None, [], {}, float('nan'), -1):
            with self.subTest(type=type(malformed).__name__):
                c = FakeCoordinator(view(replace(S, generation=0, latest_generation=0)))
                generation = c.refresh()
                incoming = view(replace(S, generation=generation, latest_generation=generation))
                before = self.state(c)
                self.assertFalse(c.publish(malformed, incoming))
                self.assertEqual(self.state(c), before)
                self.assertTrue(c.publish(generation, incoming))

    def test_H_current_generation_cannot_publish_managed_revision_rollback(self):
        c = FakeCoordinator(view(managed_revision=2))
        c.reserve('sent', 'GBP_USD', 'SELL', 'x')
        c.dispatch('sent')
        generation = c.refresh()
        before = self.state(c)
        rollback = view(replace(S, generation=generation, latest_generation=generation), managed_revision=1)
        self.assertTrue(rollback.valid)
        self.assertFalse(c.publish(generation, rollback))
        # A current-generation invalid completion consumes the refresh and fails;
        # it must not publish its stale view or remove intents/capacity.
        self.assertEqual(c.view, before[0])
        self.assertEqual(c.intents, before[1])
        self.assertEqual(c._slots(), before[8])
        self.assertEqual(c.revision, before[3] + 1)
        self.assertTrue(c.failed)
        self.assertFalse(c.refreshing)
        failed_state = self.state(c)
        self.assertFalse(c.publish(generation, rollback))
        self.assertEqual(self.state(c), failed_state)
        newer = c.refresh()
        accepted = view(replace(S, generation=newer, latest_generation=newer), managed_revision=2)
        self.assertTrue(c.publish(newer, accepted))
        self.assertEqual(c.view, accepted)
        self.assertEqual(c.intents, before[1])
        self.assertEqual(c._slots(), before[8])
        self.assertEqual(c.revision, before[3] + 3)

    def test_I_malformed_current_completion_consumes_failure_without_overwrite(self):
        for malformed in ('generation', 'revision_string', 'revision_bool', 'object'):
            with self.subTest(malformed=malformed):
                c = FakeCoordinator(view())
                c.reserve('intent', 'GBP_USD', 'SELL', 'x')
                generation = c.refresh()
                candidate = view(replace(S, generation=generation, latest_generation=generation))
                incoming = {
                    'generation': replace(candidate, generation=float(generation)),
                    'revision_string': replace(candidate, managed_revision='0'),
                    'revision_bool': replace(candidate, managed_revision=False),
                    'object': object(),
                }[malformed]
                before = self.state(c)
                self.assertFalse(c.publish(generation, incoming))
                self.assertEqual(c.view, before[0])
                self.assertEqual(c.intents, before[1])
                self.assertEqual(c._slots(), before[8])
                self.assertEqual(c.revision, before[3] + 1)
                self.assertTrue(c.failed)
                self.assertFalse(c.refreshing)
                failed = self.state(c)
                self.assertFalse(c.publish(generation, candidate))
                self.assertEqual(self.state(c), failed)


if __name__ == '__main__':
    unittest.main()
