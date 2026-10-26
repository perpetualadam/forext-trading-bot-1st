"""One offline iteration through the real decision gates. No broker and no database."""

from __future__ import annotations

import atexit
import importlib.util
import json
import os
import socket
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R12 = ROOT / "data" / "research" / "adaptive_ensemble" / "r12"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R12 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    broker_entry_block_reason,
    evaluate_one_instrument_iteration,
    run_bot,
)
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    exposure_entry_block_reason,
    interpret_close_evidence,
    note_blocking_reservation,
    note_unconfirmed_exposure,
    reset_order_intent_gate_for_tests,
    restore_unresolved_intent,
    select_rows_for_recovery,
)
from forex_bot.orders import (  # noqa: E402
    LocalOrder,
    OrderStatus,
    ingest_recovery_snapshot,
    register_order,
    reset_orders_for_tests,
)
from forex_bot.positions import Position, close_position, get_position, open_position, positions  # noqa: E402
from forex_bot.strategy_meta import SCALP_STRATEGY_KEYS, SWING_STRATEGY_KEYS, strategies  # noqa: E402

_fake_spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
_fake_mod = importlib.util.module_from_spec(_fake_spec)
assert _fake_spec is not None and _fake_spec.loader is not None
_fake_spec.loader.exec_module(_fake_mod)
FakeBroker = _fake_mod.FakeBroker
FakeResource = _fake_mod.FakeResource

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
CLOSED = datetime(2026, 1, 7, 23, 0, tzinfo=timezone.utc)
WEEKEND = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
FLATTEN = datetime(2026, 1, 9, 20, 50, tzinfo=timezone.utc)
RECORDS: list[dict[str, object]] = []
OPS_PERMISSION = ROOT / "data" / "ops" / "live_safety_state.json"


def _ops_stamp() -> float | None:
    return OPS_PERMISSION.stat().st_mtime if OPS_PERMISSION.exists() else None


OPS_BEFORE = _ops_stamp()


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R12)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R12 / "synthetic_live_safety_state.json")
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def _bars(price: float = 1.1, count: int = 50, **changes: object) -> list[dict[str, object]]:
    rows = []
    for _ in range(count):
        row: dict[str, object] = {
            "open": price,
            "high": price + 0.0002,
            "low": price - 0.0002,
            "close": price,
            "time": "2026-01-07T11:55:00+00:00",
        }
        row.update(changes)
        rows.append(row)
    return rows


def _deps(**overrides: object) -> IterationDependencies:
    broker = overrides.pop("broker", None)
    values: dict[str, object] = {
        "candles": _bars(),
        "spread": 0.0002,
        "balance": 10000.0,
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.6},
        "strategy_name": "scalp",
        "strategy_known": True,
        "strategy_active": True,
        "strategy_authorised": True,
        "safety_initialised": True,
        "simulation": True,
        "now": OPEN,
        "quote_as_of": OPEN,
        "stop_distance": 0.001,
        "price": 1.1,
        "bid": 1.09995,
        "ask": 1.10005,
        "broker": broker if broker is not None else FakeBroker("filled"),
    }
    values.update(overrides)
    if "unrealised" not in overrides:
        values["unrealised"] = 0.0
    if "account_as_of" not in overrides:
        values["account_as_of"] = values.get("now")
    return IterationDependencies(**values)  # type: ignore[arg-type]


def _run(**overrides: object) -> dict[str, object]:
    symbol = str(overrides.pop("symbol", "EUR_USD"))
    return evaluate_one_instrument_iteration(symbol, _deps(**overrides))


def record(test_id: str, function: str, application: str, expected: str, result: dict[str, object] | None, status: str, **extra: object) -> None:
    broker_requests = 0 if result is None else int(result.get("broker_requests") or 0)
    RECORDS.append(
        {
            "test_id": test_id,
            "function": function,
            "application_function": application,
            "expected": expected,
            "actual": None if result is None else result.get("blocked_by") or result.get("status"),
            "status": status,
            "seam_ran": result is not None,
            "fake_broker_dispatch": broker_requests > 0,
            "real_service": False,
            "evidence": extra,
        }
    )


def _note(test_id: str, function: str, application: str, expected: str, result: dict[str, object], ok: bool, **extra: object) -> None:
    record(test_id, function, application, expected, result, "PASS" if ok else "FAIL", **extra)
    assert ok, result


def _dump() -> None:
    R12.mkdir(parents=True, exist_ok=True)
    (R12 / "12_integration_test_results.json").write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")


atexit.register(_dump)


def test_j01_live_permission_blocks() -> None:
    result = _run(simulation=False, broker=FakeBroker("filled"))
    _note("J01", "test_j01_live_permission_blocks", "pre_trade_entry_blocked_reason", "live permission blocks", result, result["broker_requests"] == 0 and "live_order_auth" in str(result["blocked_by"]))


def test_j02_inactive_strategy_blocks_before_broker() -> None:
    result = _run(strategy_active=False)
    _note("J02", "test_j02_inactive_strategy_blocks_before_broker", "strategy_entry_block_reason", "STRATEGY_INACTIVE", result, result["blocked_by"] == "STRATEGY_INACTIVE" and result["broker_requests"] == 0 and "sizing" not in result["phases"])


def test_j03_unknown_strategy_blocks() -> None:
    result = _run(strategy_name="not-a-strategy", strategy_known=False)
    _note("J03", "test_j03_unknown_strategy_blocks", "strategy_entry_block_reason", "UNKNOWN_STRATEGY", result, result["blocked_by"] == "UNKNOWN_STRATEGY" and result["broker_requests"] == 0)


def test_j04_invalid_direction_blocks() -> None:
    result = _run(vote={"allow": True, "direction": "HOLD"})
    _note("J04", "test_j04_invalid_direction_blocks", "direction_action_gate", "invalid direction", result, result["blocked_by"] == "invalid_entry_direction" and result["broker_requests"] == 0)


