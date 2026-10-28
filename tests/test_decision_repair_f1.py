"""Stage F.1 completion: audit coverage, selector, RL, risk, health, harness.

Broker-disconnected. Temporary stores only. No live authorisation, no Docker.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.decision_repair import AUDIT_SCHEMA_VERSION
from forex_bot.decision_repair.account_risk import (
    REASON_DAILY_TOTAL,
    REASON_EQUITY_INVALID,
    REASON_EQUITY_MISSING,
    REASON_UNREALISED_MISSING,
    block_reason,
    observe,
    operator_clear_latch,
)
from forex_bot.decision_repair.audit import (
    FORBIDDEN_KEYS,
    EvaluationAudit,
    empty_record,
)
from forex_bot.decision_repair.flags import (
    account_risk_enabled,
    audit_enabled,
    deterministic_select_enabled,
)
from forex_bot.decision_repair.harness import SCENARIOS, load_jsonl
from forex_bot.decision_repair.health import (
    ELIGIBLE_FOR_OFFLINE_REVIEW,
    INACTIVE,
    OPERATOR_DISABLED,
    SUSPENDED_PERFORMANCE,
    SUSPENDED_RISK,
    evaluate_name,
)
from forex_bot.decision_repair.rl_store import (
    RLStore,
    config_fingerprint,
    production_path,
)
from forex_bot.decision_repair.selection import (
    ALL_NAMES,
    last_selection,
    select_deterministic,
)
from forex_bot.execution import pre_trade_entry_blocked_reason
from forex_bot.live_safety import (
    AUTH_BLOCKED,
    initialise_fail_closed,
    live_order_auth_state,
)
from forex_bot.rl_agent import RLAgent
from forex_bot.strategy_meta import select_strategy, strategies

_FLAG_KEYS = (
    "DECISION_REPAIR_DETERMINISTIC_SELECT",
    "DECISION_REPAIR_RL_PERSIST",
    "DECISION_REPAIR_RL_REQUIRE_STATE",
    "DECISION_REPAIR_AUDIT",
    "DECISION_REPAIR_HEALTH",
    "DECISION_REPAIR_ACCOUNT_RISK",
)


@pytest.fixture(autouse=True)
def _clear_repair_flags(monkeypatch):
    for key in _FLAG_KEYS:
        monkeypatch.delenv(key, raising=False)


def _ohlcv(*, close_nan: bool = False) -> pd.DataFrame:
    idx = pd.date_range("2026-10-01", periods=40, freq="5min", tz="UTC")
    close = pd.Series([1.1000 + i * 0.0001 for i in range(40)], index=idx)
    if close_nan:
        close.iloc[-1] = float("nan")
    return pd.DataFrame(
        {
            "time": idx,
            "open": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "close": close,
            "volume": 1.0,
        }
    )


def _atr_df(n: int = 20, last: float = 0.002, med: float = 0.001) -> pd.DataFrame:
    atr = [med] * (n - 1) + [last]
    return pd.DataFrame(
        {
            "time": [datetime(2026, 6, 1, tzinfo=timezone.utc)] * n,
            "open": [1.1] * n,
            "high": [1.11] * n,
            "low": [1.09] * n,
            "close": [1.1] * n,
            "atr": atr,
        }
    )


def _read_audit(path: Path) -> list[dict]:
    return load_jsonl(path)


def _enable_audit(monkeypatch, tmp_path: Path) -> Path:
    dest = tmp_path / "decisions.jsonl"
    monkeypatch.setenv("DECISION_REPAIR_AUDIT", "1")
    monkeypatch.setenv("DECISION_REPAIR_AUDIT_PATH", str(dest))
    return dest


def _patch_session_open(monkeypatch, raw: pd.DataFrame) -> None:
    # Unit-test legacy audit emission downstream of the shared entry decision.
    # The production dispatcher and its refusal contracts are tested separately.
    monkeypatch.setattr("forex_bot.bot_loop.dispatch_production_iteration", lambda *_a, **_k: {"status": "continue_existing_production_broker"})
    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", lambda *_a, **_k: raw)
    monkeypatch.setattr("forex_bot.bot_loop.in_active_session", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.bot_loop.flatten_for_weekend", lambda: False)
    monkeypatch.setattr("forex_bot.bot_loop.get_position", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.broker_exit.broker_exit_open_blocked_reason", lambda *_a, **_k: None)


def test_schema_version_is_two_and_flags_still_default_off():
    rec = empty_record(symbol="EUR_USD")
    assert rec["schema_version"] == AUDIT_SCHEMA_VERSION == 3
    assert rec["not_broker_proof"] is True
    assert rec["order_submitted"] is False
    assert rec["audit_delivery"] == "at_least_once_best_effort"
    assert deterministic_select_enabled() is False
    assert audit_enabled() is False
    assert account_risk_enabled() is False


def test_zero_and_empty_env_do_not_enable_flags(monkeypatch):
    monkeypatch.setenv("DECISION_REPAIR_AUDIT", "0")
    monkeypatch.setenv("DECISION_REPAIR_DETERMINISTIC_SELECT", "")
    monkeypatch.setenv("DECISION_REPAIR_ACCOUNT_RISK", "false")
    assert audit_enabled() is False
    assert deterministic_select_enabled() is False
    assert account_risk_enabled() is False


def test_audit_covers_missing_data_session_and_auth(monkeypatch, tmp_path):
    from forex_bot.bot_loop import evaluate
    from forex_bot.decision_skip_log import (
        LIVE_ORDER_AUTH_BLOCKED,
        MARKET_SESSION_CLOSED,
        NO_OHLCV,
    )

    dest = _enable_audit(monkeypatch, tmp_path)
    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", lambda *_a, **_k: None)
    asyncio.run(evaluate("EUR_USD"))
    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", lambda *_a, **_k: _ohlcv())
    monkeypatch.setattr("forex_bot.bot_loop.get_position", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.bot_loop.in_active_session", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.bot_loop.flatten_for_weekend", lambda: False)
    asyncio.run(evaluate("EUR_USD"))
    initialise_fail_closed()
    _patch_session_open(monkeypatch, _ohlcv())
    asyncio.run(evaluate("EUR_USD"))
    rows = _read_audit(dest)
    reasons = {row.get("explicit_rejection_reason") for row in rows}
    assert NO_OHLCV in reasons
    assert MARKET_SESSION_CLOSED in reasons
    assert LIVE_ORDER_AUTH_BLOCKED in reasons
    assert all(row.get("schema_version") == 3 for row in rows)
    assert all(row.get("not_broker_proof") is True for row in rows)
    for row in rows:
        for key in FORBIDDEN_KEYS:
            assert key not in row


def test_audit_covers_inactive_ai_rl_and_unexpected(monkeypatch, tmp_path):
    from forex_bot.bot_loop import evaluate
    from forex_bot.decision_skip_log import (
        QUANT_AI_REJECTED,
        RL_STATE_UNAVAILABLE,
        STRATEGY_INACTIVE,
    )

    dest = _enable_audit(monkeypatch, tmp_path)
    raw = _ohlcv()
    _patch_session_open(monkeypatch, raw)
    monkeypatch.setattr("forex_bot.bot_loop.pre_trade_entry_blocked_reason", lambda: None)
    monkeypatch.setattr("forex_bot.bot_loop.select_strategy", lambda *_a, **_k: ("trend", 50, "legacy"))
    strategies["trend"].active = False
    asyncio.run(evaluate("EUR_USD"))

    strategies["trend"].active = True
    monkeypatch.setattr("forex_bot.bot_loop.volatility_ok", lambda *_a, **_k: True)

    async def _reject(*_a, **_k):
        return {"allow": False, "direction": "BUY", "confidence": 0.1, "model": "stub"}

    monkeypatch.setattr("forex_bot.bot_loop.ai.vote", _reject)
    asyncio.run(evaluate("EUR_USD"))

    async def _allow(*_a, **_k):
        return {"allow": True, "direction": "BUY", "confidence": 0.6, "model": "stub"}

    monkeypatch.setattr("forex_bot.bot_loop.ai.vote", _allow)
    monkeypatch.setenv("DECISION_REPAIR_RL_REQUIRE_STATE", "1")
    monkeypatch.setattr("forex_bot.bot_loop.rl_agent.persisted_ok", False, raising=False)
    monkeypatch.setattr("forex_bot.bot_loop.rl_agent.decide", lambda *_a, **_k: "UNAVAILABLE")
    asyncio.run(evaluate("EUR_USD"))

    def _boom(*_a, **_k):
        raise RuntimeError("injected evaluation error")

    # A candle-fetch RuntimeError is an acquisition failure, not a shared-state fault.
    # The unexpected-error audit is proved on the indicator path, after candles exist.
    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", lambda *_a, **_k: raw)
    monkeypatch.setattr("forex_bot.bot_loop.compute_indicators", _boom)
    with pytest.raises(RuntimeError, match="injected"):
        asyncio.run(evaluate("EUR_USD"))

    rows = _read_audit(dest)
    reasons = {row.get("explicit_rejection_reason") for row in rows}
    assert STRATEGY_INACTIVE in reasons
    assert QUANT_AI_REJECTED in reasons
    assert RL_STATE_UNAVAILABLE in reasons
    assert "UNEXPECTED_EVALUATION_ERROR" in reasons
    ai_reject = next(r for r in rows if r.get("explicit_rejection_reason") == QUANT_AI_REJECTED)
    assert ai_reject["ai_vote"] == "BUY"
    assert ai_reject["quant_filter"] == QUANT_AI_REJECTED


def test_audit_rate_limit_still_records_and_fail_closed_new_exposure(monkeypatch, tmp_path):
    from forex_bot.bot_loop import evaluate

    dest = _enable_audit(monkeypatch, tmp_path)
    monkeypatch.setenv("DECISION_SKIP_LOG_INTERVAL_SEC", "60")
    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", lambda *_a, **_k: None)
    asyncio.run(evaluate("EUR_USD"))
    asyncio.run(evaluate("EUR_USD"))
    rows = _read_audit(dest)
    assert len(rows) >= 2
    assert {r.get("explicit_rejection_reason") for r in rows} == {"NO_OHLCV"}

    opened: list[object] = []
    raw = _ohlcv()
    _patch_session_open(monkeypatch, raw)
    monkeypatch.setattr("forex_bot.bot_loop.pre_trade_entry_blocked_reason", lambda: None)
    monkeypatch.setattr("forex_bot.bot_loop.select_strategy", lambda *_a, **_k: ("trend", 50, "legacy"))
    strategies["trend"].active = True
    monkeypatch.setattr("forex_bot.bot_loop.volatility_ok", lambda *_a, **_k: True)

    async def _allow(*_a, **_k):
        return {"allow": True, "direction": "BUY", "confidence": 0.8, "model": "stub"}

    monkeypatch.setattr("forex_bot.bot_loop.ai.vote", _allow)
    monkeypatch.setattr("forex_bot.bot_loop.rl_agent.decide", lambda *_a, **_k: "BUY")
    monkeypatch.setattr("forex_bot.bot_loop.position_sizing", lambda *_a, **_k: 2.0)
    monkeypatch.setattr("forex_bot.bot_loop.cap_position_units", lambda u: u)
    monkeypatch.setattr("forex_bot.bot_loop.notional_pct_of_nav", lambda: 0.0)
    monkeypatch.setattr("forex_bot.bot_loop.pre_close_adjustment", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.bot_loop.open_fill_path", lambda *_a, **_k: "simulate")
    monkeypatch.setattr("forex_bot.bot_loop.effective_paper_trading", lambda: True)
    monkeypatch.setattr("forex_bot.bot_loop.is_live_trading", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.bot_loop.live_window_log_enabled", lambda: False)
    monkeypatch.setattr(
        "forex_bot.bot_loop.notional_cap_decision",
        lambda *_a, **_k: {
            "exceeds": False,
            "existing_gross_usd": 0.0,
            "proposed_add_usd": 1.0,
            "resulting_gross_usd": 1.0,
            "cap_usd": 10000.0,
            "existing_by_symbol": {},
            "portfolio_gross_pct": 0.0,
        },
    )
    monkeypatch.setattr("forex_bot.bot_loop.portfolio_risk_cap_exceeded", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.bot_loop.usd_direction_guard_decision", lambda *_a, **_k: {"exceeds": False})
    monkeypatch.setattr("forex_bot.bot_loop.current_equity", lambda: 10_000.0)
    monkeypatch.setattr("forex_bot.oanda_client.last_account_summary", lambda: {"currency": "GBP", "NAV": 10_000.0})
    monkeypatch.setattr("forex_bot.reconciliation.paper_open_blocked_reason", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.bot_loop.apply_latency", lambda: asyncio.sleep(0, result=0))
    monkeypatch.setattr("forex_bot.bot_loop.apply_market_impact", lambda *_a, **_k: (1.10, 0.0))
    monkeypatch.setattr("forex_bot.bot_loop.apply_execution_costs", lambda *_a, **_k: (1.10, 0.0, 0.0))
    monkeypatch.setattr("forex_bot.bot_loop.open_position", lambda pos: opened.append(pos))
    monkeypatch.setattr(
        "forex_bot.decision_repair.audit.append_record",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
    )
    asyncio.run(evaluate("EUR_USD"))
    assert opened == []
    assert live_order_auth_state() == AUTH_BLOCKED


def test_audit_internal_intent_and_mock_broker_outcomes(monkeypatch, tmp_path):
    from forex_bot.bot_loop import evaluate
    from forex_bot.oanda_exec import OrderCreateClassification, OrderCreateOutcomeError

    dest = _enable_audit(monkeypatch, tmp_path)
    raw = _ohlcv()
    _patch_session_open(monkeypatch, raw)
    monkeypatch.setattr("forex_bot.bot_loop.pre_trade_entry_blocked_reason", lambda: None)
    monkeypatch.setattr("forex_bot.bot_loop.select_strategy", lambda *_a, **_k: ("trend", 50, "legacy"))
    strategies["trend"].active = True
    monkeypatch.setattr("forex_bot.bot_loop.volatility_ok", lambda *_a, **_k: True)

    async def _allow(*_a, **_k):
        return {"allow": True, "direction": "BUY", "confidence": 0.8, "model": "stub"}

    monkeypatch.setattr("forex_bot.bot_loop.ai.vote", _allow)
    monkeypatch.setattr("forex_bot.bot_loop.rl_agent.decide", lambda *_a, **_k: "BUY")
    monkeypatch.setattr("forex_bot.bot_loop.position_sizing", lambda *_a, **_k: 2.0)
    monkeypatch.setattr("forex_bot.bot_loop.cap_position_units", lambda u: u)
    monkeypatch.setattr("forex_bot.bot_loop.notional_pct_of_nav", lambda: 0.0)
    monkeypatch.setattr("forex_bot.bot_loop.pre_close_adjustment", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.bot_loop.open_fill_path", lambda *_a, **_k: "simulate")
    monkeypatch.setattr("forex_bot.bot_loop.effective_paper_trading", lambda: True)
    monkeypatch.setattr("forex_bot.bot_loop.is_live_trading", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.bot_loop.live_window_log_enabled", lambda: False)
    monkeypatch.setattr(
        "forex_bot.bot_loop.notional_cap_decision",
        lambda *_a, **_k: {
            "exceeds": False,
            "existing_gross_usd": 0.0,
            "proposed_add_usd": 1.0,
            "resulting_gross_usd": 1.0,
            "cap_usd": 10000.0,
            "existing_by_symbol": {},
            "portfolio_gross_pct": 0.0,
        },
    )
    monkeypatch.setattr("forex_bot.bot_loop.portfolio_risk_cap_exceeded", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.bot_loop.usd_direction_guard_decision", lambda *_a, **_k: {"exceeds": False})
    monkeypatch.setattr("forex_bot.bot_loop.current_equity", lambda: 10_000.0)
    monkeypatch.setattr("forex_bot.oanda_client.last_account_summary", lambda: {"currency": "GBP", "NAV": 10_000.0})
    monkeypatch.setattr("forex_bot.reconciliation.paper_open_blocked_reason", lambda *_a, **_k: None)

    async def _lat():
        return 0

    monkeypatch.setattr("forex_bot.bot_loop.apply_latency", _lat)
    monkeypatch.setattr("forex_bot.bot_loop.apply_market_impact", lambda *_a, **_k: (1.10, 0.0))
    monkeypatch.setattr("forex_bot.bot_loop.apply_execution_costs", lambda *_a, **_k: (1.10, 0.0, 0.0))
    opened: list[object] = []
    monkeypatch.setattr("forex_bot.bot_loop.open_position", lambda pos: opened.append(pos))
    asyncio.run(evaluate("EUR_USD"))
    assert opened
    internal = _read_audit(dest)[-1]
    assert internal["submission_status"] == "internal_open"
    assert internal["order_submitted"] is False
    assert internal["not_broker_proof"] is True

    class _Geom:
        sl = 1.09
        tp = 1.11
        executable_reference = 1.10

    class _Fetched:
        skip_reason = None
        quote = None
        request_duration_ms = 1

        def fetch_age_ms(self) -> int:
            return 1

    opened.clear()
    dest.write_text("", encoding="utf-8")
    monkeypatch.setattr("forex_bot.bot_loop.open_fill_path", lambda *_a, **_k: "broker")
    monkeypatch.setattr("forex_bot.bot_loop.is_paper_like_kind", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.bot_loop.generate_client_order_id", lambda: "cid-f1")
    monkeypatch.setattr("forex_bot.bot_loop.try_begin_order_submission", lambda **_k: True)
    monkeypatch.setattr("forex_bot.bot_loop.live_broker_geometry_required", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.bot_loop.fetch_entry_pricing", lambda *_a, **_k: _Fetched())
    monkeypatch.setattr(
        "forex_bot.bot_loop.resolve_live_entry_geometry",
        lambda *_a, **_k: (_Geom(), None),
    )
    monkeypatch.setattr("forex_bot.bot_loop.format_entry_geometry_line", lambda *_a, **_k: "geom")

    broker_calls = []

    async def _ack(*_a, **_k):
        broker_calls.append("ack")
        return (1.1001, 2.0, "oid-1", 0.0, 1.0)

    monkeypatch.setattr("forex_bot.oanda_exec.execute_oanda_market_open", _ack)
    monkeypatch.setattr("forex_bot.bot_loop.finalize_order_fill", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.bot_loop.record_fill_quality", lambda **_k: None)
    monkeypatch.setattr("forex_bot.bot_loop.format_entry_fill_geometry_line", lambda **_k: "fill")
    from datetime import datetime, timezone

    from forex_bot.market_provenance import bind_live_frame
    from forex_bot.oanda_client import official_rest_host

    raw.loc[raw.index[-1], "time"] = datetime.now(timezone.utc)
    bind_live_frame(raw, instrument="EUR_USD", host=official_rest_host())
    asyncio.run(evaluate("EUR_USD"))
    ack_rows = _read_audit(dest)
    assert ack_rows
    assert all(not r.get("broker_ack") for r in ack_rows)
    assert all(not r.get("order_submitted") for r in ack_rows)
    assert broker_calls == []

    dest.write_text("", encoding="utf-8")

    async def _fail(*_a, **_k):
        broker_calls.append("fail")
        raise OrderCreateOutcomeError(
            OrderCreateClassification(outcome="rejected", error_message="mock reject"),
            "mock reject",
        )

    monkeypatch.setattr("forex_bot.oanda_exec.execute_oanda_market_open", _fail)
    monkeypatch.setattr("forex_bot.bot_loop.mark_order_failed_or_cancelled", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.bot_loop.record_fill_failure", lambda: None)
    asyncio.run(evaluate("EUR_USD"))
    fail_rows = _read_audit(dest)
    assert fail_rows
    assert all(not r.get("broker_ack") for r in fail_rows)
    assert all(not r.get("order_submitted") for r in fail_rows)
    assert all(r.get("explicit_rejection_reason") != "BROKER_SUBMISSION_FAILED" for r in fail_rows)
    assert broker_calls == []


def test_incomplete_candle_is_rejected(monkeypatch, tmp_path):
    from forex_bot.bot_loop import evaluate
    from forex_bot.decision_skip_log import STALE_OR_INVALID_DATA

    dest = _enable_audit(monkeypatch, tmp_path)
    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", lambda *_a, **_k: _ohlcv(close_nan=True))
    asyncio.run(evaluate("EUR_USD"))
    rows = _read_audit(dest)
    assert rows
    assert rows[-1]["explicit_rejection_reason"] == STALE_OR_INVALID_DATA


def test_deterministic_selector_inactive_and_starvation_limitation(monkeypatch):
    monkeypatch.delenv("HYBRID_EUR_USD", raising=False)
    active = {n: False for n in ALL_NAMES}
    active["trend"] = True
    active["scalp"] = True
    first = select_deterministic("EUR_USD", _atr_df(), active_override=active)
    second = select_deterministic("EUR_USD", _atr_df(), active_override=active)
    assert first.selected == second.selected == "scalp"
    assert last_selection() is first or last_selection().selected == "scalp"
    inact = next(c for c in first.candidates if c.name == "mean_reversion")
    assert inact.eligible is False
    assert inact.reject_reason == "inactive"
    assert "trend" in {c.name for c in first.candidates if c.eligible}


def test_invalid_indicator_inputs_are_rejected(monkeypatch):
    monkeypatch.delenv("HYBRID_EUR_USD", raising=False)
    missing = select_deterministic("EUR_USD", pd.DataFrame({"close": [1.1]}), active_override={"trend": True})
    assert missing.inputs.get("route") in {"missing_atr", "legacy_all"}
    nan = _atr_df()
    nan.loc[nan.index[-1], "atr"] = float("nan")
    monkeypatch.setenv("HYBRID_EUR_USD", "1")
    routed = select_deterministic("EUR_USD", nan, active_override={"scalp": True})
    assert routed.inputs.get("route") in {"atr_invalid", "atr_warmup", "missing_atr"}


def test_selector_does_not_activate_and_flag_off_is_legacy(monkeypatch):
    monkeypatch.setenv("DECISION_REPAIR_DETERMINISTIC_SELECT", "1")
    for strat in strategies.values():
        strat.active = False
    try:
        name, _lb, _h = select_strategy("EUR_USD", _atr_df())
        assert name is None
        assert all(s.active is False for s in strategies.values())
    finally:
        for strat in strategies.values():
            strat.active = False
            strat.authorised_for_live = False
    monkeypatch.delenv("DECISION_REPAIR_DETERMINISTIC_SELECT", raising=False)
    called = {"n": 0}

    def fake_choice(names, p=None):
        called["n"] += 1
        return names[0]

    monkeypatch.setattr("forex_bot.strategy_meta.np.random.choice", fake_choice)
    for strat in strategies.values():
        strat.active = True
    try:
        select_strategy("EUR_USD", _atr_df())
        assert called["n"] >= 1
    finally:
        for strat in strategies.values():
            strat.active = False


def test_rl_partial_write_and_inference_do_not_train(tmp_path, monkeypatch):
    path = tmp_path / "rl.json"
    store = RLStore(path)
    q = {"s": {"BUY": 0.4, "SELL": 0.1, "SKIP": 0.0}}
    store.save(q, alpha=0.15, epsilon=0.0, mode="inference")
    (tmp_path / "rl.json.tmp").write_text("{partial", encoding="utf-8")
    loaded = store.load(expected_fingerprint=config_fingerprint(0.15, 0.0))
    assert loaded is not None
    assert loaded["q"]["s"]["BUY"] == pytest.approx(0.4)
    monkeypatch.setenv("DECISION_REPAIR_RL_REQUIRE_STATE", "1")
    agent = RLAgent(epsilon=0.0)
    agent.q = store.q_table() or {}
    agent.persisted_ok = True
    before = json.dumps(agent.q, sort_keys=True)
    assert agent.decide("s") == "BUY"
    assert json.dumps(agent.q, sort_keys=True) == before
    with pytest.raises(PermissionError):
        RLStore(production_path(), experiment=True).save({}, alpha=0.1, epsilon=0.1, mode="training")
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED


def test_risk_invalid_nav_total_loss_and_no_auth_grant(tmp_path):
    path = tmp_path / "risk.json"
    assert block_reason(equity=None, path=path) == REASON_EQUITY_MISSING
    assert block_reason(equity=float("nan"), path=path) == REASON_EQUITY_INVALID
    assert block_reason(equity=0.0, path=path) == REASON_EQUITY_INVALID
    assert block_reason(equity=100.0, unrealised=None, path=path) == REASON_UNREALISED_MISSING
    path2 = tmp_path / "total.json"
    observe(
        event_id="t1",
        realised_delta=-1.0,
        equity=100.0,
        unrealised=0.0,
        broker_time_utc="2026-06-01T10:00:00+00:00",
        broker_seq=1,
        path=path2,
    )
    assert block_reason(equity=96.0, unrealised=-3.5, path=path2) == REASON_DAILY_TOTAL
    initialise_fail_closed()
    operator_clear_latch(operator_confirmed=True, path=path2)
    assert live_order_auth_state() == AUTH_BLOCKED
    assert pre_trade_entry_blocked_reason() == "live_order_auth_blocked"


def test_health_states_never_permit_trade():
    for name in ALL_NAMES:
        row = evaluate_name(name, pnl=[-1.0] * 40, operator_disabled=True, risk_suspended=False)
        assert row["state"] == OPERATOR_DISABLED
        assert row["may_trade"] is False
        risk = evaluate_name(name, pnl=[1.0] * 40, operator_disabled=False, risk_suspended=True)
        assert risk["state"] == SUSPENDED_RISK
        assert risk["may_trade"] is False
        small = evaluate_name(name, pnl=[1.0] * 5, operator_disabled=False, risk_suspended=False)
        assert small["state"] == INACTIVE
        assert small["evidence"] == "INSUFFICIENT_EVIDENCE"
        perf = evaluate_name(name, pnl=[-1.0] * 40, operator_disabled=False, risk_suspended=False)
        assert perf["state"] == SUSPENDED_PERFORMANCE
        review = evaluate_name(name, pnl=[1.0] * 40, operator_disabled=False, risk_suspended=False)
        assert review["state"] == ELIGIBLE_FOR_OFFLINE_REVIEW
        assert review["may_trade"] is False
        assert review["authorised_for_live"] is False


def test_repair_actions_cannot_grant_live_orders(monkeypatch, tmp_path):
    initialise_fail_closed()
    monkeypatch.setenv("DECISION_REPAIR_AUDIT", "1")
    monkeypatch.setenv("DECISION_REPAIR_HEALTH", "1")
    monkeypatch.setenv("DECISION_REPAIR_ACCOUNT_RISK", "1")
    monkeypatch.setenv("DECISION_REPAIR_RL_PERSIST", "1")
    session = EvaluationAudit.start("EUR_USD")
    session.update(final_decision="order_intent")
    session.finish()
    from forex_bot.decision_repair.health import record_evaluation

    record_evaluation(
        pnl_by_name={"scalp": [1.0] * 40},
        operator_disabled={"scalp": False},
        path=tmp_path / "health.json",
    )
    assert live_order_auth_state() == AUTH_BLOCKED
    assert pre_trade_entry_blocked_reason() == "live_order_auth_blocked"
    assert all(s.active is False for s in strategies.values())
    assert all(getattr(s, "authorised_for_live", False) is False for s in strategies.values())


def test_risk_out_of_order_events_are_applied_as_observed(tmp_path):
    from forex_bot.decision_repair.account_risk import reconstruct_day_realised

    path = tmp_path / "ooo.json"
    observe(
        event_id="later",
        realised_delta=-1.0,
        equity=99.0,
        broker_time_utc="2026-06-01T12:00:00+00:00",
        broker_seq=20,
        path=path,
    )
    observe(
        event_id="earlier",
        realised_delta=-1.5,
        equity=97.5,
        broker_time_utc="2026-06-01T10:00:00+00:00",
        broker_seq=10,
        path=path,
    )
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert reconstruct_day_realised(doc["events"], "2026-06-01") == pytest.approx(-2.5)
    assert [row["event_id"] for row in doc["events"]] == ["earlier", "later"]


def test_offline_harness_scenarios_are_named_and_disconnected():
    assert "authorisation_blocked" in SCENARIOS
    assert "audit_write_failure" in SCENARIOS
    assert "restart_risk_latch" in SCENARIOS
    text = Path("forex_bot/decision_repair/harness.py").read_text(encoding="utf-8")
    assert "oanda_exec" not in text
    assert "OANDA_" not in text


def test_default_off_evaluate_writes_no_audit(monkeypatch, tmp_path):
    from forex_bot.bot_loop import evaluate

    dest = tmp_path / "decisions.jsonl"
    monkeypatch.setenv("DECISION_REPAIR_AUDIT_PATH", str(dest))
    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", lambda *_a, **_k: None)
    asyncio.run(evaluate("EUR_USD"))
    assert dest.exists() is False
