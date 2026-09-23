"""Research-only EMA retracement harness. Does not change live trading."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pathlib import Path

from forex_bot.decision_quality.ema_retracement import (
    FROZEN_LOOKBACK,
    indicator_sma_periods,
    ma_state,
    mean_reversion_mask,
    scan_pullback_resume,
    simulate_occupancy_trades,
    swing_retrace_mask,
)
from forex_bot.decision_quality.isolation import forbidden_hits_in_source
from forex_bot.indicators import compute_indicators

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "decision_quality" / "ema_retracement_signal_research.md"
HARNESS = ROOT / "forex_bot" / "decision_quality" / "ema_retracement.py"

REQUIRED_SECTIONS = (
    "CURRENT CODE AUDIT",
    "EXPERIMENT DESIGN",
    "PARAMETERS TESTED",
    "BASELINE RESULTS",
    "EMA TREND RESULTS",
    "EMA + RETRACEMENT RESULTS",
    "EMA + RETRACEMENT + RESUMPTION RESULTS",
    "MEAN-REVERSION COMPARISON",
    "TRAIN / VALIDATION / TEST",
    "PER-SYMBOL RESULTS",
    "FORWARD-RETURN ANALYSIS",
    "COST SENSITIVITY",
    "FAILURE MODES / LIMITATIONS",
    "EVIDENCE CLASSIFICATION",
    "NEXT RESEARCH STEP",
    "PRODUCTION CODE CHANGED: NO",
    "LIVE STRATEGY CHANGED: NO",
    "OANDA ORDERS SENT: NO",
    "DOCKER RESTARTED: NO",
)


def test_frozen_sma_periods_match_compute_indicators():
    n = 500
    close = pd.Series(np.linspace(1.1, 1.2, n))
    df = pd.DataFrame(
        {
            "time": pd.date_range("2025-01-01", periods=n, freq="5min"),
            "open": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "close": close,
        }
    )
    for symbol, lb in FROZEN_LOOKBACK.items():
        fast_n, slow_n = indicator_sma_periods(lb, n)
        ind = compute_indicators(df, lookback=lb)
        # Last complete windows: rolling mean of last fast_n / slow_n closes.
        assert abs(float(ind["ma_fast"].iloc[-1]) - float(close.iloc[-fast_n:].mean())) < 1e-12
        assert abs(float(ind["ma_slow"].iloc[-1]) - float(close.iloc[-slow_n:].mean())) < 1e-12
        if symbol == "USD_JPY":
            assert (fast_n, slow_n) == (5, 25)
        else:
            assert (fast_n, slow_n) == (10, 50)


def test_ma_state_orientation():
    assert list(ma_state(np.array([1.2, 1.0]), np.array([1.0, 1.2]))) == [1, -1]


def test_pullback_requires_extension_then_resume():
    n = 8
    state = np.array([1] * n, dtype=np.int8)
    # Extend to 0.8 ATR, then pull to 0.1, then close back above fast EMA.
    signed = np.array([0.2, 0.8, 0.7, 0.10, 0.10, 0.3, 0.4, 0.5])
    close = np.array([1.00, 1.08, 1.07, 1.01, 1.01, 1.04, 1.05, 1.06])
    fast = np.array([1.03] * n)
    pull, resume = scan_pullback_resume(state, signed, close, fast)
    assert list(pull).count(True) == 1
    assert int(np.flatnonzero(pull)[0]) == 3
    assert list(resume).count(True) == 1
    assert int(np.flatnonzero(resume)[0]) == 5


def test_new_episode_resets_pullback_state():
    state = np.array([1, 1, 1, -1, -1, -1], dtype=np.int8)
    signed = np.array([0.8, 0.1, 0.4, 0.8, 0.1, 0.4])
    close = np.array([1.10, 1.01, 1.06, 0.90, 0.99, 0.94])
    fast = np.array([1.03, 1.03, 1.03, 0.97, 0.97, 0.97])
    pull, resume = scan_pullback_resume(state, signed, close, fast)
    assert bool(pull[1]) and bool(pull[4])
    assert bool(resume[2]) and bool(resume[5])


def test_swing_retrace_is_once_per_episode():
    state = np.ones(6, dtype=np.int8)
    close = np.array([1.00, 1.10, 1.05, 1.04, 1.03, 1.02])
    high = np.array([1.01, 1.10, 1.06, 1.05, 1.04, 1.03])
    low = np.array([0.99, 1.00, 1.04, 1.03, 1.02, 1.01])
    slow = np.array([0.98] * 6)
    mask = swing_retrace_mask(state, close, high, low, slow, lookback=6, depth=0.50)
    assert int(mask.sum()) == 1


def test_mean_reversion_fades_extension():
    close = np.array([1.00, 1.00, 1.30, 1.30, 0.70])
    ema = np.array([1.00] * 5)
    atr = np.array([0.10] * 5)
    entry, side = mean_reversion_mask(close, ema, atr, z=2.0)
    assert list(entry) == [False, False, True, False, True]
    assert int(side[2]) == -1
    assert int(side[4]) == 1


def test_economic_sl_is_minus_one_r_without_book():
    n = 5
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2025-01-01", periods=n, freq="5min"),
            "symbol": ["EUR_USD"] * n,
            "close": [1.1000, 1.0990, 1.0970, 1.0960, 1.0950],
            "high": [1.1005, 1.0992, 1.0972, 1.0962, 1.0952],
            "low": [1.0998, 1.0988, 1.0960, 1.0950, 1.0940],
            "atr": [0.0010] * n,
            "state": [1] * n,
        }
    )
    sig = np.array([True, False, False, False, False])
    trades = simulate_occupancy_trades(frame, sig, "EUR_USD")
    assert len(trades) == 1
    assert trades[0]["reason"] in ("sl", "ambiguous_sl")
    assert trades[0]["r"] == pytest.approx(-1.0)


def test_harness_does_not_import_broker_or_bot_loop():
    hits = forbidden_hits_in_source(HARNESS.read_text(encoding="utf-8"))
    assert hits == []


def test_research_report_has_required_sections():
    text = REPORT.read_text(encoding="utf-8")
    missing = [title for title in REQUIRED_SECTIONS if title not in text]
    assert missing == []
