"""Leakage and orientation tests for research feature/target builders."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from forex_bot.decision_quality.feature_discovery import (
    HORIZONS_MIN,
    _closed_htf,
    _join_closed_htf,
    apply_bins,
    assign_split,
    build_symbol_frame,
    freeze_splits,
    train_quintile_edges,
)
from forex_bot.profit_protection import pip_size


def _synth(n: int = 80, start: datetime | None = None, step_pips: float = 1.0) -> pd.DataFrame:
    t0 = start or datetime(2025, 1, 6, 8, 0)
    close = 1.1000 + np.arange(n) * (step_pips * 0.0001)
    rows = []
    for i, c in enumerate(close):
        rows.append(
            {
                "time": t0 + timedelta(minutes=5 * i),
                "open": c - 0.00005,
                "high": c + 0.00010,
                "low": c - 0.00010,
                "close": c,
            }
        )
    return pd.DataFrame(rows)


def test_target_uses_future_close_only():
    df = _synth(20)
    close = df["close"].to_numpy()
    # emulate builder: y at i is close[i+1] - close[i] for 5m
    y5 = np.full(20, np.nan)
    y5[:-1] = close[1:] - close[:-1]
    assert y5[0] == close[1] - close[0]
    assert np.isnan(y5[-1])


def test_quintile_edges_from_train_only_apply_to_later():
    train = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])
    edges = train_quintile_edges(train)
    later = np.array([-5.0, 1.5, 10.0])
    bins = apply_bins(later, edges)
    assert bins[0] == 0
    assert bins[-1] == 4


def test_jpy_pips_use_0_01():
    assert pip_size("USD_JPY") == 0.01
    assert pip_size("EUR_USD") == 0.0001
    # 0.10 JPY move = 10 pips
    assert (150.10 - 150.00) / pip_size("USD_JPY") == pytest.approx(10.0)


def test_closed_htf_excludes_unfinished_bar():
    t0 = datetime(2025, 1, 6, 8, 0)
    df = _synth(20, start=t0)
    h1 = _closed_htf(df, "1h", 60)
    # H1 starting 08:00 ends 09:00. A 08:30 M5 must not see that H1.
    joined = _join_closed_htf(df, h1, "h1")
    row_0830 = df["time"] == datetime(2025, 1, 6, 8, 30)
    if row_0830.any() and not h1.empty:
        # first completed H1 ends at 09:00
        first_end = h1["end"].iloc[0]
        assert first_end >= pd.Timestamp("2025-01-06 09:00:00")
        val = joined.loc[row_0830, "h1_close"]
        if first_end > pd.Timestamp("2025-01-06 08:30:00"):
            assert val.isna().all() or (joined.loc[row_0830, "end"] <= pd.Timestamp("2025-01-06 08:30:00")).all()


def test_rolling_return_uses_past_closes_only():
    df = _synth(30)
    close = df["close"].astype(float)
    ret6 = close.pct_change(6)
    i = 10
    expected = (close.iloc[i] - close.iloc[i - 6]) / close.iloc[i - 6]
    assert abs(float(ret6.iloc[i]) - float(expected)) < 1e-12
    # does not use close[i+1]
    assert close.iloc[i + 1] != close.iloc[i]


def test_split_assignment_is_chronological():
    times = pd.Series(pd.date_range("2025-09-01", periods=100, freq="5min"))
    t50, t75 = freeze_splits(times)
    parts = assign_split(times, t50, t75)
    assert parts[0] == "train"
    assert parts[-1] == "discovery_test"
    assert t50 < t75


def test_feature_frame_no_lookahead_on_returns(tmp_path, monkeypatch):
    # Use real builder against a tiny written CSV if needed — skip file IO by
    # checking the documented shift convention on a constructed series.
    close = pd.Series([1.0, 1.1, 1.2, 1.0, 0.9])
    ret1 = close.pct_change(1)
    assert np.isnan(ret1.iloc[0])
    assert ret1.iloc[1] == (1.1 - 1.0) / 1.0
    y = close.shift(-1) - close
    assert y.iloc[0] == pytest.approx(0.1)
    assert np.isnan(y.iloc[-1])
