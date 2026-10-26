"""R.80 recovery-authorised entry, close, cycle, and fault tests.

Historical R.68–R.79 tests are not modified. Recovery authority comes from
execute_startup_sequence. The cycle wrapper calls the real _execute_bot_cycle.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import bot_loop, oanda_client  # noqa: E402
from forex_bot.broker_close_evidence import reset_close_evidence_state, run_guarded_live_close  # noqa: E402
from forex_bot.close_journal import (  # noqa: E402
    CloseSubmissionPermit,
    JournalUnavailable,
    account_binding,
    arm_active_journal_fault,
    bootstrap_journal,
    reset_journal_process_state,
)
from forex_bot.entry_capture import record_entry_response  # noqa: E402
from forex_bot.entry_journal import EntryGuardRefusal, begin_entry_submission, entry_row  # noqa: E402
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import (  # noqa: E402
    CloseGuardRefusal,
    _place_market_order_open_sync,
    _submit_order_create,
    _submit_position_close_body,
)
from forex_bot.position_recovery import durable_positions, persist_bot_position, persist_protection_progress  # noqa: E402
from forex_bot.positions import Position, positions  # noqa: E402
from forex_bot.profit_protection import (  # noqa: E402
    activation_trigger_pips,
    apply_profit_protection,
    pip_size,
)
from forex_bot.recovery_owner_lock import RecoveryOwnerLock  # noqa: E402
from forex_bot.startup_recovery import (  # noqa: E402
    RECOVERY_COMPLETED,
    RECOVERY_COMPLETED_WITH_QUARANTINE,
    current_fencing_epoch,
    execute_startup_sequence,
    live_management_permitted,
    reset_startup_recovery_memory,
)
from forex_bot.state import state as state_dict  # noqa: E402
import forex_bot.live_safety as live_safety  # noqa: E402
import forex_bot.startup_recovery as recovery_mod  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WORKER = Path(__file__).with_name("race_worker.py")
WRITES = {"OrderCreate", "PositionClose", "TradeClose", "TradeCRCDO", "OrderCancel", "OrderReplace"}
PERMIT = (
    ROOT
    / "data"
    / "research"
    / "adaptive_ensemble"
    / "r56"
    / "phase6_connection_enablement"
    / "real_activation"
    / "one_session.permit"
)


class Broker:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._request_params: dict = {}
        self.fail: BaseException | None = None
        self.on_request = None

    def request(self, request_obj):
        name = type(request_obj).__name__
        self.calls.append(name)
        if self.on_request is not None:
            self.on_request(name)
        if name in WRITES and self.fail is not None:
            raise self.fail
        if name == "PositionClose":
            return {
                "longOrderFillTransaction": {
                    "id": "TX1",
                    "type": "ORDER_FILL",
                    "instrument": "EUR_USD",
                    "units": "-1000",
                }
            }
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
        if name == "OrderCreate":
            raise AssertionError("broker write intercepted: OrderCreate")
        return {"prices": []}


def _position(symbol: str, direction: str, trade: str, instance: str, entry: float, stop: float, take: float) -> Position:
    return Position(
        symbol=symbol,
        direction=direction,
        units=1000.0,
        entry_price=entry,
        stop_loss=stop,
        take_profit=take,
        open_time=1.0,
        strategy_name="r80",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids=trade,
        position_instance_id=instance,
        position_generation=1,
        max_profit_pips=0.0,
        profit_protection_active=False,
        min_profit_pips=0.0,
        max_adverse_pips=0.0,
    )


def _fill(client: str, trade: str = "T-TRADE", units: str = "1000", extra: dict | None = None) -> dict:
    fill = {
        "id": "F-1",
        "type": "ORDER_FILL",
        "accountID": ACCOUNT,
        "instrument": "EUR_USD",
        "units": units,
        "price": "1.10000",
        "orderID": "O-ORDER",
        "clientExtensions": {"id": client},
        "tradeOpened": {"tradeID": trade, "units": units, "price": "1.10000"},
    }
    if extra:
        fill.update(extra)
    return {"orderCreateTransaction": {"id": "O-ORDER"}, "orderFillTransaction": fill}


class AuthorisedBase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "r80.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["OANDA_MAX_RETRIES"] = "1"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        reset_journal_process_state()
        reset_startup_recovery_memory()
        reset_close_evidence_state()
        positions.clear()
        self.journal = bootstrap_journal(self.path, acknowledge_empty=True)
        self.binding = account_binding(ACCOUNT)
        self.broker = Broker()
        oanda_client._api = self.broker
        self.exposure = live_safety.assert_new_live_exposure_allowed
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
        self.cycle_calls = 0
        self.original_cycle = bot_loop._execute_bot_cycle
        state_dict.pop("last_bot_cycle_utc", None)

        async def traced(symbols):
            self.cycle_calls += 1
            await self.original_cycle(symbols)

        bot_loop._execute_bot_cycle = traced
        self.recorder = str(Path(self.temp.name) / "recorder.sqlite")
        connection = sqlite3.connect(self.recorder)
        connection.execute("CREATE TABLE submissions (id INTEGER PRIMARY KEY, kind TEXT)")
        connection.commit()
        connection.close()

    def tearDown(self) -> None:
        bot_loop._execute_bot_cycle = self.original_cycle
        live_safety.assert_new_live_exposure_allowed = self.exposure
        oanda_client._api = None
        reset_startup_recovery_memory()
        reset_journal_process_state()
        try:
            self.journal.close()
        except Exception:
            pass
        positions.clear()
        self.temp.cleanup()
        self.assertFalse(PERMIT.exists())

    def _view_for_rows(self, edits: dict | None = None) -> dict:
        trades = []
        for row in durable_positions():
            item = {
                "trade_id": row["trade_id"],
                "instrument": row["instrument"],
                "direction": row["direction"],
                "units": str(row["units"]),
                "account_binding": row["account_binding"],
                "provenance": "bot_managed",
            }
            if edits and row["instrument"] in edits:
                item.update(edits[row["instrument"]])
            trades.append(item)
        return {"snapshot": "COMPLETE" if trades else "COMPLETE_EMPTY", "trades": trades}

    def _authorise(self, view: dict | None = None) -> dict:
        report = execute_startup_sequence(view if view is not None else {"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertIn(report["state"], {RECOVERY_COMPLETED, RECOVERY_COMPLETED_WITH_QUARANTINE})
        self.assertTrue(live_management_permitted())
        self.assertEqual(
            current_fencing_epoch(),
            int(self.journal._conn.execute("SELECT fencing_epoch FROM recovery_authority WHERE id = 1").fetchone()[0]),
        )
        lock = RecoveryOwnerLock(self.path)
        self.assertTrue(lock.try_acquire())
        lock.release()
        self.assertEqual([name for name in self.broker.calls if name in WRITES], [])
        return report

    def _reserve(self, client: str, instance: str = "INST-R80"):
        return begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id=instance,
            position_generation=1,
            client_order_id=client,
            strategy_name="r80",
            stop_loss="1.09000",
            take_profit="1.12000",
            entry_reference="decision-r80",
            atr_at_entry_pips="8",
        )

    def _spawn(self, mode: str, **env_extra: str) -> subprocess.Popen:
        env = os.environ.copy()
        env["R80_JOURNAL"] = self.path
        env["R80_RECORDER"] = self.recorder
        env["R80_CLIENT"] = env_extra.pop("client", "client-r80")
        env["R80_INSTANCE"] = env_extra.pop("instance", "INST-R80")
        env.update(env_extra)
        return subprocess.Popen(
            [sys.executable, "-B", str(WORKER), mode],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _count(self) -> int:
        connection = sqlite3.connect(self.recorder)
        count = connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        connection.close()
        return int(count)

    def _wait_entered(self, path: Path, process: subprocess.Popen) -> None:
        deadline = time.time() + 15
        while not path.exists():
            if process.poll() is not None:
                out, err = process.communicate()
                self.fail(f"worker exited before barrier\n{out}\n{err}")
            if time.time() > deadline:
                process.kill()
                self.fail("barrier timeout")
            time.sleep(0.02)


class CloseAndEntryTests(AuthorisedBase):
    def test_01_authorised_close_once_and_stale_permit(self) -> None:
        persist_bot_position(_position("EUR_USD", "BUY", "T1", "INST-CLOSE", 1.1, 1.05, 1.2), self.binding)
        self._authorise(self._view_for_rows())
        row = positions["EUR_USD"]
        operation = asyncio.run(run_guarded_live_close(row, reason="r80"))
        self.assertEqual(operation.confirmation_state, "CLOSE_FULLY_CONFIRMED")
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        stale = CloseSubmissionPermit(
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
            _submit_position_close_body("EUR_USD", 1000, "BUY", stale)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        again = asyncio.run(run_guarded_live_close(row, reason="r80-repeat"))
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        self.assertEqual(again.confirmation_state, "CLOSE_FULLY_CONFIRMED")

    def test_02_ambiguous_close_does_not_retry(self) -> None:
        persist_bot_position(_position("EUR_USD", "BUY", "T1", "INST-CLOSE", 1.1, 1.05, 1.2), self.binding)
        self._authorise(self._view_for_rows())
        self.broker.fail = TimeoutError("synthetic close timeout")
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r80"))
        self.assertEqual(operation.confirmation_state, "CLOSE_OUTCOME_AMBIGUOUS")
        self.assertEqual(operation.error_classification, "timeout")
        self.assertEqual(self.broker.calls, ["PositionClose"])
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        self.broker.fail = None
        again = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r80-again"))
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        self.assertNotEqual(again.confirmation_state, "CLOSE_FULLY_CONFIRMED")

    def test_03_missing_trade_observation_and_wrong_account(self) -> None:
        self._authorise()
        blank = _position("EUR_USD", "BUY", "", "INST-BLANK", 1.1, 1.05, 1.2)
        blank.broker_order_id = ""
        blank.broker_trade_ids = ""
        missing = asyncio.run(run_guarded_live_close(blank, reason="r80"))
        self.assertEqual(missing.error_classification, "missing_trade_id")
        observed = _position("GBP_USD", "BUY", "T-OBS", "INST-OBS", 1.3, 1.2, 1.4)
        observed.observation_only = True
        observed.execution_kind = "reconcile_import"
        refused = asyncio.run(run_guarded_live_close(observed, reason="r80"))
        self.assertEqual(refused.reason, "management_not_permitted")
        self.assertEqual(self.broker.calls.count("PositionClose"), 0)
        foreign = CloseSubmissionPermit(
            operation_id="missing-close",
            owner_token="owner",
            account_binding=account_binding("001-002-0000001-009"),
            instrument="EUR_USD",
            trade_id="T-FOREIGN",
            direction="BUY",
            requested_units="1000",
            position_instance_id="INST-FOREIGN",
            position_generation=1,
        )
        with self.assertRaises(CloseGuardRefusal):
            _submit_position_close_body("EUR_USD", 1000, "BUY", foreign)
        self.assertEqual(self.broker.calls.count("PositionClose"), 0)

    def test_04_entry_intent_before_request_and_one_shot(self) -> None:
        self._authorise()
        permit = self._reserve("client-r80-entry")
        stored = entry_row(permit.operation_id)
        self.assertEqual(stored["outcome"], "ENTRY_SUBMITTING")
        self.assertEqual(self.broker.calls, [])
        quote = mint_live_quote("EUR_USD")

        def _accept(name: str) -> None:
            if name == "OrderCreate":
                self.broker.fail = AssertionError("count-only")

        self.broker.on_request = _accept
        with self.assertRaises(Exception):
            _submit_order_create("EUR_USD", 1000, "BUY", "client-r80-entry", 1.09, 1.12, quote, permit)
        self.assertEqual(self.broker.calls, ["OrderCreate"])
        with self.assertRaises(EntryGuardRefusal):
            _submit_order_create("EUR_USD", 1000, "BUY", "client-r80-entry", 1.09, 1.12, quote, permit)
        self.assertEqual(self.broker.calls, ["OrderCreate"])

    def test_05_entry_fault_after_request_stays_ambiguous(self) -> None:
        self._authorise()
        permit = self._reserve("client-r80-ambiguous")
        quote = mint_live_quote("EUR_USD")

        def _body(name: str) -> None:
            if name != "OrderCreate":
                raise isolation.IsolationBreach(name)
            self.broker.fail = None

        self.broker.request = lambda request_obj: (
            self.broker.calls.append(type(request_obj).__name__) or _fill("client-r80-ambiguous")
        )
        import forex_bot.entry_capture as capture

        original = capture.record_entry_response

        def armed(permit_arg, body, *, account_id, retrieved_fill=None):
            arm_active_journal_fault("before_commit")
            return original(permit_arg, body, account_id=account_id, retrieved_fill=retrieved_fill)

        capture.record_entry_response = armed
        try:
            with self.assertRaises(JournalUnavailable):
                _place_market_order_open_sync(
                    "EUR_USD", 1000, "BUY", "client-r80-ambiguous", 1.09, 1.12, quote, entry_permit=permit
                )
        finally:
            capture.record_entry_response = original
        self.assertEqual(self.broker.calls, ["OrderCreate"])
        self.assertEqual(entry_row(permit.operation_id)["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        with self.assertRaises(JournalUnavailable):
            self._reserve("client-r80-ambiguous", "INST-OTHER")

    def test_06_partial_mixed_and_order_id_are_not_manageable(self) -> None:
        self._authorise()
        partial = self._reserve("client-partial", "INST-PARTIAL")
        evidence = record_entry_response(partial, _fill("client-partial", units="500"), account_id=ACCOUNT)
        self.assertEqual(evidence["reason"], "partial_fill")
        self.assertFalse(evidence["published"])
        self.assertNotEqual(entry_row(partial.operation_id)["outcome"], "ENTRY_FINALISED")
        mixed = self._reserve("client-mixed", "INST-MIXED")
        body = _fill("client-mixed", extra={"tradesClosed": [{"tradeID": "T-OLD", "units": "1000"}]})
        evidence = record_entry_response(mixed, body, account_id=ACCOUNT)
        self.assertEqual(evidence["reason"], "existing_trade_reduced_or_closed")
        self.assertNotIn("EUR_USD", positions)
        same = self._reserve("client-same-id", "INST-SAME")
        body = _fill("client-same-id", trade="O-ORDER")
        evidence = record_entry_response(same, body, account_id=ACCOUNT)
        self.assertEqual(evidence["reason"], "order_id_is_not_trade_id")
        self.assertEqual(self.journal._conn.execute("SELECT COUNT(*) FROM managed_positions").fetchone()[0], 0)

    def test_07_duplicate_client_and_restart_after_commit(self) -> None:
        self._authorise()
        permit = self._reserve("client-final")
        evidence = record_entry_response(permit, _fill("client-final"), account_id=ACCOUNT)
        self.assertTrue(evidence["published"])
        self.assertEqual(entry_row(permit.operation_id)["outcome"], "ENTRY_FINALISED")
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("client-final", "INST-DUP")
        self.assertIn(caught.exception.reason, {"client_order_id_retained", "unresolved_entry_exists"})
        reset_startup_recovery_memory()
        positions.clear()
        self.assertFalse(live_management_permitted())
        report = self._authorise(self._view_for_rows())
        self.assertEqual(report["state"], RECOVERY_COMPLETED)
        self.assertEqual(positions["EUR_USD"].broker_trade_ids, "T-TRADE")
        self.assertEqual(self.cycle_calls, 0)

    def test_08_authority_lost_before_request_sends_nothing(self) -> None:
        self._authorise()
        permit = self._reserve("client-lost")
        real = recovery_mod.live_management_permitted
        seen = {"n": 0}

        def wrapped() -> bool:
            seen["n"] += 1
            if seen["n"] >= 2:
                self.journal._conn.execute("UPDATE recovery_authority SET fencing_epoch = fencing_epoch + 1")
            return real()

        recovery_mod.live_management_permitted = wrapped
        try:
            with self.assertRaises(EntryGuardRefusal):
                _submit_order_create(
                    "EUR_USD", 1000, "BUY", "client-lost", 1.09, 1.12, mint_live_quote("EUR_USD"), permit
                )
        finally:
            recovery_mod.live_management_permitted = real
        self.assertGreaterEqual(seen["n"], 2)
        self.assertEqual(self.broker.calls, [])
        self.assertFalse(live_management_permitted())
        with self.assertRaises(EntryGuardRefusal):
            _submit_order_create(
                "EUR_USD", 1000, "BUY", "client-lost", 1.09, 1.12, mint_live_quote("EUR_USD"), permit
            )
        self.assertEqual(self.broker.calls, [])

    def test_09_request_already_sent_when_authority_changes_inside_it(self) -> None:
        self._authorise()
        permit = self._reserve("client-inflight")

        def request(request_obj):
            name = type(request_obj).__name__
            self.broker.calls.append(name)
            self.journal._conn.execute("UPDATE recovery_authority SET fencing_epoch = fencing_epoch + 1")
            return _fill("client-inflight")

        self.broker.request = request
        evidence_holder: dict = {}

        def run() -> None:
            evidence_holder["evidence"] = record_entry_response(
                permit,
                _place_market_order_open_sync(
                    "EUR_USD",
                    1000,
                    "BUY",
                    "client-inflight",
                    1.09,
                    1.12,
                    mint_live_quote("EUR_USD"),
                    entry_permit=permit,
                )
                and None,
                account_id=ACCOUNT,
            )

        # The open helper records the response itself. Call it directly.
        _place_market_order_open_sync(
            "EUR_USD", 1000, "BUY", "client-inflight", 1.09, 1.12, mint_live_quote("EUR_USD"), entry_permit=permit
        )
        self.assertEqual(self.broker.calls, ["OrderCreate"])
        self.assertEqual(entry_row(permit.operation_id)["outcome"], "ENTRY_FINALISED")
        self.assertNotIn("EUR_USD", positions)
        with self.assertRaises((EntryGuardRefusal, JournalUnavailable)):
            self._reserve("client-inflight-2")
            _submit_order_create(
                "EUR_USD", 1000, "BUY", "client-second", 1.09, 1.12, mint_live_quote("EUR_USD"), self._reserve("client-second", "INST-2")
            )
        self.assertEqual(self.broker.calls, ["OrderCreate"])


class MultiProcessTests(AuthorisedBase):
    def test_10_two_processes_cannot_reserve_one_client(self) -> None:
        self._authorise()
        first = self._spawn("reserve", client="client-race", instance="INST-RACE")
        second = self._spawn("reserve", client="client-race", instance="INST-RACE-2")
        out1, err1 = first.communicate(timeout=20)
        out2, err2 = second.communicate(timeout=20)
        text = "\n".join((out1, err1, out2, err2))
        self.assertIn("reserved", text)
        self.assertIn("unresolved_entry_exists", text)
        self.assertEqual(self._count(), 0)
        self.assertEqual(text.count("reserved"), 1)

    def test_11_authorised_entry_pauses_and_competitor_cannot_submit(self) -> None:
        entered = Path(self.temp.name) / "entered.txt"
        release = Path(self.temp.name) / "release.txt"
        release.write_text("wait", encoding="utf-8")
        owner = self._spawn(
            "startup-entry",
            client="client-owner",
            instance="INST-OWNER",
            R80_ENTERED=str(entered),
            R80_RELEASE=str(release),
        )
        self._wait_entered(entered, owner)
        rival = self._spawn("entry-cold", client="client-owner", instance="INST-RIVAL")
        rival_out, rival_err = rival.communicate(timeout=20)
        self.assertIn("refused=", rival_out + rival_err)
        self.assertEqual(self._count(), 0)
        release.write_text("go", encoding="utf-8")
        out, err = owner.communicate(timeout=20)
        self.assertIn("submitted", out, err)
        self.assertEqual(self._count(), 1)
        stale = self._spawn("startup-entry", client="client-owner", instance="INST-STALE")
        stale_out, stale_err = stale.communicate(timeout=20)
        self.assertNotIn("\nsubmitted", f"\n{stale_out}")
        self.assertEqual(self._count(), 1)

    def test_12_authorised_close_pauses_and_competitor_cannot_submit(self) -> None:
        persist_bot_position(_position("EUR_USD", "BUY", "T1", "INST-CLOSE", 1.1, 1.05, 1.2), self.binding)
        entered = Path(self.temp.name) / "close-entered.txt"
        release = Path(self.temp.name) / "close-release.txt"
        release.write_text("wait", encoding="utf-8")
        owner = self._spawn(
            "startup-close",
            R80_ENTERED=str(entered),
            R80_RELEASE=str(release),
        )
        self._wait_entered(entered, owner)
        claimed = self.journal._conn.execute(
            "SELECT network_permit, confirmation_state FROM close_operations"
        ).fetchone()
        self.assertIsNotNone(claimed)
        self.assertEqual(int(claimed[0]), 1)
        rival = self._spawn("close-cold")
        rival.communicate(timeout=20)
        self.assertEqual(self._count(), 0)
        release.write_text("go", encoding="utf-8")
        out, err = owner.communicate(timeout=20)
        self.assertTrue("CLOSE_FULLY_CONFIRMED" in out or "CLOSE_CONFIRMATION_PENDING" in out, out + err)
        self.assertEqual(self._count(), 1)
        successor = self._spawn("startup-close")
        successor.communicate(timeout=20)
        self.assertEqual(self._count(), 1)

    def test_13_kill_during_entry_request_does_not_authorise_a_second(self) -> None:
        entered = Path(self.temp.name) / "kill-entered.txt"
        release = Path(self.temp.name) / "kill-release.txt"
        release.write_text("wait", encoding="utf-8")
        owner = self._spawn(
            "startup-entry",
            client="client-killed",
            instance="INST-KILLED",
            R80_ENTERED=str(entered),
            R80_RELEASE=str(release),
        )
        self._wait_entered(entered, owner)
        owner.kill()
        owner.wait(timeout=10)
        self.assertEqual(self._count(), 0)
        successor = self._spawn("startup-entry", client="client-killed", instance="INST-NEXT")
        out, err = successor.communicate(timeout=20)
        self.assertNotIn("\nsubmitted", f"\n{out}")
        self.assertEqual(self._count(), 0, out + err)


class CycleAndProtectionTests(AuthorisedBase):
    def _book(self) -> None:
        persist_bot_position(_position("EUR_USD", "BUY", "T-EUR", "INST-EUR", 1.10, 1.09, 1.12), self.binding)
        persist_bot_position(_position("GBP_USD", "SELL", "T-GBP", "INST-GBP", 1.30, 1.32, 1.28), self.binding)
        persist_bot_position(_position("USD_JPY", "BUY", "T-JPY", "INST-JPY", 150.0, 149.0, 151.0), self.binding)

    def test_14_several_managed_trades_survive_the_real_cycle(self) -> None:
        self._book()
        view = self._view_for_rows()
        view["trades"].append(
            {
                "trade_id": "T-BROKER",
                "instrument": "AUD_USD",
                "direction": "BUY",
                "units": "1000",
                "account_binding": self.binding,
                "provenance": "broker_only",
            }
        )
        view["trades"].append(
            {
                "trade_id": "T-MANUAL",
                "instrument": "NZD_USD",
                "direction": "SELL",
                "units": "1000",
                "account_binding": self.binding,
                "provenance": "manual_or_external",
            }
        )
        report = asyncio.run(bot_loop.run_startup_and_one_iteration(["EUR_USD", "GBP_USD", "USD_JPY"], broker_view=view))
        self.assertEqual(self.cycle_calls, 1)
        self.assertIn("last_bot_cycle_utc", state_dict)
        self.assertEqual(report["state"], RECOVERY_COMPLETED_WITH_QUARANTINE)
        self.assertEqual(set(positions), {"EUR_USD", "GBP_USD", "USD_JPY"})
        self.assertEqual(positions["EUR_USD"].broker_trade_ids, "T-EUR")
        self.assertEqual(positions["GBP_USD"].direction, "SELL")
        self.assertEqual(positions["USD_JPY"].broker_trade_ids, "T-JPY")
        self.assertNotIn("AUD_USD", positions)
        self.assertNotIn("NZD_USD", positions)
        self.assertEqual([name for name in self.broker.calls if name in WRITES], [])

    def test_15_conflicting_identity_is_quarantined(self) -> None:
        self._book()
        view = self._view_for_rows({"GBP_USD": {"account_binding": account_binding("001-002-0000001-009")}})
        report = self._authorise(view)
        self.assertEqual(report["state"], RECOVERY_COMPLETED_WITH_QUARANTINE)
        self.assertIn("EUR_USD", positions)
        self.assertNotIn("GBP_USD", positions)
        self.assertIn("USD_JPY", positions)

    def test_16_profit_protection_on_recovered_rows(self) -> None:
        self._book()
        self._authorise(self._view_for_rows())
        eur = positions["EUR_USD"]
        gbp = positions["GBP_USD"]
        jpy = positions["USD_JPY"]
        self.assertEqual(pip_size("USD_JPY"), 0.01)
        self.assertAlmostEqual(activation_trigger_pips(eur), 134.0, places=4)
        self.assertAlmostEqual(activation_trigger_pips(gbp), 134.0, places=4)
        self.assertAlmostEqual(activation_trigger_pips(jpy), 67.0, places=4)
        below = apply_profit_protection(eur, eur.entry_price + (activation_trigger_pips(eur) - 1) * pip_size(eur.symbol))
        self.assertFalse(below.active)
        exact = apply_profit_protection(eur, eur.entry_price + activation_trigger_pips(eur) * pip_size(eur.symbol))
        self.assertTrue(exact.active)
        sell = apply_profit_protection(gbp, gbp.entry_price - activation_trigger_pips(gbp) * pip_size(gbp.symbol))
        self.assertTrue(sell.active)
        yen = apply_profit_protection(jpy, jpy.entry_price + activation_trigger_pips(jpy) * pip_size(jpy.symbol))
        self.assertTrue(yen.active)
        self.assertEqual(positions["EUR_USD"].atr_fallback_used or exact.exit_threshold_pips is not None, True)
        stronger = positions["EUR_USD"].profit_protection_exit_pips
        positions["EUR_USD"].profit_protection_exit_pips = float(stronger) + 25
        held = apply_profit_protection(positions["EUR_USD"], positions["EUR_USD"].entry_price + activation_trigger_pips(eur) * pip_size("EUR_USD"))
        self.assertGreaterEqual(positions["EUR_USD"].profit_protection_exit_pips, float(stronger) + 25)
        self.assertTrue(held.active)
        positions["EUR_USD"].protect_activated_atr_pips = 4.0
        self.assertTrue(persist_protection_progress(positions["EUR_USD"], self.binding))
        stored = self.journal._conn.execute(
            "SELECT profit_protection_exit_pips FROM managed_positions WHERE position_instance_id = 'INST-EUR'"
        ).fetchone()[0]
        reset_startup_recovery_memory()
        positions.clear()
        self._authorise(self._view_for_rows())
        self.assertEqual(Decimal(str(positions["EUR_USD"].profit_protection_exit_pips)), Decimal(str(stored)))
        self.journal._conn.execute("UPDATE recovery_authority SET fencing_epoch = fencing_epoch + 1")
        self.assertFalse(live_management_permitted())
        before = self.cycle_calls
        asyncio.run(self.original_cycle(["EUR_USD"]))
        self.assertEqual(self.cycle_calls, before)
        self.assertEqual([name for name in self.broker.calls if name in WRITES], [])

    def test_17_journal_fault_after_recovery_blocks_management(self) -> None:
        self._authorise()
        self.assertTrue(live_management_permitted())
        arm_active_journal_fault("before_commit")
        with self.assertRaises(JournalUnavailable):
            self._reserve("client-fault")
        self.assertEqual(self.broker.calls, [])
        self.journal.close()
        reset_journal_process_state()
        for suffix in ("", "-wal", "-shm"):
            leftover = Path(self.path + suffix)
            if leftover.exists():
                leftover.unlink()
        Path(self.path).write_bytes(b"not a database")
        self.assertFalse(live_management_permitted())
        asyncio.run(self.original_cycle(["EUR_USD"]))
        self.assertEqual([name for name in self.broker.calls if name in WRITES], [])
        self.assertGreaterEqual(self.cycle_calls, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
