"""R.78 offline liveness, fencing and OANDA protocol fixture tests.

No network, PostgreSQL, production database, or real broker.
"""

from __future__ import annotations

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

from forex_bot.broker_entry_evidence import (  # noqa: E402
    ENTRY_CONFIRMED_MULTIPLE_TRADES,
    ENTRY_CONFIRMED_SINGLE_TRADE,
    ENTRY_EVIDENCE_CONFLICT,
    ENTRY_OUTCOME_AMBIGUOUS,
    ENTRY_PARTIAL_OR_MIXED_EFFECT,
    ENTRY_RECONCILIATION_REQUIRED,
    ENTRY_REJECTED_CONFIRMED,
    classify_entry_response,
)
from forex_bot.close_journal import (  # noqa: E402
    SCHEMA_VERSION,
    JournalUnavailable,
    account_binding,
    active_journal,
    arm_active_journal_fault,
    bootstrap_journal,
    canonical_client_order_id,
    migrate_journal_4_to_5,
    open_journal,
    reset_journal_process_state,
)
from forex_bot.entry_investigation import classify_entry_investigation, record_entry_investigation  # noqa: E402
from forex_bot.entry_journal import begin_entry_submission  # noqa: E402
from forex_bot.position_recovery import evaluate_durable_row, publish_recovered  # noqa: E402
from forex_bot.recovery_owner_lock import (  # noqa: E402
    RecoveryOwnerLock,
    current_process_start,
    host_boot_id,
    lock_identity,
    owner_process_status,
)
from forex_bot.recovery_repair import (  # noqa: E402
    ProcessLivenessEvidence,
    RepairAuthorisation,
    repair_abandoned_recovery,
)
from forex_bot.startup_recovery import (  # noqa: E402
    RECOVERY_BLOCKED,
    RECOVERY_COMPLETED,
    current_fencing_epoch,
    execute_startup_sequence,
    live_management_permitted,
    reset_startup_recovery_memory,
)

ACCOUNT = "001-002-0000001-003"
WORKER = Path(__file__).with_name("liveness_worker.py")
PROFIT = ROOT / "forex_bot" / "profit_protection.py"
PROFIT_HASH = "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f"
GATE = ROOT / "data" / "research" / "adaptive_ensemble" / "r56" / "phase6_connection_enablement" / "live_session_gate.py"
R59 = ROOT / "data" / "research" / "adaptive_ensemble" / "r59" / "live_session_gate.py"
R60 = ROOT / "data" / "research" / "adaptive_ensemble" / "r60" / "live_session_gate.py"
R61 = ROOT / "data" / "research" / "adaptive_ensemble" / "r61" / "live_session_gate.py"
MARKER = ROOT / "data" / "research" / "adaptive_ensemble" / "r56" / "phase6_connection_enablement" / "real_activation" / "one_session.consumed"
MARKER_HASH = "e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c"
PERMIT = ROOT / "data" / "research" / "adaptive_ensemble" / "r56" / "phase6_connection_enablement" / "real_activation" / "one_session.permit"


def _empty_snapshot():
    return {"snapshot": "COMPLETE_EMPTY", "trades": []}


def _entry(client_id: str = "client-r78") -> dict:
    return {
        "client_order_id": client_id,
        "instrument": "EUR_USD",
        "direction": "BUY",
        "requested_units": "1000",
        "account_id": ACCOUNT,
    }


def _response(fill_changes: dict | None = None, **envelope) -> dict:
    fill = {
        "id": "F-1",
        "type": "ORDER_FILL",
        "accountID": ACCOUNT,
        "instrument": "EUR_USD",
        "units": "1000",
        "orderID": "O-ORDER",
        "clientExtensions": {"id": "client-r78"},
        "tradeOpened": {"tradeID": "T-TRADE", "units": "1000"},
    }
    if fill_changes:
        fill.update(fill_changes)
    body = {
        "orderCreateTransaction": {"id": "O-ORDER", "accountID": ACCOUNT, "type": "MARKET_ORDER"},
        "orderFillTransaction": fill,
    }
    body.update(envelope)
    return body


