"""R.79 operational cycle and fencing tests. Synthetic broker only.

The cycle wrapper calls the real ``_execute_bot_cycle``. It does not replace it.
"""

from __future__ import annotations

import asyncio
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import bot_loop, oanda_client  # noqa: E402
from forex_bot.broker_entry_evidence import classify_entry_response  # noqa: E402
from forex_bot.close_journal import (  # noqa: E402
    SCHEMA_VERSION,
    CloseSubmissionPermit,
    JournalUnavailable,
    account_binding,
    bootstrap_journal,
    open_journal,
    reset_journal_process_state,
)
from forex_bot.entry_capture import record_entry_response  # noqa: E402
from forex_bot.entry_journal import EntryGuardRefusal, begin_entry_submission  # noqa: E402
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import (  # noqa: E402
    CloseGuardRefusal,
    _submit_order_create,
    _submit_position_close_body,
)
from forex_bot.position_recovery import publish_recovered, recover_managed_book  # noqa: E402
from forex_bot.positions import Position, positions  # noqa: E402
from forex_bot.startup_recovery import (  # noqa: E402
    RECOVERY_BLOCKED,
    RECOVERY_COMPLETED,
    execute_startup_sequence,
    live_management_permitted,
    recovery_fence_allows_publication,
    reset_startup_recovery_memory,
)
from forex_bot.state import state as state_dict  # noqa: E402
from decimal import Decimal  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WRITES = {"OrderCreate", "PositionClose", "TradeClose", "TradeCRCDO", "OrderCancel", "OrderReplace"}
MARKER = (
    ROOT
    / "data"
    / "research"
    / "adaptive_ensemble"
    / "r56"
    / "phase6_connection_enablement"
    / "real_activation"
    / "one_session.consumed"
)
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


class SyntheticBroker:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._request_params: dict = {}

    def request(self, request_obj):
        name = type(request_obj).__name__
        self.calls.append(name)
        if name in WRITES:
            raise AssertionError(f"broker write intercepted: {name}")
        if name == "AccountSummary":
            return {
                "account": {
                    "id": ACCOUNT,
                    "NAV": "10000",
                    "balance": "10000",
                    "currency": "USD",
                    "marginAvailable": "10000",
                }
            }
        return {"prices": []}


class OperationalCycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "r79.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        os.environ["EXECUTION_MODE"] = "paper"
        reset_journal_process_state()
        reset_startup_recovery_memory()
        positions.clear()
        self.journal = bootstrap_journal(self.path, acknowledge_empty=True)
        self.binding = account_binding(ACCOUNT)
        self.broker = SyntheticBroker()
        oanda_client._api = self.broker
        self.cycle_calls = 0
        self.original_cycle = bot_loop._execute_bot_cycle
        state_dict.pop("last_bot_cycle_utc", None)

        async def traced(symbols):
            self.cycle_calls += 1
            await self.original_cycle(symbols)

        bot_loop._execute_bot_cycle = traced

    def tearDown(self) -> None:
        bot_loop._execute_bot_cycle = self.original_cycle
        oanda_client._api = None
        reset_startup_recovery_memory()
        reset_journal_process_state()
        try:
            self.journal.close()
        except Exception:
            pass
        positions.clear()
        self.temp.cleanup()

    def _empty(self) -> dict:
        return {"snapshot": "COMPLETE_EMPTY", "trades": []}

    def _run(self, view: dict, symbols: list[str] | None = None) -> dict:
        return asyncio.run(
            bot_loop.run_startup_and_one_iteration(symbols if symbols is not None else [], broker_view=view)
        )

    def test_01_real_cycle_follows_empty_startup(self) -> None:
        report = self._run(self._empty(), ["EUR_USD"])
        self.assertEqual(report["state"], RECOVERY_COMPLETED)
        self.assertEqual(self.cycle_calls, 1)
        self.assertIn("last_bot_cycle_utc", state_dict)
        self.assertTrue(live_management_permitted())
        self.assertEqual([name for name in self.broker.calls if name in WRITES], [])
        self.assertFalse(PERMIT.exists())

    def test_02_blocked_recovery_still_invokes_cycle_without_management(self) -> None:
        report = self._run({"snapshot": "INCOMPLETE", "trades": []})
        self.assertEqual(report["state"], RECOVERY_BLOCKED)
        self.assertEqual(self.cycle_calls, 1)
        self.assertFalse(live_management_permitted())
        self.assertEqual([name for name in self.broker.calls if name in WRITES], [])

    def test_03_null_epoch_cannot_publish_operationally(self) -> None:
        self.assertIsNone(__import__("forex_bot.startup_recovery", fromlist=["current_fencing_epoch"]).current_fencing_epoch())
        self.assertFalse(recovery_fence_allows_publication())
        row = {
            "position_id": "pos-r79",
            "instrument": "EUR_USD",
            "direction": "BUY",
            "units": "1000",
            "entry_price": "1.1",
            "stop_loss": "1.0",
            "take_profit": "1.2",
            "broker_trade_id": "T-1",
            "broker_order_id": "O-1",
            "entry_client_order_id": "client-r79",
            "account_binding": self.binding,
            "provenance": "bot_managed",
            "ownership_state": "bot_managed",
            "position_instance_id": "INST-R79",
            "position_generation": 1,
            "trade_id": "T-1",
            "execution_kind": "live",
        }
        published = publish_recovered(row, {"manageable": True, "state": "restore", "reason": "match"})
        self.assertEqual(published["reason"], "recovery_authority_absent")
        self.assertNotIn("EUR_USD", positions)

    def test_04_offline_reconstruction_does_not_grant_management(self) -> None:
        pos = Position(
            symbol="EUR_USD",
            direction="BUY",
            units=1000.0,
            entry_price=1.1,
            stop_loss=1.09,
            take_profit=1.12,
            open_time=1.0,
            strategy_name="r79",
            rl_state="held",
            execution_kind="live",
            client_order_id="CID-R79",
            broker_order_id="",
            broker_trade_ids="T-TRADE",
            position_instance_id="INST-R79",
            position_generation=1,
            max_profit_pips=0.0,
            profit_protection_active=False,
            min_profit_pips=0.0,
            max_adverse_pips=0.0,
        )
        from forex_bot.position_recovery import persist_bot_position

        persist_bot_position(pos, self.binding)
        positions.clear()
        decisions = recover_managed_book(
            {
                "snapshot": "COMPLETE",
                "trades": [
                    {
                        "trade_id": "T-TRADE",
                        "instrument": "EUR_USD",
                        "direction": "BUY",
                        "units": "1000",
                        "account_binding": self.binding,
                        "provenance": "broker_snapshot_single_trade",
                    }
                ],
            }
        )
        self.assertTrue(decisions)
        self.assertFalse(live_management_permitted())
        self.assertFalse(recovery_fence_allows_publication())

    def test_05_stale_epoch_blocks_publish_and_management(self) -> None:
        report = self._run(self._empty())
        self.assertEqual(report["state"], RECOVERY_COMPLETED)
        self.journal._conn.execute("UPDATE recovery_authority SET fencing_epoch = fencing_epoch + 1")
        self.assertFalse(live_management_permitted())
        published = publish_recovered(
            {
                "instrument": "EUR_USD",
                "direction": "BUY",
                "units": "1",
                "entry_price": "1.1",
                "stop_loss": "1.0",
                "take_profit": "1.2",
                "trade_id": "T-2",
                "position_instance_id": "INST-2",
                "position_generation": 1,
                "account_binding": self.binding,
                "provenance": "bot_managed",
                "execution_kind": "live",
            },
            {"manageable": True},
        )
        self.assertEqual(published["reason"], "recovery_fence_lost")

    def test_06_entry_and_close_sinks_refuse_without_authority(self) -> None:
        permit = begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-R79",
            position_generation=1,
            client_order_id="client-r79",
            strategy_name="r79",
            stop_loss="1.09",
            take_profit="1.12",
            entry_reference="decision-r79",
            atr_at_entry_pips="8",
        )
        with self.assertRaises(EntryGuardRefusal):
            _submit_order_create("EUR_USD", 1000, "BUY", "client-r79", 1.09, 1.12, None, permit)
        close_permit = CloseSubmissionPermit(
            operation_id="close-r79",
            owner_token="owner",
            account_binding=self.binding,
            instrument="EUR_USD",
            trade_id="T-1",
            direction="BUY",
            requested_units="1000",
            position_instance_id="INST-R79",
            position_generation=1,
        )
        with self.assertRaises(CloseGuardRefusal) as refused:
            _submit_position_close_body("EUR_USD", 1000, "BUY", close_permit)
        self.assertIn("recovery authority", str(refused.exception))
        self.assertEqual([name for name in self.broker.calls if name in WRITES], [])

    def test_07_authorised_order_is_intercepted(self) -> None:
        import forex_bot.live_safety as live_safety

        self._run(self._empty())
        self.assertTrue(live_management_permitted())
        permit = begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-R79B",
            position_generation=1,
            client_order_id="client-r79b",
            strategy_name="r79",
            stop_loss="1.09",
            take_profit="1.12",
            entry_reference="decision-r79b",
            atr_at_entry_pips="8",
        )
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
        quote = mint_live_quote("EUR_USD")
        with self.assertRaises(Exception):
            _submit_order_create("EUR_USD", 1000, "BUY", "client-r79b", 1.09, 1.12, quote, permit)
        self.assertIn("OrderCreate", self.broker.calls)
        self.assertEqual(self.cycle_calls, 1)

    def test_08_capture_without_authority_keeps_the_durable_row(self) -> None:
        permit = begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-R79C",
            position_generation=1,
            client_order_id="client-r79c",
            strategy_name="r79",
            stop_loss="1.09",
            take_profit="1.12",
            entry_reference="decision-r79c",
            atr_at_entry_pips="8",
        )
        body = {
            "orderCreateTransaction": {"id": "O-ORDER"},
            "orderFillTransaction": {
                "id": "F-1",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "1000",
                "orderID": "O-ORDER",
                "price": "1.10000",
                "clientExtensions": {"id": "client-r79c"},
                "tradeOpened": {"tradeID": "T-TRADE", "units": "1000", "price": "1.10000"},
            },
        }
        evidence = record_entry_response(permit, body, account_id=ACCOUNT)
        self.assertEqual(evidence["publication_reason"], "recovery_authority_absent")
        self.assertFalse(evidence["published"])
        outcome = self.journal._conn.execute("SELECT outcome FROM entry_operations").fetchone()[0]
        self.assertEqual(outcome, "ENTRY_FINALISED")
        self.assertNotIn("EUR_USD", positions)
        classified = classify_entry_response(
            body,
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="client-r79c",
        )
        self.assertNotEqual(classified["broker_order_id"], classified["broker_trade_id"])

    def test_09_schema_and_isolation_probes(self) -> None:
        self.assertEqual(SCHEMA_VERSION, 5)
        legacy = Path(self.temp.name) / "v4.sqlite"
        legacy.write_bytes(self.journal._conn.execute("PRAGMA database_list").fetchone() and b"")
        import sqlite3

        connection = sqlite3.connect(legacy)
        connection.execute(
            "CREATE TABLE schema_meta (id INTEGER PRIMARY KEY, schema_version INTEGER NOT NULL, bootstrapped_at TEXT, closes_authorised INTEGER)"
        )
        connection.execute("INSERT INTO schema_meta (id, schema_version, bootstrapped_at, closes_authorised) VALUES (1, 4, 't', 1)")
        connection.commit()
        connection.close()
        with self.assertRaises(JournalUnavailable):
            open_journal(legacy)
        with self.assertRaises(isolation.IsolationBreach):
            socket.create_connection(("203.0.113.5", 9), timeout=0.2)
        self.assertEqual(hashlib_marker(), "e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c")
        self.assertFalse(PERMIT.exists())
        self.assertEqual(self.cycle_calls, 0)


    def test_10_snapshot_matrix_records_cycle_execution(self) -> None:
        cases = {
            "unavailable": {"snapshot": "UNAVAILABLE", "trades": []},
            "malformed": {"snapshot": "MALFORMED", "trades": []},
            "request_failed": {"snapshot": "REQUEST_FAILED", "trades": []},
            "stale": {"snapshot": "STALE", "trades": []},
            "unknown": {"snapshot": "UNKNOWN", "trades": []},
            "conflict": {"snapshot": "CONFLICT", "trades": []},
            "broker_only": {
                "snapshot": "COMPLETE",
                "trades": [{"trade_id": "T-BROKER", "provenance": "broker_only"}],
            },
            "manual": {
                "snapshot": "COMPLETE",
                "trades": [{"trade_id": "T-MANUAL", "provenance": "manual_or_external"}],
            },
        }
        for name, view in cases.items():
            with self.subTest(name=name):
                reset_startup_recovery_memory()
                before = self.cycle_calls
                report = self._run(view)
                self.assertEqual(self.cycle_calls, before + 1)
                if name in {"broker_only", "manual"}:
                    self.assertEqual(report["state"], "RECOVERY_COMPLETED_WITH_QUARANTINE")
                    self.assertTrue(report["decisions"])
                    self.assertFalse(any(item.get("manageable") for item in report["decisions"]))
                    self.assertNotIn("EUR_USD", positions)
                else:
                    self.assertEqual(report["state"], RECOVERY_BLOCKED)
                    self.assertFalse(live_management_permitted())
                self.assertEqual([call for call in self.broker.calls if call in WRITES], [])

    def test_11_authority_loss_before_a_second_cycle(self) -> None:
        self._run(self._empty())
        self.assertTrue(live_management_permitted())
        self.journal._conn.execute("UPDATE recovery_authority SET fencing_epoch = fencing_epoch + 1")
        self.assertFalse(live_management_permitted())
        before = self.cycle_calls
        state_dict.pop("last_bot_cycle_utc", None)
        asyncio.run(self.original_cycle([]))
        self.assertEqual(self.cycle_calls, before)
        self.assertIn("last_bot_cycle_utc", state_dict)
        self.assertFalse(live_management_permitted())
        self.assertEqual([name for name in self.broker.calls if name in WRITES], [])

    def test_12_restart_after_committed_recovery(self) -> None:
        first = self._run(self._empty())
        self.assertEqual(first["state"], RECOVERY_COMPLETED)
        reset_startup_recovery_memory()
        self.assertFalse(live_management_permitted())
        second = self._run(self._empty())
        self.assertEqual(second["state"], RECOVERY_COMPLETED)
        self.assertTrue(live_management_permitted())
        self.assertGreaterEqual(self.cycle_calls, 2)

    def test_13_lock_held_elsewhere_blocks_startup(self) -> None:
        import subprocess
        import time

        entered = Path(self.temp.name) / "entered.txt"
        release = Path(self.temp.name) / "release.txt"
        entered.write_text("wait", encoding="utf-8")
        release.write_text("wait", encoding="utf-8")
        worker = ROOT / "data" / "research" / "adaptive_ensemble" / "r78" / "poc" / "liveness_worker.py"
        env = os.environ.copy()
        env["R78_JOURNAL"] = self.path
        env["R78_ENTERED"] = str(entered)
        env["R78_RELEASE"] = str(release)
        process = subprocess.Popen([sys.executable, "-B", str(worker), "hold"], env=env, cwd=str(ROOT))
        try:
            deadline = time.time() + 10
            while entered.read_text(encoding="utf-8") != "held":
                if time.time() > deadline:
                    self.fail("lock holder did not start")
                time.sleep(0.02)
            report = execute_startup_sequence(self._empty())
            self.assertEqual(report["reason"], "recovery_already_in_progress")
            self.assertEqual(self.cycle_calls, 0)
            self.assertFalse(live_management_permitted())
        finally:
            release.write_text("go", encoding="utf-8")
            process.wait(timeout=10)

    def test_15_close_guard_still_confirms_once_after_recovery(self) -> None:
        from forex_bot.broker_close_evidence import run_guarded_live_close

        class RecordingAPI:
            def __init__(self) -> None:
                self.calls: list[str] = []
                self._request_params: dict = {}

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
                return {
                    "longOrderFillTransaction": {
                        "id": "TX1",
                        "type": "ORDER_FILL",
                        "instrument": "EUR_USD",
                        "units": "-1000",
                    }
                }

        self._run(self._empty())
        self.assertTrue(live_management_permitted())
        row = Position(
            symbol="EUR_USD",
            direction="BUY",
            units=1000.0,
            entry_price=1.1,
            stop_loss=1.05,
            take_profit=1.2,
            open_time=1.0,
            strategy_name="r79",
            rl_state="held",
            execution_kind="live",
            broker_trade_ids="T1",
            broker_order=True,
            position_instance_id="instance-a",
            position_generation=1,
            max_profit_pips=0.0,
            profit_protection_active=False,
            min_profit_pips=0.0,
            max_adverse_pips=0.0,
        )
        positions[row.symbol] = row
        os.environ["EXECUTION_MODE"] = "paper_broker"
        api = RecordingAPI()
        oanda_client._api = api
        operation = asyncio.run(run_guarded_live_close(row, reason="r79"))
        self.assertEqual(operation.confirmation_state, "CLOSE_FULLY_CONFIRMED")
        self.assertEqual(api.calls.count("PositionClose"), 1)
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
        self.assertEqual(api.calls.count("PositionClose"), 1)
        self.assertGreaterEqual(self.cycle_calls, 1)

    def test_14_corrupt_journal_blocks_before_management(self) -> None:
        self.journal.close()
        Path(self.path).write_bytes(b"not a sqlite database")
        reset_journal_process_state()
        report = self._run(self._empty())
        self.assertEqual(report["state"], RECOVERY_BLOCKED)
        self.assertEqual(self.cycle_calls, 1)
        self.assertFalse(live_management_permitted())


    def test_16_ambiguous_submit_is_not_retried_after_authority(self) -> None:
        from forex_bot.close_journal import arm_active_journal_fault
        from forex_bot.entry_journal import entry_row
        from forex_bot.oanda_exec import _place_market_order_open_sync
        import forex_bot.entry_capture as capture
        import forex_bot.live_safety as live_safety

        self._run(self._empty())
        self.assertTrue(live_management_permitted())
        permit = begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-R79D",
            position_generation=1,
            client_order_id="client-r79d",
            strategy_name="r79",
            stop_loss="1.09",
            take_profit="1.12",
            entry_reference="decision-r79d",
            atr_at_entry_pips="8",
        )
        os.environ["EXECUTION_MODE"] = "paper_broker"
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
        calls: list[str] = []

        def request(request_obj):
            name = type(request_obj).__name__
            calls.append(name)
            if name != "OrderCreate":
                raise isolation.IsolationBreach(name)
            return {
                "orderCreateTransaction": {"id": "O-ORDER"},
                "orderFillTransaction": {
                    "id": "F-1",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "1000",
                    "price": "1.10000",
                    "orderID": "O-ORDER",
                    "clientExtensions": {"id": "client-r79d"},
                    "tradeOpened": {"tradeID": "T-TRADE", "units": "1000", "price": "1.10000"},
                },
            }

        self.broker.request = request
        original = capture.record_entry_response

        def armed(permit_arg, body, *, account_id, retrieved_fill=None):
            arm_active_journal_fault("before_commit")
            return original(permit_arg, body, account_id=account_id, retrieved_fill=retrieved_fill)

        capture.record_entry_response = armed
        quote = mint_live_quote("EUR_USD")
        try:
            with self.assertRaises(JournalUnavailable):
                _place_market_order_open_sync(
                    "EUR_USD", 1000, "BUY", "client-r79d", 1.09, 1.12, quote, entry_permit=permit
                )
        finally:
            capture.record_entry_response = original
        self.assertEqual(calls, ["OrderCreate"])
        self.assertEqual(entry_row(permit.operation_id)["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertNotIn("EUR_USD", positions)

    def test_17_repeat_finalisation_does_not_lower_a_ratchet(self) -> None:
        from forex_bot.position_recovery import persist_protection_progress

        self._run(self._empty())
        permit = begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-R79E",
            position_generation=1,
            client_order_id="client-r79e",
            strategy_name="r79",
            stop_loss="1.09",
            take_profit="1.12",
            entry_reference="decision-r79e",
            atr_at_entry_pips="8",
        )
        body = {
            "orderCreateTransaction": {"id": "O-ORDER"},
            "orderFillTransaction": {
                "id": "F-1",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "1000",
                "price": "1.10000",
                "orderID": "O-ORDER",
                "clientExtensions": {"id": "client-r79e"},
                "tradeOpened": {"tradeID": "T-TRADE", "units": "1000", "price": "1.10000"},
            },
        }
        evidence = record_entry_response(permit, body, account_id=ACCOUNT)
        self.assertTrue(evidence["published"])
        positions["EUR_USD"].profit_protection_exit_pips = 3.5
        self.assertTrue(persist_protection_progress(positions["EUR_USD"], self.binding))
        record_entry_response(permit, body, account_id=ACCOUNT)
        exit_pips = self.journal._conn.execute(
            "SELECT profit_protection_exit_pips FROM managed_positions"
        ).fetchone()[0]
        self.assertEqual(Decimal(exit_pips), Decimal("3.5"))


def hashlib_marker() -> str:
    import hashlib

    return hashlib.sha256(MARKER.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main(verbosity=2)
