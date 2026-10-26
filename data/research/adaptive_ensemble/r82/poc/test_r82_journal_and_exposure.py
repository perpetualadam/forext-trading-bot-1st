"""R.82 journal integrity, close-confirmation faults, and partial exposure.

Isolation is imported before any operational module. No production journal,
credential, PostgreSQL connection, or real broker request is used.
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
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import live_safety, oanda_client  # noqa: E402
from forex_bot.broker_close_evidence import (  # noqa: E402
    CLOSE_FULLY_CONFIRMED,
    CLOSE_OUTCOME_AMBIGUOUS,
    CLOSE_PARTIALLY_CONFIRMED,
    CLOSE_RECONCILIATION_REQUIRED,
    CLOSE_REJECTED_CONFIRMED,
    CloseReadError,
    apply_transaction_body,
    reset_close_evidence_state,
    run_guarded_live_close,
)
from forex_bot.close_journal import (  # noqa: E402
    account_binding,
    active_journal,
    arm_active_journal_fault,
    bootstrap_journal,
    reset_journal_process_state,
)
from forex_bot.entry_journal import (  # noqa: E402
    EntryGuardRefusal,
    JournalUnavailable,
    begin_entry_submission,
    claim_entry_permit,
)
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import (  # noqa: E402
    CloseGuardRefusal,
    _place_market_order_open_sync,
    _submit_order_create,
    _submit_position_close_body,
)
from forex_bot.position_recovery import persist_bot_position  # noqa: E402
from forex_bot.positions import (  # noqa: E402
    Position,
    close_confirmed_live_position,
    positions,
)
from forex_bot.profit_protection import update_protected_exit_pips  # noqa: E402
from forex_bot.startup_recovery import (  # noqa: E402
    RECOVERY_COMPLETED,
    RECOVERY_COMPLETED_WITH_QUARANTINE,
    execute_startup_sequence,
    live_management_permitted,
    reset_startup_recovery_memory,
)
import forex_bot.config as config_mod  # noqa: E402
import forex_bot.oanda_rate_limit as rate_mod  # noqa: E402
import forex_bot.startup_recovery as recovery_mod  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WORKER = ROOT / "data" / "research" / "adaptive_ensemble" / "r82" / "poc" / "race_worker.py"
GATES = (
    ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py",
    ROOT / "data/research/adaptive_ensemble/r59/live_session_gate.py",
    ROOT / "data/research/adaptive_ensemble/r60/live_session_gate.py",
    ROOT / "data/research/adaptive_ensemble/r61/live_session_gate.py",
)
WRITES = {"OrderCreate", "PositionClose"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Broker:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.pause = False
        self.entered = threading.Event()
        self.release = threading.Event()
        self.partial = False
        self.fault_on_details = False
        self.reject = False
        self.fail: Exception | None = None
        self._request_params: dict = {}

    def request(self, request_obj):
        name = type(request_obj).__name__
        if name not in WRITES | {"TransactionDetails", "AccountSummary", "InstrumentCandles"}:
            raise isolation.IsolationBreach(name)
        self.calls.append(name)
        if name in WRITES and self.fail is not None:
            raise self.fail
        if name in WRITES and self.pause:
            self.entered.set()
            if not self.release.wait(5):
                raise TimeoutError("request release")
        if name == "PositionClose" and self.reject:
            return {"longOrderRejectTransaction": {"id": "RJ", "type": "ORDER_REJECT"}}
        if name == "PositionClose":
            units = "400" if self.partial else "1000"
            return {
                "longOrderFillTransaction": {
                    "id": "TX-CLOSE",
                    "type": "ORDER_FILL",
                    "instrument": "EUR_USD",
                    "units": f"-{units}",
                }
            }
        if name == "TransactionDetails":
            if self.fault_on_details:
                arm_active_journal_fault("before_commit")
            units = "400" if self.partial else "1000"
            return {
                "transaction": {
                    "id": "TX-CLOSE",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": f"-{units}",
                    "tradesClosed": [{"tradeID": "T1", "units": units}],
                }
            }
        if name == "OrderCreate":
            data = getattr(request_obj, "data", {}) or {}
            order = data.get("order") if isinstance(data, dict) else {}
            extensions = (order or {}).get("clientExtensions") if isinstance(order, dict) else {}
            client = str((extensions or {}).get("id") or "")
            return {
                "orderFillTransaction": {
                    "id": "TX-ENTRY",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "1000",
                    "price": "1.10000",
                    "tradeOpened": {"tradeID": "T-ENTRY", "units": "1000"},
                    "clientExtensions": {"id": client},
                }
            }
        return {"account": {"NAV": "10000"}, "candles": []}


def _position() -> Position:
    return Position(
        symbol="EUR_USD",
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=1.0,
        strategy_name="r82",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids="T1",
        position_instance_id="INST-R82",
        position_generation=1,
        max_profit_pips=0.0,
        profit_protection_active=False,
        min_profit_pips=0.0,
        max_adverse_pips=0.0,
    )


class R82Base(unittest.TestCase):
    def setUp(self) -> None:
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        reset_journal_process_state()
        positions.clear()
        self._tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self._tmp.name) / "journal.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        os.environ["OANDA_MAX_RETRIES"] = "1"
        self.binding = account_binding(ACCOUNT)
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
        created = bootstrap_journal(self.path, acknowledge_empty=True)
        created.close()
        self.journal = active_journal()
        self.broker = Broker()
        oanda_client._api = self.broker
        rate_mod.reset_oanda_rate_limiter_for_tests()
        self._authority = recovery_mod.live_management_permitted
        self._slot = rate_mod.acquire_oanda_rest_slot
        self._exposure = live_safety.assert_new_live_exposure_allowed
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None

    def tearDown(self) -> None:
        recovery_mod.live_management_permitted = self._authority
        rate_mod.acquire_oanda_rest_slot = self._slot
        live_safety.assert_new_live_exposure_allowed = self._exposure
        oanda_client._api = None
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        positions.clear()
        reset_journal_process_state()
        self._tmp.cleanup()
        self.assertFalse((ROOT / "one_session.permit").exists())

    def _authorise(self) -> None:
        report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertIn(report["state"], {RECOVERY_COMPLETED, RECOVERY_COMPLETED_WITH_QUARANTINE})
        self.assertTrue(live_management_permitted())
        self.assertEqual(self._writes(), [])

    def _entry_permit(self, client: str):
        return begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id=f"INST-{client}",
            position_generation=1,
            client_order_id=client,
            strategy_name="r82",
            stop_loss="1.05",
            take_profit="1.20",
            entry_reference="r82",
            atr_at_entry_pips="8",
        )

    def _submit_entry(self, client: str) -> None:
        permit = self._entry_permit(client)
        _place_market_order_open_sync(
            "EUR_USD",
            1000,
            "BUY",
            permit.client_order_id,
            1.05,
            1.2,
            mint_live_quote("EUR_USD"),
            entry_permit=permit,
        )

    def _managed(self) -> Position:
        self._authorise()
        pos = _position()
        persist_bot_position(pos, self.binding)
        positions["EUR_USD"] = pos
        return pos

    def _writes(self) -> list[str]:
        return [name for name in self.broker.calls if name in WRITES]

    def _delete_authority(self) -> None:
        other = sqlite3.connect(self.path, isolation_level=None)
        other.execute("DELETE FROM recovery_authority")
        other.close()

    def _entry_row(self, client: str):
        reset_journal_process_state()
        journal = active_journal()
        self.journal = journal
        return journal._conn.execute(
            "SELECT network_permit, outcome FROM entry_operations WHERE client_order_id = ?",
            (client,),
        ).fetchone()

    def _close_row(self):
        reset_journal_process_state()
        journal = active_journal()
        self.journal = journal
        return journal._conn.execute(
            "SELECT confirmation_state, network_permit, submission_state, confirmed_units, remaining_units FROM close_operations ORDER BY rowid DESC LIMIT 1"
        ).fetchone()

    def _during_slot(self, action) -> None:
        def wrapped() -> None:
            action()
            return self._slot()

        rate_mod.acquire_oanda_rest_slot = wrapped


class BaselineTests(R82Base):
    def test_01_baseline_and_gates(self) -> None:
        self.assertFalse((ROOT / "one_session.permit").exists())
        for gate in GATES:
            self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", gate.read_text(encoding="utf-8"))
        self.assertEqual(
            _sha(ROOT / "forex_bot" / "profit_protection.py"),
            "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f",
        )
        self._authorise()


class JournalLossTests(R82Base):
    def test_02_entry_authority_missing_before_claim(self) -> None:
        self._authorise()
        self._delete_authority()
        with self.assertRaises(EntryGuardRefusal):
            self._submit_entry("client-before")
        self.assertEqual(self._writes(), [])
        row = self._entry_row("client-before")
        self.assertEqual(int(row["network_permit"]), 0)

    def test_03_close_authority_missing_before_claim(self) -> None:
        self._managed()
        self._delete_authority()
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(self._writes(), [])
        self.assertNotEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        row = self._close_row()
        self.assertEqual(int(row["network_permit"]), 0)

    def test_04_entry_authority_missing_after_claim(self) -> None:
        self._authorise()
        permit = self._entry_permit("client-after-claim")
        calls = {"n": 0}

        def wrapped() -> bool:
            calls["n"] += 1
            if calls["n"] == 2:
                self._delete_authority()
            return self._authority()

        recovery_mod.live_management_permitted = wrapped
        with self.assertRaises(EntryGuardRefusal):
            _submit_order_create(
                "EUR_USD", 1000, "BUY", permit.client_order_id, 1.05, 1.2, mint_live_quote("EUR_USD"), permit
            )
        self.assertEqual(self._writes(), [])
        row = self._entry_row("client-after-claim")
        self.assertEqual(int(row["network_permit"]), 1)
        self.assertEqual(row["outcome"], "ENTRY_SUBMITTING")

    def test_05_close_authority_missing_after_claim(self) -> None:
        self._managed()
        calls = {"n": 0}

        def wrapped() -> bool:
            calls["n"] += 1
            if calls["n"] == 2:
                self._delete_authority()
            return self._authority()

        recovery_mod.live_management_permitted = wrapped
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(self._writes(), [])
        self.assertNotEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        row = self._close_row()
        self.assertEqual(int(row["network_permit"]), 1)

    def test_06_entry_journal_unreadable_after_rate_limit(self) -> None:
        self._authorise()
        permit = self._entry_permit("client-slot")
        self._during_slot(self.journal._conn.close)
        with self.assertRaises(Exception):
            _submit_order_create(
                "EUR_USD", 1000, "BUY", permit.client_order_id, 1.05, 1.2, mint_live_quote("EUR_USD"), permit
            )
        self.assertEqual(self._writes(), [])
        row = self._entry_row("client-slot")
        self.assertEqual(int(row["network_permit"]), 1)

    def test_07_close_journal_unreadable_after_rate_limit(self) -> None:
        self._managed()
        self._during_slot(self.journal._conn.close)
        with self.assertRaises(sqlite3.ProgrammingError):
            asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(self._writes(), [])
        row = self._close_row()
        self.assertEqual(int(row["network_permit"]), 1)
        self.assertNotEqual(row["confirmation_state"], CLOSE_FULLY_CONFIRMED)

    def test_08_entry_authority_row_removed_during_slot(self) -> None:
        self._authorise()
        permit = self._entry_permit("client-row")
        self._during_slot(self._delete_authority)
        with self.assertRaises(EntryGuardRefusal):
            _submit_order_create(
                "EUR_USD", 1000, "BUY", permit.client_order_id, 1.05, 1.2, mint_live_quote("EUR_USD"), permit
            )
        self.assertEqual(self._writes(), [])
        row = self._entry_row("client-row")
        self.assertEqual(int(row["network_permit"]), 1)
        with self.assertRaises(EntryGuardRefusal):
            self._submit_entry("client-row-2")
        self.assertEqual(self._writes(), [])

    def test_19_readable_wal_stays_authorised_and_malformed_file_does_not(self) -> None:
        self._authorise()
        holder = sqlite3.connect(self.path, isolation_level=None, timeout=0.1)
        holder.execute("BEGIN EXCLUSIVE")
        try:
            self.assertTrue(live_management_permitted())
            reset_journal_process_state()
            self.assertTrue(live_management_permitted())
        finally:
            holder.execute("ROLLBACK")
            holder.close()
        reset_journal_process_state()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(self.path + suffix)
            if sidecar.exists():
                sidecar.unlink()
        Path(self.path).write_bytes(b"not-a-database")
        self.assertFalse(live_management_permitted())
        with self.assertRaises(JournalUnavailable):
            self._submit_entry("client-malformed")
        self.assertEqual(self._writes(), [])

    def test_09_close_authority_row_removed_during_slot(self) -> None:
        self._managed()
        self._during_slot(self._delete_authority)
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(self._writes(), [])
        self.assertNotEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        row = self._close_row()
        self.assertEqual(int(row["network_permit"]), 1)
        reset_close_evidence_state()
        again = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(self._writes(), [])
        self.assertTrue(again.blocks_resubmission or again.confirmation_state != CLOSE_FULLY_CONFIRMED)


class RaceAndPersistenceTests(R82Base):
    def _spawn(self, mode: str, view: str = "empty") -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["R82_JOURNAL"] = self.path
        env["R82_VIEW"] = view
        return subprocess.run(
            [sys.executable, "-B", str(WORKER), mode],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=40,
            check=False,
        )

    def test_10_entry_request_entered_after_final_check(self) -> None:
        self._authorise()
        permit = self._entry_permit("client-race")
        self.broker.pause = True
        holder: dict = {}

        def run() -> None:
            try:
                _submit_order_create(
                    "EUR_USD", 1000, "BUY", permit.client_order_id, 1.05, 1.2, mint_live_quote("EUR_USD"), permit
                )
            except Exception as exc:
                holder["error"] = type(exc).__name__

        thread = threading.Thread(target=run)
        thread.start()
        self.assertTrue(self.broker.entered.wait(5))
        child = self._spawn("successor-startup")
        self.broker.release.set()
        thread.join(5)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
        self.assertEqual(self._writes(), ["OrderCreate"])
        self.assertFalse(live_management_permitted())
        with self.assertRaises(EntryGuardRefusal):
            self._submit_entry("client-race-2")
        self.assertEqual(self._writes(), ["OrderCreate"])

    def test_11_close_request_entered_after_final_check(self) -> None:
        self._managed()
        self.broker.pause = True
        self.broker.partial = True

        def run() -> None:
            try:
                asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
            except Exception:
                pass

        thread = threading.Thread(target=run)
        thread.start()
        self.assertTrue(self.broker.entered.wait(5))
        child = self._spawn("successor-startup", "original")
        self.broker.release.set()
        thread.join(8)
        self.assertFalse(thread.is_alive())
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
        self.assertEqual(self._writes(), ["PositionClose"])
        self.assertFalse(live_management_permitted())
        reset_close_evidence_state()
        again = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(self._writes(), ["PositionClose"])
        self.assertNotEqual(again.confirmation_state, CLOSE_FULLY_CONFIRMED)

    def test_12_entry_commit_failure_after_acceptance(self) -> None:
        self._authorise()
        permit = self._entry_permit("client-commit")

        def request(request_obj):
            name = type(request_obj).__name__
            self.broker.calls.append(name)
            if name == "OrderCreate":
                arm_active_journal_fault("before_commit")
                data = getattr(request_obj, "data", {}) or {}
                order = data.get("order") if isinstance(data, dict) else {}
                client = str(((order or {}).get("clientExtensions") or {}).get("id") or "")
                return {
                    "orderFillTransaction": {
                        "id": "TX-ENTRY",
                        "type": "ORDER_FILL",
                        "accountID": ACCOUNT,
                        "instrument": "EUR_USD",
                        "units": "1000",
                        "price": "1.10000",
                        "tradeOpened": {"tradeID": "T-ENTRY", "units": "1000"},
                        "clientExtensions": {"id": client},
                    }
                }
            raise isolation.IsolationBreach(name)

        self.broker.request = request
        with self.assertRaises(Exception):
            _place_market_order_open_sync(
                "EUR_USD", 1000, "BUY", permit.client_order_id, 1.05, 1.2, mint_live_quote("EUR_USD"), entry_permit=permit
            )
        self.assertEqual(self._writes(), ["OrderCreate"])
        row = self._entry_row("client-commit")
        self.assertEqual(int(row["network_permit"]), 1)
        self.assertNotEqual(row["outcome"], "ENTRY_FINALISED")
        with self.assertRaises(JournalUnavailable):
            self._entry_permit("client-commit")

    def test_13_close_confirmation_commit_does_not_remove_position(self) -> None:
        self._managed()
        self.broker.fault_on_details = True
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(self._writes(), ["PositionClose"])
        row = self._close_row()
        self.assertNotEqual(row["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        self.assertEqual(int(row["network_permit"]), 1)
        removed = close_confirmed_live_position("EUR_USD", operation)
        self.assertIsNone(removed)
        self.assertEqual(positions["EUR_USD"].units, 1000.0)
        reset_close_evidence_state()
        again = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(self._writes(), ["PositionClose"])
        self.assertNotEqual(again.confirmation_state, CLOSE_FULLY_CONFIRMED)

    def test_14_ambiguous_entry_and_close_survive_restart(self) -> None:
        self._authorise()
        permit = self._entry_permit("client-ambiguous")
        claim_entry_permit(permit)
        record = self.journal.reserve(
            account_binding_value=self.binding,
            position_instance_id="INST-HELD",
            position_generation=1,
            instrument="EUR_USD",
            trade_id="T-HELD",
            direction="BUY",
            original_units=Decimal("1000"),
            requested_units=Decimal("1000"),
        )
        token = self.journal.commit_submission_intent(record["operation_id"])
        close_permit = self.journal.issue_submission_permit(record["operation_id"], token)
        self.journal.claim_network_permit(close_permit)
        reset_startup_recovery_memory()
        reset_journal_process_state()
        reset_close_evidence_state()
        report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertIn(report["state"], {RECOVERY_COMPLETED, RECOVERY_COMPLETED_WITH_QUARANTINE})
        entry = self._entry_row("client-ambiguous")
        close = self._close_row()
        self.assertEqual(entry["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertEqual(close["confirmation_state"], "CLOSE_OUTCOME_AMBIGUOUS")
        self.assertEqual(self._writes(), [])


class PartialExposureTests(R82Base):
    def _body(self, closed: str, **overrides) -> dict:
        body = {
            "id": overrides.get("tx", "TX1"),
            "type": "ORDER_FILL",
            "accountID": overrides.get("account", ACCOUNT),
            "instrument": overrides.get("instrument", "EUR_USD"),
            "units": overrides.get("direction_units", f"-{closed}" if not str(closed).startswith("-") else closed),
            "tradesClosed": [{"tradeID": overrides.get("trade", "T1"), "units": closed}],
        }
        return body

    def _apply(self, body: dict, requested: str = "1000", direction: str = "BUY", instrument: str = "EUR_USD"):
        return apply_transaction_body(
            body,
            instrument=instrument,
            trade_id="T1",
            direction=direction,
            requested_units=Decimal(requested),
            transaction_id=str(body.get("id") or "TX1"),
            account_id=ACCOUNT,
        )

    def test_15_partial_400_records_remaining_and_blocks_repeat(self) -> None:
        self._managed()
        update_protected_exit_pips(positions["EUR_USD"], 80.0, 20.0)
        before = positions["EUR_USD"].profit_protection_exit_pips
        self.broker.partial = True
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(operation.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(operation.confirmed_units, Decimal("400"))
        self.assertEqual(operation.remaining_units, Decimal("600"))
        self.assertEqual(positions["EUR_USD"].units, 1000.0)
        self.assertGreaterEqual(positions["EUR_USD"].profit_protection_exit_pips, before)
        row = self._close_row()
        self.assertEqual(Decimal(row["confirmed_units"]), Decimal("400"))
        self.assertEqual(Decimal(row["remaining_units"]), Decimal("600"))
        again = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(self._writes(), ["PositionClose"])
        self.assertEqual(again.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        removed = close_confirmed_live_position("EUR_USD", operation)
        self.assertIsNone(removed)

    def test_16_unit_validation_matrix(self) -> None:
        cases = {
            "999": (CLOSE_PARTIALLY_CONFIRMED, Decimal("999"), Decimal("1")),
            "1000": (CLOSE_FULLY_CONFIRMED, Decimal("1000"), Decimal("0")),
            "0": (CLOSE_RECONCILIATION_REQUIRED, Decimal("0"), Decimal("1000")),
        }
        for closed, expected in cases.items():
            units = "-1" if closed == "0" else f"-{closed}"
            result = self._apply(self._body(closed, direction_units=units))
            self.assertEqual(result["state"], expected[0], closed)
            self.assertEqual(result["confirmed_units"], expected[1], closed)
            self.assertEqual(result["remaining_units"], expected[2], closed)
        over = self._apply(self._body("1200", direction_units="-1200"))
        self.assertEqual(over["state"], CLOSE_RECONCILIATION_REQUIRED)
        self.assertIsNone(over["remaining_units"])
        with self.assertRaises(CloseReadError):
            self._apply(self._body("-100", direction_units="-100"))
        with self.assertRaises(CloseReadError):
            self._apply(self._body("400", tx=""))
        with self.assertRaises(CloseReadError):
            self._apply(self._body("400", trade="T-OTHER"))
        with self.assertRaises(CloseReadError):
            self._apply(self._body("400", account="001-002-0000001-009"))
        with self.assertRaises(CloseReadError):
            self._apply(self._body("400", instrument="GBP_USD"), instrument="EUR_USD")
        duplicate = self._body("400")
        duplicate["tradesClosed"].append({"tradeID": "T1", "units": "100"})
        with self.assertRaises(CloseReadError):
            self._apply(duplicate)
        sell = apply_transaction_body(
            {
                "id": "TX-SELL",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "400",
                "tradesClosed": [{"tradeID": "T1", "units": "400"}],
            },
            instrument="EUR_USD",
            trade_id="T1",
            direction="SELL",
            requested_units=Decimal("1000"),
            transaction_id="TX-SELL",
            account_id=ACCOUNT,
        )
        self.assertEqual(sell["confirmed_units"], Decimal("400"))
        self.assertEqual(sell["remaining_units"], Decimal("600"))
        jpy = self._apply(self._body("400", instrument="USD_JPY"), instrument="USD_JPY")
        self.assertEqual(jpy["remaining_units"], Decimal("600"))

    def test_18_rejection_can_reserve_again_and_ambiguous_cannot(self) -> None:
        self._managed()
        self.broker.reject = True
        rejected = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(rejected.confirmation_state, CLOSE_REJECTED_CONFIRMED)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        self.broker.reject = False
        second = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(second.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertNotEqual(second.operation_id, rejected.operation_id)
        self.assertEqual(self.broker.calls.count("PositionClose"), 2)
        reset_close_evidence_state()
        positions.clear()
        self.broker.calls.clear()
        pos = _position()
        pos.broker_trade_ids = "T-AMB"
        pos.position_instance_id = "INST-AMB"
        persist_bot_position(pos, self.binding)
        positions["EUR_USD"] = pos
        self.broker.fail = TimeoutError("synthetic")
        ambiguous = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(ambiguous.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.broker.fail = None
        repeat = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.assertEqual(repeat.operation_id, ambiguous.operation_id)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)

    def test_17_partial_restart_quarantines_and_cycle_sends_nothing(self) -> None:
        self._managed()
        self.broker.partial = True
        asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r82"))
        self.journal.close()
        reset_journal_process_state()
        reset_startup_recovery_memory()
        positions.clear()
        for mode in ("remaining", "original", "empty", "wrong-trade", "wrong-account", "missing", "incomplete"):
            child = self._spawn_restart(mode)
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
            self.assertIn("manageable=0", child.stdout, mode)
        cycle = self._spawn_restart("remaining", cycle=True)
        self.assertEqual(cycle.returncode, 0, cycle.stdout + cycle.stderr)
        self.assertIn("cycle=1", cycle.stdout)
        self.assertIn("manageable=0", cycle.stdout)

    def _spawn_restart(self, view: str, cycle: bool = False) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["R82_JOURNAL"] = self.path
        env["R82_VIEW"] = view
        mode = "restart-cycle" if cycle else "restart"
        return subprocess.run(
            [sys.executable, "-B", str(WORKER), mode],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