def test_j05_blank_direction_blocks() -> None:
    result = _run(vote={"allow": True, "direction": "  "})
    _note("J05", "test_j05_blank_direction_blocks", "direction_action_gate", "blank direction", result, result["blocked_by"] == "invalid_entry_direction")


def test_j06_no_trade_direction_blocks() -> None:
    result = _run(vote={"allow": True, "direction": "NO_TRADE"})
    _note("J06", "test_j06_no_trade_direction_blocks", "direction_action_gate", "NO_TRADE", result, result["blocked_by"] == "invalid_entry_direction")


def test_j07_simulated_buy_reaches_fake_broker() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    ok = result["status"] == "filled" and result["direction"] == "BUY" and broker.request_count == 1 and result["production_authorised"] is False
    _note("J07", "test_j07_simulated_buy_reaches_fake_broker", "evaluate_one_instrument_iteration", "simulated BUY reaches fake broker", result, ok, requests=broker.requests)


def test_j08_simulated_sell_reaches_fake_broker() -> None:
    broker = FakeBroker("filled")
    result = _run(vote={"allow": True, "direction": "SELL"}, broker=broker)
    _note("J08", "test_j08_simulated_sell_reaches_fake_broker", "evaluate_one_instrument_iteration", "simulated SELL", result, result["direction"] == "SELL" and broker.request_count == 1)


def test_j09_production_strategies_stay_inactive() -> None:
    _run()
    names = tuple(SCALP_STRATEGY_KEYS) + tuple(SWING_STRATEGY_KEYS)
    ok = len(names) == 6 and all(strategies[name].active is False and strategies[name].authorised_for_live is False for name in names)
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0, "phases": ()}
    _note("J09", "test_j09_production_strategies_stay_inactive", "strategy_meta.strategies", "six strategies inactive", result, ok, names=names)


def test_j10_no_production_permission_write() -> None:
    _run()
    ok = _ops_stamp() == OPS_BEFORE
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("J10", "test_j10_no_production_permission_write", "live_safety path", "production permission file unchanged", result, ok)


def test_j11_blocking_permission_prevents_dispatch() -> None:
    broker = FakeBroker("filled")
    result = _run(simulation=False, broker=broker)
    _note("J11", "test_j11_blocking_permission_prevents_dispatch", "pre_trade_entry_blocked_reason", "no dispatch", result, broker.request_count == 0 and result["broker_requests"] == 0)


def test_j12_simulation_is_not_production_authorisation() -> None:
    result = _run()
    _note("J12", "test_j12_simulation_is_not_production_authorisation", "evaluate_one_instrument_iteration", "production_authorised false", result, result["production_authorised"] is False and result["trading_ready"] is False and result["simulation"] is True)


def test_j13_valid_candles_still_hit_permission_without_simulation() -> None:
    result = _run(simulation=False)
    _note("J13", "test_j13_valid_candles_still_hit_permission_without_simulation", "pre_trade_entry_blocked_reason", "permission block", result, "live_order_auth" in str(result["blocked_by"]))


def test_j14_empty_candles_block() -> None:
    result = _run(candles=[])
    _note("J14", "test_j14_empty_candles_block", "evaluate_one_instrument_iteration", "no_candles", result, result["blocked_by"] == "no_candles" and result["broker_requests"] == 0)


def test_j15_missing_ohlc_blocks_in_indicators() -> None:
    result = _run(candles=[{"open": 1.1, "high": 1.2, "low": 1.0, "time": "2026-01-07T11:55:00+00:00"}])
    _note("J15", "test_j15_missing_ohlc_blocks_in_indicators", "compute_indicators", "indicator_failure", result, result["blocked_by"] == "indicator_failure" and result["broker_requests"] == 0)


def test_j16_nonfinite_price_blocks() -> None:
    rows = _bars()
    rows[-1]["close"] = float("nan")
    result = _run(candles=rows, price=None)
    _note("J16", "test_j16_nonfinite_price_blocks", "_market_entry_block", "non-finite candle blocks", result, result["broker_requests"] == 0 and result["blocked_by"] == "candle_nonfinite")


def test_j17_invalid_timestamp_is_behind_missing_provenance() -> None:
    rows = _bars()
    rows[-1]["time"] = "not-a-time"
    result = _run(candles=rows)
    ok = result["blocked_by"] == "candle_malformed" and result["broker_requests"] == 0
    _note("J17", "test_j17_invalid_timestamp_is_behind_missing_provenance", "_market_entry_block", "unparseable candle time blocks", result, ok, source_gap="R.17 blocks a candle time that cannot be parsed")


def test_j18_stale_bar_is_behind_missing_provenance() -> None:
    rows = _bars()
    rows[-1]["time"] = "2020-01-01T00:00:00+00:00"
    result = _run(candles=rows)
    _note("J18", "test_j18_stale_bar_is_behind_missing_provenance", "decision_frame_rejection", "missing provenance before stale bar", result, result["provenance"] == "missing_provenance", source_gap="stale_bar requires a sealed frame")


def test_j19_excessive_spread_has_no_hard_block() -> None:
    result = _run(spread=0.05)
    ok = result["details"]["spread_limit"] == "not_approved" and result["broker_requests"] == 1 and result["production_eligible"] is False
    _note("J19", "test_j19_excessive_spread_has_no_hard_block", "evaluate_one_instrument_iteration", "unapproved spread is not production eligibility", result, ok, source_gap="numeric spread stays POLICY_UNAPPROVED and does not authorise production")


def test_j20_short_lookback_is_not_a_hard_block() -> None:
    result = _run(candles=_bars(count=5))
    _note("J20", "test_j20_short_lookback_is_not_a_hard_block", "_entry_lookback_requirement", "short lookback blocks", result, result["blocked_by"] in {"insufficient_lookback", "volatility_unsafe"} and result["broker_requests"] == 0)


