"""Tests for H1/H4 aggregation. They do not score a strategy."""

from __future__ import annotations

import pandas as pd
import pytest

from forex_bot.research.learning.timeframes import aggregate_bid_ask, research_pip_size, visible_close


def _bars(start: str, count: int, *, drop: int | None = None, incomplete: int | None = None) -> pd.DataFrame:
    times = pd.date_range(start, periods=count, freq="5min", tz="UTC")
    frame = pd.DataFrame(
        {
            "time": times,
            "bid_open": [1.0 + index * 0.0001 for index in range(count)],
            "bid_high": [1.1 + index * 0.0001 for index in range(count)],
            "bid_low": [0.9 + index * 0.0001 for index in range(count)],
            "bid_close": [1.05 + index * 0.0001 for index in range(count)],
            "ask_open": [1.2 + index * 0.0001 for index in range(count)],
            "ask_high": [1.3 + index * 0.0001 for index in range(count)],
            "ask_low": [1.15 + index * 0.0001 for index in range(count)],
            "ask_close": [1.25 + index * 0.0001 for index in range(count)],
            "volume": [1.0] * count,
            "complete": [True] * count,
        }
    )
    if drop is not None:
        frame = frame.drop(index=drop).reset_index(drop=True)
    if incomplete is not None:
        frame.loc[incomplete, "complete"] = False
    return frame


def test_h1_uses_the_first_open_extreme_high_low_and_last_close() -> None:
    candles, report = aggregate_bid_ask(_bars("2026-01-05T00:00:00Z", 12), 60)
    assert report["complete_candles"] == 1
    assert report["incomplete_buckets"] == 0
    row = candles.iloc[0]
    assert row["time"] == pd.Timestamp("2026-01-05T00:00:00Z")
    assert row["available_at"] == pd.Timestamp("2026-01-05T01:00:00Z")
    assert row["bid_open"] == 1.0
    assert row["bid_high"] == 1.1 + 11 * 0.0001
    assert row["bid_low"] == 0.9
    assert row["bid_close"] == 1.05 + 11 * 0.0001
    assert row["ask_open"] == 1.2
    assert row["volume"] == 12.0


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_timestamp_resolution_preserves_candle_and_missing_bar_checks(unit: str) -> None:
    bars = _bars("2026-01-05T00:00:00Z", 24)
    bars["time"] = bars["time"].dt.as_unit(unit)
    candles, report = aggregate_bid_ask(bars, 60)
    assert report["complete_candles"] == 2
    assert list(candles["time"]) == list(pd.date_range("2026-01-05", periods=2, freq="h", tz="UTC"))
    assert visible_close(candles, pd.Timestamp("2026-01-05T00:59:59Z")) is None
    missing, report = aggregate_bid_ask(bars.drop(index=4), 60)
    assert report["incomplete_buckets"] == 1
    assert len(missing) == 1
    assert missing.iloc[0]["time"] == pd.Timestamp("2026-01-05T01:00:00Z")


def test_missing_or_incomplete_constituents_are_rejected() -> None:
    missing, missing_report = aggregate_bid_ask(_bars("2026-01-05T00:00:00Z", 12, drop=4), 60)
    assert missing.empty
    assert missing_report["incomplete_buckets"] == 1
    flagged, flagged_report = aggregate_bid_ask(_bars("2026-01-05T00:00:00Z", 12, incomplete=3), 60)
    assert flagged.empty
    assert flagged_report["incomplete_buckets"] == 1


def test_h4_alignment_is_four_utc_hours() -> None:
    candles, report = aggregate_bid_ask(_bars("2026-01-05T00:00:00Z", 48), 240)
    assert report["complete_candles"] == 1
    assert candles.iloc[0]["time"] == pd.Timestamp("2026-01-05T00:00:00Z")
    assert candles.iloc[0]["available_at"] == pd.Timestamp("2026-01-05T04:00:00Z")
    shifted, shifted_report = aggregate_bid_ask(_bars("2026-01-05T00:05:00Z", 48), 240)
    assert shifted.empty
    assert shifted_report["incomplete_buckets"] >= 1


def test_asof_join_hides_the_unfinished_higher_timeframe_close() -> None:
    candles, _report = aggregate_bid_ask(_bars("2026-01-05T00:00:00Z", 24), 60)
    during = pd.Timestamp("2026-01-05T00:30:00Z")
    after = pd.Timestamp("2026-01-05T01:00:00Z")
    assert visible_close(candles, during) is None
    assert visible_close(candles, after) == float(candles.iloc[0]["bid_close"])


def test_earlier_h1_candle_is_unchanged_when_later_bars_are_removed() -> None:
    full, _report = aggregate_bid_ask(_bars("2026-01-05T00:00:00Z", 24), 60)
    prefix, _prefix_report = aggregate_bid_ask(_bars("2026-01-05T00:00:00Z", 12), 60)
    assert full.iloc[0]["bid_close"] == prefix.iloc[0]["bid_close"]
    assert len(prefix) == 1
    assert len(full) == 2


def test_pip_rule_and_strategy_flags() -> None:
    assert research_pip_size("USD_JPY") == 0.01
    assert research_pip_size("EUR_JPY") == 0.01
    assert research_pip_size("EUR_GBP") == 0.0001
    assert research_pip_size("NZD_USD") == 0.0001
    from forex_bot.strategy_meta import strategies

    assert all(not item.active and not item.authorised_for_live for item in strategies.values())
    assert "aggregate_bid_ask" not in open("forex_bot/bot_loop.py", encoding="utf-8").read()
