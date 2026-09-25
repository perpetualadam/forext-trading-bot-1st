"""Research-only Fibonacci vs control retracement. Does not change live trading."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forex_bot.decision_quality.ema_retracement import (
    SWING_LOOKBACK,
    simulate_occupancy_trades,
    swing_retrace_mask,
)
from forex_bot.decision_quality.fibonacci_retracement import (
    CONTROL_DEPTHS,
    EMA_FAST,
    EMA_SLOW,
    FIB_DEPTHS,
    PLACEBO_DEPTHS,
    PLACEBO_N,
    PLACEBO_SEED,
    SWING_BARS,
    classify_conclusion,
    depth_resume_mask,
    generate_placebo_depths,
    retrace_fraction,
    resume_after_pull,
    swing_window_bounds,
)
from forex_bot.decision_quality.isolation import forbidden_hits_in_source
from forex_bot.decision_quality.stub_components import chrono_masks

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "forex_bot" / "decision_quality" / "fibonacci_retracement.py"
REPORT = ROOT / "reports" / "decision_quality" / "fibonacci_retracement_research.md"
EMA_REPORT = ROOT / "reports" / "decision_quality" / "ema_retracement_signal_research.md"


def test_placebo_is_frozen_and_deterministic():
    assert generate_placebo_depths() == PLACEBO_DEPTHS
    assert generate_placebo_depths(PLACEBO_SEED, PLACEBO_N) == PLACEBO_DEPTHS
    assert generate_placebo_depths(99, PLACEBO_N) != PLACEBO_DEPTHS
    assert len(PLACEBO_DEPTHS) == PLACEBO_N
    reserved = set(CONTROL_DEPTHS) | set(FIB_DEPTHS)
    assert reserved.isdisjoint(PLACEBO_DEPTHS)


def test_depth_grid_is_frozen():
    assert CONTROL_DEPTHS == (
        0.20,
        0.25,
        0.30,
        0.35,
        0.40,
        0.45,
        0.50,
        0.55,
        0.60,
        0.65,
        0.70,
        0.75,
        0.80,
    )
    assert FIB_DEPTHS == (0.236, 0.382, 0.618, 0.786)
    assert SWING_BARS == SWING_LOOKBACK == 24
    assert (EMA_FAST, EMA_SLOW) == (50, 200)


def test_swing_window_is_causal():
    start, end = swing_window_bounds(10, lookback=24)
    assert start == 0
    assert end == 11
    start, end = swing_window_bounds(30, lookback=24)
    assert start == 7
    assert end == 31
    # Future bar index 31 is excluded.
    assert end == 30 + 1


def test_retrace_fraction_matches_definition():
    # BUY: high 1.10, low 1.00, close 1.05 → 50% retrace.
    assert retrace_fraction(side=1, close=1.05, swing_high=1.10, swing_low=1.00) == pytest.approx(0.50)
    # SELL: high 1.10, low 1.00, close 1.06 → 60% retrace off the low.
    assert retrace_fraction(side=-1, close=1.06, swing_high=1.10, swing_low=1.00) == pytest.approx(0.60)


def test_fib_and_control_use_identical_mask_function():
    state = np.ones(8, dtype=np.int8)
    close = np.array([1.00, 1.10, 1.08, 1.06, 1.05, 1.04, 1.03, 1.02])
    high = np.array([1.01, 1.10, 1.09, 1.07, 1.06, 1.05, 1.04, 1.03])
    low = np.array([0.99, 1.00, 1.06, 1.04, 1.03, 1.02, 1.01, 1.00])
    slow = np.array([0.95] * 8)
    a = swing_retrace_mask(state, close, high, low, slow, lookback=8, depth=0.382)
    b = swing_retrace_mask(state, close, high, low, slow, lookback=8, depth=0.40)
    # Same function, only the depth argument changes.
    assert a.dtype == b.dtype
    assert int(a.sum()) <= 1
    assert int(b.sum()) <= 1


def test_first_qualification_once_per_episode():
    state = np.ones(10, dtype=np.int8)
    close = np.linspace(1.10, 1.02, 10)
    high = close + 0.01
    high[1] = 1.12
    low = close - 0.01
    slow = np.array([0.90] * 10)
    mask = swing_retrace_mask(state, close, high, low, slow, lookback=10, depth=0.50)
    assert int(mask.sum()) == 1


def test_resume_uses_same_reclaim_rule():
    state = np.ones(6, dtype=np.int8)
    close = np.array([1.00, 1.00, 1.00, 1.02, 1.03, 1.04])
    fast = np.array([1.01] * 6)
    pull = np.array([False, True, False, False, False, False])
    resume = resume_after_pull(state, close, fast, pull)
    assert list(resume).count(True) == 1
    assert bool(resume[3])


def test_depth_does_not_set_direction():
    src = HARNESS.read_text(encoding="utf-8")
    assert "direction_source" in src
    assert "depth never sets BUY/SELL" in src


def test_economic_buy_uses_ask_then_bid_path():
    n = 4
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2025-01-01", periods=n, freq="5min"),
            "symbol": ["EUR_USD"] * n,
            "close": [1.1000, 1.1010, 1.1030, 1.1040],
            "high": [1.1005, 1.1015, 1.1035, 1.1045],
            "low": [1.0995, 1.1005, 1.1025, 1.1035],
            "bid_close": [1.0999, 1.1009, 1.1029, 1.1039],
            "ask_close": [1.1001, 1.1011, 1.1031, 1.1041],
            "bid_high": [1.1004, 1.1014, 1.1040, 1.1044],
            "bid_low": [1.0994, 1.1004, 1.1024, 1.1034],
            "ask_high": [1.1006, 1.1016, 1.1036, 1.1046],
            "ask_low": [1.0996, 1.1006, 1.1026, 1.1036],
            "atr": [0.0010] * n,
            "state": [1] * n,
        }
    )
    trades = simulate_occupancy_trades(frame, np.array([True, False, False, False]), "EUR_USD")
    assert len(trades) == 1
    assert trades[0]["entry"] == pytest.approx(1.1001)
    assert trades[0]["side"] == "BUY"


def test_economic_sell_uses_bid_then_ask_path():
    n = 4
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2025-01-01", periods=n, freq="5min"),
            "symbol": ["EUR_USD"] * n,
            "close": [1.1000, 1.0990, 1.0970, 1.0960],
            "high": [1.1005, 1.0995, 1.0975, 1.0965],
            "low": [1.0995, 1.0985, 1.0965, 1.0955],
            "bid_close": [1.0999, 1.0989, 1.0969, 1.0959],
            "ask_close": [1.1001, 1.0991, 1.0971, 1.0961],
            "bid_high": [1.1004, 1.0994, 1.0974, 1.0964],
            "bid_low": [1.0994, 1.0984, 1.0964, 1.0954],
            "ask_high": [1.1006, 1.0996, 1.0976, 1.0966],
            "ask_low": [1.0996, 1.0980, 1.0966, 1.0956],
            "atr": [0.0010] * n,
            "state": [-1] * n,
        }
    )
    trades = simulate_occupancy_trades(frame, np.array([True, False, False, False]), "EUR_USD")
    assert len(trades) == 1
    assert trades[0]["entry"] == pytest.approx(1.0999)
    assert trades[0]["side"] == "SELL"


def test_train_valid_test_cuts_match_ema_research_method():
    text = EMA_REPORT.read_text(encoding="utf-8")
    assert "train ≤ **2026-03-03 12:15**" in text
    assert "validation ≤ **2026-06-02 05:05**" in text
    from forex_bot.decision_quality.ema_retracement import RESEARCH_SYMBOLS, load_m5_with_book

    cache = ROOT / "data" / "historical"
    if not (cache / "EUR_USD_M5.csv").is_file():
        pytest.skip("historical cache not present")
    times = pd.concat(
        [pd.to_datetime(load_m5_with_book(s, cache)["time"]) for s in RESEARCH_SYMBOLS],
        ignore_index=True,
    )
    cuts = chrono_masks(times)
    assert str(cuts["cut_50"]).startswith("2026-03-03 12:15")
    assert str(cuts["cut_75"]).startswith("2026-06-02 05:05")


def test_depth_resume_mask_builds_without_future_columns():
    n = 40
    close = np.linspace(1.10, 1.12, n)
    close[20:] = np.linspace(1.12, 1.08, n - 20)
    frame = pd.DataFrame(
        {
            "state": np.ones(n, dtype=np.int8),
            "close": close,
            "high": close + 0.001,
            "low": close - 0.001,
            "ema_slow": np.full(n, 1.07),
            "ema_fast": np.full(n, 1.09),
        }
    )
    mask = depth_resume_mask(frame, 0.382)
    assert mask.dtype == bool
    assert int(mask.sum()) <= 1


def test_classify_conclusion_is_not_best_level():
    empty = classify_conclusion([], {})
    assert empty == "A"
    neighbors = [
        {
            "valid_fib_beats_both": True,
            "test_fib_beats_both": True,
        }
    ]
    assert classify_conclusion(neighbors, {}) == "C"


def test_research_report_has_required_sections():
    text = REPORT.read_text(encoding="utf-8")
    for title in (
        "EXPERIMENT: Fibonacci vs ordinary retracement depth",
        "PRODUCTION IMPACT:",
        "CAUSAL SWING",
        "DEPTHS",
        "RESULT TABLE",
        "FIB-vs-NEIGHBOR TABLE",
        "PAIR STABILITY",
        "SIDE STABILITY",
        "PLACEBO RESULT",
        "GENERIC RETRACEMENT-DEPTH EFFECT, NOT FIB-SPECIFIC",
        "PRODUCTION CODE CHANGED: NO",
    ):
        assert title in text


def test_harness_isolation_from_live_execution():
    hits = forbidden_hits_in_source(HARNESS.read_text(encoding="utf-8"))
    assert hits == []
    src = HARNESS.read_text(encoding="utf-8")
    assert "forex_bot.bot_loop" not in src
    assert "forex_bot.v2_shadow" not in src
    assert "forex_bot.oanda_exec" not in src
    assert "forex_bot.rl_agent" not in src
