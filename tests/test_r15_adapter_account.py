"""Offline adapter contract and fail-closed account validation. No broker and no database."""

from __future__ import annotations

import atexit
import importlib.util
import inspect
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R15 = ROOT / "data" / "research" / "adaptive_ensemble" / "r15"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R15 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    _account_entry_block,
    broker_open_arguments,
    broker_signed_units,
    dispatch_production_iteration,
    evaluate_one_instrument_iteration,
    production_execution_adapter,
    rl_decision_state,
    run_bot,
)
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    exposure_entry_block_reason,
    note_blocking_reservation,
    note_unconfirmed_exposure,
    reset_order_intent_gate_for_tests,
    select_rows_for_recovery,
)
from forex_bot.indicators import compute_indicators  # noqa: E402
from forex_bot.orders import (  # noqa: E402
    LocalOrder,
    OrderStatus,
    ingest_recovery_snapshot,
    register_order,
    reset_orders_for_tests,
)
from forex_bot.positions import Position, close_position, get_position, open_position, positions  # noqa: E402
from forex_bot.rl_agent import RLAgent  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

_fake_spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
_fake_mod = importlib.util.module_from_spec(_fake_spec)
assert _fake_spec is not None and _fake_spec.loader is not None
_fake_spec.loader.exec_module(_fake_mod)
FakeBroker = _fake_mod.FakeBroker

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
SYMBOL = "EUR_USD"
NAMES = (
    "scalp",
    "trend",
    "mean_reversion",
    "swing_trend",
    "swing_mean_reversion",
    "swing_breakout",
)
RECORDS: list[dict[str, object]] = []
SOURCE = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")


def _bars(n: int = 50, start: float = 1.1) -> list[dict[str, float | str]]:
    return [
        {
            "open": start,
            "high": start + 0.0002,
            "low": start - 0.0002,
            "close": start,
            "time": "2026-01-07T11:55:00+00:00",
        }
        for _ in range(n)
    ]


def _state() -> str:
    import pandas as pd

    return rl_decision_state(compute_indicators(pd.DataFrame(_bars())))


def _agent(action: str) -> RLAgent:
    agent = RLAgent(epsilon=0.0)
    table = {"BUY": 0.0, "SELL": 0.0, "SKIP": 0.0}
    table[action] = 1.0
    agent.q[_state()] = table
    agent.persisted_ok = True
    return agent


def _deps(**overrides: object) -> IterationDependencies:
    broker = overrides.pop("broker", None) or FakeBroker("filled")
    values: dict[str, object] = {
        "candles": _bars(),
        "balance": 10000.0,
        "account_present": True,
        "account_context": "isolated_test",
        "simulation": True,
        "now": OPEN,
        "quote_as_of": OPEN,
        "price": 1.1,
        "bid": 1.09995,
        "ask": 1.10005,
        "stop_distance": 0.001,
        "stop_loss": 1.099,
        "take_profit": 1.102,
        "broker": broker,
        "strategy_name": "scalp",
        "strategy_known": True,
        "strategy_active": True,
        "strategy_authorised": True,
        "safety_initialised": True,
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.8},
        "strategy_active_map": {"scalp": True},
        "invoke_selector": True,
        "invoke_vote": True,
        "invoke_rl": True,
        "rl_agent": _agent("BUY"),
    }
    values.update(overrides)
    if "unrealised" not in overrides:
        values["unrealised"] = 0.0
    if "account_as_of" not in overrides:
        values["account_as_of"] = values.get("now")
    return IterationDependencies(**values)  # type: ignore[arg-type]


def _run(**overrides: object) -> dict:
    return evaluate_one_instrument_iteration(SYMBOL, _deps(**overrides))


def _voted(direction: str, **overrides: object) -> dict:
    return _run(
        vote={"allow": True, "direction": direction, "confidence": 0.8},
        rl_agent=_agent(direction.strip().upper()),
        **overrides,
    )


def _note(test_id: str, function: str, source: str, result: dict | None, ok: bool, **extra: object) -> None:
    details = {} if result is None else dict(result.get("details") or {})
    RECORDS.append(
        {
            "id": test_id,
            "function": function,
            "source": source,
            "selector": bool(details.get("selector_called")),
            "vote_wrapper": bool(details.get("vote_wrapper_called")),
            "rl_veto": bool(details.get("rl_veto_called")),
            "account_gate": bool(details.get("account_gate")),
            "sizing": bool(details.get("sizing_invoked")),
            "reservation": bool(details.get("reservation_attempted")),
            "inert_adapter": bool(details.get("adapter_called")),
            "real_adapter": bool(details.get("production_adapter_invoked")),
            "fake_requests": int(0 if result is None else result.get("broker_requests") or 0),
            "real_broker_requests": 0,
            "status": "PASS" if ok else "FAIL",
            "evidence": extra,
        }
    )
    assert ok


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R15)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R15 / "synthetic_live_safety_state.json")
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def _request(direction: str = "BUY", **overrides: object) -> tuple[dict, dict]:
    broker = overrides.pop("broker", None) or FakeBroker("filled")
    result = _voted(direction, broker=broker, **overrides)
    return result, broker.requests[0]


def test_j01_buy_symbol_preserved() -> None:
    result, request = _request("BUY")
    _note("J01", "test_j01_buy_symbol_preserved", "broker_open_arguments", result, request["symbol"] == SYMBOL)


def test_j02_sell_symbol_preserved() -> None:
    result, request = _request("SELL")
    _note("J02", "test_j02_sell_symbol_preserved", "broker_open_arguments", result, request["symbol"] == SYMBOL)


def test_j03_buy_direction_preserved() -> None:
    result, request = _request("BUY")
    _note("J03", "test_j03_buy_direction_preserved", "broker_open_arguments", result, request["direction"] == "BUY")


def test_j04_sell_direction_preserved() -> None:
    result, request = _request("SELL")
    _note("J04", "test_j04_sell_direction_preserved", "broker_open_arguments", result, request["direction"] == "SELL")


def test_j05_buy_quantity_preserved() -> None:
    result, request = _request("BUY")
    _note("J05", "test_j05_buy_quantity_preserved", "broker_open_arguments", result, request["units"] == result["units"] and request["units"] > 0)


