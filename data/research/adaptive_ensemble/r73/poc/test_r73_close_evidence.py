"""R.73 close-result evidence. Synthetic broker only."""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import threading
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
    CLOSE_RECONCILIATION_REQUIRED,
    CLOSE_REJECTED_CONFIRMED,
    broker_flat_note,
    close_operation_for,
    declare_process_restart,
    reset_close_evidence_state,
    run_guarded_live_close,
)
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.positions import (  # noqa: E402
    Position,
    broker_observations,
    close_position,
    import_position_from_broker,
    position_management_permitted,
    positions,
)
import forex_bot.config as config_mod  # noqa: E402

ACCOUNT = "001-002-0000001-003"


class FakeAPI:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.close_body: dict | None = None
        self.transaction: dict | None = None
        self.fail_close: BaseException | None = None
        self.fail_tx: BaseException | None = None
        self.hold: threading.Event | None = None
        self.release: threading.Event | None = None
        self.held = False
        self.lock = threading.Lock()
        self.payloads: list[dict] = []
        self.positions_body: dict = {"positions": []}

    def request(self, request_obj):
        name = type(request_obj).__name__
        with self.lock:
            self.calls.append(name)
            payload = getattr(request_obj, "data", None)
            if isinstance(payload, dict):
                self.payloads.append(dict(payload))
            stall = name == "PositionClose" and self.hold is not None and not self.held
            if stall:
                self.held = True
        if name not in {"PositionClose", "TransactionDetails", "OpenPositions", "OrdersPending", "TradeDetails"}:
            raise isolation.IsolationBreach(name)
        if stall:
            assert self.hold is not None and self.release is not None
            self.hold.set()
            assert self.release.wait(5)
        if name == "PositionClose":
            if self.fail_close is not None:
                raise self.fail_close
            return self.close_body
        if name == "TransactionDetails":
            if self.fail_tx is not None:
                raise self.fail_tx
            return {"transaction": self.transaction}
        if name == "OrdersPending":
            return {"orders": []}
        if name == "OpenPositions":
            return self.positions_body
        return {"trade": {"id": "T1", "instrument": "EUR_USD", "state": "OPEN", "currentUnits": "1000"}}


def _row(**kwargs) -> Position:
    data = dict(
        symbol="EUR_USD",
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=1_700_000_000.0,
        strategy_name="existing_strategy",
        rl_state="held",
        execution_kind="live",
        broker_order_id="T1",
        broker_trade_ids="T1",
        broker_order=True,
    )
    data.update(kwargs)
    return Position(**data)


def _fill(tx_id: str = "TX1", instrument: str = "EUR_USD", units: str = "-1000", side: str = "long") -> dict:
    key = "longOrderFillTransaction" if side == "long" else "shortOrderFillTransaction"
    return {key: {"id": tx_id, "type": "ORDER_FILL", "instrument": instrument, "units": units}}


def _tx(
    tx_id: str = "TX1",
    units: str = "-1000",
    closed: str = "1000",
    trade_id: str = "T1",
    instrument: str = "EUR_USD",
    account: str = ACCOUNT,
    extra: list | None = None,
) -> dict:
    rows = [{"tradeID": trade_id, "units": closed}]
    if extra:
        rows.extend(extra)
    return {
        "id": tx_id,
        "type": "ORDER_FILL",
        "accountID": account,
        "instrument": instrument,
        "units": units,
        "tradesClosed": rows,
    }


class CloseEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["OANDA_MAX_RETRIES"] = "1"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        os.environ["EXECUTION_MODE"] = "paper_broker"
        reset_oanda_rate_limiter_for_tests()
        reset_close_evidence_state()
        positions.clear()
        broker_observations.clear()
        config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
        self.api = FakeAPI()
        oanda_client._api = self.api

    def tearDown(self) -> None:
        oanda_client._api = None
        positions.clear()
        broker_observations.clear()
        reset_close_evidence_state()

    def _install(self, pos: Position | None = None) -> Position:
        row = pos or _row()
        positions[row.symbol] = row
        return row

    def _arm_full(self) -> None:
        self.api.close_body = _fill()
        self.api.transaction = _tx()

    def _run(self, pos: Position, reason: str = "protect_hit"):
        return asyncio.run(run_guarded_live_close(pos, reason=reason))

    def _assert_no_write_endpoints(self) -> None:
        self.assertFalse(set(self.api.calls).intersection({"OrderCreate", "OrderCancel", "TradeClose"}))
        self.assertFalse(any("ClientExtensions" in str(item) for item in self.api.payloads))
        self.assertFalse((ROOT / "one_session.permit").exists())
        kinds = {item[0] for item in isolation.ATTEMPTS}
        self.assertNotIn("socket.connect", kinds)
        self.assertNotIn("psycopg2.connect", kinds)

    def test_01_full_fill_allows_one_delete(self) -> None:
        pos = self._install()
        self._arm_full()
        op = self._run(pos)
        self.assertEqual(op.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertEqual(op.confirmed_units, Decimal("1000"))
        self.assertEqual(op.remaining_units, Decimal("0"))
        self.assertTrue(op.transaction_body_retrieved)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)
        self.assertIs(close_position("EUR_USD"), pos)
        self.assertNotIn("EUR_USD", positions)
        self._assert_no_write_endpoints()

    def test_02_partial_fill_retains_and_blocks_retry(self) -> None:
        pos = self._install()
        self.api.close_body = _fill()
        self.api.transaction = _tx(closed="400")
        op = self._run(pos)
        self.assertEqual(op.confirmation_state, CLOSE_PARTIALLY_CONFIRMED)
        self.assertEqual(op.confirmed_units, Decimal("400"))
        self.assertEqual(op.remaining_units, Decimal("600"))
        self.assertIsNone(close_position("EUR_USD"))
        self.assertEqual(positions["EUR_USD"].units, 1000.0)
        again = self._run(pos)
        self.assertEqual(again.operation_id, op.operation_id)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)
        self._assert_no_write_endpoints()

    def test_03_zero_confirmed_units(self) -> None:
        pos = self._install()
        self.api.close_body = _fill()
        self.api.transaction = _tx(closed="0")
        op = self._run(pos)
        self.assertEqual(op.confirmation_state, CLOSE_RECONCILIATION_REQUIRED)
        self.assertEqual(op.confirmed_units, Decimal("0"))
        self.assertIsNone(close_position("EUR_USD"))
        self.assertIn("EUR_USD", positions)

    def test_04_rejection_does_not_delete_and_names_rejection(self) -> None:
        pos = self._install()
        self.api.close_body = {"orderRejectTransaction": {"id": "RJ1", "type": "ORDER_REJECT", "rejectReason": "INSUFFICIENT_MARGIN"}}
        op = self._run(pos)
        self.assertEqual(op.confirmation_state, CLOSE_REJECTED_CONFIRMED)
        self.assertEqual(op.confirmed_units, Decimal("0"))
        self.assertIsNone(close_position("EUR_USD"))
        self.assertEqual(self.api.calls.count("TransactionDetails"), 0)

    def test_05_and_06_timeout_is_ambiguous_and_blocks_retry(self) -> None:
        pos = self._install()
        self.api.fail_close = TimeoutError("before-body")
        op = self._run(pos)
        self.assertEqual(op.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.assertIsNone(op.confirmed_units)
        self.assertEqual(op.submission_count, 1)
        self.api.fail_close = None
        self._arm_full()
        again = self._run(pos)
        self.assertEqual(again.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)
        self.assertIsNone(close_position("EUR_USD"))

    def test_07_and_08_connection_and_http_errors_are_ambiguous(self) -> None:
        pos = self._install()
        self.api.fail_close = ConnectionError("broken")
        op = self._run(pos)
        self.assertEqual(op.error_classification, "request_exception")
        self.assertEqual(op.confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.assertIsNone(close_position("EUR_USD"))

    def test_09_missing_fill_transaction(self) -> None:
        pos = self._install()
        self.api.close_body = {"lastTransactionID": "99"}
        op = self._run(pos)
        self.assertEqual(op.error_classification, "missing_fill_transaction")
        self.assertIsNone(op.confirmed_units)
        self.assertIsNone(close_position("EUR_USD"))

    def test_10_missing_closed_trade_details(self) -> None:
        pos = self._install()
        self.api.close_body = _fill()
        self.api.transaction = _tx()
        self.api.transaction.pop("tradesClosed")
        op = self._run(pos)
        self.assertEqual(op.error_classification, "missing_closed_trade_details")
        self.assertNotEqual(op.confirmation_state, CLOSE_FULLY_CONFIRMED)

    def test_11_wrong_trade_id(self) -> None:
        pos = self._install()
        self.api.close_body = _fill()
        self.api.transaction = _tx(trade_id="OTHER")
        op = self._run(pos)
        self.assertEqual(op.error_classification, "trade_id_mismatch")
        self.assertIsNone(close_position("EUR_USD"))

    def test_12_wrong_instrument(self) -> None:
        pos = self._install()
        self.api.close_body = _fill()
        self.api.transaction = _tx(instrument="GBP_USD")
        op = self._run(pos)
        self.assertEqual(op.error_classification, "instrument_mismatch")
        self.assertNotEqual(op.confirmation_state, CLOSE_FULLY_CONFIRMED)

    def test_13_wrong_direction(self) -> None:
        pos = self._install()
        self.api.close_body = _fill(units="1000")
        self.api.transaction = _tx(units="1000")
        op = self._run(pos)
        self.assertEqual(op.error_classification, "direction_mismatch")
        self.assertIsNone(close_position("EUR_USD"))

    def test_14_wrong_account(self) -> None:
        pos = self._install()
        self.api.close_body = _fill()
        self.api.transaction = _tx(account="999-000-0000000-000")
        op = self._run(pos)
        self.assertEqual(op.error_classification, "account_mismatch")
        self.assertNotIn(ACCOUNT, op.error_classification)
        self.assertIsNone(close_position("EUR_USD"))

    def test_15_duplicate_trade_rows(self) -> None:
        pos = self._install()
        self.api.close_body = _fill()
        self.api.transaction = _tx(extra=[{"tradeID": "T1", "units": "1000"}])
        op = self._run(pos)
        self.assertEqual(op.error_classification, "duplicate_transaction_id")
        self.assertNotEqual(op.confirmation_state, CLOSE_FULLY_CONFIRMED)

    def test_16_conflicting_transaction_body(self) -> None:
        pos = self._install()
        self.api.close_body = _fill(tx_id="TX1")
        self.api.transaction = _tx(tx_id="TX9")
        op = self._run(pos)
        self.assertEqual(op.error_classification, "transaction_id_mismatch")
        self.assertIsNone(close_position("EUR_USD"))

    def test_18_excessive_units(self) -> None:
        pos = self._install()
        self.api.close_body = _fill()
        self.api.transaction = _tx(closed="1500")
        op = self._run(pos)
        self.assertEqual(op.confirmation_state, CLOSE_RECONCILIATION_REQUIRED)
        self.assertEqual(op.confirmed_units, Decimal("1500"))
        self.assertIsNone(close_position("EUR_USD"))

    def test_19_two_threads_submit_once(self) -> None:
        pos = self._install()
        self._arm_full()
        self.api.hold = threading.Event()
        self.api.release = threading.Event()
        box: dict = {}

        def worker(name: str) -> None:
            op = asyncio.run(run_guarded_live_close(pos, reason="protect_hit"))
            box[name] = (op.confirmation_state, op.submission_count)

        first = threading.Thread(target=worker, args=("a",))
        first.start()
        self.assertTrue(self.api.hold.wait(5))
        second = threading.Thread(target=worker, args=("b",))
        second.start()
        second.join(5)
        self.api.release.set()
        first.join(5)
        self.assertFalse(first.is_alive())
        self.assertEqual(self.api.calls.count("PositionClose"), 1)
        self.assertIn(CLOSE_FULLY_CONFIRMED, {box["a"][0], box["b"][0]})
        self.assertTrue(any(state != CLOSE_FULLY_CONFIRMED for state, _count in box.values()))

    def test_20_second_trigger_after_ambiguous_does_not_submit(self) -> None:
        pos = self._install()
        self.api.fail_close = TimeoutError("cycle")
        first = self._run(pos, "protect_hit")
        second = self._run(pos, "weekend_flat")
        self.assertEqual(first.operation_id, second.operation_id)
        self.assertEqual(self.api.calls.count("PositionClose"), 1)

    def test_22_empty_snapshot_preserves_ambiguous_close(self) -> None:
        from forex_bot.broker_exit import account_disappeared_broker_position

        pos = self._install()
        self.api.fail_close = TimeoutError("sent")
        op = self._run(pos)
        result = account_disappeared_broker_position(pos)
        self.assertEqual(result, "retained")
        self.assertIs(positions["EUR_USD"], pos)
        self.assertEqual(close_operation_for("EUR_USD").operation_id, op.operation_id)
        self.assertEqual(close_operation_for("EUR_USD").confirmation_state, CLOSE_OUTCOME_AMBIGUOUS)
        self.assertEqual(broker_flat_note("EUR_USD"), "broker_flat_not_close_confirmation")
        self.assertEqual(self.api.calls.count("PositionClose"), 1)

    def test_23_incomplete_snapshot_does_not_flat_the_book(self) -> None:
        from forex_bot.reconciliation import BrokerSnapshotError, _interpret_open_positions

        pos = self._install()
        self._arm_full()
        self.api.fail_tx = TimeoutError("verify")
        op = self._run(pos)
        with self.assertRaises(BrokerSnapshotError) as caught:
            _interpret_open_positions({})
        self.assertEqual(caught.exception.classification, "INCOMPLETE")
        self.assertIs(positions["EUR_USD"], pos)
        self.assertEqual(close_operation_for("EUR_USD").confirmation_state, op.confirmation_state)

    def test_24_broker_flat_without_a_close_operation(self) -> None:
        from forex_bot.broker_exit import account_disappeared_broker_position

        pos = self._install()
        result = account_disappeared_broker_position(pos)
        self.assertEqual(result, "retained")
        self.assertIn("EUR_USD", positions)
        self.assertEqual(self.api.calls.count("PositionClose"), 0)
        self.assertIsNone(close_operation_for("EUR_USD"))

    def test_26_stop_reference_does_not_submit_or_delete(self) -> None:
        from forex_bot.broker_protection import (
            EXIT_ATTRIBUTION_UNKNOWN,
            record_management_protection_evidence,
        )

        pos = self._install()
        op = self._run.__func__ if False else None
        del op
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self.assertEqual(self.api.calls.count("PositionClose"), 0)
        self.assertIn("EUR_USD", positions)

    def test_27_observation_is_not_closed(self) -> None:
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.05, 1.2, broker_trade_ids="T1")
        observed = broker_observations["EUR_USD"]
        op = self._run(observed)
        self.assertEqual(op.error_classification, "management_not_permitted")
        self.assertEqual(self.api.calls, [])
        self.assertFalse(position_management_permitted(observed))
        self.assertNotIn("EUR_USD", positions)

    def test_28_paper_close_semantics_stay_local(self) -> None:
        pos = self._install(_row(execution_kind="paper", broker_order=False, broker_order_id="", broker_trade_ids=""))
        op = self._run(pos)
        self.assertEqual(op.error_classification, "not_live_close")
        self.assertEqual(self.api.calls, [])
        self.assertIs(close_position("EUR_USD"), pos)
        self.assertNotIn("EUR_USD", positions)

    def test_29_missing_trade_id_blocks_submission(self) -> None:
        pos = self._install(_row(broker_order_id="", broker_trade_ids=""))
        op = self._run(pos)
        self.assertEqual(op.error_classification, "missing_trade_id")
        self.assertEqual(self.api.calls, [])
        again = self._run(pos)
        self.assertEqual(again.operation_id, op.operation_id)
        self.assertIsNone(close_position("EUR_USD"))

    def test_30_multiple_trade_ids(self) -> None:
        pos = self._install(_row(broker_trade_ids="T1,T2"))
        op = self._run(pos)
        self.assertEqual(op.error_classification, "multiple_trade_ids")
        self.assertEqual(self.api.calls.count("PositionClose"), 0)
        self.assertIsNone(close_position("EUR_USD"))

    def test_31_restart_keeps_unresolved_blocker_in_memory(self) -> None:
        pos = self._install()
        self.api.fail_close = TimeoutError("restart")
        op = self._run(pos)
        declare_process_restart()
        self.api.fail_close = None
        self._arm_full()
        again = self._run(pos)
        self.assertEqual(again.error_classification, "restart_unresolved")
        self.assertEqual(self.api.calls.count("PositionClose"), 1)
        self.assertEqual(again.operation_id, op.operation_id)
        self.assertIsNone(close_position("EUR_USD"))

    def test_32_and_33_verification_failure_blocks_repeat_reads(self) -> None:
        pos = self._install()
        self.api.close_body = _fill()
        self.api.fail_tx = TimeoutError("verify")
        op = self._run(pos)
        self.assertEqual(op.confirmation_state, "CLOSE_CONFIRMATION_PENDING")
        self.assertFalse(op.transaction_body_retrieved)
        again = self._run(pos)
        self.assertEqual(self.api.calls.count("TransactionDetails"), 1)
        self.assertEqual(again.operation_id, op.operation_id)
        self.assertIsNone(close_position("EUR_USD"))

    def test_35_two_symbols_can_close_concurrently(self) -> None:
        eur = self._install()
        gbp = _row(symbol="GBP_USD", broker_order_id="T2", broker_trade_ids="T2")
        positions["GBP_USD"] = gbp
        self.api.close_body = _fill()
        self.api.transaction = _tx()
        barrier = threading.Barrier(2)
        original = self.api.request

        def request(request_obj):
            if type(request_obj).__name__ == "PositionClose":
                barrier.wait(5)
            return original(request_obj)

        self.api.request = request
        box: dict = {}

        def run(name: str, pos: Position) -> None:
            box[name] = asyncio.run(run_guarded_live_close(pos, reason="protect_hit"))

        threads = [
            threading.Thread(target=run, args=("eur", eur)),
            threading.Thread(target=run, args=("gbp", gbp)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        self.assertEqual(self.api.calls.count("PositionClose"), 2)
        self.assertEqual(box["eur"].confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertEqual(box["gbp"].instrument, "GBP_USD")

    def test_sell_full_fill(self) -> None:
        pos = self._install(_row(direction="SELL"))
        self.api.close_body = _fill(units="1000", side="short")
        self.api.transaction = _tx(units="1000")
        op = self._run(pos)
        self.assertEqual(op.confirmation_state, CLOSE_FULLY_CONFIRMED)
        self.assertIs(close_position("EUR_USD"), pos)

    def test_source_wiring_and_gates(self) -> None:
        bot_loop = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
        self.assertLess(
            bot_loop.index("run_guarded_live_close(pos, reason=close_reason)"),
            bot_loop.index("removed = close_position(symbol)"),
        )
        self.assertIn("production_path_has_no_simulation_context", bot_loop)
        module = (ROOT / "forex_bot" / "broker_close_evidence.py").read_text(encoding="utf-8")
        self.assertNotIn("longClientExtensions", module)
        for gate in (
            ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py",
            ROOT / "data/research/adaptive_ensemble/r59/live_session_gate.py",
            ROOT / "data/research/adaptive_ensemble/r60/live_session_gate.py",
            ROOT / "data/research/adaptive_ensemble/r61/live_session_gate.py",
        ):
            self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", gate.read_text(encoding="utf-8"))
        marker = ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.consumed"
        self.assertEqual(
            hashlib.sha256(marker.read_bytes()).hexdigest(),
            "e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c",
        )

    def test_profit_protection_and_r72_pending_stop(self) -> None:
        from forex_bot.broker_protection import (
            ORDER_PENDING_CONFIRMED,
            PROTECTION_CONFIRMED,
            record_management_protection_evidence,
            reset_protection_evidence_state,
        )
        from forex_bot.profit_protection import (
            activation_trigger_pips,
            pip_size,
            profit_giveback_atr_multiplier,
            profit_giveback_pips,
            profit_protection_atr_period,
            profit_protection_trigger_percent,
        )
        from forex_bot.reconciliation import _interpret_open_positions

        self.assertEqual(profit_protection_trigger_percent(), 0.67)
        self.assertEqual(profit_protection_atr_period(), 14)
        self.assertEqual(profit_giveback_atr_multiplier(), 0.5)
        self.assertEqual(profit_giveback_pips(), 4.0)
        self.assertEqual(pip_size("USD_JPY"), 0.01)
        paper = _row(execution_kind="paper", broker_order=False, take_profit=1.1030, entry_price=1.1, direction="BUY")
        self.assertAlmostEqual(activation_trigger_pips(paper), 20.1)
        classification, _detail, _ids = _interpret_open_positions({"positions": []})
        self.assertEqual(classification, "COMPLETE_EMPTY")
        reset_protection_evidence_state()
        live = self._install()
        self.api.request = FakeAPI.request.__get__(self.api, FakeAPI)

        def trade_request(request_obj):
            name = type(request_obj).__name__
            self.api.calls.append(name)
            if name != "TradeDetails":
                raise isolation.IsolationBreach(name)
            return {
                "trade": {
                    "id": "T1",
                    "instrument": "EUR_USD",
                    "state": "OPEN",
                    "currentUnits": "1000",
                    "stopLossOrder": {
                        "id": "S1",
                        "type": "STOP_LOSS",
                        "tradeID": "T1",
                        "price": "1.05000",
                        "state": "PENDING",
                    },
                }
            }

        self.api.request = trade_request
        evidence = record_management_protection_evidence(live)
        self.assertEqual(evidence.stop_protection, PROTECTION_CONFIRMED)
        self.assertEqual(evidence.stop_order_state, ORDER_PENDING_CONFIRMED)
        self.assertFalse(evidence.authorises_close)
        self.assertEqual(self.api.calls.count("PositionClose"), 0)
        self.assertIn("EUR_USD", positions)


if __name__ == "__main__":
    unittest.main()
