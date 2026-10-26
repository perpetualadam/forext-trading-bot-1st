"""R.84 OANDA close-contract tests. Isolation is imported before operational modules."""

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
sys.path.insert(0, str(ROOT / "data" / "research" / "adaptive_ensemble" / "r84" / "poc"))
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402
import oanda_fixtures as fixtures  # noqa: E402

from forex_bot import live_safety, oanda_client  # noqa: E402
from forex_bot.broker_close_evidence import (  # noqa: E402
    CLOSE_FULLY_CONFIRMED,
    CLOSE_PARTIALLY_CONFIRMED,
    CLOSE_RECONCILIATION_REQUIRED,
    CloseReadError,
    apply_transaction_body,
    reset_close_evidence_state,
    resolve_from_retrieved_transaction,
    run_guarded_live_close,
)
from forex_bot.close_journal import (  # noqa: E402
    account_binding,
    active_journal,
    bootstrap_journal,
    reset_journal_process_state,
)
from forex_bot.position_recovery import persist_bot_position  # noqa: E402
from forex_bot.positions import (  # noqa: E402
    Position,
    close_confirmed_live_position,
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
import forex_bot.oanda_rate_limit as rate_mod  # noqa: E402

ACCOUNT = fixtures.ACCOUNT
WORKER = ROOT / "data" / "research" / "adaptive_ensemble" / "r84" / "poc" / "race_worker.py"
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
    def __init__(self, shape: str) -> None:
        self.calls: list[str] = []
        self.shape = shape
        self.instrument = "EUR_USD"
        self.trade_id = "T1"
        self.transaction_id = "TX-R84"
        self._request_params: dict = {}

    def request(self, request_obj):
        name = type(request_obj).__name__
        if name not in WRITES | {"TransactionDetails", "AccountSummary", "InstrumentCandles"}:
            raise isolation.IsolationBreach(name)
        self.calls.append(name)
        if name == "PositionClose":
            units = "-1000" if self.shape == "full" else "-400"
            return {
                "orderFillTransaction": {
                    "id": self.transaction_id,
                    "type": "ORDER_FILL",
                    "instrument": self.instrument,
                    "units": units,
                }
            }
        if name == "TransactionDetails":
            return {"transaction": self._transaction()}
        return {"account": {"NAV": "10000"}, "candles": []}

    def _transaction(self) -> dict:
        if self.shape == "ambiguous":
            return {
                "id": self.transaction_id,
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": self.instrument,
                "units": "-1000",
            }
        if self.shape == "partial":
            return fixtures.order_fill(
                transaction_id=self.transaction_id,
                instrument=self.instrument,
                fill_units="-400",
                trade_id=self.trade_id,
                trade_reduced="-400",
            )
        return fixtures.order_fill(
            transaction_id=self.transaction_id,
            instrument=self.instrument,
            fill_units="-1000",
            trade_id=self.trade_id,
            trades_closed="-1000",
        )


def _position(direction: str = "BUY", symbol: str = "EUR_USD", trade: str = "T1") -> Position:
    return Position(
        symbol=symbol,
        direction=direction,
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=1.0,
        strategy_name="r84",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids=trade,
        position_instance_id=f"INST-{trade}",
        position_generation=1,
        max_profit_pips=0.0,
        profit_protection_active=False,
        min_profit_pips=0.0,
        max_adverse_pips=0.0,
        profit_protection_exit_pips=40.0,
    )


class R84Base(unittest.TestCase):
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
        self.broker = Broker("full")
        oanda_client._api = self.broker
        rate_mod.reset_oanda_rate_limiter_for_tests()
        self._exposure = live_safety.assert_new_live_exposure_allowed
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None

    def tearDown(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)
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

    def _apply(self, body: dict, **kwargs):
        return apply_transaction_body(
            body,
            instrument=kwargs.get("instrument", body.get("instrument", "EUR_USD")),
            trade_id=kwargs.get("trade_id", "T1"),
            direction=kwargs.get("direction", "BUY"),
            requested_units=Decimal(kwargs.get("requested", "1000")),
            transaction_id=kwargs.get("transaction_id", str(body.get("id") or "")),
            account_id=kwargs.get("account_id", ACCOUNT),
        )

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
        env["R84_JOURNAL"] = self.path
        env["R84_RECORDER"] = self.recorder
        env["R84_ENTERED"] = str(entered)
        env["R84_RELEASE"] = str(release)
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


class ContractTests(R84Base):
    def test_01_baseline_gates_and_unchanged_modules(self) -> None:
        self.assertFalse((ROOT / "one_session.permit").exists())
        for gate in GATES:
            self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", gate.read_text(encoding="utf-8"))
        self.assertEqual(_sha(ROOT / "forex_bot" / "profit_protection.py"), "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f")
        self.assertEqual(_sha(ROOT / "forex_bot" / "oanda_exec.py"), "e83bcc1095aba3f1c06cd625fb01fc0823698f348c0cd517d929928b559701c5")
        self.assertEqual(_sha(ROOT / "forex_bot" / "entry_journal.py"), "961b3e167bbc8553a0febc2f8ace430e536ffce8389c1ab0a49227feaeb02dcd")
        self.assertEqual(_sha(ROOT / "forex_bot" / "positions.py"), "b9da0d1da27e298919eff3a889ff4ec83a53baf95b320876839207ab6827153e")
        text = (ROOT / "forex_bot" / "broker_close_evidence.py").read_text(encoding="utf-8")
        self.assertIn('raise CloseReadError("negative_closed_units")', text)
        self.assertNotIn("units = abs(", text)

    def test_02_documented_buy_and_sell_full_closes(self) -> None:
        buy = self._apply(fixtures.documented_buy_full_close(), trade_id="6395", requested="100", direction="BUY")
        self.assertEqual(buy["state"], CLOSE_FULLY_CONFIRMED)
        self.assertEqual(buy["confirmed_units"], Decimal("100"))
        self.assertEqual(buy["remaining_units"], Decimal("0"))
        self.assertEqual(buy["signed_reduction_units"], "-100")
        sell = self._apply(
            fixtures.order_fill(
                transaction_id="TX-SELL-FULL",
                instrument="EUR_USD",
                fill_units="1000",
                trade_id="T-SELL",
                trades_closed="1000",
            ),
            trade_id="T-SELL",
            direction="SELL",
            requested="1000",
            transaction_id="TX-SELL-FULL",
        )
        self.assertEqual(sell["state"], CLOSE_FULLY_CONFIRMED)
        self.assertEqual(sell["remaining_units"], Decimal("0"))
        self.assertEqual(sell["signed_reduction_units"], "1000")

    def test_03_documented_partial_closes_keep_remainder(self) -> None:
        buy = self._apply(
            fixtures.order_fill(
                transaction_id="TX-BUY-PART",
                instrument="EUR_USD",
                fill_units="-400",
                trade_id="T1",
                trade_reduced="-400",
            ),
            requested="1000",
        )
        self.assertEqual(buy["state"], CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(buy["confirmed_units"], Decimal("400"))
        self.assertEqual(buy["remaining_units"], Decimal("600"))
        sell_doc = self._apply(
            fixtures.documented_sell_partial_close(),
            instrument="USD_CAD",
            trade_id="6397",
            direction="SELL",
            requested="1000",
            transaction_id="6402",
        )
        self.assertEqual(sell_doc["state"], CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(sell_doc["confirmed_units"], Decimal("10"))
        self.assertEqual(sell_doc["remaining_units"], Decimal("990"))
        sell = self._apply(
            fixtures.order_fill(
                transaction_id="TX-SELL-PART",
                instrument="EUR_USD",
                fill_units="400",
                trade_id="T-SELL",
                trade_reduced="400",
            ),
            trade_id="T-SELL",
            direction="SELL",
            transaction_id="TX-SELL-PART",
        )
        self.assertEqual(sell["state"], CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(sell["remaining_units"], Decimal("600"))

    def test_04_unit_bounds_and_nonfinite_values(self) -> None:
        almost = self._apply(
            fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-999", trade_id="T1", trades_closed="-999")
        )
        self.assertEqual(almost["remaining_units"], Decimal("1"))
        full = self._apply(
            fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-1000", trade_id="T1", trades_closed="-1000")
        )
        self.assertEqual(full["state"], CLOSE_FULLY_CONFIRMED)
        zero = self._apply(
            fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-1", trade_id="T1", trades_closed="0")
        )
        self.assertEqual(zero["state"], CLOSE_RECONCILIATION_REQUIRED)
        over = self._apply(
            fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-1200", trade_id="T1", trades_closed="-1200")
        )
        self.assertEqual(over["state"], CLOSE_RECONCILIATION_REQUIRED)
        self.assertIsNone(over["remaining_units"])
        decimal_units = self._apply(
            fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-400.5", trade_id="T1", trade_reduced="-400.5")
        )
        self.assertEqual(decimal_units["remaining_units"], Decimal("599.5"))
        jpy = self._apply(
            fixtures.order_fill(transaction_id="TX", instrument="USD_JPY", fill_units="-400", trade_id="T-JPY", trades_closed="-400"),
            instrument="USD_JPY",
            trade_id="T-JPY",
        )
        self.assertEqual(jpy["confirmed_units"], Decimal("400"))
        for raw in ("NaN", "Infinity", "-Infinity", "nope", ""):
            body = fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-1", trade_id="T1", trades_closed=raw or "0")
            if raw == "":
                body["tradesClosed"][0]["units"] = ""
            with self.assertRaises(CloseReadError):
                self._apply(body)
        missing = fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-400", trade_id="T1", trades_closed="400")
        del missing["tradesClosed"][0]["units"]
        with self.assertRaises(CloseReadError):
            self._apply(missing)

    def test_05_wrong_sign_duplicate_and_mixed_evidence(self) -> None:
        with self.assertRaises(CloseReadError):
            self._apply(
                fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="400", trade_id="T1", trade_reduced="-400"),
                direction="SELL",
            )
        with self.assertRaises(CloseReadError):
            self._apply(
                fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="400", trade_id="T1", trade_reduced="400"),
                direction="BUY",
            )
        duplicate = fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-500", trade_id="T1", trades_closed="-400")
        duplicate["tradesClosed"].append({"tradeID": "T1", "units": "-100"})
        with self.assertRaises(CloseReadError):
            self._apply(duplicate)
        same = fixtures.order_fill(
            transaction_id="TX",
            instrument="EUR_USD",
            fill_units="-400",
            trade_id="T1",
            trades_closed="-400",
            trade_reduced="-400",
        )
        once = self._apply(same)
        self.assertEqual(once["confirmed_units"], Decimal("400"))
        conflict = fixtures.order_fill(
            transaction_id="TX",
            instrument="EUR_USD",
            fill_units="-400",
            trade_id="T1",
            trades_closed="-400",
            trade_reduced="-300",
        )
        self.assertEqual(self._apply(conflict)["state"], CLOSE_RECONCILIATION_REQUIRED)
        other = fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-400", trade_id="T1", trades_closed="-400")
        other["tradeReduced"] = {"tradeID": "T-OTHER", "units": "-400"}
        other["units"] = "-800"
        self.assertEqual(self._apply(other)["state"], CLOSE_RECONCILIATION_REQUIRED)
        mixed = fixtures.order_fill(
            transaction_id="TX",
            instrument="EUR_USD",
            fill_units="-400",
            trade_id="T1",
            trade_reduced="-400",
            trade_opened={"tradeID": "T-NEW", "units": "10"},
        )
        self.assertEqual(self._apply(mixed)["error"], "mixed_open_and_reduce")
        absent = fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-400", trade_id="T1")
        with self.assertRaises(CloseReadError):
            self._apply(absent)
        positive_magnitude = self._apply(
            fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-400", trade_id="T1", trades_closed="400")
        )
        self.assertEqual(positive_magnitude["state"], CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(positive_magnitude["remaining_units"], Decimal("600"))

    def test_06_identity_rejects_false_confirmation(self) -> None:
        good = fixtures.order_fill(transaction_id="TX", instrument="EUR_USD", fill_units="-1000", trade_id="T1", trades_closed="-1000")
        with self.assertRaises(CloseReadError):
            self._apply(good, trade_id="T-OTHER")
        with self.assertRaises(CloseReadError):
            self._apply(good, account_id="001-002-0000001-009")
        with self.assertRaises(CloseReadError):
            self._apply(good, instrument="GBP_USD")
        with self.assertRaises(CloseReadError):
            self._apply(good, direction="SELL")
        with self.assertRaises(CloseReadError):
            self._apply(good, transaction_id="TX-OTHER")
        blank = dict(good)
        blank["id"] = ""
        with self.assertRaises(CloseReadError):
            self._apply(blank, transaction_id="")
        reduced_full = fixtures.order_fill(
            transaction_id="TX", instrument="EUR_USD", fill_units="-1000", trade_id="T1", trade_reduced="-1000"
        )
        self.assertNotEqual(self._apply(reduced_full)["state"], CLOSE_FULLY_CONFIRMED)
        good["clientExtensions"] = {"id": "not-idempotency", "comment": "idempotent client order"}
        self.assertEqual(self._apply(good)["state"], CLOSE_FULLY_CONFIRMED)
        self.assertNotEqual(good["orderID"], good["tradesClosed"][0]["tradeID"])


class OperationalTests(R84Base):
    def test_07_operational_full_and_partial_paths(self) -> None:
        self._authorise()
        pos = _position()
        persist_bot_position(pos, self.binding)
        positions["EUR_USD"] = pos
        self.broker.shape = "full"
        operation = asyncio.run(run_guarded_live_close(pos, reason="r84"))
        self.assertEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertEqual(operation.confirmed_units, Decimal("1000"))
        self.assertEqual(operation.remaining_units, Decimal("0"))
        self.assertEqual(self._writes(), ["PositionClose"])
        self.assertIn("EUR_USD", positions)
        again = resolve_from_retrieved_transaction(
            operation.operation_id,
            {"transaction": self.broker._transaction()},
            account_id=ACCOUNT,
        )
        self.assertEqual(again, CLOSE_FULLY_CONFIRMED)
        row = active_journal()._conn.execute(
            "SELECT confirmed_units FROM close_operations WHERE operation_id = ?",
            (operation.operation_id,),
        ).fetchone()
        self.assertEqual(Decimal(row["confirmed_units"]), Decimal("1000"))
        removed = close_confirmed_live_position("EUR_USD", operation)
        self.assertIsNotNone(removed)
        self.assertNotIn("EUR_USD", positions)
        replay = resolve_from_retrieved_transaction(
            operation.operation_id,
            {"transaction": self.broker._transaction()},
            account_id=ACCOUNT,
        )
        self.assertEqual(replay, "CLOSE_FINALISED")

    def test_08_operational_partial_does_not_resubmit_or_publish_remainder(self) -> None:
        self._authorise()
        pos = _position()
        persist_bot_position(pos, self.binding)
        positions["EUR_USD"] = pos
        self.broker.shape = "partial"
        operation = asyncio.run(run_guarded_live_close(pos, reason="r84"))
        self.assertEqual(operation.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(operation.confirmed_units, Decimal("400"))
        self.assertEqual(operation.remaining_units, Decimal("600"))
        self.assertEqual(pos.units, 1000.0)
        self.assertEqual(pos.profit_protection_exit_pips, 40.0)
        second = asyncio.run(run_guarded_live_close(pos, reason="r84"))
        self.assertEqual(self._writes(), ["PositionClose"])
        self.assertEqual(second.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        self.assertIn("EUR_USD", positions)

    def test_09_full_close_kill_and_successor(self) -> None:
        worker = self._spawn("full-hold", R84_SHAPE="full")
        self._wait_entered(worker)
        self.assertEqual(self._count(), 1)
        worker.kill()
        worker.communicate(timeout=10)
        successor = self._spawn("successor", R84_VIEW="empty", R84_SHAPE="full")
        out, err = successor.communicate(timeout=20)
        self.assertEqual(successor.returncode, 0, err)
        self.assertIn("close_state=CLOSE_FULLY_CONFIRMED", out)
        self.assertIn("confirmed=1000", out)
        self.assertIn("remaining=0", out)
        self.assertIn("manageable=0", out)
        self.assertEqual(self._count(), 1)

    def test_10_partial_kill_quarantine_and_ratchet(self) -> None:
        worker = self._spawn("partial-hold", R84_SHAPE="partial")
        self._wait_entered(worker)
        self.assertEqual(self._count(), 1)
        worker.kill()
        worker.communicate(timeout=10)
        successor = self._spawn("successor", R84_VIEW="match", R84_SHAPE="partial", R84_CYCLE="1")
        out, err = successor.communicate(timeout=20)
        self.assertEqual(successor.returncode, 0, err)
        self.assertIn("close_state=CLOSE_PARTIALLY_CONFIRMED", out)
        self.assertIn("confirmed=400", out)
        self.assertIn("remaining=600", out)
        self.assertIn("durable_units=1000", out)
        self.assertIn("ratchet=40", out)
        self.assertIn("manageable=0", out)
        self.assertIn("cycle=1", out)
        self.assertEqual(self._count(), 1)

    def test_11_ambiguous_restart_sends_no_second_close(self) -> None:
        worker = self._spawn("ambiguous-hold", R84_SHAPE="ambiguous")
        self._wait_entered(worker)
        self.assertEqual(self._count(), 1)
        worker.kill()
        worker.communicate(timeout=10)
        successor = self._spawn("successor", R84_VIEW="conflict-open", R84_SHAPE="ambiguous", R84_CYCLE="1")
        out, err = successor.communicate(timeout=20)
        self.assertEqual(successor.returncode, 0, err)
        self.assertIn("manageable=0", out)
        self.assertIn("cycle=1", out)
        self.assertNotIn("close_state=CLOSE_FULLY_CONFIRMED", out)
        self.assertEqual(self._count(), 1)

    def test_12_conflicting_snapshot_and_stale_owner(self) -> None:
        self._authorise()
        pos = _position()
        persist_bot_position(pos, self.binding)
        positions["EUR_USD"] = pos
        operation = asyncio.run(run_guarded_live_close(pos, reason="r84"))
        self.assertEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        successor = self._spawn("successor", R84_VIEW="conflict-open", R84_SHAPE="full")
        out, err = successor.communicate(timeout=20)
        self.assertEqual(successor.returncode, 0, err)
        self.assertIn("manageable=0", out)
        self.assertIsNone(close_confirmed_live_position("EUR_USD", operation))
        self.assertIn("EUR_USD", positions)
        row = active_journal()._conn.execute(
            "SELECT confirmation_state FROM close_operations WHERE operation_id = ?",
            (operation.operation_id,),
        ).fetchone()
        self.assertEqual(row["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        asyncio.run(run_guarded_live_close(pos, reason="r84-again"))
        self.assertEqual(self._writes(), ["PositionClose"])


if __name__ == "__main__":
    unittest.main()
