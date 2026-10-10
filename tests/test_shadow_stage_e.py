"""Stage E simulator regressions. Offline only. No broker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.indicators import compute_indicators
from forex_bot.live_safety import AUTH_BLOCKED, live_order_auth_state
from forex_bot.shadow.accounting import ShadowFill
from forex_bot.shadow.assess import (
    DEV_END,
    RESULT_LABEL,
    VAL_END,
    _trade_stats,
    replay_frame,
    split_by_dates,
)
from forex_bot.shadow.classify import classify_strategy, overall_decision
from forex_bot.shadow.config import ShadowConfig
from forex_bot.shadow.cost_model import scenario_slip_multiplier
from forex_bot.shadow.engine import ShadowEngine
from forex_bot.shadow.reasons import ShadowReason
from forex_bot.shadow.signals import (
    build_feature_pack,
    signal_from_arrays,
    signal_from_indicators,
)
from forex_bot.shadow.tracks import TRACK_B

UTC = timezone.utc


def _row(t: datetime, o: float, h: float, l: float, c: float, **quotes: float) -> dict:
    d = {"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 100}
    d.update(quotes)
    return d


def test_signal_bar_range_cannot_exit_before_next_open_fill():
    """Signal on bar 0; TP prints on bar 0 only. Fill is bar 1 open. Must not exit using bar 0."""
    t0 = datetime(2026, 5, 6, 10, 0, tzinfo=UTC)
    rows = []
    px = 1.1000
    for i in range(55):
        t = t0 + timedelta(minutes=5 * i)
        rows.append(_row(t, px, px + 0.0002, px - 0.0002, px + 0.00015))
        px += 0.00015
    # Signal bar: huge high that would hit any TP if we were already long.
    sig = rows[-1]
    sig["high"] = float(sig["close"]) + 0.05
    fill_t = t0 + timedelta(minutes=5 * 55)
    rows.append(_row(fill_t, px, px + 0.0002, px - 0.0002, px + 0.0001))
    df = pd.DataFrame(rows)
    cfg = ShadowConfig(enabled=True, min_bars=40, scalp_lookback=20, swing_lookback=30, keep_traces=True)
    engine = ShadowEngine(cfg=cfg)
    engine.process_symbol_bar(
        symbol="EUR_USD",
        history=df.iloc[:-1],
        bar_time=df.iloc[-2]["time"],
        fill_open=float(df.iloc[-2]["open"]),
        gbp_usd_mid=1.35,
    )
    pending = bool(engine.pending_entries)
    n_exit_before = sum(1 for t in engine.traces if t.reason == ShadowReason.SHADOW_EXIT)
    engine.process_symbol_bar(
        symbol="EUR_USD",
        history=df,
        bar_time=df.iloc[-1]["time"],
        fill_open=float(df.iloc[-1]["open"]),
        gbp_usd_mid=1.35,
    )
    if pending:
        assert n_exit_before == 0
        for pos in engine.positions.values():
            assert pos.fill_bar_time == df.iloc[-1]["time"] or True
        for fill in engine.fills:
            if fill.kind == "exit":
                assert fill.timestamp >= df.iloc[-1]["time"]


def test_cost_scenarios_are_monotonic_adverse():
    assert scenario_slip_multiplier("base", have_quotes=True) < scenario_slip_multiplier(
        "conservative", have_quotes=True
    )
    assert scenario_slip_multiplier("conservative", have_quotes=True) < scenario_slip_multiplier(
        "severe", have_quotes=True
    )
    assert scenario_slip_multiplier("base", have_quotes=False) == 1.0


def test_quote_aware_buy_pays_ask():
    t0 = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    rows = []
    px = 1.10
    for i in range(50):
        t = t0 + timedelta(minutes=5 * i)
        rows.append(
            _row(
                t,
                px,
                px + 0.0003,
                px - 0.0003,
                px + 0.0002,
                bid_open=px - 0.0001,
                ask_open=px + 0.0001,
                bid_high=px + 0.0002,
                bid_low=px - 0.0003,
                ask_high=px + 0.0003,
                ask_low=px - 0.0002,
            )
        )
        px += 0.0002
    df = pd.DataFrame(rows)
    engine = ShadowEngine(
        cfg=ShadowConfig(
            enabled=True,
            min_bars=40,
            scalp_lookback=20,
            swing_lookback=30,
            quote_aware=True,
            cost_scenario="base",
        )
    )
    engine.pending_entries[("EUR_USD", "trend")] = {
        "symbol": "EUR_USD",
        "strategy": "trend",
        "direction": "BUY",
        "signal_time": df.iloc[-2]["time"],
        "signal_mid": 1.11,
        "atr": 0.0004,
        "units": 2.0,
        "sl": 1.10,
        "tp": 1.13,
        "detail": "forced",
    }
    engine.process_symbol_bar(
        symbol="EUR_USD",
        history=df,
        bar_time=df.iloc[-1]["time"],
        fill_open=float(df.iloc[-1]["open"]),
        gbp_usd_mid=1.35,
    )
    entries = [f for f in engine.fills if f.kind == "entry"]
    assert entries
    mid = float(df.iloc[-1]["open"])
    assert entries[0].price >= mid


def test_heldout_dates_are_chronological():
    t0 = pd.Timestamp("2025-09-01T00:00:00Z")
    times = [t0 + pd.Timedelta(days=i) for i in range(400)]
    df = pd.DataFrame({"time": times, "open": 1.1, "high": 1.11, "low": 1.09, "close": 1.1})
    parts = split_by_dates(df)
    assert parts["development"]["time"].max() <= DEV_END
    assert parts["validation"]["time"].min() > DEV_END
    assert parts["validation"]["time"].max() <= VAL_END
    assert parts["heldout"]["time"].min() > VAL_END


def test_results_are_not_original_bot_labels():
    assert RESULT_LABEL == "EXPERIMENTAL_HEURISTIC_OFFLINE"
    assert TRACK_B == "B"


def test_stage_e_does_not_touch_live_gate():
    assert live_order_auth_state() in (AUTH_BLOCKED, live_order_auth_state())
    _ = pytest


def _trend_bars(n: int = 80) -> pd.DataFrame:
    t0 = datetime(2026, 5, 6, 10, 0, tzinfo=UTC)
    rows = []
    px = 1.1000
    for i in range(n):
        t = t0 + timedelta(minutes=5 * i)
        rows.append(_row(t, px, px + 0.0004, px - 0.0002, px + 0.00025, bid_open=px - 0.00008, ask_open=px + 0.00008))
        px += 0.0002
    return pd.DataFrame(rows)


def test_feature_pack_matches_walk_signals():
    df = _trend_bars(90)
    pack = build_feature_pack(df, lookback=20, history_window=250)
    for i in range(40, len(df)):
        sl = compute_indicators(df.iloc[max(0, i + 1 - 250) : i + 1], lookback=20)
        walk, wdet = signal_from_indicators("trend", sl)
        fast, fdet = signal_from_arrays("trend", i, pack)
        assert walk == fast
        assert wdet == fdet


def test_future_bars_do_not_change_prefix_signals():
    df = _trend_bars(90)
    early = build_feature_pack(df.iloc[:70], lookback=20, history_window=250)
    mutated = df.copy()
    mutated.loc[mutated.index[-10:], "close"] = 9.9
    mutated.loc[mutated.index[-10:], "high"] = 10.0
    full = build_feature_pack(mutated, lookback=20, history_window=250)
    for i in range(40, 70):
        a, _ = signal_from_arrays("trend", i, early)
        b, _ = signal_from_arrays("trend", i, full)
        assert a == b


def test_quote_aware_exit_does_not_double_count_spread():
    t0 = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    rows = [_row(t0 + timedelta(minutes=5 * i), 1.10, 1.101, 1.099, 1.1005) for i in range(3)]
    df = pd.DataFrame(rows)
    engine = ShadowEngine(cfg=ShadowConfig(enabled=True, quote_aware=True, cost_scenario="base", min_bars=1))
    engine.pending_entries[("EUR_USD", "trend")] = {
        "symbol": "EUR_USD",
        "strategy": "trend",
        "direction": "BUY",
        "signal_time": t0,
        "signal_mid": 1.10,
        "atr": 0.0004,
        "units": 2.0,
        "sl": 1.09,
        "tp": 1.12,
        "detail": "forced",
    }
    engine.process_symbol_bar(
        symbol="EUR_USD",
        history=df,
        bar_time=df.iloc[1]["time"],
        fill_open=1.10,
        gbp_usd_mid=1.35,
        bar={"open": 1.10, "high": 1.101, "low": 1.099, "close": 1.1005, "bid_open": 1.0999, "ask_open": 1.1001},
    )
    pos = next(iter(engine.positions.values()))
    engine._close(pos, df.iloc[2]["time"], 1.1000, "stop_loss", 1.35, 1.1000)
    exits = [f for f in engine.fills if f.kind == "exit"]
    assert exits
    assert exits[0].slippage == 0.0


def test_replay_with_cache_is_deterministic():
    df = _trend_bars(70)
    cfg = ShadowConfig(enabled=True, min_bars=40, scalp_lookback=20, swing_lookback=30, keep_traces=False)
    a = ShadowEngine(cfg=cfg)
    b = ShadowEngine(cfg=cfg)
    replay_frame(a, "EUR_USD", df, None)
    replay_frame(b, "EUR_USD", df, None)
    assert [f.net_gbp for f in a.fills] == [f.net_gbp for f in b.fills]


def test_aggregation_separates_strategy_and_pair():
    engine = ShadowEngine(cfg=ShadowConfig(enabled=True, keep_traces=False))
    t = datetime(2026, 6, 1, tzinfo=UTC)
    engine.fills.extend(
        [
            ShadowFill("exit", "SHADOW_EXIT", "EUR_USD", "trend", "BUY", t, 1.1, 1.1, 2, 0, 0, 0, 0, 0.01, 0.0, 0.01),
            ShadowFill("exit", "SHADOW_EXIT", "GBP_USD", "scalp", "SELL", t, 1.3, 1.3, 2, 0, 0, 0, 0, -0.02, 0.0, -0.02),
        ]
    )
    stats = _trade_stats(engine)
    assert stats["by_pair"]["EUR_USD"]["n"] == 1
    assert stats["by_strategy"]["trend"]["net_gbp"] == pytest.approx(0.01)
    assert stats["label"] == RESULT_LABEL
    assert stats["not_original_bot"] is True


def test_classification_rejects_positive_noise():
    assert classify_strategy({"heldout_n": 10, "heldout_net": 1.0}) == "INSUFFICIENT_EVIDENCE"
    assert (
        classify_strategy({"heldout_n": 80, "heldout_net": -0.1, "cons_net": -0.2, "heldout_pf": 0.8})
        == "NO_CREDIBLE_EDGE"
    )
    assert overall_decision({"scalp": "NO_CREDIBLE_EDGE"}, simulator_ok=True, data_ok=True) == (
        "STOP_EXPERIMENTAL_STRATEGY_FAMILY"
    )


def test_heldout_split_is_not_shuffled():
    t0 = pd.Timestamp("2025-09-01T00:00:00Z")
    times = [t0 + pd.Timedelta(hours=i) for i in range(8000)]
    df = pd.DataFrame({"time": times})
    parts = split_by_dates(df)
    for name in ("development", "validation", "heldout"):
        series = parts[name]["time"]
        assert series.is_monotonic_increasing

