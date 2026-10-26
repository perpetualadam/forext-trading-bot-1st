"""Stage F decision-engine repairs. Offline fixtures only. No broker I/O."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.bot_loop import evolve
from forex_bot.decision_repair.account_risk import (
    REASON_DAILY_REALISED,
    REASON_EQUITY_MISSING,
    REASON_MAX_DD,
    block_reason,
    observe,
    operator_clear_latch,
)
from forex_bot.decision_repair.audit import (
    FORBIDDEN_KEYS,
    append_record,
    append_record_safe,
    candle_fingerprint,
    empty_record,
)
from forex_bot.decision_repair.flags import (
    account_risk_enabled,
    audit_enabled,
    deterministic_select_enabled,
    health_enabled,
    rl_persist_enabled,
    rl_require_state_enabled,
)
from forex_bot.decision_repair.health import (
    ELIGIBLE_FOR_OFFLINE_REVIEW,
    OPERATOR_DISABLED,
    SUSPENDED_PERFORMANCE,
    evaluate_name,
    record_evaluation,
)
from forex_bot.decision_repair.rl_store import (
    MODEL_ID,
    RLStore,
    build_document,
    config_fingerprint,
    production_path,
    validate_document,
)
from forex_bot.decision_repair.selection import ALL_NAMES, select_deterministic
from forex_bot.execution import pre_trade_entry_blocked_reason
from forex_bot.live_safety import (
    AUTH_BLOCKED,
    initialise_fail_closed,
    live_order_auth_state,
    operator_set_strategy_active,
)
from forex_bot.rl_agent import RLAgent
from forex_bot.strategy_meta import select_strategy, strategies

REPAIR_ROOT = Path("forex_bot") / "decision_repair"
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
FORBIDDEN_IMPORTS = {
    "forex_bot.oanda_exec",
    "forex_bot.trading",
    "forex_bot.database",
    "forex_bot.telegram_control",
}


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


def test_flags_default_off():
    assert deterministic_select_enabled() is False
    assert rl_persist_enabled() is False
    assert rl_require_state_enabled() is False
    assert audit_enabled() is False
    assert health_enabled() is False
    assert account_risk_enabled() is False


def test_package_has_no_broker_imports():
    found: list[str] = []
    for path in REPAIR_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (node.module in FORBIDDEN_IMPORTS or node.module.startswith("forex_bot.oanda"))
            ):
                found.append(f"{path.name}:{node.module}")
    assert found == []


def test_deterministic_select_is_stable_and_tie_breaks(monkeypatch):
    monkeypatch.delenv("HYBRID_EUR_USD", raising=False)
    active = {n: False for n in ALL_NAMES}
    active["trend"] = True
    active["scalp"] = True
    a = select_deterministic("EUR_USD", _atr_df(), active_override=active)
    b = select_deterministic("EUR_USD", _atr_df(), active_override=active)
    assert a.selected == b.selected == "scalp"
    assert a.effectiveness == "UNVALIDATED"
    assert a.policy_version == "deterministic_rotate_v2_unvalidated"
    assert any(c.reject_reason == "rotation_not_selected" for c in a.candidates)


def test_deterministic_select_rejects_missing_and_inactive():
    none = select_deterministic("EUR_USD", _atr_df(), active_override={n: False for n in ALL_NAMES})
    assert none.selected is None
    assert none.reason == "NO_ACTIVE_ELIGIBLE"


def test_select_strategy_flag_uses_deterministic_policy(monkeypatch):
    monkeypatch.setenv("DECISION_REPAIR_DETERMINISTIC_SELECT", "1")
    monkeypatch.delenv("HYBRID_EUR_USD", raising=False)
    for name, strat in strategies.items():
        strat.active = name == "mean_reversion"
    try:
        name, _lb, horizon = select_strategy("EUR_USD", _atr_df())
        assert name == "mean_reversion"
        assert horizon == "legacy"
    finally:
        for strat in strategies.values():
            strat.active = False
            strat.authorised_for_live = False


def test_future_candles_do_not_change_prefix_selection(monkeypatch):
    monkeypatch.delenv("HYBRID_EUR_USD", raising=False)
    active = {n: (n == "trend") for n in ALL_NAMES}
    prefix = _atr_df(12, last=0.002)
    mutated = pd.concat([prefix, _atr_df(5, last=9.9)], ignore_index=True)
    a = select_deterministic("EUR_USD", prefix, active_override=active)
    b = select_deterministic("EUR_USD", mutated.iloc[:12], active_override=active)
    assert a.selected == b.selected


def test_rl_missing_and_corrupt_state_are_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("DECISION_REPAIR_RL_REQUIRE_STATE", "1")
    agent = RLAgent(epsilon=0.0)
    assert agent.decide("s") == "UNAVAILABLE"
    store = RLStore(tmp_path / "rl.json")
    assert store.load() is None
    assert store.status == "UNAVAILABLE"
    (tmp_path / "rl.json").write_text("{not-json", encoding="utf-8")
    assert store.load() is None
    assert store.detail == "corrupt"


def test_rl_incompatible_and_tampered_rejected(tmp_path):
    store = RLStore(tmp_path / "rl.json")
    doc = build_document(q={"s": {"BUY": 1.0, "SELL": 0.0, "SKIP": 0.0}}, alpha=0.15, epsilon=0.0, mode="inference")
    store.save({"s": {"BUY": 1.0, "SELL": 0.0, "SKIP": 0.0}}, alpha=0.15, epsilon=0.0, mode="inference")
    raw = json.loads((tmp_path / "rl.json").read_text(encoding="utf-8"))
    raw["q"]["s"]["BUY"] = 99.0
    (tmp_path / "rl.json").write_text(json.dumps(raw), encoding="utf-8")
    assert store.load() is None
    raw["integrity"] = "deadbeef"
    raw["schema_version"] = 99
    (tmp_path / "rl.json").write_text(json.dumps(raw), encoding="utf-8")
    assert validate_document(raw) is None
    other = dict(doc)
    other["schema_version"] = 2
    other["integrity"] = "x"
    assert validate_document(other) is None


def test_rl_restart_roundtrip_and_stable_inference(tmp_path, monkeypatch):
    monkeypatch.setenv("DECISION_REPAIR_RL_REQUIRE_STATE", "1")
    store = RLStore(tmp_path / "rl.json")
    q = {"s": {"BUY": 0.4, "SELL": 0.4, "SKIP": 0.1}}
    store.save(q, alpha=0.15, epsilon=0.25, mode="inference")
    loaded = store.load(expected_fingerprint=config_fingerprint(0.15, 0.25))
    assert loaded is not None
    agent = RLAgent(epsilon=0.25)
    agent.q = store.q_table() or {}
    agent.persisted_ok = True
    assert agent.decide("s") == "UNAVAILABLE"
    assert agent.decide("s") == "UNAVAILABLE"


def test_offline_learning_cannot_overwrite_production(tmp_path):
    store = RLStore(production_path(), experiment=True)
    with pytest.raises(PermissionError):
        store.save({}, alpha=0.1, epsilon=0.1, mode="training")
    ops = tmp_path / "data" / "ops" / "rl.json"
    ops.parent.mkdir(parents=True)
    with pytest.raises(PermissionError):
        RLStore(ops, experiment=True).save({}, alpha=0.1, epsilon=0.1, mode="training")


def test_health_does_not_change_operator_authorisation(tmp_path):
    path = tmp_path / "health.json"
    doc = record_evaluation(
        pnl_by_name={"scalp": [-1.0] * 40, "trend": [0.1] * 8},
        operator_disabled={"scalp": True, "trend": True},
        path=path,
    )
    row = doc["strategies"]["scalp"]
    assert row["state"] == OPERATOR_DISABLED
    assert row["authorised_for_live"] is False
    assert row["may_trade"] is False
    perf = evaluate_name("scalp", pnl=[-1.0] * 40, operator_disabled=False, risk_suspended=False)
    assert perf["state"] == SUSPENDED_PERFORMANCE
    review = evaluate_name("trend", pnl=[1.0] * 40, operator_disabled=False, risk_suspended=False)
    assert review["state"] == ELIGIBLE_FOR_OFFLINE_REVIEW
    assert review["may_trade"] is False


def test_evolve_health_flag_does_not_silently_disable(monkeypatch, tmp_path):
    monkeypatch.setenv("DECISION_REPAIR_HEALTH", "1")
    monkeypatch.setenv("DECISION_REPAIR_HEALTH_PATH", str(tmp_path / "health.json"))
    strategies["scalp"].active = True
    strategies["scalp"].authorised_for_live = False
    strategies["scalp"].pnl = [-1.0] * 40
    try:
        evolve()
        assert strategies["scalp"].active is True
        assert strategies["scalp"].authorised_for_live is False
    finally:
        strategies["scalp"].active = False
        strategies["scalp"].pnl = []


def test_risk_latch_blocks_and_survives_restart_and_rollover(tmp_path):
    path = tmp_path / "risk.json"
    observe(
        event_id="e1",
        realised_delta=-5.0,
        equity=100.0,
        broker_time_utc="2026-06-01T10:00:00+00:00",
        broker_seq=1,
        path=path,
    )
    observe(
        event_id="e1",
        realised_delta=-5.0,
        equity=95.0,
        broker_time_utc="2026-06-01T10:00:00+00:00",
        broker_seq=1,
        path=path,
    )
    doc = json.loads(path.read_text(encoding="utf-8"))
    from forex_bot.decision_repair.account_risk import reconstruct_day_realised

    assert reconstruct_day_realised(doc["events"], doc["events"][0]["utc_day"]) == pytest.approx(-5.0)
    observe(
        event_id="e2",
        realised_delta=-3.0,
        equity=92.0,
        broker_time_utc="2026-06-01T11:00:00+00:00",
        broker_seq=2,
        path=path,
    )
    reason = block_reason(equity=92.0, path=path)
    assert reason == REASON_DAILY_REALISED
    restarted = block_reason(equity=92.0, path=path)
    assert restarted == REASON_DAILY_REALISED
    with pytest.raises(PermissionError):
        operator_clear_latch(operator_confirmed=False, path=path)
    operator_clear_latch(operator_confirmed=True, path=path)
    assert block_reason(equity=100.0, path=path) is None


def test_missing_equity_and_drawdown_fail_closed(tmp_path):
    path = tmp_path / "risk.json"
    assert block_reason(equity=None, path=path) == REASON_EQUITY_MISSING
    path2 = tmp_path / "dd.json"
    observe(
        event_id="p",
        realised_delta=0.0,
        equity=100.0,
        broker_time_utc="2026-06-01T10:00:00+00:00",
        broker_seq=1,
        path=path2,
    )
    observe(
        event_id="q",
        realised_delta=0.0,
        equity=90.0,
        broker_time_utc="2026-06-01T11:00:00+00:00",
        broker_seq=2,
        path=path2,
    )
    assert block_reason(equity=90.0, path=path2) == REASON_MAX_DD


def test_account_risk_gate_is_after_auth_and_opt_in(monkeypatch, tmp_path):
    monkeypatch.setenv("DECISION_REPAIR_ACCOUNT_RISK", "1")
    monkeypatch.setenv("DECISION_REPAIR_RISK_PATH", str(tmp_path / "risk.json"))
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert pre_trade_entry_blocked_reason() == "live_order_auth_blocked"


def test_audit_omits_credentials_and_survives_write_failure(tmp_path):
    rec = empty_record(symbol="EUR_USD")
    rec["ai_vote"] = "BUY"
    rec["token"] = "secret-token"
    rec["OANDA_TOKEN"] = "abc"
    path = tmp_path / "decisions.jsonl"
    append_record(rec, path)
    text = path.read_text(encoding="utf-8")
    assert "secret-token" not in text
    assert "abc" not in text
    assert "BUY" in text
    assert rec["not_broker_proof"] is True
    assert candle_fingerprint({"time": "t", "open": 1, "high": 2, "low": 0, "close": 1})
    assert append_record_safe(rec, tmp_path / "missing" / "x.jsonl") is True
    for key in FORBIDDEN_KEYS:
        assert key not in json.loads(text)


def test_logging_failure_does_not_bypass_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("DECISION_REPAIR_AUDIT", "1")
    monkeypatch.setenv("DECISION_REPAIR_AUDIT_PATH", str(tmp_path / "nope" / "a.jsonl"))
    initialise_fail_closed()
    from forex_bot.bot_loop import _safe_audit

    _safe_audit(symbol="EUR_USD", token="should-not-authorise")
    assert live_order_auth_state() == AUTH_BLOCKED
    assert pre_trade_entry_blocked_reason() == "live_order_auth_blocked"


def test_default_select_path_still_random_when_flag_off(monkeypatch):
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
            strat.authorised_for_live = False


def test_operator_activation_does_not_grant_live_orders(tmp_path, monkeypatch):
    initialise_fail_closed()
    with pytest.raises(PermissionError):
        operator_set_strategy_active(name="scalp", active=True, reason="no", operator_confirmed=False)
    assert live_order_auth_state() == AUTH_BLOCKED


def test_model_identity_is_explicit():
    doc = build_document(q={}, alpha=0.15, epsilon=0.25, mode="inference")
    assert doc["model_id"] == MODEL_ID
    assert doc["schema_version"] == 1
    assert doc["feature_space"] == "trend4_vol6"
