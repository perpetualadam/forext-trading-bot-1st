"""R.76 entry identity, durable capture, and startup recovery. Synthetic broker only."""

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
from forex_bot.broker_close_evidence import apply_transaction_body  # noqa: E402
from forex_bot.broker_entry_evidence import classify_entry_response  # noqa: E402
from forex_bot.broker_exit import local_broker_trade_ids  # noqa: E402
from forex_bot.broker_protection import interpret_trade_protection  # noqa: E402
from forex_bot.close_journal import (  # noqa: E402
    JournalUnavailable,
    account_binding,
    arm_active_journal_fault,
    bootstrap_journal,
    reset_journal_process_state,
)
from forex_bot.entry_capture import record_entry_response  # noqa: E402
from forex_bot.entry_journal import (  # noqa: E402
    begin_entry_submission,
    claim_entry_permit,
    entry_row,
    recover_entry_operations,
)
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import (  # noqa: E402
    _place_market_order_open_sync,
    _place_market_order_sync,
    _submit_order_create,
    execute_oanda_market_close,
)
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.position_recovery import (  # noqa: E402
    classify_broker_discovery,
    durable_positions,
    persist_bot_position,
    persist_protection_progress,
    store_incomplete_position,
)
from forex_bot.positions import (  # noqa: E402
    Position,
    broker_observations,
    position_management_permitted,
    positions,
)
from forex_bot.profit_protection import (  # noqa: E402
    activation_trigger_pips,
    pip_size,
    profit_giveback_atr_multiplier,
    profit_giveback_pips,
    profit_protection_atr_period,
    profit_protection_trigger_percent,
)
from forex_bot.reconciliation import BrokerSnapshotError, _interpret_open_positions  # noqa: E402
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
WORKER = Path(__file__).with_name("entry_worker.py")


class RecordingAPI:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.body: dict | None = None
        self.error: BaseException | None = None

    def request(self, request_obj):
        name = type(request_obj).__name__
        self.calls.append(name)
        if name != "OrderCreate":
            raise isolation.IsolationBreach(name)
        if self.error is not None:
            raise self.error
        return self.body


def _fill(
    *,
    trade: str = "T-TRADE",
    order: str = "O-ORDER",
    units: str = "1000",
    instrument: str = "EUR_USD",
    account: str = ACCOUNT,
    client: str = "CID-1",
    price: str = "1.10000",
    opened: dict | None | str = None,
    fill_extra: dict | None = None,
) -> dict:
    if opened == "omit":
        opened_value = None
    elif opened is None:
        opened_value = {"tradeID": trade, "units": units, "price": price}
    else:
        opened_value = opened
    fill = {
        "id": "F-1",
        "type": "ORDER_FILL",
        "accountID": account,
        "instrument": instrument,
        "units": units,
        "price": price,
        "orderID": order,
        "clientExtensions": {"id": client},
    }
    if opened_value is not None:
        fill["tradeOpened"] = opened_value
    if fill_extra:
        fill.update(fill_extra)
    return {
        "orderCreateTransaction": {"id": order, "accountID": account},
        "orderFillTransaction": fill,
    }


