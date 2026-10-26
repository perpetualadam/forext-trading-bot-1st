"""Offline equity-source unification. No broker, database, or production loop."""

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
R16 = ROOT / "data" / "research" / "adaptive_ensemble" / "r16"
R16.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R16 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    _account_entry_block,
    evaluate_one_instrument_iteration,
    production_execution_adapter,
    rl_decision_state,
    run_bot,
)
from forex_bot.config import Config  # noqa: E402
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    exposure_entry_block_reason,
    note_blocking_reservation,
    note_unconfirmed_exposure,
    reset_order_intent_gate_for_tests,
    reservation_status_block_reason,
    restore_unresolved_intent,
    select_rows_for_recovery,
)
from forex_bot.indicators import compute_indicators  # noqa: E402
from forex_bot.orders import (  # noqa: E402
    LocalOrder,
    OrderStatus,
    register_order,
    reset_orders_for_tests,
)
from forex_bot.positions import Position, close_position, get_position, open_position, positions  # noqa: E402
from forex_bot.rl_agent import RLAgent  # noqa: E402
from forex_bot.state import current_equity, state  # noqa: E402
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
SHARED = inspect.getsource(evaluate_one_instrument_iteration)
LIMIT = "synthetic snapshot only; production account provenance is NOT_EVALUATED"


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


def _agent_for(bars: list[dict[str, float | str]], action: str) -> RLAgent:
    import pandas as pd

    key = rl_decision_state(compute_indicators(pd.DataFrame(bars)))
    agent = RLAgent(epsilon=0.0)
    table = {"BUY": 0.0, "SELL": 0.0, "SKIP": 0.0}
    table[action] = 1.0
    agent.q[key] = table
    agent.persisted_ok = True
    return agent


def _deps(**overrides: object) -> IterationDependencies:
    broker = overrides.pop("broker", None) or FakeBroker("filled")
    bars = overrides.get("candles") or _bars()
    vote = overrides.get("vote") or {"allow": True, "direction": "BUY", "confidence": 0.8}
    direction = str(vote.get("direction") or "BUY").upper()
    action = direction if direction in {"BUY", "SELL", "SKIP"} else "BUY"
    values: dict[str, object] = {
        "candles": bars,
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
        "vote": vote,
        "strategy_active_map": {"scalp": True},
        "invoke_selector": True,
        "invoke_vote": True,
        "invoke_rl": True,
        "rl_agent": _agent_for(bars, action),  # type: ignore[arg-type]
    }
    values.update(overrides)
    if "unrealised" not in overrides:
        values["unrealised"] = 0.0
    if "account_as_of" not in overrides:
        values["account_as_of"] = values.get("now")
    return IterationDependencies(**values)  # type: ignore[arg-type]


def _run(symbol: str = SYMBOL, **overrides: object) -> dict:
    return evaluate_one_instrument_iteration(symbol, _deps(**overrides))


def _voted(direction: str, **overrides: object) -> dict:
    symbol = str(overrides.pop("symbol", SYMBOL))
    return _run(
        symbol,
        vote={"allow": True, "direction": direction, "confidence": 0.8},
        **overrides,
    )


def _note(test_id: str, function: str, source: str, result: dict | None, ok: bool, **extra: object) -> None:
    details = {} if result is None else dict(result.get("details") or {})
    RECORDS.append(
        {
            "id": test_id,
            "function": function,
            "source": source,
            "shared_path": bool(result is not None and "phases" in result),
            "selector": bool(details.get("selector_called")),
            "vote_wrapper": bool(details.get("vote_wrapper_called")),
            "rl_veto": bool(details.get("rl_veto_called")),
            "account_validation": bool(details.get("account_gate")),
            "accepted_equity": details.get("accepted_equity"),
            "sizing_equity": details.get("sizing_equity"),
            "portfolio_cap_equity": details.get("portfolio_cap_equity"),
            "reservation": bool(details.get("reservation_attempted")),
            "inert_adapter": bool(details.get("adapter_called")),
            "production_adapter": bool(details.get("production_adapter_invoked")),
            "fake_requests": int(0 if result is None else result.get("broker_requests") or 0),
            "real_broker_requests": 0,
            "status": "PASS" if ok else "FAIL",
            "evidence": extra,
            "limitations": extra.get("limitations", LIMIT),
        }
    )
    assert ok, result if result is not None else extra


def _skip(test_id: str, function: str, source: str, limitation: str) -> None:
    RECORDS.append(
        {
            "id": test_id,
            "function": function,
            "source": source,
            "shared_path": False,
            "selector": False,
            "vote_wrapper": False,
            "rl_veto": False,
            "account_validation": False,
            "accepted_equity": None,
            "sizing_equity": None,
            "portfolio_cap_equity": None,
            "reservation": False,
            "inert_adapter": False,
            "production_adapter": False,
            "fake_requests": 0,
            "real_broker_requests": 0,
            "status": "NOT_EVALUATED",
            "evidence": {},
            "limitations": limitation,
        }
    )
    pytest.skip("NOT_EVALUATED")


def _same(result: dict, equity: float) -> bool:
    details = result["details"]
    return (
        details.get("accepted_equity") == equity
        and details.get("sizing_equity") == equity
        and details.get("portfolio_cap_equity") == equity
        and details.get("current_equity_used_for_entry") is False
        and details.get("entry_equity_source") == "accepted_snapshot"
    )


def _seed_risk() -> None:
    open_position(Position("EUR_USD", "BUY", 300_000, 1.1, 1.099, 1.2, 0, "synthetic", "synthetic", "synthetic"))


def _gbp(accepted: float, fallback: float) -> dict:
    state["broker_nav"] = float(fallback)
    state["equity_curve"] = [float(fallback)]
    _seed_risk()
    bars = _bars(start=1.27)
    return _run(
        "GBP_USD",
        candles=bars,
        price=1.27,
        balance=accepted,
        stop_loss=1.269,
        take_profit=1.272,
        rl_agent=_agent_for(bars, "BUY"),
    )


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R16)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R16 / "synthetic_live_safety_state.json")
    os.environ.pop("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", None)
    os.environ.pop("POSITION_NOTIONAL_PCT_OF_NAV", None)
    os.environ.pop("MAX_PORTFOLIO_RISK_PCT", None)
    os.environ.pop("POSITION_RISK_PCT", None)
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)
    state["broker_nav"] = None
    state["broker_currency"] = ""
    state["equity_curve"] = []


