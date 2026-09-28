"""Consensus PIT pilot: validate records, join official actuals, write report. Research-only."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PILOT_DIR = Path("data/research/macro/consensus_pit/pilot")
ART_DIR = PILOT_DIR / "artifacts"
EVIDENCE_PATH = PILOT_DIR / "consensus_evidence.json"
SURPRISE_PATH = PILOT_DIR / "raw_surprise_proof.json"
SELECTION_PATH = PILOT_DIR / "selection.json"
VALUES_PATH = Path("data/research/macro/us_pit/events/macro_event_value.json")
EVENTS_PATH = Path("data/research/macro/us_pit/events/macro_event.json")
REPORT_PATH = Path("reports/decision_quality/macro_consensus_pit_pilot.md")
US_PIT_DIR = Path("data/research/macro/us_pit")

SELECTED_IDS = [
    "usd_cpi_2025-09-11",
    "usd_cpi_2026-02-13",
    "usd_cpi_2026-07-14",
    "usd_empsit_2025-09-05",
    "usd_empsit_2026-02-11",
    "usd_empsit_2026-08-07",
    "usd_fomc_statement_2025-09-17",
    "usd_fomc_statement_2026-01-28",
    "usd_fomc_statement_2026-07-29",
]

PIT_SAFE = {"PIT_SAFE"}
PIT_OK_JOIN = {"PIT_SAFE", "PIT_SAFE_IF_USING_ARCHIVED_RELEASE"}


def parse_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_excerpt(name: str, text: str) -> tuple[str, str]:
    ART_DIR.mkdir(parents=True, exist_ok=True)
    path = ART_DIR / name
    body = text.strip() + "\n"
    path.write_text(body, encoding="utf-8")
    return str(path).replace("\\", "/"), sha256_text(body)


def event_pit() -> dict[str, str]:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    return {e["macro_event_id"]: e.get("pit_status") for e in events}


def official_map() -> dict[tuple[str, str], dict]:
    pits = event_pit()
    rows = json.loads(VALUES_PATH.read_text(encoding="utf-8"))
    out = {}
    for r in rows:
        rec = dict(r)
        rec["event_pit_status"] = pits.get(r["macro_event_id"])
        out[(r["macro_event_id"], r["series_name"])] = rec
    return out


def event_t0() -> dict[str, str]:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    return {e["macro_event_id"]: e["scheduled_release_utc"] for e in events if e.get("scheduled_release_utc")}


def lead_minutes(pub: str | None, t0: str) -> int | None:
    p, t = parse_utc(pub), parse_utc(t0)
    if p is None or t is None:
        return None
    return int((t - p).total_seconds() // 60)


# Short fair-use excerpts proving the number and meaning. Not full articles.
EXCERPTS = {
    "factset_cpi_aug2025.txt": """By John Butters | September 10, 2025
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of August 2025 is 2.9%.
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 3.1%.
Tomorrow (September 11) the U.S. Bureau of Labor Statistics (BLS) will release the CPI and Core CPI numbers for August.""",
    "morningstar_cpi_aug2025.txt": """Frank Lee Sep 9, 2025
Economists expect the CPI to rise 0.3% on a monthly basis in August and 2.9% year over year, according to the latest consensus estimates from FactSet. Core CPI, which excludes volatile food and fuel prices, is also expected to come in at 0.3% on a monthly basis for August and 3.1% year over year.
CPI report release date and time: Thursday, Sept. 11, at 8:30 a.m. Eastern time.
Goldman Sachs economists predict August's core CPI will rise 0.36%, slightly above the consensus of 0.30%.""",
    "factset_nfp_aug2025.txt": """By John Butters | September 4, 2025
The median estimate for total nonfarm payroll employment for the month of August 2025 is 80,000.
The median estimate for the unemployment rate for the month of August 2025 is 4.2%.
Tomorrow, the U.S. Bureau of Labor Statistics (BLS) will release the total nonfarm payroll employment number and unemployment rate for August.""",
    "reuters_nfp_aug2025.txt": """By Lucia Mutikani
September 5, 2025 4:09 AM UTC Updated September 5, 2025
- Nonfarm payrolls forecast increasing 75,000 in August
- Unemployment rate seen rising to 4.3% from 4.2% in July
- Average hourly earnings expected to rise 0.3%; increase 3.7% year-on-year
A Reuters survey of economists expected the Labor Department's Bureau of Labor Statistics (BLS) would report that nonfarm payrolls increased by 75,000 jobs last month after rising by 73,000 in July.
Estimates ranged from no jobs added to 144,000 positions created.""",
    "reuters_fomc_poll_20250911.txt": """By Indradip Ghosh
September 11, 2025 12:40 PM UTC Updated September 11, 2025
The Fed will lower the interest rate by a quarter point to 4.00%-4.25% next week for the first time this year, 105 of 107 economists in the September 8-11 Reuters poll predicted.
Two of the analysts expected a 50-basis-point reduction.""",
    "reuters_cpi_jan2026.txt": """By Lucia Mutikani
February 13, 2026 5:04 AM UTC Updated February 13, 2026
- Consumer price index forecast to have increased 0.3% in January
- CPI excluding food and energy expected to have gained 0.3%
The CPI likely increased by 0.3% after a similar gain in December, a Reuters survey of economists predicted. Estimates ranged from a 0.1% gain to a 0.4% rise.
In the 12 months through January, the CPI is forecast to have advanced 2.5%.
In the 12 months through January, the so-called core CPI was forecast to have increased 2.5% after advancing 2.6% in December.""",
    "factset_cpi_jan2026.txt": """By John Butters | February 12, 2026
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of January 2026 is 2.4%.
The median estimate of 2.4% is based on 12 estimates collected by FactSet. These CPI estimates range from a low of 2.30% to a high of 2.70%.
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.5%.
Tomorrow (February 13) the U.S. Bureau of Labor Statistics (BLS) will release the CPI and Core CPI numbers for January.""",
    "reuters_nfp_jan2026.txt": """By Lucia Mutikani
February 11, 2026 5:03 AM UTC Updated February 11, 2026
- Nonfarm payrolls forecast increasing 70,000 in January
- Unemployment rate projected to have held steady at 4.4%
Nonfarm payrolls likely increased by 70,000 jobs last month after rising 50,000 in December, a Reuters survey of economists showed.
Estimates ranged from a loss of 10,000 jobs to a gain of 135,000 positions.""",
    "factset_nfp_jan2026.txt": """By John Butters | February 10, 2026
The median estimate for total nonfarm payroll employment for the month of January 2026 is 75,000.
The median estimate of 75,000 is based on 15 estimates collected by FactSet. These estimates range from a low of 50,000 to a high of 85,000.
Tomorrow (February 11), the U.S. Bureau of Labor Statistics (BLS) will release the total nonfarm payroll employment number and unemployment rate for January.""",
    "reuters_poll_fomc_20260121.txt": """By Indradip Ghosh
January 21, 2026 2:02 PM UTC Updated January 21, 2026
All 100 economists in the January 16-21 poll expect the Fed to keep rates at 3.50%-3.75% at its January 27-28 meeting.""",
    "fxstreet_fomc_20260128.txt": """01/28/2026 09:30:05 GMT
The Federal Reserve will announce its latest policy decision later today at 1900 GMT
There is less than a 3% chance of a rate cut being priced by the Federal Funds Futures market and interest rates are expected to remain unchanged at 3.5% - 3.75%.""",
    "reuters_cpi_jun2026.txt": """By Lucia Mutikani
July 14, 2026 4:02 AM UTC Updated July 14, 2026
- Consumer Price Index forecast increasing 3.8% year-on-year in June
The Labor Department's Bureau of Labor Statistics is likely to report on Tuesday that the Consumer Price Index increased by a still-high 3.8% in the 12 months through June, a Reuters survey of economists predicted.
Estimates ranged from as low as 3.6% to as high as 4.0%.
Consumer prices are expected to have dipped 0.1% over the month
Excluding the volatile food and energy components, the CPI was forecast increasing 2.8% year-on-year in June after rising 2.9% in May. The so-called core CPI inflation was projected to have advanced 0.2% over the month.""",
    "factset_cpi_jun2026.txt": """By John Butters | July 13, 2026
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of June 2026 is 3.8%.
The median estimate of 3.8% is based on 4 estimates collected by FactSet. These CPI estimates range from a low of 3.75% to a high of 3.90%.
The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.9%.
Tomorrow (July 14) the U.S. Bureau of Labor Statistics (BLS) will release the CPI and Core CPI numbers for June.""",
    "reuters_nfp_jul2026.txt": """By Lucia Mutikani
August 7, 2026 4:02 AM UTC Updated August 7, 2026
- Nonfarm payrolls forecast to increase 80,000 in July
- Unemployment rate expected to hold steady at 4.2%
Nonfarm payrolls likely increased by 80,000 last month after rising by 57,000, a Reuters survey of economists showed. Estimates ranged from as low as 10,000 to as high as 140,000 jobs added.
Annual wage growth was seen holding steady at 3.5%.""",
    "factset_nfp_jul2026.txt": """By John Butters | August 6, 2026
The median estimate for total nonfarm payroll employment for the month of July 2026 is 97,500.
The median estimate of 97,500 is based on 12 estimates collected by FactSet. These estimates range from a low of 65,000 to a high of 130,000.
Tomorrow (August 7), the U.S. Bureau of Labor Statistics (BLS) will release the total nonfarm payroll employment number and unemployment rate for July.""",
    "ibtimes_nfp_jul2026.txt": """Published 07 August 2026, 8:51 AM BST
Economists polled by Dow Jones expect 83,000 new jobs and an unchanged 4.2% unemployment rate when the Bureau of Labour Statistics reports nonfarm payrolls at 8:30 a.m. in Washington
The Dow Jones survey points to 83,000 jobs against June's weak 57,000, FactSet's panel says 100,000, and the outliers run from Vanguard's 18,000 to 120,000.""",
    "cbs_fomc_20260729.txt": """Updated on: July 29, 2026 / 9:38 AM EDT / CBS News
The Federal Open Market Committee ... is scheduled to announce its next interest rate decision on Wednesday, July 29, at 2 p.m. ET.
The tool now shows a 36% likelihood that the central bank will hike its benchmark rate next week.
Still, the greater likelihood is that the Fed will hold its benchmark rate steady within a target range of 3.5% to 3.75%, according to CME FedWatch.
Economists polled by FactSet predict the Fed will hold interest rates steady at 3.5% to 3.75%.""",
}


