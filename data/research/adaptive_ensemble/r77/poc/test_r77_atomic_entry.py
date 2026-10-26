"""R.77 atomic entry finalisation, client-id retention, and recovery repair.

Synthetic broker and temporary SQLite only. This does not start run_bot.
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

from forex_bot import oanda_client  # noqa: E402
from forex_bot.close_journal import (  # noqa: E402
    SCHEMA_VERSION,
    CloseSubmissionPermit,
    JournalUnavailable,
    account_binding,
    arm_active_journal_fault,
    bootstrap_journal,
    canonical_client_order_id,
    client_order_truncation_key,
    create_legacy_schema_3_database,
    migrate_journal_3_to_4,
    open_journal,
    reset_journal_process_state,
)
from forex_bot.entry_capture import record_entry_response  # noqa: E402
from forex_bot.entry_journal import (  # noqa: E402
    EntryGuardRefusal,
    archive_finalised_client_id,
    begin_entry_submission,
    claim_entry_permit,
    commit_verified_entry,
    entry_row,
)
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import (  # noqa: E402
    CloseGuardRefusal,
    _place_market_order_open_sync,
    _submit_order_create,
    _submit_position_close_body,
)
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.position_recovery import durable_positions, persist_bot_position, persist_protection_progress  # noqa: E402
from forex_bot.positions import Position, position_management_permitted, positions  # noqa: E402
from forex_bot.profit_protection import (  # noqa: E402
    profit_giveback_atr_multiplier,
    profit_giveback_pips,
    profit_protection_atr_period,
    profit_protection_trigger_percent,
)
from forex_bot.recovery_repair import (  # noqa: E402
    ProcessLivenessEvidence,
    RepairAuthorisation,
    repair_abandoned_recovery,
)
from forex_bot.startup_recovery import (  # noqa: E402
    execute_startup_sequence,
    live_management_permitted,
    load_startup_broker_view,
    reset_startup_recovery_memory,
)
from forex_bot.trading import execute_trade  # noqa: E402
import forex_bot.bot_loop as bot_loop  # noqa: E402
import forex_bot.config as config_mod  # noqa: E402
import forex_bot.live_safety as live_safety  # noqa: E402

ACCOUNT = "001-002-0000001-003"
BINDING = account_binding(ACCOUNT)
OTHER_BINDING = account_binding("001-002-0000001-004")
WORKER = Path(__file__).with_name("repair_worker.py")
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
PROFIT_HASH = "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f"
MARKER_HASH = "e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c"


class RecordingAPI:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def request(self, request_obj):
        name = type(request_obj).__name__
        self.calls.append(name)
        if name in {"OrderCreate", "PositionClose", "OrderCancel", "TradeCRCDO"}:
            raise isolation.IsolationBreach(name)
        raise isolation.IsolationBreach(name)


def _fill(units: str = "1000", trade: str = "T-TRADE", client: str = "CID-1", **extra) -> dict:
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
    fill.update(extra)
    return {
        "orderCreateTransaction": {"id": "O-ORDER", "accountID": ACCOUNT},
        "orderFillTransaction": fill,
    }


class AtomicEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["OANDA_MAX_RETRIES"] = "1"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        os.environ["EXECUTION_MODE"] = "paper_broker"
        os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "journal.sqlite")
        os.environ["CLOSE_JOURNAL_PATH"] = self.path
        bootstrap_journal(self.path, acknowledge_empty=True).close()
        reset_journal_process_state()
        reset_startup_recovery_memory()
        reset_oanda_rate_limiter_for_tests()
        positions.clear()
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
        self.api = RecordingAPI()
        oanda_client._api = self.api
        self._exposure = live_safety.assert_new_live_exposure_allowed
        self.quote = mint_live_quote("EUR_USD")

    def tearDown(self) -> None:
        live_safety.assert_new_live_exposure_allowed = self._exposure
        oanda_client._api = None
        reset_journal_process_state()
        reset_startup_recovery_memory()
        positions.clear()
        self.tmp.cleanup()

    def _reserve(self, client: str = "CID-1", instance: str = "INST-1", **kwargs):
        payload = dict(
            account_binding_value=BINDING,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id=instance,
            position_generation=1,
            client_order_id=client,
            strategy_name="r77",
            stop_loss="1.09000",
            take_profit="1.12000",
            entry_reference="decision-1",
            atr_at_entry_pips="8",
        )
        payload.update(kwargs)
        return begin_entry_submission(**payload)

    def _capture(self, permit=None, body=None, client: str = "CID-1"):
        permit = self._reserve(client) if permit is None else permit
        evidence = record_entry_response(permit, body if body is not None else _fill(client=client), account_id=ACCOUNT)
        return permit, evidence

    def _managed(self, **kwargs) -> Position:
        values = dict(
            symbol="EUR_USD",
            direction="BUY",
            units=1000.0,
            entry_price=1.1,
            stop_loss=1.09,
            take_profit=1.12,
            open_time=1.0,
            strategy_name="r77",
            rl_state="held",
            execution_kind="live",
            client_order_id="CID-1",
            broker_order_id="",
            broker_trade_ids="T-TRADE",
            broker_order=True,
            position_instance_id="INST-1",
            position_generation=1,
            max_profit_pips=0.0,
            profit_protection_active=False,
            profit_protection_close_attempt_ts=0.0,
            min_profit_pips=0.0,
            max_adverse_pips=0.0,
            atr_at_entry_pips=8.0,
        )
        values.update(kwargs)
        return Position(**values)

    def _view(self, trade_id: str = "T-TRADE") -> dict:
        return {
            "snapshot": "COMPLETE",
            "trades": [
                {
                    "trade_id": trade_id,
                    "instrument": "EUR_USD",
                    "direction": "BUY",
                    "units": "1000",
                    "account_binding": BINDING,
                    "provenance": "bot_managed",
                }
            ],
        }

    def _observe(self) -> dict:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        entries = [dict(row) for row in connection.execute("SELECT outcome, client_order_id FROM entry_operations")]
        stored = [
            dict(row)
            for row in connection.execute(
                "SELECT position_instance_id, trade_id, position_generation, entry_operation_id FROM managed_positions"
            )
        ]
        connection.close()
        return {
            "entries": entries,
            "positions": stored,
            "memory": sorted(positions),
            "broker_submissions": list(self.api.calls),
        }

    def _sql(self, statement: str, params: tuple = ()) -> None:
        reset_journal_process_state()
        connection = sqlite3.connect(self.path)
        connection.execute(statement, params)
        connection.commit()
        connection.close()

    def _insert_run(self, run_id: str = "RUN-1", token: str = "TOKEN-1") -> None:
        self._sql(
            """
            INSERT INTO recovery_runs (run_id, state, owner_token, created_at, updated_at)
            VALUES (?, 'RECOVERY_IN_PROGRESS', ?, '2026-10-25T00:00:00Z', '2026-10-25T00:00:00Z')
            """,
            (run_id, token),
        )

    def _auth(self, **kwargs) -> RepairAuthorisation:
        evidence = kwargs.pop(
            "liveness",
            ProcessLivenessEvidence("inactive", "owner_token_and_exit_observation", "TOKEN-1"),
        )
        payload = dict(
            operator_acknowledged=True,
            acknowledgement="operator confirms the recovery owner has exited",
            account_binding=BINDING,
            journal_path=self.path,
            target_run_id="RUN-1",
            liveness=evidence,
        )
        payload.update(kwargs)
        return RepairAuthorisation(**payload)

    def _run_state(self) -> str | None:
        connection = sqlite3.connect(self.path)
        row = connection.execute("SELECT state FROM recovery_runs WHERE run_id = 'RUN-1'").fetchone()
        connection.close()
        return None if row is None else row[0]

    def test_01_confirmed_single_trade_finalises(self) -> None:
        permit, evidence = self._capture()
        observed = self._observe()
        self.assertTrue(evidence["published"], observed)
        self.assertEqual(observed["entries"][0]["outcome"], "ENTRY_FINALISED")
        self.assertEqual(observed["positions"][0]["trade_id"], "T-TRADE")
        self.assertEqual(observed["positions"][0]["entry_operation_id"], permit.operation_id)
        self.assertEqual(observed["memory"], ["EUR_USD"])
        self.assertEqual(observed["broker_submissions"], [])

    def test_02_entry_and_position_share_one_commit(self) -> None:
        permit = self._reserve()
        journal = __import__("forex_bot.close_journal", fromlist=["active_journal"]).active_journal()
        commits: list[str] = []
        original = journal._commit

        def wrapped() -> None:
            commits.append("commit")
            original()

        journal._commit = wrapped
        record_entry_response(permit, _fill(), account_id=ACCOUNT)
        self.assertEqual(commits, ["commit"], self._observe())
        source = (ROOT / "forex_bot" / "entry_journal.py").read_text(encoding="utf-8")
        finaliser = source.split("def commit_verified_entry")[1].split("def archive_finalised_client_id")[0]
        self.assertLess(finaliser.index("_write_managed_position"), finaliser.index("SET outcome = ?"))
        self.assertEqual(finaliser.count("_commit()"), 1)

    def test_03_position_commit_failure_rolls_back_finalisation(self) -> None:
        permit = self._reserve()
        arm_active_journal_fault("before_commit")
        with self.assertRaises(JournalUnavailable):
            record_entry_response(permit, _fill(), account_id=ACCOUNT)
        observed = self._observe()
        self.assertEqual(observed["entries"][0]["outcome"], "ENTRY_SUBMITTING")
        self.assertEqual(observed["positions"], [])
        self.assertEqual(observed["memory"], [])
        self.assertEqual(observed["broker_submissions"], [])

    def test_04_finalisation_identity_failure_keeps_prior_position(self) -> None:
        persist_bot_position(self._managed(position_generation=2), BINDING)
        permit = self._reserve()
        with self.assertRaises(JournalUnavailable) as caught:
            commit_verified_entry(
                permit,
                self._managed(),
                broker_order_id="O-ORDER",
                broker_trade_id="T-TRADE",
                transaction_ids=("F-1",),
            )
        self.assertEqual(caught.exception.reason, "conflicting_generation")
        observed = self._observe()
        self.assertEqual(observed["entries"][0]["outcome"], "ENTRY_SUBMITTING")
        self.assertEqual(observed["positions"][0]["position_generation"], 2)
        self.assertEqual(observed["memory"], [])

    def test_05_crash_before_transaction_leaves_intent(self) -> None:
        self._reserve()
        observed = self._observe()
        self.assertEqual(observed["entries"][0]["outcome"], "ENTRY_SUBMITTING")
        self.assertEqual(observed["positions"], [])
        self.assertEqual(observed["memory"], [])

    def test_06_crash_during_transaction_rolls_back(self) -> None:
        self.test_03_position_commit_failure_rolls_back_finalisation()

    def test_07_crash_after_commit_keeps_both_rows(self) -> None:
        permit = self._reserve()
        commit_verified_entry(
            permit,
            self._managed(),
            broker_order_id="O-ORDER",
            broker_trade_id="T-TRADE",
            transaction_ids=("F-1",),
        )
        positions.clear()
        observed = self._observe()
        self.assertEqual(observed["entries"][0]["outcome"], "ENTRY_FINALISED")
        self.assertEqual(len(observed["positions"]), 1)
        self.assertEqual(observed["memory"], [])

    def test_08_crash_before_memory_publication(self) -> None:
        self.test_07_crash_after_commit_keeps_both_rows()

    def test_09_and_10_restart_after_commit_restores_memory(self) -> None:
        self._capture()
        positions.clear()
        reset_journal_process_state()
        report = execute_startup_sequence(self._view())
        self.assertEqual(report["state"], "RECOVERY_COMPLETED", report)
        self.assertIn("EUR_USD", positions)
        self.assertTrue(live_management_permitted())
        self.assertEqual(self.api.calls, [])

    def test_11_restart_after_rollback_does_not_publish(self) -> None:
        permit = self._reserve()
        arm_active_journal_fault("before_commit")
        with self.assertRaises(JournalUnavailable):
            record_entry_response(permit, _fill(), account_id=ACCOUNT)
        report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
        observed = self._observe()
        self.assertEqual(observed["entries"][0]["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertEqual(observed["positions"], [])
        self.assertEqual(observed["memory"], [])
        self.assertEqual(report["close_submission_count"], 0)
        with self.assertRaises(JournalUnavailable):
            self._reserve("CID-1", "INST-2")

    def test_12_repeated_finalisation_does_not_move_ratchet(self) -> None:
        permit, _evidence = self._capture()
        positions["EUR_USD"].profit_protection_active = True
        positions["EUR_USD"].profit_protection_exit_pips = 3.5
        positions["EUR_USD"].protect_activated_mfe_pips = 8
        positions["EUR_USD"].protect_activated_atr_pips = 8
        positions["EUR_USD"].protect_activated_giveback_pips = 4
        positions["EUR_USD"].protect_activated_exit_pips = 3.5
        self.assertTrue(persist_protection_progress(positions["EUR_USD"], BINDING))
        record_entry_response(permit, _fill(), account_id=ACCOUNT)
        connection = sqlite3.connect(self.path)
        exit_pips = connection.execute(
            "SELECT profit_protection_exit_pips FROM managed_positions"
        ).fetchone()[0]
        connection.close()
        self.assertEqual(Decimal(exit_pips), Decimal("3.5"))
        self.assertEqual(self._observe()["entries"][0]["outcome"], "ENTRY_FINALISED")

    def test_13_conflicting_trade_id_refuses_second_finalisation(self) -> None:
        self._capture()
        permit = self._reserve("CID-2", "INST-2")
        with self.assertRaises(JournalUnavailable) as caught:
            record_entry_response(permit, _fill(client="CID-2"), account_id=ACCOUNT)
        self.assertEqual(caught.exception.reason, "duplicate_position_identity")
        observed = self._observe()
        self.assertEqual([row["outcome"] for row in observed["entries"]], ["ENTRY_FINALISED", "ENTRY_SUBMITTING"])
        self.assertEqual(len(observed["positions"]), 1)

    def test_14_conflicting_position_instance_refuses(self) -> None:
        self._capture()
        permit = self._reserve("CID-2", "INST-1")
        with self.assertRaises(JournalUnavailable):
            record_entry_response(permit, _fill(trade="T-OTHER", client="CID-2"), account_id=ACCOUNT)
        self.assertEqual(self._observe()["positions"][0]["trade_id"], "T-TRADE")

    def test_15_conflicting_generation_refuses(self) -> None:
        self.test_04_finalisation_identity_failure_keeps_prior_position()

    def test_16_missing_original_take_profit_is_not_finalised(self) -> None:
        permit = self._reserve(take_profit="")
        evidence = record_entry_response(permit, _fill(), account_id=ACCOUNT)
        self.assertEqual(evidence["reason"], "missing_protection_state")
        self.assertEqual(self._observe()["positions"], [])
        self.assertNotEqual(self._observe()["entries"][0]["outcome"], "ENTRY_FINALISED")

    def test_17_missing_original_stop_is_not_finalised(self) -> None:
        permit = self._reserve(stop_loss="")
        evidence = record_entry_response(permit, _fill(), account_id=ACCOUNT)
        self.assertEqual(evidence["reason"], "missing_protection_state")
        self.assertEqual(self._observe()["memory"], [])

    def test_18_missing_protection_state_quarantines_on_startup(self) -> None:
        self._capture()
        self._sql("UPDATE managed_positions SET stop_loss = NULL")
        positions.clear()
        report = execute_startup_sequence(self._view())
        self.assertIn("missing_management_state", [item["reason"] for item in report["decisions"]])
        self.assertNotIn("EUR_USD", positions)

    def test_19_partial_fill_is_not_published(self) -> None:
        permit = self._reserve()
        evidence = record_entry_response(permit, _fill(units="500"), account_id=ACCOUNT)
        self.assertEqual(evidence["state"], "ENTRY_PARTIAL_OR_MIXED_EFFECT")
        self.assertEqual(self._observe()["positions"], [])
        self.assertEqual(self._observe()["memory"], [])

    def test_20_multiple_opened_trades_are_not_published(self) -> None:
        body = _fill()
        body["orderFillTransaction"]["tradesOpened"] = [
            {"tradeID": "T-1", "units": "1000"},
            {"tradeID": "T-2", "units": "1000"},
        ]
        body["orderFillTransaction"].pop("tradeOpened")
        permit = self._reserve()
        evidence = record_entry_response(permit, body, account_id=ACCOUNT)
        self.assertEqual(evidence["state"], "ENTRY_CONFIRMED_MULTIPLE_TRADES")
        self.assertEqual(self._observe()["positions"], [])

    def test_21_existing_trade_reduction_is_not_published(self) -> None:
        body = _fill()
        body["orderFillTransaction"]["tradeReduced"] = {"tradeID": "T-OLD", "units": "100"}
        permit = self._reserve()
        evidence = record_entry_response(permit, body, account_id=ACCOUNT)
        self.assertEqual(evidence["reason"], "existing_trade_reduced_or_closed")
        self.assertEqual(self._observe()["positions"], [])

    def test_22_existing_trade_closure_is_not_published(self) -> None:
        body = _fill()
        body["orderFillTransaction"]["tradesClosed"] = [{"tradeID": "T-OLD", "units": "1000"}]
        permit = self._reserve()
        evidence = record_entry_response(permit, body, account_id=ACCOUNT)
        self.assertEqual(evidence["state"], "ENTRY_PARTIAL_OR_MIXED_EFFECT")
        self.assertEqual(self._observe()["memory"], [])

    def test_23_ambiguous_broker_response_is_not_finalised(self) -> None:
        permit = self._reserve()
        evidence = record_entry_response(permit, None, account_id=ACCOUNT)
        self.assertEqual(evidence["state"], "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertEqual(self._observe()["positions"], [])

    def test_24_missing_fill_transaction_is_not_finalised(self) -> None:
        permit = self._reserve()
        evidence = record_entry_response(permit, {"orderCreateTransaction": {"id": "O-ORDER"}}, account_id=ACCOUNT)
        self.assertEqual(evidence["reason"], "missing_fill_transaction")
        self.assertNotEqual(self._observe()["entries"][0]["outcome"], "ENTRY_FINALISED")

    def test_25_journal_write_failure_after_synthetic_submit_stays_ambiguous(self) -> None:
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
        permit = self._reserve()
        self.api.request = lambda request_obj: _fill() if type(request_obj).__name__ == "OrderCreate" else (_ for _ in ()).throw(isolation.IsolationBreach(type(request_obj).__name__))
        calls = []
        original = self.api.request

        def request(request_obj):
            calls.append(type(request_obj).__name__)
            if type(request_obj).__name__ != "OrderCreate":
                raise isolation.IsolationBreach(type(request_obj).__name__)
            return _fill()

        self.api.request = request
        original_record = __import__("forex_bot.entry_capture", fromlist=["record_entry_response"]).record_entry_response

        def armed(permit_arg, body, *, account_id, retrieved_fill=None):
            arm_active_journal_fault("before_commit")
            return original_record(permit_arg, body, account_id=account_id, retrieved_fill=retrieved_fill)

        import forex_bot.entry_capture as capture

        capture.record_entry_response = armed
        try:
            with self.assertRaises(JournalUnavailable):
                _place_market_order_open_sync(
                    "EUR_USD", 1000, "BUY", "CID-1", 1.09, 1.12, self.quote, entry_permit=permit
                )
        finally:
            capture.record_entry_response = original_record
        self.assertEqual(calls, ["OrderCreate"])
        self.assertEqual(entry_row(permit.operation_id)["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertEqual(self._observe()["positions"], [])

    def test_26_journal_lock_timeout_refuses_reservation(self) -> None:
        external = sqlite3.connect(self.path, timeout=0.2, isolation_level=None)
        external.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaises(JournalUnavailable) as caught:
                self._reserve("CID-LOCK")
            self.assertEqual(caught.exception.reason, "journal_lock_or_disk")
        finally:
            external.execute("ROLLBACK")
            external.close()
        self.assertEqual(self._observe()["entries"], [])

    def test_27_corrupt_journal_fails_closed(self) -> None:
        reset_journal_process_state()
        Path(self.path).write_bytes(b"not a database")
        with self.assertRaises(JournalUnavailable) as caught:
            open_journal(self.path)
        self.assertEqual(caught.exception.reason, "corrupt_journal")

    def test_28_unsupported_schema_fails_closed(self) -> None:
        self._sql("UPDATE schema_meta SET schema_version = 3")
        with self.assertRaises(JournalUnavailable) as caught:
            open_journal(self.path)
        self.assertEqual(caught.exception.reason, "unsupported_schema")
        self.assertEqual(SCHEMA_VERSION, 4)

    def test_29_historical_partial_states_are_quarantined(self) -> None:
        permit = self._reserve()
        from forex_bot.entry_journal import mark_entry

        mark_entry(permit.operation_id, outcome="ENTRY_CONFIRMED_SINGLE_TRADE", error="unfinalised")
        persist_bot_position(self._managed(), BINDING, entry_operation_id=permit.operation_id)
        report = execute_startup_sequence(self._view())
        self.assertIn("unfinalised_capture", [item["reason"] for item in report["decisions"]])
        self.assertNotIn("EUR_USD", positions)
        self._sql("UPDATE entry_operations SET outcome = 'ENTRY_FINALISED', broker_trade_id = 'T-OTHER'")
        positions.clear()
        reset_startup_recovery_memory()
        report = execute_startup_sequence(self._view())
        self.assertIn("entry_position_identity_conflict", [item["reason"] for item in report["decisions"]])
        self.assertNotIn("EUR_USD", positions)

    def test_30_duplicate_durable_position_identity_refuses(self) -> None:
        persist_bot_position(self._managed(), BINDING)
        with self.assertRaises(JournalUnavailable) as caught:
            persist_bot_position(self._managed(position_instance_id="INST-2"), BINDING)
        self.assertEqual(caught.exception.reason, "duplicate_position_identity")
        self.assertEqual(len(durable_positions()), 1)

    def test_31_new_client_id_is_accepted(self) -> None:
        permit = self._reserve("CID-NEW")
        self.assertEqual(permit.client_order_id, "CID-NEW")
        self.assertEqual(self._observe()["broker_submissions"], [])

    def test_32_duplicate_unresolved_id_is_refused(self) -> None:
        self._reserve("CID-1")
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("CID-1", "INST-2")
        self.assertEqual(caught.exception.reason, "unresolved_entry_exists")

    def test_33_duplicate_finalised_id_is_refused(self) -> None:
        self._capture()
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("CID-1", "INST-2")
        self.assertEqual(caught.exception.reason, "client_order_id_retained")

    def test_34_duplicate_rejected_id_is_refused(self) -> None:
        permit = self._reserve()
        record_entry_response(
            permit,
            {"orderRejectTransaction": {"id": "R-1"}, "orderCreateTransaction": {"id": "O-ORDER"}},
            account_id=ACCOUNT,
        )
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("CID-1", "INST-2")
        self.assertEqual(caught.exception.reason, "client_order_id_retained")

    def test_35_duplicate_ambiguous_id_is_refused(self) -> None:
        permit = self._reserve()
        record_entry_response(permit, None, account_id=ACCOUNT)
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("CID-1", "INST-2")
        self.assertEqual(caught.exception.reason, "client_order_id_retained")

    def test_36_duplicate_conflicting_id_is_refused(self) -> None:
        permit = self._reserve()
        record_entry_response(permit, _fill(units="-1000"), account_id=ACCOUNT)
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("CID-1", "INST-2")
        self.assertEqual(caught.exception.reason, "client_order_id_retained")

    def test_37_duplicate_id_across_two_processes(self) -> None:
        reset_journal_process_state()
        first_env = os.environ.copy()
        first_env["R77_JOURNAL"] = self.path
        first_env["R77_CLIENT"] = "CID-PROC"
        first_env["R77_INSTANCE"] = "INST-1"
        second_env = os.environ.copy()
        second_env["R77_JOURNAL"] = self.path
        second_env["R77_CLIENT"] = "CID-PROC"
        second_env["R77_INSTANCE"] = "INST-2"
        first = subprocess.Popen([sys.executable, "-B", str(WORKER), "reserve"], cwd=ROOT, env=first_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen([sys.executable, "-B", str(WORKER), "reserve"], cwd=ROOT, env=second_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first_out, first_err = first.communicate(timeout=20)
        second_out, second_err = second.communicate(timeout=20)
        lines = [first_out.strip(), second_out.strip()]
        self.assertIn("accepted", lines, (lines, first_err, second_err))
        self.assertEqual(sum(line == "accepted" for line in lines), 1, lines)
        self.assertEqual(len(self._observe()["entries"]), 1)

    def test_38_same_id_on_another_account_binding_is_distinct(self) -> None:
        self._reserve("CID-1")
        other = begin_entry_submission(
            account_binding_value=OTHER_BINDING,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-OTHER",
            position_generation=1,
            client_order_id="CID-1",
            strategy_name="r77",
            stop_loss="1.09000",
            take_profit="1.12000",
            entry_reference="decision-1",
            atr_at_entry_pips="8",
        )
        self.assertEqual(other.client_order_id, "CID-1")
        self.assertEqual(len(self._observe()["entries"]), 2)

    def test_39_client_id_truncation_collision_is_refused(self) -> None:
        left = "C" * 128 + "X"
        right = "C" * 128 + "Y"
        self.assertEqual(client_order_truncation_key(left), client_order_truncation_key(right))
        with self.assertRaises(JournalUnavailable) as caught:
            canonical_client_order_id(left)
        self.assertEqual(caught.exception.reason, "client_order_id_exceeds_broker_limit")
        with self.assertRaises(JournalUnavailable):
            self._reserve(left)
        self.assertEqual(self._observe()["entries"], [])

    def test_40_client_id_normalisation_collision_is_refused(self) -> None:
        permit = self._reserve(" CID-1 ")
        record_entry_response(permit, _fill(client="CID-1"), account_id=ACCOUNT)
        connection = sqlite3.connect(self.path)
        stored = connection.execute("SELECT client_order_id FROM entry_operations").fetchone()[0]
        connection.close()
        self.assertEqual(stored, "CID-1")
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("CID-1", "INST-2")
        self.assertEqual(caught.exception.reason, "client_order_id_retained")

    def test_41_existing_duplicate_rows_block_migration(self) -> None:
        legacy = str(Path(self.tmp.name) / "legacy.sqlite")
        create_legacy_schema_3_database(legacy)
        connection = sqlite3.connect(legacy)
        connection.execute(
            "INSERT INTO entry_operations VALUES ('op-1', ?, 'CID-1', 'ENTRY_FINALISED', 't1')",
            (BINDING,),
        )
        connection.execute(
            "INSERT INTO entry_operations VALUES ('op-2', ?, 'CID-1', 'ENTRY_FINALISED', 't2')",
            (BINDING,),
        )
        connection.commit()
        connection.close()
        with self.assertRaises(JournalUnavailable) as caught:
            migrate_journal_3_to_4(legacy)
        self.assertEqual(caught.exception.reason, "historical_client_id_conflict")
        connection = sqlite3.connect(legacy)
        version = connection.execute("SELECT schema_version FROM schema_meta").fetchone()[0]
        count = connection.execute("SELECT COUNT(*) FROM entry_operations").fetchone()[0]
        connection.close()
        self.assertEqual(version, 3)
        self.assertEqual(count, 2)

    def test_42_interrupted_schema_migration_stays_on_version_3(self) -> None:
        legacy = str(Path(self.tmp.name) / "legacy-interrupt.sqlite")
        create_legacy_schema_3_database(legacy)
        connection = sqlite3.connect(legacy)
        connection.execute(
            "INSERT INTO entry_operations VALUES ('op-1', ?, 'CID-1', 'ENTRY_FINALISED', 't1')",
            (BINDING,),
        )
        connection.commit()
        connection.close()
        with self.assertRaises(JournalUnavailable) as caught:
            migrate_journal_3_to_4(legacy, fail_before_commit=True)
        self.assertEqual(caught.exception.reason, "migration_interrupted")
        with self.assertRaises(JournalUnavailable) as opened:
            open_journal(legacy)
        self.assertEqual(opened.exception.reason, "unsupported_schema")

    def test_43_reopening_the_journal_preserves_uniqueness(self) -> None:
        self._capture()
        reset_journal_process_state()
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("CID-1", "INST-2")
        self.assertEqual(caught.exception.reason, "client_order_id_retained")

    def test_44_archival_preserves_the_client_id_tombstone(self) -> None:
        permit, _evidence = self._capture()
        archive_finalised_client_id(permit.operation_id)
        connection = sqlite3.connect(self.path)
        entries = connection.execute("SELECT COUNT(*) FROM entry_operations").fetchone()[0]
        registry = connection.execute("SELECT COUNT(*) FROM client_order_id_registry").fetchone()[0]
        connection.close()
        self.assertEqual(entries, 0)
        self.assertEqual(registry, 1)
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("CID-1", "INST-2")
        self.assertEqual(caught.exception.reason, "client_order_id_retained")

    def test_45_missing_journal_does_not_authorise_reuse(self) -> None:
        missing = str(Path(self.tmp.name) / "absent.sqlite")
        reset_journal_process_state()
        os.environ["CLOSE_JOURNAL_PATH"] = missing
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve("CID-1")
        self.assertEqual(caught.exception.reason, "missing_journal")
        self.assertFalse(Path(missing).exists())

    def test_46_no_abandoned_claim_refuses_repair(self) -> None:
        result = repair_abandoned_recovery(self._auth())
        self.assertEqual(result["result"], "REPAIR_REFUSED")
        self.assertEqual(result["reason"], "recovery_claim_missing")
        self.assertFalse(result["trading_enabled"])
        self.assertEqual(result["order_submission_count"], 0)

    def test_47_abandoned_claim_with_inactive_owner_is_released(self) -> None:
        self._insert_run()
        result = repair_abandoned_recovery(self._auth())
        self.assertEqual(result["result"], "REPAIR_COMMITTED", result)
        self.assertEqual(self._run_state(), "RECOVERY_REPAIR_RELEASED")
        self.assertEqual(positions, {})
        self.assertEqual(self.api.calls, [])

    def test_48_active_recovery_owner_refuses_repair(self) -> None:
        self._insert_run()
        result = repair_abandoned_recovery(
            self._auth(liveness=ProcessLivenessEvidence("active", "owner_token_and_exit_observation", "TOKEN-1"))
        )
        self.assertEqual(result["reason"], "recovery_owner_active")
        self.assertEqual(self._run_state(), "RECOVERY_IN_PROGRESS")

    def test_49_unknown_process_status_refuses_repair(self) -> None:
        self._insert_run()
        result = repair_abandoned_recovery(
            self._auth(liveness=ProcessLivenessEvidence("unknown", "owner_token_and_exit_observation", "TOKEN-1"))
        )
        self.assertEqual(result["reason"], "process_status_unknown")
        self.assertEqual(self._run_state(), "RECOVERY_IN_PROGRESS")

    def test_50_pid_reuse_ambiguity_refuses_repair(self) -> None:
        self._insert_run()
        result = repair_abandoned_recovery(
            self._auth(liveness=ProcessLivenessEvidence("pid_reused", "pid", "TOKEN-1"))
        )
        self.assertEqual(result["reason"], "pid_reuse_ambiguous")
        self.assertEqual(self._run_state(), "RECOVERY_IN_PROGRESS")

    def test_51_wrong_account_binding_refuses_repair(self) -> None:
        self._insert_run()
        self._reserve()
        result = repair_abandoned_recovery(self._auth(account_binding=OTHER_BINDING))
        self.assertEqual(result["reason"], "wrong_account_binding")
        self.assertEqual(self._run_state(), "RECOVERY_IN_PROGRESS")
        self.assertEqual(self._observe()["entries"][0]["outcome"], "ENTRY_SUBMITTING")

    def test_52_wrong_journal_refuses_repair(self) -> None:
        self._insert_run()
        other = str(Path(self.tmp.name) / "other.sqlite")
        Path(other).write_bytes(b"")
        result = repair_abandoned_recovery(self._auth(journal_path=other))
        self.assertEqual(result["reason"], "wrong_journal")
        self.assertEqual(self._run_state(), "RECOVERY_IN_PROGRESS")
        self.assertEqual(Path(other).stat().st_size, 0)

    def test_53_corrupt_journal_refuses_repair(self) -> None:
        reset_journal_process_state()
        Path(self.path).write_bytes(b"corrupt")
        result = repair_abandoned_recovery(self._auth())
        self.assertEqual(result["result"], "REPAIR_REFUSED")
        self.assertEqual(result["reason"], "corrupt_journal")

    def test_54_unsupported_schema_refuses_repair(self) -> None:
        self._sql("UPDATE schema_meta SET schema_version = 3")
        result = repair_abandoned_recovery(self._auth())
        self.assertEqual(result["reason"], "unsupported_schema")

    def test_55_unresolved_entry_remains_unresolved(self) -> None:
        self._insert_run()
        self._reserve()
        repair_abandoned_recovery(self._auth())
        self.assertEqual(self._observe()["entries"][0]["outcome"], "ENTRY_SUBMITTING")

    def test_56_unresolved_close_remains_unresolved(self) -> None:
        self._insert_run()
        self._sql(
            """
            INSERT INTO close_operations (
                operation_id, position_instance_id, position_generation, account_binding, instrument,
                trade_id, direction, original_units, requested_units, confirmed_units, remaining_units,
                submission_state, confirmation_state, submission_intent, network_permit, owner_token,
                transaction_ids, attempt_count, created_at, updated_at, error_classification,
                recovery_status, schema_version
            ) VALUES (
                'close-1', 'INST-1', 1, ?, 'EUR_USD', 'T-TRADE', 'BUY', '1000', '1000', NULL, NULL,
                'SENDING', 'CLOSE_OUTCOME_AMBIGUOUS', 1, 1, 'close-token', '', 1, 't', 't', '',
                'ambiguous', 4
            )
            """,
            (BINDING,),
        )
        repair_abandoned_recovery(self._auth())
        connection = sqlite3.connect(self.path)
        state = connection.execute("SELECT confirmation_state FROM close_operations").fetchone()[0]
        connection.close()
        self.assertEqual(state, "CLOSE_OUTCOME_AMBIGUOUS")
        self.assertEqual(self.api.calls, [])

    def test_57_repair_does_not_publish_positions(self) -> None:
        self._insert_run()
        persist_bot_position(self._managed(), BINDING)
        positions.clear()
        repair_abandoned_recovery(self._auth())
        self.assertEqual(list(positions), [])
        self.assertEqual(len(durable_positions()), 1)

    def test_58_repair_does_not_submit_orders(self) -> None:
        self.test_47_abandoned_claim_with_inactive_owner_is_released()
        self.assertEqual(self.api.calls, [])

    def test_59_repair_does_not_delete_positions(self) -> None:
        self.test_57_repair_does_not_publish_positions()

    def test_60_repair_audit_record_is_committed(self) -> None:
        self._insert_run()
        repair_abandoned_recovery(self._auth())
        connection = sqlite3.connect(self.path)
        row = connection.execute(
            "SELECT result, reason, unresolved_entry_count FROM recovery_repairs"
        ).fetchone()
        connection.close()
        self.assertEqual(row[0], "REPAIR_COMMITTED")
        self.assertEqual(row[1], "abandoned_claim_released")
        self.assertEqual(row[2], 0)

    def test_61_audit_persistence_failure_leaves_the_claim(self) -> None:
        self._insert_run()
        from forex_bot.close_journal import active_journal

        active_journal()
        arm_active_journal_fault("before_commit")
        with self.assertRaises(JournalUnavailable):
            repair_abandoned_recovery(self._auth())
        self.assertEqual(self._run_state(), "RECOVERY_IN_PROGRESS")
        connection = sqlite3.connect(self.path)
        count = connection.execute("SELECT COUNT(*) FROM recovery_repairs").fetchone()[0]
        connection.close()
        self.assertEqual(count, 0)

    def test_62_two_repair_processes_release_once(self) -> None:
        self._insert_run()
        reset_journal_process_state()
        env = os.environ.copy()
        env["R77_JOURNAL"] = self.path
        env["R77_RUN"] = "RUN-1"
        env["R77_OWNER"] = "TOKEN-1"
        first = subprocess.Popen([sys.executable, "-B", str(WORKER), "repair"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen([sys.executable, "-B", str(WORKER), "repair"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first_out, first_err = first.communicate(timeout=20)
        second_out, second_err = second.communicate(timeout=20)
        lines = [first_out.strip(), second_out.strip()]
        self.assertEqual(lines.count("REPAIR_COMMITTED abandoned_claim_released"), 1, (lines, first_err, second_err))
        self.assertEqual(self._run_state(), "RECOVERY_REPAIR_RELEASED")

    def test_63_repair_interrupted_before_commit_keeps_the_claim(self) -> None:
        self.test_61_audit_persistence_failure_leaves_the_claim()

    def test_64_repair_interrupted_after_commit_stays_released(self) -> None:
        self._insert_run()
        repair_abandoned_recovery(self._auth())
        reset_journal_process_state()
        self.assertEqual(self._run_state(), "RECOVERY_REPAIR_RELEASED")
        connection = sqlite3.connect(self.path)
        count = connection.execute("SELECT COUNT(*) FROM recovery_repairs").fetchone()[0]
        connection.close()
        self.assertEqual(count, 1)

    def test_65_next_startup_reconciles_again_without_deleting(self) -> None:
        self._insert_run()
        persist_bot_position(self._managed(), BINDING)
        self._reserve("CID-KEEP", "INST-KEEP")
        repair_abandoned_recovery(self._auth())
        positions.clear()
        report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
        self.assertNotEqual(report["reason"], "recovery_already_in_progress")
        self.assertEqual(len(durable_positions()), 1)
        self.assertNotIn("EUR_USD", positions)
        outcomes = [row["outcome"] for row in self._observe()["entries"]]
        self.assertNotIn("ENTRY_FINALISED", outcomes)
        self.assertNotIn("ENTRY_REJECTED_CONFIRMED", outcomes)

    def test_66_and_67_startup_orchestration_precedes_management(self) -> None:
        source = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
        function = source.split("async def run_startup_and_one_iteration")[1].split("async def run_bot")[0]
        self.assertLess(function.index("execute_startup_sequence"), function.index("_execute_bot_cycle"))
        self._capture()
        positions.clear()
        report = asyncio.run(bot_loop.run_startup_and_one_iteration(["EUR_USD"], broker_view=self._view()))
        self.assertEqual(report["state"], "RECOVERY_COMPLETED")
        self.assertTrue(live_management_permitted())
        self.assertIn("EUR_USD", positions)
        self.assertEqual(self.api.calls.count("OrderCreate") + self.api.calls.count("PositionClose"), 0)

    def test_68_recovery_failure_blocks_management(self) -> None:
        persist_bot_position(self._managed(), BINDING)
        report = asyncio.run(
            bot_loop.run_startup_and_one_iteration(["EUR_USD"], broker_view={"snapshot": "REQUEST_FAILED", "trades": []})
        )
        self.assertEqual(report["state"], "RECOVERY_BLOCKED")
        self.assertFalse(live_management_permitted())
        self.assertNotIn("EUR_USD", positions)
        self.assertEqual(len(durable_positions()), 1)

    def test_69_missing_broker_client_blocks_management(self) -> None:
        oanda_client._api = None
        view = load_startup_broker_view()
        self.assertEqual(view["snapshot"], "REQUEST_FAILED")
        report = asyncio.run(bot_loop.run_startup_and_one_iteration(["EUR_USD"], broker_view=view))
        self.assertFalse(live_management_permitted())
        self.assertEqual(report["empty_book_is_not_flat"], True)

    def test_70_incomplete_snapshot_blocks_management(self) -> None:
        report = execute_startup_sequence({"snapshot": "INCOMPLETE", "trades": []})
        self.assertEqual(report["state"], "RECOVERY_BLOCKED")
        self.assertFalse(live_management_permitted())

    def test_71_broker_only_position_stays_observation_only(self) -> None:
        from forex_bot.position_recovery import classify_broker_discovery

        decision = classify_broker_discovery("broker_only")
        report = execute_startup_sequence(
            {"snapshot": "COMPLETE", "trades": [{"trade_id": "T-EXT", "instrument": "EUR_USD", "provenance": "broker_only"}]}
        )
        self.assertFalse(decision["manageable"])
        self.assertEqual(list(positions), [])
        self.assertTrue(any(not item.get("manageable") for item in report["decisions"]))

    def test_72_manual_trade_stays_unmanaged(self) -> None:
        from forex_bot.position_recovery import classify_broker_discovery

        self.assertFalse(classify_broker_discovery("manual")["manageable"])
        execute_startup_sequence(
            {"snapshot": "COMPLETE", "trades": [{"trade_id": "T-MAN", "instrument": "EUR_USD", "provenance": "manual"}]}
        )
        self.assertNotIn("EUR_USD", positions)

    def test_73_unknown_execution_kind_stays_unmanaged(self) -> None:
        self._sql(
            """
            INSERT INTO managed_positions (
                position_instance_id, position_generation, account_binding, instrument, trade_id,
                direction, units, execution_kind, provenance, entry_price, stop_loss, take_profit,
                open_time, strategy_name, rl_state, client_order_id, broker_order_id, broker_order,
                management_status, close_operation_id, max_profit_pips, profit_protection_active,
                profit_protection_seeded, profit_protection_exit_pips, profit_protection_close_attempt_ts,
                atr_at_entry_pips, protect_activated_mfe_pips, protect_activated_atr_pips,
                protect_activated_giveback_pips, protect_activated_exit_pips, atr_fallback_used,
                min_profit_pips, max_adverse_pips, entry_operation_id, created_at, updated_at
            ) VALUES (
                'INST-U', 1, ?, 'EUR_USD', 'T-U', 'BUY', '1000', 'mystery', 'bot_managed',
                '1.1', '1.09', '1.12', '1', 'r77', 'held', '', '', 1, 'recorded', NULL,
                '0', 0, 0, NULL, '0', '8', NULL, NULL, NULL, NULL, 0, '0', '0', NULL, 't', 't'
            )
            """,
            (BINDING,),
        )
        report = execute_startup_sequence(self._view("T-U"))
        self.assertIn("unknown_execution_kind", [item["reason"] for item in report["decisions"]])
        self.assertNotIn("EUR_USD", positions)

    def test_74_verified_durable_position_restores(self) -> None:
        self._capture()
        positions.clear()
        report = execute_startup_sequence(self._view())
        self.assertEqual(report["state"], "RECOVERY_COMPLETED")
        self.assertTrue(position_management_permitted(positions["EUR_USD"]))

    def test_75_quarantined_position_stays_unmanaged(self) -> None:
        self.test_29_historical_partial_states_are_quarantined()
        self.assertFalse(live_management_permitted() and "EUR_USD" in positions)

    def test_76_ambiguous_entry_does_not_retry(self) -> None:
        permit = self._reserve()
        record_entry_response(permit, None, account_id=ACCOUNT)
        before = list(self.api.calls)
        with self.assertRaises(JournalUnavailable):
            self._reserve("CID-1", "INST-2")
        self.assertEqual(self.api.calls, before)

    def test_77_ambiguous_close_does_not_retry(self) -> None:
        self.test_56_unresolved_close_remains_unresolved()
        self.assertNotIn("PositionClose", self.api.calls)

    def test_78_entry_permit_cannot_close(self) -> None:
        permit = self._reserve()
        claim_entry_permit(permit)
        with self.assertRaises(JournalUnavailable):
            claim_entry_permit(permit)
        with self.assertRaises(CloseGuardRefusal):
            _submit_position_close_body("EUR_USD", 1000, "BUY", permit)
        self.assertEqual(self.api.calls, [])

    def test_79_close_permit_cannot_open(self) -> None:
        permit = CloseSubmissionPermit(
            operation_id="close-x",
            owner_token="token",
            account_binding=BINDING,
            instrument="EUR_USD",
            trade_id="T-TRADE",
            direction="BUY",
            requested_units="1000",
            position_instance_id="INST-1",
            position_generation=1,
        )
        with self.assertRaises(EntryGuardRefusal):
            _submit_order_create("EUR_USD", 1000, "BUY", "CID-X", 1.09, 1.12, self.quote, permit)
        self.assertEqual(self.api.calls, [])

    def test_80_legacy_live_close_bypass_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            asyncio.run(execute_trade("EUR_USD", "r77", "BUY", 1000, 1.1, 1.09, 1.12, execution_kind="live"))
        self.assertEqual(self.api.calls, [])

    def test_81_production_adapter_remains_withheld(self) -> None:
        source = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("execute_oanda_market_open"), 1)
        self.assertIn("production_execution_adapter_withheld", source)
        self.assertEqual(bot_loop.production_adapter_refusal({"production_eligible": False}, symbol="EUR_USD", units=1, direction="BUY", client_order_id="CID"), "production_ineligible")

    def test_82_and_83_entry_and_management_gates_unchanged(self) -> None:
        with self.assertRaises(RuntimeError):
            live_safety.assert_new_live_exposure_allowed(action="open")
        self.assertIn("live_management_permitted", (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8"))

    def test_84_and_85_profit_protection_and_weekend_flatten_unchanged(self) -> None:
        digest = hashlib.sha256((ROOT / "forex_bot" / "profit_protection.py").read_bytes()).hexdigest()
        self.assertEqual(digest, PROFIT_HASH)
        self.assertEqual(profit_protection_trigger_percent(), 0.67)
        self.assertEqual(profit_protection_atr_period(), 14)
        self.assertEqual(profit_giveback_atr_multiplier(), 0.5)
        self.assertEqual(profit_giveback_pips(), 4.0)
        weekend = (ROOT / "forex_bot" / "session_rules.py").read_text(encoding="utf-8")
        self.assertIn("def flatten_for_weekend", weekend)

    def test_86_and_87_no_real_network_or_postgresql(self) -> None:
        self.assertNotIn(("psycopg2.connect",), isolation.ATTEMPTS)
        self.assertFalse(any(kind == "socket.connect" for kind, *_rest in isolation.ATTEMPTS))

    def test_88_no_live_permit_creation(self) -> None:
        self.assertEqual(list(ROOT.rglob("one_session.permit")), [])

    def test_89_consumed_marker_is_unchanged(self) -> None:
        digest = hashlib.sha256(MARKER.read_bytes()).hexdigest()
        self.assertEqual(digest, MARKER_HASH)

    def test_90_operational_journal_is_the_temporary_file(self) -> None:
        self.assertEqual(Path(os.environ["CLOSE_JOURNAL_PATH"]).resolve(), Path(self.path).resolve())
        self.assertIn(tempfile.gettempdir(), self.path)

    def test_finalised_without_position_is_not_invented(self) -> None:
        permit = self._reserve()
        self._sql(
            "UPDATE entry_operations SET outcome = 'ENTRY_FINALISED', broker_trade_id = 'T-TRADE' WHERE operation_id = ?",
            (permit.operation_id,),
        )
        report = execute_startup_sequence(self._view())
        self.assertIn("finalised_without_position", [item["reason"] for item in report["decisions"]])
        self.assertEqual(list(positions), [])

    def test_successful_migration_installs_permanent_uniqueness(self) -> None:
        legacy = str(Path(self.tmp.name) / "legacy-ok.sqlite")
        create_legacy_schema_3_database(legacy)
        connection = sqlite3.connect(legacy)
        connection.execute(
            "INSERT INTO entry_operations VALUES ('op-1', ?, 'CID-KEEP', 'ENTRY_FINALISED', 't1')",
            (BINDING,),
        )
        connection.commit()
        connection.close()
        migrate_journal_3_to_4(legacy)
        connection = sqlite3.connect(legacy)
        version = connection.execute("SELECT schema_version FROM schema_meta").fetchone()[0]
        registry = connection.execute("SELECT client_order_id FROM client_order_id_registry").fetchone()[0]
        connection.close()
        self.assertEqual(version, 4)
        self.assertEqual(registry, "CID-KEEP")
        journal = open_journal(legacy)
        journal.close()


if __name__ == "__main__":
    unittest.main(verbosity=1)
