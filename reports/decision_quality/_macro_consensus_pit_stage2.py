"""Consensus PIT Stage 2: remaining-20 historical reconstruction + report.

Does not rewrite the Stage-1 pilot evidence files.
Does not write to data/research/macro/us_pit/.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HIST_DIR = Path("data/research/macro/consensus_pit/historical")
RAW_DIR = HIST_DIR / "raw"
EVIDENCE_DIR = HIST_DIR / "evidence"
MANIFEST_DIR = HIST_DIR / "manifest"
NORM_DIR = HIST_DIR / "normalized"
GOLD_DIR = HIST_DIR / "gold"
SILVER_DIR = HIST_DIR / "silver"
REMAINING_PATH = MANIFEST_DIR / "remaining_events.json"
PILOT_EVIDENCE = Path("data/research/macro/consensus_pit/pilot/consensus_evidence.json")
PILOT_DIR = Path("data/research/macro/consensus_pit/pilot")
US_PIT_DIR = Path("data/research/macro/us_pit")
VALUES_PATH = US_PIT_DIR / "events" / "macro_event_value.json"
EVENTS_PATH = US_PIT_DIR / "events" / "macro_event.json"
REPORT_PATH = Path("reports/decision_quality/macro_consensus_pit_stage2.md")

PIT_SAFE = {"PIT_SAFE"}
PIT_OK_JOIN = {"PIT_SAFE", "PIT_SAFE_IF_USING_ARCHIVED_RELEASE"}
SCALAR_SERIES = {
    "headline_mom",
    "headline_yoy",
    "core_mom",
    "core_yoy",
    "nonfarm_payroll_change",
    "unemployment_rate",
    "average_hourly_earnings_mom",
    "average_hourly_earnings_yoy",
}
CONSENSUS_TYPES = {
    "SURVEY_CONSENSUS",
    "SURVEY_MEDIAN",
    "SURVEY_MEAN",
    "PROVIDER_CONSENSUS",
}


def parse_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def publication_before_t0(pub: str | None, t0: str | None) -> bool:
    p, t = parse_utc(pub), parse_utc(t0)
    return p is not None and t is not None and p < t


def exact_series_match(expectation: dict, official: dict) -> bool:
    return expectation.get("series_name") == official.get("series_name")


def units_match(expectation: dict, official: dict) -> bool:
    eu, ou = expectation.get("unit"), official.get("unit")
    if not eu or not ou:
        return False
    return eu == ou


def seasonal_match(expectation: dict, official: dict) -> bool:
    es, os_ = expectation.get("seasonal_adjustment"), official.get("seasonal_adjustment")
    if not es or not os_:
        return es == os_
    return es == os_


def reference_period_match(expectation: dict, event: dict) -> bool:
    return expectation.get("reference_period") == event.get("reference_period")


def is_individual_not_consensus(rec: dict) -> bool:
    return rec.get("expectation_type") == "INDIVIDUAL_FORECAST" and "CONSENSUS" not in rec.get("expectation_type", "")


def fomc_probs_not_collapsed(rec: dict) -> bool:
    if rec.get("expectation_type") != "MARKET_IMPLIED_EXPECTATION":
        return True
    return rec.get("unit") == "probability" and rec.get("forecast_value") not in (-25, 25, -50, 50)


def event_pit() -> dict[str, str]:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    return {e["macro_event_id"]: e.get("pit_status") for e in events}


def event_meta() -> dict[str, dict]:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    return {e["macro_event_id"]: e for e in events}


def official_map() -> dict[tuple[str, str], dict]:
    pits = event_pit()
    rows = json.loads(VALUES_PATH.read_text(encoding="utf-8"))
    out = {}
    for r in rows:
        rec = dict(r)
        rec["event_pit_status"] = pits.get(r["macro_event_id"])
        out[(r["macro_event_id"], r["series_name"])] = rec
    return out


def frozen_remaining() -> dict:
    blob = json.loads(REMAINING_PATH.read_text(encoding="utf-8"))
    if blob.get("fx_outcomes_used") is not False:
        raise RuntimeError("Remaining universe must not be FX-conditioned.")
    if int(blob.get("remaining_n") or 0) != 20:
        raise RuntimeError("Remaining n must be 20.")
    return blob


def lead_minutes(pub: str | None, t0: str) -> int | None:
    p, t = parse_utc(pub), parse_utc(t0)
    if p is None or t is None:
        return None
    return int((t - p).total_seconds() // 60)


def write_excerpt(name: str, text: str) -> tuple[str, str]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / name
    body = text.strip() + "\n"
    path.write_text(body, encoding="utf-8")
    rel = str(path).replace("\\", "/")
    return rel, sha256_text(body)


EXCERPTS = {
    "reuters_poll_fomc_20251021.txt": """By Indradip Ghosh
October 21, 2025 2:20 PM UTC Updated October 22, 2025
All but two economists, 115 of 117, predicted the Fed would lower the interest rate again by a quarter point to 3.75%-4.00% on October 29. Two expected a 25 bps cut in October and a 50 bps cut in December.
The poll was conducted on October 15-21.
Delayed official data due on October 24 are expected to show consumer inflation rose to 3.1% last month from 2.9% in August.""",
    "reuters_cpi_20251024_instantview.txt": """NEW YORK, Oct 24 (Reuters) - U.S. consumer prices rose slightly less than expected in September
The Consumer Price Index (CPI) rose 0.3% last month
Economists polled by Reuters had forecast the CPI increasing 0.4% and rising 3.1% year-on-year.""",
    "reuters_explainer_20251215.txt": """WASHINGTON, Dec 15 (Reuters) - The U.S. Bureau of Labor Statistics on Tuesday releases its long-awaited combined employment reports for October and November
A Reuters survey of economists forecasts nonfarm payrolls increased by 50,000 jobs in November.
A Reuters survey of economists forecasts the unemployment rate at 4.4% in November.
Goldman Sachs ... estimated the late collection could impose a drag of up to 15 basis points on overall November core CPI.""",
    "reuters_cpi_20260113_wrap.txt": """WASHINGTON, Jan 13 (Reuters) - U.S. consumer prices increased in December