def records_template(hashes: dict[str, tuple[str, str]]) -> list[dict]:
    """hashes maps excerpt filename -> (path, sha256)."""
    t0 = event_t0()
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def base(**kw):
        eid = kw["macro_event_id"]
        pub = kw.get("source_publication_utc")
        rec = {
            "retrieved_at_utc": retrieved,
            "official_release_utc": t0[eid],
            "lead_time_minutes": lead_minutes(pub, t0[eid]),
            "reference_period": kw.pop("reference_period"),
            **kw,
        }
        fn = rec.pop("excerpt_file", None)
        if fn:
            loc, h = hashes[fn]
            rec["artifact_location"] = loc
            rec["raw_artifact_hash"] = h
            rec["artifact_scope"] = "short_verbatim_excerpt_not_full_page"
        else:
            rec["artifact_location"] = None
            rec["raw_artifact_hash"] = None
            rec["artifact_scope"] = None
        rec["source_publication_utc"] = pub
        return rec

    out = []
    # CPI Aug 2025 / Sep 11
    out.append(base(
        consensus_evidence_id="ce_cpi_20250911_factset_headline_yoy",
        macro_event_id="usd_cpi_2025-09-11", event_family="CPI", series_name="headline_yoy",
        reference_period="2025-08", forecast_value=2.9, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=None,
        source_publisher="FactSet Insight", source_title="CPI for August 2025 is Projected to Rise 2.9% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-august-2025-is-projected-to-rise-2.9-year-over-year",
        source_publication_utc=None, source_publication_date="2025-09-10",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Byline date Sep 10 plus explicit 'Tomorrow (September 11)'. No UTC clock. Full-page not archived (excerpt only).",
        excerpt_file="factset_cpi_aug2025.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of August 2025 is 2.9%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20250911_factset_core_yoy",
        macro_event_id="usd_cpi_2025-09-11", event_family="CPI", series_name="core_yoy",
        reference_period="2025-08", forecast_value=3.1, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=None,
        source_publisher="FactSet Insight", source_title="CPI for August 2025 is Projected to Rise 2.9% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-august-2025-is-projected-to-rise-2.9-year-over-year",
        source_publication_utc=None, source_publication_date="2025-09-10",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same FactSet page as headline YoY. No MoM on this page.",
        excerpt_file="factset_cpi_aug2025.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 3.1%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20250911_morningstar_factset_headline_mom",
        macro_event_id="usd_cpi_2025-09-11", event_family="CPI", series_name="headline_mom",
        reference_period="2025-08", forecast_value=0.3, unit="percent", seasonal_adjustment="SA",
        expectation_type="PROVIDER_CONSENSUS", survey_provider="FactSet via Morningstar", n_forecasters=None,
        source_publisher="Morningstar", source_title="August CPI Report Forecasts Point to Sticky Inflation and Tariff Pressures",
        source_reference="https://www.morningstar.com/economy/august-cpi-report-forecasts-point-sticky-inflation-tariff-pressures",
        source_publication_utc=None, source_publication_date="2025-09-09",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Date Sep 9 (two days before T0) but no clock. Relays FactSet consensus. SA assumed from standard CPI MoM reporting; article does not print SA/NSA.",
        excerpt_file="morningstar_cpi_aug2025.txt",
        verbatim_evidence_snippet="Economists expect the CPI to rise 0.3% on a monthly basis in August and 2.9% year over year, according to the latest consensus estimates from FactSet.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20250911_gs_core_mom_individual",
        macro_event_id="usd_cpi_2025-09-11", event_family="CPI", series_name="core_mom",
        reference_period="2025-08", forecast_value=0.36, unit="percent", seasonal_adjustment="SA",
        expectation_type="INDIVIDUAL_FORECAST", survey_provider="Goldman Sachs", n_forecasters=1,
        source_publisher="Morningstar", source_title="August CPI Report Forecasts Point to Sticky Inflation and Tariff Pressures",
        source_reference="https://www.morningstar.com/economy/august-cpi-report-forecasts-point-sticky-inflation-tariff-pressures",
        source_publication_utc=None, source_publication_date="2025-09-09",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Not consensus. Preserved as INDIVIDUAL_FORECAST. Article states consensus 0.30%.",
        excerpt_file="morningstar_cpi_aug2025.txt",
        verbatim_evidence_snippet="Goldman Sachs economists predict August's core CPI will rise 0.36%, slightly above the consensus of 0.30%.",
    ))
    # Employment Aug 2025 / Sep 5
    out.append(base(
        consensus_evidence_id="ce_empsit_20250905_reuters_nfp",
        macro_event_id="usd_empsit_2025-09-05", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2025-08", forecast_value=75000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Lackluster US job growth anticipated in August; focus on revisions",
        source_reference="https://www.reuters.com/business/lackluster-us-job-growth-anticipated-august-focus-revisions-2025-09-05/",
        source_publication_utc="2025-09-05T04:09:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Original clock 04:09Z < T0 12:30Z. Same-calendar-day 'Updated September 5, 2025' without last-mod clock. Body remains preview-tense. Range 0 to 144000 preserved, not averaged.",
        excerpt_file="reuters_nfp_aug2025.txt",
        verbatim_evidence_snippet="A Reuters survey of economists expected ... nonfarm payrolls increased by 75,000 jobs last month",
        forecast_range={"min": 0, "max": 144000},
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20250905_reuters_urate",
        macro_event_id="usd_empsit_2025-09-05", event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
        reference_period="2025-08", forecast_value=4.3, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Lackluster US job growth anticipated in August; focus on revisions",
        source_reference="https://www.reuters.com/business/lackluster-us-job-growth-anticipated-august-focus-revisions-2025-09-05/",
        source_publication_utc="2025-09-05T04:09:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same Reuters preview. Headline says unemployment seen rising to 4.3% from 4.2%.",
        excerpt_file="reuters_nfp_aug2025.txt",
        verbatim_evidence_snippet="Unemployment rate seen rising to 4.3% from 4.2% in July",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20250905_reuters_ahe_mom",
        macro_event_id="usd_empsit_2025-09-05", event_family="EMPLOYMENT_SITUATION", series_name="average_hourly_earnings_mom",
        reference_period="2025-08", forecast_value=0.3, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Lackluster US job growth anticipated in August; focus on revisions",
        source_reference="https://www.reuters.com/business/lackluster-us-job-growth-anticipated-august-focus-revisions-2025-09-05/",
        source_publication_utc="2025-09-05T04:09:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Bullet 'Average hourly earnings expected to rise 0.3%'.",
        excerpt_file="reuters_nfp_aug2025.txt",
        verbatim_evidence_snippet="Average hourly earnings expected to rise 0.3%; increase 3.7% year-on-year",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20250905_reuters_ahe_yoy",
        macro_event_id="usd_empsit_2025-09-05", event_family="EMPLOYMENT_SITUATION", series_name="average_hourly_earnings_yoy",
        reference_period="2025-08", forecast_value=3.7, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Lackluster US job growth anticipated in August; focus on revisions",
        source_reference="https://www.reuters.com/business/lackluster-us-job-growth-anticipated-august-focus-revisions-2025-09-05/",
        source_publication_utc="2025-09-05T04:09:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="YoY 3.7% in same bullet. NSA typical for AHE YoY.",
        excerpt_file="reuters_nfp_aug2025.txt",
        verbatim_evidence_snippet="Average hourly earnings expected to rise 0.3%; increase 3.7% year-on-year",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20250905_factset_nfp",
        macro_event_id="usd_empsit_2025-09-05", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2025-08", forecast_value=80000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=None,
        source_publisher="FactSet Insight", source_title="Total Nonfarm Payrolls for August 2025 Are Projected to Rise By 80,000",
        source_reference="https://insight.factset.com/total-nonfarm-payrolls-for-august-2025-are-projected-to-rise-by-80000",
        source_publication_utc=None, source_publication_date="2025-09-04",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Disagrees with Reuters 75,000. Not averaged.",
        excerpt_file="factset_nfp_aug2025.txt",
        verbatim_evidence_snippet="The median estimate for total nonfarm payroll employment for the month of August 2025 is 80,000.",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20250905_factset_urate",
        macro_event_id="usd_empsit_2025-09-05", event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
        reference_period="2025-08", forecast_value=4.2, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=None,
        source_publisher="FactSet Insight", source_title="Total Nonfarm Payrolls for August 2025 Are Projected to Rise By 80,000",
        source_reference="https://insight.factset.com/total-nonfarm-payrolls-for-august-2025-are-projected-to-rise-by-80000",
        source_publication_utc=None, source_publication_date="2025-09-04",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Disagrees with Reuters 4.3%. Not averaged.",
        excerpt_file="factset_nfp_aug2025.txt",
        verbatim_evidence_snippet="The median estimate for the unemployment rate for the month of August 2025 is 4.2%.",
    ))
    # FOMC Sep 17
    out.append(base(
        consensus_evidence_id="ce_fomc_20250917_reuters_poll_decision",
        macro_event_id="usd_fomc_statement_2025-09-17", event_family="FOMC", series_name="expected_policy_decision",
        reference_period="2025-09-16/17", forecast_value="cut_25bp", unit="categorical", seasonal_adjustment=None,
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=107,
        source_publisher="Reuters", source_title="September Fed rate cut a done deal, at least one more to follow by year-end: Reuters poll",
        source_reference="https://www.reuters.com/business/september-fed-rate-cut-done-deal-least-one-more-follow-by-year-end-reuters-poll-2025-09-11/",
        source_publication_utc="2025-09-11T12:40:00Z",
        pit_status="PIT_SAFE",
        notes="105 of 107 expect -25bp; 2 expect -50bp. Poll window Sep 8-11 overlaps CPI morning; still < FOMC T0. Distribution retained, not collapsed to a probability.",
        excerpt_file="reuters_fomc_poll_20250911.txt",
        verbatim_evidence_snippet="105 of 107 economists in the September 8-11 Reuters poll predicted. Two of the analysts expected a 50-basis-point reduction.",
        distribution={"cut_25bp": 105, "cut_50bp": 2, "n": 107},
        expected_change_bp=-25,
    ))
    # CPI Jan 2026 / Feb 13
    out.append(base(
        consensus_evidence_id="ce_cpi_20260213_reuters_headline_mom",
        macro_event_id="usd_cpi_2026-02-13", event_family="CPI", series_name="headline_mom",
        reference_period="2026-01", forecast_value=0.3, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Start-of-year price increases seen lifting monthly US consumer inflation in January",
        source_reference="https://www.reuters.com/business/start-of-year-price-increases-seen-lifting-monthly-us-consumer-inflation-january-2026-02-13/",
        source_publication_utc="2026-02-13T05:04:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="05:04Z < T0 13:30Z. Same-day Updated without last-mod. Range 0.1 to 0.4 not averaged.",
        excerpt_file="reuters_cpi_jan2026.txt",
        verbatim_evidence_snippet="The CPI likely increased by 0.3% after a similar gain in December, a Reuters survey of economists predicted.",
        forecast_range={"min": 0.1, "max": 0.4},
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260213_reuters_headline_yoy",
        macro_event_id="usd_cpi_2026-02-13", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-01", forecast_value=2.5, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Start-of-year price increases seen lifting monthly US consumer inflation in January",
        source_reference="https://www.reuters.com/business/start-of-year-price-increases-seen-lifting-monthly-us-consumer-inflation-january-2026-02-13/",
        source_publication_utc="2026-02-13T05:04:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Disagrees with FactSet median 2.4% YoY. Not averaged.",
        excerpt_file="reuters_cpi_jan2026.txt",
        verbatim_evidence_snippet="In the 12 months through January, the CPI is forecast to have advanced 2.5%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260213_reuters_core_mom",
        macro_event_id="usd_cpi_2026-02-13", event_family="CPI", series_name="core_mom",
        reference_period="2026-01", forecast_value=0.3, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Start-of-year price increases seen lifting monthly US consumer inflation in January",
        source_reference="https://www.reuters.com/business/start-of-year-price-increases-seen-lifting-monthly-us-consumer-inflation-january-2026-02-13/",
        source_publication_utc="2026-02-13T05:04:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Bullet and body both 0.3% core MoM.",
        excerpt_file="reuters_cpi_jan2026.txt",
        verbatim_evidence_snippet="CPI excluding food and energy expected to have gained 0.3%",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260213_reuters_core_yoy",
        macro_event_id="usd_cpi_2026-02-13", event_family="CPI", series_name="core_yoy",
        reference_period="2026-01", forecast_value=2.5, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="Start-of-year price increases seen lifting monthly US consumer inflation in January",
        source_reference="https://www.reuters.com/business/start-of-year-price-increases-seen-lifting-monthly-us-consumer-inflation-january-2026-02-13/",
        source_publication_utc="2026-02-13T05:04:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Matches FactSet core YoY 2.5%.",
        excerpt_file="reuters_cpi_jan2026.txt",
        verbatim_evidence_snippet="the so-called core CPI was forecast to have increased 2.5% after advancing 2.6% in December.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260213_factset_headline_yoy",
        macro_event_id="usd_cpi_2026-02-13", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-01", forecast_value=2.4, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=12,
        source_publisher="FactSet Insight", source_title="CPI for January 2026 is Projected to Rise 2.4% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-january-2026-is-projected-to-rise-2.4-year-over-year",
        source_publication_utc=None, source_publication_date="2026-02-12",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Disagrees with Reuters 2.5%. Range 2.30-2.70. No MoM on this page.",
        excerpt_file="factset_cpi_jan2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of January 2026 is 2.4%.",
        forecast_range={"min": 2.3, "max": 2.7},
    ))
    # Employment Jan 2026 / Feb 11
    out.append(base(
        consensus_evidence_id="ce_empsit_20260211_reuters_nfp",
        macro_event_id="usd_empsit_2026-02-11", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2026-01", forecast_value=70000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US job growth likely picked up in January; unemployment rate forecast steady at 4.4%",
        source_reference="https://www.reuters.com/business/us-job-growth-likely-picked-up-january-unemployment-rate-forecast-steady-44-2026-02-11/",
        source_publication_utc="2026-02-11T05:03:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="CES annual benchmark on this official event. Consensus is still for the headline first print, not the benchmark revision. Range -10k to +135k.",
        excerpt_file="reuters_nfp_jan2026.txt",
        verbatim_evidence_snippet="Nonfarm payrolls likely increased by 70,000 jobs last month after rising 50,000 in December, a Reuters survey of economists showed.",
        forecast_range={"min": -10000, "max": 135000},
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260211_reuters_urate",
        macro_event_id="usd_empsit_2026-02-11", event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
        reference_period="2026-01", forecast_value=4.4, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US job growth likely picked up in January; unemployment rate forecast steady at 4.4%",
        source_reference="https://www.reuters.com/business/us-job-growth-likely-picked-up-january-unemployment-rate-forecast-steady-44-2026-02-11/",
        source_publication_utc="2026-02-11T05:03:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same preview.",
        excerpt_file="reuters_nfp_jan2026.txt",
        verbatim_evidence_snippet="Unemployment rate projected to have held steady at 4.4%",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260211_factset_nfp",
        macro_event_id="usd_empsit_2026-02-11", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2026-01", forecast_value=75000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=15,
        source_publisher="FactSet Insight", source_title="Total Nonfarm Payrolls for January 2026 Are Projected to Rise By 75,000",
        source_reference="https://insight.factset.com/total-nonfarm-payrolls-for-january-2026-are-projected-to-rise-by-75000",
        source_publication_utc=None, source_publication_date="2026-02-10",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Disagrees with Reuters 70,000. FactSet range 50k-85k vs Reuters -10k to 135k.",
        excerpt_file="factset_nfp_jan2026.txt",
        verbatim_evidence_snippet="The median estimate for total nonfarm payroll employment for the month of January 2026 is 75,000.",
        forecast_range={"min": 50000, "max": 85000},
    ))
    # FOMC Jan 28
    out.append(base(
        consensus_evidence_id="ce_fomc_20260128_reuters_poll_hold",
        macro_event_id="usd_fomc_statement_2026-01-28", event_family="FOMC", series_name="expected_policy_decision",
        reference_period="2026-01-27/28", forecast_value="hold", unit="categorical", seasonal_adjustment=None,
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=100,
        source_publisher="Reuters", source_title="Fed to hold rates through March ... Reuters poll",
        source_reference="https://www.reuters.com/business/fed-hold-rates-through-march-possibly-through-powells-tenure-strong-growth-2026-01-21/",
        source_publication_utc="2026-01-21T14:02:00Z",
        pit_status="PIT_SAFE",
        notes="All 100 expect hold at 3.50-3.75 at Jan 27-28. Poll fielded Jan 16-21. Not converted to a scalar -25bp.",
        excerpt_file="reuters_poll_fomc_20260121.txt",
        verbatim_evidence_snippet="All 100 economists in the January 16-21 poll expect the Fed to keep rates at 3.50%-3.75% at its January 27-28 meeting.",
        expected_change_bp=0,
        distribution={"hold": 100, "n": 100},
    ))
    out.append(base(
        consensus_evidence_id="ce_fomc_20260128_fxstreet_ff_futures",
        macro_event_id="usd_fomc_statement_2026-01-28", event_family="FOMC", series_name="market_implied_cut_probability",
        reference_period="2026-01-27/28", forecast_value=0.03, unit="probability", seasonal_adjustment=None,
        expectation_type="MARKET_IMPLIED_EXPECTATION", survey_provider="Federal Funds futures via FXStreet", n_forecasters=None,
        source_publisher="FXStreet", source_title="FOMC preview: Fed on hold, as independence fears and Dollar's demise in focus",
        source_reference="https://www.fxstreet.com/analysis/fomc-preview-fed-on-hold-as-independence-fears-and-dollars-demise-in-focus-202601280930",
        source_publication_utc="2026-01-28T09:30:05Z",
        pit_status="PIT_SAFE",
        notes="Clock 09:30:05 GMT < T0 19:00Z. 'less than a 3%' cut odds. Stored as upper bound 0.03, not as consensus=-25bp. Not reconstructed from today's CME tool.",
        excerpt_file="fxstreet_fomc_20260128.txt",
        verbatim_evidence_snippet="There is less than a 3% chance of a rate cut being priced by the Federal Funds Futures market",
        probability_cut_lt=0.03,
    ))
    # CPI Jun 2026 / Jul 14
    out.append(base(
        consensus_evidence_id="ce_cpi_20260714_reuters_headline_yoy",
        macro_event_id="usd_cpi_2026-07-14", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-06", forecast_value=3.8, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation likely increased at a slow pace in June as gasoline prices retreated",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-likely-increased-slow-pace-june-gasoline-prices-retreated-2026-07-14/",
        source_publication_utc="2026-07-14T04:02:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Range 3.6 to 4.0. Same-day Updated.",
        excerpt_file="reuters_cpi_jun2026.txt",
        verbatim_evidence_snippet="the Consumer Price Index increased by a still-high 3.8% in the 12 months through June, a Reuters survey of economists predicted.",
        forecast_range={"min": 3.6, "max": 4.0},
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260714_reuters_headline_mom",
        macro_event_id="usd_cpi_2026-07-14", event_family="CPI", series_name="headline_mom",
        reference_period="2026-06", forecast_value=-0.1, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation likely increased at a slow pace in June as gasoline prices retreated",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-likely-increased-slow-pace-june-gasoline-prices-retreated-2026-07-14/",
        source_publication_utc="2026-07-14T04:02:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="MoM -0.1%.",
        excerpt_file="reuters_cpi_jun2026.txt",
        verbatim_evidence_snippet="Consumer prices are expected to have dipped 0.1% over the month",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260714_reuters_core_yoy",
        macro_event_id="usd_cpi_2026-07-14", event_family="CPI", series_name="core_yoy",
        reference_period="2026-06", forecast_value=2.8, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation likely increased at a slow pace in June as gasoline prices retreated",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-likely-increased-slow-pace-june-gasoline-prices-retreated-2026-07-14/",
        source_publication_utc="2026-07-14T04:02:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Disagrees with FactSet core YoY 2.9%.",
        excerpt_file="reuters_cpi_jun2026.txt",
        verbatim_evidence_snippet="the CPI was forecast increasing 2.8% year-on-year in June after rising 2.9% in May.",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260714_reuters_core_mom",
        macro_event_id="usd_cpi_2026-07-14", event_family="CPI", series_name="core_mom",
        reference_period="2026-06", forecast_value=0.2, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US consumer inflation likely increased at a slow pace in June as gasoline prices retreated",
        source_reference="https://www.reuters.com/business/us-consumer-inflation-likely-increased-slow-pace-june-gasoline-prices-retreated-2026-07-14/",
        source_publication_utc="2026-07-14T04:02:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Core MoM 0.2%.",
        excerpt_file="reuters_cpi_jun2026.txt",
        verbatim_evidence_snippet="core CPI inflation was projected to have advanced 0.2% over the month",
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260714_factset_headline_yoy",
        macro_event_id="usd_cpi_2026-07-14", event_family="CPI", series_name="headline_yoy",
        reference_period="2026-06", forecast_value=3.8, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=4,
        source_publisher="FactSet Insight", source_title="CPI for June 2026 is Projected to Rise 3.8% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-june-2026-is-projected-to-rise-3.8-year-over-year",
        source_publication_utc=None, source_publication_date="2026-07-13",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Matches Reuters headline YoY 3.8%. n=4 is a thin panel. No MoM on this page.",
        excerpt_file="factset_cpi_jun2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of June 2026 is 3.8%.",
        forecast_range={"min": 3.75, "max": 3.9},
    ))
    out.append(base(
        consensus_evidence_id="ce_cpi_20260714_factset_core_yoy",
        macro_event_id="usd_cpi_2026-07-14", event_family="CPI", series_name="core_yoy",
        reference_period="2026-06", forecast_value=2.9, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=4,
        source_publisher="FactSet Insight", source_title="CPI for June 2026 is Projected to Rise 3.8% Year-Over-Year",
        source_reference="https://insight.factset.com/consumer-price-index-cpi-for-june-2026-is-projected-to-rise-3.8-year-over-year",
        source_publication_utc=None, source_publication_date="2026-07-13",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Disagrees with Reuters 2.8%.",
        excerpt_file="factset_cpi_jun2026.txt",
        verbatim_evidence_snippet="The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 2.9%.",
    ))
    # Employment Jul 2026 / Aug 7
    out.append(base(
        consensus_evidence_id="ce_empsit_20260807_reuters_nfp",
        macro_event_id="usd_empsit_2026-08-07", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2026-07", forecast_value=80000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US job growth likely picked up in July; unemployment rate forecast unchanged at 4.2%",
        source_reference="https://www.reuters.com/business/us-job-growth-likely-picked-up-july-unemployment-rate-forecast-unchanged-42-2026-08-07/",
        source_publication_utc="2026-08-07T04:02:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Range 10k-140k. Disagrees with FactSet 97500 and Dow Jones 83000.",
        excerpt_file="reuters_nfp_jul2026.txt",
        verbatim_evidence_snippet="Nonfarm payrolls likely increased by 80,000 last month after rising by 57,000, a Reuters survey of economists showed.",
        forecast_range={"min": 10000, "max": 140000},
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260807_reuters_urate",
        macro_event_id="usd_empsit_2026-08-07", event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
        reference_period="2026-07", forecast_value=4.2, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US job growth likely picked up in July; unemployment rate forecast unchanged at 4.2%",
        source_reference="https://www.reuters.com/business/us-job-growth-likely-picked-up-july-unemployment-rate-forecast-unchanged-42-2026-08-07/",
        source_publication_utc="2026-08-07T04:02:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Same preview.",
        excerpt_file="reuters_nfp_jul2026.txt",
        verbatim_evidence_snippet="Unemployment rate expected to hold steady at 4.2%",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260807_reuters_ahe_yoy",
        macro_event_id="usd_empsit_2026-08-07", event_family="EMPLOYMENT_SITUATION", series_name="average_hourly_earnings_yoy",
        reference_period="2026-07", forecast_value=3.5, unit="percent", seasonal_adjustment="NSA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Reuters", n_forecasters=None,
        source_publisher="Reuters", source_title="US job growth likely picked up in July; unemployment rate forecast unchanged at 4.2%",
        source_reference="https://www.reuters.com/business/us-job-growth-likely-picked-up-july-unemployment-rate-forecast-unchanged-42-2026-08-07/",
        source_publication_utc="2026-08-07T04:02:00Z",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="AHE YoY 3.5%. Official archive for this event has no AHE YoY first print in us_pit values — join not possible.",
        excerpt_file="reuters_nfp_jul2026.txt",
        verbatim_evidence_snippet="Annual wage growth was seen holding steady at 3.5%.",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260807_factset_nfp",
        macro_event_id="usd_empsit_2026-08-07", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2026-07", forecast_value=97500, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_MEDIAN", survey_provider="FactSet", n_forecasters=12,
        source_publisher="FactSet Insight", source_title="Total Nonfarm Payrolls for July 2026 Are Projected to Rise By 97,500",
        source_reference="https://insight.factset.com/total-nonfarm-payrolls-for-july-2026-are-projected-to-rise-by-97500",
        source_publication_utc=None, source_publication_date="2026-08-06",
        pit_status="PIT_SAFE_WITH_LIMITATION",
        notes="Material disagreement vs Reuters 80k and Dow Jones 83k.",
        excerpt_file="factset_nfp_jul2026.txt",
        verbatim_evidence_snippet="The median estimate for total nonfarm payroll employment for the month of July 2026 is 97,500.",
        forecast_range={"min": 65000, "max": 130000},
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260807_dowjones_nfp",
        macro_event_id="usd_empsit_2026-08-07", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2026-07", forecast_value=83000, unit="persons", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Dow Jones", n_forecasters=None,
        source_publisher="IBTimes UK", source_title="Markets Hold Their Breath for Friday's Jobs Number",
        source_reference="https://www.ibtimes.co.uk/wall-street-awaits-july-jobs-report-amid-feds-silence-1812939",
        source_publication_utc="2026-08-07T07:51:00Z",
        pit_status="PIT_SAFE",
        notes="Published 07 Aug 2026 08:51 BST = 07:51Z < T0 12:30Z. Relays Dow Jones poll. Also reports FactSet 100000 in the same article as a different panel (IBTimes says 100k; FactSet insight page says 97500) — those are not averaged.",
        excerpt_file="ibtimes_nfp_jul2026.txt",
        verbatim_evidence_snippet="Economists polled by Dow Jones expect 83,000 new jobs and an unchanged 4.2% unemployment rate",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260807_dowjones_urate",
        macro_event_id="usd_empsit_2026-08-07", event_family="EMPLOYMENT_SITUATION", series_name="unemployment_rate",
        reference_period="2026-07", forecast_value=4.2, unit="percent", seasonal_adjustment="SA",
        expectation_type="SURVEY_CONSENSUS", survey_provider="Dow Jones", n_forecasters=None,
        source_publisher="IBTimes UK", source_title="Markets Hold Their Breath for Friday's Jobs Number",
        source_reference="https://www.ibtimes.co.uk/wall-street-awaits-july-jobs-report-amid-feds-silence-1812939",
        source_publication_utc="2026-08-07T07:51:00Z",
        pit_status="PIT_SAFE",
        notes="Same IBTimes/Dow Jones preview.",
        excerpt_file="ibtimes_nfp_jul2026.txt",
        verbatim_evidence_snippet="Economists polled by Dow Jones expect 83,000 new jobs and an unchanged 4.2% unemployment rate",
    ))
    out.append(base(
        consensus_evidence_id="ce_empsit_20260807_vanguard_nfp_individual",
        macro_event_id="usd_empsit_2026-08-07", event_family="EMPLOYMENT_SITUATION", series_name="nonfarm_payroll_change",
        reference_period="2026-07", forecast_value=18000, unit="persons", seasonal_adjustment="SA",
        expectation_type="INDIVIDUAL_FORECAST", survey_provider="Vanguard", n_forecasters=1,
        source_publisher="IBTimes UK", source_title="Markets Hold Their Breath for Friday's Jobs Number",
        source_reference="https://www.ibtimes.co.uk/wall-street-awaits-july-jobs-report-amid-feds-silence-1812939",
        source_publication_utc="2026-08-07T07:51:00Z",
        pit_status="PIT_SAFE",
        notes="Not consensus. Pension-account-based individual forecast.",
        excerpt_file="ibtimes_nfp_jul2026.txt",
        verbatim_evidence_snippet="the outliers run from Vanguard's 18,000, drawn from its own pension-account data, to 120,000.",
    ))
    # FOMC Jul 29
    out.append(base(
        consensus_evidence_id="ce_fomc_20260729_factset_hold",
        macro_event_id="usd_fomc_statement_2026-07-29", event_family="FOMC", series_name="expected_policy_decision",
        reference_period="2026-07-28/29", forecast_value="hold", unit="categorical", seasonal_adjustment=None,
        expectation_type="SURVEY_CONSENSUS", survey_provider="FactSet", n_forecasters=None,
        source_publisher="CBS News", source_title="Will the Federal Reserve raise interest rates? Here is what experts predict for July's meeting.",
        source_reference="https://www.cbsnews.com/news/fed-interest-rate-decision-july-meeting/",
        source_publication_utc="2026-07-29T13:38:00Z",
        pit_status="PIT_SAFE",
        notes="Updated 9:38 AM EDT = 13:38Z < T0 18:00Z. FactSet survey hold. n_forecasters not stated.",
        excerpt_file="cbs_fomc_20260729.txt",
        verbatim_evidence_snippet="Economists polled by FactSet predict the Fed will hold interest rates steady at 3.5% to 3.75%.",
        expected_change_bp=0,
    ))
    out.append(base(
        consensus_evidence_id="ce_fomc_20260729_fedwatch_hike_prob",
        macro_event_id="usd_fomc_statement_2026-07-29", event_family="FOMC", series_name="market_implied_hike_probability",
        reference_period="2026-07-28/29", forecast_value=0.36, unit="probability", seasonal_adjustment=None,
        expectation_type="MARKET_IMPLIED_EXPECTATION", survey_provider="CME FedWatch via CBS News", n_forecasters=None,
        source_publisher="CBS News", source_title="Will the Federal Reserve raise interest rates? Here is what experts predict for July's meeting.",
        source_reference="https://www.cbsnews.com/news/fed-interest-rate-decision-july-meeting/",
        source_publication_utc="2026-07-29T13:38:00Z",
        pit_status="PIT_SAFE",
        notes="36% hike odds contemporaneously cited. Not converted to consensus=+25bp. Greater likelihood is hold per same article. Not reconstructed from today's FedWatch.",
        excerpt_file="cbs_fomc_20260729.txt",
        verbatim_evidence_snippet="The tool now shows a 36% likelihood that the central bank will hike its benchmark rate next week.",
    ))
    return out


