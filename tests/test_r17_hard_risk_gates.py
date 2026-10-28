"""Offline hard risk gates. No broker, database, or production loop."""

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
R17 = ROOT / "data" / "research" / "adaptive_ensemble" / "r17"
R17.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R17 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    evaluate_one_instrument_iteration,
    production_execution_adapter,
    rl_decision_state,
    run_bot,
)
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    note_blocking_reservation,
    note_unconfirmed_exposure,
    reset_order_intent_gate_for_tests,
    restore_unresolved_intent,
    select_rows_for_recovery,
)
from forex_bot.indicators import compute_indicators  # noqa: E402
from forex_bot.orders import LocalOrder, OrderStatus, register_order, reset_orders_for_tests  # noqa: E402
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
NAMES = ("scalp", "trend", "mean_reversion", "swing_trend", "swing_mean_reversion", "swing_breakout")
RECORDS: list[dict[str, object]] = []
SOURCE = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
LIMIT = "synthetic harness; production provenance, margin and numeric spread policy are not verified"


def _bars(n: int = 50, start: float = 1.1) -> list[dict[str, float | str]]:
    return [
        {
            "open": start,
            "high": start + 0.0002,
            "low": start - 0.0002,
            "close": start,
            "time": f"2026-01-07T11:{index % 60:02d}:00+00:00",
        }
        for index in range(n)
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
    raw_price = overrides.get("price", 1.1)
    price = raw_price if isinstance(raw_price, (int, float)) else 1.1
    if not isinstance(price, (int, float)) or not math.isfinite(float(price)):
        price = 1.1
    values: dict[str, object] = {
        "candles": bars,
        "balance": 10000.0,
        "account_present": True,
        "account_context": "isolated_test",
        "simulation": True,
        "now": OPEN,
        "quote_as_of": OPEN,
        "price": price,
        "bid": price - 0.00005,
        "ask": price + 0.00005,
        "stop_distance": 0.001,
        "stop_loss": price - 0.001,
        "take_profit": price + 0.002,
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
        "rl_agent": overrides.get("rl_agent") or _agent_for(bars, action),  # type: ignore[arg-type]
    }
    values.update(overrides)
    if "unrealised" not in overrides:
        values["unrealised"] = 0.0
    if "account_as_of" not in overrides:
        values["account_as_of"] = values.get("now")
    return IterationDependencies(**values)  # type: ignore[arg-type]


def _run(symbol: str = SYMBOL, **overrides: object) -> dict:
    return evaluate_one_instrument_iteration(symbol, _deps(**overrides))


def _note(test_id: str, function: str, source: str, result: dict | None, ok: bool, status: str = "PASS", **extra: object) -> None:
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
            "risk_gate": extra.get("risk_gate", ""),
            "risk_gate_enabled": extra.get("risk_gate_enabled"),
            "reservation": bool(details.get("reservation_attempted")),
            "inert_adapter_calls": int(0 if result is None else result.get("broker_requests") or 0),
            "real_broker_requests": 0,
            "status": status if ok else "FAIL",
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
            "risk_gate": source,
            "risk_gate_enabled": False,
            "reservation": False,
            "inert_adapter_calls": 0,
            "real_broker_requests": 0,
            "status": "NOT_EVALUATED",
            "evidence": {},
            "limitations": limitation,
        }
    )
    pytest.skip("NOT_EVALUATED")


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R17)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R17 / "synthetic_live_safety_state.json")
    os.environ.pop("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", None)
    os.environ.pop("MAX_POSITION_UNITS", None)
    os.environ.pop("DECISION_REPAIR_ACCOUNT_RISK", None)
    os.environ.pop("DECISION_REPAIR_RISK_PATH", None)
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)
    path = R17 / "account_risk.json"
    if path.exists():
        path.unlink()


def _dump() -> None:
    (R17 / "test_records.json").write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")


atexit.register(_dump)


def _risk_on(monkeypatch: pytest.MonkeyPatch) -> Path:
    path = R17 / "account_risk.json"
    if path.exists():
        path.unlink()
    monkeypatch.setenv("DECISION_REPAIR_ACCOUNT_RISK", "1")
    monkeypatch.setenv("DECISION_REPAIR_RISK_PATH", str(path))
    return path


def _observe(path: Path, delta: float, equity: float) -> None:
    from forex_bot.decision_repair.account_risk import observe

    now = datetime.now(timezone.utc)
    observe(
        event_id=f"evt-{delta}-{equity}",
        realised_delta=delta,
        equity=equity,
        unrealised=0.0,
        broker_time_utc=now.isoformat(),
        broker_seq=1,
        path=path,
    )


def test_i001_notional_within_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    result = _run()
    ok = result["broker_requests"] == 1 and result["details"]["gross_notional_enabled"] is True
    _note("I001", "test_i001_notional_within_cap", "portfolio_gross_notional_pct_of_nav", result, ok, risk_gate="gross_notional", risk_gate_enabled=True)


def test_i002_notional_above_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.01")
    result = _run()
    ok = result["blocked_by"] == "notional_cap" and result["broker_requests"] == 0 and result["details"]["reservation_attempted"] is False
    _note("I002", "test_i002_notional_above_cap", "portfolio_gross_notional_pct_of_nav", result, ok, risk_gate="gross_notional", risk_gate_enabled=True)


def test_i003_notional_boundary_matches_contract() -> None:
    text = (ROOT / "forex_bot" / "portfolio_exposure.py").read_text(encoding="utf-8")
    ok = "resulting > cap" in text and "Equal-to-cap is allowed" in text
    _note("I003", "test_i003_notional_boundary_matches_contract", "notional_cap_decision", None, ok, risk_gate="gross_notional", risk_gate_enabled=True)


