"""Stage-3 macro x FX mining helpers. No bot_loop. No source JSONL/FX writes."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PATH = Path("reports/decision_quality/_macro_us_fx_event_mining_stage3.py")
_SPEC = importlib.util.spec_from_file_location("macro_us_fx_event_mining_stage3", _PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)

floor_m5 = _MOD.floor_m5
last_completed_m5_start = _MOD.last_completed_m5_start
t0_on_m5_boundary = _MOD.t0_on_m5_boundary
usd_normalize_native_move = _MOD.usd_normalize_native_move
classify_cont = _MOD.classify_cont
eligible_events = _MOD.eligible_events


def test_lookahead_t0_on_m5_boundary():
    t0 = datetime(2025, 9, 11, 12, 30, tzinfo=timezone.utc)
    assert t0_on_m5_boundary(t0)
    assert floor_m5(t0) == t0
    last = last_completed_m5_start(t0)
    assert last == datetime(2025, 9, 11, 12, 25, tzinfo=timezone.utc)
    assert last + timedelta(minutes=5) <= t0
    containing = floor_m5(t0)
    assert not (containing + timedelta(minutes=5) <= t0 and containing == t0)


def test_lookahead_t0_inside_candle():
    t0 = datetime(2025, 9, 11, 12, 31, tzinfo=timezone.utc)
    assert not t0_on_m5_boundary(t0)
    containing = floor_m5(t0)
    assert containing == datetime(2025, 9, 11, 12, 30, tzinfo=timezone.utc)
    last = last_completed_m5_start(t0)
    assert last == datetime(2025, 9, 11, 12, 25, tzinfo=timezone.utc)
    assert last + timedelta(minutes=5) <= t0
    assert containing + timedelta(minutes=5) > t0


def test_usd_sign_normalization():
    assert usd_normalize_native_move("EUR_USD", -10.0) == 10.0
    assert usd_normalize_native_move("GBP_USD", 4.0) == -4.0
    assert usd_normalize_native_move("AUD_USD", -1.0) == 1.0
    assert usd_normalize_native_move("USD_JPY", 8.0) == 8.0
    assert usd_normalize_native_move("USD_CAD", -3.0) == -3.0
    assert usd_normalize_native_move("USD_CHF", 2.0) == 2.0


def test_continuation_classifier():
    assert classify_cont(5.0, 8.0) == "continuation"
    assert classify_cont(-4.0, -1.0) == "continuation"
    assert classify_cont(5.0, -2.0) == "reversal"
    assert classify_cont(0.0, 3.0) == "flat"
    assert classify_cont(3.0, 0.0) == "flat"


def test_eligibility_excludes_unpublished_and_blocked():
    events = [
        {"macro_event_id": "ok", "archive_status": "ARCHIVED", "raw_document_hash": "abc", "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE", "scheduled_release_utc": "2025-09-11T12:30:00Z"},
        {"macro_event_id": "unpub", "archive_status": "OFFICIALLY_UNPUBLISHED", "raw_document_hash": None, "pit_status": "UNKNOWN", "scheduled_release_utc": None},
        {"macro_event_id": "blocked", "archive_status": "RETRIEVAL_BLOCKED", "raw_document_hash": None, "pit_status": "UNKNOWN", "scheduled_release_utc": "2026-08-12T12:30:00Z"},
    ]
    keep, drop = eligible_events(events)
    assert [e["macro_event_id"] for e in keep] == ["ok"]
    dropped = {d["macro_event_id"]: d["reasons"] for d in drop}
    assert "officially_unpublished" in dropped["unpub"]
    assert "retrieval_blocked" in dropped["blocked"]


def test_two_month_cpi_not_used_as_mom_accel():
    event = {
        "family": "CPI",
        "series": {
            "headline_mom": {"actual": None, "previous_as_reported": None},
            "headline_2m_sa": {"actual": 0.2, "previous_as_reported": None},
        },
        "median_usd_pips_post": {60: 10.0},
        "macro_event_id": "usd_cpi_2025-12-18",
    }
    mom = (event["series"].get("headline_mom") or {}).get("actual")
    prev = (event["series"].get("headline_mom") or {}).get("previous_as_reported")
    assert mom is None or prev is None