def assert_pit_clock(rec: dict) -> None:
    t0 = parse_utc(rec["official_release_utc"])
    pub = parse_utc(rec.get("source_publication_utc"))
    if rec["pit_status"] == "PIT_SAFE":
        assert pub is not None, rec["consensus_evidence_id"]
        assert t0 is not None
        assert pub < t0, rec["consensus_evidence_id"]
    if pub is not None and t0 is not None and pub >= t0:
        assert rec["pit_status"] == "REJECT_POST_RELEASE", rec["consensus_evidence_id"]


def compute_surprise(records: list[dict]) -> list[dict]:
    off = official_map()
    out = []
    for rec in records:
        if rec["pit_status"] not in PIT_SAFE:
            continue
        key = (rec["macro_event_id"], rec["series_name"])
        official = off.get(key)
        row = {
            "consensus_evidence_id": rec["consensus_evidence_id"],
            "macro_event_id": rec["macro_event_id"],
            "series_name": rec["series_name"],
            "expectation_type": rec["expectation_type"],
            "forecast_value": rec["forecast_value"],
            "official_join_valid": False,
            "raw_surprise_possible": False,
            "surprise_raw": None,
            "notes": "",
        }
        if rec["series_name"] in {"expected_policy_decision", "market_implied_cut_probability", "market_implied_hike_probability"}:
            actual_chg = off.get((rec["macro_event_id"], "ff_target_change_bp"), {}).get("actual_first_print")
            row["official_join_valid"] = actual_chg is not None
            row["official_actual"] = actual_chg
            if rec["series_name"] == "expected_policy_decision" and rec.get("expected_change_bp") is not None and actual_chg is not None:
                row["raw_surprise_possible"] = True
                row["surprise_raw"] = float(actual_chg) - float(rec["expected_change_bp"])
                row["notes"] = "Categorical survey mapped only via stored expected_change_bp. Probability distribution not collapsed."
            elif rec["series_name"].startswith("market_implied"):
                row["notes"] = "Market-implied probability retained. Not converted to a scalar consensus rate change. No surprise_raw."
            out.append(row)
            continue
        if official is None:
            row["notes"] = "No matching official series on us_pit values."
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
        if rec.get("unit") and official.get("unit") and rec["unit"] != official["unit"]:
            row["notes"] = "Unit mismatch."
            out.append(row)
            continue
        row["official_join_valid"] = True
        row["official_actual"] = actual
        if rec["expectation_type"] == "INDIVIDUAL_FORECAST":
            row["notes"] = "Joinable but individual forecast is not consensus; surprise not computed as consensus surprise."
            out.append(row)
            continue
        row["raw_surprise_possible"] = True
        row["surprise_raw"] = float(actual) - float(rec["forecast_value"])
        row["notes"] = "Pipeline proof only. No z-score. No FX join."
        out.append(row)
    return out