The Consumer Price Index rose 0.3% last month, the Labor Department's Bureau of Labor Statistics said.""",
    "factset_cpi_feb2026.txt": """By John Butters | March 10, 2026
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of February 2026 is 2.5%.
The median estimate of 2.5% is based on 4 estimates collected by FactSet. These CPI estimates range from a low of 2.40% to a high of 2.60%.
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.5%.
Tomorrow (March 11) the U.S. Bureau of Labor Statistics (BLS) will release the CPI and Core CPI numbers for February.""",
    "factset_cpi_mar2026.txt": """By John Butters | April 9, 2026
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of March 2026 is 3.4%.
The median estimate of 3.4% is based on 3 estimates collected by FactSet. These CPI estimates range from a low of 3.30% to a high of 3.90%.
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.7%.
Tomorrow (April 10) the U.S. Bureau of Labor Statistics (BLS) will release the CPI and Core CPI numbers for March.""",
    "reuters_cpi_mar2026.txt": """By Lucia Mutikani
April 10, 2026 4:05 AM UTC Updated April 10, 2026
The CPI likely increased 0.9% last month, a Reuters survey of economists predicted. Estimates ranged from a 0.4% gain to a 1.7% jump.
In the 12 months through March, the CPI was estimated to have advanced 3.3%.
Outside of food and energy, the CPI is forecast to have risen 0.3% last month ... year-on-year increase of 2.7% in the so-called core CPI.""",
    "factset_cpi_apr2026.txt": """By John Butters | May 11, 2026
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of April 2026 is 3.7%.
The median estimate of 3.7% is based on 4 estimates collected by FactSet. These CPI estimates range from a low of 3.68% to a high of 3.70%.
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.7%.
Tomorrow (May 12) the U.S. Bureau of Labor Statistics (BLS) will release the CPI and Core CPI numbers for April.""",
    "reuters_cpi_apr2026.txt": """By Lucia Mutikani
May 12, 2026 4:05 AM UTC Updated May 12, 2026
The CPI likely increased 0.6% last month after jumping 0.9% in March, a Reuters survey of economists predicted. Estimates ranged from a 0.4% gain to a 0.9% rise.
In the 12 months through April, the CPI is projected to have advanced 3.7%.
Excluding food and energy, the CPI is forecast to have risen 0.3% last month
Core CPI inflation is expected to have increased 2.7% year-on-year in April.""",
    "factset_cpi_may2026.txt": """By John Butters | June 9, 2026
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of May 2026 is 4.2%.
The median estimate of 4.2% is based on 3 estimates collected by FactSet. These CPI estimates range from a low of 4.20% to a high of 4.20%.
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.9%.
Tomorrow (June 10) the U.S. Bureau of Labor Statistics (BLS) will release the CPI and Core CPI numbers for May.""",
    "reuters_cpi_may2026.txt": """WASHINGTON, June 10 (Reuters) - U.S. consumer inflation likely increased
The Consumer Price Index likely increased 4.2% in the 12 months through May, a Reuters survey of economists predicted.
It is expected to have increased 0.5% on a monthly basis in May
core CPI was forecast to have increased 2.9% year-on-year in May
The so-called core CPI was projected to have gained 0.3% on a monthly basis.""",
    "factset_nfp_sep2025.txt": """By John Butters | October 2, 2025
The median estimate for total nonfarm payroll employment for the month of September 2025 is 50,000.
The median estimate of 50,000 is based on 19 estimates collected by FactSet. These estimates range from a low of 30,000 to a high of 80,000.
The median estimate for the unemployment rate for the month of September 2025 is 4.3%.""",
    "reuters_nfp_sep2025_preview.txt": """WASHINGTON, Nov 20 (Reuters) - U.S. job growth likely picked up moderately in September
Nonfarm payrolls likely increased by 50,000 jobs in September, a Reuters survey showed
Unemployment rate estimated to have been unchanged at 4.3%""",
    "factset_nfp_dec2025.txt": """By John Butters | January 8, 2026
The median estimate for total nonfarm payroll employment for the month of December 2025 is 55,000.
The median estimate of 55,000 is based on 7 estimates collected by FactSet. These estimates range from a low of 30,000 to a high of 80,000.
The median estimate for the unemployment rate for the month of November 2025 is 4.5%.
Tomorrow (January 9), the U.S. Bureau of Labor Statistics (BLS) will release the total nonfarm payroll employment number and unemployment rate for December.""",
    "factset_nfp_feb2026.txt": """By John Butters | March 5, 2026
The median estimate for total nonfarm payroll employment for the month of February 2026 is 60,000.
The median estimate of 60,000 is based on 13 estimates collected by FactSet. These estimates range from a low of 0 to a high of 85,000.
The median estimate for the unemployment rate for the month of February 2026 is 4.3%.
Tomorrow (March 6), the U.S. Bureau of Labor Statistics (BLS) will release the total nonfarm payroll employment number and unemployment rate for February.""",
    "factset_nfp_mar2026.txt": """By John Butters | April 2, 2026
The median estimate for total nonfarm payroll employment for the month of March 2026 is 60,000.
The median estimate of 60,000 is based on 7 estimates collected by FactSet. These estimates range from a low of 40,000 to a high of 85,000.
The median estimate for the unemployment rate for the month of March 2026 is 4.4%.
Tomorrow (April 3), the U.S. Bureau of Labor Statistics (BLS) will release the total nonfarm payroll employment number and unemployment rate for March.""",
    "factset_nfp_apr2026.txt": """By John Butters | May 7, 2026
The median estimate for total nonfarm payroll employment for the month of April 2026 is 65,000.
The median estimate of 65,000 is based on 13 estimates collected by FactSet. These estimates range from a low of 0 to a high of 95,000.
The median estimate for the unemployment rate for the month of April 2026 is 4.3%.
Tomorrow (May 8), the U.S. Bureau of Labor Statistics (BLS) will release the total nonfarm payroll employment number and unemployment rate for April.""",
    "factset_nfp_may2026.txt": """By John Butters | June 4, 2026
The median estimate for total nonfarm payroll employment for the month of May 2026 is 105,000.
The median estimate of 105,000 is based on 6 estimates collected by FactSet. These estimates range from a low of 50,000 to a high of 125,000.
The median estimate for the unemployment rate for the month of May 2026 is 4.3%.
Tomorrow (June 5), the U.S. Bureau of Labor Statistics (BLS) will release the total nonfarm payroll employment number and unemployment rate for May.""",
    "factset_nfp_jun2026.txt": """By John Butters | July 1, 2026
The median estimate for total nonfarm payroll employment for the month of June 2026 is 100,000.
The median estimate of 100,000 is based on 7 estimates collected by FactSet. These estimates range from a low of 70,000 to a high of 150,000.
The median estimate for the unemployment rate for the month of June 2026 is 4.3%.
Tomorrow (July 2), the U.S. Bureau of Labor Statistics (BLS) will release the total nonfarm payroll employment number and unemployment rate for June.""",
    "reuters_poll_fomc_20251204.txt": """By Sarupya Ganguly
December 4, 2025 1:40 PM UTC Updated December 4, 2025
a markedly large 82% majority, 89 of 108 economists in the November 28-December 4 Reuters poll, predicted a 25-bps reduction.
That strong consensus broadly mirrored a November poll and the near-85% chance of a cut implied by rate futures""",
    "reuters_poll_fomc_20260312.txt": """BENGALURU, March 12 (Reuters) - The U.S. Federal Reserve will cut interest rates for the first time this year in June
all 96 economists in the March 6-12 poll see the Fed holding at 3.50%-3.75% on March 18.
Around two-thirds of economists, 63 of 96, expected the Fed to lower rates to a 3.25%-3.50% range next quarter, most likely in June.""",
    "reuters_poll_fomc_20260423.txt": """By Indradip Ghosh
April 23, 2026 10:37 AM UTC Updated April 23, 2026
The U.S. Federal Reserve will wait at least six months before cutting interest rates this year, according to a Reuters poll of economists
A slim majority of economists, 56 of 103, in the April 17-21 Reuters poll predicted the Fed's benchmark interest rate would remain steady in the 3.50%-3.75% range by the end of September.""",
    "reuters_fomc_20260617_preview.txt": """By Howard Schneider
June 17, 2026 10:03 AM UTC Updated June 17, 2026
The Fed is expected to leave rates unchanged at 3.5% to 3.75% this week
Interest rates are expected to remain on hold in the current 3.50%-to-3.75% range""",
}