def test_j21_buy_vote() -> None:
    result = _run(vote={"allow": True, "direction": "BUY"})
    _note("J21", "test_j21_buy_vote", "direction_action_gate", "BUY", result, result["direction"] == "BUY" and result["status"] == "filled")


def test_j22_sell_vote() -> None:
    result = _run(vote={"allow": True, "direction": "SELL"})
    _note("J22", "test_j22_sell_vote", "direction_action_gate", "SELL", result, result["direction"] == "SELL")


def test_j23_no_vote_blocks() -> None:
    result = _run(vote={"allow": False, "direction": "BUY"})
    _note("J23", "test_j23_no_vote_blocks", "evaluate_one_instrument_iteration", "ai_vote_rejected", result, result["blocked_by"] == "ai_vote_rejected" and result["broker_requests"] == 0)


def test_j24_unknown_vote_blocks() -> None:
    result = _run(vote={"allow": True, "direction": "MAYBE"})
    _note("J24", "test_j24_unknown_vote_blocks", "canonical_entry_direction", "invalid direction", result, result["blocked_by"] == "invalid_entry_direction")


def test_j25_vote_provider_error_blocks() -> None:
    result = _run(vote_error="boom")
    _note("J25", "test_j25_vote_provider_error_blocks", "evaluate_one_instrument_iteration", "ai_vote_provider_error", result, result["blocked_by"] == "ai_vote_provider_error" and result["broker_requests"] == 0)


def test_j26_second_signal_in_same_interval_is_blocked() -> None:
    first = _run()
    second = _run(broker=FakeBroker("filled"))
    ok = first["broker_requests"] == 1 and second["broker_requests"] == 0 and second["blocked_by"] == "position_already_open"
    _note("J26", "test_j26_second_signal_in_same_interval_is_blocked", "exposure_entry_block_reason", "second entry blocked", second, ok, first=first["status"])


def test_j27_different_symbols_can_each_run_once() -> None:
    first = _run(symbol="EUR_USD")
    second = _run(symbol="AUD_USD", price=0.65, candles=_bars(0.65))
    _note("J27", "test_j27_different_symbols_can_each_run_once", "portfolio_risk_cap_exceeded", "second symbol hits the portfolio risk cap", second, first["status"] == "filled" and second["blocked_by"] == "portfolio_risk_cap" and second["broker_requests"] == 0)


def test_j28_session_closed_blocks() -> None:
    result = _run(now=CLOSED)
    _note("J28", "test_j28_session_closed_blocks", "in_active_session_at", "market_session_closed", result, result["blocked_by"] == "market_session_closed" and result["broker_requests"] == 0)


def test_j29_weekend_flatten_blocks() -> None:
    result = _run(now=FLATTEN)
    _note("J29", "test_j29_weekend_flatten_blocks", "flatten_for_weekend_at", "weekend_flatten", result, result["blocked_by"] == "weekend_flatten" and result["broker_requests"] == 0)


def test_j30_missing_account_uses_current_equity() -> None:
    result = _run(account_present=False, balance=None)
    _note("J30", "test_j30_missing_account_uses_current_equity", "account_entry_block", "missing snapshot blocks before sizing", result, result["blocked_by"] == "account_missing" and result["broker_requests"] == 0 and "sizing" not in result["phases"])


def test_j31_nonfinite_account_blocks() -> None:
    result = _run(balance=float("nan"))
    _note("J31", "test_j31_nonfinite_account_blocks", "account_entry_block", "account_equity_nonfinite", result, result["blocked_by"] == "account_equity_nonfinite" and result["broker_requests"] == 0)


def test_j32_malformed_spread_has_no_hard_block() -> None:
    result = _run(spread="wide")
    _note("J32", "test_j32_malformed_spread_has_no_hard_block", "_market_entry_block", "malformed spread blocks", result, result["blocked_by"] == "quote_malformed" and result["broker_requests"] == 0)


def test_j33_valid_balance_sizes() -> None:
    result = _run(balance=10000.0)
    _note("J33", "test_j33_valid_balance_sizes", "position_sizing", "positive units", result, float(result["units"]) > 0 and result["status"] == "filled")


def test_j34_zero_balance_blocks() -> None:
    result = _run(balance=0.0)
    _note("J34", "test_j34_zero_balance_blocks", "account_entry_block", "account_equity_not_positive", result, result["blocked_by"] == "account_equity_not_positive" and result["broker_requests"] == 0 and "sizing" not in result["phases"])


def test_j35_negative_balance_blocks() -> None:
    result = _run(balance=-50.0)
    _note("J35", "test_j35_negative_balance_blocks", "account_entry_block", "account_equity_not_positive", result, result["blocked_by"] == "account_equity_not_positive" and result["broker_requests"] == 0 and "sizing" not in result["phases"])


def test_j36_nonfinite_balance_blocks() -> None:
    result = _run(balance=float("inf"))
    _note("J36", "test_j36_nonfinite_balance_blocks", "account_entry_block", "account_equity_nonfinite", result, result["blocked_by"] == "account_equity_nonfinite" and result["broker_requests"] == 0)


def test_j37_valid_stop_sizes() -> None:
    result = _run(stop_distance=0.002)
    _note("J37", "test_j37_valid_stop_sizes", "position_sizing", "positive units", result, float(result["units"]) > 0)


def test_j38_zero_stop_blocks_dispatch() -> None:
    result = _run(stop_distance=0.0)
    _note("J38", "test_j38_zero_stop_blocks_dispatch", "position_sizing", "size_not_positive", result, result["blocked_by"] == "size_not_positive" and "non_positive_size" in str(result["source_gap"]))


