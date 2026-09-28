"""US PIT Stage-2 helpers. Research-only. No bot_loop. No source JSONL writes."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

_PATH = Path("reports/decision_quality/_macro_us_pit_stage2.py")
_SPEC = importlib.util.spec_from_file_location("macro_us_pit_stage2", _PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)

et_wall_to_utc = _MOD.et_wall_to_utc
parse_fomc_statement = _MOD.parse_fomc_statement
last_completed_m5_start = _MOD.last_completed_m5_start
floor_m5 = _MOD.floor_m5
fx_coverage_for_event = _MOD.fx_coverage_for_event
store_artifact = _MOD.store_artifact
validate_archive = _MOD.validate_archive
_value_row = _MOD._value_row
_enrich_cpi = _MOD._enrich_cpi
parse_cpi_release = _MOD.parse_cpi_release


def test_dst_utc_conversion():
    winter = et_wall_to_utc(2026, 1, 13, 8, 30)
    summer = et_wall_to_utc(2026, 7, 14, 8, 30)
    fomc_edt = et_wall_to_utc(2025, 9, 17, 14, 0)
    fomc_est = et_wall_to_utc(2025, 12, 10, 14, 0)
    assert winter == datetime(2026, 1, 13, 13, 30, tzinfo=timezone.utc)
    assert summer == datetime(2026, 7, 14, 12, 30, tzinfo=timezone.utc)
    assert fomc_edt == datetime(2025, 9, 17, 18, 0, tzinfo=timezone.utc)
    assert fomc_est == datetime(2025, 12, 10, 19, 0, tzinfo=timezone.utc)


def test_event_value_normalization_and_multi_value():
    row = _value_row("usd_cpi_2025-09-11", "headline_mom", 0.4, unit="percent", sa="SA", previous_as_reported=0.2)
    assert row["macro_event_id"] == "usd_cpi_2025-09-11"
    assert row["value_id"] == "usd_cpi_2025-09-11:headline_mom"
    assert row["consensus"] is None
    assert row["consensus_asof_utc"] is None
    rows = [
        _value_row("usd_cpi_2025-09-11", "headline_mom", 0.4, unit="percent", sa="SA"),
        _value_row("usd_cpi_2025-09-11", "core_mom", 0.3, unit="percent", sa="SA"),
    ]
    assert {r["macro_event_id"] for r in rows} == {"usd_cpi_2025-09-11"}
    assert len({r["value_id"] for r in rows}) == 2


def test_first_print_immutability_and_revision_preservation():
    events = [
        {"macro_event_id": "usd_empsit_2025-09-05", "event_family": "EMPLOYMENT_SITUATION", "archive_status": "ARCHIVED", "reference_period": "2025-08", "consensus": None},
        {"macro_event_id": "usd_empsit_2025-11-20", "event_family": "EMPLOYMENT_SITUATION", "archive_status": "ARCHIVED", "reference_period": "2025-09", "consensus": None},
        {"macro_event_id": "usd_empsit_2025-12-16", "event_family": "EMPLOYMENT_SITUATION", "archive_status": "ARCHIVED", "reference_period": "2025-11", "consensus": None},
    ]
    values = [
        _value_row("usd_empsit_2025-09-05", "nonfarm_payroll_change", 22000, unit="persons", sa="SA"),
        _value_row("usd_empsit_2025-11-20", "nfp_revision_august", -4000, unit="persons", sa="SA", previous_as_reported=22000, previous_revised=-4000, revision_amount=-26000, notes="revision_to_August"),
        _value_row("usd_empsit_2025-12-16", "nfp_revision_august", -26000, unit="persons", sa="SA", previous_as_reported=-4000, previous_revised=-26000, revision_amount=-22000, notes="revision_to_August"),
    ]
    problems = validate_archive(events, values, [])
    assert "first_print_overwrite" not in problems or problems["first_print_overwrite"] == []
    first = [v for v in values if v["value_id"] == "usd_empsit_2025-09-05:nonfarm_payroll_change"][0]
    assert first["actual_first_print"] == 22000
    later = [v["actual_first_print"] for v in values if v["series_name"] == "nfp_revision_august"]
    assert later == [-4000, -26000]


def test_artifact_hash_duplicate_and_new_vintage(tmp_path: Path):
    body = b"official artifact v1"
    first = store_artifact(tmp_path, "x.official.txt", body, "https://example.invalid/a", "2026-09-28T00:00:00Z", "2025-09-11")
    second = store_artifact(tmp_path, "x.official.txt", body, "https://example.invalid/a", "2026-09-28T00:00:01Z", "2025-09-11")
    assert first["sha256"] == second["sha256"]
    assert second["reused"] is True
    assert second["hash_changed"] is False
    third = store_artifact(tmp_path, "x.official.txt", b"official artifact v2", "https://example.invalid/a", "2026-09-28T00:00:02Z", "2025-09-11")
    assert third["hash_changed"] is True
    assert third["sha256"] != first["sha256"]
    assert (tmp_path / "x.official.txt").read_bytes() == body


def test_null_consensus_enforced():
    events = [{"macro_event_id": "x", "event_family": "CPI", "archive_status": "ARCHIVED", "raw_document_hash": "abc", "consensus": None, "scheduled_release_utc": "2025-09-11T12:30:00Z", "reference_period": "2025-08"}]
    bad = _value_row("x", "headline_mom", 0.4, unit="percent", sa="SA")
    bad["consensus"] = 0
    problems = validate_archive(events, [bad], [])
    assert "consensus_not_null" in problems
    assert "consensus_zero_not_allowed" in problems


def test_irregular_cpi_two_month_not_mom():
    text = """