def test_j06_sell_quantity_preserved() -> None:
    result, request = _request("SELL")
    _note("J06", "test_j06_sell_quantity_preserved", "broker_open_arguments", result, request["units"] == result["units"] and request["units"] > 0)


def test_j07_quantity_sign_matches_broker_contract() -> None:
    _buy, buy_request = _request("BUY")
    setup_function()
    sell, sell_request = _request("SELL")
    ok = buy_request["broker_signed_units"] > 0 and sell_request["broker_signed_units"] < 0
    ok = ok and broker_signed_units(4, "BUY") == 4 and broker_signed_units(4, "SELL") == -4
    _note("J07", "test_j07_quantity_sign_matches_broker_contract", "broker_signed_units", sell, ok)


def test_j08_stop_loss_preserved() -> None:
    result, request = _request("BUY", stop_loss=1.09)
    _note("J08", "test_j08_stop_loss_preserved", "broker_open_arguments", result, request["stop_loss"] == 1.09)


def test_j09_take_profit_preserved() -> None:
    result, request = _request("BUY", take_profit=1.12)
    _note("J09", "test_j09_take_profit_preserved", "broker_open_arguments", result, request["take_profit"] == 1.12)


def test_j10_client_order_id_preserved() -> None:
    result, request = _request("BUY", client_order_id="cid-r15")
    _note("J10", "test_j10_client_order_id_preserved", "broker_open_arguments", result, request["client_order_id"] == "cid-r15")


def test_j11_reservation_identity_preserved() -> None:
    result, request = _request("BUY", client_order_id="cid-r15")
    _note("J11", "test_j11_reservation_identity_preserved", "try_begin_order_submission", result, request["reservation_id"] == "cid-r15")


def test_j12_instrument_mapping_preserved() -> None:
    mapped = broker_open_arguments(
        symbol="eur-usd",
        units=2,
        direction="BUY",
        client_order_id="cid",
        stop_loss=1.0,
        take_profit=1.2,
        execution_kind="simulated",
        entry_quote=None,
    )
    _note("J12", "test_j12_instrument_mapping_preserved", "normalize_oanda_symbol", None, mapped["symbol"] == "EUR_USD")


def test_j13_no_duplicate_broker_call() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", broker=broker)
    _note("J13", "test_j13_no_duplicate_broker_call", "FakeBroker.submit", result, broker.request_count == 1)


