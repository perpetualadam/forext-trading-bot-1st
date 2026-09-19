"""Local inventory, chronological order, and no future-bar leakage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from forex_bot.decision_quality.data import (
    REQUIRED_SYMBOLS,
    assert_no_future,
    ensure_chronological,
    history_at,
    inventory_local_ohlcv,
    load_symbol_frame,
)

REQUIRED_HISTORICAL = (
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
)


def test_inventory_reports_required_six_pairs_present():
    """Current intended dataset: six downloaded M5 histories must be inventoried."""
    assert tuple(REQUIRED_SYMBOLS) == REQUIRED_HISTORICAL
    cov = inventory_local_ohlcv()
    by_sym = {c.symbol: c for c in cov if c.timeframe == "M5"}
    for symbol in REQUIRED_HISTORICAL:
        assert symbol in by_sym, f"{symbol} missing from inventory"
        series = by_sym[symbol]
        assert series.bars > 0, f"{symbol} has no bars"
        assert series.path, f"{symbol} has no CSV path"
        assert Path(series.path).is_file(), f"{symbol} CSV missing on disk"
        assert series.earliest is not None
        assert series.latest is not None
        assert series.timeframe == "M5"
        assert symbol in Path(series.path).name


def test_inventory_reports_missing_pairs(tmp_path: Path):
    """Still detects a genuinely missing required pair (isolated data dir)."""
    only = tmp_path / "EUR_USD_M5.csv"
    only.write_text(
        "time,open,high,low,close\n"
        "2024-01-02T08:00:00,1.1,1.11,1.09,1.1\n",
        encoding="utf-8",
    )
    cov = inventory_local_ohlcv(tmp_path)
    by_sym = {c.symbol: c for c in cov}
    assert by_sym["EUR_USD"].bars > 0
    assert by_sym["EUR_USD"].path
    for missing in ("GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"):
        assert by_sym[missing].bars == 0
        assert by_sym[missing].path is None
        assert "no local CSV" in by_sym[missing].missing_reason


def test_sample_csv_is_chronological():
    root = Path(__file__).resolve().parents[1]
    df = load_symbol_frame(root / "data" / "eurusd_m5_2024_sample.csv")
    assert df["time"].is_monotonic_increasing
    assert list(df.columns[:5]) == ["time", "open", "high", "low", "close"]


def test_history_at_excludes_future_bars():
    times = pd.date_range("2024-01-02 08:00", periods=10, freq="5min")
    df = pd.DataFrame(
        {
            "time": times,
            "open": 1.1,
            "high": 1.11,
            "low": 1.09,
            "close": 1.1,
        }
    )
    window = history_at(df, 4)
    assert len(window) == 5
    asof = times[4].to_pydatetime()
    assert_no_future(window, asof)
    with pytest.raises(AssertionError):
        leaked = df.iloc[:8].copy()
        assert_no_future(leaked, asof)


def test_ensure_chronological_sorts_and_dedupes():
    df = pd.DataFrame(
        {
            "time": ["2024-01-02T08:10:00Z", "2024-01-02T08:00:00Z", "2024-01-02T08:00:00Z"],
            "open": [1.2, 1.0, 1.1],
            "high": [1.2, 1.0, 1.1],
            "low": [1.2, 1.0, 1.1],
            "close": [1.2, 1.0, 1.05],
        }
    )
    out = ensure_chronological(df)
    assert list(out["close"]) == [1.05, 1.2]
    assert out["time"].iloc[0] == pd.Timestamp("2024-01-02 08:00:00")
