"""Official BLS first-print research tests. Network is not required."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from forex_bot.decision_quality.isolation import assert_package_cannot_write_broker, forbidden_hits_in_source
from forex_bot.decision_quality.macro_first_print.alfred import (
    ALFRED_USED_AS_FIRST_PRINT,
    FRED_CURRENT_USED_AS_FIRST_PRINT,
)
from forex_bot.decision_quality.macro_first_print.build import assemble_event
from forex_bot.decision_quality.macro_first_print.catalog import CatalogEntry, catalog_from_year_text
from forex_bot.decision_quality.macro_first_print.parse_common import parse_payroll, parse_percent
from forex_bot.decision_quality.macro_first_print.parse_cpi import parse_cpi_release
from forex_bot.decision_quality.macro_first_print.parse_empsit import parse_empsit_release
from forex_bot.decision_quality.macro_first_print.schema import NormalizedEvent
from forex_bot.decision_quality.macro_first_print.store import sha256_bytes, write_raw_release
from forex_bot.decision_quality.macro_first_print.validate import first_prints_immutable, quality_checks
from forex_bot.decision_quality.schedule import local_clock_to_utc

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "macro_first_print"
PKG = ROOT / "forex_bot" / "decision_quality" / "macro_first_print"
YEAR_TEXT = ROOT / "data" / "research" / "external" / "raw" / "BLS" / "2026-09-19" / "year_2025_cpi_empsit.txt"


def _text(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _entry(event_type: str, ref: str, release: str) -> CatalogEntry:
    local = datetime.strptime(f"{release} 08:30", "%Y-%m-%d %H:%M")
    utc = local_clock_to_utc(local, "America/New_York")
    return CatalogEntry(
        event_type=event_type,
        reference_period=ref,
        release_date=release,
        scheduled_time_local=f"{release}T08:30:00",
        timezone="America/New_York",
        scheduled_time_utc=utc.isoformat(timespec="seconds") + "Z",
        source_url="https://www.bls.gov/news.release/archives/fixture.htm",
        release_name=f"{event_type} {ref}",
    )


def test_no_production_imports_or_side_effects():
    assert assert_package_cannot_write_broker() == []
    for path in PKG.glob("*.py"):
        hits = forbidden_hits_in_source(path.read_text(encoding="utf-8"))
        assert hits == []
    assert ALFRED_USED_AS_FIRST_PRINT is False
    assert FRED_CURRENT_USED_AS_FIRST_PRINT is False


def test_cpi_percentage_parsing_from_official_lead():
    parsed = parse_cpi_release(_text("cpi_2025-01-15_lead.txt"))
    assert parsed["headline_mom_first_print"] == 0.4
    assert parsed["headline_yoy_first_print"] == 2.9
    assert parsed["core_mom_first_print"] == 0.2
    assert parsed["core_yoy_first_print"] == 3.2
    assert parsed["previous_headline_mom_as_known"] == 0.3
    assert parsed["previous_headline_yoy_as_known"] == 2.7
    assert parsed["reference_period"] == "2024-12"
    assert parsed["release_number"] == "USDL-25-0021"
    assert parsed["validation_status"] == "VERIFIED_FIRST_PRINT"


def test_cpi_html_table_does_not_confuse_all_items_with_core():
    parsed = parse_cpi_release(_text("cpi_html_table.html"))
    assert parsed["headline_mom_first_print"] == 0.4
    assert parsed["headline_yoy_first_print"] == 2.9
    assert parsed["core_mom_first_print"] == 0.2
    assert parsed["core_yoy_first_print"] == 3.2
    assert parsed["validation_status"] == "VERIFIED_FIRST_PRINT"


def test_nfp_integer_parsing_and_revisions():
    parsed = parse_empsit_release(_text("empsit_2025-01-10_lead.txt"))
    assert parsed["nfp_first_print"] == 256000
    assert parsed["unemployment_rate_first_print"] == 4.1
    assert parsed["ahe_mom_first_print"] == 0.3
    assert parsed["ahe_yoy_first_print"] == 3.9
    assert parsed["participation_rate_first_print"] == 62.5
    assert parsed["previous_nfp_as_presented"] == 212000
    assert parsed["previous_nfp_revision"] == -15000
    assert parsed["two_month_nfp_revision"] == -8000
    assert parsed["reference_period"] == "2024-12"
    assert parsed["validation_status"] == "VERIFIED_FIRST_PRINT"


def test_parenthetical_and_edged_nfp_and_rate_at():
    text = (
        "THE EMPLOYMENT SITUATION -- JULY 2025\n"
        "Total nonfarm payroll employment changed little in July (+73,000) and has shown little change since April.\n"
        "The unemployment rate, at 4.2 percent, also changed little.\n"
        "The labor force participation rate (62.2 percent) changed little.\n"
        "Average hourly earnings for all employees on private nonfarm payrolls rose by 12 cents, or 0.3 percent, to $36.44. "
        "Over the past 12 months, average hourly earnings have increased by 3.9 percent.\n"
    )
    parsed = parse_empsit_release(text)
    assert parsed["nfp_first_print"] == 73000
    assert parsed["unemployment_rate_first_print"] == 4.2
    assert parsed["participation_rate_first_print"] == 62.2
    edged = parse_empsit_release(
        "THE EMPLOYMENT SITUATION -- SEPTEMBER 2025\n"
        "Total nonfarm payroll employment edged up by 119,000 in September.\n"
        "The unemployment rate, at 4.4 percent, changed little in September.\n"
        "The labor force participation rate, at 62.4 percent, changed little over the month.\n"
        "Average hourly earnings for all employees on private nonfarm payrolls rose by 10 cents, or 0.3 percent, to $36.67. "
        "Over the past 12 months, average hourly earnings have increased by 3.8 percent.\n"
    )
    assert edged["nfp_first_print"] == 119000
    assert edged["unemployment_rate_first_print"] == 4.4


def test_two_month_cpi_is_not_treated_as_mom_first_print():
    text = (
        "CONSUMER PRICE INDEX - NOVEMBER 2025\n"
        "The Consumer Price Index for All Urban Consumers (CPI-U) increased 0.2 percent on a seasonally adjusted basis "
        "over the 2 months from September 2025 to November 2025. Over the last 12 months, the all items index "
        "increased 2.7 percent before seasonal adjustment.\n"
        "The all items less food and energy index rose 2.6 percent over the last 12 months.\n"
    )
    parsed = parse_cpi_release(text)
    assert parsed["headline_mom_first_print"] is None
    assert parsed["headline_yoy_first_print"] == 2.7
    assert parsed["core_yoy_first_print"] == 2.6
    assert parsed["validation_status"] == "AMBIGUOUS"
    assert "two_month" in (parsed["notes"] or "")


def test_negative_payroll_change():
    parsed = parse_empsit_release(_text("empsit_negative_nfp.txt"))
    assert parsed["nfp_first_print"] == -33000
    assert parsed["unemployment_rate_first_print"] == 4.3
    assert parsed["previous_nfp_as_presented"] == 150000
    assert parsed["previous_nfp_revision"] == -25000
    assert parsed["two_month_nfp_revision"] == -35000


def test_revised_previous_does_not_overwrite_first_print():
    jan = assemble_event(
        _entry("EMPLOYMENT_SITUATION", "2025-01", "2025-02-07"),
        parse_empsit_release(_text("empsit_jan_first_print.txt")),
        None,
    )
    feb = assemble_event(
        _entry("EMPLOYMENT_SITUATION", "2025-02", "2025-03-07"),
        parse_empsit_release(_text("empsit_feb_revises_jan.txt")),
        None,
    )
    assert jan.nfp_first_print == 150000
    assert feb.nfp_first_print == 200000
    assert feb.previous_nfp_as_presented == 125000
    assert feb.previous_nfp_revision == -25000
    assert first_prints_immutable([jan, feb]) == []

    overwritten = NormalizedEvent(**{**jan.to_dict(), "nfp_first_print": 125000})
    problems = first_prints_immutable([overwritten, feb])
    assert any("overwrite" in p for p in problems)


def test_first_print_immutability_across_assemble():
    jan_parsed = parse_empsit_release(_text("empsit_jan_first_print.txt"))
    feb_parsed = parse_empsit_release(_text("empsit_feb_revises_jan.txt"))
    jan = assemble_event(_entry("EMPLOYMENT_SITUATION", "2025-01", "2025-02-07"), jan_parsed, None)
    feb = assemble_event(_entry("EMPLOYMENT_SITUATION", "2025-02", "2025-03-07"), feb_parsed, None)
    assert jan.nfp_first_print != feb.previous_nfp_as_presented
    assert jan.nfp_first_print + feb.previous_nfp_revision == feb.previous_nfp_as_presented


def test_timezone_conversion_est_and_edt():
    est = local_clock_to_utc(datetime(2025, 1, 10, 8, 30), "America/New_York")
    edt = local_clock_to_utc(datetime(2025, 7, 3, 8, 30), "America/New_York")
    assert est == datetime(2025, 1, 10, 13, 30)
    assert edt == datetime(2025, 7, 3, 12, 30)
    # Must not hard-code 08:30 ET = 13:30 UTC year-round.
    assert est.hour != edt.hour


def test_catalog_2025_uses_official_year_schedule():
    catalog = catalog_from_year_text(YEAR_TEXT.read_text(encoding="utf-8"))
    cpi = [e for e in catalog if e.event_type == "CPI" and e.release_date.startswith("2025-")]
    emp = [e for e in catalog if e.event_type == "EMPLOYMENT_SITUATION" and e.release_date.startswith("2025-")]
    assert len(cpi) == 11
    assert len(emp) == 11
    jan_emp = next(e for e in emp if e.release_date == "2025-01-10")
    assert jan_emp.scheduled_time_utc == "2025-01-10T13:30:00Z"
    jul_emp = next(e for e in emp if e.release_date == "2025-07-03")
    assert jul_emp.scheduled_time_utc == "2025-07-03T12:30:00Z"
    assert not any(e.reference_period == "2025-10" for e in catalog)


def test_duplicate_detection():
    parsed = parse_cpi_release(_text("cpi_2025-01-15_lead.txt"))
    a = assemble_event(_entry("CPI", "2024-12", "2025-01-15"), parsed, None)
    b = assemble_event(_entry("CPI", "2024-12", "2025-01-15"), parsed, None)
    b.event_id = "CPI_2024-12_2025-01-15_dup"
    q = quality_checks([a, b], expected_cpi=11, expected_emp=11)
    assert "CPI:2025-01-15" in q["duplicate_release_dates"]


def test_missing_field_and_malformed_source():
    missing = parse_cpi_release("CONSUMER PRICE INDEX - JANUARY 2025\nThe CPI-U increased 0.2 percent on a seasonally adjusted basis in January.")
    assert missing["headline_mom_first_print"] == 0.2
    assert missing["core_yoy_first_print"] is None
    assert missing["validation_status"] == "PARTIAL"
    bad = parse_empsit_release(_text("malformed_release.txt"))
    assert bad["nfp_first_print"] is None
    assert bad["validation_status"] == "FAILED"
    assert parse_percent("not-a-number") is None
    assert parse_payroll("12,000") == 12000
    assert parse_payroll("99999999") is None


def test_provenance_and_hash_never_overwrite(tmp_path):
    body = b"<html>official release</html>"
    first = write_raw_release(
        dest_dir=tmp_path,
        filename="cpi_01152025.htm",
        body=body,
        source_url="https://www.bls.gov/news.release/archives/cpi_01152025.htm",
        http_status=200,
        content_type="text/html",
        publication_date="2025-01-15",
        release_number="USDL-25-0021",
        retrieved_at="2026-09-23T00:00:00Z",
    )
    again = write_raw_release(
        dest_dir=tmp_path,
        filename="cpi_01152025.htm",
        body=body,
        source_url="https://www.bls.gov/news.release/archives/cpi_01152025.htm",
        http_status=200,
        content_type="text/html",
        publication_date="2025-01-15",
        release_number="USDL-25-0021",
        retrieved_at="2026-09-23T01:00:00Z",
    )
    assert first.sha256 == sha256_bytes(body)
    assert again.reused is True
    assert again.hash_changed is False
    assert (tmp_path / "cpi_01152025.htm").read_bytes() == body
    changed = write_raw_release(
        dest_dir=tmp_path,
        filename="cpi_01152025.htm",
        body=b"<html>different</html>",
        source_url="https://www.bls.gov/news.release/archives/cpi_01152025.htm",
        http_status=200,
        content_type="text/html",
        publication_date="2025-01-15",
        release_number="USDL-25-0021",
        retrieved_at="2026-09-23T02:00:00Z",
    )
    assert changed.hash_changed is True
    assert changed.body_path != first.body_path
    assert (tmp_path / "cpi_01152025.htm").read_bytes() == body