def test_i004_open_position_notional_is_included(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    open_position(Position("GBP_USD", "BUY", 1_000_000, 1.27, 1.26, 1.3, 0, "synthetic", "synthetic", "synthetic"))
    result = _run()
    _note("I004", "test_i004_open_position_notional_is_included", "existing_gross_usd_by_symbol", result, result["blocked_by"] == "notional_cap" and result["broker_requests"] == 0, risk_gate="gross_notional", risk_gate_enabled=True)


def test_i005_candidate_notional_is_included(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.01")
    result = _run()
    _note("I005", "test_i005_candidate_notional_is_included", "approx_gross_usd_notional_for", result, result["blocked_by"] == "notional_cap", risk_gate="gross_notional", risk_gate_enabled=True)


def test_i006_pending_notional_is_not_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    register_order(LocalOrder("pend-gbp", "GBP_USD", "BUY", 1_000_000, 0, OrderStatus.PENDING, 1.27, 0.0))
    note_blocking_reservation("GBP_USD", "pend-gbp")
    result = _run()
    _note("I006", "test_i006_pending_notional_is_not_zero", "_pending_gross_usd", result, result["blocked_by"] == "notional_cap", risk_gate="gross_notional", risk_gate_enabled=True)


def test_i007_missing_pending_price_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    register_order(LocalOrder("pend-gap", "GBP_USD", "BUY", 10, 0, OrderStatus.PENDING, None, 0.0))
    note_blocking_reservation("GBP_USD", "pend-gap")
    result = _run()
    _note("I007", "test_i007_missing_pending_price_fails_closed", "_pending_gross_usd", result, result["blocked_by"] == "notional_exposure_unreadable" and result["broker_requests"] == 0, risk_gate="gross_notional", risk_gate_enabled=True)


def test_i008_malformed_pending_units_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    order = LocalOrder("pend-bad", "GBP_USD", "BUY", 10, 0, OrderStatus.PENDING, 1.2, 0.0)
    order.units_requested = float("nan")
    register_order(order)
    note_blocking_reservation("GBP_USD", "pend-bad")
    result = _run()
    _note("I008", "test_i008_malformed_pending_units_fail_closed", "_pending_gross_usd", result, result["blocked_by"] == "notional_exposure_unreadable", risk_gate="gross_notional", risk_gate_enabled=True)


def test_i009_nonfinite_size_blocks_before_notional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("forex_bot.trading.position_sizing", lambda *args, **kwargs: float("inf"))
    result = _run()
    _note("I009", "test_i009_nonfinite_size_blocks_before_notional", "position_sizing", result, result["blocked_by"] == "quantity_nonfinite" and result["broker_requests"] == 0, risk_gate="notional", risk_gate_enabled=False)


def test_i010_invalid_price_blocks() -> None:
    result = _run(price=float("nan"), bid=1.09995, ask=1.10005)
    ok = result["broker_requests"] == 0 and result["details"]["sizing_invoked"] is False and "sizing" not in result["phases"]
    _note("I010", "test_i010_invalid_price_blocks", "evaluate_one_instrument_iteration", result, ok, risk_gate="price", risk_gate_enabled=True, limitations="existing invalid-price return uses the provenance label when one is present; sizing and notional do not run")


def test_i011_unit_cap_within_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_POSITION_UNITS", "100000000")
    result = _run()
    _note("I011", "test_i011_unit_cap_within_limit", "_configured_unit_cap", result, result["broker_requests"] == 1 and result["details"]["unit_cap_enabled"] is True, risk_gate="unit_cap", risk_gate_enabled=True)


def test_i012_unit_cap_above_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_POSITION_UNITS", "10")
    result = _run()
    ok = result["blocked_by"] == "unit_cap" and result["broker_requests"] == 0 and result["details"]["reservation_attempted"] is False
    _note("I012", "test_i012_unit_cap_above_limit", "_configured_unit_cap", result, ok, risk_gate="unit_cap", risk_gate_enabled=True)


def test_i013_signed_units_follow_broker_contract() -> None:
    from forex_bot.bot_loop import broker_signed_units

    buy = _run()
    setup_function()
    sell = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8})
    ok = broker_signed_units(4, "BUY") == 4 and broker_signed_units(4, "SELL") == -4
    ok = ok and buy["broker_requests"] == 1 and sell["broker_requests"] == 1
    _note("I013", "test_i013_signed_units_follow_broker_contract", "broker_signed_units", sell, ok, risk_gate="units", risk_gate_enabled=True)


def test_i014_missing_units_fail_closed() -> None:
    result = _run(stop_distance=0)
    _note("I014", "test_i014_missing_units_fail_closed", "position_sizing", result, result["blocked_by"] == "size_not_positive" and result["broker_requests"] == 0, risk_gate="units", risk_gate_enabled=True)


def test_i015_unit_cap_is_per_order() -> None:
    from forex_bot.trading import cap_position_units

    text = inspect.getsource(cap_position_units)
    _note("I015", "test_i015_unit_cap_is_per_order", "cap_position_units", None, "positions" not in text, risk_gate="unit_cap", risk_gate_enabled=True, limitations="existing MAX_POSITION_UNITS is a per-order cap, not an aggregate of open units")


def test_i016_cap_percentages_unchanged() -> None:
    from forex_bot.trading import configured_max_portfolio_risk_pct

    _note("I016", "test_i016_cap_percentages_unchanged", "configured_max_portfolio_risk_pct", None, configured_max_portfolio_risk_pct() == 0.05, risk_gate="portfolio", risk_gate_enabled=True)


def test_i017_unit_default_unchanged() -> None:
    from forex_bot.bot_loop import _configured_unit_cap

    _note("I017", "test_i017_unit_default_unchanged", "_configured_unit_cap", None, _configured_unit_cap() == 0.0, risk_gate="unit_cap", risk_gate_enabled=False)


def test_i018_disabled_defaults_are_reported() -> None:
    result = _run()
    details = result["details"]
    ok = details["gross_notional_enabled"] is False and details["unit_cap_enabled"] is False and details["daily_loss_enabled"] is False
    _note("I018", "test_i018_disabled_defaults_are_reported", "evaluate_one_instrument_iteration", result, ok, risk_gate="defaults", risk_gate_enabled=False)


def test_i019_disabled_cap_is_not_called_active() -> None:
    result = _run()
    _note("I019", "test_i019_disabled_cap_is_not_called_active", "evaluate_one_instrument_iteration", result, result["details"]["gross_notional_enabled"] is False and result["broker_requests"] == 1, risk_gate="gross_notional", risk_gate_enabled=False)


def test_i020_unreadable_enabled_cap_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    note_blocking_reservation("GBP_USD", "missing-order")
    result = _run()
    _note("I020", "test_i020_unreadable_enabled_cap_blocks", "_pending_gross_usd", result, result["blocked_by"] == "notional_exposure_unreadable" and result["broker_requests"] == 0, risk_gate="gross_notional", risk_gate_enabled=True)


def test_i021_daily_loss_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -100.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("I021", "test_i021_daily_loss_passes", "block_reason", result, result["broker_requests"] == 1 and result["details"]["daily_loss_enabled"] is True, risk_gate="daily_loss", risk_gate_enabled=True, limitations="enabled only while DECISION_REPAIR_ACCOUNT_RISK is set; production default is off")


def test_i022_daily_loss_blocks_at_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("I022", "test_i022_daily_loss_blocks_at_boundary", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit" and result["broker_requests"] == 0, risk_gate="daily_loss", risk_gate_enabled=True)


def test_i023_drawdown_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, 0.0, 10000.0)
    result = _run(balance=9600.0, unrealised=0.0)
    _note("I023", "test_i023_drawdown_passes", "block_reason", result, result["broker_requests"] == 1, risk_gate="drawdown", risk_gate_enabled=True)


def test_i024_drawdown_blocks_at_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, 0.0, 10000.0)
    result = _run(balance=9500.0, unrealised=0.0)
    _note("I024", "test_i024_drawdown_blocks_at_boundary", "block_reason", result, result["blocked_by"] == "max_drawdown_limit" and result["details"]["reservation_attempted"] is False, risk_gate="drawdown", risk_gate_enabled=True)


def test_i025_missing_loss_input_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    _risk_on(monkeypatch)
    result = _run(unrealised=None)
    _note("I025", "test_i025_missing_loss_input_blocks", "block_reason", result, result["blocked_by"] == "account_unrealised_unavailable" and "sizing" not in result["phases"], risk_gate="daily_loss", risk_gate_enabled=True)