def remaining_records(hashes: dict[str, tuple[str, str]], t0: dict[str, str]) -> list[dict]:
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def base(**kw):
        eid = kw["macro_event_id"]
        pub = kw.get("source_publication_utc")
        rec = {
            "retrieved_at_utc": retrieved,
            "official_release_utc": t0[eid],
            "lead_time_minutes": lead_minutes(pub, t0[eid]),
            "source_stage": "historical_reconstruction",
            **kw,
        }
        fn = rec.pop("excerpt_file", None)
        if fn:
            loc, h = hashes[fn]
            rec["artifact_location"] = loc
            rec["raw_artifact_hash"] = h
            rec["artifact_scope"] = "short_verbatim_excerpt_not_full_page"
        rec["source_publication_utc"] = pub
        if rec.get("pit_status") == "PIT_SAFE":
            if not publication_before_t0(pub, t0[eid]):
                raise AssertionError("PIT_SAFE requires publication before T0: " + rec["consensus_evidence_id"])
        if pub and parse_utc(pub) and parse_utc(t0[eid]) and parse_utc(pub) >= parse_utc(t0[eid]):
            if rec["pit_status"] != "REJECT_POST_RELEASE":
                raise AssertionError("post-T0 must be REJECT_POST_RELEASE: " + rec["consensus_evidence_id"])
        return rec

    out = []
    # CPI Oct 24 / Sep 2025
    out.append(base(
        consensus_evidence_id="ce_cpi_20251024_reuters_poll_headline_yoy",
        macro_event_id="usd_cpi_2025-10-24", event_family="CPI", series_name="headline_yoy",
        reference_period="2025-09", forecast_value=3.1, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US Fed to trim rates twice more this year; 2026 rate path very unclear",
        source_reference="https://www.reuters.com/business/us-fed-trim-rates-twice-more-this-year-2026-rate-path-very-unclear-2025-10-21/",
        source_publication_utc="2025-10-21T14:20:00Z", source_updated_date="2025-10-22",
        pit_status="PIT_SAFE",
        notes="Original 14:20Z Oct 21. Untimed Updated Oct 22 is still a calendar day before T0 Oct 24 12:30Z, so same-day-as-T0 Updated limitation does not apply. YoY only; MoM not in this poll article.",
        excerpt_file="reuters_poll_fomc_20251021.txt",
        verbatim_evidence_snippet="Delayed official data due on October 24 are expected to show consumer inflation rose to 3.1% last month from 2.9% in August.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20251024_reuters_instantview_post",
        macro_event_id="usd_cpi_2025-10-24", event_family="CPI", series_name="headline_mom",
        reference_period="2025-09", forecast_value=0.4, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Instant View: US consumer prices increase less than expected in September",
        source_reference="https://www.reuters.com/world/africa/view-us-consumer-prices-increase-less-than-expected-september-2025-10-24/",
        source_publication_utc="2025-10-24T12:30:00Z",
        pit_status="REJECT_POST_RELEASE",
        notes="Post-release Instant View. Quoted survey is not used as a pre-T0 vintage even though the number may match a pre-release poll.",
        excerpt_file="reuters_cpi_20251024_instantview.txt",
        verbatim_evidence_snippet="Economists polled by Reuters had forecast the CPI increasing 0.4% and rising 3.1% year-on-year.",
    ))
    # CPI Dec 18 / Nov 2025 irregular 2m SA
    out.append(base(
        consensus_evidence_id="ce_cpi_20251218_gs_core_drag_individual",
        macro_event_id="usd_cpi_2025-12-18", event_family="CPI", series_name="core_mom",
        reference_period="2025-11", forecast_value=None, unit="percent", seasonal_adjustment="SA",
        expectation_type="INDIVIDUAL_FORECAST", survey_provider="Goldman Sachs", n_forecasters=1,
        source_publisher="Reuters", source_title="Explainer: Delayed US employment, CPI reports are due this week, with many gaps",
        source_reference="https://www.reuters.com/markets/us/delayed-us-employment-cpi-reports-are-due-this-week-with-many-gaps-2025-12-15/",
        source_publication_utc=None, source_publication_date="2025-12-15",
        pit_status="REJECT_WRONG_SERIES",
        notes="Not consensus. Up-to-15bp collection-drag comment, not a headline/core print forecast. Official first print is headline_2m_sa / core_2m_sa, not MoM. Missing is better than forcing a 2-month consensus.",
        excerpt_file="reuters_explainer_20251215.txt",
        verbatim_evidence_snippet="estimated the late collection could impose a drag of up to 15 basis points on overall November core CPI.",
    ))
    # CPI Jan 13 / Dec 2025
    out.append(base(
        consensus_evidence_id="ce_cpi_20260113_reuters_wrap_post",
        macro_event_id="usd_cpi_2026-01-13", event_family="CPI", series_name="headline_mom",
        reference_period="2025-12", forecast_value=None, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation increases steadily, but households paying more for food and rents",
        source_reference="https://www.reuters.com/business/us-consumer-prices-increase-expected-december-2026-01-13/",
        source_publication_utc="2026-01-13T13:30:00Z",
        pit_status="REJECT_POST_RELEASE",
        notes="Past-tense actuals wrap. FactSet December-2025 Insight URL pattern 404 in this session. No lawful pre-release vintage located.",
        excerpt_file="reuters_cpi_20260113_wrap.txt",
        verbatim_evidence_snippet="The Consumer Price Index rose 0.3% last month, the Labor Department's Bureau of Labor Statistics said.",
    ))
    # CPI Mar 11 / Feb 2026 FactSet
    out.append(base(
        consensus_evidence_id="ce_cpi_20260311_factset_headline_yoy",
        macro_event_id="usd_cpi_2026-03-11", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-02", forecast_value=2.5, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=4,
        source_publisher="FactSet Insight", source_title="CPI for February 2026 is Projected to Rise 2.5% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-february-2026-is-projected-to-rise-2.5-year-over-year",
        source_publication_utc=None, source_publication_date="2026-03-10",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Byline Mar 10 plus Tomorrow (March 11). No UTC clock. n=4, range 2.40-2.60. Archiving today does not prove pre-T0 content vintage.",
        excerpt_file="factset_cpi_feb2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of February 2026 is 2.5%.",
        forecast_range={"min": 2.4, "max": 2.6},
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260311_factset_core_yoy",
        macro_event_id="usd_cpi_2026-03-11", event_family="CPI", series_name="core_yoy",
        reference_period="2026-02", forecast_value=2.5, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=4,
        source_publisher="FactSet Insight", source_title="CPI for February 2026 is Projected to Rise 2.5% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-february-2026-is-projected-to-rise-2.5-year-over-year",
        source_publication_utc=None, source_publication_date="2026-03-10",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same FactSet page. No MoM on this page.",
        excerpt_file="factset_cpi_feb2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.5%.",
    ))
    # CPI Apr 10 / Mar 2026
    out.append(base(
        consensus_evidence_id="ce_cpi_20260410_factset_headline_yoy",
        macro_event_id="usd_cpi_2026-04-10", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-03", forecast_value=3.4, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=3,
        source_publisher="FactSet Insight", source_title="CPI for March 2026 is Projected to Rise 3.4% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-march-2026-is-projected-to-rise-3.4-year-over-year",
        source_publication_utc=None, source_publication_date="2026-04-09",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Date + Tomorrow (April 10). n=3. Disagrees with Reuters YoY 3.3. Not averaged.",
        excerpt_file="factset_cpi_mar2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of March 2026 is 3.4%.",
        forecast_range={"min": 3.3, "max": 3.9},
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260410_factset_core_yoy",
        macro_event_id="usd_cpi_2026-04-10", event_family="CPI", series_name="core_yoy",
        reference_period="2026-03", forecast_value=2.7, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=3,
        source_publisher="FactSet Insight", source_title="CPI for March 2026 is Projected to Rise 3.4% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-march-2026-is-projected-to-rise-3.4-year-over-year",
        source_publication_utc=None, source_publication_date="2026-04-09",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same FactSet page.",
        excerpt_file="factset_cpi_mar2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.7%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260410_reuters_headline_mom",
        macro_event_id="usd_cpi_2026-04-10", event_family="CPI", series_name="headline_mom",
        reference_period="2026-03", forecast_value=0.9, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation expected to have surged in March amid Iran war",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-expected-have-surged-march-amid-iran-war-2026-04-10/",
        source_publication_utc="2026-04-10T04:05:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="04:05Z < T0 12:30Z. Same-day Updated without last-mod. Range 0.4 to 1.7 preserved.",
        excerpt_file="reuters_cpi_mar2026.txt",
        verbatim_evidence_snippet="The CPI likely increased 0.9% last month, a Reuters survey of economists predicted.",
        forecast_range={"min": 0.4, "max": 1.7},
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260410_reuters_headline_yoy",
        macro_event_id="usd_cpi_2026-04-10", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-03", forecast_value=3.3, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation expected to have surged in March amid Iran war",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-expected-have-surged-march-amid-iran-war-2026-04-10/",
        source_publication_utc="2026-04-10T04:05:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Reuters 3.3 vs FactSet 3.4. Not averaged.",
        excerpt_file="reuters_cpi_mar2026.txt",
        verbatim_evidence_snippet="In the 12 months through March, the CPI was estimated to have advanced 3.3%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260410_reuters_core_mom",
        macro_event_id="usd_cpi_2026-04-10", event_family="CPI", series_name="core_mom",
        reference_period="2026-03", forecast_value=0.3, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation expected to have surged in March amid Iran war",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-expected-have-surged-march-amid-iran-war-2026-04-10/",
        source_publication_utc="2026-04-10T04:05:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same-day Updated limitation.",
        excerpt_file="reuters_cpi_mar2026.txt",
        verbatim_evidence_snippet="Outside of food and energy, the CPI is forecast to have risen 0.3% last month after climbing 0.2% in February.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260410_reuters_core_yoy",
        macro_event_id="usd_cpi_2026-04-10", event_family="CPI", series_name="core_yoy",
        reference_period="2026-03", forecast_value=2.7, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation expected to have surged in March amid Iran war",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-expected-have-surged-march-amid-iran-war-2026-04-10/",
        source_publication_utc="2026-04-10T04:05:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Agrees with FactSet core YoY 2.7; still stored separately.",
        excerpt_file="reuters_cpi_mar2026.txt",
        verbatim_evidence_snippet="That would translate to a year-on-year increase of 2.7% in the so-called core CPI.",
    ))
    return out + remaining_records_part2(hashes, t0, retrieved)


