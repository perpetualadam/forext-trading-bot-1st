"""Focused tests for Quant V2 Experiment C M1 path-order primitives."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forex_bot.decision_quality.download_history import format_plan, main, plan_range
from forex_bot.decision_quality.event_discovery import SPLIT_T50, SPLIT_T75, assign_split, event_bootstrap_mean
from forex_bot.decision_quality.history_cache import RESEARCH_SYMBOLS, TimeWindow, default_m1_historical_dir
from forex_bot.decision_quality.m1_path import (
    EVENT_FAMILIES,
    FIRST_ELIGIBLE_M1_OFFSET_MIN,
    HORIZONS_MIN,
    HURDLE_MULTS,
    POS_RANGE_Q1,
    POS_RANGE_Q5,
    RESID_PCA6_EDGES,
    classify_same_bar_touch,
    event_forming_m1_starts,
    first_eligible_m1_time,
    first_touch_labels,
    half_spread_pips,
    half_spread_price,
    instrument_reversal_side,
    last_m1_time_for_horizon,
    range_events,
    summarize_labels,
)
from forex_bot.decision_quality.spread_volume import half_close_spread, to_pips
from forex_bot.oanda_candles_read import request_candles_page
from forex_bot.profit_protection import pip_size


def test_m1_downloader_granularity_default_unchanged():
    calls: list[dict] = []

    def request_fn(instrument: str, params: dict) -> dict:
        calls.append(params)
        return {"candles": []}

    request_candles_page(
        "EUR_USD",
        datetime(2025, 9, 1, 0, 0, 0),
        datetime(2025, 9, 1, 0, 5, 0),
        request_fn=request_fn,
        now_utc=datetime(2025, 9, 2, 0, 0, 0),
    )
    assert calls[0]["granularity"] == "M5"
    assert calls[0]["price"] == "MBA"


def test_m1_downloader_granularity_m1():
    calls: list[dict] = []

    def request_fn(instrument: str, params: dict) -> dict:
        calls.append(params)
        return {
            "candles": [
                {
                    "time": "2025-09-01T00:00:00.000000000Z",
                    "complete": True,
                    "volume": 4,
                    "mid": {"o": "1.1", "h": "1.2", "l": "1.0", "c": "1.15"},
                    "bid": {"o": "1.0999", "h": "1.1999", "l": "0.9999", "c": "1.1499"},
                    "ask": {"o": "1.1001", "h": "1.2001", "l": "1.0001", "c": "1.1501"},
                }
            ]
        }

    df = request_candles_page(
        "EUR_USD",
        datetime(2025, 9, 1, 0, 0, 0),
        datetime(2025, 9, 1, 0, 1, 0),
        request_fn=request_fn,
        now_utc=datetime(2025, 9, 2, 0, 0, 0),
        granularity="M1",
    )
    assert calls[0]["granularity"] == "M1"
    assert len(df) == 1
    assert float(df["bid_close"].iloc[0]) == pytest.approx(1.1499)


def test_m1_cache_dir_is_separate_from_m5():
    m1 = default_m1_historical_dir()
    assert m1.as_posix().endswith("data/historical/m1")
    assert "M5" not in m1.name


def test_m5_m1_causal_timestamp_boundary():
    t = pd.Timestamp("2025-09-01 10:00:00")
    first = first_eligible_m1_time(t)
    assert first == pd.Timestamp("2025-09-01 10:05:00")
    forming = event_forming_m1_starts(t)
    assert forming == [
        pd.Timestamp("2025-09-01 10:00:00"),
        pd.Timestamp("2025-09-01 10:01:00"),
        pd.Timestamp("2025-09-01 10:02:00"),
        pd.Timestamp("2025-09-01 10:03:00"),
        pd.Timestamp("2025-09-01 10:04:00"),
    ]
    assert first not in forming
    assert FIRST_ELIGIBLE_M1_OFFSET_MIN == 5
    assert last_m1_time_for_horizon(first, 15) == pd.Timestamp("2025-09-01 10:19:00")


def test_no_inclusion_of_event_forming_m1_candles():
    entry = 1.1000
    cost = 0.0001
    # Forming bar 10:04 goes UP through cost; first eligible 10:05 goes DOWN.
    times = pd.date_range("2025-09-01 10:00", periods=20, freq="min")
    high = np.full(20, entry)
    low = np.full(20, entry)
    high[4] = entry + 2 * cost  # 10:04 forming
    low[5] = entry - 2 * cost  # 10:05 eligible
    first = first_eligible_m1_time(pd.Timestamp("2025-09-01 10:00"))
    rec = first_touch_labels(
        times.to_numpy(),
        high,
        low,
        first_eligible=first,
        entry_close=entry,
        cost_price=cost,
    )
    assert rec["15m_1x"]["label"] == "DOWN_FIRST"


def test_first_touch_up_down_neither():
    entry = 1.0
    cost = 0.01
    times = pd.date_range("2025-09-01 10:05", periods=15, freq="min")
    high = np.full(15, entry)
    low = np.full(15, entry)
    high[2] = entry + 0.02
    rec = first_touch_labels(times.to_numpy(), high, low, first_eligible=times[0], entry_close=entry, cost_price=cost)
    assert rec["15m_1x"]["label"] == "UP_FIRST"
    low2 = low.copy()
    high2 = np.full(15, entry)
    low2[1] = entry - 0.02
    rec2 = first_touch_labels(times.to_numpy(), high2, low2, first_eligible=times[0], entry_close=entry, cost_price=cost)
    assert rec2["15m_1x"]["label"] == "DOWN_FIRST"
    rec3 = first_touch_labels(
        times.to_numpy(),
        np.full(15, entry),
        np.full(15, entry),
        first_eligible=times[0],
        entry_close=entry,
        cost_price=cost,
    )
    assert rec3["15m_1x"]["label"] == "NEITHER"


def test_same_m1_candle_ambiguity():
    assert classify_same_bar_touch(1.02, 0.98, 1.00, 0.01) == "M1_AMBIGUOUS"
    entry = 1.0
    cost = 0.01
    times = pd.date_range("2025-09-01 10:05", periods=15, freq="min")
    high = np.full(15, entry)
    low = np.full(15, entry)
    high[0] = entry + 0.02
    low[0] = entry - 0.02
    rec = first_touch_labels(times.to_numpy(), high, low, first_eligible=times[0], entry_close=entry, cost_price=cost)
    assert rec["15m_1x"]["label"] == "M1_AMBIGUOUS"


def test_missing_m1_is_insufficient_not_neither():
    entry = 1.0
    cost = 0.01
    # Only first 3 minutes present; later open minutes missing.
    times = pd.date_range("2025-09-01 10:05", periods=3, freq="min")
    rec = first_touch_labels(
        times.to_numpy(),
        np.full(3, entry),
        np.full(3, entry),
        first_eligible=times[0],
        entry_close=entry,
        cost_price=cost,
    )
    assert rec["15m_1x"]["label"] == "INSUFFICIENT_DATA"


def test_event_time_half_spread_and_jpy_pips():
    assert half_spread_price(1.1002, 1.1000) == pytest.approx(0.0001)
    assert half_spread_pips(1.1002, 1.1000, "EUR_USD") == pytest.approx(1.0)
    assert pip_size("USD_JPY") == pytest.approx(0.01)
    assert half_spread_pips(150.02, 150.00, "USD_JPY") == pytest.approx(1.0)
    assert to_pips(half_close_spread(np.array([150.02]), np.array([150.00])), "USD_JPY")[0] == pytest.approx(1.0)


def test_frozen_m5_event_definitions():
    assert EVENT_FAMILIES["range_bottom"]["hypothesis"] == "UP"
    assert EVENT_FAMILIES["range_top"]["hypothesis"] == "DOWN"
    assert EVENT_FAMILIES["breakout_up_24"]["hypothesis"] == "DOWN"
    assert EVENT_FAMILIES["breakout_dn_24"]["hypothesis"] == "UP"
    pos = np.array([0.5, 0.10, 0.10, 0.5])
    g = np.array(["EUR_USD"] * 4)
    ev = range_events(pos, g)
    assert ev["range_bottom"].tolist() == [False, True, False, False]
    assert POS_RANGE_Q1 == pytest.approx(0.1911764703070358)
    assert POS_RANGE_Q5 == pytest.approx(0.8314606732231985)
    assert len(RESID_PCA6_EDGES) == 6


def test_reversal_maps_to_instrument_side():
    assert instrument_reversal_side("EUR_USD", 0.01) == "UP"
    assert instrument_reversal_side("USD_JPY", 0.01) == "DOWN"


def test_base_rate_and_splits_preserved():
    labels = ["UP_FIRST"] * 6 + ["DOWN_FIRST"] * 4 + ["NEITHER"] * 10
    rec = summarize_labels(labels, "UP")
    assert rec["n"] == 20
    assert rec["favorable_first"] == 6
    assert rec["adverse_first"] == 4
    assert rec["fav_minus_adv"] == pytest.approx(0.1)
    t = pd.Series([SPLIT_T50 - pd.Timedelta(days=1), SPLIT_T50 + pd.Timedelta(days=1), SPLIT_T75 + pd.Timedelta(days=1)])
    assert list(assign_split(t)) == ["train", "valid", "discovery_test"]
    assert HORIZONS_MIN == (15, 30, 60, 120, 240, 480)
    assert HURDLE_MULTS == (1.0, 1.5, 2.0, 3.0)


def test_bootstrap_seed_and_m5_immutability():
    x = np.array([1.0, 0.0, 1.0, 0.0] * 10)
    a = event_bootstrap_mean(x, seed=42, reps=30)
    b = event_bootstrap_mean(x, seed=42, reps=30)
    assert a == b
    path = Path("data/historical/EUR_USD_M5.csv")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    _ = pd.read_csv(path, nrows=2)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after


def test_no_lookahead_first_eligible_after_event():
    t = pd.Timestamp("2025-09-01 12:00:00")
    assert first_eligible_m1_time(t) > t
    window = plan_range(start="2025-09-01T00:00:00", end="2026-08-31T23:59:00")
    text = format_plan(window, RESEARCH_SYMBOLS, Path("data/historical/m1"), granularity="M1")
    assert "M1" in text
    assert "EUR_USD_M1.csv" in text
    assert "never overwrites M5" in text


def test_m1_cli_dry_run_default(capsys):
    code = main(
        [
            "--granularity",
            "M1",
            "--start",
            "2025-09-01T00:00:00",
            "--end",
            "2025-09-01T01:00:00",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "granularity: M1" in out
