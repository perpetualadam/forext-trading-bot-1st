"""Stage 2: pagination, resume, dedupe — mocked fetch, no OANDA."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from forex_bot.decision_quality.history_cache import (
    iter_page_windows,
    merge_frames,
    missing_windows,
    resume_and_fetch,
    validate_frame,
)


def _mid(ts: datetime, px: float = 1.1) -> dict:
    return {
        "time": ts,
        "open": px,
        "high": px + 0.0002,
        "low": px - 0.0002,
        "close": px,
        "complete": True,
    }


def test_pagination_covers_range_without_overlap_or_holes():
    start = datetime(2024, 1, 2, 0, 0, 0)
    end = datetime(2024, 1, 2, 8, 15, 0)  # 8h15m = 99 M5 bars inclusive? 
    # 00:00 through 08:15 inclusive = 8*12 + 4 = 100 starts if 5-min
    pages = iter_page_windows(start, end, max_candles=20)
    assert pages
    assert pages[0].start == start
    assert pages[-1].end == end
    # Adjacent pages: next starts exactly 5 minutes after previous end.
    for a, b in zip(pages, pages[1:]):
        assert b.start == a.end + timedelta(minutes=5)
        assert a.end < b.start
    # Reconstruct every start that pages claim.
    covered: list[datetime] = []
    for p in pages:
        cur = p.start
        while cur <= p.end:
            covered.append(cur)
            cur += timedelta(minutes=5)
    assert covered == sorted(covered)
    assert covered[0] == start
    assert covered[-1] == end
    assert len(covered) == len(set(covered))


def test_missing_windows_prefix_internal_suffix():
    start = datetime(2024, 1, 2, 8, 0, 0)
    end = datetime(2024, 1, 2, 8, 30, 0)
    existing = pd.DataFrame(
        [
            _mid(datetime(2024, 1, 2, 8, 10, 0)),
            _mid(datetime(2024, 1, 2, 8, 15, 0)),
        ]
    )
    gaps = missing_windows(existing, start, end)
    assert [(g.start, g.end) for g in gaps] == [
        (datetime(2024, 1, 2, 8, 0, 0), datetime(2024, 1, 2, 8, 5, 0)),
        (datetime(2024, 1, 2, 8, 20, 0), datetime(2024, 1, 2, 8, 30, 0)),
    ]


def test_resume_fetches_only_missing_pages():
    start = datetime(2024, 1, 2, 8, 0, 0)
    end = datetime(2024, 1, 2, 8, 20, 0)
    existing = pd.DataFrame([_mid(datetime(2024, 1, 2, 8, 10, 0), 1.2)])
    calls: list[tuple] = []

    def fetch_page(symbol: str, a: datetime, b: datetime) -> pd.DataFrame:
        calls.append((symbol, a, b))
        rows = []
        cur = a
        px = 1.0
        while cur <= b:
            rows.append(_mid(cur, px))
            cur += timedelta(minutes=5)
            px += 0.001
        return pd.DataFrame(rows)

    merged, pages = resume_and_fetch(
        "EUR_USD",
        start,
        end,
        existing=existing,
        fetch_page=fetch_page,
        max_candles=500,
    )
    assert all(c[0] == "EUR_USD" for c in calls)
    fetched_starts = []
    for _sym, a, b in calls:
        cur = a
        while cur <= b:
            fetched_starts.append(cur)
            cur += timedelta(minutes=5)
    assert datetime(2024, 1, 2, 8, 10, 0) not in fetched_starts
    times = list(pd.to_datetime(merged["time"]))
    assert times == [
        pd.Timestamp("2024-01-02 08:00:00"),
        pd.Timestamp("2024-01-02 08:05:00"),
        pd.Timestamp("2024-01-02 08:10:00"),
        pd.Timestamp("2024-01-02 08:15:00"),
        pd.Timestamp("2024-01-02 08:20:00"),
    ]
    # Existing 08:10 close 1.2 kept (later fetch does not overlap that stamp).
    assert float(merged.loc[merged["time"] == pd.Timestamp("2024-01-02 08:10:00"), "close"].iloc[0]) == 1.2
    assert pages
    now = datetime(2024, 1, 3, 0, 0, 0)
    assert validate_frame(merged, symbol="EUR_USD", now_utc=now).ok


def test_overlap_pages_dedupe_keep_last():
    t0 = datetime(2024, 1, 2, 8, 0, 0)
    first = pd.DataFrame([_mid(t0, 1.1), _mid(t0 + timedelta(minutes=5), 1.2)])
    second = pd.DataFrame([_mid(t0 + timedelta(minutes=5), 9.9), _mid(t0 + timedelta(minutes=10), 1.3)])
    merged = merge_frames(first, second)
    assert len(merged) == 3
    mid = merged.loc[merged["time"] == pd.Timestamp(t0 + timedelta(minutes=5)), "close"].iloc[0]
    assert float(mid) == 9.9