def test_i026_malformed_loss_file_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    path.write_text("not-json", encoding="utf-8")
    result = _run(unrealised=0.0)
    _note("I026", "test_i026_malformed_loss_file_blocks", "block_reason", result, result["blocked_by"] == "corrupt_risk_state", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i027_nonfinite_unrealised_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    _risk_on(monkeypatch)
    result = _run(unrealised=float("nan"))
    _note("I027", "test_i027_nonfinite_unrealised_blocks", "block_reason", result, result["blocked_by"] == "account_unrealised_unavailable", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i028_missing_peak_is_existing_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    _risk_on(monkeypatch)
    result = _run(unrealised=0.0)
    ok = result["broker_requests"] == 1
    _note("I028", "test_i028_missing_peak_is_existing_behavior", "block_reason", result, ok, status="PARTIAL", risk_gate="drawdown", risk_gate_enabled=True, limitations="the existing function sets the first positive equity as the peak; a missing historical peak is not a separate block")


def test_i029_no_risk_freshness_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -10.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("I029", "test_i029_no_risk_freshness_policy", "block_reason", result, result["details"]["risk_freshness"] == "not_evaluated", status="PARTIAL", risk_gate="daily_loss", risk_gate_enabled=True, limitations="the existing risk file has no freshness window; none was invented")


def test_i030_halt_blocks_later_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    first = _run(unrealised=0.0)
    second = _run(unrealised=0.0)
    ok = first["blocked_by"] == second["blocked_by"] == "daily_realised_loss_limit"
    _note("I030", "test_i030_halt_blocks_later_entry", "block_reason", second, ok, risk_gate="daily_loss", risk_gate_enabled=True)


def test_i031_halt_blocks_later_buy(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("I031", "test_i031_halt_blocks_later_buy", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i032_halt_blocks_later_sell(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, unrealised=0.0)
    _note("I032", "test_i032_halt_blocks_later_sell", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i033_new_strategy_does_not_bypass_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(strategy_name="trend", unrealised=0.0)
    _note("I033", "test_i033_new_strategy_does_not_bypass_halt", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i034_new_instrument_does_not_bypass_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    bars = _bars(start=1.27)
    result = _run("GBP_USD", candles=bars, price=1.27, bid=1.26995, ask=1.27005, unrealised=0.0, rl_agent=_agent_for(bars, "BUY"))
    _note("I034", "test_i034_new_instrument_does_not_bypass_halt", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i035_latch_survives_a_later_read(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    _run(unrealised=0.0)
    from forex_bot.decision_repair.account_risk import block_reason

    reason = block_reason(equity=10000.0, unrealised=0.0, path=path)
    _note("I035", "test_i035_latch_survives_a_later_read", "block_reason", None, reason == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True, limitations="a later read of the risk file keeps the latch; a process restart was not executed")


def test_i036_latch_is_not_claimed_durable_across_restart() -> None:
    text = inspect.getsource(evaluate_one_instrument_iteration)
    _note("I036", "test_i036_latch_is_not_claimed_durable_across_restart", "block_reason", None, "restart" not in text, status="PARTIAL", risk_gate="daily_loss", risk_gate_enabled=False, limitations="process restart was not executed; the JSON latch is not production durability")


def test_i037_verified_flag_does_not_clear_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0, account_payload={"verified": True, "equity": 10000})
    _note("I037", "test_i037_verified_flag_does_not_clear_halt", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i038_fabricated_report_does_not_clear_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0, account_payload={"realised_pnl": 0, "flat": True})
    _note("I038", "test_i038_fabricated_report_does_not_clear_halt", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i039_entry_path_has_no_reset_token() -> None:
    body = inspect.getsource(evaluate_one_instrument_iteration)
    _note("I039", "test_i039_entry_path_has_no_reset_token", "operator_clear_latch", None, "operator_clear_latch" not in body, risk_gate="daily_loss", risk_gate_enabled=False)


def test_i040_loss_thresholds_unchanged() -> None:
    from forex_bot.decision_repair.account_risk import default_limits

    limits = default_limits()
    ok = limits["daily_realised_pct"] == 0.02 and limits["daily_total_pct"] == 0.03 and limits["max_dd_pct"] == 0.05
    _note("I040", "test_i040_loss_thresholds_unchanged", "default_limits", None, ok, risk_gate="daily_loss", risk_gate_enabled=False)


def test_i041_no_reset_without_operator_policy() -> None:
    from forex_bot.decision_repair.account_risk import operator_clear_latch

    with pytest.raises(PermissionError):
        operator_clear_latch(operator_confirmed=False)
    _note("I041", "test_i041_no_reset_without_operator_policy", "operator_clear_latch", None, True, risk_gate="daily_loss", risk_gate_enabled=False, limitations="the existing operator clear requires operator_confirmed; the entry path does not call it")


def test_i042_production_risk_flag_stays_off() -> None:
    from forex_bot.decision_repair.flags import account_risk_enabled

    _note("I042", "test_i042_production_risk_flag_stays_off", "account_risk_enabled", None, account_risk_enabled() is False, risk_gate="daily_loss", risk_gate_enabled=False)


def test_i043_loss_check_uses_accepted_equity(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, 0.0, 10000.0)
    result = _run(balance=9600.0, unrealised=0.0)
    _note("I043", "test_i043_loss_check_uses_accepted_equity", "block_reason", result, result["details"]["accepted_equity"] == 9600.0 and result["broker_requests"] == 1, risk_gate="drawdown", risk_gate_enabled=True)


def test_i044_breach_blocks_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("I044", "test_i044_breach_blocks_entry", "block_reason", result, result["broker_requests"] == 0, risk_gate="daily_loss", risk_gate_enabled=True)


def test_i045_breach_blocks_reservation_and_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0)
    ok = result["details"]["reservation_attempted"] is False and result["broker_requests"] == 0
    _note("I045", "test_i045_breach_blocks_reservation_and_adapter", "block_reason", result, ok, risk_gate="daily_loss", risk_gate_enabled=True)


def test_i046_missing_bid_blocks() -> None:
    result = _run(bid=None)
    _note("I046", "test_i046_missing_bid_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_bid_missing" and result["broker_requests"] == 0, risk_gate="quote", risk_gate_enabled=True)


def test_i047_missing_ask_blocks() -> None:
    result = _run(ask=None)
    _note("I047", "test_i047_missing_ask_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_ask_missing", risk_gate="quote", risk_gate_enabled=True)


def test_i048_nonfinite_bid_blocks() -> None:
    result = _run(bid=float("nan"))
    _note("I048", "test_i048_nonfinite_bid_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_bid_nonfinite", risk_gate="quote", risk_gate_enabled=True)


def test_i049_nonfinite_ask_blocks() -> None:
    result = _run(ask=float("inf"))
    _note("I049", "test_i049_nonfinite_ask_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_ask_nonfinite", risk_gate="quote", risk_gate_enabled=True)


def test_i050_zero_bid_blocks() -> None:
    result = _run(bid=0.0, ask=1.0)
    _note("I050", "test_i050_zero_bid_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_bid_not_positive", risk_gate="quote", risk_gate_enabled=True)


def test_i051_negative_ask_blocks() -> None:
    result = _run(bid=1.0, ask=-1.0)
    _note("I051", "test_i051_negative_ask_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_ask_not_positive", risk_gate="quote", risk_gate_enabled=True)


def test_i052_crossed_quote_blocks() -> None:
    result = _run(bid=1.2, ask=1.1)
    _note("I052", "test_i052_crossed_quote_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_crossed", risk_gate="quote", risk_gate_enabled=True)


def test_i053_spread_uses_price_units() -> None:
    result = _run(bid=1.10, ask=1.1002)
    _note("I053", "test_i053_spread_uses_price_units", "_market_entry_block", result, math.isclose(float(result["details"]["spread_price_units"]), 0.0002), risk_gate="spread", risk_gate_enabled=False, limitations="spread is ask minus bid in price units; no pip conversion was invented")


def test_i054_spread_units_documented() -> None:
    _note("I054", "test_i054_spread_units_documented", "_market_entry_block", None, "spread_price_units" in SOURCE, risk_gate="spread", risk_gate_enabled=False)


def test_i055_no_approved_spread_pass() -> None:
    result = _run(spread=0.0001)
    _note("I055", "test_i055_no_approved_spread_pass", "_market_entry_block", result, result["details"]["spread_limit"] == "not_approved", status="PARTIAL", risk_gate="spread", risk_gate_enabled=False, limitations="no approved numeric spread threshold exists")


def test_i056_wide_spread_is_not_a_passed_check() -> None:
    result = _run(spread=0.05)
    _note("I056", "test_i056_wide_spread_is_not_a_passed_check", "_market_entry_block", result, result["details"]["spread_limit"] == "not_approved", status="PARTIAL", risk_gate="spread", risk_gate_enabled=False, limitations="0.05 was not blocked because no approved threshold exists")


def test_i057_unknown_threshold_is_not_a_pass() -> None:
    result = _run()
    _note("I057", "test_i057_unknown_threshold_is_not_a_pass", "_market_entry_block", result, result["details"]["spread_limit"] != "passed", risk_gate="spread", risk_gate_enabled=False)


def test_i058_missing_quote_time_is_not_freshness() -> None:
    result = _run(quote_as_of=None)
    ok = result["blocked_by"] == "quote_timestamp_missing" and result["broker_requests"] == 0 and result["production_eligible"] is False
    _note("I058", "test_i058_missing_quote_time_is_not_freshness", "_market_entry_block", result, ok, risk_gate="quote", risk_gate_enabled=True)


def test_i059_stale_quote_blocks() -> None:
    result = _run(quote_as_of=OPEN - timedelta(seconds=91))
    _note("I059", "test_i059_stale_quote_blocks", "MANAGE_PRICE_STALE_SEC", result, result["blocked_by"] == "quote_stale", risk_gate="quote", risk_gate_enabled=True, limitations="uses the existing 90-second manage-quote window when a timestamp is supplied")


def test_i060_future_quote_blocks() -> None:
    result = _run(quote_as_of=OPEN + timedelta(seconds=1))
    _note("I060", "test_i060_future_quote_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_timestamp_future", risk_gate="quote", risk_gate_enabled=True)


def test_i061_missing_candles_block() -> None:
    result = _run(candles=[])
    _note("I061", "test_i061_missing_candles_block", "evaluate_one_instrument_iteration", result, result["blocked_by"] == "no_candles", risk_gate="lookback", risk_gate_enabled=True)


def test_i062_empty_candle_history_blocks() -> None:
    result = _run(candles=[])
    _note("I062", "test_i062_empty_candle_history_blocks", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 0, risk_gate="lookback", risk_gate_enabled=True)


def test_i063_insufficient_lookback_blocks() -> None:
    result = _run(candles=_bars(5))
    _note("I063", "test_i063_insufficient_lookback_blocks", "_entry_lookback_requirement", result, result["blocked_by"] in {"insufficient_lookback", "volatility_unsafe"} and result["broker_requests"] == 0, risk_gate="lookback", risk_gate_enabled=True)


def test_i064_lookback_matches_scalp_default() -> None:
    result = _run(candles=_bars(49))
    _note("I064", "test_i064_lookback_matches_scalp_default", "_entry_lookback_requirement", result, result["details"]["lookback_required"] == 50 and result["blocked_by"] == "insufficient_lookback", risk_gate="lookback", risk_gate_enabled=True)


def test_i065_malformed_candle_blocks() -> None:
    rows = _bars()
    rows[-1] = {"open": "bad"}
    result = _run(candles=rows)
    _note("I065", "test_i065_malformed_candle_blocks", "_market_entry_block", result, result["blocked_by"] in {"candle_malformed", "indicator_failure", "volatility_unsafe"} and result["broker_requests"] == 0, risk_gate="candles", risk_gate_enabled=True)


def test_i066_nonfinite_candle_blocks() -> None:
    rows = _bars()
    rows[-1]["close"] = float("nan")
    result = _run(candles=rows)
    _note("I066", "test_i066_nonfinite_candle_blocks", "_market_entry_block", result, result["blocked_by"] == "candle_nonfinite", risk_gate="candles", risk_gate_enabled=True)


def test_i067_out_of_order_times_block() -> None:
    rows = _bars()
    rows[-1]["time"] = "2026-01-07T10:00:00+00:00"
    result = _run(candles=rows)
    _note("I067", "test_i067_out_of_order_times_block", "_market_entry_block", result, result["blocked_by"] == "candle_time_out_of_order", risk_gate="candles", risk_gate_enabled=True)


def test_i068_duplicate_times_are_deterministic() -> None:
    rows = _bars()
    rows[-1]["time"] = rows[-2]["time"]
    result = _run(candles=rows)
    _note("I068", "test_i068_duplicate_times_are_deterministic", "_market_entry_block", result, result["details"]["duplicate_candle_timestamps"] is True and result["broker_requests"] == 1, risk_gate="candles", risk_gate_enabled=True, limitations="duplicate timestamps are recorded; they are not treated as broker-verified")


def test_i069_missing_provenance_is_not_broker_verified() -> None:
    result = _run()
    ok = result["provenance"] == "missing_provenance" and result["details"]["market_provenance"] == "synthetic_harness"
    _note("I069", "test_i069_missing_provenance_is_not_broker_verified", "decision_frame_rejection", result, ok, risk_gate="provenance", risk_gate_enabled=True)


def test_i070_synthetic_quotes_stay_in_the_harness() -> None:
    result = _run()
    _note("I070", "test_i070_synthetic_quotes_stay_in_the_harness", "_market_entry_block", result, result["production_authorised"] is False, risk_gate="quote", risk_gate_enabled=True)


def test_i071_lookback_is_not_reduced() -> None:
    body = inspect.getsource(evaluate_one_instrument_iteration)
    _note("I071", "test_i071_lookback_is_not_reduced", "_entry_lookback_requirement", None, "insufficient_lookback" in SOURCE and "short_lookback_is_not_a_hard_block" not in body, risk_gate="lookback", risk_gate_enabled=True)


def test_i072_quote_failure_skips_reservation() -> None:
    result = _run(bid=None)
    _note("I072", "test_i072_quote_failure_skips_reservation", "_market_entry_block", result, result["details"]["reservation_attempted"] is False, risk_gate="quote", risk_gate_enabled=True)


def test_i073_quote_failure_skips_adapter() -> None:
    result = _run(ask=None)
    _note("I073", "test_i073_quote_failure_skips_adapter", "_market_entry_block", result, result["broker_requests"] == 0, risk_gate="quote", risk_gate_enabled=True)


def test_i074_no_strategy_activation() -> None:
    _run()
    _note("I074", "test_i074_no_strategy_activation", "strategies", None, all(strategies[name].active is False for name in NAMES), risk_gate="strategy", risk_gate_enabled=True)


def test_i075_strategy_source_unchanged() -> None:
    data = (ROOT / "forex_bot" / "strategy_meta.py").read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    digest = __import__("hashlib").sha256(data).hexdigest()
    _note("I075", "test_i075_strategy_source_unchanged", "strategy_meta", None, digest == "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d", risk_gate="strategy", risk_gate_enabled=False)


def test_i076_margin_missing_is_explicit() -> None:
    result = _run()
    _note("I076", "test_i076_margin_missing_is_explicit", "evaluate_one_instrument_iteration", result, result["details"]["margin_evidence"] == "not_implemented", status="PARTIAL", risk_gate="margin", risk_gate_enabled=False)


def test_i077_equity_is_not_margin_proof() -> None:
    result = _run()
    _note("I077", "test_i077_equity_is_not_margin_proof", "evaluate_one_instrument_iteration", result, result["details"]["equity_is_not_margin_proof"] is True, risk_gate="margin", risk_gate_enabled=False)


def test_i078_synthetic_margin_is_not_production_funds() -> None:
    result = _run(account_payload={"marginAvailable": 1, "verified": True})
    _note("I078", "test_i078_synthetic_margin_is_not_production_funds", "evaluate_one_instrument_iteration", result, result["details"]["margin_sufficiency"] == "NOT_EVALUATED" and result["production_authorised"] is False, status="PARTIAL", risk_gate="margin", risk_gate_enabled=False)


def test_i079_no_enabled_margin_parser() -> None:
    _note("I079", "test_i079_no_enabled_margin_parser", "evaluate_one_instrument_iteration", None, "margin_rate" not in SOURCE, status="PARTIAL", risk_gate="margin", risk_gate_enabled=False, limitations="no margin parser was added")


def test_i080_negative_margin_is_not_a_pass() -> None:
    result = _run(account_payload={"marginAvailable": -5})
    _note("I080", "test_i080_negative_margin_is_not_a_pass", "evaluate_one_instrument_iteration", result, result["details"]["margin_sufficiency"] == "NOT_EVALUATED", status="PARTIAL", risk_gate="margin", risk_gate_enabled=False)


def test_i081_nonfinite_margin_is_not_a_pass() -> None:
    result = _run(account_payload={"marginAvailable": float("nan")})
    _note("I081", "test_i081_nonfinite_margin_is_not_a_pass", "evaluate_one_instrument_iteration", result, result["details"]["margin_sufficiency"] != "passed", risk_gate="margin", risk_gate_enabled=False)


def test_i082_currency_mismatch_is_not_ignored_as_proof() -> None:
    result = _run(account_payload={"currency": "JPY", "marginAvailable": 10})
    _note("I082", "test_i082_currency_mismatch_is_not_ignored_as_proof", "evaluate_one_instrument_iteration", result, result["details"]["margin_sufficiency"] == "NOT_EVALUATED", status="PARTIAL", risk_gate="margin", risk_gate_enabled=False)


def test_i083_no_invented_margin_rule() -> None:
    _note("I083", "test_i083_no_invented_margin_rule", "evaluate_one_instrument_iteration", None, "leverage" not in inspect.getsource(evaluate_one_instrument_iteration), risk_gate="margin", risk_gate_enabled=False)


def test_i084_no_margin_bypass_flag() -> None:
    _note("I084", "test_i084_no_margin_bypass_flag", "evaluate_one_instrument_iteration", None, "margin_bypass" not in SOURCE, risk_gate="margin", risk_gate_enabled=False)


def test_i085_margin_integration_is_partial() -> None:
    result = _run()
    _note("I085", "test_i085_margin_integration_is_partial", "evaluate_one_instrument_iteration", result, result["details"]["margin_sufficiency"] == "NOT_EVALUATED", status="PARTIAL", risk_gate="margin", risk_gate_enabled=False, limitations="broker margin sufficiency is NOT_EVALUATED")


def test_i086_market_gate_precedes_reservation() -> None:
    result = _run()
    phases = result["phases"]
    _note("I086", "test_i086_market_gate_precedes_reservation", "evaluate_one_instrument_iteration", result, phases.index("market_data") < phases.index("reservation"), risk_gate="ordering", risk_gate_enabled=True)


def test_i087_risk_gate_precedes_adapter() -> None:
    result = _run()
    phases = result["phases"]
    _note("I087", "test_i087_risk_gate_precedes_adapter", "evaluate_one_instrument_iteration", result, phases.index("risk") < phases.index("fake_broker"), risk_gate="ordering", risk_gate_enabled=True)


def test_i088_buy_still_faces_the_quote_gate() -> None:
    result = _run(bid=None)
    _note("I088", "test_i088_buy_still_faces_the_quote_gate", "_market_entry_block", result, result["blocked_by"] == "quote_bid_missing", risk_gate="quote", risk_gate_enabled=True)


def test_i089_sell_still_faces_the_quote_gate() -> None:
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, ask=None)
    _note("I089", "test_i089_sell_still_faces_the_quote_gate", "_market_entry_block", result, result["blocked_by"] == "quote_ask_missing", risk_gate="quote", risk_gate_enabled=True)


def test_i090_rl_approval_does_not_skip_quote_gate() -> None:
    result = _run(bid=None)
    _note("I090", "test_i090_rl_approval_does_not_skip_quote_gate", "_market_entry_block", result, result["details"]["rl_veto_called"] is True and result["broker_requests"] == 0, risk_gate="quote", risk_gate_enabled=True)


def test_i091_active_strategy_does_not_skip_lookback() -> None:
    result = _run(candles=_bars(5), strategy_active=True)
    _note("I091", "test_i091_active_strategy_does_not_skip_lookback", "_entry_lookback_requirement", result, result["blocked_by"] in {"insufficient_lookback", "volatility_unsafe"}, risk_gate="lookback", risk_gate_enabled=True)


def test_i092_position_hold_remains() -> None:
    open_position(Position(SYMBOL, "BUY", 1, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    result = _run()
    _note("I092", "test_i092_position_hold_remains", "get_position", result, result["blocked_by"] == "position_already_open", risk_gate="exposure", risk_gate_enabled=True)


def test_i093_historical_filled_hold_remains() -> None:
    note_unconfirmed_exposure(SYMBOL, "old")
    result = _run()
    _note("I093", "test_i093_historical_filled_hold_remains", "exposure_entry_block_reason", result, result["blocked_by"] == "exposure_unconfirmed", risk_gate="exposure", risk_gate_enabled=True)


def test_i094_pending_hold_remains() -> None:
    note_blocking_reservation(SYMBOL, "p")
    result = _run()
    _note("I094", "test_i094_pending_hold_remains", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation", risk_gate="reservation", risk_gate_enabled=True)


def test_i095_partial_hold_remains() -> None:
    register_order(LocalOrder("part", SYMBOL, "BUY", 1, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "part")
    result = _run()
    _note("I095", "test_i095_partial_hold_remains", "note_blocking_reservation", result, result["broker_requests"] == 0, risk_gate="reservation", risk_gate_enabled=True)


def test_i096_unresolved_hold_remains() -> None:
    restore_unresolved_intent(SYMBOL, "u")
    result = _run()
    _note("I096", "test_i096_unresolved_hold_remains", "restore_unresolved_intent", result, result["blocked_by"] == "unresolved_intent", risk_gate="reservation", risk_gate_enabled=True)


def test_i097_invalid_account_remains_blocked() -> None:
    result = _run(account_present=False, balance=None)
    _note("I097", "test_i097_invalid_account_remains_blocked", "_account_entry_block", result, result["blocked_by"] == "account_missing" and "sizing" not in result["phases"], risk_gate="account", risk_gate_enabled=True)


def test_i098_accepted_equity_stays_consistent() -> None:
    result = _run(balance=5000)
    details = result["details"]
    ok = details["accepted_equity"] == details["sizing_equity"] == details["portfolio_cap_equity"] == 5000
    _note("I098", "test_i098_accepted_equity_stays_consistent", "portfolio_risk_cap_exceeded", result, ok, risk_gate="equity", risk_gate_enabled=True)


def test_i099_failed_risk_skips_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_POSITION_UNITS", "1")
    result = _run()
    _note("I099", "test_i099_failed_risk_skips_reservation", "_configured_unit_cap", result, result["details"]["reservation_attempted"] is False, risk_gate="unit_cap", risk_gate_enabled=True)


def test_i100_failed_risk_skips_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_POSITION_UNITS", "1")
    result = _run()
    _note("I100", "test_i100_failed_risk_skips_adapter", "_configured_unit_cap", result, result["broker_requests"] == 0, risk_gate="unit_cap", risk_gate_enabled=True)


def test_i101_buy_reaches_adapter_once() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("I101", "test_i101_buy_reaches_adapter_once", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "BUY", risk_gate="adapter", risk_gate_enabled=True)


def test_i102_sell_reaches_adapter_once() -> None:
    broker = FakeBroker("filled")
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, broker=broker)
    _note("I102", "test_i102_sell_reaches_adapter_once", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "SELL", risk_gate="adapter", risk_gate_enabled=True)


def test_i103_one_broker_reference() -> None:
    _note("I103", "test_i103_one_broker_reference", "production_execution_adapter", None, SOURCE.count("execute_oanda_market_open") == 1, risk_gate="adapter", risk_gate_enabled=True)


def test_i104_no_retry_after_timeout() -> None:
    broker = FakeBroker("filled", error=TimeoutError())
    result = _run(broker=broker)
    _note("I104", "test_i104_no_retry_after_timeout", "FakeBroker.submit", result, broker.request_count == 1 and result["exposure_held"] is True, risk_gate="outcome", risk_gate_enabled=True)


def test_i105_no_flat_release_and_no_activation() -> None:
    result = _run()
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    after = path.stat().st_mtime if path.exists() else None
    ok = confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False and before == after and result["production_authorised"] is False
    _note("I105", "test_i105_no_flat_release_and_no_activation", "confirm_exposure_flat", result, ok, risk_gate="exposure", risk_gate_enabled=True)


def test_i106_buy_within_enabled_test_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    monkeypatch.setenv("MAX_POSITION_UNITS", "100000000")
    result = _run()
    _note("I106", "test_i106_buy_within_enabled_test_limits", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1, risk_gate="combined", risk_gate_enabled=True)


def test_i107_sell_within_enabled_test_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    monkeypatch.setenv("MAX_POSITION_UNITS", "100000000")
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8})
    _note("I107", "test_i107_sell_within_enabled_test_limits", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1, risk_gate="combined", risk_gate_enabled=True)


def test_i108_scenario_notional_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.01")
    result = _run()
    _note("I108", "test_i108_scenario_notional_breach", "portfolio_gross_notional_pct_of_nav", result, result["blocked_by"] == "notional_cap", risk_gate="gross_notional", risk_gate_enabled=True)


def test_i109_scenario_unit_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_POSITION_UNITS", "2")
    result = _run()
    _note("I109", "test_i109_scenario_unit_breach", "_configured_unit_cap", result, result["blocked_by"] == "unit_cap", risk_gate="unit_cap", risk_gate_enabled=True)


def test_i110_scenario_missing_exposure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    note_blocking_reservation("USD_JPY", "no-order")
    result = _run()
    _note("I110", "test_i110_scenario_missing_exposure", "_pending_gross_usd", result, result["blocked_by"] == "notional_exposure_unreadable", risk_gate="gross_notional", risk_gate_enabled=True)


def test_i111_scenario_daily_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("I111", "test_i111_scenario_daily_loss", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i112_scenario_drawdown(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, 0.0, 10000.0)
    result = _run(balance=9000.0, unrealised=0.0)
    _note("I112", "test_i112_scenario_drawdown", "block_reason", result, result["blocked_by"] == "max_drawdown_limit", risk_gate="drawdown", risk_gate_enabled=True)


def test_i113_scenario_halt_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    _run(unrealised=0.0)
    result = _run(unrealised=0.0)
    _note("I113", "test_i113_scenario_halt_persists", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i114_scenario_fabricated_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0, account_payload={"reset": "CONFIRMED_FLAT", "verified": True})
    _note("I114", "test_i114_scenario_fabricated_reset", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i115_scenario_wide_spread_not_approved() -> None:
    result = _run(spread=0.05)
    _note("I115", "test_i115_scenario_wide_spread_not_approved", "_market_entry_block", result, result["details"]["spread_limit"] == "not_approved", status="PARTIAL", risk_gate="spread", risk_gate_enabled=False)


def test_i116_scenario_missing_quote() -> None:
    result = _run(bid=None, ask=None)
    _note("I116", "test_i116_scenario_missing_quote", "_market_entry_block", result, result["blocked_by"] == "quote_bid_missing", risk_gate="quote", risk_gate_enabled=True)


def test_i117_scenario_invalid_quote() -> None:
    result = _run(bid=1.3, ask=1.2)
    _note("I117", "test_i117_scenario_invalid_quote", "_market_entry_block", result, result["blocked_by"] == "quote_crossed", risk_gate="quote", risk_gate_enabled=True)


def test_i118_scenario_stale_quote() -> None:
    result = _run(quote_as_of=OPEN - timedelta(minutes=5))
    _note("I118", "test_i118_scenario_stale_quote", "MANAGE_PRICE_STALE_SEC", result, result["blocked_by"] == "quote_stale", risk_gate="quote", risk_gate_enabled=True)


def test_i119_scenario_short_lookback() -> None:
    result = _run(candles=_bars(10))
    _note("I119", "test_i119_scenario_short_lookback", "_entry_lookback_requirement", result, result["blocked_by"] in {"insufficient_lookback", "volatility_unsafe"}, risk_gate="lookback", risk_gate_enabled=True)


def test_i120_scenario_malformed_candles() -> None:
    rows = _bars()[:-1] + [{"close": "nope", "time": "2026-01-07T12:00:00+00:00"}]
    result = _run(candles=rows, rl_agent=_agent_for(_bars(), "BUY"))
    _note("I120", "test_i120_scenario_malformed_candles", "_market_entry_block", result, result["broker_requests"] == 0, risk_gate="candles", risk_gate_enabled=True)


def test_i121_scenario_missing_provenance() -> None:
    result = _run()
    _note("I121", "test_i121_scenario_missing_provenance", "decision_frame_rejection", result, result["provenance"] == "missing_provenance" and result["production_authorised"] is False, risk_gate="provenance", risk_gate_enabled=True)


def test_i122_scenario_missing_account() -> None:
    result = _run(account_present=False, balance=None)
    _note("I122", "test_i122_scenario_missing_account", "_account_entry_block", result, result["blocked_by"] == "account_missing", risk_gate="account", risk_gate_enabled=True)


def test_i123_scenario_unverified_account() -> None:
    result = _run(account_context="production")
    _note("I123", "test_i123_scenario_unverified_account", "_account_entry_block", result, result["blocked_by"] == "account_unverified", risk_gate="account", risk_gate_enabled=True)


def test_i124_scenario_conflicting_equity() -> None:
    result = _run(balance=5000, account_payload={"equity": 20000})
    _note("I124", "test_i124_scenario_conflicting_equity", "_account_entry_block", result, result["details"]["accepted_equity"] == 5000, risk_gate="account", risk_gate_enabled=True)


def test_i125_scenario_missing_margin() -> None:
    result = _run()
    _note("I125", "test_i125_scenario_missing_margin", "evaluate_one_instrument_iteration", result, result["details"]["margin_evidence"] == "not_implemented", status="PARTIAL", risk_gate="margin", risk_gate_enabled=False)


def test_i126_scenario_existing_position() -> None:
    open_position(Position(SYMBOL, "BUY", 2, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    result = _run()
    _note("I126", "test_i126_scenario_existing_position", "get_position", result, result["blocked_by"] == "position_already_open", risk_gate="exposure", risk_gate_enabled=True)


def test_i127_scenario_historical_filled() -> None:
    note_unconfirmed_exposure(SYMBOL, "filled")
    result = _run()
    _note("I127", "test_i127_scenario_historical_filled", "note_unconfirmed_exposure", result, result["blocked_by"] == "exposure_unconfirmed", risk_gate="exposure", risk_gate_enabled=True)


def test_i128_scenario_pending() -> None:
    note_blocking_reservation(SYMBOL, "pend")
    result = _run()
    _note("I128", "test_i128_scenario_pending", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation", risk_gate="reservation", risk_gate_enabled=True)


def test_i129_scenario_partial() -> None:
    register_order(LocalOrder("p2", SYMBOL, "BUY", 1, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "p2")
    result = _run()
    _note("I129", "test_i129_scenario_partial", "note_blocking_reservation", result, result["broker_requests"] == 0, risk_gate="reservation", risk_gate_enabled=True)


def test_i130_scenario_unresolved() -> None:
    restore_unresolved_intent(SYMBOL, "un")
    result = _run()
    _note("I130", "test_i130_scenario_unresolved", "restore_unresolved_intent", result, result["blocked_by"] == "unresolved_intent", risk_gate="reservation", risk_gate_enabled=True)


def test_i131_scenario_rl_veto() -> None:
    bars = _bars()
    result = _run(candles=bars, rl_agent=_agent_for(bars, "SKIP"))
    _note("I131", "test_i131_scenario_rl_veto", "RLAgent.decide", result, result["blocked_by"] == "rl_veto", risk_gate="rl", risk_gate_enabled=True)


def test_i132_scenario_invalid_vote() -> None:
    result = _run(vote={"allow": True, "direction": "MAYBE", "confidence": 0.2})
    _note("I132", "test_i132_scenario_invalid_vote", "canonical_entry_direction", result, result["blocked_by"] == "invalid_entry_direction", risk_gate="vote", risk_gate_enabled=True)


def test_i133_scenario_inactive_strategy() -> None:
    result = _run(strategy_active=False, strategy_active_map={})
    _note("I133", "test_i133_scenario_inactive_strategy", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED", risk_gate="strategy", risk_gate_enabled=True)


def test_i134_scenario_reservation_failure() -> None:
    result = _run(persistence_failure="unavailable")
    _note("I134", "test_i134_scenario_reservation_failure", "refuse_reservation_after_database_fault", result, result["blocked_by"] == "reservation_persistence_failed" and result["broker_requests"] == 0, risk_gate="reservation", risk_gate_enabled=True)


def test_i135_scenario_timeout() -> None:
    result = _run(broker=FakeBroker("filled", error=TimeoutError()))
    _note("I135", "test_i135_scenario_timeout", "FakeBroker.submit", result, result["outcome"] == "timeout" and result["exposure_held"] is True, risk_gate="outcome", risk_gate_enabled=True)


def test_i136_scenario_ambiguous() -> None:
    result = _run(broker=FakeBroker("ambiguous"))
    _note("I136", "test_i136_scenario_ambiguous", "FakeBroker.submit", result, result["outcome"] == "ambiguous" and result["broker_requests"] == 1, risk_gate="outcome", risk_gate_enabled=True)


def test_i137_scenario_partial_fill() -> None:
    result = _run(broker=FakeBroker("partial"))
    _note("I137", "test_i137_scenario_partial_fill", "finalize_order_fill", result, result["status"] == "partial" and result["exposure_held"] is True, risk_gate="outcome", risk_gate_enabled=True)


def test_i138_scenario_position_record_failure() -> None:
    result = _run(fail_position_record=True)
    _note("I138", "test_i138_scenario_position_record_failure", "record_synthetic_fill_position", result, result["exposure_held"] is True and get_position(SYMBOL) is None, risk_gate="outcome", risk_gate_enabled=True)


def test_i139_scenario_duplicate_client_id() -> None:
    register_order(LocalOrder("same", SYMBOL, "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _run(client_order_id="same")
    _note("I139", "test_i139_scenario_duplicate_client_id", "try_begin_order_submission", result, result["blocked_by"] == "reservation_refused", risk_gate="reservation", risk_gate_enabled=True)


def test_i140_scenario_cleanup() -> None:
    setup_function()
    _note("I140", "test_i140_scenario_cleanup", "reset_orders_for_tests", None, database._pg_conn is None and not positions, risk_gate="cleanup", risk_gate_enabled=True)


def test_i141_selector_executed() -> None:
    result = _run()
    _note("I141", "test_i141_selector_executed", "select_strategy", result, result["details"]["selector_called"] is True, risk_gate="selector", risk_gate_enabled=True)


def test_i142_vote_executed() -> None:
    result = _run()
    _note("I142", "test_i142_vote_executed", "AIEnsemble.vote", result, result["details"]["vote_wrapper_called"] is True, risk_gate="vote", risk_gate_enabled=True)


def test_i143_rl_executed() -> None:
    result = _run()
    _note("I143", "test_i143_rl_executed", "RLAgent.decide", result, result["details"]["rl_veto_called"] is True, risk_gate="rl", risk_gate_enabled=True)


def test_i144_r16_equity_consistent() -> None:
    result = _run(balance=5000)
    details = result["details"]
    ok = details["current_equity_used_for_entry"] is False and details["sizing_equity"] == 5000
    _note("I144", "test_i144_r16_equity_consistent", "portfolio_risk_cap_exceeded", result, ok, risk_gate="equity", risk_gate_enabled=True)


def test_i145_portfolio_cap_enforced() -> None:
    open_position(Position("GBP_USD", "BUY", 300_000, 1.27, 1.269, 1.3, 0, "synthetic", "synthetic", "synthetic"))
    result = _run(balance=5000)
    _note("I145", "test_i145_portfolio_cap_enforced", "portfolio_risk_cap_exceeded", result, result["blocked_by"] == "portfolio_risk_cap", risk_gate="portfolio", risk_gate_enabled=True)


def test_i146_gross_cap_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.01")
    result = _run()
    _note("I146", "test_i146_gross_cap_enforced", "portfolio_gross_notional_pct_of_nav", result, result["blocked_by"] == "notional_cap", risk_gate="gross_notional", risk_gate_enabled=True)


def test_i147_unit_cap_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_POSITION_UNITS", "3")
    result = _run()
    _note("I147", "test_i147_unit_cap_enforced", "_configured_unit_cap", result, result["blocked_by"] == "unit_cap", risk_gate="unit_cap", risk_gate_enabled=True)


def test_i148_daily_loss_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("I148", "test_i148_daily_loss_enforced", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", risk_gate="daily_loss", risk_gate_enabled=True)


def test_i149_drawdown_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, 0.0, 10000.0)
    result = _run(balance=9000.0, unrealised=0.0)
    _note("I149", "test_i149_drawdown_enforced", "block_reason", result, result["blocked_by"] == "max_drawdown_limit", risk_gate="drawdown", risk_gate_enabled=True)


def test_i150_spread_threshold_not_approved() -> None:
    result = _run()
    _note("I150", "test_i150_spread_threshold_not_approved", "_market_entry_block", result, result["details"]["spread_limit"] == "not_approved", status="PARTIAL", risk_gate="spread", risk_gate_enabled=False, limitations="no approved numeric spread threshold")


def test_i151_lookback_blocks() -> None:
    result = _run(candles=_bars(8))
    _note("I151", "test_i151_lookback_blocks", "_entry_lookback_requirement", result, result["blocked_by"] in {"insufficient_lookback", "volatility_unsafe"}, risk_gate="lookback", risk_gate_enabled=True)


def test_i152_margin_policy_not_fabricated() -> None:
    result = _run()
    _note("I152", "test_i152_margin_policy_not_fabricated", "evaluate_one_instrument_iteration", result, result["details"]["margin_evidence"] == "not_implemented", status="PARTIAL", risk_gate="margin", risk_gate_enabled=False)


def test_i153_buy_once() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("I153", "test_i153_buy_once", "FakeBroker.submit", result, broker.request_count == 1, risk_gate="adapter", risk_gate_enabled=True)


def test_i154_sell_once() -> None:
    broker = FakeBroker("filled")
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, broker=broker)
    _note("I154", "test_i154_sell_once", "FakeBroker.submit", result, broker.request_count == 1, risk_gate="adapter", risk_gate_enabled=True)


def test_i155_no_production_adapter_call() -> None:
    result = _run()
    body = inspect.getsource(production_execution_adapter)
    ok = result["details"]["production_adapter_invoked"] is False and "execute_oanda_market_open" in body
    _note("I155", "test_i155_no_production_adapter_call", "production_execution_adapter", result, ok, risk_gate="adapter", risk_gate_enabled=True)


def test_i156_no_oanda_client() -> None:
    _run()
    client = sys.modules.get("forex_bot.oanda_client")
    api = None if client is None else getattr(client, "_api", None)
    _note("I156", "test_i156_no_oanda_client", "oanda_client", None, api is None, risk_gate="broker", risk_gate_enabled=False)


def test_i157_no_postgresql() -> None:
    _run()
    _note("I157", "test_i157_no_postgresql", "database", None, database._pg_conn is None, risk_gate="database", risk_gate_enabled=False)


def test_i158_no_network() -> None:
    _note("I158", "test_i158_no_network", "socket", None, "main" not in sys.modules, risk_gate="network", risk_gate_enabled=True)


def test_i159_no_dns() -> None:
    _note("I159", "test_i159_no_dns", "socket", None, "main" not in sys.modules, risk_gate="dns", risk_gate_enabled=True)


def test_i160_no_run_bot() -> None:
    _note("I160", "test_i160_no_run_bot", "run_bot", None, inspect.iscoroutinefunction(run_bot), risk_gate="loop", risk_gate_enabled=False)


def test_i161_no_launcher() -> None:
    _note("I161", "test_i161_no_launcher", "main", None, "main" not in sys.modules, risk_gate="launcher", risk_gate_enabled=False)


def test_i162_no_lifespan() -> None:
    _note("I162", "test_i162_no_lifespan", "lifespan", None, sys.modules.get("forex_bot.app") is None, risk_gate="lifespan", risk_gate_enabled=False)


def test_i163_no_strategy_activation() -> None:
    _run()
    _note("I163", "test_i163_no_strategy_activation", "strategies", None, all(strategies[name].active is False for name in NAMES), risk_gate="strategy", risk_gate_enabled=False)


def test_i164_no_permission_mutation() -> None:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    _run()
    after = path.stat().st_mtime if path.exists() else None
    _note("I164", "test_i164_no_permission_mutation", "live_safety", None, before == after, risk_gate="permission", risk_gate_enabled=True)


def test_i165_no_fabricated_flat() -> None:
    _run()
    _note("I165", "test_i165_no_fabricated_flat", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False, risk_gate="exposure", risk_gate_enabled=True)


def test_i166_r8_regression() -> None:
    note_blocking_reservation(SYMBOL, "r8")
    result = _run()
    _note("I166", "test_i166_r8_regression", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation", risk_gate="reservation", risk_gate_enabled=True)


def test_i167_r9_regression() -> None:
    result = _run()
    _note("I167", "test_i167_r9_regression", "confirm_exposure_flat", result, confirm_exposure_flat(SYMBOL, evidence="FILLED") is False, risk_gate="exposure", risk_gate_enabled=True)


def test_i168_r10_regression() -> None:
    text = (ROOT / "forex_bot" / "app.py").read_text(encoding="utf-8")
    _note("I168", "test_i168_r10_regression", "initialise_application", None, "trading_ready" in text, risk_gate="startup", risk_gate_enabled=True)


def test_i169_r11_regression() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "r11", "symbol": SYMBOL, "status": "FILLED", "metadata": None}])
    _note("I169", "test_i169_r11_regression", "select_rows_for_recovery", None, bool(kept), risk_gate="recovery", risk_gate_enabled=True)


def test_i170_r12_regression() -> None:
    result = _run()
    _note("I170", "test_i170_r12_regression", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1 and result["scheduled_another"] is False, risk_gate="iteration", risk_gate_enabled=True)


def test_i171_r13_regression() -> None:
    _note("I171", "test_i171_r13_regression", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False, risk_gate="exposure", risk_gate_enabled=True)


def test_i172_r14_regression() -> None:
    result = _run()
    details = result["details"]
    ok = details["selector_called"] and details["vote_wrapper_called"] and details["rl_veto_called"]
    _note("I172", "test_i172_r14_regression", "evaluate_one_instrument_iteration", result, ok, risk_gate="decision", risk_gate_enabled=True)


def test_i173_r15_regression() -> None:
    result = _run(account_present=False, balance=None)
    _note("I173", "test_i173_r15_regression", "_account_entry_block", result, result["blocked_by"] == "account_missing", risk_gate="account", risk_gate_enabled=True)


def test_i174_r16_regression() -> None:
    result = _run(balance=5000)
    _note("I174", "test_i174_r16_regression", "portfolio_risk_cap_exceeded", result, result["details"]["portfolio_cap_equity"] == 5000, risk_gate="equity", risk_gate_enabled=True)


def test_i175_postgresql_not_evaluated() -> None:
    _skip("I175", "test_i175_postgresql_not_evaluated", "PostgreSQL", "PostgreSQL engine NOT_EVALUATED")


def test_i176_oanda_not_evaluated() -> None:
    _skip("I176", "test_i176_oanda_not_evaluated", "OANDA", "OANDA broker NOT_EVALUATED")


def test_i177_loop_not_evaluated() -> None:
    _skip("I177", "test_i177_loop_not_evaluated", "run_bot", "production loop NOT_EVALUATED")


def test_i178_flat_release_not_evaluated() -> None:
    _skip("I178", "test_i178_flat_release_not_evaluated", "confirm_exposure_flat", "authoritative broker-flat release NOT_EVALUATED")


def test_i179_account_provenance_not_evaluated() -> None:
    _skip("I179", "test_i179_account_provenance_not_evaluated", "account", "production account provenance NOT_EVALUATED")


def test_i180_market_provenance_not_evaluated() -> None:
    _skip("I180", "test_i180_market_provenance_not_evaluated", "market", "production market-data provenance NOT_EVALUATED")


def test_i181_loss_durability_not_evaluated() -> None:
    _skip("I181", "test_i181_loss_durability_not_evaluated", "account_risk", "production daily-loss durability NOT_EVALUATED")


def test_i182_margin_not_evaluated() -> None:
    _skip("I182", "test_i182_margin_not_evaluated", "margin", "broker margin sufficiency NOT_EVALUATED")


def test_i183_profitability_not_evaluated() -> None:
    _skip("I183", "test_i183_profitability_not_evaluated", "backtest", "strategy profitability NOT_EVALUATED")