CONSUMER PRICE INDEX - NOVEMBER 2025
The Consumer Price Index for All Urban Consumers (CPI-U) increased 0.2 percent on a seasonally adjusted basis over the
2 months from September 2025 to November 2025, the U.S. Bureau of Labor Statistics reported today. Over the last 12
months, the all items index increased 2.7 percent before seasonal adjustment.
The seasonally adjusted index for all items less food and energy rose 0.2 percent over the 2 months ending in November.
The all items less food and energy index rose 2.6 percent over the last 12 months.
"""
    parsed = _enrich_cpi(parse_cpi_release(text), text)
    assert parsed["irregular_two_month"] is True
    assert parsed["headline_mom_first_print"] is None
    assert parsed["core_mom_first_print"] is None
    assert parsed["headline_2m_sa"] == 0.2
    assert parsed["headline_yoy_first_print"] == 2.7
    assert parsed["validation_status"] == "IRREGULAR"


def test_fomc_target_range():
    cut = parse_fomc_statement("For release at 2:00 p.m. EDT\nThe Committee decided to lower the target range for the federal funds rate by 1/4 percentage point to 4 to 4-1/4 percent.")
    hold = parse_fomc_statement("For release at 2:00 p.m. EST\nThe Committee decided to maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent.")
    assert cut["target_range_lower"] == 4.0
    assert cut["target_range_upper"] == 4.25
    assert cut["change_bps"] == -25
    assert cut["previous_target_range_lower"] == 4.25
    assert hold["change_bps"] == 0
    assert hold["target_range_lower"] == 3.5
    assert hold["target_range_upper"] == 3.75


def test_fx_coverage_boundary_inside_candle():
    t0 = datetime(2025, 9, 11, 12, 30, tzinfo=timezone.utc)
    assert last_completed_m5_start(t0) == datetime(2025, 9, 11, 12, 25, tzinfo=timezone.utc)
    assert floor_m5(t0) == datetime(2025, 9, 11, 12, 30, tzinfo=timezone.utc)
    bars = {
        "EUR_USD": {
            "2025-09-11T08:25:00Z",
            "2025-09-11T08:30:00Z",
            "2025-09-11T12:25:00Z",
            "2025-09-11T12:30:00Z",
            "2025-09-11T12:35:00Z",
            "2025-09-11T16:30:00Z",
        }
    }
    cov = fx_coverage_for_event(t0, bars)
    assert cov["pairs"]["EUR_USD"]["last_completed_present"] is True
    assert cov["pairs"]["EUR_USD"]["containing_present"] is True
    assert cov["pairs"]["EUR_USD"]["windows"]["-5m"] is True
    assert cov["pairs"]["EUR_USD"]["windows"]["+5m"] is True
    assert cov["pairs"]["EUR_USD"]["windows"]["-240m"] is True
    assert cov["pairs"]["EUR_USD"]["windows"]["+240m"] is True
    assert cov["lookahead_note"]
