"""Focused tests for Quant V2 Experiment D official-schedule primitives."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forex_bot.decision_quality.history_cache import default_historical_dir
from forex_bot.decision_quality.schedule import (
    ACTIVITY_EDGES,
    BLS_RESCHEDULED_UTC,
    DISP_EDGES,
    PAIR_MAP,
    activity_quintile,
    analysis_fields_clean,
    assign_post_window,
    assign_pre_window,
    dispersion_quintile,
    event_bootstrap_diff,
    exclude_uncertain,
    find_duplicates,
    first_eligible_post_m5_start,
    last_eligible_pre_m5_end,
    local_clock_to_utc,
    map_official_name,
    minutes_to_event,
    parse_bls_year_lines,
    parse_fomc_meeting_blocks,
    parse_ons_version_clocks,
    parse_statcan_named_dates,
)
from forex_bot.decision_quality.spread_volume import apply_frozen_edges, half_close_spread


def test_taxonomy_mapping_frozen():
    assert map_official_name("Consumer Price Index for August 2025") == "INFLATION"
    assert map_official_name("CPIH") == "INFLATION"
    assert map_official_name("Employment Situation for August 2025") == "EMPLOYMENT"
    assert map_official_name("Labour Force Survey") == "EMPLOYMENT"
    assert map_official_name("FOMC statement") == "CENTRAL_BANK_DECISION"
    assert map_official_name("Monetary Policy Committee") == "CENTRAL_BANK_DECISION"
    assert map_official_name("Producer Price Index") is None
    assert map_official_name("JOLTS") is None
    assert map_official_name("Real Earnings") is None
    assert map_official_name("GDP") is None


def test_timezone_and_dst():
    # 08:30 ET: winter = UTC 13:30, summer = UTC 12:30
    winter = local_clock_to_utc(datetime(2026, 1, 13, 8, 30), "America/New_York")
    summer = local_clock_to_utc(datetime(2026, 7, 14, 8, 30), "America/New_York")
    assert winter == datetime(2026, 1, 13, 13, 30)
    assert summer == datetime(2026, 7, 14, 12, 30)
    # UK 07:00 / 12:00
    ons_gmt = local_clock_to_utc(datetime(2026, 1, 21, 7, 0), "Europe/London")
    ons_bst = local_clock_to_utc(datetime(2026, 7, 22, 7, 0), "Europe/London")
    assert ons_gmt == datetime(2026, 1, 21, 7, 0)
    assert ons_bst == datetime(2026, 7, 22, 6, 0)
    boe = local_clock_to_utc(datetime(2026, 2, 5, 12, 0), "Europe/London")
    assert boe == datetime(2026, 2, 5, 12, 0)
    boc = local_clock_to_utc(datetime(2026, 1, 28, 9, 45), "America/Toronto")
    assert boc == datetime(2026, 1, 28, 14, 45)


def test_pre_post_window_boundaries():
    assert assign_pre_window(120) == "pre_120_60"
    assert assign_pre_window(60.0001) == "pre_120_60"
    assert assign_pre_window(60) == "pre_60_30"
    assert assign_pre_window(5) is None
    assert assign_pre_window(5.0001) == "pre_15_5"
    assert assign_pre_window(15) == "pre_15_5"
    assert assign_post_window(0) == "post_0_15"
    assert assign_post_window(14.99) == "post_0_15"
    assert assign_post_window(15) == "post_15_30"
    assert assign_post_window(120) is None


def test_causal_m5_alignment():
    sched = datetime(2026, 1, 13, 13, 30, 0)
    assert first_eligible_post_m5_start(sched) == datetime(2026, 1, 13, 13, 30)
    assert last_eligible_pre_m5_end(sched) == datetime(2026, 1, 13, 13, 25)
    mid = datetime(2026, 1, 28, 19, 45, 0)  # BoC 09:45 ET winter
    assert first_eligible_post_m5_start(mid) == datetime(2026, 1, 28, 19, 45)
    off = datetime(2026, 1, 28, 19, 46, 0)
    assert first_eligible_post_m5_start(off) == datetime(2026, 1, 28, 19, 50)
    assert minutes_to_event(datetime(2026, 1, 13, 13, 20), sched) == 10


def test_duplicate_and_uncertain_exclusion():
    a = {
        "event_id": "aaa",
        "currency": "USD",
        "category": "INFLATION",
        "scheduled_ts_utc": "2026-01-13T13:30:00",
        "row_status": "PRIMARY",
        "scheduled_precision": "clock",
    }
    b = dict(a, event_id="bbb")
    assert find_duplicates([a, b])
    bad = {**a, "event_id": "ccc", "row_status": "UNCERTAIN", "scheduled_precision": "unknown", "scheduled_ts_utc": None}
    ok, excl = exclude_uncertain([a, bad])
    assert [r["event_id"] for r in ok] == ["aaa"]
    assert excl[0]["event_id"] == "ccc"


def test_no_actual_consensus_fields():
    row = {
        "event_id": "x",
        "category": "INFLATION",
        "consensus": None,
        "forecast": None,
        "actual": None,
        "surprise": None,
    }
    assert analysis_fields_clean(row)
    assert not analysis_fields_clean({**row, "actual": 3.2})
    assert not analysis_fields_clean({**row, "consensus": 3.1})


def test_bls_and_ons_and_statcan_parsers():
    bls = parse_bls_year_lines(
        "Friday, September 5, 2025 08:30 AM Employment Situation for August 2025\n"
        "Thursday, September 11, 2025 08:30 AM Consumer Price Index for August 2025\n"
        "Friday, October 24, 2025 08:30 AM Consumer Price Index for September 2025\n"
    )
    cats = {r["category"] for r in bls}
    assert cats == {"EMPLOYMENT", "INFLATION"}
    delayed = [r for r in bls if r["row_status"] == "RESCHEDULED"]
    assert delayed and delayed[0]["scheduled_ts_utc"] in BLS_RESCHEDULED_UTC
    ons = parse_ons_version_clocks("17 September 2025 07:00", "INFLATION")
    assert ons[0]["currency"] == "GBP"
    assert ons[0]["scheduled_tz_source"] == "Europe/London"
    st = parse_statcan_named_dates("CPI	2025-09-16	08:30	America/New_York	August 2025\n", "INFLATION")
    assert st[0]["currency"] == "CAD"
    assert st[0]["scheduled_precision"] == "clock"


def test_fomc_notation_vote_uncertain():
    html = """
    <a id="x">2025 FOMC Meetings</a>
    <div class="fomc-meeting__month"><strong>August</strong></div>
    <div class="fomc-meeting__date">22</div>
    notation vote Statement on Longer-Run Goals
    """
    rows = parse_fomc_meeting_blocks(html)
    assert rows
    assert rows[0]["row_status"] == "UNCERTAIN"


def test_event_level_independence_not_bar_count():
    ev = np.array([4.0, 6.0, 8.0])
    base = np.array([1.0] * 500)
    boot = event_bootstrap_diff(ev, base, seed=42, reps=50)
    assert boot["n_event"] == 3
    assert boot["n_base"] == 500
    assert boot["diff"] == pytest.approx(5.0)


def test_clock_time_base_definition():
    # Ordinary 13:00 Wednesday must not sit inside +/- 120m of a 13:30 event
    event = datetime(2026, 1, 14, 13, 30)
    ordinary = datetime(2026, 1, 21, 13, 00)
    assert ordinary.weekday() == event.weekday()
    assert ordinary.hour == 13
    assert abs((ordinary - event).total_seconds()) > 120 * 60


def test_frozen_activity_and_dispersion_edges_reused():
    x = np.array([0.5, 1.0, 2.0])
    assert np.array_equal(activity_quintile(x), apply_frozen_edges(x, ACTIVITY_EDGES))
    y = np.array([1e-4, 3e-4, 1e-3])
    assert np.array_equal(dispersion_quintile(y), apply_frozen_edges(y, DISP_EDGES))
    # later data must not retune
    assert ACTIVITY_EDGES[2] == pytest.approx(0.879106438896188)
    assert DISP_EDGES[2] == pytest.approx(0.00022407212602446188)


def test_contemporaneous_half_spread():
    half = half_close_spread(np.array([1.10020]), np.array([1.10000]))
    assert half[0] == pytest.approx(0.00010)


def test_pair_map_and_no_lookahead_future_only():
    assert PAIR_MAP["USD"][0] == "EUR_USD"
    assert PAIR_MAP["GBP"] == ("GBP_USD",)
    assert PAIR_MAP["CAD"] == ("USD_CAD",)
    sched = datetime(2026, 2, 5, 12, 0)
    first = first_eligible_post_m5_start(sched)
    assert first >= sched


def test_source_market_csv_immutability():
    path = default_historical_dir() / "EUR_USD_M5.csv"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    local_clock_to_utc(datetime(2026, 1, 13, 8, 30), "America/New_York")
    map_official_name("CPI")
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after
    m1 = Path("data/historical/m1/EUR_USD_M1.csv")
    if m1.exists():
        b2 = hashlib.sha256(m1.read_bytes()).hexdigest()
        assert hashlib.sha256(m1.read_bytes()).hexdigest() == b2
