"""R.83 post-commit publication, SQLite authority reads, and close-unit checks.

Isolation is imported before any operational module.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
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
    CLOSE_PARTIALLY_CONFIRMED,
    CLOSE_RECONCILIATION_REQUIRED,
    CloseReadError,
    apply_transaction_body,
    reset_close_evidence_state,
    run_guarded_live_close,
)
from forex_bot.close_journal import (  # noqa: E402
    JournalUnavailable,
    account_binding,
    active_journal,
    bootstrap_journal,
    reset_journal_process_state,
)
from forex_bot.entry_journal import EntryGuardRefusal, begin_entry_submission  # noqa: E402
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import _place_market_order_open_sync, _submit_order_create  # noqa: E402
from forex_bot.position_recovery import persist_bot_position  # noqa: E402
from forex_bot.positions import (  # noqa: E402
    Position,
    close_confirmed_live_position,
    position_management_permitted,
    positions,
)
from forex_bot.startup_recovery import (  # noqa: E402
    RECOVERY_COMPLETED,
    RECOVERY_COMPLETED_WITH_QUARANTINE,
    execute_startup_sequence,
    live_management_permitted,
    reset_startup_recovery_memory,
)
import forex_bot.config as config_mod  # noqa: E402
import forex_bot.entry_capture as entry_capture  # noqa: E402
import forex_bot.oanda_rate_limit as rate_mod  # noqa: E402
import forex_bot.startup_recovery as recovery_mod  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WORKER = ROOT / "data" / "research" / "adaptive_ensemble" / "r83" / "poc" / "race_worker.py"
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
        self.partial = False
        self._request_params: dict = {}

    def request(self, request_obj):
        name = type(request_obj).__name__
        if name not in WRITES | {"TransactionDetails", "AccountSummary", "InstrumentCandles"}:
            raise isolation.IsolationBreach(name)
        self.calls.append(name)
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
            client = str(((order or {}).get("clientExtensions") or {}).get("id") or "")
            return {
                "orderCreateTransaction": {"id": "O-R83", "accountID": ACCOUNT},
                "orderFillTransaction": {
                    "id": "F-R83",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "1000",
                    "price": "1.10000",
                    "orderID": "O-R83",
                    "tradeOpened": {"tradeID": "T-R83", "units": "1000", "price": "1.10000"},
                    "clientExtensions": {"id": client},
                },
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
        strategy_name="r83",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids="T1",
        position_instance_id="INST-CLOSE",
        position_generation=1,
        max_profit_pips=0.0,
        profit_protection_active=False,
        min_profit_pips=0.0,
        max_adverse_pips=0.0,
        profit_protection_exit_pips=40.0,
    )


class R83Base(unittest.TestCase):
    def setUp(self) -> None:
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        reset_journal_process_state()
        positions.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "journal.sqlite")
        self.recorder = str(Path(self.temp.name) / "recorder.sqlite")
        connection = sqlite3.connect(self.recorder)
        connection.execute("CREATE TABLE submissions (id INTEGER PRIMARY KEY, kind TEXT)")
        connection.commit()
        connection.close()
        self.processes: list[subprocess.Popen] = []
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
        self._exposure = live_safety.assert_new_live_exposure_allowed
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
        self._book = entry_capture.positions

    def tearDown(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)
        recovery_mod.live_management_permitted = self._authority
        entry_capture.positions = self._book
        live_safety.assert_new_live_exposure_allowed = self._exposure
        oanda_client._api = None
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        positions.clear()
        reset_journal_process_state()
        self.temp.cleanup()
        self.assertFalse((ROOT / "one_session.permit").exists())

    def _authorise(self) -> None:
        report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertIn(report["state"], {RECOVERY_COMPLETED, RECOVERY_COMPLETED_WITH_QUARANTINE})
        self.assertTrue(live_management_permitted())

    def _writes(self) -> list[str]:
        return [name for name in self.broker.calls if name in WRITES]

    def _count(self) -> int:
        connection = sqlite3.connect(self.recorder)
        count = connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        connection.close()
        return int(count)

    def _spawn(self, mode: str, **env_extra: str) -> subprocess.Popen:
        entered = Path(self.temp.name) / f"{mode}-entered"
        release = Path(self.temp.name) / f"{mode}-release"
        release.write_text("wait", encoding="utf-8")
        env = os.environ.copy()
        env["R83_JOURNAL"] = self.path
        env["R83_RECORDER"] = self.recorder
        env["R83_ENTERED"] = str(entered)
        env["R83_RELEASE"] = str(release)
        env.update(env_extra)
        process = subprocess.Popen(
            [sys.executable, "-B", str(WORKER), mode],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.processes.append(process)
        process.entered = entered  # type: ignore[attr-defined]
        process.release = release  # type: ignore[attr-defined]
        return process

    def _wait_entered(self, process: subprocess.Popen) -> None:
        import time

        deadline = time.time() + 15
        path = process.entered  # type: ignore[attr-defined]
        while not path.exists() or path.read_text(encoding="utf-8") != "entered":
            if process.poll() is not None:
                out, err = process.communicate()
                self.fail(f"worker exited {process.returncode} {out} {err}")
            if time.time() > deadline:
                process.kill()
                out, err = process.communicate()
                self.fail(f"barrier timeout {out} {err}")
            time.sleep(0.02)

    def _entry_permit(self, client: str = "client-r83"):
        return begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-R83",
            position_generation=1,
            client_order_id=client,
            strategy_name="r83",
            stop_loss="1.05",
            take_profit="1.20",
            entry_reference="r83",
            atr_at_entry_pips="8",
        )

    def _managed(self) -> None:
        self._authorise()
        pos = _position()
        persist_bot_position(pos, self.binding)
        positions["EUR_USD"] = pos

    def _body(self, closed: str, **overrides) -> dict:
        return {
            "id": overrides.get("tx", "TX1"),
            "type": "ORDER_FILL",
            "accountID": overrides.get("account", ACCOUNT),
            "instrument": overrides.get("instrument", "EUR_USD"),
            "units": overrides.get("direction_units", f"-{closed}"),
            "tradesClosed": [{"tradeID": overrides.get("trade", "T1"), "units": closed}],
        }

    def _apply(self, body: dict, **kwargs):
        return apply_transaction_body(
            body,
            instrument=kwargs.get("instrument", "EUR_USD"),
            trade_id="T1",
            direction=kwargs.get("direction", "BUY"),
            requested_units=Decimal(kwargs.get("requested", "1000")),
            transaction_id=str(body.get("id") or "TX1"),
            account_id=ACCOUNT,
        )


class BaselineTests(R83Base):
    def test_01_baseline_gates_and_profit_hash(self) -> None:
        self.assertFalse((ROOT / "one_session.permit").exists())
        for gate in GATES:
            self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", gate.read_text(encoding="utf-8"))
        self.assertEqual(
            _sha(ROOT / "forex_bot" / "profit_protection.py"),
            "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f",
        )
        self.assertEqual(_sha(ROOT / "forex_bot" / "oanda_exec.py"), "e83bcc1095aba3f1c06cd625fb01fc0823698f348c0cd517d929928b559701c5")
        text = (ROOT / "forex_bot" / "broker_close_evidence.py").read_text(encoding="utf-8")
        self.assertIn('raise CloseReadError("negative_closed_units")', text)
        self.assertNotIn("units = abs(", text)


class EntryPublicationTests(R83Base):
    def test_02_publication_exception_keeps_finalised_entry(self) -> None:
        self._authorise()
        permit = self._entry_permit()

        class Boom(dict):
            def __setitem__(self, key, value) -> None:
                raise RuntimeError("publication_failed")

        entry_capture.positions = Boom(entry_capture.positions)
        with self.assertRaises(RuntimeError):
            _place_market_order_open_sync(
                "EUR_USD", 1000, "BUY", permit.client_order_id, 1.05, 1.2, mint_live_quote("EUR_USD"), entry_permit=permit
            )
        self.assertEqual(self._writes(), ["OrderCreate"])
        self.assertNotIn("EUR_USD", positions)
        row = self.journal._conn.execute(
            "SELECT outcome, network_permit, broker_trade_id FROM entry_operations WHERE client_order_id = 'client-r83'"
        ).fetchone()
        self.assertEqual(row["outcome"], "ENTRY_FINALISED")
        self.assertEqual(int(row["network_permit"]), 1)
        self.assertEqual(row["broker_trade_id"], "T-R83")
        with self.assertRaises(JournalUnavailable):
            self._entry_permit("client-r83")
        self.assertEqual(self._writes(), ["OrderCreate"])
        count = self.journal._conn.execute("SELECT COUNT(*) FROM managed_positions").fetchone()[0]
        self.assertEqual(int(count), 1)

    def test_03_process_kill_after_entry_commit_reconstructs_once(self) -> None:
        self.journal.close()
        reset_journal_process_state()
        worker = self._spawn("entry-memory")
        self._wait_entered(worker)
        self.assertEqual(self._count(), 1)
        worker.kill()
        worker.communicate(timeout=10)
        child = self._spawn("successor", R83_VIEW="match")
        out, err = child.communicate(timeout=20)
        self.assertEqual(child.returncode, 0, out + err)
        self.assertIn("manageable=1", out)
        self.assertIn("entry_outcome=ENTRY_FINALISED", out)
        self.assertIn("durable_trade=T-R83", out)
        self.assertIn("units=1000.0", out)
        self.assertEqual(self._count(), 1)
        reset_journal_process_state()
        self.journal = active_journal()
        with self.assertRaises(JournalUnavailable):
            self._entry_permit("client-r83")
        again = self.journal._conn.execute("SELECT COUNT(*) FROM managed_positions").fetchone()[0]
        self.assertEqual(int(again), 1)

    def test_04_stale_owner_publication_is_refused(self) -> None:
        self.journal.close()
        reset_journal_process_state()
        worker = self._spawn("entry-fence")
        self._wait_entered(worker)
        successor = self._spawn("successor", R83_VIEW="match")
        sout, serr = successor.communicate(timeout=20)
        self.assertEqual(successor.returncode, 0, sout + serr)
        worker.release.write_text("go", encoding="utf-8")  # type: ignore[attr-defined]
        out, err = worker.communicate(timeout=20)
        self.assertEqual(worker.returncode, 0, out + err)
        self.assertIn("published=0", out)
        self.assertIn("manageable=1", sout)
        self.assertEqual(self._count(), 1)


class ClosePublicationTests(R83Base):
    def test_05_removal_exception_leaves_full_confirmation(self) -> None:
        self._managed()
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r83"))
        self.assertEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        try:
            raise RuntimeError("removal_not_reached")
        except RuntimeError:
            pass
        self.assertIn("EUR_USD", positions)
        row = self.journal.get(operation.operation_id)
        self.assertEqual(row["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        self.assertEqual(Decimal(row["confirmed_units"]), Decimal("1000"))
        self.assertEqual(Decimal(row["remaining_units"]), Decimal("0"))
        self.assertEqual(self._writes().count("PositionClose"), 1)
        reset_close_evidence_state()
        again = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r83"))
        self.assertEqual(self._writes().count("PositionClose"), 1)
        self.assertEqual(again.confirmation_state, CLOSE_FULLY_CONFIRMED)

    def test_06_process_kill_before_close_removal(self) -> None:
        self.journal.close()
        reset_journal_process_state()
        worker = self._spawn("close-hold")
        self._wait_entered(worker)
        self.assertEqual(self._count(), 1)
        worker.kill()
        worker.communicate(timeout=10)
        child = self._spawn("successor", R83_VIEW="empty")
        out, err = child.communicate(timeout=20)
        self.assertEqual(child.returncode, 0, out + err)
        self.assertIn("close_state=CLOSE_FULLY_CONFIRMED", out)
        self.assertIn("confirmed=1000", out)
        self.assertIn("remaining=0", out)
        self.assertIn("manageable=0", out)
        self.assertEqual(self._count(), 1)

    def test_07_stale_owner_cannot_finalise_or_resubmit(self) -> None:
        self._managed()
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r83"))
        self.journal.close()
        reset_journal_process_state()
        child = self._spawn("successor", R83_VIEW="conflict-open")
        out, err = child.communicate(timeout=20)
        self.assertEqual(child.returncode, 0, out + err)
        self.assertIn("manageable=0", out)
        removed = close_confirmed_live_position("EUR_USD", operation)
        self.assertIsNone(removed)
        self.assertIn("EUR_USD", positions)
        reset_journal_process_state()
        self.journal = active_journal()
        row = self.journal._conn.execute(
            "SELECT confirmation_state FROM close_operations ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        reset_close_evidence_state()
        again = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r83"))
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        self.assertNotEqual(again.confirmation_state, "CLOSE_SUBMITTING")

    def test_08_partial_kill_keeps_remainder_and_quarantine(self) -> None:
        self.journal.close()
        reset_journal_process_state()
        worker = self._spawn("partial-hold")
        self._wait_entered(worker)
        self.assertEqual(self._count(), 1)
        worker.kill()
        worker.communicate(timeout=10)
        child = self._spawn("successor", R83_VIEW="match")
        out, err = child.communicate(timeout=20)
        self.assertEqual(child.returncode, 0, out + err)
        self.assertIn("close_state=CLOSE_PARTIALLY_CONFIRMED", out)
        self.assertIn("confirmed=400", out)
        self.assertIn("remaining=600", out)
        self.assertIn("durable_units=1000", out)
        self.assertIn("manageable=0", out)
        self.assertIn("ratchet=40", out)
        self.assertEqual(self._count(), 1)
        conflict = self._spawn("successor", R83_VIEW="conflict-open", R83_CYCLE="1")
        cout, cerr = conflict.communicate(timeout=30)
        self.assertEqual(conflict.returncode, 0, cout + cerr)
        self.assertIn("manageable=0", cout)
        self.assertIn("cycle=1", cout)
        self.assertEqual(self._count(), 1)


class SqliteFaultTests(R83Base):
    def test_09_rollback_select_raises_sqlite_busy(self) -> None:
        path = Path(self.temp.name) / "rollback.sqlite"
        holder = sqlite3.connect(path, isolation_level=None, timeout=0)
        reader = None
        try:
            holder.execute("PRAGMA journal_mode=DELETE")
            holder.execute("CREATE TABLE recovery_authority (id INTEGER PRIMARY KEY, fencing_epoch INTEGER)")
            holder.execute("INSERT INTO recovery_authority VALUES (1, 1)")
            holder.execute("BEGIN EXCLUSIVE")
            reader = sqlite3.connect(path, isolation_level=None, timeout=0)
            with self.assertRaises(sqlite3.OperationalError) as caught:
                reader.execute("SELECT fencing_epoch FROM recovery_authority WHERE id = 1")
            self.assertEqual(caught.exception.sqlite_errorname, "SQLITE_BUSY")
            self.assertEqual(caught.exception.sqlite_errorcode, 5)
        finally:
            if reader is not None:
                reader.close()
            holder.close()
        self.assertEqual(self._writes(), [])

    def test_10_shared_cache_begin_raises_sqlite_locked(self) -> None:
        uri = "file:r83lock?mode=memory&cache=shared"
        holder = sqlite3.connect(uri, uri=True, isolation_level=None)
        other = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=0)
        try:
            holder.execute("CREATE TABLE recovery_authority (id INTEGER PRIMARY KEY, fencing_epoch INTEGER)")
            holder.execute("INSERT INTO recovery_authority VALUES (1, 1)")
            holder.execute("BEGIN IMMEDIATE")
            other.execute("SELECT fencing_epoch FROM recovery_authority WHERE id = 1").fetchone()
            with self.assertRaises(sqlite3.OperationalError) as caught:
                other.execute("BEGIN IMMEDIATE")
            self.assertEqual(caught.exception.sqlite_errorname, "SQLITE_LOCKED_SHAREDCACHE")
            self.assertEqual(caught.exception.sqlite_errorcode, 262)
        finally:
            holder.close()
            other.close()
        self.assertEqual(self._writes(), [])

    def _inject(self, exc: BaseException) -> None:
        calls = {"n": 0}

        def wrapped() -> bool:
            calls["n"] += 1
            if calls["n"] >= 3:
                raise exc
            return self._authority()

        recovery_mod.live_management_permitted = wrapped

    def test_11_injected_busy_and_locked_block_both_sinks(self) -> None:
        self._authorise()
        busy_permit = self._entry_permit("client-busy")
        self._inject(sqlite3.OperationalError("database is locked"))
        with self.assertRaises(Exception):
            _submit_order_create(
                "EUR_USD",
                1000,
                "BUY",
                busy_permit.client_order_id,
                1.05,
                1.2,
                mint_live_quote("EUR_USD"),
                busy_permit,
            )
        self.assertEqual(self._writes(), [])
        recovery_mod.live_management_permitted = self._authority
        locked_permit = self._entry_permit("client-locked")
        self._inject(sqlite3.OperationalError("database table is locked"))
        with self.assertRaises(Exception):
            _submit_order_create(
                "EUR_USD",
                1000,
                "BUY",
                locked_permit.client_order_id,
                1.05,
                1.2,
                mint_live_quote("EUR_USD"),
                locked_permit,
            )
        self.assertEqual(self._writes(), [])
        recovery_mod.live_management_permitted = self._authority
        self._managed()
        self._inject(sqlite3.OperationalError("database table is locked"))
        locked_close = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r83"))
        self.assertEqual(self._writes(), [])
        self.assertNotEqual(locked_close.confirmation_state, CLOSE_FULLY_CONFIRMED)
        recovery_mod.live_management_permitted = self._authority
        second = _position()
        second.symbol = "GBP_USD"
        second.broker_trade_ids = "T2"
        second.position_instance_id = "INST-CLOSE-2"
        persist_bot_position(second, self.binding)
        positions["GBP_USD"] = second
        self._inject(sqlite3.OperationalError("database is locked"))
        busy_close = asyncio.run(run_guarded_live_close(second, reason="r83"))
        self.assertEqual(self._writes(), [])
        self.assertNotEqual(busy_close.confirmation_state, CLOSE_FULLY_CONFIRMED)
        rows = active_journal()._conn.execute(
            "SELECT network_permit, confirmation_state FROM close_operations ORDER BY rowid"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(int(row["network_permit"]), 1)
            self.assertNotEqual(row["confirmation_state"], CLOSE_FULLY_CONFIRMED)

    def test_12_closed_connection_and_missing_row_send_nothing(self) -> None:
        self._authorise()
        permit = self._entry_permit("client-closed")
        self.journal._conn.close()
        with self.assertRaises(Exception):
            _submit_order_create(
                "EUR_USD", 1000, "BUY", permit.client_order_id, 1.05, 1.2, mint_live_quote("EUR_USD"), permit
            )
        self.assertEqual(self._writes(), [])
        reset_journal_process_state()
        self.journal = active_journal()
        self._authorise()
        other = sqlite3.connect(self.path, isolation_level=None)
        other.execute("DELETE FROM recovery_authority")
        other.close()
        with self.assertRaises(EntryGuardRefusal):
            _place_market_order_open_sync(
                "EUR_USD",
                1000,
                "BUY",
                "client-missing",
                1.05,
                1.2,
                mint_live_quote("EUR_USD"),
                entry_permit=self._entry_permit("client-missing"),
            )
        self.assertEqual(self._writes(), [])


class MoreFaultTests(R83Base):
    def test_14_stale_epoch_and_closed_close_send_nothing(self) -> None:
        self._managed()
        other = sqlite3.connect(self.path, isolation_level=None)
        other.execute("UPDATE recovery_authority SET fencing_epoch = fencing_epoch + 1 WHERE id = 1")
        other.close()
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r83"))
        self.assertEqual(self._writes(), [])
        self.assertNotEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        reset_startup_recovery_memory()
        reset_journal_process_state()
        reset_close_evidence_state()
        positions.clear()
        self.journal = active_journal()
        self._authorise()
        pos = _position()
        pos.position_instance_id = "INST-CLOSED"
        pos.broker_trade_ids = "T9"
        persist_bot_position(pos, self.binding)
        positions["EUR_USD"] = pos
        self.journal._conn.close()
        with self.assertRaises(Exception):
            asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r83"))
        self.assertEqual(self._writes(), [])


class UnitTests(R83Base):
    def test_13_closed_unit_contract(self) -> None:
        partial = self._apply(self._body("400"))
        self.assertEqual(partial["state"], CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(partial["remaining_units"], Decimal("600"))
        full = self._apply(self._body("1000", direction_units="-1000"))
        self.assertEqual(full["state"], CLOSE_FULLY_CONFIRMED)
        self.assertEqual(full["remaining_units"], Decimal("0"))
        almost = self._apply(self._body("999", direction_units="-999"))
        self.assertEqual(almost["remaining_units"], Decimal("1"))
        zero = self._apply(self._body("0", direction_units="-1"))
        self.assertEqual(zero["state"], CLOSE_RECONCILIATION_REQUIRED)
        self.assertNotEqual(zero["state"], CLOSE_FULLY_CONFIRMED)
        over = self._apply(self._body("1200", direction_units="-1200"))
        self.assertEqual(over["state"], CLOSE_RECONCILIATION_REQUIRED)
        self.assertIsNone(over["remaining_units"])
        with self.assertRaises(CloseReadError):
            self._apply(self._body("-100", direction_units="-100"))
        with self.assertRaises(CloseReadError):
            self._apply(self._body("nope", direction_units="-1"))
        with self.assertRaises(CloseReadError):
            self._apply(self._body("", direction_units="-1"))
        missing = self._body("400")
        del missing["tradesClosed"][0]["units"]
        with self.assertRaises(CloseReadError):
            self._apply(missing)
        decimal_units = self._apply(self._body("400.5", direction_units="-400.5"))
        self.assertEqual(decimal_units["state"], CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(decimal_units["remaining_units"], Decimal("599.5"))
        duplicate = self._body("400")
        duplicate["tradesClosed"].append({"tradeID": "T1", "units": "100"})
        with self.assertRaises(CloseReadError):
            self._apply(duplicate)
        with self.assertRaises(CloseReadError):
            self._apply(self._body("400", trade="T-OTHER"))
        with self.assertRaises(CloseReadError):
            self._apply(self._body("400", account="001-002-0000001-009"))
        with self.assertRaises(CloseReadError):
            self._apply(self._body("400", instrument="GBP_USD"))
        with self.assertRaises(CloseReadError):
            self._apply(self._body("400", tx=""))
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
        self.assertEqual(sell["remaining_units"], Decimal("600"))
        jpy = self._apply(self._body("400", instrument="USD_JPY"), instrument="USD_JPY")
        self.assertEqual(jpy["confirmed_units"], Decimal("400"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