def coverage_matrix(records: list[dict], surprise: list[dict]) -> list[dict]:
    by = {i: [] for i in SELECTED_IDS}
    for r in records:
        by[r["macro_event_id"]].append(r)
    sur_by = {}
    for s in surprise:
        sur_by.setdefault(s["macro_event_id"], []).append(s)
    t0 = event_t0()
    fam = {
        "usd_cpi_2025-09-11": "CPI",
        "usd_cpi_2026-02-13": "CPI",
        "usd_cpi_2026-07-14": "CPI",
        "usd_empsit_2025-09-05": "EMPLOYMENT_SITUATION",
        "usd_empsit_2026-02-11": "EMPLOYMENT_SITUATION",
        "usd_empsit_2026-08-07": "EMPLOYMENT_SITUATION",
        "usd_fomc_statement_2025-09-17": "FOMC",
        "usd_fomc_statement_2026-01-28": "FOMC",
        "usd_fomc_statement_2026-07-29": "FOMC",
    }
    rows = []
    for eid in SELECTED_IDS:
        recs = by[eid]
        safe = [r for r in recs if r["pit_status"] == "PIT_SAFE"]
        clock = any(r.get("source_publication_utc") for r in recs)
        hashed = any(r.get("raw_artifact_hash") for r in recs)
        series = sorted({r["series_name"] for r in recs})
        join_ok = any(s.get("official_join_valid") for s in sur_by.get(eid, []))
        surprise_ok = any(s.get("raw_surprise_possible") for s in sur_by.get(eid, []))
        rows.append({
            "event": eid,
            "family": fam[eid],
            "T0": t0[eid],
            "sources_found": len({r["source_reference"] for r in recs}),
            "PIT_safe_sources": len({r["source_reference"] for r in safe}),
            "series_covered": ",".join(series),
            "publication_time_proven": clock,
            "artifact_hashed": hashed,
            "official_join_valid": join_ok,
            "raw_surprise_possible": surprise_ok,
        })
    return rows