def remaining_records_part2(hashes, t0, retrieved):
    def base(**kw):
        eid = kw["macro_event_id"]
        pub = kw.get("source_publication_utc")
        rec = {
            "retrieved_at_utc": retrieved,
            "official_release_utc": t0[eid],
            "lead_time_minutes": lead_minutes(pub, t0[eid]),
            "source_stage": "historical_reconstruction",
            **kw,
        }
        fn = rec.pop("excerpt_file", None)
        if fn:
            loc, h = hashes[fn]
            rec["artifact_location"] = loc
            rec["raw_artifact_hash"] = h
            rec["artifact_scope"] = "short_verbatim_excerpt_not_full_page"
        rec["source_publication_utc"] = pub
        if rec.get("pit_status") == "PIT_SAFE":
            if not publication_before_t0(pub, t0[eid]):
                raise AssertionError("PIT_SAFE requires publication before T0: " + rec["consensus_evidence_id"])
        if pub and parse_utc(pub) and parse_utc(t0[eid]) and parse_utc(pub) >= parse_utc(t0[eid]):
            if rec["pit_status"] != "REJECT_POST_RELEASE":
                raise AssertionError("post-T0 must be REJECT_POST_RELEASE: " + rec["consensus_evidence_id"])
        return rec

    out = []
    out.append(base(
        consensus_evidence_id="ce_cpi_20260512_factset_headline_yoy",
        macro_event_id="usd_cpi_2026-05-12", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-04", forecast_value=3.7, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=4,
        source_publisher="FactSet Insight", source_title="CPI for April 2026 is Projected to Rise 3.7% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-april-2026-is-projected-to-rise-3.7-year-over-year",
        source_publication_utc=None, source_publication_date="2026-05-11",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Date + Tomorrow (May 12). n=4, range 3.68-3.70.",
        excerpt_file="factset_cpi_apr2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of April 2026 is 3.7%.",
        forecast_range={"min": 3.68, "max": 3.7},
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260512_factset_core_yoy",
        macro_event_id="usd_cpi_2026-05-12", event_family="CPI", series_name="core_yoy",
        reference_period="2026-04", forecast_value=2.7, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=4,
        source_publisher="FactSet Insight", source_title="CPI for April 2026 is Projected to Rise 3.7% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-april-2026-is-projected-to-rise-3.7-year-over-year",
        source_publication_utc=None, source_publication_date="2026-05-11",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same FactSet page.",
        excerpt_file="factset_cpi_apr2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.7%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260512_reuters_headline_mom",
        macro_event_id="usd_cpi_2026-05-12", event_family="CPI", series_name="headline_mom",
        reference_period="2026-04", forecast_value=0.6, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation expected to have increased further in April amid Iran war",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-expected-have-increased-further-april-amid-iran-war-2026-05-12/",
        source_publication_utc="2026-05-12T04:05:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="04:05Z < T0 12:30Z. Same-day Updated. Range 0.4 to 0.9.",
        excerpt_file="reuters_cpi_apr2026.txt",
        verbatim_evidence_snippet="The CPI likely increased 0.6% last month after jumping 0.9% in March, a Reuters survey of economists predicted.",
        forecast_range={"min": 0.4, "max": 0.9},
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260512_reuters_headline_yoy",
        macro_event_id="usd_cpi_2026-05-12", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-04", forecast_value=3.7, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation expected to have increased further in April amid Iran war",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-expected-have-increased-further-april-amid-iran-war-2026-05-12/",
        source_publication_utc="2026-05-12T04:05:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Agrees with FactSet 3.7; stored separately.",
        excerpt_file="reuters_cpi_apr2026.txt",
        verbatim_evidence_snippet="In the 12 months through April, the CPI is projected to have advanced 3.7%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260512_reuters_core_mom",
        macro_event_id="usd_cpi_2026-05-12", event_family="CPI", series_name="core_mom",
        reference_period="2026-04", forecast_value=0.3, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation expected to have increased further in April amid Iran war",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-expected-have-increased-further-april-amid-iran-war-2026-05-12/",
        source_publication_utc="2026-05-12T04:05:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Article also says greater chance of rounding up to 0.4; 0.3 stored as stated forecast, not a house blend.",
        excerpt_file="reuters_cpi_apr2026.txt",
        verbatim_evidence_snippet="Excluding food and energy, the CPI is forecast to have risen 0.3% last month, with a greater chance of rounding up to 0.4%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260512_reuters_core_yoy",
        macro_event_id="usd_cpi_2026-05-12", event_family="CPI", series_name="core_yoy",
        reference_period="2026-04", forecast_value=2.7, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation expected to have increased further in April amid Iran war",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-expected-have-increased-further-april-amid-iran-war-2026-05-12/",
        source_publication_utc="2026-05-12T04:05:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same-day Updated limitation.",
        excerpt_file="reuters_cpi_apr2026.txt",
        verbatim_evidence_snippet="Core CPI inflation is expected to have increased 2.7% year-on-year in April after rising 2.6% in March.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260610_factset_headline_yoy",
        macro_event_id="usd_cpi_2026-06-10", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-05", forecast_value=4.2, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=3,
        source_publisher="FactSet Insight", source_title="CPI for May 2026 is Projected to Rise 4.2% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-may-2026-is-projected-to-rise-4.2-year-over-year",
        source_publication_utc=None, source_publication_date="2026-06-09",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Date + Tomorrow (June 10). n=3, range 4.20-4.20.",
        excerpt_file="factset_cpi_may2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of May 2026 is 4.2%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260610_factset_core_yoy",
        macro_event_id="usd_cpi_2026-06-10", event_family="CPI", series_name="core_yoy",
        reference_period="2026-05", forecast_value=2.9, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=3,
        source_publisher="FactSet Insight", source_title="CPI for May 2026 is Projected to Rise 4.2% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-may-2026-is-projected-to-rise-4.2-year-over-year",
        source_publication_utc=None, source_publication_date="2026-06-09",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same FactSet page.",
        excerpt_file="factset_cpi_may2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.9%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260610_reuters_headline_yoy",
        macro_event_id="usd_cpi_2026-06-10", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-05", forecast_value=4.2, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Higher gasoline prices likely pushed up US consumer inflation again in May",
        source_reference="https://www.reuters.com/legal/transactional/higher-gasoline-prices-likely-pushed-up-us-consumer-inflation-again-may-2026-06-10/",
        source_publication_utc=None, source_publication_date="2026-06-10",
        pit_status="UNCERTAIN",
        notes="T0-day dateline without observed UTC clock. Preview tense, but publication could theoretically be after 12:30Z. Not promoted. FactSet day-before remains SILVER.",
        excerpt_file="reuters_cpi_may2026.txt",
        verbatim_evidence_snippet="The Consumer Price Index likely increased 4.2% in the 12 months through May, a Reuters survey of economists predicted.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260610_reuters_headline_mom",
        macro_event_id="usd_cpi_2026-06-10", event_family="CPI", series_name="headline_mom",
        reference_period="2026-05", forecast_value=0.5, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Higher gasoline prices likely pushed up US consumer inflation again in May",
        source_reference="https://www.reuters.com/legal/transactional/higher-gasoline-prices-likely-pushed-up-us-consumer-inflation-again-may-2026-06-10/",
        source_publication_utc=None, source_publication_date="2026-06-10",
        pit_status="UNCERTAIN",
        notes="Same T0-day unclocked Reuters preview.",
        excerpt_file="reuters_cpi_may2026.txt",
        verbatim_evidence_snippet="It is expected to have increased 0.5% on a monthly basis in May after advancing 0.6% in April.",
    ))
    return out + remaining_records_part3(hashes, t0, retrieved)


