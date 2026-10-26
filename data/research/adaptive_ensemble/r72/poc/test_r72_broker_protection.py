"""R.72 broker-protection evidence. Synthetic responses only. No broker writes."""

from __future__ import annotations

import hashlib
import os
import sys
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

from forex_bot import oanda_client  # noqa: E402
from forex_bot.broker_protection import (  # noqa: E402
    EXIT_ATTRIBUTION_UNKNOWN,
    ORDER_CANCELLED_CONFIRMED,
    ORDER_FILLED_CONFIRMED,
    ORDER_PENDING_CONFIRMED,
    ORDER_REJECTED_CONFIRMED,
    ORDER_UNKNOWN,
    PROTECTION_CONFIRMED,
    PROTECTION_CONFLICT,
    PROTECTION_UNKNOWN,
    STOP_LOSS_FILL_CONFIRMED,
    TAKE_PROFIT_FILL_CONFIRMED,
    UNPROTECTED_CONFIRMED,
    published_protection_evidence,
    record_management_protection_evidence,
    reset_protection_evidence_state,
)
from forex_bot.live_manage import broker_sl_tp_hit  # noqa: E402
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.positions import (  # noqa: E402
    Position,
    broker_observations,
    import_position_from_broker,
    position_management_permitted,
    positions,
)
import forex_bot.config as config_mod  # noqa: E402

WRITE_ENDPOINTS = {
    "OrderCreate",
    "OrderCancel",
    "OrderReplace",
    "PositionClose",
    "TradeClose",
    "StopLossOrder",
    "TakeProfitOrder",
}
UNCHANGED = {
    "forex_bot/positions.py": "129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5",
    "forex_bot/profit_protection.py": "d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f",
    "forex_bot/trading.py": "5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7",
    "forex_bot/reconciliation.py": "df67cc020986e0056b4bf3bea6fbbd9947090741cafa8793a4ac57660a0b9165",
    "forex_bot/broker_exit.py": "bcdc3e04908208f8c397acb291eceae19fca5dc78028a6914269d409cc53474c",
    "forex_bot/oanda_exec.py": "f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8",
    "main.py": "4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb",
}


class FakeAPI:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.bodies: list[object] = []
        self.fail: BaseException | None = None
        self.hold: threading.Event | None = None
        self.release: threading.Event | None = None
        self.held = False
        self.lock = threading.Lock()

    def request(self, request_obj):
        name = type(request_obj).__name__
        with self.lock:
            self.calls.append(name)
            stall = self.hold is not None and not self.held
            if stall:
                self.held = True
            body = self.bodies.pop(0) if self.bodies else None
            fail = self.fail
        if name != "TradeDetails":
            raise isolation.IsolationBreach(name)
        if stall:
            assert self.hold is not None
            self.hold.set()
            assert self.release is not None and self.release.wait(5)
        if fail is not None:
            raise fail
        return body


def _row(kind: str = "live", **kwargs) -> Position:
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
        execution_kind=kind,
        broker_order_id="T1",
        broker_trade_ids="T1",
        broker_order=True,
        observation_only=False,
    )
    data.update(kwargs)
    return Position(**data)


def _stop(order_id: str = "S1", **kwargs) -> dict:
    order = {
        "id": order_id,
        "type": "STOP_LOSS",
        "tradeID": "T1",
        "price": "1.05000",
        "state": "PENDING",
    }
    order.update(kwargs)
    return order


def _tp(order_id: str = "P1", **kwargs) -> dict:
    order = {
        "id": order_id,
        "type": "TAKE_PROFIT",
        "tradeID": "T1",
        "price": "1.20000",
        "state": "PENDING",
    }
    order.update(kwargs)
    return order


def _body(symbol: str = "EUR_USD", units: str = "1000", **trade) -> dict:
    base = {
        "id": "T1",
        "instrument": symbol,
        "state": "OPEN",
        "currentUnits": units,
    }
    base.update(trade)
    return {"trade": base}


class BrokerProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["OANDA_MAX_RETRIES"] = "1"
        os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
        reset_oanda_rate_limiter_for_tests()
        reset_protection_evidence_state()
        positions.clear()
        broker_observations.clear()
        config_mod.Config.OANDA_ACCOUNT_ID = "001-002-0000001-003"
        self.api = FakeAPI()
        oanda_client._api = self.api

    def tearDown(self) -> None:
        oanda_client._api = None
        positions.clear()
        broker_observations.clear()

    def _install(self, pos: Position) -> Position:
        positions[pos.symbol] = pos
        return pos

    def _assert_inert(self, pos: Position, evidence) -> None:
        self.assertFalse(evidence.local_prices_are_broker_evidence)
        self.assertFalse(evidence.authorises_close)
        self.assertFalse(evidence.authorises_management)
        self.assertFalse(evidence.authorises_local_delete)
        self.assertNotEqual(evidence.exit_attribution, STOP_LOSS_FILL_CONFIRMED)
        self.assertNotEqual(evidence.exit_attribution, TAKE_PROFIT_FILL_CONFIRMED)
        self.assertIs(positions.get(pos.symbol), pos)
        self.assertFalse(pos.observation_only and position_management_permitted(pos))
        self.assertFalse(WRITE_ENDPOINTS.intersection(self.api.calls))
        self.assertFalse((ROOT / "one_session.permit").exists())
        kinds = {item[0] for item in isolation.ATTEMPTS}
        self.assertNotIn("psycopg2.connect", kinds)
        self.assertNotIn("socket.connect", kinds)
        self.assertNotIn("urlopen", kinds)
        self.assertFalse(broker_sl_tp_hit(pos))

    def test_01_pending_stop_buy_eur(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=_stop()))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.stop_protection, PROTECTION_CONFIRMED)
        self.assertEqual(evidence.stop_order_state, ORDER_PENDING_CONFIRMED)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self.assertEqual(evidence.orders[0].price, Decimal("1.05000"))
        self.assertEqual(self.api.calls, ["TradeDetails"])
        self._assert_inert(pos, evidence)

    def test_02_pending_take_profit(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(takeProfitOrder=_tp()))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.take_profit_protection, PROTECTION_CONFIRMED)
        self.assertEqual(evidence.take_profit_order_state, ORDER_PENDING_CONFIRMED)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_03_both_pending(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=_stop(), takeProfitOrder=_tp()))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.protection_state, PROTECTION_CONFIRMED)
        self.assertEqual(evidence.stop_protection, PROTECTION_CONFIRMED)
        self.assertEqual(evidence.take_profit_protection, PROTECTION_CONFIRMED)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_04_sell_usd_jpy_pending_stop(self) -> None:
        pos = self._install(
            _row(symbol="USD_JPY", direction="SELL", units=1000, stop_loss=151.0, take_profit=148.0)
        )
        self.api.bodies.append(
            _body(
                symbol="USD_JPY",
                units="-1000",
                stopLossOrder=_stop(price="151.200"),
            )
        )
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.instrument, "USD_JPY")
        self.assertEqual(evidence.stop_protection, PROTECTION_CONFIRMED)
        self.assertEqual(evidence.orders[0].price, Decimal("151.200"))
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_08_explicit_null_stop_is_confirmed_absence(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=None, takeProfitOrder=None))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.stop_protection, UNPROTECTED_CONFIRMED)
        self.assertEqual(evidence.take_profit_protection, UNPROTECTED_CONFIRMED)
        self.assertEqual(evidence.protection_state, UNPROTECTED_CONFIRMED)
        self.assertNotEqual(pos.stop_loss, 0)
        self._assert_inert(pos, evidence)

    def test_09_missing_stop_field_is_not_absence(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(takeProfitOrder=None))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.stop_protection, PROTECTION_UNKNOWN)
        self.assertNotEqual(evidence.stop_protection, UNPROTECTED_CONFIRMED)
        self.assertEqual(evidence.protection_state, PROTECTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_10_missing_trade_id(self) -> None:
        pos = self._install(_row(broker_order_id="", broker_trade_ids=""))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "missing_trade_id")
        self.assertEqual(evidence.protection_state, PROTECTION_UNKNOWN)
        self.assertEqual(self.api.calls, [])
        self._assert_inert(pos, evidence)

    def test_11_missing_account(self) -> None:
        config_mod.Config.OANDA_ACCOUNT_ID = ""
        pos = self._install(_row())
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "missing_account")
        self.assertEqual(self.api.calls, [])
        self._assert_inert(pos, evidence)

    def test_12_missing_client(self) -> None:
        oanda_client._api = None
        pos = self._install(_row())
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "missing_client")
        self._assert_inert(pos, evidence)

    def test_13_timeout(self) -> None:
        pos = self._install(_row())
        self.api.fail = TimeoutError("synthetic")
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "timeout")
        self.assertEqual(evidence.protection_state, PROTECTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_14_request_exception(self) -> None:
        pos = self._install(_row())
        self.api.fail = RuntimeError("synthetic")
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "request_exception")
        self._assert_inert(pos, evidence)

    def test_15_null_body(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(None)
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "null_body")
        self._assert_inert(pos, evidence)

    def test_16_malformed_body(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append("not-a-trade")
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "malformed_body")
        self._assert_inert(pos, evidence)

    def test_17_nonfinite_price(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=_stop(price="NaN")))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.protection_state, PROTECTION_UNKNOWN)
        self.assertIn("nonfinite", evidence.uncertainty_reason)
        self._assert_inert(pos, evidence)

    def test_18_invalid_units(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(units="nope", stopLossOrder=_stop()))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "malformed_units")
        self.assertNotEqual(evidence.protection_state, PROTECTION_CONFIRMED)
        self._assert_inert(pos, evidence)

    def test_19_duplicate_order_ids(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=_stop(order_id="SAME"), takeProfitOrder=_tp(order_id="SAME")))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.protection_state, PROTECTION_CONFLICT)
        self.assertEqual(evidence.uncertainty_reason, "duplicate_order_id")
        self._assert_inert(pos, evidence)

    def test_20_contradictory_order_state(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=_stop(state="PENDING", fillingTransactionID="X1")))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.protection_state, PROTECTION_CONFLICT)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_22_cancelled_stop_is_not_protection_or_fill(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=_stop(state="CANCELLED")))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.stop_order_state, ORDER_CANCELLED_CONFIRMED)
        self.assertEqual(evidence.stop_protection, PROTECTION_UNKNOWN)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_23_rejected_stop(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=_stop(state="REJECTED")))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.stop_order_state, ORDER_REJECTED_CONFIRMED)
        self.assertNotEqual(evidence.stop_protection, PROTECTION_CONFIRMED)
        self._assert_inert(pos, evidence)

    def test_24_filled_stop_is_recorded_and_does_not_delete(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(
            _body(stopLossOrder=_stop(state="FILLED", fillingTransactionID="TX9", price="1.04990"))
        )
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.stop_order_state, ORDER_FILLED_CONFIRMED)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self.assertEqual(evidence.orders[0].transaction_id, "TX9")
        self.assertEqual(evidence.uncertainty_reason, "fill_reported_without_transaction_body")
        self.assertNotEqual(evidence.stop_protection, PROTECTION_CONFIRMED)
        self.assertIs(positions["EUR_USD"], pos)
        self._assert_inert(pos, evidence)

    def test_25_filled_take_profit_linked(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(
            _body(takeProfitOrder=_tp(state="FILLED", fillingTransactionID="TX8"))
        )
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.take_profit_order_state, ORDER_FILLED_CONFIRMED)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self.assertEqual(evidence.orders[0].transaction_id, "TX8")
        self.assertIs(positions["EUR_USD"], pos)
        self._assert_inert(pos, evidence)

    def test_26_fill_for_another_trade_is_conflict(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(
            _body(stopLossOrder=_stop(state="FILLED", fillingTransactionID="TX1", tradeID="OTHER"))
        )
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.protection_state, PROTECTION_CONFLICT)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_27_broker_flat_without_fill_attribution(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(state="CLOSED", currentUnits="0", stopLossOrder=None, takeProfitOrder=None))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self.assertEqual(evidence.uncertainty_reason, "broker_trade_closed_without_fill_attribution")
        self.assertIs(positions["EUR_USD"], pos)
        self._assert_inert(pos, evidence)

    def test_28_partial_fill_is_not_a_confirmed_exit(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(
            _body(stopLossOrder=_stop(state="PARTIALLY_FILLED", fillingTransactionID="TX3", units="400"))
        )
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.stop_order_state, ORDER_UNKNOWN)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_29_multiple_trade_ids_are_not_aggregated(self) -> None:
        pos = self._install(_row(broker_trade_ids="T1,T2"))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "multiple_trade_ids")
        self.assertEqual(evidence.protection_state, PROTECTION_UNKNOWN)
        self.assertEqual(self.api.calls, [])
        self._assert_inert(pos, evidence)

    def test_30_observation_import_is_not_promoted(self) -> None:
        import_position_from_broker(
            "EUR_USD",
            1000,
            1.1,
            1.05,
            1.2,
            execution_kind="live",
            broker_trade_ids="T1",
            broker_order_id="T1",
        )
        observed = broker_observations["EUR_USD"]
        evidence = record_management_protection_evidence(observed)
        self.assertEqual(evidence.uncertainty_reason, "management_not_permitted")
        self.assertNotIn("EUR_USD", positions)
        self.assertTrue(observed.observation_only)
        self.assertFalse(position_management_permitted(observed))
        self.assertEqual(self.api.calls, [])
        self.assertFalse(evidence.authorises_management)

    def test_31_paper_local_price_is_not_broker_protection(self) -> None:
        pos = self._install(_row(execution_kind="paper", broker_order=False, broker_order_id="", broker_trade_ids=""))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "local_reference_not_broker_evidence")
        self.assertEqual(evidence.protection_state, PROTECTION_UNKNOWN)
        self.assertEqual(self.api.calls, [])
        self._assert_inert(pos, evidence)

    def test_32_simulated_window_and_synthetic_do_not_read(self) -> None:
        for kind in ("simulated", "window_paper", "synthetic"):
            with self.subTest(kind=kind):
                positions.clear()
                self.api.calls.clear()
                pos = self._install(
                    _row(execution_kind=kind, broker_order=False, broker_order_id="", broker_trade_ids="")
                )
                evidence = record_management_protection_evidence(pos)
                self.assertEqual(evidence.uncertainty_reason, "local_reference_not_broker_evidence")
                self.assertEqual(self.api.calls, [])
                self._assert_inert(pos, evidence)

    def test_33_older_success_does_not_overwrite_newer_success(self) -> None:
        pos = self._install(_row())
        self.api.hold = threading.Event()
        self.api.release = threading.Event()
        self.api.bodies.append(_body(stopLossOrder=_stop(order_id="OLD")))
        self.api.bodies.append(_body(stopLossOrder=_stop(order_id="NEW")))
        box: dict = {}

        def first() -> None:
            box["old"] = record_management_protection_evidence(pos)

        worker = threading.Thread(target=first)
        worker.start()
        self.assertTrue(self.api.hold.wait(5))
        newer = record_management_protection_evidence(pos)
        self.api.release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(newer.orders[0].order_id, "NEW")
        self.assertEqual(box["old"].uncertainty_reason, "stale_response")
        stored = published_protection_evidence("EUR_USD")
        assert stored is not None
        self.assertEqual(stored.orders[0].order_id, "NEW")
        self._assert_inert(pos, newer)

    def test_34_identity_change_discards_inflight_evidence(self) -> None:
        pos = self._install(_row())
        self.api.hold = threading.Event()
        self.api.release = threading.Event()
        self.api.bodies.append(_body(stopLossOrder=_stop()))

        def read() -> None:
            self.discarded = record_management_protection_evidence(pos)

        worker = threading.Thread(target=read)
        worker.start()
        self.assertTrue(self.api.hold.wait(5))
        pos.broker_trade_ids = "T9"
        self.api.release.set()
        worker.join(5)
        self.assertEqual(self.discarded.uncertainty_reason, "identity_changed")
        self.assertIsNone(published_protection_evidence("EUR_USD"))
        self.assertIs(positions["EUR_USD"], pos)
        self._assert_inert(pos, self.discarded)

    def test_35_removal_and_reconcile_overlap_do_not_publish_or_promote(self) -> None:
        pos = self._install(_row())
        self.api.hold = threading.Event()
        self.api.release = threading.Event()
        self.api.bodies.append(_body(stopLossOrder=_stop()))

        def read() -> None:
            self.discarded = record_management_protection_evidence(pos)

        worker = threading.Thread(target=read)
        worker.start()
        self.assertTrue(self.api.hold.wait(5))
        positions.pop("EUR_USD")
        import_position_from_broker("EUR_USD", 1000, 1.1, 1.05, 1.2, broker_trade_ids="T1")
        self.api.release.set()
        worker.join(5)
        self.assertEqual(self.discarded.uncertainty_reason, "identity_changed")
        self.assertIsNone(published_protection_evidence("EUR_USD"))
        self.assertNotIn("EUR_USD", positions)
        self.assertTrue(broker_observations["EUR_USD"].observation_only)
        self.assertFalse(position_management_permitted(broker_observations["EUR_USD"]))

    def test_newer_failure_keeps_published_success(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=_stop(order_id="KEEP")))
        first = record_management_protection_evidence(pos)
        self.api.fail = TimeoutError("later")
        second = record_management_protection_evidence(pos)
        self.assertEqual(first.stop_protection, PROTECTION_CONFIRMED)
        self.assertEqual(second.uncertainty_reason, "timeout")
        stored = published_protection_evidence("EUR_USD")
        assert stored is not None
        self.assertEqual(stored.orders[0].order_id, "KEEP")
        self._assert_inert(pos, second)

    def test_unknown_kind_and_manual_observation_are_refused(self) -> None:
        unknown = self._install(_row(execution_kind="mystery"))
        evidence = record_management_protection_evidence(unknown)
        self.assertEqual(evidence.uncertainty_reason, "management_not_permitted")
        self.assertEqual(self.api.calls, [])
        manual = _row(observation_only=True)
        positions["EUR_USD"] = manual
        refused = record_management_protection_evidence(manual)
        self.assertEqual(refused.uncertainty_reason, "management_not_permitted")
        self.assertTrue(manual.observation_only)
        self.assertEqual(self.api.calls, [])

    def test_unlinked_fill_is_not_attributed(self) -> None:
        pos = self._install(_row())
        self.api.bodies.append(_body(stopLossOrder=_stop(state="FILLED")))
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.stop_order_state, ORDER_FILLED_CONFIRMED)
        self.assertEqual(evidence.exit_attribution, EXIT_ATTRIBUTION_UNKNOWN)
        self._assert_inert(pos, evidence)

    def test_local_stop_does_not_confirm_protection(self) -> None:
        pos = self._install(_row(stop_loss=1.05, take_profit=1.2))
        self.api.bodies.append(_body())
        evidence = record_management_protection_evidence(pos)
        self.assertEqual(evidence.uncertainty_reason, "protection_sections_absent")
        self.assertNotEqual(evidence.protection_state, PROTECTION_CONFIRMED)
        self.assertNotEqual(evidence.stop_protection, UNPROTECTED_CONFIRMED)
        self._assert_inert(pos, evidence)

    def test_operational_source_wiring_and_unchanged_files(self) -> None:
        bot_loop = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
        self.assertIn("record_management_protection_evidence(pos)", bot_loop)
        self.assertIn("sl_tp_hit = broker_sl_tp_hit(pos)", bot_loop)
        self.assertLess(
            bot_loop.index("record_management_protection_evidence(pos)"),
            bot_loop.index("sl_tp_hit = broker_sl_tp_hit(pos)"),
        )
        self.assertIn("production_path_has_no_simulation_context", bot_loop)
        module = (ROOT / "forex_bot" / "broker_protection.py").read_text(encoding="utf-8")
        for banned in ("OrderCreate", "PositionClose", "TradeClose", "OrderCancel", "OrderReplace", "oanda_exec"):
            self.assertNotIn(banned, module)
        live = (ROOT / "forex_bot" / "live_manage.py").read_text(encoding="utf-8")
        self.assertIn("return False", live[live.index("def broker_sl_tp_hit") : live.index("def format_manage_price_line")])
        for rel, digest in UNCHANGED.items():
            payload = (ROOT / rel).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), digest, rel)
        for gate in (
            ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py",
            ROOT / "data/research/adaptive_ensemble/r59/live_session_gate.py",
            ROOT / "data/research/adaptive_ensemble/r60/live_session_gate.py",
            ROOT / "data/research/adaptive_ensemble/r61/live_session_gate.py",
        ):
            self.assertIn("REAL_SESSION_SOURCE_ENABLEMENT = False", gate.read_text(encoding="utf-8"))
        marker = ROOT / "data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.consumed"
        self.assertEqual(marker.stat().st_size, 10)
        self.assertEqual(
            hashlib.sha256(marker.read_bytes()).hexdigest(),
            "e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c",
        )

    def test_profit_protection_and_snapshot_regression(self) -> None:
        from datetime import datetime, timezone

        from forex_bot.profit_protection import (
            activation_trigger_pips,
            apply_profit_protection,
            atr_to_pips,
            original_tp_distance_pips,
            pip_size,
            profit_giveback_atr_multiplier,
            profit_giveback_pips,
            profit_protection_atr_period,
            profit_protection_trigger_percent,
            resolve_giveback_pips,
        )
        from forex_bot.reconciliation import BrokerSnapshotError, _interpret_open_positions
        from forex_bot.session_rules import flatten_for_weekend_at

        self.assertEqual(profit_protection_trigger_percent(), 0.67)
        self.assertEqual(profit_protection_atr_period(), 14)
        self.assertEqual(profit_giveback_atr_multiplier(), 0.5)
        self.assertEqual(profit_giveback_pips(), 4.0)
        self.assertEqual(pip_size("EUR_USD"), 0.0001)
        self.assertEqual(pip_size("USD_JPY"), 0.01)
        buy = _row(execution_kind="paper", broker_order=False, symbol="EUR_USD", direction="BUY", entry_price=1.1, take_profit=1.1030, stop_loss=1.098)
        sell = _row(execution_kind="paper", broker_order=False, symbol="EUR_USD", direction="SELL", entry_price=1.1, take_profit=1.0970, stop_loss=1.102)
        self.assertAlmostEqual(original_tp_distance_pips(buy), 30.0)
        self.assertAlmostEqual(activation_trigger_pips(buy), 20.1)
        self.assertAlmostEqual(activation_trigger_pips(sell), 20.1)
        giveback, source = resolve_giveback_pips(buy, atr_price=0.0010)
        self.assertEqual(source, "atr")
        self.assertAlmostEqual(giveback, 5.0)
        self.assertAlmostEqual(atr_to_pips("EUR_USD", 0.0010), 10.0)
        fallback, fallback_source = resolve_giveback_pips(buy, atr_price=None)
        self.assertEqual(fallback_source, "fallback")
        self.assertAlmostEqual(fallback, 4.0)
        first = apply_profit_protection(buy, 1.1025, atr_price=0.0004)
        held = buy.profit_protection_exit_pips
        second = apply_profit_protection(buy, 1.1025, atr_price=0.0040)
        self.assertGreaterEqual(second.exit_threshold_pips, held)
        self.assertGreaterEqual(buy.max_profit_pips, first.max_profit_pips)
        with self.assertRaises(BrokerSnapshotError) as caught:
            _interpret_open_positions({})
        self.assertEqual(caught.exception.classification, "INCOMPLETE")
        classification, detail, _ids = _interpret_open_positions({"positions": []})
        self.assertEqual(classification, "COMPLETE_EMPTY")
        self.assertEqual(detail, {})
        friday = datetime(2026, 10, 23, 20, 50, tzinfo=timezone.utc)
        sunday = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(flatten_for_weekend_at(friday))
        self.assertFalse(flatten_for_weekend_at(sunday))
        observed = _row(execution_kind="reconcile_import", observation_only=True)
        self.assertFalse(position_management_permitted(observed))


if __name__ == "__main__":
    unittest.main()