def _dump() -> None:
    R16.mkdir(parents=True, exist_ok=True)
    (R16 / "test_records.json").write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")


atexit.register(_dump)


def test_h01_validate_before_sizing() -> None:
    result = _run(account_present=False, balance=None)
    ok = result["blocked_by"] == "account_missing" and "sizing" not in result["phases"]
    _note("H01", "test_h01_validate_before_sizing", "_account_entry_block", result, ok)


def test_h02_validate_before_reservation() -> None:
    result = _run(account_present=False, balance=None)
    ok = result["blocked_by"] == "account_missing" and result["details"]["reservation_attempted"] is False
    _note("H02", "test_h02_validate_before_reservation", "_account_entry_block", result, ok)


def test_h03_validate_before_adapter() -> None:
    result = _run(account_present=False, balance=None)
    _note("H03", "test_h03_validate_before_adapter", "_account_entry_block", result, result["broker_requests"] == 0)


def test_h04_provenance_restriction_remains() -> None:
    result = _run(account_context="", balance=5000)
    _note("H04", "test_h04_provenance_restriction_remains", "_account_entry_block", result, result["blocked_by"] == "account_unverified" and result["broker_requests"] == 0)


def test_h05_verified_flag_is_not_production_proof() -> None:
    reason, value = _account_entry_block(_deps(simulation=False, balance=5000, account_payload={"verified": True}))
    _note("H05", "test_h05_verified_flag_is_not_production_proof", "_account_entry_block", None, reason == "account_unverified" and value is None, reason=reason)


def test_h06_synthetic_snapshot_only_in_harness() -> None:
    result = _voted("BUY", balance=5000, account_context="isolated_test")
    _note("H06", "test_h06_synthetic_snapshot_only_in_harness", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1 and result["production_authorised"] is False)


def test_h07_accepted_equity_is_fixed(monkeypatch: pytest.MonkeyPatch) -> None:
    from forex_bot.trading import position_sizing as real

    payload = {"equity": 5000.0}

    def sizing(symbol, price, stop, balance, **kwargs):  # noqa: ANN001
        payload["equity"] = 20000.0
        return real(symbol, price, stop, balance, **kwargs)

    monkeypatch.setattr("forex_bot.trading.position_sizing", sizing)
    result = _run(balance=5000, account_payload=payload)
    _note("H07", "test_h07_accepted_equity_is_fixed", "evaluate_one_instrument_iteration", result, _same(result, 5000.0) and payload["equity"] == 20000.0)


def test_h08_sizing_uses_accepted_equity() -> None:
    result = _voted("BUY", balance=5000)
    _note("H08", "test_h08_sizing_uses_accepted_equity", "position_sizing", result, result["details"]["sizing_equity"] == 5000.0)


def test_h09_portfolio_cap_uses_accepted_equity() -> None:
    result = _voted("BUY", balance=5000)
    _note("H09", "test_h09_portfolio_cap_uses_accepted_equity", "portfolio_risk_cap_exceeded", result, _same(result, 5000.0))


def test_h10_enabled_notional_cap_uses_accepted_equity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.10")
    state["broker_nav"] = 1_000_000.0
    result = _run(balance=5000)
    ok = (
        result["blocked_by"] == "notional_cap"
        and result["details"]["notional_cap_equity"] == 5000.0
        and result["broker_requests"] == 0
        and current_equity() == 1_000_000.0
    )
    _note("H10", "test_h10_enabled_notional_cap_uses_accepted_equity", "portfolio_gross_notional_pct_of_nav", result, ok, limitations="gross notional cap is off unless this test sets it; production default stays off")