class R78Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "r78.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        reset_journal_process_state()
        reset_startup_recovery_memory()
        self.journal = bootstrap_journal(self.path, acknowledge_empty=True)
        self.binding = account_binding(ACCOUNT)

    def tearDown(self) -> None:
        reset_startup_recovery_memory()
        reset_journal_process_state()
        try:
            self.journal.close()
        except Exception:
            pass
        self.temp.cleanup()

    def _insert_run(self, run_id: str = "RUN-1", token: str = "OWNER-1", **columns) -> None:
        values = {
            "run_id": run_id,
            "state": "RECOVERY_IN_PROGRESS",
            "owner_token": token,
            "created_at": "t0",
            "updated_at": "t0",
            "fencing_epoch": 1,
            "owner_pid": None,
            "process_start": None,
            "boot_id": None,
            "lock_identity": None,
        }
        values.update(columns)
        self.journal._conn.execute(
            """
            INSERT INTO recovery_runs (
                run_id, state, owner_token, created_at, updated_at, fencing_epoch,
                owner_pid, process_start, boot_id, lock_identity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(values[name] for name in (
                "run_id", "state", "owner_token", "created_at", "updated_at", "fencing_epoch",
                "owner_pid", "process_start", "boot_id", "lock_identity",
            )),
        )

    def _auth(self, run_id: str = "RUN-1", token: str = "OWNER-1", **changes) -> RepairAuthorisation:
        evidence = ProcessLivenessEvidence(
            status=changes.pop("status", "inactive"),
            method=changes.pop("method", "owner_token_and_exit_observation"),
            observed_owner_token=changes.pop("observed_owner_token", token),
        )
        return RepairAuthorisation(
            operator_acknowledged=changes.pop("operator_acknowledged", True),
            acknowledgement=changes.pop("acknowledgement", "operator confirms the recovery owner has exited"),
            account_binding=changes.pop("account_binding", self.binding),
            journal_path=changes.pop("journal_path", self.path),
            target_run_id=run_id,
            liveness=evidence,
        )

    def _reserve(self, client_id: str = "client-r78"):
        return begin_entry_submission(
            account_binding_value=self.binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-R78",
            position_generation=1,
            client_order_id=client_id,
            strategy_name="r78",
            stop_loss="1.09000",
            take_profit="1.12000",
            entry_reference="decision-r78",
            atr_at_entry_pips="8",
        )

    def _hold_repair(self, authorisation: RepairAuthorisation) -> dict:
        entered = Path(self.temp.name) / "entered"
        release = Path(self.temp.name) / "release"
        entered.write_text("", encoding="utf-8")
        release.write_text("wait", encoding="utf-8")
        env = os.environ.copy()
        env["R78_JOURNAL"] = self.path
        env["R78_ENTERED"] = str(entered)
        env["R78_RELEASE"] = str(release)
        process = subprocess.Popen(
            [sys.executable, "-B", str(WORKER), "hold"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 15
        while entered.read_text(encoding="utf-8") != "held" and time.time() < deadline:
            time.sleep(0.02)
        try:
            return repair_abandoned_recovery(authorisation)
        finally:
            release.write_text("go", encoding="utf-8")
            process.communicate(timeout=15)

    def test_01_schema_and_fresh_authority(self) -> None:
        self.assertEqual(SCHEMA_VERSION, 5)
        epoch = self.journal._conn.execute("SELECT fencing_epoch FROM recovery_authority WHERE id = 1").fetchone()[0]
        self.assertEqual(int(epoch), 0)

    def test_02_version_4_refuses_open_until_explicit_migration(self) -> None:
        legacy = Path(self.temp.name) / "v4.sqlite"
        connection = sqlite3.connect(legacy, isolation_level=None)
        connection.executescript(
            """
            CREATE TABLE schema_meta (
                id INTEGER PRIMARY KEY, schema_version INTEGER NOT NULL,
                bootstrapped_at TEXT, closes_authorised INTEGER
            );
            CREATE TABLE recovery_runs (
                run_id TEXT PRIMARY KEY, state TEXT NOT NULL, owner_token TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            INSERT INTO schema_meta (id, schema_version, bootstrapped_at, closes_authorised)
            VALUES (1, 4, 't', 1);
            """
        )
        connection.close()
        with self.assertRaises(JournalUnavailable) as blocked:
            open_journal(legacy)
        self.assertEqual(str(blocked.exception), "unsupported_schema")
        migrate_journal_4_to_5(legacy)
        migrated = open_journal(legacy)
        version = migrated._conn.execute("SELECT schema_version FROM schema_meta WHERE id = 1").fetchone()[0]
        self.assertEqual(int(version), 5)
        migrated.close()

    def test_03_active_owner_lock_refuses_forged_inactive_evidence(self) -> None:
        self._insert_run()
        result = self._hold_repair(self._auth())
        self.assertEqual(result["result"], "REPAIR_REFUSED")
        self.assertEqual(result["reason"], "recovery_owner_active")
        self.assertEqual(result["independent_liveness"], "lock_held")
        state = self.journal._conn.execute("SELECT state FROM recovery_runs WHERE run_id = 'RUN-1'").fetchone()[0]
        self.assertEqual(state, "RECOVERY_IN_PROGRESS")

    def test_04_crashed_owner_releases_after_process_exit(self) -> None:
        entered = Path(self.temp.name) / "entered"
        release = Path(self.temp.name) / "release"
        entered.write_text("", encoding="utf-8")
        release.write_text("", encoding="utf-8")
        env = os.environ.copy()
        env["R78_JOURNAL"] = self.path
        env["R78_ENTERED"] = str(entered)
        env["R78_RELEASE"] = str(release)
        process = subprocess.Popen([sys.executable, "-B", str(WORKER), "crash-owner"], cwd=ROOT, env=env)
        deadline = time.time() + 15
        while entered.read_text(encoding="utf-8") != "held" and time.time() < deadline:
            time.sleep(0.02)
        process.wait(timeout=10)
        self.assertEqual(process.returncode, 0)
        result = repair_abandoned_recovery(self._auth(run_id="RUN-CRASH", token="TOKEN-CRASH"))
        self.assertEqual(result["result"], "REPAIR_COMMITTED", result)
        self.assertEqual(result["process_observation"], "dead")
        epoch = self.journal._conn.execute("SELECT fencing_epoch FROM recovery_authority WHERE id = 1").fetchone()[0]
        self.assertEqual(int(epoch), 1)

    def test_05_pid_reuse_does_not_protect_a_different_process(self) -> None:
        self._insert_run(owner_pid=os.getpid(), process_start="not-the-current-start")
        result = repair_abandoned_recovery(self._auth())
        self.assertEqual(result["result"], "REPAIR_COMMITTED")
        self.assertEqual(result["process_observation"], "pid_reused")

    def test_06_same_process_start_refuses_even_without_lock(self) -> None:
        self._insert_run(owner_pid=os.getpid(), process_start=current_process_start())
        result = repair_abandoned_recovery(self._auth())
        self.assertEqual(result["result"], "REPAIR_REFUSED")
        self.assertEqual(result["reason"], "recovery_owner_active")

    def test_07_missing_and_wrong_token_and_weak_methods(self) -> None:
        self._insert_run()
        missing = repair_abandoned_recovery(self._auth(observed_owner_token=""))
        wrong = repair_abandoned_recovery(self._auth(observed_owner_token="other"))
        pid = repair_abandoned_recovery(self._auth(method="pid"))
        timestamp = repair_abandoned_recovery(self._auth(method="timestamp"))
        active = repair_abandoned_recovery(self._auth(status="active"))
        unknown = repair_abandoned_recovery(self._auth(status="unknown"))
        stale = repair_abandoned_recovery(self._auth(status="pid_reused"))
        unacked = repair_abandoned_recovery(self._auth(operator_acknowledged=False))
        self.assertEqual(missing["reason"], "process_not_proven_inactive")
        self.assertEqual(wrong["reason"], "process_not_proven_inactive")
        self.assertEqual(pid["reason"], "pid_reuse_ambiguous")
        self.assertEqual(timestamp["reason"], "timestamp_not_sufficient")
        self.assertEqual(active["reason"], "recovery_owner_active")
        self.assertEqual(unknown["reason"], "process_status_unknown")
        self.assertEqual(stale["reason"], "pid_reuse_ambiguous")
        self.assertEqual(unacked["reason"], "operator_acknowledgement_required")

    def test_08_boot_and_journal_path_fail_closed(self) -> None:
        self._insert_run(run_id="RUN-BOOT", boot_id="linux:other-boot")
        boot = repair_abandoned_recovery(self._auth(run_id="RUN-BOOT"))
        self.assertEqual(boot["reason"], "host_boot_identity_changed")
        self.journal._conn.execute("UPDATE recovery_runs SET state = 'RECOVERY_BLOCKED' WHERE run_id = 'RUN-BOOT'")
        self._insert_run(run_id="RUN-PATH", lock_identity="different-path")
        moved = repair_abandoned_recovery(self._auth(run_id="RUN-PATH"))
        self.assertEqual(moved["reason"], "journal_lock_path_changed")

    def test_09_two_repairs_one_commit(self) -> None:
        self._insert_run()
        first = repair_abandoned_recovery(self._auth())
        second = repair_abandoned_recovery(self._auth())
        self.assertEqual(first["result"], "REPAIR_COMMITTED")
        self.assertEqual(second["reason"], "recovery_claim_missing")
        count = self.journal._conn.execute("SELECT COUNT(*) FROM recovery_repairs WHERE result = 'REPAIR_COMMITTED'").fetchone()[0]
        self.assertEqual(int(count), 1)

    def test_10_overlapping_repairs(self) -> None:
        self._insert_run()
        worker = ROOT / "data" / "research" / "adaptive_ensemble" / "r77" / "poc" / "repair_worker.py"
        env = os.environ.copy()
        env["R77_JOURNAL"] = self.path
        env["R77_RUN"] = "RUN-1"
        env["R77_OWNER"] = "OWNER-1"
        env["R77_BINDING"] = self.binding
        first = subprocess.Popen([sys.executable, "-B", str(worker), "repair"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen([sys.executable, "-B", str(worker), "repair"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        outputs = [first.communicate(timeout=30)[0], second.communicate(timeout=30)[0]]
        committed = [line for line in outputs if "REPAIR_COMMITTED" in line]
        self.assertEqual(len(committed), 1)

    def test_11_stale_owner_cannot_publish_or_manage(self) -> None:
        report = execute_startup_sequence(_empty_snapshot())
        self.assertEqual(report["state"], RECOVERY_COMPLETED)
        old_epoch = current_fencing_epoch()
        self.assertTrue(live_management_permitted())
        self.journal._conn.execute(
            "UPDATE recovery_authority SET fencing_epoch = fencing_epoch + 1, updated_at = 'later'"
        )
        self.assertFalse(live_management_permitted())
        row = {
            "position_id": "pos-r78",
            "instrument": "EUR_USD",
            "direction": "BUY",
            "units": "1000",
            "entry_price": "1.1",
            "stop_loss": "1.0",
            "take_profit": "1.2",
            "broker_trade_id": "300",
            "broker_order_id": "200",
            "entry_client_order_id": "client-r78",
            "account_binding": self.binding,
            "provenance": "bot_created",
            "ownership_state": "bot_managed",
        }
        decision = evaluate_durable_row(row, _empty_snapshot())
        published = publish_recovered(row, decision)
        self.assertEqual(published["reason"], "recovery_fence_lost")
        self.assertIsNotNone(old_epoch)

    def test_12_fresh_startup_after_repair_reconciles(self) -> None:
        self._insert_run()
        released = repair_abandoned_recovery(self._auth())
        self.assertEqual(released["result"], "REPAIR_COMMITTED")
        self.assertFalse(live_management_permitted())
        report = execute_startup_sequence(_empty_snapshot())
        self.assertEqual(report["state"], RECOVERY_COMPLETED)
        self.assertTrue(live_management_permitted())

    def test_13_repair_failure_and_unresolved_rows_stay(self) -> None:
        self._insert_run()
        self._reserve()
        self.journal._conn.execute(
            "UPDATE entry_operations SET outcome = 'ENTRY_OUTCOME_AMBIGUOUS' WHERE client_order_id = 'client-r78'"
        )
        arm_active_journal_fault("before_commit")
        with self.assertRaises(JournalUnavailable):
            repair_abandoned_recovery(self._auth())
        state = self.journal._conn.execute("SELECT state FROM recovery_runs WHERE run_id = 'RUN-1'").fetchone()[0]
        outcome = self.journal._conn.execute("SELECT outcome FROM entry_operations").fetchone()[0]
        self.assertEqual(state, "RECOVERY_IN_PROGRESS")
        self.assertEqual(outcome, "ENTRY_OUTCOME_AMBIGUOUS")

    def test_14_clock_does_not_authorise_release(self) -> None:
        self._insert_run(created_at="2099-01-01T00:00:00+00:00", updated_at="2000-01-01T00:00:00+00:00")
        future = repair_abandoned_recovery(self._auth())
        self.assertEqual(future["result"], "REPAIR_COMMITTED")
        self.assertEqual(owner_process_status(None, None), "unrecorded")

    def test_15_repair_does_not_enable_trading(self) -> None:
        self._insert_run()
        result = repair_abandoned_recovery(self._auth())
        text = Path(ROOT / "forex_bot" / "recovery_repair.py").read_text(encoding="utf-8")
        self.assertEqual(result["result"], "REPAIR_COMMITTED")
        self.assertNotIn("orderCreate", text)
        self.assertNotIn("one_session.permit", text)
        self.assertFalse(PERMIT.exists())
        self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", GATE.read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(MARKER.read_bytes()).hexdigest(), MARKER_HASH)
        self.assertEqual(hashlib.sha256(PROFIT.read_bytes()).hexdigest(), PROFIT_HASH)
        self.assertEqual(hashlib.sha256(R59.read_bytes()).hexdigest(), "2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2")
        self.assertEqual(hashlib.sha256(R60.read_bytes()).hexdigest(), "2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2")
        self.assertEqual(hashlib.sha256(R61.read_bytes()).hexdigest(), "2f89959f8cae0e45589b16d159f038af370aa9cec592455784046ef57230c4c0")
        self.assertEqual(hashlib.sha256(GATE.read_bytes()).hexdigest(), "75a2031a5dd199996eec0b533cf4a83b44362d366fad65ff3585b8151bc18cac")

    def test_16_investigation_does_not_resolve_or_retry(self) -> None:
        permit = self._reserve()
        self.journal._conn.execute(
            "UPDATE entry_operations SET outcome = 'ENTRY_OUTCOME_AMBIGUOUS' WHERE operation_id = ?",
            (permit.operation_id,),
        )
        recorded = record_entry_investigation(
            permit.operation_id,
            {"snapshot": "COMPLETE", "transactions": [_response()["orderFillTransaction"]]},
        )
        outcome = self.journal._conn.execute("SELECT outcome FROM entry_operations").fetchone()[0]
        self.assertEqual(outcome, "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertTrue(recorded["outcome_unchanged"])
        self.assertFalse(recorded["retry_permitted"])
        with self.assertRaises(JournalUnavailable) as duplicate:
            self._reserve()
        self.assertIn(str(duplicate.exception), {"client_order_id_retained", "unresolved_entry_exists"})

    def test_17_protocol_fixtures(self) -> None:
        cases = [
            ("single", _response(), ENTRY_CONFIRMED_SINGLE_TRADE, "T-TRADE", True),
            ("order_not_trade", _response(), ENTRY_CONFIRMED_SINGLE_TRADE, "T-TRADE", True),
            ("missing_fill", {"orderCreateTransaction": {"id": "O-ORDER", "clientExtensions": {"id": "client-r78"}}}, ENTRY_OUTCOME_AMBIGUOUS, "", False),
            ("multiple", _response({"tradeOpened": None, "tradesOpened": [{"tradeID": "T-1", "units": "500"}, {"tradeID": "T-2", "units": "500"}]}), ENTRY_CONFIRMED_MULTIPLE_TRADES, "", False),
            ("partial", _response({"units": "400", "tradeOpened": {"tradeID": "T-PART", "units": "400"}}), ENTRY_PARTIAL_OR_MIXED_EFFECT, "T-PART", False),
            ("reduced", _response({"tradeReduced": {"tradeID": "T-OLD", "units": "100"}}), ENTRY_PARTIAL_OR_MIXED_EFFECT, "", False),
            ("closed", _response({"tradesClosed": [{"tradeID": "T-OLD", "units": "1000"}]}), ENTRY_PARTIAL_OR_MIXED_EFFECT, "", False),
            ("cancel", {"orderCancelTransaction": {"id": "C-1", "orderID": "O-ORDER", "type": "ORDER_CANCEL"}}, ENTRY_REJECTED_CONFIRMED, "", False),
            ("reject", {"orderRejectTransaction": {"id": "R-1", "type": "ORDER_REJECT"}}, ENTRY_REJECTED_CONFIRMED, "", False),
            ("missing_client", _response({"clientExtensions": {}}), ENTRY_EVIDENCE_CONFLICT, "", False),
            ("conflict_client", _response({"clientExtensions": {"id": "other-client"}}), ENTRY_EVIDENCE_CONFLICT, "", False),
            ("wrong_account", _response({"accountID": "001-002-0000001-004"}), ENTRY_EVIDENCE_CONFLICT, "", False),
            ("wrong_instrument", _response({"instrument": "GBP_USD"}), ENTRY_EVIDENCE_CONFLICT, "", False),
            ("wrong_direction", _response({"units": "-1000", "tradeOpened": {"tradeID": "T-SELL", "units": "-1000"}}), ENTRY_EVIDENCE_CONFLICT, "", False),
            ("wrong_units", _response({"units": "1001", "tradeOpened": {"tradeID": "T-UNITS", "units": "1001"}}), ENTRY_PARTIAL_OR_MIXED_EFFECT, "T-UNITS", False),
            ("missing_related", _response(), ENTRY_CONFIRMED_SINGLE_TRADE, "T-TRADE", True),
            ("same_order_and_trade_id", _response({"orderID": "SAME", "tradeOpened": {"tradeID": "SAME", "units": "1000"}}, orderCreateTransaction={"id": "SAME"}), ENTRY_RECONCILIATION_REQUIRED, "", False),
            ("retrieved_conflict", _response(), ENTRY_EVIDENCE_CONFLICT, "", False),
        ]
        for name, response, expected, trade_id, manageable in cases:
            with self.subTest(name=name):
                retrieved = {"id": "OTHER", "instrument": "EUR_USD"} if name == "retrieved_conflict" else None
                classified = classify_entry_response(
                    response,
                    account_id=ACCOUNT,
                    instrument="EUR_USD",
                    direction="BUY",
                    requested_units=Decimal("1000"),
                    client_order_id="client-r78",
                    retrieved_fill=retrieved,
                )
                self.assertEqual(classified["state"], expected)
                self.assertEqual(classified["broker_trade_id"], trade_id)
                self.assertFalse(classified["manageable"]) if not manageable else self.assertTrue(classified["manageable"])
                if trade_id:
                    self.assertNotEqual(classified["broker_trade_id"], classified["broker_order_id"])
        absent = classify_entry_investigation(_entry(), {"snapshot": "COMPLETE", "transactions": []})
        self.assertEqual(absent["classification"], "no_matching_evidence")
        self.assertFalse(absent["retry_permitted"])
        incomplete = classify_entry_investigation(_entry(), {"snapshot": "INCOMPLETE", "transactions": []})
        self.assertEqual(incomplete["classification"], "snapshot_incomplete")
        unavailable = classify_entry_investigation(_entry(), None)
        self.assertEqual(unavailable["classification"], "evidence_unavailable")
        reject = classify_entry_investigation(_entry(), {"snapshot": "COMPLETE", "transactions": [{"type": "ORDER_REJECT", "clientOrderID": "client-r78", "accountID": ACCOUNT, "instrument": "EUR_USD"}]})
        self.assertEqual(reject["classification"], "rejected_order_found")
        unknown = evaluate_durable_row(
            {"instrument": "EUR_USD", "broker_trade_id": "900", "direction": "BUY", "units": "1", "provenance": "unknown", "ownership_state": "unknown", "account_binding": self.binding},
            {"snapshot": "COMPLETE", "trades": [{"trade_id": "900", "instrument": "EUR_USD", "direction": "BUY", "units": "1", "account_binding": self.binding, "provenance": "broker_only"}]},
        )
        self.assertFalse(unknown["manageable"])

    def test_18_client_identity_and_duplicate_reservation(self) -> None:
        self.assertEqual(canonical_client_order_id(" client-r78 "), "client-r78")
        self._reserve()
        with self.assertRaises(JournalUnavailable):
            self._reserve()

    def test_19_management_blocked_before_recovery(self) -> None:
        self.assertFalse(live_management_permitted())
        report = execute_startup_sequence({"snapshot": "REQUEST_FAILED", "trades": []})
        self.assertEqual(report["state"], RECOVERY_BLOCKED)
        self.assertFalse(live_management_permitted())

    def test_21_second_startup_is_blocked_while_owner_holds_the_lock(self) -> None:
        entered = Path(self.temp.name) / "entered"
        release = Path(self.temp.name) / "release"
        entered.write_text("", encoding="utf-8")
        release.write_text("wait", encoding="utf-8")
        env = os.environ.copy()
        env["R78_JOURNAL"] = self.path
        env["R78_ENTERED"] = str(entered)
        env["R78_RELEASE"] = str(release)
        process = subprocess.Popen(
            [sys.executable, "-B", str(WORKER), "hold"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 15
        while entered.read_text(encoding="utf-8") != "held" and time.time() < deadline:
            time.sleep(0.02)
        try:
            report = execute_startup_sequence(_empty_snapshot())
        finally:
            release.write_text("go", encoding="utf-8")
            process.communicate(timeout=15)
        self.assertEqual(report["state"], RECOVERY_BLOCKED)
        self.assertEqual(report["reason"], "recovery_already_in_progress")
        self.assertFalse(live_management_permitted())

    def test_20_corrupt_and_schema_mismatch(self) -> None:
        corrupt = Path(self.temp.name) / "bad.sqlite"
        corrupt.write_bytes(b"not-sqlite")
        with self.assertRaises(JournalUnavailable):
            open_journal(corrupt)
        self.journal._conn.execute("UPDATE schema_meta SET schema_version = 4")
        reset_journal_process_state()
        with self.assertRaises(JournalUnavailable) as mismatch:
            open_journal(self.path)
        self.assertEqual(str(mismatch.exception), "unsupported_schema")


if __name__ == "__main__":
    unittest.main(verbosity=2)
