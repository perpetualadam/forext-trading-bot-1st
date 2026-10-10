"""Track A fidelity, Track B isolation, cost model v2. No broker, no live writes."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.live_safety import (
    AUTH_BLOCKED,
    initialise_fail_closed,
    live_order_auth_state,
)
from forex_bot.shadow.compare import compare_track_a_to_fills
from forex_bot.shadow.config import ShadowConfig
from forex_bot.shadow.cost_model import (
    COST_MODEL_VERSION,
    FINANCING_STATUS,
    conservative_half_spread,
    quoted_half_spread,
    table_half_spread,
)
from forex_bot.shadow.engine import ShadowEngine
from forex_bot.shadow.fidelity import FIDELITY_MATRIX, overall_original_fidelity
from forex_bot.shadow.original import (
    ShadowMetaSnapshot,
    evaluate_original_bar,
    quant_stub_vote,
    select_name_argmax,
)
from forex_bot.shadow.protocol import PROSPECTIVE_STARTED, PROTOCOL_FROZEN
from forex_bot.shadow.reasons import ShadowReason
from forex_bot.shadow.tracks import TRACK_B_LABEL, TrackMixError, refuse_mixed_stats
from forex_bot.strategy_meta import strategies

UTC = timezone.utc
SHADOW_ROOT = Path("forex_bot") / "shadow"
FORBIDDEN = {
    "forex_bot.oanda_exec",
    "forex_bot.trading",
    "forex_bot.bot_loop",
    "forex_bot.database",
    "forex_bot.telegram_control",
    "forex_bot.execution",
}


def _bars(n: int = 80) -> pd.DataFrame:
    t0 = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)
    rows = []
    px = 1.10
    t = t0
    for _ in range(n):
        c = px + 0.0002
        rows.append(
            {
                "time": t,
                "open": px,
                "high": max(px, c) + 0.0002,
                "low": min(px, c) - 0.0002,
                "close": c,
                "volume": 100,
            }
        )
        px = c
        t = t + timedelta(minutes=5)
    return pd.DataFrame(rows)


def test_track_a_modules_have_no_broker_imports():
    found: list[str] = []
    for path in SHADOW_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in FORBIDDEN:
                found.append(f"{path.name}:{node.module}")
    assert found == []


def test_quant_stub_is_deterministic():
    buy = quant_stub_vote(1.11, 1.10, 0.001, 0.0004)
    sell = quant_stub_vote(1.09, 1.10, -0.001, 0.0004)
    none = quant_stub_vote(1.10, 1.10, 0.001, 0.0004)
    assert buy["allow"] is True and buy["direction"] == "BUY"
    assert sell["allow"] is True and sell["direction"] == "SELL"
    assert none["allow"] is False
    assert buy["fidelity"] == "EXACT"


def test_rl_missing_q_is_not_reproducible():
    decision = evaluate_original_bar(
        symbol="EUR_USD",
        history=_bars(80),
        bar_time=datetime(2026, 9, 16, 16, 0, tzinfo=UTC),
        q_table=None,
    )
    assert decision.track == "A"
    assert decision.reason == ShadowReason.NOT_REPRODUCIBLE
    assert decision.rl_action is None
    assert decision.fidelity_overall == "NO"


def test_rl_with_matching_q_is_partial_not_exact(monkeypatch):
    monkeypatch.setattr(
        "forex_bot.shadow.original.rl_decide",
        lambda state, q_table: ("BUY", ShadowReason.PARTIALLY_REPRODUCIBLE),
    )
    decision = evaluate_original_bar(
        symbol="EUR_USD",
        history=_bars(80),
        bar_time=datetime(2026, 9, 16, 16, 0, tzinfo=UTC),
        q_table={"x": {"BUY": 1.0, "SELL": 0.0, "SKIP": 0.0}},
    )
    if decision.quant_allow:
        assert decision.fidelity_overall == "PARTIAL"
        assert decision.reason != ShadowReason.EXPERIMENTAL_HEURISTIC
        assert decision.label != TRACK_B_LABEL


def test_track_a_does_not_activate_live_strategies():
    before = {n: (s.active, s.authorised_for_live) for n, s in strategies.items()}
    evaluate_original_bar(
        symbol="EUR_USD",
        history=_bars(50),
        bar_time=datetime(2026, 9, 16, 14, 0, tzinfo=UTC),
        snap=ShadowMetaSnapshot(active={n: True for n in before}),
    )
    after = {n: (s.active, s.authorised_for_live) for n, s in strategies.items()}
    assert after == before


def test_track_b_outputs_are_experimental_heuristic():
    engine = ShadowEngine(cfg=ShadowConfig(enabled=True, min_bars=40, scalp_lookback=20, swing_lookback=30))
    df = _bars(55)
    engine.process_symbol_bar(
        symbol="EUR_USD",
        history=df,
        bar_time=df.iloc[-1]["time"],
        fill_open=float(df.iloc[-1]["open"]),
        gbp_usd_mid=1.35,
    )
    assert engine.traces
    assert all(t.track == "B" for t in engine.traces)
    assert all(str(t.label).startswith("EXPERIMENTAL_HEURISTIC") for t in engine.traces)


def test_refuse_mixed_track_stats():
    with pytest.raises(TrackMixError):
        refuse_mixed_stats(["A", "B"])


def test_comparison_without_overlapping_keys_has_no_agreement_rate():
    report = compare_track_a_to_fills(
        [{"track": "A", "symbol": "EUR_USD", "time_key": "t1", "strategy": "trend", "direction": "BUY"}],
        [{"symbol": "EUR_USD", "time_key": "t2", "strategy": "trend", "direction": "BUY"}],
    )
    assert report.valid_reference_decisions == 0
    assert report.missing_references >= 1
    assert report.agreement_rate is None


def test_cost_model_v2_is_not_favourable_vs_table():
    assert COST_MODEL_VERSION == "shadow_cost_v2"
    assert conservative_half_spread("EUR_USD") >= table_half_spread("EUR_USD")
    assert conservative_half_spread("USD_JPY") >= table_half_spread("USD_JPY")
    assert quoted_half_spread(1.1000, 1.1002) == pytest.approx(0.0001)
    assert FINANCING_STATUS == "UNAVAILABLE"


def test_argmax_is_deterministic():
    assert select_name_argmax({"trend": 0.5, "scalp": 0.5}) == "scalp"


def test_overall_fidelity_is_no():
    assert overall_original_fidelity() == "NO"
    assert FIDELITY_MATRIX["rl_decide"]["offline"] == "UNAVAILABLE"


def test_protocol_not_frozen():
    assert PROTOCOL_FROZEN is False
    assert PROSPECTIVE_STARTED is False


def test_track_a_failure_leaves_live_gate():
    initialise_fail_closed()
    decision = evaluate_original_bar(
        symbol="EUR_USD",
        history=pd.DataFrame({"time": [datetime.now(UTC)]}),
        bar_time=datetime.now(UTC),
    )
    assert decision.reason == ShadowReason.INSUFFICIENT_DATA
    assert live_order_auth_state() == AUTH_BLOCKED