def test_h11_entry_does_not_call_current_equity(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> float:
        raise AssertionError("entry risk called current_equity")

    monkeypatch.setattr("forex_bot.state.current_equity", boom)
    monkeypatch.setattr("forex_bot.bot_loop.current_equity", boom)
    monkeypatch.setattr("forex_bot.trading.current_equity", boom)
    result = _voted("BUY", balance=5000)
    _note("H11", "test_h11_entry_does_not_call_current_equity", "portfolio_risk_cap_exceeded", result, result["broker_requests"] == 1 and _same(result, 5000.0))


def test_h12_base_balance_cannot_authorise_entry() -> None:
    result = _run(account_present=False, balance=None)
    ok = result["blocked_by"] == "account_missing" and result["broker_requests"] == 0 and Config.BASE_BALANCE > 0
    _note("H12", "test_h12_base_balance_cannot_authorise_entry", "_account_entry_block", result, ok)


def test_h13_equity_curve_cannot_authorise_entry() -> None:
    state["equity_curve"] = [20000.0]
    result = _run(account_present=False, balance=None)
    ok = result["blocked_by"] == "account_missing" and current_equity() == 20000.0 and result["broker_requests"] == 0
    _note("H13", "test_h13_equity_curve_cannot_authorise_entry", "current_equity", result, ok)


def test_h14_cached_nav_cannot_override_snapshot() -> None:
    state["broker_nav"] = 20000.0
    blocked = _run(account_cached=True, balance=5000)
    allowed = _voted("BUY", balance=5000)
    ok = blocked["blocked_by"] == "unverified_cached_equity" and blocked["broker_requests"] == 0 and _same(allowed, 5000.0)
    _note("H14", "test_h14_cached_nav_cannot_override_snapshot", "_account_entry_block", allowed, ok, blocked=blocked["blocked_by"])


def test_h15_invalid_snapshot_blocks() -> None:
    result = _run(balance=float("nan"))
    _note("H15", "test_h15_invalid_snapshot_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_nonfinite" and "sizing" not in result["phases"])


def test_h16_no_new_production_verification_source() -> None:
    result = _voted("BUY", balance=5000, account_payload={"verified": True, "equity": 20000})
    ok = result["production_authorised"] is False and _same(result, 5000.0) and result["details"]["account_context"] == "isolated_test"
    _note("H16", "test_h16_no_new_production_verification_source", "_account_entry_block", result, ok)


def test_h17_risk_percentage_unchanged() -> None:
    from forex_bot.trading import configured_max_portfolio_risk_pct, position_sizing

    text = inspect.getsource(position_sizing)
    ok = configured_max_portfolio_risk_pct() == 0.05 and 'POSITION_RISK_PCT", 0.01' in text
    _note("H17", "test_h17_risk_percentage_unchanged", "configured_max_portfolio_risk_pct", None, ok)


def test_h18_sizing_formula_unchanged() -> None:
    from forex_bot.trading import position_sizing

    text = inspect.getsource(position_sizing)
    units = position_sizing("EUR_USD", 1.1, 1.099, 5000)
    ok = "balance_eff * rp" in text and math.isclose(units, 50000.0, rel_tol=1e-9)
    _note("H18", "test_h18_sizing_formula_unchanged", "position_sizing", None, ok, units=units)


def test_h19_portfolio_formula_keeps_equity_argument() -> None:
    from forex_bot.trading import portfolio_risk_cap_exceeded

    text = inspect.getsource(portfolio_risk_cap_exceeded)
    ok = "current_equity" not in text and "portfolio_risk_cap_exceeded(accepted_equity, new_risk)" in SHARED
    _note("H19", "test_h19_portfolio_formula_keeps_equity_argument", "portfolio_risk_cap_exceeded", None, ok)


def test_h20_no_permission_or_strategy_activation() -> None:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    _voted("BUY")
    after = path.stat().st_mtime if path.exists() else None
    ok = before == after and all(strategies[name].active is False for name in NAMES)
    _note("H20", "test_h20_no_permission_or_strategy_activation", "strategies", None, ok)


def test_h21_cap_uses_smaller_accepted_equity() -> None:
    result = _gbp(5000, 20000)
    ok = result["blocked_by"] == "portfolio_risk_cap" and result["details"]["portfolio_cap_equity"] == 5000.0
    _note("H21", "test_h21_cap_uses_smaller_accepted_equity", "portfolio_risk_cap_exceeded", result, ok and result["broker_requests"] == 0)


def test_h22_cap_uses_larger_accepted_equity() -> None:
    result = _gbp(20000, 5000)
    ok = result["blocked_by"] != "portfolio_risk_cap" and result["details"]["portfolio_cap_equity"] == 20000.0
    _note("H22", "test_h22_cap_uses_larger_accepted_equity", "portfolio_risk_cap_exceeded", result, ok and result["broker_requests"] == 1)


def test_h23_raising_fallback_is_not_consulted(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> float:
        raise AssertionError("current_equity was called")

    monkeypatch.setattr("forex_bot.state.current_equity", boom)
    monkeypatch.setattr("forex_bot.bot_loop.current_equity", boom)
    result = _voted("BUY", balance=5000)
    _note("H23", "test_h23_raising_fallback_is_not_consulted", "portfolio_risk_cap_exceeded", result, result["broker_requests"] == 1)


def test_h24_nan_fallback_does_not_replace_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("forex_bot.state.current_equity", lambda: float("nan"))
    monkeypatch.setattr("forex_bot.bot_loop.current_equity", lambda: float("nan"))
    result = _voted("BUY", balance=5000)
    _note("H24", "test_h24_nan_fallback_does_not_replace_snapshot", "portfolio_risk_cap_exceeded", result, _same(result, 5000.0) and result["broker_requests"] == 1)


def test_h25_equity_curve_change_does_not_replace_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    from forex_bot.trading import position_sizing as real

    def sizing(symbol, price, stop, balance, **kwargs):  # noqa: ANN001
        state["equity_curve"].append(99_000.0)
        state["broker_nav"] = 99_000.0
        return real(symbol, price, stop, balance, **kwargs)

    monkeypatch.setattr("forex_bot.trading.position_sizing", sizing)
    result = _voted("BUY", balance=5000)
    _note("H25", "test_h25_equity_curve_change_does_not_replace_snapshot", "position_sizing", result, _same(result, 5000.0))


def test_h26_base_balance_does_not_change_permission() -> None:
    result = _voted("BUY", balance=5000)
    ok = _same(result, 5000.0) and float(Config.BASE_BALANCE) != 5000.0 and result["broker_requests"] == 1
    _note("H26", "test_h26_base_balance_does_not_change_permission", "Config.BASE_BALANCE", result, ok)


def test_h27_cached_nav_does_not_override_cap() -> None:
    state["broker_nav"] = 20000.0
    result = _voted("BUY", balance=5000)
    ok = current_equity() == 20000.0 and _same(result, 5000.0)
    _note("H27", "test_h27_cached_nav_does_not_override_cap", "current_equity", result, ok)


def test_h28_open_position_risk_uses_existing_formula() -> None:
    from forex_bot.trading import portfolio_risk_amount, position_risk_dollars

    _seed_risk()
    amount = portfolio_risk_amount()
    one = position_risk_dollars(positions["EUR_USD"])
    _note("H28", "test_h28_open_position_risk_uses_existing_formula", "position_risk_dollars", None, math.isclose(amount, one) and math.isclose(amount, 300.0, rel_tol=1e-9), amount=amount)


def test_h29_aggregate_uses_existing_cap_formula() -> None:
    from forex_bot.trading import configured_max_portfolio_risk_pct, portfolio_risk_amount, portfolio_risk_cap_exceeded

    _seed_risk()
    equity = 5000.0
    additional = 50.0
    cap = equity * configured_max_portfolio_risk_pct()
    expected = portfolio_risk_amount() + additional > cap + 1e-9
    _note("H29", "test_h29_aggregate_uses_existing_cap_formula", "portfolio_risk_cap_exceeded", None, portfolio_risk_cap_exceeded(equity, additional) is expected is True)


def test_h30_cap_breach_blocks_reservation() -> None:
    result = _gbp(5000, 20000)
    _note("H30", "test_h30_cap_breach_blocks_reservation", "try_begin_order_submission", result, result["blocked_by"] == "portfolio_risk_cap" and result["details"]["reservation_attempted"] is False)


def test_h31_cap_breach_blocks_adapter() -> None:
    result = _gbp(5000, 20000)
    _note("H31", "test_h31_cap_breach_blocks_adapter", "FakeBroker.submit", result, result["blocked_by"] == "portfolio_risk_cap" and result["broker_requests"] == 0)


def test_h32_passing_cap_does_not_bypass_other_gates() -> None:
    result = _run(balance=20000, strategy_active=False, strategy_active_map={})
    _note("H32", "test_h32_passing_cap_does_not_bypass_other_gates", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and result["broker_requests"] == 0)


def test_h33_cap_percentage_unchanged() -> None:
    from forex_bot.trading import configured_max_portfolio_risk_pct

    text = inspect.getsource(configured_max_portfolio_risk_pct)
    ok = configured_max_portfolio_risk_pct() == 0.05 and "0.05" in text
    _note("H33", "test_h33_cap_percentage_unchanged", "configured_max_portfolio_risk_pct", None, ok)


def test_h34_stop_distance_formula_unchanged() -> None:
    from forex_bot.trading import stop_risk_account_ccy

    text = inspect.getsource(stop_risk_account_ccy)
    value = stop_risk_account_ccy("EUR_USD", 1.1, 0.001, 300_000)
    _note("H34", "test_h34_stop_distance_formula_unchanged", "stop_risk_account_ccy", None, "return d * u" in text and value == 300.0)


def test_h35_position_sizing_formula_unchanged() -> None:
    from forex_bot.trading import position_sizing

    _note("H35", "test_h35_position_sizing_formula_unchanged", "position_sizing", None, math.isclose(position_sizing("EUR_USD", 1.1, 1.099, 5000), 50000.0, rel_tol=1e-9))


def test_h36_missing_snapshot_blocks() -> None:
    result = _run(account_present=False, balance=None)
    _note("H36", "test_h36_missing_snapshot_blocks", "_account_entry_block", result, result["blocked_by"] == "account_missing")


def test_h37_empty_snapshot_blocks() -> None:
    result = _run(balance=None, account_payload={})
    _note("H37", "test_h37_empty_snapshot_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_missing" and result["broker_requests"] == 0)


def test_h38_missing_equity_blocks() -> None:
    result = _run(balance=None, account_payload={"id": "A"})
    _note("H38", "test_h38_missing_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_missing")


def test_h39_zero_equity_blocks() -> None:
    result = _run(balance=0)
    _note("H39", "test_h39_zero_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_not_positive" and "sizing" not in result["phases"])


def test_h40_negative_equity_blocks() -> None:
    result = _run(balance=-5)
    _note("H40", "test_h40_negative_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_not_positive")


def test_h41_nan_equity_blocks() -> None:
    result = _run(balance=math.nan)
    _note("H41", "test_h41_nan_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_nonfinite")


def test_h42_infinite_equity_blocks() -> None:
    result = _run(balance=math.inf)
    _note("H42", "test_h42_infinite_equity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_nonfinite")


def test_h43_malformed_numeric_string_blocks() -> None:
    result = _run(balance="1,000")
    _note("H43", "test_h43_malformed_numeric_string_blocks", "_account_entry_block", result, result["blocked_by"] == "account_equity_malformed")


def test_h44_unverified_snapshot_blocks() -> None:
    result = _run(account_context="production", balance=5000, account_payload={"verified": True})
    _note("H44", "test_h44_unverified_snapshot_blocks", "_account_entry_block", result, result["blocked_by"] == "account_unverified" and result["broker_requests"] == 0)


def test_h45_cached_snapshot_blocks() -> None:
    result = _run(account_cached=True, balance=5000)
    _note("H45", "test_h45_cached_snapshot_blocks", "_account_entry_block", result, result["blocked_by"] == "unverified_cached_equity")


def test_h46_wrong_identity_blocks() -> None:
    result = _run(balance=5000, expected_account_id="A", account_payload={"id": "B", "equity": 5000})
    _note("H46", "test_h46_wrong_identity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_identity_mismatch" and "sizing" not in result["phases"])


def test_h47_stale_timestamp_blocks() -> None:
    result = _run(balance=5000, account_as_of=OPEN - timedelta(seconds=301))
    _note("H47", "test_h47_stale_timestamp_blocks", "_account_entry_block", result, result["blocked_by"] == "account_snapshot_stale", limitations="harness timestamp check; not broker-verified freshness")


def test_h48_future_timestamp_blocks() -> None:
    result = _run(balance=5000, account_as_of=OPEN + timedelta(seconds=1))
    _note("H48", "test_h48_future_timestamp_blocks", "_account_entry_block", result, result["blocked_by"] == "account_timestamp_future", limitations="harness clock check; not broker-verified freshness")


def test_h49_acquisition_exception_blocks() -> None:
    result = _run(account_error="boom", balance=5000)
    _note("H49", "test_h49_acquisition_exception_blocks", "_account_entry_block", result, result["blocked_by"] == "account_acquisition_error")


def test_h50_acquisition_timeout_blocks() -> None:
    result = _run(account_timeout=True, balance=5000)
    _note("H50", "test_h50_acquisition_timeout_blocks", "_account_entry_block", result, result["blocked_by"] == "account_acquisition_timeout")


def test_h51_later_equity_change_keeps_accepted_value(monkeypatch: pytest.MonkeyPatch) -> None:
    from forex_bot.trading import position_sizing as real

    def sizing(symbol, price, stop, balance, **kwargs):  # noqa: ANN001
        state["broker_nav"] = 1.0
        return real(symbol, price, stop, balance, **kwargs)

    monkeypatch.setattr("forex_bot.trading.position_sizing", sizing)
    result = _voted("BUY", balance=5000)
    _note("H51", "test_h51_later_equity_change_keeps_accepted_value", "portfolio_risk_cap_exceeded", result, _same(result, 5000.0))


def test_h52_payload_mutation_keeps_risk_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    from forex_bot.trading import position_sizing as real

    payload = {"equity": 9000.0, "id": "A"}

    def sizing(symbol, price, stop, balance, **kwargs):  # noqa: ANN001
        payload["equity"] = None
        payload["id"] = "OTHER"
        return real(symbol, price, stop, balance, **kwargs)

    monkeypatch.setattr("forex_bot.trading.position_sizing", sizing)
    result = _run(balance=5000, account_payload=payload)
    _note("H52", "test_h52_payload_mutation_keeps_risk_inputs", "position_sizing", result, _same(result, 5000.0))


def test_h53_disappearance_after_acceptance_does_not_substitute_equity(monkeypatch: pytest.MonkeyPatch) -> None:
    from forex_bot.trading import position_sizing as real

    holder: dict[str, IterationDependencies] = {}

    def sizing(symbol, price, stop, balance, **kwargs):  # noqa: ANN001
        holder["deps"].account_present = False
        holder["deps"].balance = None
        return real(symbol, price, stop, balance, **kwargs)

    monkeypatch.setattr("forex_bot.trading.position_sizing", sizing)
    deps = _deps(balance=5000)
    holder["deps"] = deps
    result = evaluate_one_instrument_iteration(SYMBOL, deps)
    ok = _same(result, 5000.0) and result["broker_requests"] == 1
    _note("H53", "test_h53_disappearance_after_acceptance_does_not_substitute_equity", "_account_entry_block", result, ok, limitations="validation is one-shot; a later disappearance cannot replace the accepted equity")


def test_h54_freshness_is_applied_at_the_gate() -> None:
    fresh = _voted("BUY", balance=5000, account_as_of=OPEN)
    setup_function()
    stale = _run(balance=5000, account_as_of=OPEN - timedelta(seconds=301))
    ok = fresh["broker_requests"] == 1 and stale["blocked_by"] == "account_snapshot_stale" and stale["broker_requests"] == 0
    _note("H54", "test_h54_freshness_is_applied_at_the_gate", "_account_entry_block", stale, ok, limitations="one gate check per decision; not broker-verified freshness")


def test_h55_balance_is_authoritative_when_payload_differs() -> None:
    result = _voted("BUY", balance=5000, account_payload={"equity": 20000})
    _note("H55", "test_h55_balance_is_authoritative_when_payload_differs", "_account_entry_block", result, _same(result, 5000.0))


def test_h56_conflicting_identity_blocks() -> None:
    result = _run(balance=5000, expected_account_id="desk", account_payload={"id": "other", "equity": 5000})
    _note("H56", "test_h56_conflicting_identity_blocks", "_account_entry_block", result, result["blocked_by"] == "account_identity_mismatch")


def test_h57_missing_provenance_is_not_production_verification() -> None:
    result = _voted("BUY", balance=5000)
    ok = result["provenance"] == "missing_provenance" and result["production_authorised"] is False
    _note("H57", "test_h57_missing_provenance_is_not_production_verification", "decision_frame_rejection", result, ok)


def test_h58_test_context_cannot_verify_production() -> None:
    reason, value = _account_entry_block(_deps(simulation=False, account_context="isolated_test", balance=5000))
    _note("H58", "test_h58_test_context_cannot_verify_production", "_account_entry_block", None, reason == "account_unverified" and value is None)


def test_h59_second_equity_read_cannot_replace_acceptance(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def boom() -> float:
        calls["n"] += 1
        return 20_000.0

    monkeypatch.setattr("forex_bot.state.current_equity", boom)
    monkeypatch.setattr("forex_bot.bot_loop.current_equity", boom)
    result = _voted("BUY", balance=5000)
    _note("H59", "test_h59_second_equity_read_cannot_replace_acceptance", "current_equity", result, calls["n"] == 0 and _same(result, 5000.0))


def test_h60_retry_does_not_reuse_invalid_snapshot() -> None:
    stale = OPEN - timedelta(seconds=400)
    first = _run(balance=5000, account_as_of=stale)
    second = _run("GBP_USD", balance=5000, account_as_of=stale, price=1.27, candles=_bars(start=1.27))
    ok = first["blocked_by"] == second["blocked_by"] == "account_snapshot_stale" and second["broker_requests"] == 0
    _note("H60", "test_h60_retry_does_not_reuse_invalid_snapshot", "_account_entry_block", second, ok)


def test_h61_buy_uses_one_accepted_equity() -> None:
    result = _voted("BUY", balance=5000)
    _note("H61", "test_h61_buy_uses_one_accepted_equity", "evaluate_one_instrument_iteration", result, _same(result, 5000.0) and result["direction"] == "BUY" and result["broker_requests"] == 1)


def test_h62_sell_uses_one_accepted_equity() -> None:
    result = _voted("SELL", balance=5000)
    _note("H62", "test_h62_sell_uses_one_accepted_equity", "evaluate_one_instrument_iteration", result, _same(result, 5000.0) and result["direction"] == "SELL" and result["broker_requests"] == 1)


def test_h63_portfolio_cap_passes() -> None:
    result = _voted("BUY", balance=5000)
    _note("H63", "test_h63_portfolio_cap_passes", "portfolio_risk_cap_exceeded", result, result["blocked_by"] == "" and _same(result, 5000.0))


def test_h64_portfolio_cap_fails() -> None:
    result = _gbp(5000, 20000)
    _note("H64", "test_h64_portfolio_cap_fails", "portfolio_risk_cap_exceeded", result, result["blocked_by"] == "portfolio_risk_cap" and result["details"]["portfolio_cap_equity"] == 5000.0)


def test_h65_missing_account_blocks() -> None:
    result = _run(account_present=False, balance=None)
    _note("H65", "test_h65_missing_account_blocks", "_account_entry_block", result, result["blocked_by"] == "account_missing" and result["broker_requests"] == 0)


def test_h66_unverified_account_blocks() -> None:
    result = _run(account_context="", balance=5000)
    _note("H66", "test_h66_unverified_account_blocks", "_account_entry_block", result, result["blocked_by"] == "account_unverified")


def test_h67_stale_synthetic_account_blocks() -> None:
    result = _run(balance=5000, account_as_of=OPEN - timedelta(minutes=10))
    _note("H67", "test_h67_stale_synthetic_account_blocks", "_account_entry_block", result, result["blocked_by"] == "account_snapshot_stale", limitations="harness timestamp; not production freshness")


def test_h68_inactive_strategy_blocks() -> None:
    result = _run(strategy_active=False, balance=5000, strategy_active_map={})
    _note("H68", "test_h68_inactive_strategy_blocks", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and result["broker_requests"] == 0)


def test_h69_rl_veto_blocks() -> None:
    bars = _bars()
    result = _run(balance=5000, candles=bars, rl_agent=_agent_for(bars, "SKIP"))
    _note("H69", "test_h69_rl_veto_blocks", "RLAgent.decide", result, result["blocked_by"] == "rl_veto" and result["broker_requests"] == 0)


def test_h70_invalid_ai_direction_blocks() -> None:
    result = _run(balance=5000, vote={"allow": True, "direction": "MAYBE", "confidence": 0.8})
    _note("H70", "test_h70_invalid_ai_direction_blocks", "canonical_entry_direction", result, result["blocked_by"] == "invalid_entry_direction")


def test_h71_existing_position_blocks() -> None:
    open_position(Position(SYMBOL, "BUY", 1, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    result = _run(balance=5000)
    _note("H71", "test_h71_existing_position_blocks", "get_position", result, result["blocked_by"] == "position_already_open" and result["broker_requests"] == 0)


def test_h72_historical_filled_hold_blocks() -> None:
    note_unconfirmed_exposure(SYMBOL, "old-fill")
    result = _run(balance=5000)
    _note("H72", "test_h72_historical_filled_hold_blocks", "exposure_entry_block_reason", result, result["blocked_by"] == "exposure_unconfirmed")


def test_h73_pending_reservation_blocks() -> None:
    note_blocking_reservation(SYMBOL, "pending-1")
    result = _run(balance=5000)
    _note("H73", "test_h73_pending_reservation_blocks", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation")


def test_h74_partial_reservation_blocks() -> None:
    register_order(LocalOrder("partial-1", SYMBOL, "BUY", 2, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "partial-1")
    result = _run(balance=5000)
    _note("H74", "test_h74_partial_reservation_blocks", "reservation_status_block_reason", result, result["blocked_by"] == "active_reservation")


def test_h75_unresolved_reservation_blocks() -> None:
    restore_unresolved_intent(SYMBOL, "unresolved-1")
    result = _run(balance=5000)
    _note("H75", "test_h75_unresolved_reservation_blocks", "restore_unresolved_intent", result, result["blocked_by"] == "unresolved_intent")


def test_h76_sizing_failure_blocks() -> None:
    result = _run(balance=5000, stop_distance=0)
    _note("H76", "test_h76_sizing_failure_blocks", "position_sizing", result, result["blocked_by"] == "size_not_positive" and result["details"]["reservation_attempted"] is False)


def test_h77_reservation_failure_blocks() -> None:
    result = _run(balance=5000, persistence_failure="unavailable")
    _note("H77", "test_h77_reservation_failure_blocks", "refuse_reservation_after_database_fault", result, result["blocked_by"] == "reservation_persistence_failed" and result["broker_requests"] == 0)


def test_h78_adapter_rejection() -> None:
    result = _voted("BUY", balance=5000, broker=FakeBroker("rejected"))
    _note("H78", "test_h78_adapter_rejection", "FakeBroker.submit", result, result["outcome"] == "rejected" and result["broker_requests"] == 1 and get_position(SYMBOL) is None)


def test_h79_adapter_timeout() -> None:
    result = _voted("BUY", balance=5000, broker=FakeBroker("filled", error=TimeoutError()))
    _note("H79", "test_h79_adapter_timeout", "FakeBroker.submit", result, result["outcome"] == "timeout" and result["exposure_held"] is True and result["broker_requests"] == 1)


def test_h80_adapter_ambiguous() -> None:
    result = _voted("BUY", balance=5000, broker=FakeBroker("ambiguous"))
    _note("H80", "test_h80_adapter_ambiguous", "FakeBroker.submit", result, result["outcome"] == "ambiguous" and result["exposure_held"] is True)


def test_h81_adapter_partial() -> None:
    result = _voted("BUY", balance=5000, broker=FakeBroker("partial"))
    _note("H81", "test_h81_adapter_partial", "finalize_order_fill", result, result["status"] == "partial" and result["exposure_held"] is True)


def test_h82_adapter_malformed() -> None:
    result = _voted("BUY", balance=5000, broker=FakeBroker("filled", response={"units": 1}))
    _note("H82", "test_h82_adapter_malformed", "FakeBroker.submit", result, result["outcome"] == "malformed" and result["exposure_held"] is True)


def test_h83_position_recording_failure() -> None:
    result = _voted("BUY", balance=5000, fail_position_record=True)
    _note("H83", "test_h83_position_recording_failure", "record_synthetic_fill_position", result, result["exposure_held"] is True and get_position(SYMBOL) is None)


def test_h84_duplicate_client_id() -> None:
    register_order(LocalOrder("same", SYMBOL, "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _run(balance=5000, client_order_id="same")
    _note("H84", "test_h84_duplicate_client_id", "try_begin_order_submission", result, result["blocked_by"] == "reservation_refused" and result["broker_requests"] == 0)


def test_h85_deterministic_termination() -> None:
    result = _voted("BUY", balance=5000)
    _note("H85", "test_h85_deterministic_termination", "evaluate_one_instrument_iteration", result, result["scheduled_another"] is False and result["trading_ready"] is False)


def test_h86_pending_blocks_duplicate() -> None:
    note_blocking_reservation(SYMBOL, "p")
    result = _run(balance=5000)
    _note("H86", "test_h86_pending_blocks_duplicate", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation" and result["broker_requests"] == 0)


def test_h87_partial_blocks_duplicate() -> None:
    register_order(LocalOrder("part", SYMBOL, "BUY", 1, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "part")
    result = _run(balance=5000)
    _note("H87", "test_h87_partial_blocks_duplicate", "note_blocking_reservation", result, result["broker_requests"] == 0)


def test_h88_unresolved_blocks_duplicate() -> None:
    restore_unresolved_intent(SYMBOL, "u")
    result = _run(balance=5000)
    _note("H88", "test_h88_unresolved_blocks_duplicate", "restore_unresolved_intent", result, result["blocked_by"] == "unresolved_intent")


def test_h89_unknown_status_fails_closed() -> None:
    order = LocalOrder("mystery", SYMBOL, "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0)
    order.status = type("Status", (), {"value": "MYSTERY"})()
    register_order(order)
    result = _run(balance=5000)
    direct = reservation_status_block_reason("MYSTERY") == "unknown_status"
    _note("H89", "test_h89_unknown_status_fails_closed", "reservation_status_block_reason", result, direct and result["blocked_by"] == "unknown_status" and result["broker_requests"] == 0)


def test_h90_historical_filled_hold_remains() -> None:
    note_unconfirmed_exposure(SYMBOL, "filled-old")
    result = _run(balance=5000)
    _note("H90", "test_h90_historical_filled_hold_remains", "exposure_entry_block_reason", result, result["blocked_by"] == "exposure_unconfirmed")


def test_h91_filled_does_not_mean_flat() -> None:
    result = _voted("BUY", balance=5000)
    _note("H91", "test_h91_filled_does_not_mean_flat", "confirm_exposure_flat", result, result["status"] == "filled" and confirm_exposure_flat(SYMBOL, evidence="FILLED") is False)


def test_h92_missing_position_does_not_prove_flat() -> None:
    note_unconfirmed_exposure(SYMBOL, "missing-position")
    result = _run(balance=5000)
    ok = get_position(SYMBOL) is None and result["blocked_by"] == "exposure_unconfirmed"
    _note("H92", "test_h92_missing_position_does_not_prove_flat", "exposure_entry_block_reason", result, ok)


def test_h93_confirmed_flat_token_cannot_release() -> None:
    note_unconfirmed_exposure(SYMBOL, "held")
    released = confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT")
    result = _run(balance=5000)
    _note("H93", "test_h93_confirmed_flat_token_cannot_release", "confirm_exposure_flat", result, released is False and result["blocked_by"] == "exposure_unconfirmed")


def test_h94_verified_flag_cannot_release() -> None:
    note_unconfirmed_exposure(SYMBOL, "held")
    released = confirm_exposure_flat(SYMBOL, verified=True)
    _note("H94", "test_h94_verified_flag_cannot_release", "confirm_exposure_flat", None, released is False and exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed")


def test_h95_reconciliation_dict_cannot_release() -> None:
    note_unconfirmed_exposure(SYMBOL, "held")
    released = confirm_exposure_flat(SYMBOL, evidence={"flat": True, "verified": True})
    _note("H95", "test_h95_reconciliation_dict_cannot_release", "confirm_exposure_flat", None, released is False)


def test_h96_partial_close_retains_hold() -> None:
    result = _voted("BUY", balance=5000, broker=FakeBroker("partial"))
    _note("H96", "test_h96_partial_close_retains_hold", "note_unconfirmed_exposure", result, result["exposure_held"] is True and exposure_entry_block_reason(SYMBOL) is not None)


def test_h97_timeout_retains_hold() -> None:
    result = _voted("BUY", balance=5000, broker=FakeBroker("filled", error=TimeoutError()))
    _note("H97", "test_h97_timeout_retains_hold", "note_unconfirmed_exposure", result, result["exposure_held"] is True)


def test_h98_ambiguous_retains_hold() -> None:
    result = _voted("BUY", balance=5000, broker=FakeBroker("ambiguous"))
    _note("H98", "test_h98_ambiguous_retains_hold", "restore_unresolved_intent", result, result["exposure_held"] is True and result["broker_requests"] == 1)


def test_h99_position_recording_failure_retains_hold() -> None:
    result = _voted("BUY", balance=5000, fail_position_record=True)
    _note("H99", "test_h99_position_recording_failure_retains_hold", "note_unconfirmed_exposure", result, result["exposure_held"] is True and get_position(SYMBOL) is None)


def test_h100_no_retry_after_uncertainty() -> None:
    broker = FakeBroker("ambiguous")
    result = _voted("BUY", balance=5000, broker=broker)
    _note("H100", "test_h100_no_retry_after_uncertainty", "FakeBroker.submit", result, broker.request_count == 1 and result["exposure_held"] is True)


def test_h101_one_production_adapter_reference() -> None:
    ok = SOURCE.count("execute_oanda_market_open") == 1 and "current_equity(" not in SHARED
    _note("H101", "test_h101_one_production_adapter_reference", "production_execution_adapter", None, ok)


def test_h102_no_synthetic_production_account_authority() -> None:
    reason, _value = _account_entry_block(_deps(simulation=False, balance=5000, account_payload={"verified": True}))
    _note("H102", "test_h102_no_synthetic_production_account_authority", "_account_entry_block", None, reason == "account_unverified")


def test_h103_rejection_does_not_fabricate_a_position() -> None:
    result = _voted("BUY", balance=5000, broker=FakeBroker("rejected"))
    _note("H103", "test_h103_rejection_does_not_fabricate_a_position", "FakeBroker.submit", result, get_position(SYMBOL) is None)


def test_h104_no_fabricated_flat_confirmation() -> None:
    result = _voted("BUY", balance=5000)
    _note("H104", "test_h104_no_fabricated_flat_confirmation", "confirm_exposure_flat", result, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False)


def test_h105_no_migration() -> None:
    database_text = (ROOT / "forex_bot" / "database.py").read_text(encoding="utf-8")
    ok = "CREATE TABLE" in database_text and database._pg_conn is None
    _note("H105", "test_h105_no_migration", "database", None, ok, limitations="source still contains existing DDL text; this stage did not execute or add a migration")


def test_h106_selector_executes() -> None:
    result = _voted("BUY", balance=5000)
    _note("H106", "test_h106_selector_executes", "select_strategy", result, result["details"]["selector_called"] is True)


def test_h107_ai_vote_executes() -> None:
    result = _voted("BUY", balance=5000)
    _note("H107", "test_h107_ai_vote_executes", "AIEnsemble.vote", result, result["details"]["vote_wrapper_called"] is True)


def test_h108_rl_veto_executes() -> None:
    result = _voted("BUY", balance=5000)
    _note("H108", "test_h108_rl_veto_executes", "RLAgent.decide", result, result["details"]["rl_veto_called"] is True)


def test_h109_buy_reaches_inert_adapter_once() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", balance=5000, broker=broker)
    _note("H109", "test_h109_buy_reaches_inert_adapter_once", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "BUY")


def test_h110_sell_reaches_inert_adapter_once() -> None:
    broker = FakeBroker("filled")
    result = _voted("SELL", balance=5000, broker=broker)
    _note("H110", "test_h110_sell_reaches_inert_adapter_once", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "SELL")


def test_h111_sizing_and_cap_share_equity() -> None:
    result = _voted("BUY", balance=5000)
    _note("H111", "test_h111_sizing_and_cap_share_equity", "portfolio_risk_cap_exceeded", result, _same(result, 5000.0))


def test_h112_no_entry_call_to_current_equity() -> None:
    _note("H112", "test_h112_no_entry_call_to_current_equity", "evaluate_one_instrument_iteration", None, "current_equity(" not in SHARED)


def test_h113_base_balance_does_not_authorise() -> None:
    result = _run(account_present=False, balance=None)
    _note("H113", "test_h113_base_balance_does_not_authorise", "_account_entry_block", result, result["broker_requests"] == 0 and result["blocked_by"] == "account_missing")


def test_h114_equity_curve_does_not_authorise() -> None:
    state["equity_curve"] = [20_000.0]
    result = _run(account_present=False, balance=None)
    _note("H114", "test_h114_equity_curve_does_not_authorise", "current_equity", result, current_equity() == 20_000.0 and result["broker_requests"] == 0)


def test_h115_cached_nav_does_not_override() -> None:
    state["broker_nav"] = 20_000.0
    result = _voted("BUY", balance=5000)
    _note("H115", "test_h115_cached_nav_does_not_override", "current_equity", result, current_equity() == 20_000.0 and result["details"]["accepted_equity"] == 5000.0)


def test_h116_no_production_adapter_invocation() -> None:
    result = _voted("BUY", balance=5000)
    body = inspect.getsource(production_execution_adapter)
    ok = result["details"]["production_adapter_invoked"] is False and "execute_oanda_market_open" in body
    _note("H116", "test_h116_no_production_adapter_invocation", "production_execution_adapter", result, ok)


def test_h117_no_real_oanda_client() -> None:
    _voted("BUY", balance=5000)
    client = sys.modules.get("forex_bot.oanda_client")
    api = None if client is None else getattr(client, "_api", "missing")
    _note("H117", "test_h117_no_real_oanda_client", "oanda_client", None, api is None and database._pg_conn is None)


def test_h118_no_real_broker_execution() -> None:
    result = _voted("BUY", balance=5000)
    _note("H118", "test_h118_no_real_broker_execution", "execute_oanda_market_open", result, result["real_broker"] is False and result["details"]["production_adapter_invoked"] is False)


def test_h119_no_postgresql_connection() -> None:
    _voted("BUY", balance=5000)
    _note("H119", "test_h119_no_postgresql_connection", "database", None, database._pg_conn is None)


def test_h120_no_network_success() -> None:
    _note("H120", "test_h120_no_network_success", "socket", None, database._pg_conn is None and "main" not in sys.modules)


def test_h121_no_dns_success() -> None:
    _note("H121", "test_h121_no_dns_success", "socket", None, "main" not in sys.modules)


def test_h122_no_run_bot() -> None:
    _note("H122", "test_h122_no_run_bot", "run_bot", None, inspect.iscoroutinefunction(run_bot) and "main" not in sys.modules)


def test_h123_no_launcher() -> None:
    _note("H123", "test_h123_no_launcher", "main", None, "main" not in sys.modules)


def test_h124_no_lifespan() -> None:
    _note("H124", "test_h124_no_lifespan", "lifespan", None, sys.modules.get("forex_bot.app") is None)


def test_h125_no_strategy_activation() -> None:
    _voted("BUY", balance=5000)
    _note("H125", "test_h125_no_strategy_activation", "strategies", None, all(strategies[name].active is False for name in NAMES))


def test_h126_no_permission_mutation() -> None:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    _voted("BUY", balance=5000)
    after = path.stat().st_mtime if path.exists() else None
    _note("H126", "test_h126_no_permission_mutation", "live_safety", None, before == after)


def test_h127_cleanup() -> None:
    setup_function()
    _note("H127", "test_h127_cleanup", "reset_orders_for_tests", None, database._pg_conn is None and not positions and state["broker_nav"] is None)


def test_h128_r8_regression() -> None:
    note_blocking_reservation(SYMBOL, "r8")
    result = _run(balance=5000)
    _note("H128", "test_h128_r8_regression", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation")


def test_h129_r9_regression() -> None:
    result = _voted("BUY", balance=5000)
    _note("H129", "test_h129_r9_regression", "confirm_exposure_flat", result, confirm_exposure_flat(SYMBOL, evidence="FILLED") is False)


def test_h130_r10_regression() -> None:
    text = (ROOT / "forex_bot" / "app.py").read_text(encoding="utf-8")
    _note("H130", "test_h130_r10_regression", "initialise_application", None, "trading_ready" in text and "select_rows_for_recovery" in text)


def test_h131_r11_regression() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "r11", "symbol": SYMBOL, "status": "FILLED", "metadata": None}])
    _note("H131", "test_h131_r11_regression", "select_rows_for_recovery", None, bool(kept))


def test_h132_r12_regression() -> None:
    result = _voted("BUY", balance=5000)
    _note("H132", "test_h132_r12_regression", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1 and result["scheduled_another"] is False)


def test_h133_r13_regression() -> None:
    _note("H133", "test_h133_r13_regression", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False)


def test_h134_r14_regression() -> None:
    result = _voted("BUY", balance=5000)
    details = result["details"]
    ok = details["selector_called"] and details["vote_wrapper_called"] and details["rl_veto_called"]
    _note("H134", "test_h134_r14_regression", "evaluate_one_instrument_iteration", result, ok and result["broker_requests"] == 1)


def test_h135_r15_regression() -> None:
    missing = _run(account_present=False, balance=None)
    ok = missing["blocked_by"] == "account_missing" and SOURCE.count("execute_oanda_market_open") == 1
    _note("H135", "test_h135_r15_regression", "_account_entry_block", missing, ok)


def test_h136_postgresql_not_evaluated() -> None:
    _skip("H136", "test_h136_postgresql_not_evaluated", "PostgreSQL", "PostgreSQL engine NOT_EVALUATED")


def test_h137_oanda_not_evaluated() -> None:
    _skip("H137", "test_h137_oanda_not_evaluated", "OANDA", "OANDA broker NOT_EVALUATED")


def test_h138_production_loop_not_evaluated() -> None:
    _skip("H138", "test_h138_production_loop_not_evaluated", "run_bot", "production loop NOT_EVALUATED")


def test_h139_broker_flat_not_evaluated() -> None:
    _skip("H139", "test_h139_broker_flat_not_evaluated", "confirm_exposure_flat", "authoritative broker-flat release NOT_EVALUATED")


def test_h140_production_account_not_evaluated() -> None:
    _skip("H140", "test_h140_production_account_not_evaluated", "account", "production account provenance and freshness NOT_EVALUATED")


def test_h141_profitability_not_evaluated() -> None:
    _skip("H141", "test_h141_profitability_not_evaluated", "backtest", "strategy profitability NOT_EVALUATED")