def remaining_records_part3(hashes, t0, retrieved):
    def base(**kw):
        eid = kw["macro_event_id"]
        pub = kw.get("source_publication_utc")
        rec = {
            "retrieved_at_utc": retrieved,
            "official_release_utc": t0[eid],
            "lead_time_minutes": lead_minutes(pub, t0[eid]),
            "source_stage": "historical_reconstruction",
            **kw,
        }
        fn = rec.pop("excerpt_file", None)
        if fn:
            loc, h = hashes[fn]
            rec["artifact_location"] = loc
            rec["raw_artifact_hash"] = h
            rec["artifact_scope"] = "short_verbatim_excerpt_not_full_page"
        rec["source_publication_utc"] = pub
        if rec.get("pit_status") == "PIT_SAFE":
            if not publication_before_t0(pub, t0[eid]):
                raise AssertionError("PIT_SAFE requires publication before T0: " + rec["consensus_evidence_id"])
        if pub and parse_utc(pub) and parse_utc(t0[eid]) and parse_utc(pub) >= parse_utc(t0[eid]):
            if rec["pit_status"] != "REJECT_POST_RELEASE":
                raise AssertionError("post-T0 must be REJECT_POST_RELEASE: " + rec["consensus_evidence_id"])
        return rec

    out = []
    out.append(base(
        consensus_evidence_id="ce_empsit_20251120_factset_nfp",
        macro_event_id="usd_empsit_2025-11-20", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2025-09", forecast_value=50000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=19,
        source_publisher="FactSet Insight", source_title="Total Nonfarm Payrolls For September 2025 Are Projected To Rise By 50,000",
        source_reference="https://insight.factset.com/total-nonfarm-payrolls-for-september-2025-are-projected-to-rise-by-50000",
        source_publication_utc=None, source_publication_date="2025-10-02",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Early vintage: byline Oct 2 for originally scheduled early-October release; actual T0 delayed to Nov 20. No Tomorrow (November 20) line. T0-49d, not proven final pre-release. Range 30k-80k.",
        excerpt_file="factset_nfp_sep2025.txt",
        verbatim_evidence_snippet="The median estimate for total nonfarm payroll employment for the month of September 2025 is 50,000.",
        forecast_range={"min": 30000, "max": 80000},
        vintage_label="T0-49d_pre_delay",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20251120_factset_urate",
        macro_event_id="usd_empsit_2025-11-20", event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
        reference_period="2025-09", forecast_value=4.3, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=19,
        source_publisher="FactSet Insight", source_title="Total Nonfarm Payrolls For September 2025 Are Projected To Rise By 50,000",
        source_reference="https://insight.factset.com/total-nonfarm-payrolls-for-september-2025-are-projected-to-rise-by-50000",
        source_publication_utc=None, source_publication_date="2025-10-02",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same delayed-event early vintage.",
        excerpt_file="factset_nfp_sep2025.txt",
        verbatim_evidence_snippet="The median estimate for the unemployment rate for the month of September 2025 is 4.3%.",
        vintage_label="T0-49d_pre_delay",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20251120_reuters_nfp",
        macro_event_id="usd_empsit_2025-11-20", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2025-09", forecast_value=50000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US economy likely added jobs at a moderate pace in September",
        source_reference="https://www.reuters.com/world/us/us-economy-likely-added-jobs-moderate-pace-september-2025-11-20/",
        source_publication_utc=None, source_publication_date="2025-11-20",
        pit_status="UNCERTAIN",
        notes="T0-day dateline, preview tense, no UTC clock observed. Could theoretically be post-13:30Z. Not promoted.",
        excerpt_file="reuters_nfp_sep2025_preview.txt",
        verbatim_evidence_snippet="Nonfarm payrolls likely increased by 50,000 jobs in September, a Reuters survey showed",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20251120_reuters_urate",
        macro_event_id="usd_empsit_2025-11-20", event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
        reference_period="2025-09", forecast_value=4.3, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US economy likely added jobs at a moderate pace in September",
        source_reference="https://www.reuters.com/world/us/us-economy-likely-added-jobs-moderate-pace-september-2025-11-20/",
        source_publication_utc=None, source_publication_date="2025-11-20",
        pit_status="UNCERTAIN",
        notes="Same unclocked T0-day preview.",
        excerpt_file="reuters_nfp_sep2025_preview.txt",
        verbatim_evidence_snippet="Unemployment rate estimated to have been unchanged at 4.3%",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20251216_reuters_nfp",
        macro_event_id="usd_empsit_2025-12-16", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2025-11", forecast_value=50000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Explainer: Delayed US employment, CPI reports are due this week, with many gaps",
        source_reference="https://www.reuters.com/markets/us/delayed-us-employment-cpi-reports-are-due-this-week-with-many-gaps-2025-12-15/",
        source_publication_utc=None, source_publication_date="2025-12-15",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Dateline Dec 15, Tuesday employment release is Dec 16 T0. Date-only, no UTC clock.",
        excerpt_file="reuters_explainer_20251215.txt",
        verbatim_evidence_snippet="A Reuters survey of economists forecasts nonfarm payrolls increased by 50,000 jobs in November.",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20251216_reuters_urate",
        macro_event_id="usd_empsit_2025-12-16", event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
        reference_period="2025-11", forecast_value=4.4, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Explainer: Delayed US employment, CPI reports are due this week, with many gaps",
        source_reference="https://www.reuters.com/markets/us/delayed-us-employment-cpi-reports-are-due-this-week-with-many-gaps-2025-12-15/",
        source_publication_utc=None, source_publication_date="2025-12-15",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same Dec 15 explainer.",
        excerpt_file="reuters_explainer_20251215.txt",
        verbatim_evidence_snippet="A Reuters survey of economists forecasts the unemployment rate at 4.4% in November.",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260109_factset_nfp",
        macro_event_id="usd_empsit_2026-01-09", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2025-12", forecast_value=55000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=7,
        source_publisher="FactSet Insight", source_title="Total Nonfarm Payrolls for December 2025 Are Projected to Rise By 55,000",
        source_reference="https://insight.factset.com/total-nonfarm-payrolls-for-december-2025-are-projected-to-rise-by-55000",
        source_publication_utc=None, source_publication_date="2026-01-08",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Tomorrow (January 9). n=7, range 30k-80k.",
        excerpt_file="factset_nfp_dec2025.txt",
        verbatim_evidence_snippet="The median estimate for total nonfarm payroll employment for the month of December 2025 is 55,000.",
        forecast_range={"min": 30000, "max": 80000},
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260109_factset_urate_wrong_period",
        macro_event_id="usd_empsit_2026-01-09", event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
        reference_period="2025-11", forecast_value=4.5, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=11,
        source_publisher="FactSet Insight", source_title="Total Nonfarm Payrolls for December 2025 Are Projected to Rise By 55,000",
        source_reference="https://insight.factset.com/total-nonfarm-payrolls-for-december-2025-are-projected-to-rise-by-55000",
        source_publication_utc=None, source_publication_date="2026-01-08",
        pit_status="REJECT_WRONG_SERIES",
        notes="Page says unemployment rate for November 2025 while the release is December payrolls. Do not join to official December u-rate.",
        excerpt_file="factset_nfp_dec2025.txt",
        verbatim_evidence_snippet="The median estimate for the unemployment rate for the month of November 2025 is 4.5%.",
    ))
    for eid, period, date, fn, nfp, n_nfp, lo, hi, ur, n_ur, url, title in [
        ("usd_empsit_2026-03-06", "2026-02", "2026-03-05", "factset_nfp_feb2026.txt", 60000, 13, 0, 85000, 4.3, 12,
         "https://insight.factset.com/total-nonfarm-payrolls-for-february-2026-are-projected-to-rise-by-60000",
         "Total Nonfarm Payrolls For February 2026 Are Projected To Rise By 60,000"),
        ("usd_empsit_2026-04-03", "2026-03", "2026-04-02", "factset_nfp_mar2026.txt", 60000, 7, 40000, 85000, 4.4, 8,
         "https://insight.factset.com/total-nonfarm-payrolls-for-march-2026-are-projected-to-rise-by-60000",
         "Total Nonfarm Payrolls for March 2026 Are Projected to Rise By 60,000"),
        ("usd_empsit_2026-05-08", "2026-04", "2026-05-07", "factset_nfp_apr2026.txt", 65000, 13, 0, 95000, 4.3, 13,
         "https://insight.factset.com/total-nonfarm-payrolls-for-april-2026-are-projected-to-rise-by-65000",
         "Total Nonfarm Payrolls for April 2026 Are Projected to Rise By 65,000"),
        ("usd_empsit_2026-06-05", "2026-05", "2026-06-04", "factset_nfp_may2026.txt", 105000, 6, 50000, 125000, 4.3, 6,
         "https://insight.factset.com/total-nonfarm-payrolls-for-may-2026-are-projected-to-rise-by-105000",
         "Total Nonfarm Payrolls for May 2026 Are Projected to Rise By 105,000"),
        ("usd_empsit_2026-07-02", "2026-06", "2026-07-01", "factset_nfp_jun2026.txt", 100000, 7, 70000, 150000, 4.3, 7,
         "https://insight.factset.com/total-nonfarm-payrolls-for-june-2026-are-projected-to-rise-by-100000",
         "Total Nonfarm Payrolls for June 2026 Are Projected to Rise By 100,000"),
    ]:
        out.append(base(
            consensus_evidence_id="ce_%s_factset_nfp" % eid.replace("usd_", "").replace("-", ""),
            macro_event_id=eid, event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
            reference_period=period, forecast_value=nfp, unit="persons", seasonal_adjustment="SA",
            expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=n_nfp,
            source_publisher="FactSet Insight", source_title=title, source_reference=url,
            source_publication_utc=None, source_publication_date=date,
            pit_status="PIT_SAFE_WITH_LIMITATION",
            notes="FactSet date + Tomorrow. No UTC clock. n=%s range %s-%s." % (n_nfp, lo, hi),
            excerpt_file=fn,
            verbatim_evidence_snippet="The median estimate for total nonfarm payroll employment for the month of %s is %s." % (
                {"2026-02": "February 2026", "2026-03": "March 2026", "2026-04": "April 2026", "2026-05": "May 2026", "2026-06": "June 2026"}[period],
                f"{nfp:,}",
            ),
            forecast_range={"min": lo, "max": hi},
        ))
        out.append(base(
            consensus_evidence_id="ce_%s_factset_urate" % eid.replace("usd_", "").replace("-", ""),
            macro_event_id=eid, event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
            reference_period=period, forecast_value=ur, unit="percent", seasonal_adjustment="SA",
            expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=n_ur,
            source_publisher="FactSet Insight", source_title=title, source_reference=url,
            source_publication_utc=None, source_publication_date=date,
            pit_status="PIT_SAFE_WITH_LIMITATION",
            notes="Same FactSet page. n=%s." % n_ur,
            excerpt_file=fn,
            verbatim_evidence_snippet="The median estimate for the unemployment rate for the month of %s is %s%%." % (
                {"2026-02": "February 2026", "2026-03": "March 2026", "2026-04": "April 2026", "2026-05": "May 2026", "2026-06": "June 2026"}[period],
                ur,
            ),
        ))
    return out + remaining_records_fomc(hashes, t0, retrieved)


