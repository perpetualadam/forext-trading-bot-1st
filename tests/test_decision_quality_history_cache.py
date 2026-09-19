"""Stage 1: historical cache validation, weekends, six-pair paths."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from forex_bot.decision_quality.history_cache import (
    RESEARCH_SYMBOLS,
    cache_filename,
    cache_path,
    classify_gap,
    default_historical_dir,
    exclude_incomplete,
    last_completed_m5_start,
    merge_frames,
    normalize_frame,
    read_canonical_csv,
    twelve_complete_months_utc,
    validate_frame,
    write_canonical_csv,
)
from forex_bot.symbols import DEFAULT_FOREX_SYMBOLS


def _bar(ts: datetime, o: float = 1.1, h: float | None = None, l: float | None = None, c: float | None = None, **extra):
    close = 1.1 if c is None else c
    high = close + 0.0002 if h is None else h
    low = close - 0.0002 if l is None else l
    row = {"time": ts, "open": o, "high": high, "low": low, "close": close, "complete": True}
    row.update(extra)
    return row


def test_six_configured_pairs_and_paths():
    assert tuple(RESEARCH_SYMBOLS) == tuple(DEFAULT_FOREX_SYMBOLS)
    assert RESEARCH_SYMBOLS == (
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "AUD_USD",
        "USD_CAD",
        "USD_CHF",
    )
    root = Path("C:/tmp/research-root")
    ddir = default_historical_dir(root)
    assert ddir.as_posix().endswith("data/historical")
    assert cache_filename("eur-usd") == "EUR_USD_M5.csv"
    assert cache_path("USD_JPY", ddir).name == "USD_JPY_M5.csv"


def test_twelve_complete_months_excludes_forming_month():
    now = datetime(2026, 9, 16, 10, 53, 0)
    start, end = twelve_complete_months_utc(now)
    assert start == datetime(2025, 9, 1, 0, 0, 0)
    assert end == datetime(2026, 8, 31, 23, 55, 0)
    forming = last_completed_m5_start(datetime(2026, 9, 16, 10, 53, 0))
    assert forming == datetime(2026, 9, 16, 10, 45, 0)
    assert forming < datetime(2026, 9, 16, 10, 50, 0)


def test_ohlc_and_ordering_validation():
    t0 = datetime(2024, 1, 2, 8, 0, 0)
    good = pd.DataFrame(
        [
            _bar(t0, 1.10, 1.11, 1.09, 1.105),
            _bar(t0 + timedelta(minutes=5), 1.105, 1.12, 1.10, 1.11),
        ]
    )
    ok = validate_frame(good, symbol="EUR_USD", now_utc=datetime(2024, 1, 3, 0, 0, 0))
    assert ok.ok
    assert ok.bars == 2

    bad_ohlc = pd.DataFrame([_bar(t0, 1.10, 1.09, 1.11, 1.10)])
    bad = validate_frame(bad_ohlc, symbol="EUR_USD", now_utc=datetime(2024, 1, 3))
    assert not bad.ok
    assert any("invalid OHLC" in e for e in bad.errors)

    dup = pd.DataFrame([_bar(t0), _bar(t0, o=1.2, c=1.2)])
    drep = validate_frame(dup, symbol="EUR_USD", now_utc=datetime(2024, 1, 3))
    # normalize_frame dedupes; remaining single bar is valid
    assert drep.bars == 1


def test_future_and_incomplete_candles_rejected():
    now = datetime(2024, 1, 2, 12, 0, 0)
    future = pd.DataFrame([_bar(datetime(2024, 1, 2, 12, 0, 0))])
    rep = validate_frame(future, symbol="EUR_USD", now_utc=now)
    assert not rep.ok
    assert any("forming" in e or "future" in e for e in rep.errors)

    raw = pd.DataFrame(
        [
            _bar(datetime(2024, 1, 2, 8, 0, 0), complete=True),
            _bar(datetime(2024, 1, 2, 8, 5, 0), complete=False),
        ]
    )
    kept = exclude_incomplete(normalize_frame(raw))
    assert len(kept) == 1
    assert kept["time"].iloc[0] == pd.Timestamp("2024-01-02 08:00:00")


def test_weekend_gap_vs_unexpected_weekday_gap():
    # Friday 20:55 → Sunday 21:00 is the FX weekend close.
    fri = datetime(2024, 1, 5, 20, 55, 0)  # Friday
    sun = datetime(2024, 1, 7, 21, 0, 0)
    assert classify_gap(fri, sun) == "expected_weekend"
    wed = datetime(2024, 1, 3, 10, 0, 0)
    wed2 = datetime(2024, 1, 3, 10, 20, 0)
    assert classify_gap(wed, wed2) == "unexpected"
    assert classify_gap(wed, wed + timedelta(minutes=5)) == "none"

    frame = pd.DataFrame([_bar(fri), _bar(sun, o=1.11, c=1.11)])
    rep = validate_frame(frame, symbol="EUR_USD", now_utc=datetime(2024, 1, 8, 12, 0, 0))
    assert rep.ok
    assert rep.expected_weekend_gaps == 1
    assert rep.unexpected_gaps == 0

    hole = pd.DataFrame([_bar(wed), _bar(wed2, o=1.11, c=1.11)])
    hole_rep = validate_frame(hole, symbol="EUR_USD", now_utc=datetime(2024, 1, 4, 12, 0, 0))
    assert hole_rep.ok  # reported, not corrupt
    assert hole_rep.unexpected_gaps == 1


def test_deterministic_csv_roundtrip(tmp_path: Path):
    t0 = datetime(2024, 1, 2, 8, 0, 0)
    df = pd.DataFrame(
        [
            _bar(t0, bid_open=1.0999, bid_high=1.11, bid_low=1.09, bid_close=1.1049, volume=12),
            _bar(t0 + timedelta(minutes=5), o=1.105, c=1.11, volume=8),
        ]
    )
    path = tmp_path / "EUR_USD_M5.csv"
    write_canonical_csv(df, path)
    text1 = path.read_text(encoding="utf-8")
    write_canonical_csv(read_canonical_csv(path), path)
    text2 = path.read_text(encoding="utf-8")
    assert text1 == text2
    assert text1.startswith("time,open,high,low,close,")
    assert "2024-01-02T08:00:00Z" in text1
    loaded = read_canonical_csv(path)
    assert list(loaded["close"]) == pytest.approx([1.1, 1.11])
    assert "bid_open" in loaded.columns


def test_merge_dedupes_and_sorts():
    t0 = datetime(2024, 1, 2, 8, 0, 0)
    a = pd.DataFrame([_bar(t0 + timedelta(minutes=5), o=1.2, c=1.2), _bar(t0)])
    b = pd.DataFrame([_bar(t0, o=1.3, c=1.3)])  # later write wins
    merged = merge_frames(a, b)
    assert list(pd.to_datetime(merged["time"])) == [pd.Timestamp(t0), pd.Timestamp(t0 + timedelta(minutes=5))]
    assert float(merged["close"].iloc[0]) == pytest.approx(1.3)
