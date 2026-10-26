"""Causal structure tests. They do not score a trade."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from forex_bot.research.learning.structure import (
    K,
    asof_view,
    build_trendlines,
    confirmed_swings,
    known_before,
    line_price,
    observation_row,
    range_decision,
    support_resistance,
    trend_states,
    trendline_events,
)
from forex_bot.research.learning.timeframes import aggregate_bid_ask, visible_close


def _candles(highs: list[float], lows: list[float], closes: list[float] | None = None, start: str = "2026-01-05T00:00:00Z") -> pd.DataFrame:
    count = len(highs)
    times = pd.date_range(start, periods=count, freq="h", tz="UTC")
    if closes is None:
        closes = [(high + low) / 2.0 for high, low in zip(highs, lows)]
    return pd.DataFrame(
        {
            "time": times,
            "available_at": times + pd.Timedelta(hours=1),
            "bid_high": highs,
            "bid_low": lows,
            "bid_close": closes,
            "bid_open": closes,
        }
    )


def test_source_hash_constant_and_h1_h4_alignment() -> None:
    from forex_bot.research.learning.data_validation import file_sha256
    from forex_bot.research.learning.regimes import DATASET_SHA256

    assert len(DATASET_SHA256) == 6
    root = Path("data/historical/EUR_USD_M5.csv")
    assert file_sha256(root) == DATASET_SHA256["EUR_USD"]
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2026-01-05T00:00:00Z", periods=48, freq="5min", tz="UTC"),
            "bid_open": [1.0] * 48,
            "bid_high": [1.2] * 48,
            "bid_low": [0.8] * 48,
            "bid_close": [1.1] * 48,
            "ask_open": [1.3] * 48,
            "ask_high": [1.4] * 48,
            "ask_low": [1.0] * 48,
            "ask_close": [1.2] * 48,
            "volume": [1.0] * 48,
            "complete": [True] * 48,
        }
    )
    hourly, hour_report = aggregate_bid_ask(frame.iloc[:12], 60)
    four, four_report = aggregate_bid_ask(frame, 240)
    assert hour_report["complete_candles"] == 1
    assert hourly.iloc[0]["available_at"] == pd.Timestamp("2026-01-05T01:00:00Z")
    assert four_report["complete_candles"] == 1
    assert four.iloc[0]["time"] == pd.Timestamp("2026-01-05T00:00:00Z")
    shifted = frame.copy()
    shifted["time"] = shifted["time"] + pd.Timedelta(minutes=5)
    rejected, rejected_report = aggregate_bid_ask(shifted, 240)
    assert rejected.empty
    assert rejected_report["incomplete_buckets"] >= 1


def test_swing_confirmation_delay_tie_and_gap() -> None:
    highs = [1, 1, 1, 1, 3, 1, 1, 1, 1, 1]
    lows = [0.4, 0.4, 0.4, 0.4, 0.5, 0.4, 0.4, 0.4, 0.4, 0.4]
    swings, report = confirmed_swings(_candles(highs, lows), period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    assert report["confirmed_swing_highs"] == 1
    assert report["confirmed_swing_lows"] == 0
    swing = swings[0]
    assert swing["pivot_time"] == pd.Timestamp("2026-01-05T04:00:00Z")
    assert swing["available_at"] == pd.Timestamp("2026-01-05T07:00:00Z")
    assert swing["confirmation_time"] == swing["available_at"]
    assert swing["available_at"] == swing["pivot_time"] + pd.Timedelta(hours=3)
    early = asof_view(swings, [], [], pd.Timestamp("2026-01-05T06:59:00Z"))
    assert early["swings"] == []
    tied = highs.copy()
    tied[5] = 3
    tied_swings, tied_report = confirmed_swings(_candles(tied, lows), period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    assert tied_report["confirmed_swing_highs"] == 0
    assert tied_report["tied_high_candidates"] == 2
    assert tied_swings == []
    gapped = _candles(highs, lows)
    gapped.loc[5:, "time"] = gapped.loc[5:, "time"] + pd.Timedelta(hours=10)
    gapped["available_at"] = gapped["time"] + pd.Timedelta(hours=1)
    gapped_swings, gapped_report = confirmed_swings(gapped, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    assert gapped_swings == []
    assert gapped_report["gap_rejected_windows"] >= 1
    lows = [1.0, 1.0, 1.0, 1.0, 0.1, 1.0, 1.0, 1.1, 1.1, 1.1]
    highs = [1.4, 1.4, 1.4, 1.4, 1.2, 1.4, 1.4, 1.5, 1.5, 1.5]
    low_swings, _low_report = confirmed_swings(_candles(highs, lows), period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    assert len(low_swings) == 1
    assert low_swings[0]["swing_type"] == "LOW"
    assert low_swings[0]["available_at"] == low_swings[0]["pivot_time"] + pd.Timedelta(hours=3)


def _pair(low_a: float, high_a: float, low_b: float, high_b: float) -> pd.DataFrame:
    highs = [1.0] * 14
    lows = [1.0] * 14
    highs[4] = high_a
    highs[8] = high_b
    lows[2] = low_a
    lows[6] = low_b
    return _candles(highs, lows, closes=[1.0] * 14)


def test_structure_labels_and_states_do_not_lead_the_confirmation() -> None:
    candles = _pair(0.2, 2.0, 0.4, 3.0)
    swings, _report = confirmed_swings(candles, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    highs_only = [item for item in swings if item["swing_type"] == "HIGH"]
    lows_only = [item for item in swings if item["swing_type"] == "LOW"]
    assert [item["relation"] for item in highs_only] == ["UNCERTAIN", "HIGHER_HIGH"]
    assert [item["relation"] for item in lows_only] == ["UNCERTAIN", "HIGHER_LOW"]
    states = trend_states(candles, swings)
    before = next(row for row in states if row["available_at"] == highs_only[1]["available_at"] - pd.Timedelta(hours=1))
    at_confirm = next(row for row in states if row["available_at"] == highs_only[1]["available_at"])
    assert before["state"] == "UNCERTAIN"
    assert at_confirm["state"] == "UPTREND"
    mixed = _pair(0.2, 3.0, 0.5, 2.0)
    mixed_swings, _mixed_report = confirmed_swings(mixed, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    assert trend_states(mixed, mixed_swings)[-1]["state"] == "TRANSITION"
    down = _pair(0.5, 3.0, 0.2, 2.0)
    down_swings, _down_report = confirmed_swings(down, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    assert trend_states(down, down_swings)[-1]["state"] == "DOWNTREND"


def test_trendline_timing_versions_and_elapsed_weekend() -> None:
    highs = [1.5] * 14
    lows = [1.5] * 14
    lows[3] = 1.0
    lows[8] = 1.2
    candles = _candles(highs, lows)
    candles.loc[6:, "time"] = candles.loc[6:, "time"] + pd.Timedelta(hours=48)
    candles["available_at"] = candles["time"] + pd.Timedelta(hours=1)
    swings, _report = confirmed_swings(candles, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    lows_only = [item for item in swings if item["swing_type"] == "LOW"]
    assert len(lows_only) >= 2
    lines = build_trendlines(swings)
    first = lines[0]
    assert first["available_at"] == lows_only[1]["available_at"]
    assert first["available_at"] > first["second_pivot_time"]
    elapsed = (first["second_pivot_time"] - first["first_pivot_time"]).total_seconds()
    assert elapsed > 48 * 3600
    assert first["slope_per_second"] == (first["second_pivot_price"] - first["first_pivot_price"]) / elapsed
    assert line_price(first, first["second_pivot_time"]) == first["second_pivot_price"]
    hidden = asof_view(swings, lines, [], first["available_at"] - pd.Timedelta(seconds=1))
    assert first["line_id"] not in {item["line_id"] for item in hidden["lines"]}
    later_lows = [1.5] * 14
    later_lows[3] = 1.0
    later_lows[6] = 1.1
    later_lows[9] = 1.2
    later = _candles([1.5] * 14, later_lows)
    later_swings, _later_report = confirmed_swings(later, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    later_lines = build_trendlines(later_swings)
    assert len(later_lines) >= 2
    assert later_lines[0]["line_id"] != later_lines[1]["line_id"]
    assert later_lines[0]["available_at"] < later_lines[1]["available_at"]
    assert later_lines[0]["version"] == 1
    assert later_lines[1]["version"] == 2


def test_touch_break_and_level_availability_are_causal() -> None:
    highs = [1.4] * 12
    lows = [1.2] * 12
    lows[2] = 1.0
    lows[5] = 1.0
    lows[8] = 0.9
    closes = [1.1] * 12
    closes[8] = 1.05
    closes[9] = 0.95
    candles = _candles(highs, lows, closes)
    swings, _report = confirmed_swings(candles, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    lines = build_trendlines(swings)
    assert lines
    events = trendline_events(candles, lines[:1])
    assert events["counts"]["BREAK"] >= 1
    assert events["counts"]["TOUCH_REACH"] >= 1
    touch = events["examples"]["TOUCH_REACH"]
    breaking = events["examples"]["BREAK"]
    assert touch["available_at"] > lines[0]["available_at"]
    assert breaking["bid_close"] < breaking["line_price"]
    assert touch["bid_close"] > touch["line_price"]
    assert touch["bid_low"] <= touch["line_price"]
    levels = support_resistance(swings)
    assert levels[0]["available_at"] == swings[0]["available_at"]
    assert levels[0]["invalidation_time"] is None
    decision = range_decision()
    assert decision["range_state"] == "UNCERTAIN"
    assert decision["confirmed_ranges"] == 0
    assert decision["available_ranges"] == []


def test_prefix_asof_end_of_data_and_no_signal() -> None:
    highs = [1, 1, 1, 2, 1, 1, 1, 3, 1, 1, 4, 1]
    lows = [1, 0.2, 1, 1, 1, 1, 0.4, 1, 1, 1, 1, 1]
    candles = _candles(highs, lows)
    full_swings, _full_report = confirmed_swings(candles, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    limit = pd.Timestamp("2026-01-05T10:00:00Z")
    prefix = candles.loc[candles["available_at"] <= limit].copy()
    prefix_swings, _prefix_report = confirmed_swings(prefix, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    assert [item["swing_id"] for item in prefix_swings] == [item["swing_id"] for item in known_before(full_swings, limit)]
    full_lines = build_trendlines(full_swings)
    prefix_lines = build_trendlines(prefix_swings)
    assert [item["line_id"] for item in prefix_lines] == [item["line_id"] for item in known_before(full_lines, limit)]
    full_states = trend_states(candles, full_swings)
    prefix_states = trend_states(prefix, prefix_swings)
    assert [row["state"] for row in prefix_states] == [row["state"] for row in full_states if row["available_at"] <= limit]
    end = candles["available_at"].iloc[-1]
    view = asof_view(full_swings, full_lines, full_states, end)
    assert all(swing["available_at"] <= end for swing in view["swings"])
    assert view["trading_signal"] is None
    terminal = _candles([1, 1, 1, 1, 1, 9], [0.5] * 6)
    terminal_swings, _terminal_report = confirmed_swings(terminal, period=pd.Timedelta(hours=1), instrument="EUR_USD", timeframe="H1", source_sha256="abc")
    assert all(swing["pivot_time"] != terminal["time"].iloc[-1] for swing in terminal_swings)
    during = pd.Timestamp("2026-01-05T00:30:00Z")
    assert visible_close(candles, during) is None
    assert asof_view(full_swings, full_lines, full_states, during)["state"] is None
    row = observation_row("EUR_USD", "H1", full_states[0], "abc", "protocol")
    assert row["trading_decision"] is None
    assert row["outcome"] is None
    assert row["confidence"] is None
    assert K == 2
    from forex_bot.ai_ensemble import _quant_stub_vote
    from forex_bot.rl_agent import RLAgent
    from forex_bot.strategy_meta import strategies

    assert all(not item.active and not item.authorised_for_live for item in strategies.values())
    assert _quant_stub_vote({"returns": 1})["allow"] is False
    assert RLAgent().decide("unseen") == "UNAVAILABLE"
    bot = open("forex_bot/bot_loop.py", encoding="utf-8").read()
    ensemble = open("forex_bot/ai_ensemble.py", encoding="utf-8").read()
    assert "learning.structure" not in bot
    assert "confirmed_swings" not in bot
    assert "learning.structure" not in ensemble
    assert "confirmed_swings" not in ensemble