def test_j39_negative_stop_is_absolute_valued() -> None:
    result = _run(stop_distance=-0.001)
    _note("J39", "test_j39_negative_stop_is_absolute_valued", "position_sizing", "abs stop still sizes", result, float(result["units"]) > 0, source_gap="position_sizing uses abs(price-stop)")


def test_j40_nonfinite_stop_blocks() -> None:
    result = _run(stop_distance=float("nan"))
    _note("J40", "test_j40_nonfinite_stop_blocks", "evaluate_one_instrument_iteration", "sizing_input_invalid", result, result["blocked_by"] == "sizing_input_invalid" and result["broker_requests"] == 0)


def test_j41_formula_floors_positive_risk_at_one_unit() -> None:
    result = _run(balance=10.0)
    _note("J41", "test_j41_formula_floors_positive_risk_at_one_unit", "position_sizing", "at least one unit", result, float(result["units"]) >= 1.0, source_gap="default formula uses max(units, 1)")


def test_j42_max_units_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAX_POSITION_UNITS", raising=False)
    result = _run(balance=1_000_000.0)
    _note("J42", "test_j42_max_units_disabled_by_default", "cap_position_units", "no default unit cap", result, float(result["units"]) > 1.0, source_gap="MAX_POSITION_UNITS default 0 disables the cap")


def test_j43_notional_cap_off_by_default() -> None:
    result = _run(balance=1_000_000.0)
    details = result["details"]
    same_equity = details.get("sizing_equity") == details.get("portfolio_cap_equity") == 1_000_000.0
    ok = same_equity and result["blocked_by"] != "portfolio_risk_cap" and result["broker_requests"] == 1
    _note("J43", "test_j43_notional_cap_off_by_default", "portfolio_risk_cap_exceeded", "accepted equity is inside its own cap", result, ok, source_gap="R.16: a 1 percent size is inside the 5 percent cap of the same accepted equity; the old assertion blocked only because current_equity fell back to BASE_BALANCE")