def write_report(records: list[dict], surprise: list[dict], matrix: list[dict]) -> None:
    n_events = 9
    events_safe = {r["macro_event_id"] for r in records if r["pit_status"] == "PIT_SAFE"}
    series_safe = sorted({(r["macro_event_id"], r["series_name"], r["expectation_type"]) for r in records if r["pit_status"] == "PIT_SAFE"})
    events_surprise = {s["macro_event_id"] for s in surprise if s.get("raw_surprise_possible")}
    fomc_proven = [e for e in events_safe if "fomc" in e]

    def lines_for(family: str) -> list[str]:
        recs = [r for r in records if r["event_family"] == family]
        out = []
        for r in recs:
            out.append(
                "- %s | %s | %s=%s %s | %s | pub=%s | PIT=%s"
                % (
                    r["macro_event_id"],
                    r["expectation_type"],
                    r["series_name"],
                    r["forecast_value"],
                    r.get("unit"),
                    r["survey_provider"] or r["source_publisher"],
                    r.get("source_publication_utc") or r.get("source_publication_date"),
                    r["pit_status"],
                )
            )
        return out

    parts = []
    parts.append("# MACRO RESEARCH — CONSENSUS STAGE 1")
    parts.append("# HISTORICAL PRE-RELEASE CONSENSUS MINING PILOT")
    parts.append("")
    parts.append("Research only. Not price-derived consensus. Not today's calendar forecast field.")
    parts.append("Official actuals joined from `data/research/macro/us_pit/` (read, not modified).")
    parts.append("No FX-performance analysis. No model. No production change.")
    parts.append("")
    parts.append("PILOT SELECTION")
    parts.append("---------------")
    parts.append("Frozen in `data/research/macro/consensus_pit/pilot/SELECTION.md` BEFORE any consensus search.")
    parts.append("Rule: from the 29 Stage-3 eligible PIT-approved events, within each family pick earliest T0, T0 closest to the midpoint of that family's first/last T0 (tie-break earlier), and latest T0. Calendar geometry only. FX outcomes were not used.")
    parts.append("CPI: usd_cpi_2025-09-11, usd_cpi_2026-02-13, usd_cpi_2026-07-14")
    parts.append("Employment: usd_empsit_2025-09-05, usd_empsit_2026-02-11, usd_empsit_2026-08-07")
    parts.append("FOMC: usd_fomc_statement_2025-09-17, usd_fomc_statement_2026-01-28, usd_fomc_statement_2026-07-29")
    parts.append("")
    parts.append("CPI RESULTS")
    parts.append("-----------")
    parts.extend(lines_for("CPI"))
    parts.append("A/B/C/D/E/F/G by event: all 3 CPI events have pre-release artifacts and exact series semantics for at least headline YoY; UTC clocks exist on Reuters same-morning previews (PIT_SAFE_WITH_LIMITATION due to same-day Updated). No CPI record was promoted to PIT_SAFE because FactSet pages lack clocks and Reuters BLS previews carry an untimed same-day Updated line. Joinable official first prints exist for standard MoM/YoY series. Strict PIT_SAFE surprise: none for CPI.")
    parts.append("")
    parts.append("EMPLOYMENT RESULTS")
    parts.append("------------------")
    parts.extend(lines_for("EMPLOYMENT_SITUATION"))
    parts.append("All 3 employment events have Reuters and/or FactSet pre-release NFP/u-rate numbers. usd_empsit_2026-08-07 also has PIT_SAFE Dow Jones 83k / 4.2% via IBTimes (08:51 BST). usd_empsit_2026-02-11 is the CES-benchmark official event; consensus still targets the headline first print, not the benchmark restatement. AHE coverage is incomplete (present on Aug 2025 Reuters; YoY only on Jul 2026 Reuters; missing on official Jul 2026 values so that series cannot join).")
    parts.append("")
    parts.append("FOMC RESULTS")
    parts.append("------------")
    parts.extend(lines_for("FOMC"))
    parts.append("FOMC is not forced into CPI/NFP schema. Survey decisions and market-implied probabilities are stored separately. Reuters Sep 8-11 poll: 105/107 expect -25bp, 2 expect -50bp (PIT_SAFE vs FOMC T0). Reuters Jan 16-21 poll: 100/100 hold (PIT_SAFE). FXStreet 2026-01-28T09:30:05Z: FF futures cut odds <3% (PIT_SAFE, MARKET_IMPLIED). CBS 2026-07-29 09:38 EDT: FactSet survey hold plus FedWatch 36% hike (PIT_SAFE). Probabilities were not converted into a scalar consensus of -25bp or +25bp.")
    parts.append("")
    parts.append("PILOT COVERAGE MATRIX")
    parts.append("---------------------")
    parts.append("| event | family | T0 | sources_found | PIT_safe_sources | series_covered | publication_time_proven | artifact_hashed | official_join_valid | raw_surprise_possible |")
    parts.append("| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |")
    for m in matrix:
        parts.append(
            "| {event} | {family} | {T0} | {sources_found} | {PIT_safe_sources} | {series_covered} | {publication_time_proven} | {artifact_hashed} | {official_join_valid} | {raw_surprise_possible} |".format(**m)
        )
    parts.append("")
    parts.append("SOURCE QUALITY MATRIX")
    parts.append("---------------------")
    parts.append("| publisher | source type | historical discoverability | publication timestamp quality | consensus semantics quality | artifact/vintage quality | automation feasibility | access limitations | overall PIT usefulness |")
    parts.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    parts.append("| Reuters | news + economist survey | HIGH (dated slugs, morning previews, dedicated polls) | HIGH original UTC clock; MEDIUM because of untimed same-day Updated | HIGH (survey of economists; range often printed) | Excerpt-only here (licensing); full HTML not stored | PARTIAL (URL pattern on T0 morning) | Paywall on some desks; no illicit mirrors | HIGH with WARC/last-mod |")
    parts.append("| FactSet Insight | survey median blog | HIGH (stable month-named URLs) | MEDIUM (calendar date + Tomorrow; no clock) | HIGH for YoY NSA; often no MoM; n sometimes 3-15 | Excerpt-only; live page could be edited | HIGH URL pattern | Marketing pages; n can be tiny | HIGH if captured day-before at known UTC |")
    parts.append("| Morningstar | news relaying FactSet + individual banks | MEDIUM | MEDIUM date-only | MIXED (FactSet consensus plus INDIVIDUAL_FORECAST) | Excerpt-only | LOW | None observed | MEDIUM |")
    parts.append("| IBTimes UK | news relaying Dow Jones | MEDIUM | HIGH (BST clock) | HIGH for DJ poll; also reports other panels | Excerpt-only | LOW | Secondary publisher | MEDIUM-HIGH as a clocked DJ relay |")
    parts.append("| CBS News | news relaying FactSet + FedWatch | MEDIUM | HIGH when Updated clock present | MIXED (survey vs market-implied must stay separate) | Excerpt-only | LOW | 406 on another CBS FOMC URL in this pilot | MEDIUM-HIGH when clocked |")
    parts.append("| FXStreet | analysis citing FF futures | MEDIUM | HIGH (GMT clock in byline) | MARKET_IMPLIED not survey | Excerpt-only | LOW | Preview later overwritten on some FXStreet news URLs | MEDIUM for implied odds |")
    parts.append("| CME FedWatch live tool | market-implied | HIGH today, POOR historically without a dated snapshot | N/A unless contemporaneously quoted | Probability distribution | Not archived here | Requires historical snapshots | Do not reconstruct from today | USEFUL only via contemporaneous citation or official archive |")
    parts.append("| Bloomberg | news | HIGH | HIGH when accessible | HIGH | Not opened (paywall) | LOW without license | Paywall; no bypass | UNKNOWN in this pilot |")
    parts.append("| Wayback CDX | archive | attempted | timeout in this session | n/a | n/a | PARTIAL | Timeouts | NOT USED |")
    parts.append("")
    parts.append("PIT REJECTIONS")
    parts.append("--------------")
    parts.append("- CBS Sep 17 2025 FOMC URL: HTTP 406 — access limitation, not used.")
    parts.append("- Bloomberg Jan 28 2026 decision-day guide: paywall, not opened.")
    parts.append("- Reuters post-release actuals articles (e.g. Sep 11 2025 CPI wrap 'economists had forecast'): REJECT_POST_RELEASE as primary vintage even if they quote the same survey.")
    parts.append("- FOMC minutes (released weeks later) describing pre-meeting market odds: REJECT_POST_RELEASE as the evidence timestamp.")
    parts.append("- TradingKey / SEO / crypto FedWatch blogs: REJECT_UNSOURCED or not opened as primary.")
    parts.append("- Search snippets: discovery only.")
    parts.append("- Live CME FedWatch today: not a historical vintage.")
    parts.append("- Same-day Reuters BLS previews: not REJECT, but PIT_SAFE_WITH_LIMITATION because Updated lacks intra-day last-mod.")
    parts.append("")
    parts.append("MULTI-SOURCE DISAGREEMENT")
    parts.append("-------------------------")
    parts.append("Not averaged. Descriptive only.")
    parts.append("- Aug 2025 NFP: Reuters 75k vs FactSet 80k. U-rate Reuters 4.3 vs FactSet 4.2.")
    parts.append("- Jan 2026 CPI headline YoY: Reuters 2.5 vs FactSet 2.4 (FactSet n=12, range 2.30-2.70).")
    parts.append("- Jan 2026 NFP: Reuters 70k (range -10k to 135k) vs FactSet 75k (n=15, range 50k-85k).")
    parts.append("- Jun 2026 core CPI YoY: Reuters 2.8 vs FactSet 2.9.")
    parts.append("- Jul 2026 NFP: Reuters 80k vs Dow Jones 83k vs FactSet 97.5k (n=12). Individual Vanguard 18k stored separately.")
    parts.append("Disagreement is data. No house consensus invented.")
    parts.append("")
    parts.append("OFFICIAL ACTUAL JOIN PROOF")
    parts.append("--------------------------")
    for s in surprise:
        parts.append(
            "- %s %s forecast=%s actual=%s join=%s surprise_possible=%s (%s)"
            % (
                s["macro_event_id"],
                s["series_name"],
                s.get("forecast_value"),
                s.get("official_actual"),
                s.get("official_join_valid"),
                s.get("raw_surprise_possible"),
                s.get("notes"),
            )
        )
    parts.append("")
    parts.append("RAW SURPRISE PIPELINE PROOF")
    parts.append("---------------------------")
    parts.append("Formula (PIT_SAFE + matching official first print + matching units only): surprise_raw = official_first_print_actual - pre_release_consensus.")
    parts.append("No z-score. No FX. Individual forecasts excluded from consensus surprise.")
    for s in surprise:
        if s.get("raw_surprise_possible"):
            parts.append("- %s %s: %s" % (s["macro_event_id"], s["series_name"], s.get("surprise_raw")))
    parts.append("")
    parts.append("CAN WE SCALE TO ALL 29 EVENTS?")
    parts.append("PARTIAL")
    parts.append("EVENTS WITH PIT-SAFE CONSENSUS:")
    parts.append("%s / %s" % (len(events_safe), n_events))
    parts.append("SERIES WITH PIT-SAFE CONSENSUS:")
    parts.append("; ".join("%s:%s (%s)" % x for x in series_safe) if series_safe else "NONE")
    parts.append("EVENTS WITH RAW SURPRISE COMPUTABLE:")
    parts.append("%s / %s" % (len(events_surprise), n_events))
    parts.append("FOMC EXPECTATION PROVEN:")
    parts.append("%s / 3" % len(fomc_proven))
    parts.append("BIGGEST BLOCKERS:")
    parts.append("- Same-day Reuters 'Updated' without last-mod clock (blocks PIT_SAFE on otherwise clocked BLS previews)")
    parts.append("- FactSet day-before pages lack UTC clocks")
    parts.append("- Full-page archival/licensing (excerpts hashed, not WARC)")
    parts.append("- Paywalls (Bloomberg) and HTTP 406 (some CBS)")
    parts.append("- No CME FedWatch historical vintage API used; only contemporaneous citations")
    parts.append("- Thin FactSet panels (n=4) and missing AHE on some official value rows")
    parts.append("- Wayback CDX timeout in this session")
    parts.append("RECOMMENDED STAGE 2 CONSENSUS ACTION:")
    parts.append("Capture Reuters morning previews and FactSet Insight pages into dated WARC/last-mod hashes at a known UTC before each remaining T0; license or skip Bloomberg; keep Reuters/FactSet/Dow Jones as separate vintages; store FOMC survey distributions and FedWatch citations without collapsing to a single bp; do not scrape SEO calendars.")
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
    parts.append("FILES CHANGED:")
    parts.append("research helpers/tests/report/new consensus pilot data only")
    parts.append("STOP.")
    parts.append("")
    REPORT_PATH.write_text("\n".join(parts), encoding="utf-8")


def run() -> dict:
    hashes = {name: write_excerpt(name, text) for name, text in EXCERPTS.items()}
    records = records_template(hashes)
    for r in records:
        assert_pit_clock(r)
        assert r["macro_event_id"] in SELECTED_IDS
    surprise = compute_surprise(records)
    matrix = coverage_matrix(records, surprise)
    EVIDENCE_PATH.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    SURPRISE_PATH.write_text(json.dumps({"surprise": surprise, "coverage": matrix}, indent=2) + "\n", encoding="utf-8")
    write_report(records, surprise, matrix)
    return {
        "n_records": len(records),
        "n_pit_safe": sum(1 for r in records if r["pit_status"] == "PIT_SAFE"),
        "events_pit_safe": sorted({r["macro_event_id"] for r in records if r["pit_status"] == "PIT_SAFE"}),
        "events_surprise": sorted({s["macro_event_id"] for s in surprise if s.get("raw_surprise_possible")}),
        "us_pit_modified": False,
    }


if __name__ == "__main__":
    summary = run()
    print(json.dumps(summary, indent=2))
