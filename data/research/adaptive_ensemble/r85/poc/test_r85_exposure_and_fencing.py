"""R.85 partial-exposure reconciliation and publication fencing.

Isolation is imported before any operational module. The broker is synthetic.
Journals are disposable. Quarantine is not released.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import config as config_mod  # noqa: E402
from forex_bot import live_safety, oanda_client  # noqa: E402
from forex_bot import startup_recovery  # noqa: E402
from forex_bot.broker_close_evidence import (  # noqa: E402
    CLOSE_FULLY_CONFIRMED,
    CLOSE_OUTCOME_AMBIGUOUS,
    CLOSE_PARTIALLY_CONFIRMED,
    CLOSE_RECONCILIATION_REQUIRED,
    CloseReadError,
    apply_transaction_body,
    reset_close_evidence_state,
    resolve_from_retrieved_transaction,
    run_guarded_live_close,
)
from forex_bot.close_journal import (  # noqa: E402
    CloseJournal,
    account_binding,
    active_journal,
    bootstrap_journal,
    reset_journal_process_state,
)
from forex_bot.entry_capture import record_entry_response  # noqa: E402
from forex_bot.entry_journal import (  # noqa: E402
    ENTRY_FINALISED,
    begin_entry_submission,
    claim_entry_permit,
    entry_row,
)
from forex_bot.position_recovery import (  # noqa: E402
    durable_positions,
    evaluate_durable_row,
    quarantined_positions,
    symbol_has_quarantined_exposure,
)
from forex_bot.positions import positions  # noqa: E402
from forex_bot.positions import Position, close_confirmed_live_position, get_position  # noqa: E402
from forex_bot.startup_recovery import (  # noqa: E402
    RECOVERY_BLOCKED,
    RECOVERY_COMPLETED,
    RECOVERY_COMPLETED_WITH_QUARANTINE,
    current_fencing_epoch,
    execute_startup_sequence,
    live_management_permitted,
    reset_startup_recovery_memory,
)

ACCOUNT = "001-002-0000001-003"
WORKER = Path(__file__).resolve().parent / "race_worker.py"
PERMIT = ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.permit"
MARKER = ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.consumed"
GATES = (
    ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py",
    ROOT / "data/research/adaptive_ensemble/r59/live_session_gate.py",
    ROOT / "data/research/adaptive_ensemble/r60/live_session_gate.py",
    ROOT / "data/research/adaptive_ensemble/r61/live_session_gate.py",
)
UNCHANGED = {
    "forex_bot/oanda_exec.py": "e83bcc1095aba3f1c06cd625fb01fc0823698f348c0cd517d929928b559701c5",
    "forex_bot/startup_recovery.py": "69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658",
    "forex_bot/entry_journal.py": "961b3e167bbc8553a0febc2f8ace430e536ffce8389c1ab0a49227feaeb02dcd",
    "forex_bot/profit_protection.py": "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f",
}
WRITES = {"OrderCreate", "PositionClose"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Broker:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.transaction: dict = {}
        self.instrument = "EUR_USD"
        self._request_params: dict = {}

    def request(self, request_obj):
        name = type(request_obj).__name__
        if name not in WRITES | {
            "TransactionDetails",
            "AccountSummary",
            "InstrumentCandles",
            "InstrumentsCandles",
            "PricingInfo",
        }:
            raise isolation.IsolationBreach(name)
        self.calls.append(name)
        if name == "PositionClose":
            units = str(self.transaction.get("units") or "-1000")
            return {
                "longOrderFillTransaction": {
                    "id": "TX-R85",
                    "type": "ORDER_FILL",
                    "instrument": self.instrument,
                    "units": units,
                }
            }
        if name == "TransactionDetails":
            return {"transaction": self.transaction}
        return {"account": {"NAV": "10000", "balance": "10000"}, "candles": []}


class R85Base(unittest.TestCase):
    def setUp(self) -> None:
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        reset_journal_process_state()
        positions.clear()
        quarantined_positions.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "journal.sqlite")
        self.recorder = str(Path(self.temp.name) / "recorder.sqlite")
        connection = sqlite3.connect(self.recorder)
        connection.execute("CREATE TABLE submissions (id INTEGER PRIMARY KEY, kind TEXT)")
        connection.commit()
        connection.close()
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["OANDA_MAX_RETRIES"] = "1"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
        self.journal = bootstrap_journal(self.path, acknowledge_empty=True)
        self.binding = account_binding(ACCOUNT)
        self.broker = Broker()
        oanda_client._api = self.broker
        self.exposure = live_safety.assert_new_live_exposure_allowed
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
        self.original_finalise = CloseJournal.finalise
        self.original_fence = startup_recovery.recovery_fence_allows_publication
        report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertIn(report["state"], {RECOVERY_COMPLETED, RECOVERY_COMPLETED_WITH_QUARANTINE})

    def tearDown(self) -> None:
        CloseJournal.finalise = self.original_finalise
        startup_recovery.recovery_fence_allows_publication = self.original_fence
        live_safety.assert_new_live_exposure_allowed = self.exposure
        oanda_client._api = None
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        reset_journal_process_state()
        positions.clear()
        quarantined_positions.clear()
        try:
            self.journal.close()
        except Exception:
            pass
        self.temp.cleanup()
        self.assertFalse(PERMIT.exists())

    def _position(self, *, symbol: str = "EUR_USD", direction: str = "BUY", units: float = 1000.0) -> Position:
        return Position(
            symbol=symbol,
            direction=direction,
            units=units,
            entry_price=150.0 if symbol == "USD_JPY" else 1.1,
            stop_loss=149.0 if symbol == "USD_JPY" else 1.05,
            take_profit=151.0 if symbol == "USD_JPY" else 1.2,
            open_time=1.0,
            strategy_name="r85",
            rl_state="held",
            execution_kind="live",
            broker_trade_ids="T1",
            position_instance_id=f"INST-{symbol}-{direction}",
            position_generation=1,
            max_profit_pips=0.0,
            profit_protection_active=False,
            min_profit_pips=0.0,
            max_adverse_pips=0.0,
            profit_protection_exit_pips=40.0,
        )

    def _transaction(self, *, instrument: str, direction: str, kind: str) -> dict:
        sign = "-" if direction == "BUY" else ""
        full = f"{sign}1000"
        part = f"{sign}400"
        body = {
            "id": "TX-R85",
            "type": "ORDER_FILL",
            "accountID": ACCOUNT,
            "instrument": instrument,
            "units": full if kind == "full" else part,
        }
        if kind == "partial":
            body["tradeReduced"] = {"tradeID": "T1", "units": part}
        elif kind == "full":
            body["tradesClosed"] = [{"tradeID": "T1", "units": full}]
        elif kind == "ambiguous":
            pass
        return body

    def _close(self, *, symbol: str = "EUR_USD", direction: str = "BUY", kind: str = "partial"):
        self.broker.instrument = symbol
        self.broker.transaction = self._transaction(instrument=symbol, direction=direction, kind=kind)
        pos = self._position(symbol=symbol, direction=direction)
        positions[symbol] = pos
        operation = asyncio.run(run_guarded_live_close(pos, reason="r85"))
        return pos, operation

    def _row(self) -> dict:
        rows = active_journal()._conn.execute("SELECT * FROM close_operations").fetchall()
        self.assertEqual(len(rows), 1)
        return dict(rows[0])

    def _managed(self) -> dict:
        rows = durable_positions()
        self.assertEqual(len(rows), 1)
        return rows[0]

    def _view(self, **edits) -> dict:
        row = self._managed()
        trade = {
            "trade_id": row["trade_id"],
            "instrument": row["instrument"],
            "direction": row["direction"],
            "units": str(row["units"]),
            "account_binding": row["account_binding"],
            "provenance": "bot_managed",
        }
        trade.update(edits)
        return {"snapshot": "COMPLETE", "trades": [trade]}

    def _restart(self, view: dict) -> dict:
        reset_startup_recovery_memory()
        report = execute_startup_sequence(view)
        return report

    def _assert_quarantined(self, report: dict) -> None:
        self.assertIn(report["state"], {RECOVERY_COMPLETED_WITH_QUARANTINE, RECOVERY_BLOCKED})
        decisions = list(report.get("decisions") or [])
        self.assertFalse(any(bool(item.get("manageable")) for item in decisions))
        self.assertEqual(get_position("EUR_USD"), None)
        self.assertEqual(get_position("USD_JPY"), None)
        self.assertEqual([name for name in self.broker.calls if name == "PositionClose"], ["PositionClose"])

    def _writes(self) -> list[str]:
        connection = sqlite3.connect(self.recorder)
        rows = connection.execute("SELECT kind FROM submissions ORDER BY id").fetchall()
        connection.close()
        return [row[0] for row in rows]

    def _spawn(self, mode: str, **env_extra: str) -> subprocess.Popen:
        env = os.environ.copy()
        env["R85_JOURNAL"] = self.path
        env["R85_RECORDER"] = self.recorder
        env.update(env_extra)
        return subprocess.Popen(
            [sys.executable, "-B", str(WORKER), mode],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


class R85ExposureTests(R85Base):
    def test_01_baseline_hashes_and_gates(self) -> None:
        for relative, digest in UNCHANGED.items():
            self.assertEqual(_sha(ROOT / relative), digest, relative)
        for gate in GATES:
            text = gate.read_text(encoding="utf-8")
            self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", text)
        self.assertFalse(PERMIT.exists())
        self.assertEqual(_sha(MARKER), "e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c")
        self.assertEqual(
            _sha(R69 / "isolation.py"),
            "b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54",
        )

    def test_02_safety_gates_and_permit_absent(self) -> None:
        self.assertFalse(PERMIT.exists())
        self.assertEqual(self.broker.calls, [])

    def test_03_original_journal_memory_units_distinguished(self) -> None:
        _pos, operation = self._close()
        row = self._row()
        managed = self._managed()
        self.assertEqual(Decimal(managed["units"]), Decimal("1000"))
        self.assertEqual(Decimal(row["confirmed_units"]), Decimal("400"))
        self.assertEqual(Decimal(row["remaining_units"]), Decimal("600"))
        self.assertEqual(Decimal(str(positions["EUR_USD"].units)), Decimal("1000"))
        self.assertNotEqual(Decimal(managed["units"]), Decimal(row["remaining_units"]))
        self.assertEqual(operation.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)

    def test_04_partial_400_of_1000_baseline(self) -> None:
        _pos, operation = self._close()
        report = self._restart(self._view(units="600"))
        self._assert_quarantined(report)
        row = self._row()
        managed = self._managed()
        self.assertEqual(row["confirmation_state"], CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(int(row["network_permit"]), 1)
        self.assertEqual(Decimal(managed["units"]), Decimal("1000"))
        self.assertEqual(int(managed["position_generation"]), 1)
        self.assertEqual(Decimal(managed["profit_protection_exit_pips"]), Decimal("40"))
        self.assertEqual(operation.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(len(quarantined_positions), 1)
        stored = next(iter(quarantined_positions.values()))
        self.assertEqual(Decimal(str(stored.units)), Decimal("1000"))
        self.assertTrue(symbol_has_quarantined_exposure("EUR_USD"))

    def test_05_complete_snapshot_600_quarantined(self) -> None:
        self._close()
        decision = evaluate_durable_row(self._managed(), self._view(units="600"))
        self.assertEqual(decision["reason"], "units_mismatch")
        self.assertFalse(decision["manageable"])
        report = self._restart(self._view(units="600"))
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "units_mismatch")

    def test_06_complete_snapshot_1000_quarantined(self) -> None:
        self._close()
        report = self._restart(self._view(units="1000"))
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "outstanding_CLOSE_PARTIALLY_CONFIRMED")

    def test_07_complete_snapshot_400_quarantined(self) -> None:
        self._close()
        report = self._restart(self._view(units="400"))
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "units_mismatch")

    def test_08_complete_snapshot_zero_quarantined(self) -> None:
        self._close()
        report = self._restart(self._view(units="0"))
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "units_mismatch")

    def test_09_complete_snapshot_1200_quarantined(self) -> None:
        self._close()
        report = self._restart(self._view(units="1200"))
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "units_mismatch")

    def test_10_wrong_direction_quarantined(self) -> None:
        self._close()
        report = self._restart(self._view(direction="SELL", units="-600"))
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "direction_mismatch")

    def test_11_empty_complete_snapshot_quarantined(self) -> None:
        self._close()
        report = self._restart({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "broker_flat_unattributed")

    def test_12_empty_incomplete_snapshot_blocked(self) -> None:
        self._close()
        before = self._row()["confirmation_state"]
        report = self._restart({"snapshot": "INCOMPLETE", "trades": []})
        self.assertEqual(report["state"], RECOVERY_BLOCKED)
        self.assertEqual(report["reason"], "broker_snapshot_not_authoritative")
        self.assertEqual(self._row()["confirmation_state"], before)
        self.assertFalse(symbol_has_quarantined_exposure("EUR_USD") is False)

    def test_13_missing_target_trade_quarantined(self) -> None:
        self._close()
        report = self._restart(
            {
                "snapshot": "COMPLETE",
                "trades": [
                    {
                        "trade_id": "OTHER",
                        "instrument": "GBP_USD",
                        "direction": "BUY",
                        "units": "600",
                        "account_binding": self.binding,
                        "provenance": "broker_only",
                    }
                ],
            }
        )
        self._assert_quarantined(report)
        reasons = [item.get("reason") for item in report["decisions"]]
        self.assertIn("multiple_or_missing_trades", reasons)
        self.assertIn("broker_only", reasons)

    def test_14_wrong_account_quarantined(self) -> None:
        self._close()
        report = self._restart(self._view(account_binding="other-binding"))
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "account_mismatch")

    def test_15_wrong_instrument_quarantined(self) -> None:
        self._close()
        report = self._restart(self._view(instrument="GBP_USD"))
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "multiple_or_missing_trades")

    def test_16_wrong_trade_id_quarantined(self) -> None:
        self._close()
        report = self._restart(self._view(trade_id="T-OTHER"))
        self._assert_quarantined(report)
        reasons = [item.get("reason") for item in report["decisions"]]
        self.assertIn("trade_id_mismatch", reasons)

    def test_17_stale_snapshot_blocked(self) -> None:
        self._close()
        report = self._restart({"snapshot": "STALE", "trades": []})
        self.assertEqual(report["state"], RECOVERY_BLOCKED)
        self.assertEqual(report["reason"], "broker_snapshot_not_authoritative")
        decision = evaluate_durable_row(self._managed(), {"snapshot": "STALE", "trades": []})
        self.assertEqual(decision["reason"], "broker_snapshot_not_authoritative")
        self.assertFalse(decision["manageable"])

    def test_18_snapshot_retrieval_failure_blocked(self) -> None:
        self._close()
        report = self._restart({"snapshot": "REQUEST_FAILED", "trades": []})
        self.assertEqual(report["state"], RECOVERY_BLOCKED)
        self.assertEqual(self._row()["confirmation_state"], CLOSE_PARTIALLY_CONFIRMED)

    def test_19_incomplete_pagination_blocked(self) -> None:
        self._close()
        report = self._restart({"snapshot": "INCOMPLETE", "trades": []})
        self.assertEqual(report["state"], RECOVERY_BLOCKED)
        source = (ROOT / "forex_bot/startup_recovery.py").read_text(encoding="utf-8")
        self.assertNotIn("pagination", source.lower())

    def test_20_duplicate_trade_records_quarantined(self) -> None:
        self._close()
        trade = self._view()["trades"][0]
        report = self._restart({"snapshot": "COMPLETE", "trades": [trade, dict(trade)]})
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "multiple_or_missing_trades")

    def test_21_unrelated_trade_not_merged(self) -> None:
        self._close()
        target = self._view(units="1000")["trades"][0]
        extra = {
            "trade_id": "T-UNRELATED",
            "instrument": "GBP_USD",
            "direction": "SELL",
            "units": "50",
            "account_binding": self.binding,
            "provenance": "broker_only",
        }
        report = self._restart({"snapshot": "COMPLETE", "trades": [target, extra]})
        self._assert_quarantined(report)
        self.assertEqual(self._managed()["trade_id"], "T1")
        self.assertNotIn("T-UNRELATED", self._managed()["trade_id"])
        reasons = [item.get("reason") for item in report["decisions"]]
        self.assertIn("outstanding_CLOSE_PARTIALLY_CONFIRMED", reasons)
        self.assertIn("broker_only", reasons)

    def test_22_buy_partial_close(self) -> None:
        _pos, operation = self._close(direction="BUY")
        self.assertEqual(operation.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(Decimal(self._row()["confirmed_units"]), Decimal("400"))
        self.assertEqual(self._row()["direction"], "BUY")

    def test_23_sell_partial_close(self) -> None:
        _pos, operation = self._close(direction="SELL")
        self.assertEqual(operation.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(Decimal(self._row()["confirmed_units"]), Decimal("400"))
        self.assertEqual(self._row()["direction"], "SELL")
        report = self._restart(self._view(units="600"))
        self._assert_quarantined(report)

    def test_24_usd_jpy_partial_close(self) -> None:
        _pos, operation = self._close(symbol="USD_JPY", direction="BUY")
        self.assertEqual(operation.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(self._managed()["instrument"], "USD_JPY")
        self.assertEqual(Decimal(self._row()["remaining_units"]), Decimal("600"))
        report = self._restart(self._view(units="600"))
        self.assertFalse(any(bool(item.get("manageable")) for item in report["decisions"]))
        self.assertEqual(Decimal(self._managed()["profit_protection_exit_pips"]), Decimal("40"))

    def test_25_original_units_not_manageable(self) -> None:
        self._close()
        report = self._restart(self._view(units="1000"))
        self.assertFalse(report["decisions"][0]["manageable"])
        self.assertEqual(Decimal(self._managed()["units"]), Decimal("1000"))
        self.assertEqual(len(positions), 0)

    def test_26_no_manageable_exposure_overstatement(self) -> None:
        self._close()
        self._restart(self._view(units="600"))
        self.assertTrue(symbol_has_quarantined_exposure("EUR_USD"))
        self.assertIsNone(get_position("EUR_USD"))
        before = len(self.broker.calls)
        from forex_bot import bot_loop

        with self.assertLogs("forex_bot.bot_loop", level="INFO") as captured:
            asyncio.run(bot_loop._execute_bot_cycle(["EUR_USD"]))
        self.assertTrue(any("quarantined exposure" in line for line in captured.output))
        self.assertEqual([name for name in self.broker.calls[before:] if name in WRITES], [])

    def test_27_no_automatic_quarantine_release(self) -> None:
        self._close()
        for units in ("600", "1000", "400", "0"):
            report = self._restart(self._view(units=units))
            self.assertFalse(any(bool(item.get("manageable")) for item in report["decisions"]))
        source = (ROOT / "forex_bot/position_recovery.py").read_text(encoding="utf-8")
        self.assertNotIn("def release_quarantine", source)

    def test_28_release_contract_not_implemented(self) -> None:
        self._close()
        report = self._restart(self._view(units="600"))
        self.assertFalse(report["decisions"][0]["manageable"])
        self.assertEqual(self._row()["confirmation_state"], CLOSE_PARTIALLY_CONFIRMED)

    def test_29_entry_publication_race(self) -> None:
        entered = Path(self.temp.name) / "entered"
        release = Path(self.temp.name) / "release"
        calls = {"n": 0}

        def wrapped() -> bool:
            calls["n"] += 1
            if calls["n"] >= 2:
                entered.write_text("1", encoding="utf-8")
                deadline = time.time() + 15
                while not release.exists():
                    if time.time() > deadline:
                        break
                    time.sleep(0.05)
            return self.original_fence()

        startup_recovery.recovery_fence_allows_publication = wrapped
        permit = begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-ENTRY",
            position_generation=1,
            client_order_id="client-r85-entry",
            strategy_name="r85",
            stop_loss="1.09000",
            take_profit="1.12000",
            entry_reference="decision-r85",
            atr_at_entry_pips="8",
        )
        claim_entry_permit(permit)
        body = {
            "orderCreateTransaction": {"id": "O-R85", "accountID": ACCOUNT},
            "orderFillTransaction": {
                "id": "F-R85",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "1000",
                "price": "1.10000",
                "orderID": "O-R85",
                "tradeOpened": {"tradeID": "T-ENTRY", "units": "1000", "price": "1.10000"},
                "clientExtensions": {"id": permit.client_order_id},
            },
        }
        holder: dict = {}

        def publish() -> None:
            holder["evidence"] = record_entry_response(permit, body, account_id=ACCOUNT)

        thread = threading.Thread(target=publish)
        thread.start()
        deadline = time.time() + 15
        while not entered.exists():
            self.assertLess(time.time(), deadline)
            time.sleep(0.05)
        before = current_fencing_epoch()
        successor = self._spawn("successor", R85_VIEW="match")
        out, err = successor.communicate(timeout=20)
        release.write_text("1", encoding="utf-8")
        thread.join(timeout=15)
        self.assertEqual(successor.returncode, 0, err)
        self.assertFalse(holder["evidence"]["published"])
        self.assertNotIn("EUR_USD", positions)
        row = entry_row(permit.operation_id)
        self.assertEqual(row["outcome"], ENTRY_FINALISED)
        self.assertIn(f"epoch=", out)
        self.assertNotEqual(str(before), "")
        self.assertEqual(self._writes(), [])

    def test_30_close_removal_race(self) -> None:
        entered = Path(self.temp.name) / "entered"
        release = Path(self.temp.name) / "release"
        original = self.original_finalise

        def wrapped(journal, operation_id, *, expected_epoch=None):
            if expected_epoch is not None:
                entered.write_text("1", encoding="utf-8")
                deadline = time.time() + 15
                while not release.exists():
                    if time.time() > deadline:
                        break
                    time.sleep(0.05)
            return original(journal, operation_id, expected_epoch=expected_epoch)

        CloseJournal.finalise = wrapped
        _pos, operation = self._close(kind="full")
        self.assertEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        holder: dict = {}

        def remove() -> None:
            holder["removed"] = close_confirmed_live_position("EUR_USD", operation)

        thread = threading.Thread(target=remove)
        thread.start()
        deadline = time.time() + 15
        while not entered.exists():
            self.assertLess(time.time(), deadline)
            time.sleep(0.05)
        successor = self._spawn("successor", R85_VIEW="match")
        out, err = successor.communicate(timeout=20)
        release.write_text("1", encoding="utf-8")
        thread.join(timeout=15)
        self.assertEqual(successor.returncode, 0, err)
        self.assertIsNone(holder["removed"])
        self.assertEqual(self._row()["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        self.assertIn("EUR_USD", positions)
        self.assertIn("manageable=0", out)
        self.assertEqual([name for name in self.broker.calls if name == "PositionClose"], ["PositionClose"])

    def test_31_genuine_successor_while_owner_alive(self) -> None:
        entered = Path(self.temp.name) / "entered"
        release = Path(self.temp.name) / "release"
        original = self.original_finalise
        before = current_fencing_epoch()

        def wrapped(journal, operation_id, *, expected_epoch=None):
            if expected_epoch is not None:
                entered.write_text("1", encoding="utf-8")
                deadline = time.time() + 15
                while not release.exists():
                    if time.time() > deadline:
                        break
                    time.sleep(0.05)
            return original(journal, operation_id, expected_epoch=expected_epoch)

        CloseJournal.finalise = wrapped
        _pos, operation = self._close(kind="full")
        holder: dict = {}

        def remove() -> None:
            holder["removed"] = close_confirmed_live_position("EUR_USD", operation)

        thread = threading.Thread(target=remove)
        thread.start()
        deadline = time.time() + 15
        while not entered.exists():
            self.assertLess(time.time(), deadline)
            time.sleep(0.05)
        successor = self._spawn("successor", R85_VIEW="match")
        out, err = successor.communicate(timeout=20)
        release.write_text("1", encoding="utf-8")
        thread.join(timeout=15)
        self.assertEqual(successor.returncode, 0, err)
        self.assertIn("state=RECOVERY_COMPLETED_WITH_QUARANTINE", out)
        child_epoch = int(out.split("epoch=")[1].splitlines()[0])
        self.assertGreater(child_epoch, int(before))
        self.assertIsNone(holder["removed"])
        self.assertEqual(self._row()["confirmation_state"], CLOSE_FULLY_CONFIRMED)

    def test_32_synthetic_epoch_change_is_not_takeover(self) -> None:
        _pos, operation = self._close(kind="full")
        before = int(current_fencing_epoch())
        active_journal()._conn.execute(
            "UPDATE recovery_authority SET fencing_epoch = fencing_epoch + 1 WHERE id = 1"
        )
        active_journal()._conn.commit()
        removed = close_confirmed_live_position("EUR_USD", operation)
        self.assertIsNone(removed)
        self.assertEqual(self._row()["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        self.assertGreater(
            int(active_journal()._conn.execute("SELECT fencing_epoch FROM recovery_authority").fetchone()[0]),
            before,
        )

    def test_33_durable_entry_finalisation_preserved(self) -> None:
        self.test_29_entry_publication_race()
        rows = active_journal()._conn.execute("SELECT outcome FROM entry_operations").fetchall()
        self.assertEqual([row[0] for row in rows], [ENTRY_FINALISED])

    def test_34_durable_full_close_preserved(self) -> None:
        self._close(kind="full")
        self.assertEqual(self._row()["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        self.assertEqual(Decimal(self._row()["remaining_units"]), Decimal("0"))
        self.assertNotEqual(self._row()["confirmation_state"], "CLOSE_FINALISED")

    def test_35_no_duplicate_order_create(self) -> None:
        self._close()
        self._restart(self._view(units="600"))
        from forex_bot import bot_loop

        asyncio.run(bot_loop._execute_bot_cycle(["EUR_USD"]))
        self.assertNotIn("OrderCreate", self.broker.calls)

    def test_36_no_duplicate_position_close(self) -> None:
        self._close()
        self._restart(self._view(units="600"))
        self._restart(self._view(units="1000"))
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)

    def test_37_full_close_conflicting_snapshot(self) -> None:
        self._close(kind="full")
        report = self._restart(self._view(units="1000"))
        self._assert_quarantined(report)
        self.assertEqual(report["decisions"][0]["reason"], "confirmed_close_not_finalised")
        self.assertEqual(self._row()["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        report_reduced = self._restart(self._view(units="600"))
        self.assertEqual(report_reduced["decisions"][0]["reason"], "units_mismatch")

    def test_38_full_close_incomplete_snapshot(self) -> None:
        self._close(kind="full")
        report = self._restart({"snapshot": "INCOMPLETE", "trades": []})
        self.assertEqual(report["state"], RECOVERY_BLOCKED)
        empty = self._restart({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertEqual(empty["decisions"][0]["reason"], "broker_flat_unattributed")
        self.assertFalse(empty["decisions"][0]["manageable"])
        failed = self._restart({"snapshot": "REQUEST_FAILED", "trades": []})
        self.assertEqual(failed["state"], RECOVERY_BLOCKED)
        stale = self._restart({"snapshot": "STALE", "trades": []})
        self.assertEqual(stale["state"], RECOVERY_BLOCKED)
        self.assertEqual(self._row()["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)

    def test_39_ambiguous_original_units(self) -> None:
        _pos, operation = self._close(kind="ambiguous")
        self.assertNotEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertIn(operation.confirmation_state, {CLOSE_RECONCILIATION_REQUIRED, CLOSE_OUTCOME_AMBIGUOUS})
        report = self._restart(self._view(units="1000"))
        self._assert_quarantined(report)
        self.assertIsNone(self._row()["confirmed_units"])

    def test_40_ambiguous_reduced_units(self) -> None:
        self._close(kind="ambiguous")
        report = self._restart(self._view(units="600"))
        self._assert_quarantined(report)
        self.assertNotEqual(self._row()["confirmation_state"], CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)

    def test_41_ambiguous_flat_snapshot(self) -> None:
        self._close(kind="ambiguous")
        report = self._restart({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self._assert_quarantined(report)
        missing = self._restart(
            {
                "snapshot": "COMPLETE",
                "trades": [
                    {
                        "trade_id": "T-OTHER",
                        "instrument": "EUR_USD",
                        "direction": "BUY",
                        "units": "1000",
                        "account_binding": self.binding,
                        "provenance": "broker_only",
                    }
                ],
            }
        )
        self.assertFalse(any(bool(item.get("manageable")) for item in missing["decisions"]))
        blocked = self._restart({"snapshot": "INCOMPLETE", "trades": []})
        self.assertEqual(blocked["state"], RECOVERY_BLOCKED)
        wrong = self._restart(self._view(trade_id="T-OTHER"))
        self.assertIn("trade_id_mismatch", [item.get("reason") for item in wrong["decisions"]])
        stale = self._restart({"snapshot": "STALE", "trades": []})
        self.assertEqual(stale["state"], RECOVERY_BLOCKED)
        self.assertEqual(int(self._row()["network_permit"]), 1)

    def test_42_duplicate_transaction_replay(self) -> None:
        _pos, operation = self._close()
        body = {"transaction": self.broker.transaction}
        first = resolve_from_retrieved_transaction(operation.operation_id, body, account_id=ACCOUNT)
        second = resolve_from_retrieved_transaction(operation.operation_id, body, account_id=ACCOUNT)
        self.assertEqual(first, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(second, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(Decimal(self._row()["confirmed_units"]), Decimal("400"))
        self.assertEqual(Decimal(self._row()["remaining_units"]), Decimal("600"))

    def test_43_conflicting_transaction_replay(self) -> None:
        _pos, operation = self._close()
        conflict = {
            "transaction": {
                "id": "TX-OTHER",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "-1000",
                "tradesClosed": [{"tradeID": "T1", "units": "-1000"}],
            }
        }
        state = resolve_from_retrieved_transaction(operation.operation_id, conflict, account_id=ACCOUNT)
        self.assertEqual(state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(Decimal(self._row()["confirmed_units"]), Decimal("400"))
        wrong = {
            "transaction": {
                "id": "TX-R85",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "-400",
                "tradeReduced": {"tradeID": "T-WRONG", "units": "-400"},
            }
        }
        kept = resolve_from_retrieved_transaction(operation.operation_id, wrong, account_id=ACCOUNT)
        self.assertEqual(kept, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(Decimal(self._row()["confirmed_units"]), Decimal("400"))

    def test_44_operational_cycle_partial_quarantine(self) -> None:
        self._close()
        consistent = self._restart(self._view(units="600"))
        self.assertFalse(consistent["decisions"][0]["manageable"])
        from forex_bot import bot_loop

        with self.assertLogs("forex_bot.bot_loop", level="INFO") as captured:
            asyncio.run(bot_loop._execute_bot_cycle(["EUR_USD"]))
        self.assertTrue(any("quarantined exposure" in line for line in captured.output))
        conflict = self._restart(self._view(units="1000"))
        self.assertEqual(conflict["decisions"][0]["reason"], "outstanding_CLOSE_PARTIALLY_CONFIRMED")
        asyncio.run(bot_loop._execute_bot_cycle(["EUR_USD"]))
        self.assertNotIn("OrderCreate", self.broker.calls)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        self.assertEqual(Decimal(self._managed()["profit_protection_exit_pips"]), Decimal("40"))
        self.assertEqual(int(self._row()["network_permit"]), 1)

    def test_45_profit_protection_ratchet_preserved(self) -> None:
        self.assertEqual(UNCHANGED["forex_bot/profit_protection.py"], _sha(ROOT / "forex_bot/profit_protection.py"))
        self._close()
        self._restart(self._view(units="600"))
        self.assertEqual(Decimal(self._managed()["profit_protection_exit_pips"]), Decimal("40"))
        text = (ROOT / "forex_bot/profit_protection.py").read_text(encoding="utf-8")
        self.assertIn("0.67", text)
        self.assertIn("0.5", text)

    def test_46_process_termination_cannot_finalise(self) -> None:
        entered = Path(self.temp.name) / "entered"
        release = Path(self.temp.name) / "release"
        worker = self._spawn(
            "pause-after-full",
            R85_ENTERED=str(entered),
            R85_RELEASE=str(release),
        )
        deadline = time.time() + 20
        while not entered.exists():
            self.assertLess(time.time(), deadline)
            time.sleep(0.05)
        worker.kill()
        worker.communicate(timeout=10)
        successor = self._spawn("successor", R85_VIEW="match")
        out, err = successor.communicate(timeout=20)
        self.assertEqual(successor.returncode, 0, err)
        self.assertIn("manageable=0", out)
        self.assertEqual(self._row()["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        self.assertEqual(self._writes().count("PositionClose"), 1)

    def test_47_signed_unit_contract_unchanged(self) -> None:
        source = (ROOT / "forex_bot/broker_close_evidence.py").read_text(encoding="utf-8")
        self.assertNotIn("units = abs(", source)
        self.assertIn("negative_closed_units", source)
        result = apply_transaction_body(
            {
                "id": "TX-SIGN",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "-400",
                "tradeReduced": {"tradeID": "T1", "units": "-400"},
            },
            instrument="EUR_USD",
            trade_id="T1",
            direction="BUY",
            requested_units=Decimal("1000"),
            transaction_id="TX-SIGN",
            account_id=ACCOUNT,
        )
        self.assertEqual(result["state"], CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(result["confirmed_units"], Decimal("400"))
        self.assertEqual(result["remaining_units"], Decimal("600"))

    def test_48_parser_rejects_positive_fill_negative_reduction(self) -> None:
        with self.assertRaises(CloseReadError) as caught:
            apply_transaction_body(
                {
                    "id": "TX-BAD",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "400",
                    "tradeReduced": {"tradeID": "T1", "units": "-400"},
                },
                instrument="EUR_USD",
                trade_id="T1",
                direction="SELL",
                requested_units=Decimal("1000"),
                transaction_id="TX-BAD",
                account_id=ACCOUNT,
            )
        self.assertEqual(caught.exception.reason, "negative_closed_units")


if __name__ == "__main__":
    unittest.main()