def remaining_records_fomc(hashes, t0, retrieved):
    def base(**kw):
        eid = kw["macro_event_id"]
        pub = kw.get("source_publication_utc")
        rec = {
            "retrieved_at_utc": retrieved,
            "official_release_utc": t0[eid],
            "lead_time_minutes": lead_minutes(pub, t0[eid]),
            "source_stage": "historical_reconstruction",
            **kw,
        }
        fn = rec.pop("excerpt_file", None)
        if fn:
            loc, h = hashes[fn]
            rec["artifact_location"] = loc
            rec["raw_artifact_hash"] = h
            rec["artifact_scope"] = "short_verbatim_excerpt_not_full_page"
        rec["source_publication_utc"] = pub
        if rec.get("pit_status") == "PIT_SAFE":
            if not publication_before_t0(pub, t0[eid]):
                raise AssertionError("PIT_SAFE requires publication before T0: " + rec["consensus_evidence_id"])
        if pub and parse_utc(pub) and parse_utc(t0[eid]) and parse_utc(pub) >= parse_utc(t0[eid]):
            if rec["pit_status"] != "REJECT_POST_RELEASE":
                raise AssertionError("post-T0 must be REJECT_POST_RELEASE: " + rec["consensus_evidence_id"])
        return rec

    out = []
    out.append(base(
        consensus_evidence_id="ce_fomc_20251029_reuters_poll_decision",
        macro_event_id="usd_fomc_statement_2025-10-29", event_family="FOMC", series_name="expected_policy_decision",
        reference_period="2025-10-28/29", forecast_value="cut_25bp", unit="categorical", seasonal_adjustment=None,
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=117,
        source_publisher="Reuters", source_title="US Fed to trim rates twice more this year; 2026 rate path very unclear",
        source_reference="https://www.reuters.com/business/us-fed-trim-rates-twice-more-this-year-2026-rate-path-very-unclear-2025-10-21/",
        source_publication_utc="2025-10-21T14:20:00Z", source_updated_date="2025-10-22",
        pit_status="PIT_SAFE",
        notes="115/117 expect -25bp on Oct 29; 2 expect -25 Oct and -50 Dec. Distribution retained. Not collapsed to scalar -25 as the only stored object. Updated Oct 22 still before T0 Oct 29 18:00Z.",
        excerpt_file="reuters_poll_fomc_20251021.txt",
        verbatim_evidence_snippet="All but two economists, 115 of 117, predicted the Fed would lower the interest rate again by a quarter point to 3.75%-4.00% on October 29.",
        distribution={"cut_25bp": 115, "cut_25bp_oct_and_50bp_dec": 2, "n": 117},
        expected_change_bp=-25,
    ))
    out.append(base(
        consensus_evidence_id="ce_fomc_20251210_reuters_poll_decision",
        macro_event_id="usd_fomc_statement_2025-12-10", event_family="FOMC", series_name="expected_policy_decision",
        reference_period="2025-12-09/10", forecast_value="cut_25bp", unit="categorical", seasonal_adjustment=None,
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=108,
        source_publisher="Reuters", source_title="Economists double down on December Fed cut despite policymaker divide: Reuters poll",
        source_reference="https://www.reuters.com/business/economists-double-down-december-fed-cut-despite-policymaker-divide-2025-12-04/",
        source_publication_utc="2025-12-04T13:40:00Z", source_updated_date="2025-12-04",
        pit_status="PIT_SAFE",
        notes="89 of 108 (82%) 25bp cut. Updated Dec 4 calendar day before T0 Dec 10 19:00Z.",
        excerpt_file="reuters_poll_fomc_20251204.txt",
        verbatim_evidence_snippet="89 of 108 economists in the November 28-December 4 Reuters poll, predicted a 25-bps reduction.",
        distribution={"cut_25bp": 89, "n": 108},
        expected_change_bp=-25,
    ))
    out.append(base(
        consensus_evidence_id="ce_fomc_20251210_reuters_ff_cut_prob",
        macro_event_id="usd_fomc_statement_2025-12-10", event_family="FOMC", series_name="market_implied_cut_probability",
        reference_period="2025-12-09/10", forecast_value=0.85, unit="probability", seasonal_adjustment=None,
        expectation_type="MARKET_IMPLIED_EXPECTATION", survey_provider="rate futures via Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Economists double down on December Fed cut despite policymaker divide: Reuters poll",
        source_reference="https://www.reuters.com/business/economists-double-down-december-fed-cut-despite-policymaker-divide-2025-12-04/",
        source_publication_utc="2025-12-04T13:40:00Z",
        pit_status="PIT_SAFE",
        notes="near-85% chance of a cut implied by rate futures. Stored as probability, not consensus=-25bp. Separate from 89/108 survey.",
        excerpt_file="reuters_poll_fomc_20251204.txt",
        verbatim_evidence_snippet="the near-85% chance of a cut implied by rate futures",
    ))
    out.append(base(
        consensus_evidence_id="ce_fomc_20260318_reuters_poll_hold",
        macro_event_id="usd_fomc_statement_2026-03-18", event_family="FOMC", series_name="expected_policy_decision",
        reference_period="2026-03-17/18", forecast_value="hold", unit="categorical", seasonal_adjustment=None,
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=96,
        source_publisher="Reuters", source_title="Fed to cut rates in June, economists still say, despite war inflation risks: Reuters poll",
        source_reference="https://www.reuters.com/business/fed-cut-rates-june-economists-still-say-despite-war-inflation-risks-2026-03-12/",
        source_publication_utc=None, source_publication_date="2026-03-12",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Poll window Mar 6-12; dateline Mar 12 is before T0 Mar 18 18:00Z but no UTC clock observed on the fetched page. 96/96 hold. Not promoted to PIT_SAFE.",
        excerpt_file="reuters_poll_fomc_20260312.txt",
        verbatim_evidence_snippet="all 96 economists in the March 6-12 poll see the Fed holding at 3.50%-3.75% on March 18.",
        distribution={"hold": 96, "n": 96},
        expected_change_bp=0,
    ))
    out.append(base(
        consensus_evidence_id="ce_fomc_20260429_reuters_poll_path_hold",
        macro_event_id="usd_fomc_statement_2026-04-29", event_family="FOMC", series_name="expected_policy_decision",
        reference_period="2026-04-28/29", forecast_value="hold", unit="categorical", seasonal_adjustment=None,
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=103,
        source_publisher="Reuters", source_title="Fed rate cut pushed back to late 2026 on war-related inflation risks: Reuters poll",
        source_reference="https://www.reuters.com/world/middle-east/fed-rate-cut-pushed-back-late-2026-war-related-inflation-risks-2026-04-22/",
        source_publication_utc="2026-04-23T10:37:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Clock 10:37Z Apr 23 < T0 Apr 29 18:00Z. Limitation: poll question is end-September range / wait-six-months, not a counted April 29 vote. Not promoted to GOLD.",
        excerpt_file="reuters_poll_fomc_20260423.txt",
        verbatim_evidence_snippet="The U.S. Federal Reserve will wait at least six months before cutting interest rates this year, according to a Reuters poll of economists",
        expected_change_bp=0,
    ))
    out.append(base(
        consensus_evidence_id="ce_fomc_20260617_reuters_march_vintage_cut",
        macro_event_id="usd_fomc_statement_2026-06-17", event_family="FOMC", series_name="expected_policy_decision",
        reference_period="2026-06-16/17", forecast_value="cut_25bp", unit="categorical", seasonal_adjustment=None,
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=96,
        source_publisher="Reuters", source_title="Fed to cut rates in June, economists still say, despite war inflation risks: Reuters poll",
        source_reference="https://www.reuters.com/business/fed-cut-rates-june-economists-still-say-despite-war-inflation-risks-2026-03-12/",
        source_publication_utc=None, source_publication_date="2026-03-12",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="T0-97d vintage. 63 of 96 expected a June cut as of Mar 12. Preserved as evolution, not overwritten by the June 17 hold preview.",
        excerpt_file="reuters_poll_fomc_20260312.txt",
        verbatim_evidence_snippet="63 of 96, expected the Fed to lower rates to a 3.25%-3.50% range next quarter, most likely in June.",
        distribution={"cut_by_end_of_next_quarter_most_likely_june": 63, "n": 96},
        expected_change_bp=-25,
        vintage_label="T0-97d",
    ))
    out.append(base(
        consensus_evidence_id="ce_fomc_20260617_reuters_hold_preview",
        macro_event_id="usd_fomc_statement_2026-06-17", event_family="FOMC", series_name="expected_policy_decision",
        reference_period="2026-06-16/17", forecast_value="hold", unit="categorical", seasonal_adjustment=None,
        expectation_type="PROVIDER_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="As oil roundtrips, AI booms, and US consumers spend, economists' Fed outlooks hit the extremes",
        source_reference="https://www.reuters.com/business/oil-roundtrips-ai-booms-us-consumers-spend-economists-fed-outlooks-hit-extremes-2026-06-17/",
        source_publication_utc="2026-06-17T10:03:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="10:03Z < T0 18:00Z. Same-day Updated. Uncounted 'expected to leave rates unchanged', not a 96-economist poll. Not relabeled SURVEY_CONSENSUS. Not averaged with March 63/96 cut vintage.",
        excerpt_file="reuters_fomc_20260617_preview.txt",
        verbatim_evidence_snippet="The Fed is expected to leave rates unchanged at 3.5% to 3.75% this week",
        expected_change_bp=0,
        vintage_label="T0-8h",
    ))
    return out


def compute_surprise(records: list[dict]) -> list[dict]:
    off = official_map()
    events = event_meta()
    out = []
    for rec in records:
        if rec.get("pit_status") != "PIT_SAFE":
            continue
        key = (rec["macro_event_id"], rec["series_name"])
        official = off.get(key)
        event = events.get(rec["macro_event_id"], {})
        row = {
            "consensus_evidence_id": rec["consensus_evidence_id"],
            "macro_event_id": rec["macro_event_id"],
            "series_name": rec["series_name"],
            "expectation_type": rec["expectation_type"],
            "forecast_value": rec.get("forecast_value"),
            "official_join_valid": False,
            "raw_surprise_possible": False,
            "surprise_raw": None,
            "notes": "",
            "tier": "GOLD",
        }
        if rec["series_name"] in {
            "expected_policy_decision",
            "market_implied_cut_probability",
            "market_implied_hike_probability",
        }:
            actual_chg = off.get((rec["macro_event_id"], "ff_target_change_bp"), {}).get("actual_first_print")
            row["official_join_valid"] = actual_chg is not None
            row["official_actual"] = actual_chg
            if rec["series_name"] == "expected_policy_decision" and rec.get("expected_change_bp") is not None and actual_chg is not None:
                row["raw_surprise_possible"] = True
                row["surprise_raw"] = float(actual_chg) - float(rec["expected_change_bp"])
                row["notes"] = "Categorical survey mapped only via stored expected_change_bp. Probability distribution not collapsed."
            elif str(rec["series_name"]).startswith("market_implied"):
                row["notes"] = "Market-implied probability retained. Not converted to a scalar consensus rate change. No surprise_raw."
            out.append(row)
            continue
        if official is None:
            row["notes"] = "No matching official series on us_pit values."
            out.append(row)
            continue
        if not exact_series_match(rec, official):
            row["notes"] = "Series mismatch."
            out.append(row)
            continue
        if not reference_period_match(rec, event):
            row["notes"] = "Reference-period mismatch."
            out.append(row)
            continue
        if rec.get("seasonal_adjustment") and official.get("seasonal_adjustment") and not seasonal_match(rec, official):
            row["notes"] = "Seasonal-adjustment mismatch."
            out.append(row)
            continue
        if official.get("event_pit_status") not in PIT_OK_JOIN:
            row["notes"] = "Official event not PIT-safe."
            out.append(row)
            continue
        actual = official.get("actual_first_print")
        if actual is None:
            row["notes"] = "Official first print missing."
            out.append(row)
            continue
        if not units_match(rec, official):
            row["notes"] = "Unit mismatch."
            out.append(row)
            continue
        row["official_join_valid"] = True
        row["official_actual"] = actual
        if rec["expectation_type"] == "INDIVIDUAL_FORECAST":
            row["notes"] = "Joinable but individual forecast is not consensus; surprise not computed."
            out.append(row)
            continue
        if rec["expectation_type"] not in CONSENSUS_TYPES and rec["series_name"] in SCALAR_SERIES:
            row["notes"] = "Expectation type is not a consensus type."
            out.append(row)
            continue
        if rec["series_name"] not in SCALAR_SERIES:
            row["notes"] = "Non-scalar series excluded from strict surprise."
            out.append(row)
            continue
        row["raw_surprise_possible"] = True
        row["surprise_raw"] = float(actual) - float(rec["forecast_value"])
        row["notes"] = "GOLD/PIT_SAFE only. Dataset validation. No z-score. No FX join."
        out.append(row)
    return out