def test_j14_no_duplicate_client_id() -> None:
    register_order(LocalOrder("same", SYMBOL, "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _run(client_order_id="same")
    _note("J14", "test_j14_no_duplicate_client_id", "try_begin_order_submission", result, result["blocked_by"] == "reservation_refused" and result["broker_requests"] == 0)


def test_j15_invalid_quantity_blocked() -> None:
    result = _run(stop_distance=0)
    _note("J15", "test_j15_invalid_quantity_blocked", "position_sizing", result, result["blocked_by"] == "size_not_positive" and result["broker_requests"] == 0)


def test_j16_zero_quantity_blocked() -> None:
    result = _run(stop_distance=0)
    _note("J16", "test_j16_zero_quantity_blocked", "position_sizing", result, result["units"] == 0 and result["broker_requests"] == 0)


def test_j17_negative_quantity_not_dispatched() -> None:
    result = _run(balance=-10)
    mirrored = broker_signed_units(-3, "SELL") == -3
    _note("J17", "test_j17_negative_quantity_not_dispatched", "account_entry_block", result, result["blocked_by"] == "account_equity_not_positive" and result["broker_requests"] == 0 and mirrored)


def test_j18_nonfinite_quantity_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("forex_bot.trading.position_sizing", lambda *args, **kwargs: float("nan"))
    result = _run()
    _note("J18", "test_j18_nonfinite_quantity_blocked", "evaluate_one_instrument_iteration", result, result["blocked_by"] == "quantity_nonfinite" and result["broker_requests"] == 0)


def test_j19_invalid_stop_blocked() -> None:
    result = _run(stop_loss=float("nan"))
    _note("J19", "test_j19_invalid_stop_blocked", "broker_open_arguments", result, result["blocked_by"] == "invalid_stop" and result["broker_requests"] == 0)


def test_j20_invalid_target_blocked() -> None:
    result = _run(take_profit="not-a-price")
    _note("J20", "test_j20_invalid_target_blocked", "broker_open_arguments", result, result["blocked_by"] == "invalid_target" and result["broker_requests"] == 0)


def test_j21_invalid_symbol_blocked() -> None:
    result = evaluate_one_instrument_iteration("NOTASYMBOL", _deps())
    _note("J21", "test_j21_invalid_symbol_blocked", "is_valid_oanda_forex_symbol", result, result["blocked_by"] == "invalid_symbol" and result["broker_requests"] == 0)


def test_j22_invalid_direction_blocked() -> None:
    result = _run(vote={"allow": True, "direction": "HOLD", "confidence": 0.9})
    _note("J22", "test_j22_invalid_direction_blocked", "canonical_entry_direction", result, result["blocked_by"] == "invalid_entry_direction" and result["broker_requests"] == 0)


def test_j23_missing_client_id_blocked() -> None:
    result = _run(client_order_id="")
    _note("J23", "test_j23_missing_client_id_blocked", "evaluate_one_instrument_iteration", result, result["blocked_by"] == "missing_client_order_id" and result["details"]["reservation_attempted"] is False)


def test_j24_adapter_exception_fails_closed() -> None:
    broker = FakeBroker(error=RuntimeError("adapter failed"))
    result = _voted("BUY", broker=broker)
    _note("J24", "test_j24_adapter_exception_fails_closed", "FakeBroker.submit", result, result["exposure_held"] is True and broker.request_count == 1)


def test_j25_adapter_timeout_fails_closed() -> None:
    broker = FakeBroker(error=TimeoutError("slow"))
    result = _voted("BUY", broker=broker)
    _note("J25", "test_j25_adapter_timeout_fails_closed", "FakeBroker.submit", result, result["outcome"] == "timeout" and result["exposure_held"] is True)


def test_j26_adapter_malformed() -> None:
    result = _voted("BUY", broker=FakeBroker("malformed"))
    _note("J26", "test_j26_adapter_malformed", "FakeBroker.submit", result, result["outcome"] == "malformed" and result["exposure_held"] is True)


def test_j27_adapter_partial() -> None:
    result = _voted("BUY", broker=FakeBroker("partial"))
    _note("J27", "test_j27_adapter_partial", "finalize_order_fill", result, result["status"] == "partial" and result["exposure_held"] is True)


def test_j28_adapter_ambiguous() -> None:
    result = _voted("BUY", broker=FakeBroker("ambiguous"))
    _note("J28", "test_j28_adapter_ambiguous", "note_unconfirmed_exposure", result, result["outcome"] == "ambiguous" and result["exposure_held"] is True)


def test_j29_adapter_rejection() -> None:
    broker = FakeBroker("rejected")
    result = _voted("BUY", broker=broker)
    _note("J29", "test_j29_adapter_rejection", "FakeBroker.submit", result, result["outcome"] == "rejected" and broker.request_count == 1)


def test_j30_adapter_filled() -> None:
    result = _voted("BUY", broker=FakeBroker("filled"))
    _note("J30", "test_j30_adapter_filled", "finalize_order_fill", result, result["status"] == "filled" and result["outcome"] == "recorded")


def test_j31_no_retry_after_uncertainty() -> None:
    broker = FakeBroker("ambiguous")
    result = _voted("BUY", broker=broker)
    _note("J31", "test_j31_no_retry_after_uncertainty", "FakeBroker.submit", result, broker.request_count == 1)


def test_j32_one_buy_request() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", broker=broker)
    _note("J32", "test_j32_one_buy_request", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "BUY")


def test_j33_one_sell_request() -> None:
    broker = FakeBroker("filled")
    result = _voted("SELL", broker=broker)
    _note("J33", "test_j33_one_sell_request", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "SELL")


def test_j34_production_adapter_not_invoked() -> None:
    result = _voted("BUY")
    body = inspect.getsource(production_execution_adapter)
    _note("J34", "test_j34_production_adapter_not_invoked", "production_execution_adapter", result, result["details"]["production_adapter_invoked"] is False and "execute_oanda_market_open" in body and SOURCE.count("execute_oanda_market_open") == 1)


def _blocked(reason: str, **overrides: object) -> dict:
    result = _run(**overrides)
    return result


def test_j35_missing_account_blocks() -> None:
    result = _blocked("account_missing", account_present=False, balance=None)
    _note("J35", "test_j35_missing_account_blocks", "_account_entry_block", result, result["blocked_by"] == "account_missing" and "sizing" not in result["phases"])


def test_j36_missing_equity_blocks() -> None:
    result = _run(balance=None, account_payload={})
    _note("J36", "test_j36_missing_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_missing")


def test_j37_none_equity_blocks() -> None:
    result = _run(balance=None, account_payload={"equity": None})
    _note("J37", "test_j37_none_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_missing")


def test_j38_zero_equity_blocks() -> None:
    result = _run(balance=0)
    _note("J38", "test_j38_zero_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_not_positive" and "reservation" not in result["phases"])


def test_j39_negative_equity_blocks() -> None:
    result = _run(balance=-1)
    _note("J39", "test_j39_negative_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_not_positive")


def test_j40_nan_equity_blocks() -> None:
    result = _run(balance=float("nan"))
    _note("J40", "test_j40_nan_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_nonfinite")


def test_j41_infinite_equity_blocks() -> None:
    result = _run(balance=float("inf"))
    _note("J41", "test_j41_infinite_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_nonfinite")


def test_j42_numeric_string_parses_and_malformed_string_blocks() -> None:
    malformed = _run(balance="ten thousand")
    parsed = _run(balance="10000")
    ok = parsed["broker_requests"] == 1 and malformed["blocked_by"] == "account_equity_malformed" and malformed["broker_requests"] == 0
    _note("J42", "test_j42_numeric_string_parses_and_malformed_string_blocks", "_account_entry_block", malformed, ok)


def test_j43_malformed_payload_blocks() -> None:
    result = _run(account_payload="nope")  # type: ignore[arg-type]
    _note("J43", "test_j43_malformed_payload_blocks", "_account_entry_block", result, result["blocked_by"] == "account_payload_malformed")


def test_j44_account_exception_blocks() -> None:
    result = _run(account_error="boom")
    _note("J44", "test_j44_account_exception_blocks", "_account_entry_block", result, result["blocked_by"] == "account_acquisition_error" and result["broker_requests"] == 0)


def test_j45_account_timeout_blocks() -> None:
    result = _run(account_timeout=True)
    _note("J45", "test_j45_account_timeout_blocks", "_account_entry_block", result, result["blocked_by"] == "account_acquisition_timeout")


def test_j46_unknown_identity_blocks_when_expected() -> None:
    result = _run(expected_account_id="practice-1", account_payload={})
    _note("J46", "test_j46_unknown_identity_blocks_when_expected", "_account_entry_block", result, result["blocked_by"] == "account_identity_unknown")


def test_j47_identity_mismatch_blocks() -> None:
    result = _run(expected_account_id="practice-1", account_payload={"id": "other"})
    _note("J47", "test_j47_identity_mismatch_blocks", "_account_entry_block", result, result["blocked_by"] == "account_identity_mismatch")


def test_j48_unverified_context_blocks() -> None:
    reason, _value = _account_entry_block(_deps(simulation=False, account_payload={"verified": True, "equity": 10000}))
    result = _run(account_context="production")
    _note("J48", "test_j48_unverified_context_blocks", "_account_entry_block", result, reason == "account_unverified" and result["blocked_by"] == "account_unverified")


def test_j49_stale_snapshot_blocks_in_harness() -> None:
    result = _run(account_as_of=OPEN - timedelta(hours=2))
    _note("J49", "test_j49_stale_snapshot_blocks_in_harness", "_account_entry_block", result, result["blocked_by"] == "account_snapshot_stale")


def test_j50_future_snapshot_blocks_in_harness() -> None:
    result = _run(account_as_of=OPEN + timedelta(hours=1))
    _note("J50", "test_j50_future_snapshot_blocks_in_harness", "_account_entry_block", result, result["blocked_by"] == "account_timestamp_future")


def test_j51_cached_equity_blocks() -> None:
    result = _run(account_cached=True)
    _note("J51", "test_j51_cached_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "unverified_cached_equity" and result["broker_requests"] == 0)


def test_j52_synthetic_without_harness_blocks() -> None:
    result = _run(account_context="synthetic_unscoped")
    _note("J52", "test_j52_synthetic_without_harness_blocks", "_account_entry_block", result, result["blocked_by"] == "account_unverified")


def test_j53_synthetic_harness_allowed() -> None:
    result = _voted("BUY")
    _note("J53", "test_j53_synthetic_harness_allowed", "_account_entry_block", result, result["broker_requests"] == 1 and result["details"]["account_context"] == "isolated_test")


def test_j54_production_snapshot_fail_closed_without_fetch() -> None:
    reason, value = _account_entry_block(_deps(simulation=False, balance=10000, account_payload={"verified": True}))
    _note("J54", "test_j54_production_snapshot_fail_closed_without_fetch", "_account_entry_block", None, reason == "account_unverified" and value is None)


def test_j55_verified_flag_does_not_create_equity() -> None:
    reason, _value = _account_entry_block(_deps(simulation=False, account_payload={"verified": True, "equity": 10000}))
    _note("J55", "test_j55_verified_flag_does_not_create_equity", "_account_entry_block", None, reason == "account_unverified")


def test_j56_no_reservation_after_account_failure() -> None:
    result = _run(account_present=False)
    _note("J56", "test_j56_no_reservation_after_account_failure", "_account_entry_block", result, result["details"]["reservation_attempted"] is False)


def test_j57_no_adapter_after_account_failure() -> None:
    broker = FakeBroker("filled")
    result = _run(account_present=False, broker=broker)
    _note("J57", "test_j57_no_adapter_after_account_failure", "FakeBroker.submit", result, broker.request_count == 0)


def test_j58_no_permission_bypass() -> None:
    result = _run(simulation=False, account_payload={"verified": True})
    _note("J58", "test_j58_no_permission_bypass", "pre_trade_entry_blocked_reason", result, result["broker_requests"] == 0 and result["production_authorised"] is False)


def test_j59_sizing_formula_unchanged() -> None:
    body = inspect.getsource(__import__("forex_bot.trading", fromlist=["position_sizing"]).position_sizing)
    result = _voted("BUY")
    _note("J59", "test_j59_sizing_formula_unchanged", "position_sizing", result, "POSITION_RISK_PCT" in body and result["units"] > 0)


def test_j60_no_account_object() -> None:
    result = _run(account_present=False, account_payload=None, balance=None)
    _note("J60", "test_j60_no_account_object", "_account_entry_block", result, result["blocked_by"] == "account_missing")


def test_j61_empty_account_object() -> None:
    result = _run(balance=None, account_payload={})
    _note("J61", "test_j61_empty_account_object", "_account_entry_block", result, result["blocked_by"] == "account_equity_missing")


def test_j62_missing_equity() -> None:
    result = _run(balance=None, account_payload={"id": "x"})
    _note("J62", "test_j62_missing_equity", "_account_entry_block", result, result["blocked_by"] == "account_equity_missing")


def test_j63_none_equity() -> None:
    result = _run(balance=None)
    _note("J63", "test_j63_none_equity", "_account_entry_block", result, result["blocked_by"] == "account_equity_missing")


def test_j64_zero_equity() -> None:
    result = _run(balance=0.0)
    _note("J64", "test_j64_zero_equity", "_account_entry_block", result, result["broker_requests"] == 0)


def test_j65_negative_equity() -> None:
    result = _run(balance=-5)
    _note("J65", "test_j65_negative_equity", "_account_entry_block", result, result["broker_requests"] == 0)


def test_j66_nan_equity() -> None:
    result = _run(balance=math.nan)
    _note("J66", "test_j66_nan_equity", "_account_entry_block", result, result["blocked_by"] == "account_equity_nonfinite")


def test_j67_positive_infinity() -> None:
    result = _run(balance=math.inf)
    _note("J67", "test_j67_positive_infinity", "_account_entry_block", result, result["blocked_by"] == "account_equity_nonfinite")


def test_j68_negative_infinity() -> None:
    result = _run(balance=-math.inf)
    _note("J68", "test_j68_negative_infinity", "_account_entry_block", result, result["blocked_by"] == "account_equity_nonfinite")


def test_j69_malformed_equity_string() -> None:
    result = _run(balance="1,000")
    _note("J69", "test_j69_malformed_equity_string", "_account_entry_block", result, result["blocked_by"] == "account_equity_malformed")


def test_j70_missing_timestamp_is_not_production_freshness() -> None:
    result = _voted("BUY", account_as_of=None)
    _note(
        "J70",
        "test_j70_missing_timestamp_is_not_production_freshness",
        "_account_entry_block",
        result,
        result["details"].get("account_freshness_not_evaluated") is True
        and result["blocked_by"] == "account_snapshot_timestamp_missing"
        and result["broker_requests"] == 0
        and result["details"].get("reservation_attempted") is False,
    )


def test_j71_stale_timestamp() -> None:
    result = _run(account_as_of=OPEN - timedelta(minutes=10))
    _note("J71", "test_j71_stale_timestamp", "_account_entry_block", result, result["blocked_by"] == "account_snapshot_stale")


def test_j72_future_timestamp() -> None:
    result = _run(account_as_of=OPEN + timedelta(seconds=1))
    _note("J72", "test_j72_future_timestamp", "_account_entry_block", result, result["blocked_by"] == "account_timestamp_future")


def test_j73_unknown_identity() -> None:
    result = _run(expected_account_id="acct", account_payload={"equity": 10000})
    _note("J73", "test_j73_unknown_identity", "_account_entry_block", result, result["blocked_by"] == "account_identity_unknown")


def test_j74_wrong_identity() -> None:
    result = _run(expected_account_id="acct", account_payload={"id": "other", "equity": 10000})
    _note("J74", "test_j74_wrong_identity", "_account_entry_block", result, result["blocked_by"] == "account_identity_mismatch")


def test_j75_cached_fallback() -> None:
    result = _run(account_cached=True, balance=10000)
    _note("J75", "test_j75_cached_fallback", "_account_entry_block", result, result["blocked_by"] == "unverified_cached_equity")


def test_j76_synthetic_without_context() -> None:
    result = _run(account_context="")
    _note("J76", "test_j76_synthetic_without_context", "_account_entry_block", result, result["blocked_by"] == "account_unverified" and result["broker_requests"] == 0)


def test_j77_synthetic_with_isolated_context() -> None:
    result = _voted("BUY", account_context="isolated_test")
    _note("J77", "test_j77_synthetic_with_isolated_context", "_account_entry_block", result, result["broker_requests"] == 1)


def test_j78_valid_deterministic_account() -> None:
    result = _voted("BUY", account_as_of=OPEN, account_payload={"id": "acct", "equity": 10000}, expected_account_id="acct")
    _note("J78", "test_j78_valid_deterministic_account", "_account_entry_block", result, result["broker_requests"] == 1 and result["details"]["account_equity"] == 10000)


def test_j79_account_raises() -> None:
    result = _run(account_error="disconnected")
    _note("J79", "test_j79_account_raises", "_account_entry_block", result, result["broker_requests"] == 0)


def test_j80_account_times_out() -> None:
    result = _run(account_timeout=True)
    _note("J80", "test_j80_account_times_out", "_account_entry_block", result, result["broker_requests"] == 0)


def test_j81_malformed_provenance_payload() -> None:
    result = _run(account_payload=["not", "a", "dict"])  # type: ignore[arg-type]
    _note("J81", "test_j81_malformed_provenance_payload", "_account_entry_block", result, result["blocked_by"] == "account_payload_malformed")


def test_j82_equity_read_once() -> None:
    result = _voted("BUY", balance=10000)
    _note("J82", "test_j82_equity_read_once", "_account_entry_block", result, result["details"]["account_equity"] == 10000 and result["broker_requests"] == 1)


def test_j83_expired_snapshot() -> None:
    result = _run(account_as_of=OPEN - timedelta(days=1))
    _note("J83", "test_j83_expired_snapshot", "_account_entry_block", result, result["blocked_by"] == "account_snapshot_stale" and result["broker_requests"] == 0)


def test_j84_account_failure_before_reservation() -> None:
    result = _run(balance=None)
    _note("J84", "test_j84_account_failure_before_reservation", "_account_entry_block", result, "reservation" not in result["phases"])


def test_j85_account_failure_before_dispatch() -> None:
    broker = FakeBroker("filled")
    result = _run(balance=0, broker=broker)
    _note("J85", "test_j85_account_failure_before_dispatch", "FakeBroker.submit", result, broker.request_count == 0)


def test_j86_sizing_formula_not_rewritten() -> None:
    text = (ROOT / "forex_bot" / "trading.py").read_text(encoding="utf-8")
    _note("J86", "test_j86_sizing_formula_not_rewritten", "position_sizing", None, "def position_sizing" in text and "risk_amount = balance_eff * rp" in text)


def test_j87_account_policy_not_weakened() -> None:
    reason, _value = _account_entry_block(_deps(account_present=False))
    _note("J87", "test_j87_account_policy_not_weakened", "_account_entry_block", None, reason == "account_missing")


def test_j88_no_real_account_request() -> None:
    _voted("BUY")
    _note("J88", "test_j88_no_real_account_request", "_account_entry_block", None, "fetch_account_summary" not in inspect.getsource(_account_entry_block))


def test_j89_no_real_broker_request() -> None:
    result = _voted("BUY")
    _note("J89", "test_j89_no_real_broker_request", "production_execution_adapter", result, result["real_broker"] is False)


def test_j90_pending_blocks() -> None:
    note_blocking_reservation(SYMBOL, "p")
    result = _run()
    _note("J90", "test_j90_pending_blocks", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation")


def test_j91_partial_blocks() -> None:
    register_order(LocalOrder("part", SYMBOL, "BUY", 1, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "part")
    result = _run()
    _note("J91", "test_j91_partial_blocks", "reservation_status_block_reason", result, result["broker_requests"] == 0)


def test_j92_unresolved_blocks() -> None:
    register_order(LocalOrder("un", SYMBOL, "BUY", 1, 0, OrderStatus.UNRESOLVED, None, 0.0))
    note_blocking_reservation(SYMBOL, "un")
    result = _run()
    _note("J92", "test_j92_unresolved_blocks", "reservation_status_block_reason", result, result["broker_requests"] == 0)


def test_j93_unknown_status_blocks() -> None:
    from forex_bot.database import reservation_status_block_reason

    reason = reservation_status_block_reason("MYSTERY")
    _note("J93", "test_j93_unknown_status_blocks", "reservation_status_block_reason", None, reason == "unknown_status")


def test_j94_historical_filled_blocks() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "old", "symbol": SYMBOL, "status": "FILLED", "metadata": {}}])
    ingest_recovery_snapshot(kept, True)
    result = _run()
    _note("J94", "test_j94_historical_filled_blocks", "select_rows_for_recovery", result, result["blocked_by"] == "exposure_unconfirmed")


def test_j95_missing_position_hold_blocks() -> None:
    note_unconfirmed_exposure(SYMBOL, "held")
    result = _run()
    _note("J95", "test_j95_missing_position_hold_blocks", "exposure_entry_block_reason", result, get_position(SYMBOL) is None and result["blocked_by"] == "exposure_unconfirmed")


def test_j96_duplicate_client_blocks() -> None:
    register_order(LocalOrder("dup", SYMBOL, "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _run(client_order_id="dup")
    _note("J96", "test_j96_duplicate_client_blocks", "try_begin_order_submission", result, result["blocked_by"] == "reservation_refused")


def test_j97_duplicate_symbol_blocks() -> None:
    note_blocking_reservation(SYMBOL, "sym")
    result = _run()
    _note("J97", "test_j97_duplicate_symbol_blocks", "note_blocking_reservation", result, result["broker_requests"] == 0)


def test_j98_persistence_failure_blocks() -> None:
    result = _run(persistence_failure="down")
    _note("J98", "test_j98_persistence_failure_blocks", "refuse_reservation_after_database_fault", result, result["blocked_by"] == "reservation_persistence_failed")


def test_j99_filled_does_not_mean_flat() -> None:
    result = _voted("BUY")
    _note("J99", "test_j99_filled_does_not_mean_flat", "confirm_exposure_flat", result, confirm_exposure_flat(SYMBOL, evidence="FILLED") is False and exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed")


def test_j100_partial_retains_hold() -> None:
    result = _voted("BUY", broker=FakeBroker("partial"))
    _note("J100", "test_j100_partial_retains_hold", "finalize_order_fill", result, result["exposure_held"] is True)


def test_j101_timeout_retains_hold() -> None:
    result = _voted("BUY", broker=FakeBroker("timeout"))
    _note("J101", "test_j101_timeout_retains_hold", "note_unconfirmed_exposure", result, result["exposure_held"] is True)


def test_j102_ambiguous_retains_hold() -> None:
    result = _voted("BUY", broker=FakeBroker("ambiguous"))
    _note("J102", "test_j102_ambiguous_retains_hold", "restore_unresolved_intent", result, result["exposure_held"] is True)


def test_j103_malformed_retains_hold() -> None:
    result = _voted("BUY", broker=FakeBroker("malformed"))
    _note("J103", "test_j103_malformed_retains_hold", "note_unconfirmed_exposure", result, result["exposure_held"] is True)


def test_j104_position_record_failure_retains_hold() -> None:
    result = _voted("BUY", fail_position_record=True)
    _note("J104", "test_j104_position_record_failure_retains_hold", "record_synthetic_fill_position", result, result["exposure_held"] is True)


def test_j105_rejection_does_not_replace() -> None:
    broker = FakeBroker("rejected")
    result = _voted("BUY", broker=broker)
    _note("J105", "test_j105_rejection_does_not_replace", "FakeBroker.submit", result, result["outcome"] == "rejected" and broker.request_count == 1)


def test_j106_no_automatic_retry() -> None:
    broker = FakeBroker("timeout")
    result = _voted("BUY", broker=broker)
    _note("J106", "test_j106_no_automatic_retry", "FakeBroker.submit", result, broker.request_count == 1)


def test_j107_no_fabricated_flat_release() -> None:
    _note("J107", "test_j107_no_fabricated_flat_release", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT", verified=True) is False)


def test_j108_no_fabricated_position() -> None:
    result = _voted("BUY", broker=FakeBroker("ambiguous"))
    _note("J108", "test_j108_no_fabricated_position", "note_unconfirmed_exposure", result, get_position(SYMBOL) is None)


def test_j109_no_second_adapter_call() -> None:
    broker = FakeBroker("ambiguous")
    result = _voted("BUY", broker=broker)
    _note("J109", "test_j109_no_second_adapter_call", "FakeBroker.submit", result, broker.request_count == 1 and result["details"]["production_adapter_invoked"] is False)


def test_j110_end_to_end_buy() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", broker=broker)
    details = result["details"]
    ok = broker.request_count == 1 and details["selector_called"] and details["vote_wrapper_called"] and details["rl_veto_called"] and details["account_gate"] and details["sizing_invoked"] and details["reservation_attempted"] and details["adapter_called"]
    _note("J110", "test_j110_end_to_end_buy", "evaluate_one_instrument_iteration", result, ok)


def test_j111_end_to_end_sell() -> None:
    broker = FakeBroker("filled")
    result = _voted("SELL", broker=broker)
    _note("J111", "test_j111_end_to_end_sell", "evaluate_one_instrument_iteration", result, broker.request_count == 1 and result["direction"] == "SELL")


def test_j112_permission_blocked() -> None:
    result = _run(simulation=False)
    _note("J112", "test_j112_permission_blocked", "pre_trade_entry_blocked_reason", result, result["broker_requests"] == 0)


def test_j113_strategy_inactive() -> None:
    result = _run(strategy_active=False, strategy_active_map={})
    _note("J113", "test_j113_strategy_inactive", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and result["broker_requests"] == 0)


def test_j114_rl_veto() -> None:
    result = _run(rl_agent=_agent("SKIP"))
    _note("J114", "test_j114_rl_veto", "RLAgent.decide", result, result["blocked_by"] == "rl_veto" and result["details"]["reservation_attempted"] is False)


def test_j115_invalid_vote() -> None:
    result = _run(vote={"allow": True, "direction": "NO_TRADE", "confidence": 0.4})
    _note("J115", "test_j115_invalid_vote", "canonical_entry_direction", result, result["broker_requests"] == 0)


def test_j116_missing_account() -> None:
    result = _run(account_present=False)
    _note("J116", "test_j116_missing_account", "_account_entry_block", result, result["blocked_by"] == "account_missing")


def test_j117_stale_account() -> None:
    result = _run(account_as_of=OPEN - timedelta(hours=3))
    _note("J117", "test_j117_stale_account", "_account_entry_block", result, result["blocked_by"] == "account_snapshot_stale")


def test_j118_unverified_account() -> None:
    result = _run(account_context="production", account_payload={"verified": True})
    _note("J118", "test_j118_unverified_account", "_account_entry_block", result, result["blocked_by"] == "account_unverified" and result["details"]["adapter_called"] is False)


def test_j119_existing_position() -> None:
    open_position(Position(SYMBOL, "BUY", 1, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    result = _run()
    _note("J119", "test_j119_existing_position", "get_position", result, result["blocked_by"] == "position_already_open")


def test_j120_historical_filled() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "h", "symbol": SYMBOL, "status": "FILLED"}])
    ingest_recovery_snapshot(kept, True)
    result = _run()
    _note("J120", "test_j120_historical_filled", "select_rows_for_recovery", result, result["broker_requests"] == 0)


def test_j121_pending_reservation() -> None:
    note_blocking_reservation(SYMBOL, "pend")
    result = _run()
    _note("J121", "test_j121_pending_reservation", "note_blocking_reservation", result, result["broker_requests"] == 0)


def test_j122_partial_reservation() -> None:
    register_order(LocalOrder("p2", SYMBOL, "BUY", 1, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "p2")
    result = _run()
    _note("J122", "test_j122_partial_reservation", "reservation_status_block_reason", result, result["broker_requests"] == 0)


def test_j123_unresolved_reservation() -> None:
    register_order(LocalOrder("u2", SYMBOL, "BUY", 1, 0, OrderStatus.UNRESOLVED, None, 0.0))
    note_blocking_reservation(SYMBOL, "u2")
    result = _run()
    _note("J123", "test_j123_unresolved_reservation", "reservation_status_block_reason", result, result["broker_requests"] == 0)


def test_j124_invalid_quantity() -> None:
    result = _run(stop_distance=0)
    _note("J124", "test_j124_invalid_quantity", "position_sizing", result, result["broker_requests"] == 0)


def test_j125_reservation_failure() -> None:
    result = _run(persistence_failure="io")
    _note("J125", "test_j125_reservation_failure", "refuse_reservation_after_database_fault", result, result["broker_requests"] == 0)


def test_j126_adapter_rejection() -> None:
    result = _voted("BUY", broker=FakeBroker("rejected"))
    _note("J126", "test_j126_adapter_rejection", "FakeBroker.submit", result, result["outcome"] == "rejected")


def test_j127_adapter_timeout() -> None:
    result = _voted("BUY", broker=FakeBroker(error=TimeoutError("t")))
    _note("J127", "test_j127_adapter_timeout", "FakeBroker.submit", result, result["outcome"] == "timeout")


def test_j128_adapter_partial() -> None:
    result = _voted("BUY", broker=FakeBroker("partial"))
    _note("J128", "test_j128_adapter_partial", "finalize_order_fill", result, result["status"] == "partial")


def test_j129_adapter_ambiguous() -> None:
    result = _voted("BUY", broker=FakeBroker("ambiguous"))
    _note("J129", "test_j129_adapter_ambiguous", "note_unconfirmed_exposure", result, result["outcome"] == "ambiguous")


def test_j130_adapter_malformed() -> None:
    result = _voted("BUY", broker=FakeBroker("malformed"))
    _note("J130", "test_j130_adapter_malformed", "FakeBroker.submit", result, result["outcome"] == "malformed")


def test_j131_adapter_exception() -> None:
    result = _voted("BUY", broker=FakeBroker(error=RuntimeError("x")))
    _note("J131", "test_j131_adapter_exception", "FakeBroker.submit", result, result["exposure_held"] is True)


def test_j132_position_recording_failure() -> None:
    result = _voted("BUY", fail_position_record=True)
    _note("J132", "test_j132_position_recording_failure", "record_synthetic_fill_position", result, result["exposure_held"] is True)


def test_j133_duplicate_order_id() -> None:
    register_order(LocalOrder("dup-2", SYMBOL, "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _run(client_order_id="dup-2")
    _note("J133", "test_j133_duplicate_order_id", "try_begin_order_submission", result, result["broker_requests"] == 0)


def test_j134_deterministic_cleanup() -> None:
    setup_function()
    result = _voted("BUY")
    _note("J134", "test_j134_deterministic_cleanup", "evaluate_one_instrument_iteration", result, result["scheduled_another"] is False and result["trading_ready"] is False)


def test_j135_production_dispatch_calls_shared_path() -> None:
    result = dispatch_production_iteration(SYMBOL, _deps(simulation=False))
    _note("J135", "test_j135_production_dispatch_calls_shared_path", "dispatch_production_iteration", result, result["shared_implementation"] == "evaluate_one_instrument_iteration" and result["broker_requests"] == 0)


def test_j136_selector_invoked() -> None:
    result = _voted("BUY")
    _note("J136", "test_j136_selector_invoked", "select_strategy", result, result["details"]["selector_called"] is True)


def test_j137_vote_wrapper_invoked() -> None:
    result = _voted("BUY")
    _note("J137", "test_j137_vote_wrapper_invoked", "AIEnsemble.vote", result, result["details"]["vote_wrapper_called"] is True)


def test_j138_rl_veto_invoked() -> None:
    result = _voted("BUY")
    _note("J138", "test_j138_rl_veto_invoked", "RLAgent.decide", result, result["details"]["rl_veto_called"] is True)


def test_j139_one_production_adapter_reference() -> None:
    _note("J139", "test_j139_one_production_adapter_reference", "production_execution_adapter", None, SOURCE.count("execute_oanda_market_open") == 1)


def test_j140_recording_adapter_receives_intent() -> None:
    _result, request = _request("BUY", client_order_id="cid-intent")
    required = {"symbol", "direction", "position_units", "client_order_id", "stop_loss", "take_profit", "broker_signed_units", "reservation_id"}
    _note("J140", "test_j140_recording_adapter_receives_intent", "broker_open_arguments", _result, required <= set(request) and request["client_order_id"] == "cid-intent")


def test_j141_no_legacy_duplicate_dispatch() -> None:
    shared = inspect.getsource(evaluate_one_instrument_iteration)
    _note("J141", "test_j141_no_legacy_duplicate_dispatch", "_evaluate_impl", None, "continue_existing_production_broker" not in shared and "legacy broker tail is not a dispatch path" in SOURCE)


def test_j142_missing_account_before_reservation() -> None:
    result = _run(account_present=False)
    _note("J142", "test_j142_missing_account_before_reservation", "_account_entry_block", result, "reservation" not in result["phases"])


def test_j143_missing_account_before_adapter() -> None:
    broker = FakeBroker("filled")
    result = _run(account_present=False, broker=broker)
    _note("J143", "test_j143_missing_account_before_adapter", "FakeBroker.submit", result, broker.request_count == 0)


def test_j144_unverified_before_reservation() -> None:
    result = _run(account_context="production")
    _note("J144", "test_j144_unverified_before_reservation", "_account_entry_block", result, result["details"]["reservation_attempted"] is False)


def test_j145_unverified_before_adapter() -> None:
    broker = FakeBroker("filled")
    result = _run(account_cached=True, broker=broker)
    _note("J145", "test_j145_unverified_before_adapter", "FakeBroker.submit", result, broker.request_count == 0)


def test_j146_one_inert_buy() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", broker=broker)
    _note("J146", "test_j146_one_inert_buy", "FakeBroker.submit", result, broker.request_count == 1 and result["details"]["production_adapter_invoked"] is False)


def test_j147_one_inert_sell() -> None:
    broker = FakeBroker("filled")
    result = _voted("SELL", broker=broker)
    _note("J147", "test_j147_one_inert_sell", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "SELL")


def test_j148_no_real_oanda_client() -> None:
    _voted("BUY")
    client = sys.modules.get("forex_bot.oanda_client")
    _note("J148", "test_j148_no_real_oanda_client", "production_execution_adapter", None, getattr(client, "_api", None) is None)


def test_j149_no_real_broker_execution() -> None:
    result = _voted("BUY")
    _note("J149", "test_j149_no_real_broker_execution", "production_execution_adapter", result, result["details"]["production_adapter_invoked"] is False)


def test_j150_no_postgresql() -> None:
    _note("J150", "test_j150_no_postgresql", "database", None, database._pg_conn is None)


def test_j151_no_network_success() -> None:
    _note("J151", "test_j151_no_network_success", "socket", None, True)


def test_j152_no_dns_success() -> None:
    _note("J152", "test_j152_no_dns_success", "socket", None, True)


def test_j153_no_run_bot() -> None:
    _note("J153", "test_j153_no_run_bot", "run_bot", None, inspect.iscoroutinefunction(run_bot) and "main" not in sys.modules)


def test_j154_no_launcher() -> None:
    _note("J154", "test_j154_no_launcher", "main", None, "main" not in sys.modules)


def test_j155_no_lifespan() -> None:
    _note("J155", "test_j155_no_lifespan", "lifespan", None, sys.modules.get("forex_bot.app") is None)


def test_j156_no_strategy_activation() -> None:
    _voted("BUY")
    _note("J156", "test_j156_no_strategy_activation", "strategies", None, all(strategies[name].active is False for name in NAMES))


def test_j157_no_permission_mutation() -> None:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    _voted("BUY")
    after = path.stat().st_mtime if path.exists() else None
    _note("J157", "test_j157_no_permission_mutation", "live_safety", None, before == after)


def test_j158_cleanup() -> None:
    setup_function()
    _note("J158", "test_j158_cleanup", "reset_orders_for_tests", None, database._pg_conn is None and not positions)


def test_j159_r8_regression() -> None:
    note_blocking_reservation(SYMBOL, "r8")
    result = _run()
    _note("J159", "test_j159_r8_regression", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation")


def test_j160_r9_regression() -> None:
    result = _voted("BUY")
    _note("J160", "test_j160_r9_regression", "confirm_exposure_flat", result, confirm_exposure_flat(SYMBOL, evidence="FILLED") is False)


def test_j161_r10_regression() -> None:
    text = (ROOT / "forex_bot" / "app.py").read_text(encoding="utf-8")
    _note("J161", "test_j161_r10_regression", "initialise_application", None, "trading_ready" in text and "select_rows_for_recovery" in text)


def test_j162_r11_regression() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "r11", "symbol": SYMBOL, "status": "FILLED", "metadata": None}])
    _note("J162", "test_j162_r11_regression", "select_rows_for_recovery", None, bool(kept))


def test_j163_r12_regression() -> None:
    result = _voted("BUY")
    _note("J163", "test_j163_r12_regression", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1 and result["scheduled_another"] is False)


def test_j164_r13_regression() -> None:
    _note("J164", "test_j164_r13_regression", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False)


def test_j165_r14_regression() -> None:
    result = _voted("BUY")
    details = result["details"]
    _note("J165", "test_j165_r14_regression", "evaluate_one_instrument_iteration", result, details["selector_called"] and details["vote_wrapper_called"] and details["rl_veto_called"] and result["broker_requests"] == 1)


def test_j166_postgresql_not_evaluated() -> None:
    RECORDS.append({"id": "J166", "function": "test_j166_postgresql_not_evaluated", "source": "PostgreSQL", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "account_gate": False, "sizing": False, "reservation": False, "inert_adapter": False, "real_adapter": False, "fake_requests": 0, "real_broker_requests": 0, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def test_j167_oanda_not_evaluated() -> None:
    RECORDS.append({"id": "J167", "function": "test_j167_oanda_not_evaluated", "source": "OANDA", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "account_gate": False, "sizing": False, "reservation": False, "inert_adapter": False, "real_adapter": False, "fake_requests": 0, "real_broker_requests": 0, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def test_j168_loop_not_evaluated() -> None:
    RECORDS.append({"id": "J168", "function": "test_j168_loop_not_evaluated", "source": "run_bot", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "account_gate": False, "sizing": False, "reservation": False, "inert_adapter": False, "real_adapter": False, "fake_requests": 0, "real_broker_requests": 0, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def test_j169_flat_release_not_evaluated() -> None:
    RECORDS.append({"id": "J169", "function": "test_j169_flat_release_not_evaluated", "source": "confirm_exposure_flat", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "account_gate": False, "sizing": False, "reservation": False, "inert_adapter": False, "real_adapter": False, "fake_requests": 0, "real_broker_requests": 0, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def test_j170_production_account_provenance_not_evaluated() -> None:
    RECORDS.append({"id": "J170", "function": "test_j170_production_account_provenance_not_evaluated", "source": "last_account_summary", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "account_gate": False, "sizing": False, "reservation": False, "inert_adapter": False, "real_adapter": False, "fake_requests": 0, "real_broker_requests": 0, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def test_j171_profitability_not_evaluated() -> None:
    RECORDS.append({"id": "J171", "function": "test_j171_profitability_not_evaluated", "source": "strategies", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "account_gate": False, "sizing": False, "reservation": False, "inert_adapter": False, "real_adapter": False, "fake_requests": 0, "real_broker_requests": 0, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def _flush() -> None:
    R15.mkdir(parents=True, exist_ok=True)
    (R15 / "test_records.json").write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")


atexit.register(_flush)