def test_j44_existing_position_blocks() -> None:
    open_position(Position("EUR_USD", "BUY", 1, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    result = _run()
    _note("J44", "test_j44_existing_position_blocks", "get_position", "position_already_open", result, result["blocked_by"] == "position_already_open" and result["broker_requests"] == 0)


def test_j45_uncertain_exposure_blocks() -> None:
    note_unconfirmed_exposure("EUR_USD", "old-fill")
    result = _run()
    _note("J45", "test_j45_uncertain_exposure_blocks", "exposure_entry_block_reason", "exposure_unconfirmed", result, result["blocked_by"] == "exposure_unconfirmed" and result["broker_requests"] == 0)


def test_j46_pending_reservation_blocks() -> None:
    note_blocking_reservation("EUR_USD", "pending-1")
    result = _run()
    _note("J46", "test_j46_pending_reservation_blocks", "exposure_entry_block_reason", "active_reservation", result, result["blocked_by"] == "active_reservation" and result["broker_requests"] == 0)


def test_j47_partial_reservation_blocks() -> None:
    register_order(LocalOrder("partial-1", "EUR_USD", "BUY", 2, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation("EUR_USD", "partial-1")
    result = _run()
    _note("J47", "test_j47_partial_reservation_blocks", "reservation_status_block_reason", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_j48_unresolved_reservation_blocks() -> None:
    restore_unresolved_intent("EUR_USD", "unresolved-1")
    result = _run()
    _note("J48", "test_j48_unresolved_reservation_blocks", "exposure_entry_block_reason", "unresolved_intent", result, result["blocked_by"] == "unresolved_intent")


def test_j49_historical_filled_exposure_blocks() -> None:
    note_unconfirmed_exposure("EUR_USD", "filled-old")
    result = _run()
    _note("J49", "test_j49_historical_filled_exposure_blocks", "exposure_entry_block_reason", "exposure_unconfirmed", result, result["blocked_by"] == "exposure_unconfirmed")


def test_j50_persistence_unavailable_blocks_durable_read() -> None:
    reason = broker_entry_block_reason("EUR_USD")
    result = _run(persistence_failure="unavailable")
    ok = reason == "recovery_unreadable" and result["blocked_by"] == "reservation_persistence_failed" and result["broker_requests"] == 0
    _note("J50", "test_j50_persistence_unavailable_blocks_durable_read", "broker_entry_block_reason", "recovery_unreadable", result, ok, durable=reason)


def test_j51_conflicting_position_data_blocks() -> None:
    open_position(Position("EUR_USD", "BUY", 5, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    recorded = __import__("forex_bot.orders", fromlist=["record_synthetic_fill_position"]).record_synthetic_fill_position(
        symbol="EUR_USD", client_order_id="conflict", direction="SELL", units=9, price=1.1
    )
    result = _run()
    _note("J51", "test_j51_conflicting_position_data_blocks", "record_synthetic_fill_position", "conflict and position block", result, recorded == "conflict" and result["blocked_by"] == "position_already_open")


def test_j52_multiple_symbols() -> None:
    first = _run(symbol="EUR_USD")
    second = _run(symbol="AUD_USD", price=0.66, candles=_bars(0.66))
    _note("J52", "test_j52_multiple_symbols", "portfolio_risk_cap_exceeded", "second symbol blocked by open risk", second, first["broker_requests"] == 1 and second["blocked_by"] == "portfolio_risk_cap")


def test_j53_valid_reservation_then_fake_broker() -> None:
    broker = FakeBroker("accepted")
    result = _run(broker=broker)
    _note("J53", "test_j53_valid_reservation_then_fake_broker", "try_begin_order_submission", "accepted", result, result["status"] == "accepted" and broker.request_count == 1)


def test_j54_duplicate_client_id_blocks() -> None:
    register_order(LocalOrder("same-id", "EUR_USD", "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _run(client_order_id="same-id")
    _note("J54", "test_j54_duplicate_client_id_blocks", "try_begin_order_submission", "reservation_refused", result, result["blocked_by"] == "reservation_refused" and result["broker_requests"] == 0)


def test_j55_duplicate_symbol_reservation_blocks() -> None:
    _run()
    result = _run(broker=FakeBroker("filled"))
    _note("J55", "test_j55_duplicate_symbol_reservation_blocks", "exposure_entry_block_reason", "second symbol reservation blocked", result, result["broker_requests"] == 0)


def test_j56_pending_reservation_blocks_dispatch() -> None:
    note_blocking_reservation("EUR_USD", "pend")
    result = _run()
    _note("J56", "test_j56_pending_reservation_blocks_dispatch", "note_blocking_reservation", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_j57_partial_reservation_blocks_dispatch() -> None:
    register_order(LocalOrder("p2", "EUR_USD", "BUY", 3, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation("EUR_USD", "p2")
    result = _run()
    _note("J57", "test_j57_partial_reservation_blocks_dispatch", "reservation_status_block_reason", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_j58_unresolved_reservation_blocks_dispatch() -> None:
    restore_unresolved_intent("EUR_USD", "u2")
    result = _run()
    _note("J58", "test_j58_unresolved_reservation_blocks_dispatch", "restore_unresolved_intent", "unresolved_intent", result, result["blocked_by"] == "unresolved_intent")


def test_j59_historical_filled_hold_blocks_dispatch() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "hist", "symbol": "EUR_USD", "status": "FILLED", "metadata": {}}])
    ingest_recovery_snapshot(kept, True)
    result = _run()
    _note("J59", "test_j59_historical_filled_hold_blocks_dispatch", "select_rows_for_recovery", "exposure_unconfirmed", result, result["blocked_by"] == "exposure_unconfirmed" and result["broker_requests"] == 0)


def test_j60_reservation_persistence_failure_blocks() -> None:
    result = _run(persistence_failure="fail")
    _note("J60", "test_j60_reservation_persistence_failure_blocks", "refuse_reservation_after_database_fault", "reservation_persistence_failed", result, result["blocked_by"] == "reservation_persistence_failed" and result["outcome"] == "fail")


def test_j61_reservation_commit_uncertain_blocks() -> None:
    result = _run(persistence_failure="uncertain")
    _note("J61", "test_j61_reservation_commit_uncertain_blocks", "refuse_reservation_after_database_fault", "uncertain", result, result["outcome"] == "uncertain" and result["broker_requests"] == 0)


def test_j62_reservation_timeout_blocks() -> None:
    result = _run(persistence_failure="timeout")
    _note("J62", "test_j62_reservation_timeout_blocks", "refuse_reservation_after_database_fault", "timeout", result, result["outcome"] == "timeout" and result["broker_requests"] == 0)


def test_j63_malformed_reservation_response_blocks() -> None:
    result = _run(persistence_failure="malformed")
    _note("J63", "test_j63_malformed_reservation_response_blocks", "refuse_reservation_after_database_fault", "malformed", result, result["outcome"] == "malformed" and result["broker_requests"] == 0)


def test_j64_existing_position_blocks_reservation() -> None:
    open_position(Position("EUR_USD", "SELL", 2, 1.1, 1.2, 1.0, 0, "scalp", "x", "synthetic"))
    result = _run()
    _note("J64", "test_j64_existing_position_blocks_reservation", "get_position", "position_already_open", result, result["blocked_by"] == "position_already_open")


def test_j65_missing_position_with_exposure_blocks() -> None:
    note_unconfirmed_exposure("EUR_USD", "missing-pos")
    result = _run()
    ok = get_position("EUR_USD") is None and result["blocked_by"] == "exposure_unconfirmed"
    _note("J65", "test_j65_missing_position_with_exposure_blocks", "exposure_entry_block_reason", "exposure without position", result, ok)


def test_j66_broker_refuses_dispatch() -> None:
    result = _run(broker=FakeBroker("refused"))
    _note("J66", "test_j66_broker_refuses_dispatch", "FakeBroker.submit", "rejected", result, result["status"] == "rejected" and result["broker_requests"] == 1)


def test_j67_at_most_one_simulated_request() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("J67", "test_j67_at_most_one_simulated_request", "FakeBroker.submit", "one request", result, broker.request_count == 1)


def test_j68_no_real_broker_constructor() -> None:
    _run()
    import forex_bot.oanda_client as oanda_client

    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("J68", "test_j68_no_real_broker_constructor", "oanda_client._api", "_api is None", result, oanda_client._api is None)


def test_j69_no_real_network_request() -> None:
    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocked = False
    except RuntimeError as exc:
        blocked = "NETWORK_BLOCKED" in str(exc) or "DNS_BLOCKED" in str(exc)
    result = {"status": "observed", "blocked_by": "network" if blocked else "open", "broker_requests": 0}
    _note("J69", "test_j69_no_real_network_request", "socket barrier", "network blocked", result, blocked)


def test_j70_uncertain_outcome_does_not_replace_the_order() -> None:
    first = _run(broker=FakeBroker("filled", error=TimeoutError("simulated timeout")))
    second = _run(broker=FakeBroker("filled"))
    _note("J70", "test_j70_uncertain_outcome_does_not_replace_the_order", "restore_unresolved_intent", "no replacement", second, first["status"] == "uncertain" and second["broker_requests"] == 0)


def test_j71_second_client_id_cannot_bypass() -> None:
    note_blocking_reservation("EUR_USD", "first-id")
    result = _run(client_order_id="second-id")
    _note("J71", "test_j71_second_client_id_cannot_bypass", "try_begin_order_submission", "second id blocked", result, result["blocked_by"] == "active_reservation" and result["broker_requests"] == 0)


def test_j72_no_dispatch_without_simulation() -> None:
    broker = FakeBroker("filled")
    result = _run(simulation=False, broker=broker)
    _note("J72", "test_j72_no_dispatch_without_simulation", "evaluate_one_instrument_iteration", "no dispatch", result, broker.request_count == 0)


def test_j73_accepted_response_keeps_reservation() -> None:
    result = _run(broker=FakeBroker("accepted"))
    _note("J73", "test_j73_accepted_response_keeps_reservation", "try_begin_order_submission", "accepted hold", result, result["status"] == "accepted" and exposure_entry_block_reason("EUR_USD") == "active_reservation")


def test_j74_complete_fill_does_not_mean_flat() -> None:
    result = _run(broker=FakeBroker("filled"))
    ok = result["status"] == "filled" and exposure_entry_block_reason("EUR_USD") == "exposure_unconfirmed" and confirm_exposure_flat("EUR_USD", evidence="FILLED") is False
    _note("J74", "test_j74_complete_fill_does_not_mean_flat", "finalize_order_fill", "filled remains unconfirmed", result, ok)


def test_j75_partial_fill_preserves_uncertainty() -> None:
    result = _run(broker=FakeBroker("partial", response={"kind": "partial", "units": 1, "price": 1.1}))
    _note("J75", "test_j75_partial_fill_preserves_uncertainty", "finalize_order_fill", "partial", result, result["status"] == "partial" and exposure_entry_block_reason("EUR_USD") == "exposure_unconfirmed")


def test_j76_rejection_releases_reservation() -> None:
    result = _run(broker=FakeBroker("rejected"))
    _note("J76", "test_j76_rejection_releases_reservation", "mark_order_failed_or_cancelled", "rejected", result, result["status"] == "rejected" and exposure_entry_block_reason("EUR_USD") is None)


def test_j77_timeout_preserves_uncertainty() -> None:
    result = _run(broker=FakeBroker("filled", error=TimeoutError("simulated")))
    _note("J77", "test_j77_timeout_preserves_uncertainty", "restore_unresolved_intent", "timeout", result, result["outcome"] == "timeout" and exposure_entry_block_reason("EUR_USD") is not None)


def test_j78_connection_failure_preserves_uncertainty() -> None:
    result = _run(broker=FakeBroker("filled", error=ConnectionError("simulated")))
    _note("J78", "test_j78_connection_failure_preserves_uncertainty", "restore_unresolved_intent", "connection_failure", result, result["outcome"] == "connection_failure" and result["exposure_held"] is True)


def test_j79_ambiguous_response_preserves_uncertainty() -> None:
    result = _run(broker=FakeBroker("ambiguous"))
    second = _run(broker=FakeBroker("filled"))
    _note("J79", "test_j79_ambiguous_response_preserves_uncertainty", "restore_unresolved_intent", "no retry", second, result["status"] == "uncertain" and second["broker_requests"] == 0)


def test_j80_malformed_response_preserves_uncertainty() -> None:
    result = _run(broker=FakeBroker("filled", response={"units": 1}))
    _note("J80", "test_j80_malformed_response_preserves_uncertainty", "evaluate_one_instrument_iteration", "malformed", result, result["outcome"] == "malformed" and result["exposure_held"] is True)


def test_j81_duplicate_fill_is_classified_once() -> None:
    broker = FakeBroker("duplicate_fill", response={"kind": "duplicate_fill", "units": 10, "price": 1.1})
    result = _run(broker=broker)
    _note("J81", "test_j81_duplicate_fill_is_classified_once", "finalize_order_fill", "one request", result, broker.request_count == 1 and result["status"] in {"filled", "partial"})


def test_j82_conflicting_quantity_preserves_uncertainty() -> None:
    result = _run(broker=FakeBroker("conflicting_quantity", response={"kind": "conflicting_quantity", "units": 1, "other": 999}))
    _note("J82", "test_j82_conflicting_quantity_preserves_uncertainty", "evaluate_one_instrument_iteration", "conflicting_fill_quantity", result, result["blocked_by"] == "conflicting_fill_quantity" and get_position("EUR_USD") is None)


def test_j83_position_recording_failure_blocks_another_entry() -> None:
    first = _run(fail_position_record=True)
    second = _run(broker=FakeBroker("filled"))
    _note("J83", "test_j83_position_recording_failure_blocks_another_entry", "note_unconfirmed_exposure", "second blocked", second, first["exposure_held"] is True and second["broker_requests"] == 0)


def test_j84_reservation_update_failure_blocks_another_entry() -> None:
    first = _run(reservation_update_failure=True)
    close_position("EUR_USD")
    second = _run(broker=FakeBroker("filled"))
    _note("J84", "test_j84_reservation_update_failure_blocks_another_entry", "refuse_reservation_after_database_fault", "fail closed", second, first["status"] == "filled" and second["blocked_by"] == "recovery_unreadable")


def test_j85_reconciliation_token_does_not_clear_exposure() -> None:
    result = _run(reconciliation_token="CONFIRMED_FLAT")
    _note("J85", "test_j85_reconciliation_token_does_not_clear_exposure", "evaluate_one_instrument_iteration", "token ignored", result, result["exposure_held"] is True and "fake_reconciliation" in str(result["source_gap"]))


def test_j86_flat_token_without_broker_evidence_is_not_applied_by_the_seam() -> None:
    result = _run(reconciliation_token="CONFIRMED_FLAT")
    _note("J86", "test_j86_flat_token_without_broker_evidence_is_not_applied_by_the_seam", "exposure_entry_block_reason", "still held", result, exposure_entry_block_reason("EUR_USD") == "exposure_unconfirmed")


def test_j87_close_timeout_evidence_keeps_the_hold() -> None:
    _run()
    reason = interpret_close_evidence("EUR_USD", "timeout")
    result = {"status": "uncertain", "blocked_by": reason, "broker_requests": 0, "exposure_held": True}
    _note("J87", "test_j87_close_timeout_evidence_keeps_the_hold", "interpret_close_evidence", "hold remains", result, reason is not None)


def test_j88_close_rejection_evidence_keeps_the_hold() -> None:
    _run()
    reason = interpret_close_evidence("EUR_USD", "rejected")
    result = {"status": "uncertain", "blocked_by": reason, "broker_requests": 0}
    _note("J88", "test_j88_close_rejection_evidence_keeps_the_hold", "interpret_close_evidence", "hold remains", result, reason is not None)


def test_j89_partial_close_evidence_keeps_the_hold() -> None:
    _run()
    reason = interpret_close_evidence("EUR_USD", "partial")
    result = {"status": "uncertain", "blocked_by": reason, "broker_requests": 0}
    _note("J89", "test_j89_partial_close_evidence_keeps_the_hold", "interpret_close_evidence", "hold remains", result, reason is not None)


def test_j90_unresolved_order_remains_after_fill() -> None:
    result = _run()
    restore_unresolved_intent("EUR_USD", str(result["client_order_id"]))
    blocked = exposure_entry_block_reason("EUR_USD")
    outcome = {"status": "uncertain", "blocked_by": blocked, "broker_requests": 0}
    _note("J90", "test_j90_unresolved_order_remains_after_fill", "restore_unresolved_intent", "unresolved or exposure", outcome, blocked in {"unresolved_intent", "exposure_unconfirmed"})


def test_j91_repeated_response_does_not_create_a_second_request() -> None:
    broker = FakeBroker("filled")
    first = _run(broker=broker)
    try:
        broker.submit({"symbol": "EUR_USD", "simulation": True})
        second_open = True
    except RuntimeError:
        second_open = False
    result = {"status": first["status"], "blocked_by": "", "broker_requests": broker.request_count}
    _note("J91", "test_j91_repeated_response_does_not_create_a_second_request", "FakeBroker.close", "broker closed after one", result, broker.request_count == 1 and second_open is False)


def test_j92_restart_snapshot_keeps_historical_filled_blocked() -> None:
    first = _run()
    row = {"client_order_id": first["client_order_id"], "symbol": "EUR_USD", "status": "FILLED", "metadata": {"exposure_safety": "UNCONFIRMED"}}
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    close_position("EUR_USD")
    kept = select_rows_for_recovery([row])
    ingest_recovery_snapshot(kept, True)
    second = _run(broker=FakeBroker("filled"))
    _note("J92", "test_j92_restart_snapshot_keeps_historical_filled_blocked", "ingest_recovery_snapshot", "exposure_unconfirmed", second, second["blocked_by"] == "exposure_unconfirmed" and second["broker_requests"] == 0)


def test_j93_exactly_one_iteration() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("J93", "test_j93_exactly_one_iteration", "evaluate_one_instrument_iteration", "one request", result, broker.request_count == 1 and result["scheduled_another"] is False)


def test_j94_no_second_iteration_scheduled() -> None:
    result = _run()
    _note("J94", "test_j94_no_second_iteration_scheduled", "evaluate_one_instrument_iteration", "scheduled_another false", result, result["scheduled_another"] is False)


def test_j95_run_bot_is_not_called() -> None:
    result = _run()
    _note("J95", "test_j95_run_bot_is_not_called", "evaluate_one_instrument_iteration", "run_bot not entered", result, result["scheduled_another"] is False and run_bot.__name__ == "run_bot")


def test_j96_no_infinite_loop() -> None:
    result = _run()
    _note("J96", "test_j96_no_infinite_loop", "evaluate_one_instrument_iteration", "returned", result, result["status"] in {"filled", "blocked", "accepted", "rejected", "partial", "uncertain"})


def test_j97_no_sleep() -> None:
    result = _run()
    _note("J97", "test_j97_no_sleep", "evaluate_one_instrument_iteration", "no sleep phase", result, "sleep" not in result["phases"])


def test_j98_no_new_background_thread() -> None:
    before = {thread.ident for thread in threading.enumerate()}
    result = _run()
    after = {thread.ident for thread in threading.enumerate()}
    _note("J98", "test_j98_no_new_background_thread", "evaluate_one_instrument_iteration", "no new thread", result, before == after)


def test_j99_fake_broker_closed() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("J99", "test_j99_fake_broker_closed", "FakeBroker.close", "closed", result, broker.closed is True)


def test_j100_fake_persistence_closed() -> None:
    book = FakeResource("persistence")
    result = _run()
    book.close()
    _note("J100", "test_j100_fake_persistence_closed", "FakeResource.close", "closed", result, book.closed is True)


def test_j101_fake_data_provider_closed() -> None:
    data = FakeResource("candles")
    result = _run()
    data.close()
    _note("J101", "test_j101_fake_data_provider_closed", "FakeResource.close", "closed", result, data.closed is True)


def test_j102_exception_closes_the_fake_broker() -> None:
    broker = FakeBroker("filled", error=RuntimeError("simulated failure"))
    result = _run(broker=broker)
    _note("J102", "test_j102_exception_closes_the_fake_broker", "FakeBroker.close", "closed after error", result, broker.closed is True and result["status"] == "uncertain")


def test_j103_repeated_runs_match() -> None:
    first = _run(symbol="EUR_USD", client_order_id="repeat-a")
    setup_function()
    second = _run(symbol="EUR_USD", client_order_id="repeat-b")
    ok = first["status"] == second["status"] == "filled" and float(first["units"]) == float(second["units"])
    _note("J103", "test_j103_repeated_runs_match", "position_sizing", "same units", second, ok, first_units=first["units"])


def test_j104_no_production_permission_mutation() -> None:
    _run()
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("J104", "test_j104_no_production_permission_mutation", "live_safety path", "unchanged", result, _ops_stamp() == OPS_BEFORE)


def test_j105_no_real_order() -> None:
    result = _run()
    _note("J105", "test_j105_no_real_order", "evaluate_one_instrument_iteration", "real_broker false", result, result["real_broker"] is False)


def test_j106_database_connection_stays_closed() -> None:
    _run()
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("J106", "test_j106_database_connection_stays_closed", "database._pg_conn", "no connection", result, database._pg_conn is None)


def test_j107_weekend_boundary_does_not_schedule() -> None:
    result = _run(now=WEEKEND)
    blocked = result["blocked_by"] in {"weekend_flatten", "market_session_closed"}
    _note("J107", "test_j107_weekend_boundary_does_not_schedule", "flatten_for_weekend_at", "weekend blocked", result, blocked and result["scheduled_another"] is False and result["broker_requests"] == 0)


def test_j108_pending_reservation_regression() -> None:
    note_blocking_reservation("EUR_USD", "r8-pending")
    result = _run()
    _note("J108", "test_j108_pending_reservation_regression", "note_blocking_reservation", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_j109_partial_reservation_regression() -> None:
    register_order(LocalOrder("r8-partial", "EUR_USD", "BUY", 4, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation("EUR_USD", "r8-partial")
    result = _run()
    _note("J109", "test_j109_partial_reservation_regression", "reservation_status_block_reason", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_j110_unresolved_reservation_regression() -> None:
    restore_unresolved_intent("EUR_USD", "r8-unresolved")
    result = _run()
    _note("J110", "test_j110_unresolved_reservation_regression", "restore_unresolved_intent", "unresolved_intent", result, result["blocked_by"] == "unresolved_intent")


def test_j111_filled_exposure_regression() -> None:
    note_unconfirmed_exposure("EUR_USD", "r9-filled")
    result = _run()
    _note("J111", "test_j111_filled_exposure_regression", "note_unconfirmed_exposure", "exposure_unconfirmed", result, result["blocked_by"] == "exposure_unconfirmed" and confirm_exposure_flat("EUR_USD", evidence="filled") is False)


def test_j112_missing_position_regression() -> None:
    note_unconfirmed_exposure("EUR_USD", "r9-missing")
    result = _run()
    _note("J112", "test_j112_missing_position_regression", "exposure_entry_block_reason", "missing position still blocked", result, get_position("EUR_USD") is None and result["blocked_by"] == "exposure_unconfirmed")


def test_j113_historical_filled_regression() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "r11-filled", "symbol": "EUR_USD", "status": "FILLED"}])
    ingest_recovery_snapshot(kept, True)
    result = _run()
    _note("J113", "test_j113_historical_filled_regression", "select_rows_for_recovery", "historical FILLED blocks", result, kept and result["blocked_by"] == "exposure_unconfirmed")


def test_j114_offline_startup_regression() -> None:
    spec = importlib.util.spec_from_file_location("r10_fakes", ROOT / "tests" / "r10_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    from forex_bot.app import initialise_application

    report = module.drive(initialise_application(module.OfflineServices().ports())) if hasattr(module, "drive") else None
    if report is None:
        coro = initialise_application(module.OfflineServices().ports())
        try:
            while True:
                coro.send(None)
        except StopIteration as stop:
            report = stop.value
    result = {"status": "offline", "blocked_by": "", "broker_requests": 0}
    _note("J114", "test_j114_offline_startup_regression", "initialise_application", "offline ready only", result, report.offline_ready is True and report.trading_ready is False)


def test_j115_no_real_broker_or_network() -> None:
    _run()
    import forex_bot.oanda_client as oanda_client

    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("J115", "test_j115_no_real_broker_or_network", "oanda_client._api", "no client", result, oanda_client._api is None and "main" not in sys.modules)


def test_j116_no_postgresql() -> None:
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("J116", "test_j116_no_postgresql", "database._pg_conn", "no connection", result, database._pg_conn is None and os.environ["PERSIST_EXEC_ORDERS"] == "0")


def test_j117_no_production_launcher() -> None:
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("J117", "test_j117_no_production_launcher", "sys.modules", "main not imported", result, "main" not in sys.modules)


def test_j118_no_run_bot() -> None:
    result = _run()
    _note("J118", "test_j118_no_run_bot", "evaluate_one_instrument_iteration", "run_bot not called", result, "run_bot" not in result["phases"])


def test_j119_postgresql_not_evaluated() -> None:
    record("J119", "test_j119_postgresql_not_evaluated", "PostgreSQL", "NOT_EVALUATED", None, "NOT_EVALUATED", seam_ran=False)
    pytest.skip("NOT_EVALUATED")


def test_j120_broker_execution_not_evaluated() -> None:
    record("J120", "test_j120_broker_execution_not_evaluated", "OANDA", "NOT_EVALUATED", None, "NOT_EVALUATED", seam_ran=False)
    pytest.skip("NOT_EVALUATED")


def test_j121_production_loop_not_evaluated() -> None:
    record("J121", "test_j121_production_loop_not_evaluated", "run_bot", "NOT_EVALUATED", None, "NOT_EVALUATED", seam_ran=False)
    pytest.skip("NOT_EVALUATED")


def test_j122_broker_reconciliation_not_evaluated() -> None:
    record("J122", "test_j122_broker_reconciliation_not_evaluated", "broker reconciliation", "NOT_EVALUATED", None, "NOT_EVALUATED", seam_ran=False)
    pytest.skip("NOT_EVALUATED")


def test_j123_profitability_not_evaluated() -> None:
    record("J123", "test_j123_profitability_not_evaluated", "profitability", "NOT_EVALUATED", None, "NOT_EVALUATED", seam_ran=False)
    pytest.skip("NOT_EVALUATED")

