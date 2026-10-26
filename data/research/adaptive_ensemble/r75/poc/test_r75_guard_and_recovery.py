"""R.75 universal close guard, recovery, and two-process tests."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import oanda_client  # noqa: E402
from forex_bot.broker_close_evidence import reset_close_evidence_state, run_guarded_live_close  # noqa: E402
from forex_bot.close_journal import (  # noqa: E402
    CloseSubmissionPermit,
    JournalUnavailable,
    account_binding,
    active_journal,
    arm_active_journal_fault,
    bootstrap_journal,
    reset_journal_process_state,
)
from forex_bot.oanda_exec import (  # noqa: E402
    CloseGuardRefusal,
    _place_market_order_sync,
    _submit_position_close_body,
    execute_oanda_market_close,
)
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.position_recovery import (  # noqa: E402
    classify_broker_discovery,
    durable_positions,
    evaluate_durable_row,
    persist_bot_position,
    quarantined_positions,
    recover_managed_book,
    reset_recovery_memory,
    store_incomplete_position,
)
from forex_bot.positions import (  # noqa: E402
    Position,
    broker_observations,
    position_management_permitted,
    positions,
)
from forex_bot.trading import execute_trade  # noqa: E402
import forex_bot.config as config_mod  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WORKER = Path(__file__).with_name("close_worker.py")
BINDING = account_binding(ACCOUNT)


class RecordingAPI:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def request(self, request_obj):
        name = type(request_obj).__name__
        self.calls.append(name)
        if name == "TransactionDetails":
            return {
                "transaction": {
                    "id": "TX1",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "-1000",
                    "tradesClosed": [{"tradeID": "T1", "units": "1000"}],
                }
            }
        if name != "PositionClose":
            raise isolation.IsolationBreach(name)
        return {"longOrderFillTransaction": {"id": "TX1", "type": "ORDER_FILL", "instrument": "EUR_USD", "units": "-1000"}}


def _position(**kwargs) -> Position:
    data = dict(
        symbol="EUR_USD",
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=1.0,
        strategy_name="existing_strategy",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids="T1",
        broker_order=True,
        position_instance_id="instance-a",
        position_generation=1,
        max_profit_pips=0.0,
        profit_protection_active=False,
        profit_protection_close_attempt_ts=0.0,
        min_profit_pips=0.0,
        max_adverse_pips=0.0,
    )
    data.update(kwargs)
    return Position(**data)


def _view(trades, snapshot="COMPLETE_NONEMPTY"):
    return {"snapshot": snapshot, "trades": trades}


def _trade(**kwargs):
    data = dict(trade_id="T1", instrument="EUR_USD", direction="BUY", units="1000", account_binding=BINDING)
    data.update(kwargs)
    return data


class GuardTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["OANDA_MAX_RETRIES"] = "1"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "closes.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        bootstrap_journal(self.path, acknowledge_empty=True).close()
        reset_journal_process_state()
        reset_recovery_memory()
        reset_close_evidence_state()
        reset_oanda_rate_limiter_for_tests()
        positions.clear()
        broker_observations.clear()
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
        self.api = RecordingAPI()
        oanda_client._api = self.api

    def tearDown(self) -> None:
        oanda_client._api = None
        reset_journal_process_state()
        reset_recovery_memory()
        positions.clear()
        broker_observations.clear()
        self.tmp.cleanup()

    def test_legacy_helpers_refuse_before_position_close(self) -> None:
        with self.assertRaises(RuntimeError):
            asyncio.run(execute_trade("EUR_USD", "existing_strategy", "BUY", 1000, 1.1, 1.0, 1.2, execution_kind="live"))
        with self.assertRaises(TypeError):
            asyncio.run(execute_oanda_market_close("EUR_USD", 1000, "BUY", 1.1, execution_kind="live"))
        with self.assertRaises(TypeError):
            _place_market_order_sync("EUR_USD", 1000, "BUY")
        with self.assertRaises(TypeError):
            _submit_position_close_body("EUR_USD", 1000, "BUY")
        forged = CloseSubmissionPermit(
            operation_id="not-real",
            owner_token="guess",
            account_binding=BINDING,
            instrument="EUR_USD",
            trade_id="T1",
            direction="BUY",
            requested_units="1000",
            position_instance_id="instance-a",
            position_generation=1,
        )
        with self.assertRaises(CloseGuardRefusal):
            _submit_position_close_body("EUR_USD", 1000, "BUY", forged)
        self.assertEqual(self.api.calls, [])

    def test_stale_and_repeat_permit_do_not_submit(self) -> None:
        row = _position()
        positions[row.symbol] = row
        operation = asyncio.run(run_guarded_live_close(row, reason="first"))
        self.assertEqual(operation.confirmation_state, "CLOSE_FULLY_CONFIRMED")
        self.assertEqual(self.api.calls.count("PositionClose"), 1)
        permit = CloseSubmissionPermit(
            operation_id=operation.operation_id,
            owner_token="stale-token",
            account_binding=operation.account_scope,
            instrument=operation.instrument,
            trade_id=operation.trade_ids[0],
            direction=operation.direction,
            requested_units="1000",
            position_instance_id=operation.position_instance_id,
            position_generation=operation.position_generation,
        )
        with self.assertRaises(CloseGuardRefusal):
            _submit_position_close_body("EUR_USD", 1000, "BUY", permit)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)

    def test_journal_failures_refuse_submission(self) -> None:
        row = _position()
        positions[row.symbol] = row
        missing = str(Path(self.tmp.name) / "absent.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = missing
        reset_journal_process_state()
        operation = asyncio.run(run_guarded_live_close(row, reason="missing"))
        self.assertEqual(operation.reason, "missing_journal")
        self.assertEqual(self.api.calls, [])

        corrupt = Path(self.tmp.name) / "corrupt.sqlite"
        corrupt.write_bytes(b"not a database")
        os.environ["CLOSE_JOURNAL_PATH"] = str(corrupt)
        reset_journal_process_state()
        operation = asyncio.run(run_guarded_live_close(row, reason="corrupt"))
        self.assertEqual(operation.reason, "corrupt_journal")
        self.assertEqual(self.api.calls, [])

        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        reset_journal_process_state()
        connection = sqlite3.connect(self.path)
        connection.execute("UPDATE schema_meta SET schema_version = 99")
        connection.commit()
        connection.close()
        reset_journal_process_state()
        operation = asyncio.run(run_guarded_live_close(row, reason="schema"))
        self.assertEqual(operation.reason, "unsupported_schema")
        self.assertEqual(self.api.calls, [])

    def test_unacknowledged_and_preexisting_do_not_submit(self) -> None:
        unacked = str(Path(self.tmp.name) / "unacked.sqlite")
        bootstrap_journal(unacked).close()
        os.environ["CLOSE_JOURNAL_PATH"] = unacked
        reset_journal_process_state()
        with self.assertRaises(JournalUnavailable) as caught:
            active_journal().reserve(
                account_binding_value=BINDING,
                position_instance_id="instance-a",
                position_generation=1,
                instrument="EUR_USD",
                trade_id="T1",
                direction="BUY",
                original_units="1000",
                requested_units="1000",
            )
        self.assertEqual(caught.exception.reason, "bootstrap_does_not_authorise_closes")
        blocked = str(Path(self.tmp.name) / "blocked.sqlite")
        bootstrap_journal(blocked, preexisting=((BINDING, "EUR_USD", "T1"),)).close()
        os.environ["CLOSE_JOURNAL_PATH"] = blocked
        reset_journal_process_state()
        row = _position()
        positions[row.symbol] = row
        operation = asyncio.run(run_guarded_live_close(row, reason="preexisting"))
        self.assertEqual(operation.error_classification, "preexisting_broker_position")
        self.assertEqual(self.api.calls, [])

    def test_journal_update_fault_does_not_submit(self) -> None:
        row = _position()
        positions[row.symbol] = row
        arm_active_journal_fault("before_reserve_commit")
        operation = asyncio.run(run_guarded_live_close(row, reason="fault"))
        self.assertEqual(operation.error_classification, "injected_before_reserve_commit")
        self.assertEqual(self.api.calls, [])

    def _recorder(self) -> str:
        path = str(Path(self.tmp.name) / "recorder.sqlite")
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE submissions (id INTEGER PRIMARY KEY, instrument TEXT, units TEXT)")
        connection.commit()
        connection.close()
        return path

    def _run_worker(self, command: str, extra: dict | None = None) -> subprocess.Popen:
        env = os.environ.copy()
        env["CLOSE_JOURNAL_PATH"] = self.path
        env["R75_RECORDER"] = self.recorder
        env["R75_INSTANCE"] = "instance-a"
        if extra:
            env.update(extra)
        return subprocess.Popen(
            [sys.executable, str(WORKER), command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    def test_two_processes_submit_once_through_the_guard(self) -> None:
        self.recorder = self._recorder()
        reset_journal_process_state()
        first = self._run_worker("close")
        second = self._run_worker("close")
        out1, err1 = first.communicate(timeout=30)
        out2, err2 = second.communicate(timeout=30)
        self.assertEqual(first.returncode, 0, err1)
        self.assertEqual(second.returncode, 0, err2)
        connection = sqlite3.connect(self.recorder)
        count = connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        connection.close()
        self.assertEqual(count, 1)
        reset_journal_process_state()
        again = self._run_worker("close")
        out3, err3 = again.communicate(timeout=30)
        self.assertEqual(again.returncode, 0, err3)
        connection = sqlite3.connect(self.recorder)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0], 1)
        connection.close()
        states = [json.loads(line)["state"] for line in (out1, out2, out3) for line in [line.strip().splitlines()[-1]]]
        self.assertIn("CLOSE_FULLY_CONFIRMED", states)

    def test_process_paused_after_claim_blocks_the_other(self) -> None:
        self.recorder = self._recorder()
        entered = str(Path(self.tmp.name) / "entered.txt")
        release = str(Path(self.tmp.name) / "release.txt")
        Path(release).write_text("wait", encoding="utf-8")
        reset_journal_process_state()
        holder = self._run_worker("close", {"R75_ENTERED": entered, "R75_RELEASE": release})
        deadline = 5
        import time

        started = time.time()
        while not Path(entered).exists():
            self.assertLess(time.time() - started, deadline)
            time.sleep(0.01)
        other = self._run_worker("close")
        out, err = other.communicate(timeout=30)
        self.assertEqual(other.returncode, 0, err)
        connection = sqlite3.connect(self.recorder)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0], 0)
        connection.close()
        self.assertNotEqual(json.loads(out.strip().splitlines()[-1])["state"], "CLOSE_FULLY_CONFIRMED")
        Path(release).write_text("go", encoding="utf-8")
        _stdout, err = holder.communicate(timeout=30)
        self.assertEqual(holder.returncode, 0, err)
        connection = sqlite3.connect(self.recorder)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0], 1)
        connection.close()


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "closes.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        bootstrap_journal(self.path, acknowledge_empty=True).close()
        reset_journal_process_state()
        reset_recovery_memory()
        positions.clear()
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT

    def tearDown(self) -> None:
        reset_journal_process_state()
        reset_recovery_memory()
        positions.clear()
        self.tmp.cleanup()

    def _base_row(self, **kwargs):
        row = dict(
            position_instance_id="instance-a",
            position_generation=1,
            account_binding=BINDING,
            instrument="EUR_USD",
            trade_id="T1",
            direction="BUY",
            units="1000",
            execution_kind="live",
            provenance="bot_managed",
            entry_price="1.1",
            stop_loss="1.05",
            take_profit="1.2",
            open_time="1",
            strategy_name="existing_strategy",
            rl_state="held",
            client_order_id="",
            broker_order_id="T1",
            broker_order=1,
            management_status="recorded",
            max_profit_pips="0",
            profit_protection_active=0,
            profit_protection_seeded=0,
            profit_protection_exit_pips=None,
            profit_protection_close_attempt_ts="0",
            atr_at_entry_pips=None,
            min_profit_pips="0",
            max_adverse_pips="0",
        )
        row.update(kwargs)
        return row

    def test_recovery_matrix(self) -> None:
        self.assertEqual(durable_positions(), [])
        self.assertEqual(classify_broker_discovery("broker_only")["state"], "observation")
        self.assertEqual(classify_broker_discovery("manual")["state"], "observation")
        self.assertEqual(positions, {})
        cases = [
            ("missing_journal_file_is_separate", None),
        ]
        del cases
        store_incomplete_position(self._base_row())
        matching = _view([_trade()])
        decision = evaluate_durable_row(durable_positions()[0], matching)
        self.assertEqual(decision["state"], "restored_managed")
        self.assertTrue(decision["manageable"])
        self.assertEqual(decision["close_submission_count"], 0)
        self.assertFalse(decision["delete_permitted"])
        published = recover_managed_book(matching)
        self.assertEqual(published[0]["published"], "managed")
        self.assertTrue(position_management_permitted(positions["EUR_USD"]))
        again = recover_managed_book(matching)
        self.assertEqual(again[0]["published"], "unchanged")
        self.assertEqual(decision["close_submission_count"], 0)
        positions.clear()
        reset_recovery_memory()
        for snapshot in ("INCOMPLETE", "COMPLETE_EMPTY", "MALFORMED", "STALE", "REQUEST_FAILED"):
            found = evaluate_durable_row(durable_positions()[0], _view([], snapshot=snapshot))
            self.assertEqual(found["state"], "quarantined")
            self.assertEqual(found["close_submission_count"], 0)
            self.assertFalse(found["delete_permitted"])
        mismatches = [
            _trade(account_binding="other"),
            _trade(instrument="GBP_USD"),
            _trade(trade_id="T9"),
            _trade(direction="SELL"),
            _trade(units="500"),
        ]
        for trade in mismatches:
            found = evaluate_durable_row(durable_positions()[0], _view([trade, _trade(trade_id="T2", instrument="EUR_USD")]))
            self.assertEqual(found["state"], "quarantined")
        one_wrong = evaluate_durable_row(durable_positions()[0], _view([_trade(units="500")]))
        self.assertEqual(one_wrong["reason"], "units_mismatch")
        self.assertTrue(one_wrong["operator_required"])

    def test_missing_protection_and_unknown_origin_are_quarantined(self) -> None:
        store_incomplete_position(self._base_row(max_profit_pips=None, position_instance_id="mfe"))
        store_incomplete_position(self._base_row(stop_loss=None, position_instance_id="stop", trade_id="T2"))
        store_incomplete_position(self._base_row(take_profit=None, position_instance_id="tp", trade_id="T3"))
        store_incomplete_position(self._base_row(provenance="manual", position_instance_id="manual", trade_id="T4"))
        store_incomplete_position(self._base_row(execution_kind="mystery", position_instance_id="mystery", trade_id="T5"))
        decisions = {item["reason"] for item in recover_managed_book(_view([_trade()]))}
        self.assertIn("missing_management_state", decisions)
        self.assertIn("manual", decisions)
        self.assertIn("unknown_execution_kind", decisions)
        self.assertNotIn("EUR_USD", positions)
        self.assertTrue(quarantined_positions)
        for pos in quarantined_positions.values():
            self.assertFalse(position_management_permitted(pos))

    def test_replaced_row_is_not_overwritten(self) -> None:
        store_incomplete_position(self._base_row())
        positions["EUR_USD"] = _position(position_instance_id="newer", position_generation=2, broker_trade_ids="T9")
        decision = recover_managed_book(_view([_trade()]))[0]
        self.assertEqual(decision["reason"], "replaced_local_position")
        self.assertEqual(positions["EUR_USD"].position_instance_id, "newer")

    def test_persist_then_restart_restores_the_same_identity(self) -> None:
        pos = _position()
        persist_bot_position(pos, BINDING)
        reset_journal_process_state()
        positions.clear()
        decision = recover_managed_book(_view([_trade()]))[0]
        self.assertEqual(decision["state"], "restored_managed")
        restored = positions["EUR_USD"]
        self.assertEqual(restored.position_instance_id, "instance-a")
        self.assertEqual(restored.broker_trade_ids, "T1")
        self.assertEqual(decision["close_submission_count"], 0)

    def test_duplicate_trade_is_refused(self) -> None:
        persist_bot_position(_position(), BINDING)
        with self.assertRaises(Exception):
            persist_bot_position(_position(position_instance_id="other"), BINDING)
        with self.assertRaises(Exception):
            store_incomplete_position(self._base_row())

    def test_restart_cases_stay_closed(self) -> None:
        for name, trade in (
            ("account", _trade(account_binding="other-binding")),
            ("instrument", _trade(instrument="GBP_USD")),
            ("trade", _trade(trade_id="T9")),
            ("direction", _trade(direction="SELL")),
        ):
            store_incomplete_position(self._base_row())
            decision = evaluate_durable_row(durable_positions()[0], _view([trade]))
            self.assertEqual(decision["state"], "quarantined", name)
            self.assertEqual(decision["close_submission_count"], 0)
            self.assertFalse(decision["delete_permitted"])
            reset_journal_process_state()
            Path(self.path).unlink()
            bootstrap_journal(self.path, acknowledge_empty=True).close()
            reset_journal_process_state()
            reset_recovery_memory()
            positions.clear()

        store_incomplete_position(
            self._base_row(profit_protection_active=1, position_instance_id="ratchet", trade_id="T8")
        )
        activated = evaluate_durable_row(durable_positions()[0], _view([_trade(trade_id="T8")]))
        self.assertEqual(activated["reason"], "missing_management_state")
        self.assertFalse(activated["manageable"])

        store_incomplete_position(
            self._base_row(
                position_instance_id="armed",
                trade_id="T7",
                profit_protection_active=1,
                profit_protection_exit_pips="12",
                protect_activated_mfe_pips="20",
                protect_activated_atr_pips="8",
                protect_activated_giveback_pips="4",
                protect_activated_exit_pips="12",
            )
        )
        armed = recover_managed_book(_view([_trade(trade_id="T7")]))
        self.assertIn("broker_trade_matches", [item["reason"] for item in armed], armed)
        armed_row = next(item for item in armed if item["reason"] == "broker_trade_matches")
        self.assertEqual(armed_row["state"], "restored_managed")
        self.assertEqual(positions["EUR_USD"].profit_protection_exit_pips, 12.0)
        self.assertEqual(armed_row["close_submission_count"], 0)

        positions.clear()
        reset_recovery_memory()
        journal = active_journal()
        record = journal.reserve(
            account_binding_value=BINDING,
            position_instance_id="other-instance",
            position_generation=1,
            instrument="EUR_USD",
            trade_id="T1",
            direction="BUY",
            original_units="1000",
            requested_units="1000",
        )
        journal.commit_submission_intent(record["operation_id"])
        journal.mark(
            record["operation_id"],
            confirmation_state="CLOSE_OUTCOME_AMBIGUOUS",
            submission_state="SENT",
            error_classification="timeout",
        )
        store_incomplete_position(self._base_row(position_instance_id="fresh", trade_id="T1"))
        disagreed = evaluate_durable_row(
            next(row for row in durable_positions() if row["position_instance_id"] == "fresh"),
            _view([_trade()]),
        )
        self.assertEqual(disagreed["reason"], "journal_position_disagreement")
        self.assertEqual(disagreed["close_submission_count"], 0)
        self.assertFalse(disagreed["delete_permitted"])

        partial_path = str(Path(self.tmp.name) / "partial.sqlite")
        bootstrap_journal(partial_path, acknowledge_empty=True).close()
        os.environ["CLOSE_JOURNAL_PATH"] = partial_path
        reset_journal_process_state()
        reset_recovery_memory()
        positions.clear()
        store_incomplete_position(self._base_row())
        journal = active_journal()
        partial = journal.reserve(
            account_binding_value=BINDING,
            position_instance_id="instance-a",
            position_generation=1,
            instrument="EUR_USD",
            trade_id="T1",
            direction="BUY",
            original_units="1000",
            requested_units="1000",
        )
        journal.commit_submission_intent(partial["operation_id"])
        journal.mark(
            partial["operation_id"],
            confirmation_state="CLOSE_PARTIALLY_CONFIRMED",
            submission_state="SENT",
            error_classification="partial_fill",
            confirmed_units="400",
            remaining_units="600",
        )
        partial_decision = evaluate_durable_row(durable_positions()[0], _view([_trade()]))
        self.assertEqual(partial_decision["reason"], "outstanding_CLOSE_PARTIALLY_CONFIRMED")
        self.assertEqual(partial_decision["close_submission_count"], 0)
        self.assertFalse(partial_decision["delete_permitted"])
        journal.mark(
            partial["operation_id"],
            confirmation_state="CLOSE_FULLY_CONFIRMED",
            submission_state="SENT",
            error_classification="",
            confirmed_units="1000",
            remaining_units="0",
            transaction_ids=("TX1",),
        )
        final_decision = evaluate_durable_row(durable_positions()[0], _view([_trade()]))
        self.assertEqual(final_decision["state"], "awaiting_finalisation")
        self.assertEqual(final_decision["reason"], "confirmed_close_not_finalised")
        self.assertEqual(final_decision["close_submission_count"], 0)
        self.assertFalse(final_decision["delete_permitted"])
        self.assertNotIn("EUR_USD", positions)

        generation_path = str(Path(self.tmp.name) / "generation.sqlite")
        bootstrap_journal(generation_path, acknowledge_empty=True).close()
        os.environ["CLOSE_JOURNAL_PATH"] = generation_path
        reset_journal_process_state()
        reset_recovery_memory()
        positions.clear()
        store_incomplete_position(self._base_row())
        positions["EUR_USD"] = _position(position_generation=4)
        replaced = recover_managed_book(_view([_trade()]))[0]
        self.assertEqual(replaced["reason"], "replaced_local_position")
        self.assertEqual(positions["EUR_USD"].position_generation, 4)
        self.assertEqual(replaced["close_submission_count"], 0)
        self.assertFalse(replaced["delete_permitted"])


if __name__ == "__main__":
    unittest.main()