class EntryRecoveryTests(unittest.TestCase):
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
        broker_observations.clear()
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
        self.api = RecordingAPI()
        self.api.body = _fill()
        oanda_client._api = self.api
        self._exposure = live_safety.assert_new_live_exposure_allowed
        self.quote = mint_live_quote("EUR_USD")

    def tearDown(self) -> None:
        live_safety.assert_new_live_exposure_allowed = self._exposure
        oanda_client._api = None
        reset_journal_process_state()
        reset_startup_recovery_memory()
        positions.clear()
        broker_observations.clear()
        self.tmp.cleanup()

    def _allow_open(self) -> None:
        live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None

    def _reserve(self, client: str = "CID-1", instance: str = "INST-1", **kwargs):
        payload = dict(
            account_binding_value=BINDING,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id=instance,
            position_generation=1,
            client_order_id=client,
            strategy_name="r76",
            stop_loss="1.09000",
            take_profit="1.12000",
            entry_reference="decision-1",
            atr_at_entry_pips="8",
        )
        payload.update(kwargs)
        return begin_entry_submission(**payload)

    def _view(self, trade_id: str = "T-TRADE", **kwargs) -> dict:
        trade = {
            "trade_id": trade_id,
            "instrument": "EUR_USD",
            "direction": "BUY",
            "units": "1000",
            "account_binding": BINDING,
            "provenance": "bot_managed",
        }
        trade.update(kwargs)
        return {"snapshot": "COMPLETE_NONEMPTY", "trades": [trade]}

    def _managed(self, **kwargs) -> Position:
        payload = dict(
            symbol="EUR_USD",
            direction="BUY",
            units=1000.0,
            entry_price=1.1,
            stop_loss=1.09,
            take_profit=1.12,
            open_time=time.time(),
            strategy_name="r76",
            rl_state="held",
            execution_kind="live",
            client_order_id="CID-1",
            broker_order_id="",
            broker_trade_ids="T-TRADE",
            position_instance_id="INST-1",
            position_generation=1,
            max_profit_pips=0.0,
            profit_protection_active=False,
            min_profit_pips=0.0,
            max_adverse_pips=0.0,
        )
        payload.update(kwargs)
        return Position(**payload)

    def test_01_valid_single_opened_trade(self) -> None:
        evidence = classify_entry_response(
            _fill(),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["state"], "ENTRY_CONFIRMED_SINGLE_TRADE")
        self.assertTrue(evidence["manageable"])
        self.assertEqual(evidence["broker_trade_id"], "T-TRADE")

    def test_02_order_id_differs_from_trade_id(self) -> None:
        evidence = classify_entry_response(
            _fill(trade="T-TRADE", order="O-ORDER"),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertNotEqual(evidence["broker_order_id"], evidence["broker_trade_id"])
        self.assertEqual(evidence["broker_order_id"], "O-ORDER")
        self.assertEqual(evidence["broker_trade_id"], "T-TRADE")

    def test_03_missing_trade_id_is_not_published(self) -> None:
        evidence = classify_entry_response(
            _fill(opened="omit"),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["state"], "ENTRY_RECONCILIATION_REQUIRED")
        self.assertEqual(evidence["reason"], "missing_trade_id")
        self.assertFalse(evidence["manageable"])

    def test_04_wrong_account(self) -> None:
        evidence = classify_entry_response(
            _fill(account="001-002-9999999-003"),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["reason"], "account_mismatch")

    def test_05_wrong_instrument(self) -> None:
        evidence = classify_entry_response(
            _fill(instrument="GBP_USD"),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["reason"], "instrument_mismatch")

    def test_06_wrong_direction(self) -> None:
        evidence = classify_entry_response(
            _fill(units="-1000"),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["reason"], "direction_mismatch")

    def test_07_wrong_units(self) -> None:
        evidence = classify_entry_response(
            _fill(units="1000", opened={"tradeID": "T-TRADE", "units": "900", "price": "1.1"}),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["reason"], "units_mismatch")
        self.assertFalse(evidence["manageable"])

    def test_08_missing_fill_transaction(self) -> None:
        evidence = classify_entry_response(
            {"lastTransactionID": "9"},
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["state"], "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertEqual(evidence["reason"], "missing_fill_transaction")

    def test_09_conflicting_retrieved_fill(self) -> None:
        evidence = classify_entry_response(
            _fill(),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
            retrieved_fill={"id": "OTHER", "instrument": "EUR_USD", "units": "1000"},
        )
        self.assertEqual(evidence["state"], "ENTRY_EVIDENCE_CONFLICT")

    def test_10_rejected_order(self) -> None:
        evidence = classify_entry_response(
            {"orderRejectTransaction": {"id": "R-1", "rejectReason": "INSUFFICIENT_MARGIN"}},
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["state"], "ENTRY_REJECTED_CONFIRMED")

    def test_11_partial_fill(self) -> None:
        evidence = classify_entry_response(
            _fill(units="400", opened={"tradeID": "T-TRADE", "units": "400", "price": "1.1"}),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["state"], "ENTRY_PARTIAL_OR_MIXED_EFFECT")
        self.assertFalse(evidence["manageable"])

    def test_12_multiple_opened_trades(self) -> None:
        evidence = classify_entry_response(
            _fill(opened={"ignored": True}, fill_extra={"tradesOpened": [
                {"tradeID": "T1", "units": "500"},
                {"tradeID": "T2", "units": "500"},
            ], "tradeOpened": None}),
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        body = _fill()
        body["orderFillTransaction"]["tradeOpened"] = None
        body["orderFillTransaction"]["tradesOpened"] = [
            {"tradeID": "T1", "units": "500"},
            {"tradeID": "T2", "units": "500"},
        ]
        evidence = classify_entry_response(
            body,
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["state"], "ENTRY_CONFIRMED_MULTIPLE_TRADES")

    def test_13_existing_trade_reduced(self) -> None:
        body = _fill()
        body["orderFillTransaction"]["tradeReduced"] = {"tradeID": "OLD", "units": "100"}
        evidence = classify_entry_response(
            body,
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["reason"], "existing_trade_reduced_or_closed")

    def test_14_existing_trade_closed(self) -> None:
        body = _fill()
        body["orderFillTransaction"]["tradesClosed"] = [{"tradeID": "OLD", "units": "1000"}]
        evidence = classify_entry_response(
            body,
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["state"], "ENTRY_PARTIAL_OR_MIXED_EFFECT")

    def test_15_malformed_broker_response(self) -> None:
        evidence = classify_entry_response(
            None,
            account_id=ACCOUNT,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            client_order_id="CID-1",
        )
        self.assertEqual(evidence["reason"], "malformed_response")

    def test_16_reservation_committed_before_request(self) -> None:
        permit = self._reserve()
        row = entry_row(permit.operation_id)
        self.assertEqual(row["outcome"], "ENTRY_SUBMITTING")
        self.assertEqual(int(row["submission_intent"]), 1)
        self.assertEqual(self.api.calls, [])

    def test_17_submission_intent_committed_before_network(self) -> None:
        permit = self._reserve()
        self._allow_open()
        self.api.body = _fill()
        _place_market_order_open_sync(
            "EUR_USD", 1000, "BUY", "CID-1", 1.09, 1.12, self.quote, entry_permit=permit
        )
        self.assertEqual(self.api.calls, ["OrderCreate"])
        self.assertEqual(entry_row(permit.operation_id)["outcome"], "ENTRY_FINALISED")

    def test_18_persistence_failure_before_submission(self) -> None:
        arm_active_journal_fault("before_commit")
        with self.assertRaises(JournalUnavailable):
            self._reserve()
        self.assertEqual(self.api.calls, [])

    def test_19_duplicate_entry_reservation(self) -> None:
        self._reserve()
        with self.assertRaises(JournalUnavailable) as caught:
            self._reserve()
        self.assertEqual(caught.exception.reason, "unresolved_entry_exists")
        self.assertEqual(self.api.calls, [])

    def test_20_two_process_entry_reservation_race(self) -> None:
        recorder = str(Path(self.tmp.name) / "recorder.sqlite")
        connection = sqlite3.connect(recorder)
        connection.execute("CREATE TABLE submissions (id INTEGER PRIMARY KEY, instrument TEXT)")
        connection.commit()
        connection.close()
        entered = str(Path(self.tmp.name) / "entered.txt")
        release = str(Path(self.tmp.name) / "release.txt")
        Path(release).write_text("wait", encoding="utf-8")
        reset_journal_process_state()
        env = os.environ.copy()
        env.update(
            {
                "CLOSE_JOURNAL_PATH": self.path,
                "R76_RECORDER": recorder,
                "R76_CLIENT": "CID-RACE",
                "R76_INSTANCE": "INST-RACE",
                "R76_ENTERED": entered,
                "R76_RELEASE": release,
            }
        )
        first = subprocess.Popen(
            [sys.executable, str(WORKER), "submit"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        deadline = time.time() + 8
        while not Path(entered).exists():
            if time.time() > deadline:
                first.kill()
                self.fail(first.stderr.read() if first.stderr else "first process did not reach OrderCreate")
            time.sleep(0.02)
        second_env = dict(env)
        second_env.pop("R76_ENTERED")
        second_env.pop("R76_RELEASE")
        second = subprocess.Popen(
            [sys.executable, str(WORKER), "submit"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=second_env,
        )
        out2, err2 = second.communicate(timeout=20)
        Path(release).write_text("go", encoding="utf-8")
        out1, err1 = first.communicate(timeout=20)
        count_connection = sqlite3.connect(recorder)
        count = count_connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        count_connection.close()
        self.assertEqual(count, 1, f"{out1}\n{err1}\n{out2}\n{err2}")
        self.assertIn("unresolved_entry_exists", out2 + err2)

    def test_21_stale_owner_token(self) -> None:
        permit = self._reserve()
        permit.owner_token = "stale"
        self._allow_open()
        with self.assertRaises(Exception):
            _submit_order_create("EUR_USD", 1000, "BUY", "CID-1", 1.09, 1.12, self.quote, permit)
        self.assertEqual(self.api.calls, [])

    def test_22_restart_after_submission_intent_does_not_resubmit(self) -> None:
        permit = self._reserve()
        reset_journal_process_state()
        recovered = recover_entry_operations()
        self.assertEqual(recovered[0]["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        with self.assertRaises(JournalUnavailable):
            self._reserve(client=permit.client_order_id)
        self.assertEqual(self.api.calls, [])

    def test_23_ambiguous_broker_timeout(self) -> None:
        permit = self._reserve()
        self._allow_open()
        self.api.error = TimeoutError("synthetic timeout")
        with self.assertRaises(TimeoutError):
            _place_market_order_open_sync(
                "EUR_USD", 1000, "BUY", "CID-1", 1.09, 1.12, self.quote, entry_permit=permit
            )
        self.assertEqual(entry_row(permit.operation_id)["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertEqual(int(entry_row(permit.operation_id)["network_permit"]), 1)
        with self.assertRaises(JournalUnavailable):
            self._reserve()

    def test_24_read_only_recovery_without_resubmission(self) -> None:
        permit = self._reserve()
        claim_entry_permit(permit)
        reset_journal_process_state()
        rows = recover_entry_operations()
        self.assertEqual(rows[0]["outcome"], "ENTRY_OUTCOME_AMBIGUOUS")
        self.assertEqual(self.api.calls, [])
        report = execute_startup_sequence(
            {
                "snapshot": "COMPLETE_NONEMPTY",
                "trades": [
                    {
                        "trade_id": "T-UNRESOLVED",
                        "instrument": "EUR_USD",
                        "direction": "BUY",
                        "units": "1000",
                        "account_binding": BINDING,
                        "provenance": "broker_only",
                    }
                ],
            }
        )
        self.assertNotIn("EUR_USD", positions)
        self.assertEqual(report["close_submission_count"], 0)
        self.assertEqual(self.api.calls, [])
        with self.assertRaises(JournalUnavailable):
            self._reserve(client=permit.client_order_id)

    def test_25_corrupt_journal_blocks_management(self) -> None:
        reset_journal_process_state()
        Path(self.path).write_bytes(b"not a sqlite database")
        report = execute_startup_sequence(self._view())
        self.assertEqual(report["state"], "RECOVERY_BLOCKED")
        self.assertFalse(live_management_permitted())

    def test_26_missing_journal_blocks_management(self) -> None:
        reset_journal_process_state()
        os.environ["CLOSE_JOURNAL_PATH"] = str(Path(self.tmp.name) / "absent.sqlite")
        report = execute_startup_sequence(self._view())
        self.assertEqual(report["reason"], "missing_journal")
        self.assertFalse(live_management_permitted())

    def test_27_unsupported_schema(self) -> None:
        reset_journal_process_state()
        connection = sqlite3.connect(self.path)
        connection.execute("UPDATE schema_meta SET schema_version = 2 WHERE id = 1")
        connection.commit()
        connection.close()
        report = execute_startup_sequence(self._view())
        self.assertEqual(report["reason"], "unsupported_schema")
        self.assertFalse(live_management_permitted())

    def test_28_verified_identity_persisted_before_publication(self) -> None:
        permit = self._reserve()
        seen = {"persisted_before_publish": False}

        original = persist_bot_position

        def wrapped(pos, binding, *, entry_operation_id=None):
            original(pos, binding, entry_operation_id=entry_operation_id)
            seen["persisted_before_publish"] = "EUR_USD" not in positions
            self.assertEqual(local_broker_trade_ids(pos), ["T-TRADE"])
            self.assertEqual(pos.broker_order_id, "")

        import forex_bot.entry_capture as capture

        capture.persist_bot_position = wrapped
        try:
            evidence = record_entry_response(permit, _fill(), account_id=ACCOUNT)
        finally:
            capture.persist_bot_position = original
        self.assertTrue(seen["persisted_before_publish"])
        self.assertTrue(evidence["published"])
        self.assertEqual(positions["EUR_USD"].broker_trade_ids, "T-TRADE")
        stored = entry_row(permit.operation_id)
        self.assertEqual(stored["broker_order_id"], "O-ORDER")
        self.assertEqual(stored["broker_trade_id"], "T-TRADE")

    def test_29_missing_trade_id_refused(self) -> None:
        permit = self._reserve()
        evidence = record_entry_response(permit, _fill(opened="omit"), account_id=ACCOUNT)
        self.assertFalse(evidence["published"])
        self.assertEqual(durable_positions(), [])

    def test_30_missing_protection_state_quarantined(self) -> None:
        permit = self._reserve(stop_loss=None, take_profit=None)
        evidence = record_entry_response(permit, _fill(), account_id=ACCOUNT)
        self.assertEqual(evidence["reason"], "missing_protection_state")
        self.assertNotIn("EUR_USD", positions)

    def test_31_duplicate_position_instance_refused(self) -> None:
        first = self._managed()
        persist_bot_position(first, BINDING)
        second = self._managed(broker_trade_ids="T-OTHER", position_instance_id="INST-1")
        with self.assertRaises(JournalUnavailable) as caught:
            persist_bot_position(second, BINDING)
        self.assertEqual(caught.exception.reason, "journal_position_disagreement")

    def test_32_duplicate_broker_trade_id_refused(self) -> None:
        persist_bot_position(self._managed(), BINDING)
        other = self._managed(position_instance_id="INST-2")
        with self.assertRaises(JournalUnavailable) as caught:
            persist_bot_position(other, BINDING)
        self.assertEqual(caught.exception.reason, "duplicate_position_identity")

    def test_33_conflicting_generation_refused(self) -> None:
        persist_bot_position(self._managed(position_generation=2), BINDING)
        with self.assertRaises(JournalUnavailable) as caught:
            persist_bot_position(self._managed(position_generation=1), BINDING)
        self.assertEqual(caught.exception.reason, "conflicting_generation")

    def test_34_crash_before_position_commit_does_not_invent_a_position(self) -> None:
        permit = self._reserve()
        claim_entry_permit(permit)
        positions.clear()
        reset_journal_process_state()
        report = execute_startup_sequence(self._view())
        self.assertNotIn("EUR_USD", positions)
        self.assertEqual(report["close_submission_count"], 0)
        self.assertEqual(self.api.calls, [])
        with self.assertRaises(JournalUnavailable):
            self._reserve()

    def test_35_crash_after_position_commit_restores_on_startup(self) -> None:
        permit = self._reserve()
        from forex_bot.entry_journal import mark_entry

        pos = self._managed(position_instance_id=permit.position_instance_id)
        persist_bot_position(pos, BINDING, entry_operation_id=permit.operation_id)
        mark_entry(
            permit.operation_id,
            outcome="ENTRY_CONFIRMED_SINGLE_TRADE",
            error="trade_opened",
            broker_order_id="O-ORDER",
            broker_trade_id="T-TRADE",
        )
        positions.clear()
        reset_journal_process_state()
        report = execute_startup_sequence(self._view())
        self.assertEqual(report["state"], "RECOVERY_COMPLETED")
        self.assertEqual(positions["EUR_USD"].broker_trade_ids, "T-TRADE")

    def test_36_crash_before_memory_publication_uses_the_durable_row(self) -> None:
        self.test_35_crash_after_position_commit_restores_on_startup()

    def test_37_crash_after_memory_publication_reloads_the_same_identity(self) -> None:
        permit = self._reserve()
        record_entry_response(permit, _fill(), account_id=ACCOUNT)
        self.assertIn("EUR_USD", positions)
        positions.clear()
        reset_journal_process_state()
        execute_startup_sequence(self._view())
        self.assertEqual(positions["EUR_USD"].position_instance_id, permit.position_instance_id)
        self.assertEqual(local_broker_trade_ids(positions["EUR_USD"]), ["T-TRADE"])

    def test_38_recovery_runs_before_management(self) -> None:
        source = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
        startup = source.index("execute_startup_sequence(load_startup_broker_view())")
        loop = source.index("while True:", startup)
        gate = source.index("live_management_permitted()")
        manage = source.index("apply_profit_protection(", gate)
        self.assertLess(startup, loop)
        self.assertLess(gate, manage)
        self.assertFalse(live_management_permitted())

    def test_39_recovery_blocked_prevents_management(self) -> None:
        positions["EUR_USD"] = self._managed()
        calls = []

        async def no_candles(symbol, count):
            return None, "NO_OHLCV"

        def forbidden(*args, **kwargs):
            calls.append("managed")

        original_load = bot_loop._load_decision_candles
        original_apply = bot_loop.apply_profit_protection
        bot_loop._load_decision_candles = no_candles
        bot_loop.apply_profit_protection = forbidden
        try:
            asyncio.run(bot_loop._evaluate_impl("EUR_USD"))
        finally:
            bot_loop._load_decision_candles = original_load
            bot_loop.apply_profit_protection = original_apply
        self.assertEqual(calls, [])
        self.assertFalse(live_management_permitted())

    def test_40_incomplete_snapshot_prevents_management(self) -> None:
        persist_bot_position(self._managed(), BINDING)
        report = execute_startup_sequence({"snapshot": "INCOMPLETE", "trades": []})
        self.assertEqual(report["state"], "RECOVERY_BLOCKED")
        self.assertTrue(report["empty_book_is_not_flat"])
        self.assertNotIn("EUR_USD", positions)
        self.assertFalse(live_management_permitted())

    def test_41_valid_durable_position_restored(self) -> None:
        persist_bot_position(self._managed(), BINDING)
        report = execute_startup_sequence(self._view())
        self.assertEqual(report["state"], "RECOVERY_COMPLETED")
        self.assertTrue(position_management_permitted(positions["EUR_USD"]))
        self.assertTrue(live_management_permitted())

    def test_42_broker_only_trade_remains_observation(self) -> None:
        decision = classify_broker_discovery("broker_only")
        self.assertFalse(decision["manageable"])
        report = execute_startup_sequence(self._view(provenance="broker_only"))
        self.assertNotIn("EUR_USD", positions)
        self.assertEqual(report["decisions"][0]["state"], "observation")

    def test_43_manual_trade_remains_unmanaged(self) -> None:
        report = execute_startup_sequence(self._view(provenance="manual"))
        self.assertFalse(report["decisions"][0]["manageable"])
        self.assertNotIn("EUR_USD", positions)

    def test_44_unknown_origin_remains_unmanaged(self) -> None:
        report = execute_startup_sequence(self._view(provenance="unknown"))
        self.assertFalse(report["decisions"][0]["manageable"])

    def test_45_ambiguous_entry_remains_quarantined(self) -> None:
        permit = self._reserve()
        claim_entry_permit(permit)
        persist_bot_position(
            self._managed(position_instance_id=permit.position_instance_id),
            BINDING,
            entry_operation_id=permit.operation_id,
        )
        positions.clear()
        reset_journal_process_state()
        report = execute_startup_sequence(self._view())
        self.assertTrue(any(item["reason"] == "ambiguous_entry" for item in report["decisions"]))
        self.assertNotIn("EUR_USD", positions)

    def test_46_ambiguous_close_remains_blocked(self) -> None:
        from forex_bot.broker_close_evidence import run_guarded_live_close

        class CloseAPI:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def request(self, request_obj):
                name = type(request_obj).__name__
                self.calls.append(name)
                if name != "PositionClose":
                    raise isolation.IsolationBreach(name)
                raise TimeoutError("synthetic close timeout")

        pos = self._managed()
        positions[pos.symbol] = pos
        close_api = CloseAPI()
        oanda_client._api = close_api
        first = asyncio.run(run_guarded_live_close(pos, reason="r76"))
        self.assertNotEqual(getattr(first, "confirmation_state", ""), "CLOSE_FULLY_CONFIRMED")
        self.assertEqual(close_api.calls, ["PositionClose"])
        second = asyncio.run(run_guarded_live_close(pos, reason="r76-again"))
        self.assertEqual(close_api.calls, ["PositionClose"])
        self.assertNotEqual(getattr(second, "confirmation_state", ""), "CLOSE_FULLY_CONFIRMED")

    def test_47_repeated_recovery_is_idempotent(self) -> None:
        persist_bot_position(self._managed(), BINDING)
        first = execute_startup_sequence(self._view())
        second = execute_startup_sequence(self._view())
        self.assertEqual(first["state"], "RECOVERY_COMPLETED")
        self.assertEqual(second["state"], "RECOVERY_COMPLETED")
        self.assertEqual(len(durable_positions()), 1)
        self.assertEqual(positions["EUR_USD"].broker_trade_ids, "T-TRADE")

    def test_48_two_simultaneous_recovery_processes(self) -> None:
        connection = sqlite3.connect(self.path)
        connection.execute(
            """
            INSERT INTO recovery_runs (run_id, state, owner_token, created_at, updated_at)
            VALUES ('other-process', 'RECOVERY_IN_PROGRESS', 'token', 't', 't')
            """
        )
        connection.commit()
        connection.close()
        reset_journal_process_state()
        env = os.environ.copy()
        env["CLOSE_JOURNAL_PATH"] = self.path
        completed = subprocess.run(
            [sys.executable, str(WORKER), "recover"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=20,
            check=False,
        )
        self.assertIn("RECOVERY_BLOCKED", completed.stdout, completed.stderr)
        self.assertIn("recovery_already_in_progress", completed.stdout + completed.stderr)

    def test_49_missing_journal_blocks_live_management(self) -> None:
        self.test_26_missing_journal_blocks_management()

    def test_50_corrupt_journal_blocks_live_management(self) -> None:
        self.test_25_corrupt_journal_blocks_management()

    def test_51_original_tp_distance_preserved(self) -> None:
        pos = self._managed(entry_price=1.1, take_profit=1.12, stop_loss=1.09)
        trigger = activation_trigger_pips(pos)
        distance = (1.12 - 1.1) / pip_size("EUR_USD")
        self.assertAlmostEqual(trigger, round(distance * 0.67, 6))

    def test_52_mfe_preserved(self) -> None:
        pos = self._managed(max_profit_pips=12.5)
        persist_bot_position(pos, BINDING)
        positions.clear()
        execute_startup_sequence(self._view())
        self.assertEqual(positions["EUR_USD"].max_profit_pips, 12.5)

    def test_53_activated_ratchet_preserved(self) -> None:
        pos = self._managed(
            max_profit_pips=20.0,
            profit_protection_active=True,
            profit_protection_exit_pips=11.0,
            protect_activated_mfe_pips=20.0,
            protect_activated_atr_pips=8.0,
            protect_activated_giveback_pips=4.0,
            protect_activated_exit_pips=11.0,
        )
        persist_bot_position(pos, BINDING)
        positions.clear()
        execute_startup_sequence(self._view())
        restored = positions["EUR_USD"]
        self.assertTrue(restored.profit_protection_active)
        self.assertEqual(restored.profit_protection_exit_pips, 11.0)

    def test_54_missing_activated_state_quarantined(self) -> None:
        store_incomplete_position(
            {
                "position_instance_id": "INST-Q",
                "position_generation": 1,
                "account_binding": BINDING,
                "instrument": "EUR_USD",
                "trade_id": "T-TRADE",
                "direction": "BUY",
                "units": "1000",
                "execution_kind": "live",
                "provenance": "bot_managed",
                "entry_price": "1.1",
                "stop_loss": "1.09",
                "take_profit": "1.12",
                "open_time": "1",
                "strategy_name": "r76",
                "rl_state": "held",
                "client_order_id": "CID-1",
                "broker_order_id": "",
                "broker_order": 1,
                "management_status": "recorded",
                "max_profit_pips": "20",
                "profit_protection_active": 1,
                "profit_protection_seeded": 1,
                "profit_protection_close_attempt_ts": "0",
                "min_profit_pips": "0",
                "max_adverse_pips": "0",
            }
        )
        report = execute_startup_sequence(self._view())
        self.assertEqual(report["state"], "RECOVERY_COMPLETED_WITH_QUARANTINE")
        self.assertNotIn("EUR_USD", positions)

    def test_55_ratchet_never_moves_backwards(self) -> None:
        pos = self._managed(
            profit_protection_active=True,
            profit_protection_exit_pips=11.0,
            protect_activated_mfe_pips=20.0,
            protect_activated_atr_pips=8.0,
            protect_activated_giveback_pips=4.0,
            protect_activated_exit_pips=11.0,
            max_profit_pips=20.0,
        )
        persist_bot_position(pos, BINDING)
        pos.profit_protection_exit_pips = 9.0
        self.assertFalse(persist_protection_progress(pos, BINDING))
        self.assertEqual(durable_positions()[0]["profit_protection_exit_pips"], "11.0")
        pos.profit_protection_active = False
        self.assertFalse(persist_protection_progress(pos, BINDING))

    def test_56_buy_handling_preserved(self) -> None:
        pos = self._managed(direction="BUY", entry_price=1.1, take_profit=1.13)
        self.assertAlmostEqual(activation_trigger_pips(pos), round(300 * 0.67, 6))

    def test_57_sell_handling_preserved(self) -> None:
        pos = self._managed(direction="SELL", entry_price=1.1, take_profit=1.07, stop_loss=1.11)
        self.assertAlmostEqual(activation_trigger_pips(pos), round(300 * 0.67, 6))

    def test_58_jpy_pip_size_preserved(self) -> None:
        self.assertEqual(pip_size("USD_JPY"), 0.01)
        self.assertEqual(pip_size("EUR_USD"), 0.0001)
        pos = Position(
            symbol="USD_JPY",
            direction="BUY",
            units=1000,
            entry_price=150.0,
            stop_loss=149.0,
            take_profit=151.0,
            open_time=1,
            strategy_name="r76",
            rl_state="held",
            execution_kind="live",
        )
        self.assertAlmostEqual(activation_trigger_pips(pos), round(100 * 0.67, 6))

    def test_59_atr_multiplier_preserved(self) -> None:
        self.assertEqual(profit_giveback_atr_multiplier(), 0.5)
        self.assertEqual(profit_protection_atr_period(), 14)

    def test_60_four_pip_fallback_preserved(self) -> None:
        self.assertEqual(profit_giveback_pips(), 4.0)
        self.assertEqual(profit_protection_trigger_percent(), 0.67)

    def test_61_r75_close_permit_preserved(self) -> None:
        with self.assertRaises(TypeError):
            asyncio.run(execute_oanda_market_close("EUR_USD", 1000, "BUY", 1.1, execution_kind="live"))
        with self.assertRaises(TypeError):
            _place_market_order_sync("EUR_USD", 1000, "BUY")

    def test_62_legacy_close_bypass_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            asyncio.run(
                execute_trade(
                    "EUR_USD", "existing_strategy", "BUY", 1000, 1.1, 1.0, 1.2, execution_kind="live"
                )
            )
        self.assertEqual(self.api.calls, [])

    def test_63_identity_bound_deletion_preserved(self) -> None:
        from forex_bot.broker_close_evidence import live_local_delete_permitted

        self.assertFalse(live_local_delete_permitted("EUR_USD"))

    def test_64_full_fill_confirmation_preserved(self) -> None:
        result = apply_transaction_body(
            {
                "id": "TX1",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "-1000",
                "tradesClosed": [{"tradeID": "T-TRADE", "units": "1000"}],
            },
            instrument="EUR_USD",
            trade_id="T-TRADE",
            direction="BUY",
            requested_units=Decimal("1000"),
            transaction_id="TX1",
            account_id=ACCOUNT,
        )
        self.assertEqual(result["state"], "CLOSE_FULLY_CONFIRMED")

    def test_65_partial_fill_remains_unresolved(self) -> None:
        result = apply_transaction_body(
            {
                "id": "TX1",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "-400",
                "tradesClosed": [{"tradeID": "T-TRADE", "units": "400"}],
            },
            instrument="EUR_USD",
            trade_id="T-TRADE",
            direction="BUY",
            requested_units=Decimal("1000"),
            transaction_id="TX1",
            account_id=ACCOUNT,
        )
        self.assertEqual(result["state"], "CLOSE_PARTIALLY_CONFIRMED")

    def test_66_protection_evidence_does_not_authorise_a_close(self) -> None:
        evidence = interpret_trade_protection(
            {
                "trade": {
                    "id": "T-TRADE",
                    "instrument": "EUR_USD",
                    "state": "OPEN",
                    "currentUnits": "1000",
                    "stopLossOrder": {
                        "id": "S1",
                        "type": "STOP_LOSS",
                        "tradeID": "T-TRADE",
                        "state": "PENDING",
                        "price": "1.09",
                    },
                }
            },
            instrument="EUR_USD",
            trade_id="T-TRADE",
            direction="BUY",
            local_units=Decimal("1000"),
        )
        self.assertEqual(evidence.exit_attribution, "EXIT_ATTRIBUTION_UNKNOWN")
        self.assertFalse(getattr(evidence, "close_authorised", False))

    def test_67_incomplete_snapshot_fails_closed(self) -> None:
        with self.assertRaises(BrokerSnapshotError) as caught:
            _interpret_open_positions({})
        self.assertEqual(caught.exception.classification, "INCOMPLETE")
        classification, rows, trade_ids = _interpret_open_positions({"positions": []})
        self.assertEqual(classification, "COMPLETE_EMPTY")
        self.assertEqual(rows, {})
        self.assertEqual(trade_ids, {})

    def test_68_ownership_preserved(self) -> None:
        pos = self._managed(observation_only=True, execution_kind="reconcile_import")
        self.assertFalse(position_management_permitted(pos))
        self.assertFalse(classify_broker_discovery("manual")["manageable"])

    def test_69_profit_protection_source_unchanged(self) -> None:
        digest = hashlib.sha256((ROOT / "forex_bot" / "profit_protection.py").read_bytes()).hexdigest()
        self.assertEqual(digest, "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f")

    def test_70_production_gates_unchanged(self) -> None:
        source = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("execute_oanda_market_open"), 1)
        self.assertIn("production_execution_adapter_withheld", source)
        gate = (
            ROOT
            / "data"
            / "research"
            / "adaptive_ensemble"
            / "r56"
            / "phase6_connection_enablement"
            / "live_session_gate.py"
        ).read_text(encoding="utf-8")
        self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", gate)
        permits = list(ROOT.rglob("one_session.permit"))
        self.assertEqual(permits, [])
        oanda_client._api = None
        view = load_startup_broker_view()
        self.assertEqual(view["snapshot"], "REQUEST_FAILED")
        self.assertEqual(view["trades"], [])

    def test_71_single_trade_snapshot_can_restore_a_durable_row(self) -> None:
        class OpenAPI:
            def request(self, request_obj):
                if type(request_obj).__name__ != "OpenPositions":
                    raise isolation.IsolationBreach(type(request_obj).__name__)
                return {
                    "positions": [
                        {
                            "instrument": "EUR_USD",
                            "long": {"units": "1000", "averagePrice": "1.1", "tradeIDs": ["T-TRADE"]},
                            "short": {"units": "0", "tradeIDs": []},
                        }
                    ]
                }

        persist_bot_position(self._managed(), BINDING)
        positions.clear()
        oanda_client._api = OpenAPI()
        report = execute_startup_sequence(load_startup_broker_view())
        self.assertEqual(report["state"], "RECOVERY_COMPLETED")
        self.assertEqual(positions["EUR_USD"].broker_trade_ids, "T-TRADE")

    def test_72_multiple_trade_ids_are_not_merged_into_the_net(self) -> None:
        class OpenAPI:
            def request(self, request_obj):
                if type(request_obj).__name__ != "OpenPositions":
                    raise isolation.IsolationBreach(type(request_obj).__name__)
                return {
                    "positions": [
                        {
                            "instrument": "EUR_USD",
                            "long": {
                                "units": "1000",
                                "averagePrice": "1.1",
                                "tradeIDs": ["T-ONE", "T-TWO"],
                            },
                            "short": {"units": "0", "tradeIDs": []},
                        }
                    ]
                }

        persist_bot_position(self._managed(broker_trade_ids="T-ONE"), BINDING)
        positions.clear()
        oanda_client._api = OpenAPI()
        report = execute_startup_sequence(load_startup_broker_view())
        self.assertNotIn("EUR_USD", positions)
        self.assertEqual(report["state"], "RECOVERY_COMPLETED_WITH_QUARANTINE")


if __name__ == "__main__":
    unittest.main()
