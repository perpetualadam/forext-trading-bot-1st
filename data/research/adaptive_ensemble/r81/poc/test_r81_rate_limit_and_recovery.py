"""R.81 rate-limit fencing, close-crash, repair, and restart tests.

Historical R.68–R.80 tests are not modified. Recovery authority comes from
execute_startup_sequence. Synthetic broker only.
"""

from __future__ import annotations

import asyncio
import hashlib
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

from forex_bot import oanda_client  # noqa: E402
from forex_bot.broker_close_evidence import (  # noqa: E402
    CLOSE_FULLY_CONFIRMED,
    CLOSE_OUTCOME_AMBIGUOUS,
    CLOSE_PARTIALLY_CONFIRMED,
    CLOSE_REJECTED_CONFIRMED,
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
from forex_bot.entry_journal import JournalUnavailable, begin_entry_submission, entry_row  # noqa: E402
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import _place_market_order_open_sync  # noqa: E402
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.position_recovery import persist_bot_position  # noqa: E402
from forex_bot.positions import Position, positions  # noqa: E402
from forex_bot.profit_protection import activation_trigger_pips, pip_size, update_protected_exit_pips  # noqa: E402
from forex_bot.recovery_repair import (  # noqa: E402
    ProcessLivenessEvidence,
    RepairAuthorisation,
    repair_abandoned_recovery,
)
from forex_bot.startup_recovery import (  # noqa: E402
    RECOVERY_COMPLETED,
    RECOVERY_COMPLETED_WITH_QUARANTINE,
    execute_startup_sequence,
    live_management_permitted,
    reset_startup_recovery_memory,
)
import forex_bot.config as config_mod  # noqa: E402
import forex_bot.live_safety as live_safety  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WORKER = Path(__file__).with_name("race_worker.py")
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
MARKER = PERMIT.with_name("one_session.consumed")
WRITES = {"OrderCreate", "PositionClose", "TradeClose", "TradeCRCDO", "OrderCancel", "OrderReplace"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Broker:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._request_params: dict = {}
        self.fail: BaseException | None = None
        self.close_body: dict | None = None
        self.transaction: dict | None = None
        self.on_request = None

    def request(self, request_obj):
        name = type(request_obj).__name__
        if name not in WRITES | {"TransactionDetails", "AccountSummary", "InstrumentsCandles"}:
            raise isolation.IsolationBreach(name)
        self.calls.append(name)
        if self.on_request is not None:
            self.on_request(name)
        if name in WRITES and self.fail is not None:
            raise self.fail
        if name == "PositionClose":
            return self.close_body or {
                "longOrderFillTransaction": {
                    "id": "TX1",
                    "type": "ORDER_FILL",
                    "instrument": "EUR_USD",
                    "units": "-1000",
                }
            }
        if name == "TransactionDetails":
            return {"transaction": self.transaction} if self.transaction else {
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
            data = getattr(request_obj, "data", {}) or {}
            order = data.get("order") if isinstance(data, dict) else {}
            extensions = (order or {}).get("clientExtensions") if isinstance(order, dict) else {}
            client = str((extensions or {}).get("id") or "client-r81")
            return {
                "orderCreateTransaction": {"id": "O-ORDER"},
                "orderFillTransaction": {
                    "id": "F-1",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "1000",
                    "price": "1.10000",
                    "orderID": "O-ORDER",
                    "tradeOpened": {"tradeID": "T-R81", "units": "1000", "price": "1.10000"},
                    "clientExtensions": {"id": client},
                },
            }
        return {"prices": []}


def _position() -> Position:
    return Position(
        symbol="EUR_USD",
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=1.0,
        strategy_name="r81",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids="T1",
        position_instance_id="INST-R81",
        position_generation=1,
        max_profit_pips=0.0,
        profit_protection_active=False,
        min_profit_pips=0.0,
        max_adverse_pips=0.0,
    )


class R81Base(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "r81.sqlite")
        self.processes: list[subprocess.Popen] = []
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["OANDA_MAX_RETRIES"] = "1"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        reset_journal_process_state()
        reset_startup_recovery_memory()
        reset_close_evidence_state()
        reset_oanda_rate_limiter_for_tests()
        positions.clear()
        self.journal = bootstrap_journal(self.path, acknowledge_empty=True)
        self.binding = account_binding(ACCOUNT)
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
        self.broker = Broker()
        oanda_client._api = self.broker
        self.exposure = live_safety.assert_new_live_exposure_allowed
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
        self.recorder = str(Path(self.temp.name) / "recorder.sqlite")
        connection = sqlite3.connect(self.recorder)
        connection.execute("CREATE TABLE submissions (id INTEGER PRIMARY KEY, kind TEXT)")
        connection.commit()
        connection.close()

    def tearDown(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)
        live_safety.assert_new_live_exposure_allowed = self.exposure
        oanda_client._api = None
        reset_startup_recovery_memory()
        reset_journal_process_state()
        reset_close_evidence_state()
        try:
            self.journal.close()
        except Exception:
            pass
        positions.clear()
        self.temp.cleanup()
        self.assertFalse(PERMIT.exists())

    def _authorise(self, view: dict | None = None) -> dict:
        report = execute_startup_sequence(view or {"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertIn(report["state"], {RECOVERY_COMPLETED, RECOVERY_COMPLETED_WITH_QUARANTINE})
        self.assertTrue(live_management_permitted())
        self.assertEqual([name for name in self.broker.calls if name in WRITES], [])
        return report

    def _spawn(self, mode: str, **extra: str) -> subprocess.Popen:
        env = os.environ.copy()
        env["R81_JOURNAL"] = self.path
        env["R81_RECORDER"] = self.recorder
        env["R81_CLIENT"] = extra.pop("client", "client-r81")
        env["R81_INSTANCE"] = extra.pop("instance", "INST-R81")
        env.update(extra)
        process = subprocess.Popen(
            [sys.executable, "-B", str(WORKER), mode],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.processes.append(process)
        return process

    def _wait_entered(self, path: Path, process: subprocess.Popen) -> None:
        deadline = time.time() + 15
        while not path.exists() or path.read_text(encoding="utf-8") != "entered":
            if process.poll() is not None:
                out, err = process.communicate()
                self.fail(f"worker exited early {process.returncode} {out} {err}")
            if time.time() > deadline:
                process.kill()
                out, err = process.communicate()
                self.fail(f"barrier timeout {out} {err}")
            time.sleep(0.02)

    def _count(self) -> int:
        connection = sqlite3.connect(self.recorder)
        count = connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        connection.close()
        return int(count)

    def _close_row(self):
        return self.journal._conn.execute(
            "SELECT confirmation_state, network_permit, submission_state FROM close_operations ORDER BY rowid DESC LIMIT 1"
        ).fetchone()

    def _entry_row(self, client: str):
        return self.journal._conn.execute(
            "SELECT outcome, network_permit, client_order_id FROM entry_operations WHERE client_order_id = ?",
            (client,),
        ).fetchone()


class BaselineTests(R81Base):
    def test_01_gates_marker_and_unchanged_recovery_files(self) -> None:
        self.assertFalse(PERMIT.exists())
        self.assertEqual(_sha(MARKER), "e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c")
        expected = {
            "forex_bot/startup_recovery.py": "69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658",
            "forex_bot/position_recovery.py": "931ade22c1fcb4371de1c0fb87a3701fc2c1766eefdb934fd6297f2f7980bbce",
            "forex_bot/entry_capture.py": "2f79ad305c3b7b7b6fefd8a47aa593810a95ea018e8679e7ae2a3fccbaa737fb",
            "forex_bot/profit_protection.py": "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f",
            "data/research/adaptive_ensemble/r69/poc/isolation.py": "b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54",
        }
        for rel, digest in expected.items():
            self.assertEqual(_sha(ROOT / rel), digest, rel)
        for rel in (
            "data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py",
            "data/research/adaptive_ensemble/r59/live_session_gate.py",
            "data/research/adaptive_ensemble/r60/live_session_gate.py",
            "data/research/adaptive_ensemble/r61/live_session_gate.py",
        ):
            self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", (ROOT / rel).read_text(encoding="utf-8"))


class RateLimitTests(R81Base):
    def test_02_entry_authority_lost_during_rate_limit_sends_nothing(self) -> None:
        self._authorise()
        entered = Path(self.temp.name) / "entered.txt"
        release = Path(self.temp.name) / "release.txt"
        release.write_text("wait", encoding="utf-8")
        owner = self._spawn(
            "entry-owner",
            client="client-rate",
            R81_ENTERED=str(entered),
            R81_RELEASE=str(release),
            R81_PAUSE="slot",
        )
        self._wait_entered(entered, owner)
        claimed = self._entry_row("client-rate")
        self.assertEqual(int(claimed["network_permit"]), 1)
        self._authorise()
        release.write_text("go", encoding="utf-8")
        out, err = owner.communicate(timeout=20)
        self.assertEqual(self._count(), 0, out + err)
        self.assertIn("refused=", out)
        self.assertEqual(int(self._entry_row("client-rate")["network_permit"]), 1)
        with self.assertRaises(JournalUnavailable):
            begin_entry_submission(
                account_binding_value=self.binding,
                instrument="EUR_USD",
                direction="BUY",
                requested_units=Decimal("1000"),
                position_instance_id="INST-R81",
                position_generation=1,
                client_order_id="client-rate",
                strategy_name="r81",
                stop_loss="1.09",
                take_profit="1.12",
                entry_reference="decision-r81",
                atr_at_entry_pips="8",
            )
        self.assertEqual(self._count(), 0)

    def test_03_close_authority_lost_during_rate_limit_sends_nothing(self) -> None:
        self._authorise()
        persist_bot_position(_position(), self.binding)
        entered = Path(self.temp.name) / "entered.txt"
        release = Path(self.temp.name) / "release.txt"
        release.write_text("wait", encoding="utf-8")
        owner = self._spawn(
            "close-owner",
            R81_ENTERED=str(entered),
            R81_RELEASE=str(release),
            R81_PAUSE="slot",
        )
        self._wait_entered(entered, owner)
        claimed = self._close_row()
        self.assertEqual(int(claimed["network_permit"]), 1)
        self._authorise()
        release.write_text("go", encoding="utf-8")
        out, err = owner.communicate(timeout=20)
        self.assertEqual(self._count(), 0, out + err)
        self.assertNotIn("CLOSE_FULLY_CONFIRMED", out)
        self.assertEqual(int(self._close_row()["network_permit"]), 1)
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        again = self._spawn("restart-close", R81_SNAPSHOT="durable")
        again_out, again_err = again.communicate(timeout=20)
        self.assertEqual(self._count(), 0, again_out + again_err)
        self.assertNotIn("CLOSE_FULLY_CONFIRMED", again_out)

    def test_04_valid_entry_and_close_each_submit_once(self) -> None:
        self._authorise()
        permit = begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-ONCE",
            position_generation=1,
            client_order_id="client-once",
            strategy_name="r81",
            stop_loss="1.09",
            take_profit="1.12",
            entry_reference="decision-r81",
            atr_at_entry_pips="8",
        )
        _place_market_order_open_sync(
            "EUR_USD", 1000, "BUY", permit.client_order_id, 1.09, 1.12, mint_live_quote("EUR_USD"), entry_permit=permit
        )
        self.assertEqual(self.broker.calls.count("OrderCreate"), 1)
        row = entry_row(permit.operation_id)
        self.assertEqual(row["outcome"], "ENTRY_FINALISED")
        self.assertEqual(int(row["network_permit"]), 1)
        with self.assertRaises(JournalUnavailable):
            begin_entry_submission(
                account_binding_value=self.binding,
                instrument="GBP_USD",
                direction="BUY",
                requested_units=Decimal("1000"),
                position_instance_id="INST-ONCE",
                position_generation=1,
                client_order_id="client-once",
                strategy_name="r81",
                stop_loss="1.09",
                take_profit="1.12",
                entry_reference="decision-r81",
                atr_at_entry_pips="8",
            )
        self.assertEqual(self.broker.calls.count("OrderCreate"), 1)
        reset_close_evidence_state()
        positions.clear()
        persist_bot_position(_position(), self.binding)
        positions["EUR_USD"] = _position()
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(operation.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        again = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(again.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)


class CloseCrashTests(R81Base):
    def _kill_close(self, pause: str) -> tuple[str, str]:
        self._authorise()
        persist_bot_position(_position(), self.binding)
        entered = Path(self.temp.name) / "entered.txt"
        release = Path(self.temp.name) / "release.txt"
        release.write_text("wait", encoding="utf-8")
        owner = self._spawn(
            "close-owner",
            R81_ENTERED=str(entered),
            R81_RELEASE=str(release),
            R81_PAUSE=pause,
        )
        self._wait_entered(entered, owner)
        claimed = self._close_row()
        self.assertIsNotNone(claimed)
        self.assertEqual(int(claimed["network_permit"]), 1)
        self.assertNotEqual(claimed["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        owner.kill()
        out, err = owner.communicate(timeout=10)
        self.assertNotEqual(owner.returncode, 0)
        return out, err

    def test_05_kill_before_request_blocks_successor(self) -> None:
        self._kill_close("slot")
        self.assertEqual(self._count(), 0)
        successor = self._spawn("restart-close", R81_SNAPSHOT="durable")
        out, err = successor.communicate(timeout=20)
        self.assertEqual(successor.returncode, 0, out + err)
        self.assertEqual(self._count(), 0, out + err)
        self.assertNotIn("CLOSE_FULLY_CONFIRMED", out)
        self.assertIn("CLOSE_OUTCOME_AMBIGUOUS", out)

    def test_06_kill_during_request_before_acceptance(self) -> None:
        self._kill_close("request-before")
        self.assertEqual(self._count(), 0)
        successor = self._spawn("restart-close", R81_SNAPSHOT="durable")
        out, err = successor.communicate(timeout=20)
        self.assertEqual(self._count(), 0, out + err)
        self.assertNotIn("CLOSE_FULLY_CONFIRMED", out)

    def test_07_kill_during_request_after_acceptance(self) -> None:
        self._kill_close("request-after")
        self.assertEqual(self._count(), 1)
        row = self._close_row()
        self.assertNotEqual(row["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        successor = self._spawn("restart-close", R81_SNAPSHOT="durable")
        out, err = successor.communicate(timeout=20)
        self.assertEqual(self._count(), 1, out + err)
        self.assertNotIn("close_state=CLOSE_FULLY_CONFIRMED", out)
        stored = self._close_row()
        self.assertNotEqual(stored["confirmation_state"], CLOSE_FULLY_CONFIRMED)


class RepairTests(R81Base):
    def _auth(self, token: str) -> RepairAuthorisation:
        return RepairAuthorisation(
            operator_acknowledged=True,
            acknowledgement="r81 explicit repair",
            account_binding=self.binding,
            journal_path=self.path,
            target_run_id="RUN-R81",
            liveness=ProcessLivenessEvidence(
                status="inactive",
                method="owner_token_and_exit_observation",
                observed_owner_token=token,
            ),
        )

    def test_08_repair_refused_while_owner_alive_and_while_submission_owner_paused(self) -> None:
        self._authorise()
        persist_bot_position(_position(), self.binding)
        entered = Path(self.temp.name) / "entered.txt"
        release = Path(self.temp.name) / "release.txt"
        release.write_text("wait", encoding="utf-8")
        owner = self._spawn(
            "close-owner",
            R81_ENTERED=str(entered),
            R81_RELEASE=str(release),
            R81_PAUSE="request-before",
        )
        self._wait_entered(entered, owner)
        paused = repair_abandoned_recovery(self._auth("not-the-live-token"))
        self.assertEqual(paused["result"], "REPAIR_REFUSED")
        self.assertEqual(self._count(), 0)
        release.write_text("go", encoding="utf-8")
        owner.communicate(timeout=20)
        status = Path(self.temp.name) / "status.txt"
        hold_entered = Path(self.temp.name) / "hold-entered.txt"
        hold_release = Path(self.temp.name) / "hold-release.txt"
        hold_release.write_text("wait", encoding="utf-8")
        holder = self._spawn(
            "abandoned-hold",
            R81_ENTERED=str(hold_entered),
            R81_RELEASE=str(hold_release),
            R81_STATUS=str(status),
        )
        self._wait_entered(hold_entered, holder)
        token = dict(line.split("=", 1) for line in status.read_text(encoding="utf-8").splitlines())["owner_token"]
        refused = repair_abandoned_recovery(self._auth(token))
        self.assertEqual(refused["result"], "REPAIR_REFUSED")
        self.assertEqual(refused["reason"], "recovery_owner_active")
        hold_release.write_text("go", encoding="utf-8")
        holder.communicate(timeout=20)

    def test_09_repair_after_owner_death_does_not_resubmit(self) -> None:
        self._authorise()
        persist_bot_position(_position(), self.binding)
        positions["EUR_USD"] = _position()
        self.broker.fail = TimeoutError("synthetic")
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(operation.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        before = int(self.journal._conn.execute("SELECT fencing_epoch FROM recovery_authority WHERE id = 1").fetchone()[0])
        status = Path(self.temp.name) / "status.txt"
        entered = Path(self.temp.name) / "entered.txt"
        dead = self._spawn("abandoned-die", R81_ENTERED=str(entered), R81_STATUS=str(status))
        self._wait_entered(entered, dead)
        dead.wait(timeout=10)
        token = dict(line.split("=", 1) for line in status.read_text(encoding="utf-8").splitlines())["owner_token"]
        repaired = repair_abandoned_recovery(self._auth(token))
        self.assertEqual(repaired["result"], "REPAIR_COMMITTED", repaired)
        self.assertEqual(repaired["order_submission_count"], 0)
        self.assertEqual(repaired["close_submission_count"], 0)
        after = int(self.journal._conn.execute("SELECT fencing_epoch FROM recovery_authority WHERE id = 1").fetchone()[0])
        self.assertGreater(after, before)
        self.assertFalse(live_management_permitted())
        reset_close_evidence_state()
        reset_startup_recovery_memory()
        reset_journal_process_state()
        successor = self._spawn("restart-close", R81_SNAPSHOT="durable")
        out, err = successor.communicate(timeout=20)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        self.assertNotIn("close_state=CLOSE_FULLY_CONFIRMED", out + err)
        stored = self._close_row()
        self.assertNotEqual(stored["confirmation_state"], CLOSE_FULLY_CONFIRMED)
        self.assertEqual(int(stored["network_permit"]), 1)

    def test_10_stale_owner_cannot_enter_or_close(self) -> None:
        self._authorise()
        entered = Path(self.temp.name) / "entered.txt"
        release = Path(self.temp.name) / "release.txt"
        release.write_text("wait", encoding="utf-8")
        entry = self._spawn(
            "stale-entry",
            client="client-stale",
            R81_ENTERED=str(entered),
            R81_RELEASE=str(release),
        )
        self._wait_entered(entered, entry)
        self._authorise()
        release.write_text("go", encoding="utf-8")
        out, err = entry.communicate(timeout=20)
        self.assertIn("refused=", out, err)
        self.assertEqual(self._count(), 0)
        persist_bot_position(_position(), self.binding)
        close_entered = Path(self.temp.name) / "close-entered.txt"
        close_release = Path(self.temp.name) / "close-release.txt"
        close_release.write_text("wait", encoding="utf-8")
        close = self._spawn(
            "stale-close",
            R81_ENTERED=str(close_entered),
            R81_RELEASE=str(close_release),
        )
        self._wait_entered(close_entered, close)
        self._authorise()
        close_release.write_text("go", encoding="utf-8")
        close_out, close_err = close.communicate(timeout=20)
        self.assertEqual(self._count(), 0, close_out + close_err)
        self.assertNotIn("close_state=CLOSE_FULLY_CONFIRMED", close_out)


class RejectionAndRestartTests(R81Base):
    def test_11_confirmed_rejection_can_reserve_a_new_operation(self) -> None:
        self._authorise()
        persist_bot_position(_position(), self.binding)
        positions["EUR_USD"] = _position()
        self.broker.close_body = {"longOrderRejectTransaction": {"id": "RJ", "type": "ORDER_REJECT"}}
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(operation.confirmation_state, CLOSE_REJECTED_CONFIRMED)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        first = operation.operation_id
        self.broker.close_body = None
        second = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(second.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertNotEqual(second.operation_id, first)
        self.assertEqual(self.broker.calls.count("PositionClose"), 2)
        stored = self.journal._conn.execute(
            "SELECT confirmation_state, network_permit FROM close_operations WHERE operation_id = ?",
            (first,),
        ).fetchone()
        self.assertEqual(stored["confirmation_state"], CLOSE_REJECTED_CONFIRMED)
        self.assertEqual(int(stored["network_permit"]), 1)

    def test_12_ambiguous_and_partial_close_do_not_rereserve(self) -> None:
        self._authorise()
        persist_bot_position(_position(), self.binding)
        positions["EUR_USD"] = _position()
        self.broker.fail = TimeoutError("synthetic")
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(operation.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.broker.fail = None
        again = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(again.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.assertEqual(again.operation_id, operation.operation_id)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        reset_close_evidence_state()
        positions.clear()
        self.broker.calls.clear()
        partial_row = _position()
        partial_row.broker_trade_ids = "T2"
        partial_row.position_instance_id = "INST-PARTIAL"
        persist_bot_position(partial_row, self.binding)
        positions["EUR_USD"] = partial_row
        self.broker.close_body = {
            "longOrderFillTransaction": {"id": "TX1", "type": "ORDER_FILL", "instrument": "EUR_USD", "units": "-400"}
        }
        self.broker.transaction = {
            "id": "TX1",
            "type": "ORDER_FILL",
            "accountID": ACCOUNT,
            "instrument": "EUR_USD",
            "units": "-400",
            "tradesClosed": [{"tradeID": "T2", "units": "400"}],
        }
        partial = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(partial.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(positions["EUR_USD"].units, 1000.0)
        repeat = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(repeat.operation_id, partial.operation_id)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)

    def test_13_ambiguous_entry_survives_fresh_restart(self) -> None:
        self._authorise()
        permit = begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-AMB",
            position_generation=1,
            client_order_id="client-amb",
            strategy_name="r81",
            stop_loss="1.09",
            take_profit="1.12",
            entry_reference="decision-r81",
            atr_at_entry_pips="8",
        )
        self.broker.fail = TimeoutError("synthetic")
        with self.assertRaises(TimeoutError):
            _place_market_order_open_sync(
                "EUR_USD", 1000, "BUY", permit.client_order_id, 1.09, 1.12, mint_live_quote("EUR_USD"), entry_permit=permit
            )
        self.assertEqual(self.broker.calls.count("OrderCreate"), 1)
        self.assertEqual(entry_row(permit.operation_id)["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertNotIn("EUR_USD", positions)
        empty = self._spawn("restart-entry", client="client-amb", R81_SNAPSHOT="COMPLETE_EMPTY")
        empty_out, empty_err = empty.communicate(timeout=20)
        self.assertIn("refused=", empty_out, empty_err)
        self.assertEqual(self._count(), 0)
        incomplete = self._spawn("restart-entry", client="client-amb", instance="INST-OTHER", R81_SNAPSHOT="INCOMPLETE")
        inc_out, inc_err = incomplete.communicate(timeout=20)
        self.assertIn("refused=", inc_out, inc_err)
        self.assertEqual(self._count(), 0)
        self.assertNotIn("EUR_USD", positions)

    def test_14_ambiguous_close_survives_fresh_restart_and_flat_snapshot(self) -> None:
        self._authorise()
        persist_bot_position(_position(), self.binding)
        positions["EUR_USD"] = _position()
        self.broker.fail = TimeoutError("synthetic")
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r81"))
        self.assertEqual(operation.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.assertEqual(self.broker.calls.count("PositionClose"), 1)
        flat = self._spawn("restart-close", R81_SNAPSHOT="COMPLETE_EMPTY")
        flat_out, flat_err = flat.communicate(timeout=20)
        self.assertEqual(self._count(), 0, flat_out + flat_err)
        self.assertIn("CLOSE_OUTCOME_AMBIGUOUS", flat_out)
        self.assertNotIn("close_state=CLOSE_FULLY_CONFIRMED", flat_out)
        open_trade = self._spawn("restart-close", R81_SNAPSHOT="durable")
        open_out, open_err = open_trade.communicate(timeout=20)
        self.assertEqual(self._count(), 0, open_out + open_err)
        self.assertNotIn("close_state=CLOSE_FULLY_CONFIRMED", open_out)
        stored = self._close_row()
        self.assertEqual(stored["confirmation_state"], CLOSE_OUTCOME_AMBIGUOUS)
        self.assertEqual(int(stored["network_permit"]), 1)

    def test_15_journal_fault_after_request_and_during_rate_limit(self) -> None:
        self._authorise()
        permit = begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-FAULT",
            position_generation=1,
            client_order_id="client-fault",
            strategy_name="r81",
            stop_loss="1.09",
            take_profit="1.12",
            entry_reference="decision-r81",
            atr_at_entry_pips="8",
        )

        def fault(name: str) -> None:
            if name == "OrderCreate":
                arm_active_journal_fault("before_commit")

        self.broker.on_request = fault
        with self.assertRaises(JournalUnavailable):
            _place_market_order_open_sync(
                "EUR_USD", 1000, "BUY", permit.client_order_id, 1.09, 1.12, mint_live_quote("EUR_USD"), entry_permit=permit
            )
        self.assertEqual(self.broker.calls.count("OrderCreate"), 1)
        self.assertEqual(entry_row(permit.operation_id)["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        restart = self._spawn("restart-entry", client="client-fault", R81_SNAPSHOT="COMPLETE_EMPTY")
        out, err = restart.communicate(timeout=20)
        self.assertIn("refused=", out, err)
        self.assertEqual(self._count(), 0)

    def test_16_profit_protection_parameters_unchanged(self) -> None:
        position = _position()
        position.take_profit = 1.12
        position.entry_price = 1.10
        self.assertEqual(pip_size("EUR_USD"), 0.0001)
        self.assertEqual(pip_size("USD_JPY"), 0.01)
        self.assertEqual(activation_trigger_pips(position), 134.0)
        position.symbol = "USD_JPY"
        position.entry_price = 150.0
        position.stop_loss = 149.0
        position.take_profit = 151.0
        self.assertEqual(activation_trigger_pips(position), 67.0)
        position.profit_protection_exit_pips = 12.0
        held = update_protected_exit_pips(position, 10.0, 4.0)
        self.assertEqual(held, 12.0)
        self.assertEqual(
            _sha(ROOT / "forex_bot/profit_protection.py"),
            "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f",
        )


if __name__ == "__main__":
    unittest.main()