def never_average_providers(records: list[dict], event_id: str, series: str) -> list:
    vals = []
    for r in records:
        if r["macro_event_id"] == event_id and r["series_name"] == series and r.get("expectation_type") != "INDIVIDUAL_FORECAST":
            if r.get("forecast_value") is not None:
                vals.append((r["source_publisher"], r["forecast_value"]))
    return vals


def write_report(combined: list[dict], remaining: list[dict], surprise: list[dict], rem_blob: dict) -> None:
    eligible = 29
    pilot_n = 9
    remaining_n = 20
    all_ids = sorted({r["macro_event_id"] for r in combined})
    rem_ids = [e["macro_event_id"] for e in rem_blob["remaining"]]
    any_ev = {r["macro_event_id"] for r in combined}
    gold_ev = {r["macro_event_id"] for r in combined if r["pit_status"] == "PIT_SAFE"}
    silver_ev = {r["macro_event_id"] for r in combined if r["pit_status"] == "PIT_SAFE_WITH_LIMITATION"}
    only_bad = []
    for eid in rem_ids:
        recs = [r for r in remaining if r["macro_event_id"] == eid]
        good = [r for r in recs if r["pit_status"] in {"PIT_SAFE", "PIT_SAFE_WITH_LIMITATION"}]
        if recs and not good:
            only_bad.append(eid)
        if not recs:
            only_bad.append(eid)

    def fam_ids(prefix):
        if prefix == "CPI":
            return [i for i in rem_ids if i.startswith("usd_cpi_")] + [i for i in all_ids if i.startswith("usd_cpi_")]
        if prefix == "EMP":
            return [i for i in all_ids if "empsit" in i]
        return [i for i in all_ids if "fomc" in i]

    def cov(family):
        recs = [r for r in combined if r["event_family"] == family]
        eids = sorted({r["macro_event_id"] for r in recs})
        g = sorted({r["macro_event_id"] for r in recs if r["pit_status"] == "PIT_SAFE"})
        s = sorted({r["macro_event_id"] for r in recs if r["pit_status"] == "PIT_SAFE_WITH_LIMITATION"})
        return eids, g, s, recs

    cpi_e, cpi_g, cpi_s, cpi_recs = cov("CPI")
    emp_e, emp_g, emp_s, emp_recs = cov("EMPLOYMENT_SITUATION")
    fomc_e, fomc_g, fomc_s, fomc_recs = cov("FOMC")

    gold_recs = [r for r in combined if r["pit_status"] == "PIT_SAFE"]
    silver_recs = [r for r in combined if r["pit_status"] == "PIT_SAFE_WITH_LIMITATION"]
    gold_series = sorted({(r["macro_event_id"], r["series_name"]) for r in gold_recs})
    silver_series = sorted({(r["macro_event_id"], r["series_name"]) for r in silver_recs})
    gold_src = sorted({r["source_publisher"] for r in gold_recs})
    surprise_ok = [s for s in surprise if s.get("raw_surprise_possible")]
    sur_cpi = [s for s in surprise_ok if s["macro_event_id"].startswith("usd_cpi_")]
    sur_emp = [s for s in surprise_ok if "empsit" in s["macro_event_id"]]
    sur_fomc = [s for s in surprise_ok if "fomc" in s["macro_event_id"]]

    dis = []
    by = {}
    for r in combined:
        if r.get("forecast_value") is None:
            continue
        if r["pit_status"] not in {"PIT_SAFE", "PIT_SAFE_WITH_LIMITATION"}:
            continue
        if r["expectation_type"] == "INDIVIDUAL_FORECAST":
            continue
        by.setdefault((r["macro_event_id"], r["series_name"]), []).append(r)
    for k, rows in sorted(by.items()):
        pubs = {(r["source_publisher"], r["forecast_value"]) for r in rows}
        if len({v for _, v in pubs}) > 1:
            dis.append("%s %s: %s" % (k[0], k[1], "; ".join("%s=%s" % p for p in sorted(pubs, key=lambda x: str(x[0])))))

    evol = [
        "usd_empsit_2025-11-20: FactSet Oct 2 (T0-49d) vs Reuters Nov 20 unclocked same-day preview (not overwritten).",
        "usd_fomc_statement_2026-06-17: Mar 12 Reuters 63/96 June-cut vintage vs Jun 17 10:03Z uncounted hold preview. Both stored.",
        "usd_fomc_statement_2026-03-18 vs 2026-04-29 vs 2026-06-17: successive Reuters polls show hold-then-later-cut then hold-at-June; vintages kept separate.",
    ]

    parts = []
    parts.append("# MACRO RESEARCH — CONSENSUS STAGE 2")
    parts.append("# FULL HISTORICAL RECONSTRUCTION + FORWARD SNAPSHOT ARCHITECTURE")
    parts.append("")
    parts.append("Research only. Two workstreams kept separate: historical reconstruction uses only evidence whose pre-release provenance can be demonstrated; forward snapshots use OUR observed_at_utc.")
    parts.append("Official US PIT archive was not modified. Pilot evidence was not rewritten.")
    parts.append("")
    parts.append("HISTORICAL EVENT UNIVERSE")
    parts.append("-------------------------")
    parts.append("total eligible: %s" % eligible)
    parts.append("pilot already researched: %s" % pilot_n)
    parts.append("remaining researched: %s" % remaining_n)
    parts.append("Remaining IDs frozen in data/research/macro/consensus_pit/historical/manifest/remaining_events.json BEFORE search. fx_outcomes_used=false.")
    parts.append("Remaining: " + ", ".join(rem_ids))
    parts.append("")
    parts.append("HISTORICAL COVERAGE")
    parts.append("-------------------")
    parts.append("any expectation evidence: %s / 29" % len(any_ev))
    parts.append("PIT_SAFE: %s / 29 events (%s)" % (len(gold_ev), ", ".join(sorted(gold_ev))))
    parts.append("PIT_SAFE_WITH_LIMITATION: %s / 29 events" % len(silver_ev))
    parts.append("uncertain/rejected-only remaining events: %s (%s)" % (len(only_bad), ", ".join(only_bad) if only_bad else "none"))
    parts.append("")
    parts.append("CPI COVERAGE")
    parts.append("------------")
    parts.append("events with evidence: %s" % len(cpi_e))
    parts.append("PIT_SAFE events: %s" % (", ".join(cpi_g) if cpi_g else "none"))
    parts.append("SILVER events: %s" % (", ".join(cpi_s) if cpi_s else "none"))
    parts.append("Series: FactSet typically headline/core YoY NSA median; Reuters often MoM+YoY headline/core. Nov 2025 (Dec 18) official first print includes 2-month SA; no matching 2m consensus was invented.")
    parts.append("")
    parts.append("EMPLOYMENT COVERAGE")
    parts.append("-------------------")
    parts.append("events with evidence: %s" % len(emp_e))
    parts.append("PIT_SAFE events: %s" % (", ".join(emp_g) if emp_g else "none"))
    parts.append("SILVER events: %s" % (", ".join(emp_s) if emp_s else "none"))
    parts.append("AHE generally missing on remaining FactSet Insight pages. Dec 2025 FactSet u-rate labeled November: REJECT_WRONG_SERIES.")
    parts.append("")
    parts.append("FOMC COVERAGE")
    parts.append("-------------")
    parts.append("events with evidence: %s" % len(fomc_e))
    parts.append("PIT_SAFE events: %s" % (", ".join(fomc_g) if fomc_g else "none"))
    parts.append("SILVER events: %s" % (", ".join(fomc_s) if fomc_s else "none"))
    parts.append("Distributions stored. Survey vs futures-implied kept separate. No scalar-bp collapse. No FOMC FX backtest.")
    parts.append("")
    parts.append("GOLD DATASET")
    parts.append("------------")
    parts.append("events: %s" % (", ".join(sorted(gold_ev)) if gold_ev else "none"))
    parts.append("series: %s" % ("; ".join("%s:%s" % x for x in gold_series) if gold_series else "none"))
    parts.append("sources: %s" % (", ".join(gold_src) if gold_src else "none"))
    parts.append("")
    parts.append("SILVER DATASET")
    parts.append("--------------")
    parts.append("events: %s" % (", ".join(sorted(silver_ev)) if silver_ev else "none"))
    parts.append("series: %s" % ("; ".join("%s:%s" % x for x in silver_series) if silver_series else "none"))
    parts.append("limitations: Reuters same-morning Updated without last-mod; FactSet date-only + Tomorrow; delayed-release early vintages; uncounted FOMC color; path-level polls not meeting-specific.")
    parts.append("SILVER is not invalid. It is excluded from the strict surprise dataset.")
    parts.append("")
    parts.append("SOURCE/VINTAGE FINDINGS")
    parts.append("-----------------------")
    parts.append("- Publication-time proof and content-vintage proof remain separate. Archiving a page today does not prove the visible forecast existed before historical T0.")
    parts.append("- Reuters poll articles whose untimed Updated marker falls on a calendar day strictly before T0 can be PIT_SAFE (Oct 21/22 vs Oct 24 CPI and Oct 29 FOMC; Dec 4 vs Dec 10 FOMC).")
    parts.append("- Reuters BLS same-morning previews remain PIT_SAFE_WITH_LIMITATION when Updated is the T0 calendar day.")
    parts.append("- T0-day Reuters without a UTC clock stays UNCERTAIN (Nov 20 employment; Jun 10 CPI).")
    parts.append("- FactSet Insight remains SILVER: date + Tomorrow, no clock. Independently evaluated; URL pattern is not auto-approval.")
    parts.append("- Instant View / actuals wraps quoting 'economists had forecast' are REJECT_POST_RELEASE.")
    parts.append("- No lawful Wayback content-vintage upgrade was obtained in this session.")
    parts.append("- Bloomberg paywall not opened. No illicit mirrors.")
    parts.append("")
    parts.append("MULTI-SOURCE DISAGREEMENT")
    parts.append("-------------------------")
    if dis:
        parts.extend("- " + d for d in dis)
    else:
        parts.append("No remaining-event numeric disagreement after filters; see also Stage-1 pilot (Jul 2026 NFP Reuters 80k / DJ 83k / FactSet 97.5k).")
    parts.append("Providers were not averaged. No house consensus.")
    parts.append("")
    parts.append("CONSENSUS EVOLUTION AVAILABLE")
    parts.append("-----------------------------")
    for line in evol:
        parts.append("- " + line)
    parts.append("Not analyzed against FX.")
    parts.append("")
    parts.append("STRICT RAW SURPRISE COVERAGE")
    parts.append("----------------------------")
    parts.append("CPI: %s records / %s events" % (len(sur_cpi), len({s['macro_event_id'] for s in sur_cpi})))
    parts.append("Employment: %s records / %s events" % (len(sur_emp), len({s['macro_event_id'] for s in sur_emp})))
    parts.append("FOMC: %s records / %s events (expected_change_bp mapping only; probabilities have no surprise_raw)" % (len(sur_fomc), len({s['macro_event_id'] for s in sur_fomc})))
    parts.append("total: %s surprise-capable GOLD records" % len(surprise_ok))
    for s in surprise_ok:
        parts.append("- %s %s forecast=%s actual=%s surprise_raw=%s" % (
            s["macro_event_id"], s["series_name"], s.get("forecast_value"), s.get("official_actual"), s.get("surprise_raw"),
        ))
    parts.append("")
    parts.append("FORWARD SNAPSHOT ARCHITECTURE")
    parts.append("-----------------------------")
    parts.append("Research-only store under data/research/macro/consensus_pit/forward/.")
    parts.append("Schema includes snapshot_id, observed_at_utc (OUR clock), source_publication_utc (separate), SHA-256 of observed bytes, snapshot_sequence, pit_status.")
    parts.append("final_pre_release_snapshot := latest snapshot with observed_at_utc < official_release_utc. Post-T0 observations cannot become final consensus.")
    parts.append("Designed cadence (not a trading rule): T0-48h, T0-24h, T0-12h, T0-4h, T0-1h.")
    parts.append("Compatible with later join to us_pit first prints. No FX surprise model run.")
    parts.append("")
    parts.append("IMMUTABILITY VALIDATION")
    parts.append("-----------------------")
    parts.append("Append-only JSONL. Identical bytes/hash reuse snapshot_id and log a new observation. Changed bytes create a new snapshot_id, hash, sequence, observed_at.")
    parts.append("Tests cover append, dedupe, new vintage, observed_at preservation, separate source clocks, post-T0 exclusion from final consensus, SHA-256 linkage.")
    parts.append("")
    parts.append("SOURCE REGISTRY")
    parts.append("---------------")
    parts.append("data/research/macro/consensus_pit/forward/source_registry.json")
    parts.append("Reuters, FactSet Insight, Dow Jones/IBTimes relay, CME FedWatch citation, Bloomberg. enabled=false on every source. archival/automation permitted=unknown unless proven.")
    parts.append("")
    parts.append("COLLECTION ENABLED:")
    parts.append("NO")
    parts.append("FORWARD_CONSENSUS_COLLECTION_ENABLED=false. No collector, scheduler, Docker, or production bot integration.")
    parts.append("")
    parts.append("CAN HISTORICAL CONSENSUS MINING SCALE?")
    parts.append("PARTIAL")
    parts.append("Documentary pre-release numbers exist for most remaining events, but GOLD still requires both a pre-T0 clock AND content-vintage proof. Same-day Reuters Updated and FactSet date-only keep the bulk of CPI/Employment in SILVER.")
    parts.append("")
    parts.append("IS GOLD DATASET LARGE ENOUGH FOR FX SURPRISE RESEARCH?")
    parts.append("NO")
    parts.append("Additional coverage required: PIT_SAFE scalar CPI and Employment vintages with proven pre-T0 forecast text (WARC/last-mod, provider-preserved original, or our own future observed_at_utc) across the remaining SILVER-only CPI/NFP events; exact-series matches for irregular prints (Nov 2025 2-month SA); AHE where official values exist; meeting-specific FOMC distributions rather than path-level polls. Do not promote SILVER to GOLD to enlarge n.")
    parts.append("")
    parts.append("CAN SILVER DATA BE USED AS SENSITIVITY ANALYSIS LATER?")
    parts.append("YES")
    parts.append("Reason: SILVER records have documentary pre-release semantics and often a pre-T0 clock; the limitation is unproven intra-day/content vintage, not a missing forecast. They must remain a separate sensitivity set, never mixed into the strict GOLD surprise file.")
    parts.append("")
    parts.append("FORWARD PIT ARCHITECTURE READY:")
    parts.append("YES")
    parts.append("Schemas, hashing, immutable append, source registry, disabled collection, and tests are in place. Live collection is not enabled.")
    parts.append("")
    parts.append("SURPRISE FX BACKTEST RUN:")
    parts.append("NO")
    parts.append("MODEL TRAINED:")
    parts.append("NO")
    parts.append("PRODUCTION CHANGE:")
    parts.append("NO")
    parts.append("V2 POLICY CHANGE:")
    parts.append("NO")
    parts.append("OANDA/API REQUESTS:")
    parts.append("0")
    parts.append("OFFICIAL US PIT ARCHIVE MODIFIED:")
    parts.append("NO")
    parts.append("FORWARD COLLECTION ENABLED:")
    parts.append("NO")
    parts.append("FILES CHANGED:")
    parts.append("- data/research/macro/consensus_pit/historical/ (raw, evidence, manifest, normalized, gold, silver)")
    parts.append("- data/research/macro/consensus_pit/forward/ (config, schema, registry)")
    parts.append("- reports/decision_quality/_macro_consensus_pit_stage2.py")
    parts.append("- reports/decision_quality/_macro_consensus_forward.py")
    parts.append("- reports/decision_quality/macro_consensus_pit_stage2.md")
    parts.append("- tests/test_macro_consensus_pit_stage2.py")
    parts.append("STOP.")
    parts.append("")
    REPORT_PATH.write_text("\n".join(parts), encoding="utf-8")


def run() -> dict:
    rem = frozen_remaining()
    meta = event_meta()
    t0 = {eid: meta[eid]["scheduled_release_utc"] for eid in [e["macro_event_id"] for e in rem["remaining"]]}
    hashes = {name: write_excerpt(name, text) for name, text in EXCERPTS.items()}
    remaining = remaining_records(hashes, t0)
    remaining_ids = {e["macro_event_id"] for e in rem["remaining"]}
    for r in remaining:
        if r["macro_event_id"] not in remaining_ids:
            raise RuntimeError("Record not in frozen remaining universe: " + r["consensus_evidence_id"])
    pilot = json.loads(PILOT_EVIDENCE.read_text(encoding="utf-8"))
    for r in pilot:
        r.setdefault("source_stage", "pilot")
    combined = list(pilot) + list(remaining)
    gold = [r for r in combined if r["pit_status"] == "PIT_SAFE"]
    silver = [r for r in combined if r["pit_status"] == "PIT_SAFE_WITH_LIMITATION"]
    surprise = compute_surprise(combined)
    for d in (EVIDENCE_DIR, NORM_DIR, GOLD_DIR, SILVER_DIR, MANIFEST_DIR):
        d.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "remaining_evidence.json").write_text(json.dumps(remaining, indent=2) + "\n", encoding="utf-8")
    (NORM_DIR / "all_records.json").write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
    (GOLD_DIR / "gold.json").write_text(json.dumps(gold, indent=2) + "\n", encoding="utf-8")
    (SILVER_DIR / "silver.json").write_text(json.dumps(silver, indent=2) + "\n", encoding="utf-8")
    (NORM_DIR / "raw_surprise_gold.json").write_text(json.dumps({"surprise": surprise}, indent=2) + "\n", encoding="utf-8")
    write_report(combined, remaining, surprise, rem)
    return {
        "remaining_n": len(remaining_ids),
        "remaining_records": len(remaining),
        "combined_records": len(combined),
        "gold_events": sorted({r["macro_event_id"] for r in gold}),
        "silver_events": sorted({r["macro_event_id"] for r in silver}),
        "surprise_n": sum(1 for s in surprise if s.get("raw_surprise_possible")),
        "us_pit_modified": False,
        "pilot_rewritten": False,
        "collection_enabled": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))

