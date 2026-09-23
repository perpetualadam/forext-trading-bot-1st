"""Emit Stage 2A six-event public-consensus pilot files. Research only."""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RETRIEVED = "2026-09-24T00:30:00Z"

SCHEMA = {
    "dataset": "macro_consensus_pilot_2025",
    "stage": "2A_PILOT",
    "purpose": "Test whether a pre-release economist consensus can be recovered from contemporaneous public sources without look-ahead.",
    "first_print_authority": "data/research/macro_first_print/normalized/events_2025.csv",
    "econoday_status": "NOT_INGESTED",
    "do_not": [
        "replace Stage 1 first-print actuals",
        "average conflicting providers",
        "use today's calendar Forecast field",
        "backtest FX or create trade rules",
    ],
    "fields": {
        "record_id": "stable observation id",
        "event_id": "Stage 1 event_id",
        "indicator": "CPI_HEADLINE_MOM | CPI_HEADLINE_YOY | CPI_CORE_MOM | CPI_CORE_YOY | NFP_PAYROLL_CHANGE | UNEMPLOYMENT_RATE | AHE_MOM | AHE_YOY",
        "consensus_value": "numeric or null",
        "unit": "percent | persons",
        "consensus_type": "SURVEY_MEDIAN | SURVEY_MEAN | SURVEY_OTHER | SINGLE_FORECAST | UNKNOWN",
        "survey_provider": "FactSet | Reuters | FinancialJuice | UNKNOWN | none",
        "publisher": "outlet that published the page",
        "source_url": "page opened for this record",
        "publication_time_original": "as printed on the source",
        "publication_time_utc": "normalized clock or null if date-only",
        "official_release_time_utc": "Stage 1 scheduled_time_utc",
        "lead_time_minutes": "release minus publication; null if no clock",
        "source_title": "page title",
        "source_evidence_excerpt": "short excerpt only",
        "retrieved_at": "when the page was opened for this pilot",
        "validation_status": "VERIFIED_PRE_RELEASE | PRE_RELEASE_DATE_ONLY | SINGLE_FORECAST_ONLY | POST_RELEASE_ONLY | CONFLICTING_SOURCES | NOT_FOUND",
        "sample_n": "survey n if disclosed",
        "range_low": "low estimate if disclosed",
        "range_high": "high estimate if disclosed",
        "qa_official_first_print": "Stage 1 first print for this indicator; not replaced",
        "qa_arithmetic_difference": "first_print minus consensus; QA only",
        "econoday_consensus_value": "reserved; null until Econoday sample arrives",
        "notes": "provenance / conflict / quality flags",
    },
}

EVENTS = [
    {
        "event_id": "CPI_2024-12_2025-01-15",
        "event_type": "CPI",
        "reference_period": "2024-12",
        "official_release_time_utc": "2025-01-15T13:30:00Z",
        "stage1_status": "VERIFIED_FIRST_PRINT",
        "first_print": {
            "CPI_HEADLINE_MOM": 0.4,
            "CPI_HEADLINE_YOY": 2.9,
            "CPI_CORE_MOM": 0.2,
            "CPI_CORE_YOY": 3.2,
        },
    },
    {
        "event_id": "CPI_2025-04_2025-05-13",
        "event_type": "CPI",
        "reference_period": "2025-04",
        "official_release_time_utc": "2025-05-13T12:30:00Z",
        "stage1_status": "VERIFIED_FIRST_PRINT",
        "first_print": {
            "CPI_HEADLINE_MOM": 0.2,
            "CPI_HEADLINE_YOY": 2.3,
            "CPI_CORE_MOM": 0.2,
            "CPI_CORE_YOY": 2.8,
        },
    },
    {
        "event_id": "CPI_2025-08_2025-09-11",
        "event_type": "CPI",
        "reference_period": "2025-08",
        "official_release_time_utc": "2025-09-11T12:30:00Z",
        "stage1_status": "VERIFIED_FIRST_PRINT",
        "first_print": {
            "CPI_HEADLINE_MOM": 0.4,
            "CPI_HEADLINE_YOY": 2.9,
            "CPI_CORE_MOM": 0.3,
            "CPI_CORE_YOY": 3.1,
        },
    },
    {
        "event_id": "EMPLOYMENT_SITUATION_2024-12_2025-01-10",
        "event_type": "EMPLOYMENT_SITUATION",
        "reference_period": "2024-12",
        "official_release_time_utc": "2025-01-10T13:30:00Z",
        "stage1_status": "VERIFIED_FIRST_PRINT",
        "first_print": {
            "NFP_PAYROLL_CHANGE": 256000,
            "UNEMPLOYMENT_RATE": 4.1,
            "AHE_MOM": 0.3,
            "AHE_YOY": 3.9,
        },
    },
    {
        "event_id": "EMPLOYMENT_SITUATION_2025-05_2025-06-06",
        "event_type": "EMPLOYMENT_SITUATION",
        "reference_period": "2025-05",
        "official_release_time_utc": "2025-06-06T12:30:00Z",
        "stage1_status": "VERIFIED_FIRST_PRINT",
        "first_print": {
            "NFP_PAYROLL_CHANGE": 139000,
            "UNEMPLOYMENT_RATE": 4.2,
            "AHE_MOM": 0.4,
            "AHE_YOY": 3.9,
        },
    },
    {
        "event_id": "EMPLOYMENT_SITUATION_2025-09_2025-11-20",
        "event_type": "EMPLOYMENT_SITUATION",
        "reference_period": "2025-09",
        "official_release_time_utc": "2025-11-20T13:30:00Z",
        "stage1_status": "VERIFIED_FIRST_PRINT",
        "first_print": {
            "NFP_PAYROLL_CHANGE": 119000,
            "UNEMPLOYMENT_RATE": 4.4,
            "AHE_MOM": 0.2,
            "AHE_YOY": 3.8,
        },
    },
]

FIRST = {e["event_id"]: e for e in EVENTS}
UNIT = {
    "CPI_HEADLINE_MOM": "percent",
    "CPI_HEADLINE_YOY": "percent",
    "CPI_CORE_MOM": "percent",
    "CPI_CORE_YOY": "percent",
    "NFP_PAYROLL_CHANGE": "persons",
    "UNEMPLOYMENT_RATE": "percent",
    "AHE_MOM": "percent",
    "AHE_YOY": "percent",
}


def rec(
    record_id: str,
    event_id: str,
    indicator: str,
    consensus_value,
    consensus_type: str,
    survey_provider: str,
    publisher: str,
    source_url: str,
    publication_time_original: str,
    publication_time_utc,
    lead_time_minutes,
    source_title: str,
    source_evidence_excerpt: str,
    validation_status: str,
    notes: str,
    sample_n=None,
    range_low=None,
    range_high=None,
):
    ev = FIRST[event_id]
    official = ev["first_print"].get(indicator)
    diff = None
    if consensus_value is not None and official is not None:
        diff = round(official - consensus_value, 6)
        if indicator == "NFP_PAYROLL_CHANGE":
            diff = int(official - consensus_value)
    return {
        "record_id": record_id,
        "event_id": event_id,
        "event_type": ev["event_type"],
        "reference_period": ev["reference_period"],
        "indicator": indicator,
        "consensus_value": consensus_value,
        "unit": UNIT[indicator],
        "consensus_type": consensus_type,
        "survey_provider": survey_provider,
        "publisher": publisher,
        "source_url": source_url,
        "publication_time_original": publication_time_original,
        "publication_time_utc": publication_time_utc,
        "official_release_time_utc": ev["official_release_time_utc"],
        "lead_time_minutes": lead_time_minutes,
        "source_title": source_title,
        "source_evidence_excerpt": source_evidence_excerpt,
        "retrieved_at": RETRIEVED,
        "validation_status": validation_status,
        "sample_n": sample_n,
        "range_low": range_low,
        "range_high": range_high,
        "qa_official_first_print": official,
        "qa_arithmetic_difference": diff,
        "econoday_consensus_value": None,
        "notes": notes,
    }


OBS = []

# --- CPI Dec 2024 / 2025-01-15 ---
CR = "https://www.calculatedriskblog.com/2025/01/cpi-preview.html"
OBS += [
    rec("CPI202412-CR-HMOM", "CPI_2024-12_2025-01-15", "CPI_HEADLINE_MOM", 0.3, "UNKNOWN", "UNKNOWN", "Calculated Risk", CR, "1/14/2025 08:12:00 AM", "2025-01-14T13:12:00Z", 1458, "CPI Preview", "The consensus is for 0.3% increase in CPI, and a 0.2% increase in core CPI.", "VERIFIED_PRE_RELEASE", "Clock assumed America/New_York EST. Provider not named. Conflicts with FactSet YoY 2.8 vs this source YoY 2.9."),
    rec("CPI202412-CR-HYOY", "CPI_2024-12_2025-01-15", "CPI_HEADLINE_YOY", 2.9, "UNKNOWN", "UNKNOWN", "Calculated Risk", CR, "1/14/2025 08:12:00 AM", "2025-01-14T13:12:00Z", 1458, "CPI Preview", "The consensus is for CPI to be up 2.9% year-over-year and core CPI to be up 3.3% YoY.", "VERIFIED_PRE_RELEASE", "Clock assumed America/New_York EST. Provider not named. Conflicts with FactSet headline YoY 2.8."),
    rec("CPI202412-CR-CMOM", "CPI_2024-12_2025-01-15", "CPI_CORE_MOM", 0.2, "UNKNOWN", "UNKNOWN", "Calculated Risk", CR, "1/14/2025 08:12:00 AM", "2025-01-14T13:12:00Z", 1458, "CPI Preview", "The consensus is for 0.3% increase in CPI, and a 0.2% increase in core CPI.", "VERIFIED_PRE_RELEASE", "Clock assumed America/New_York EST. Provider not named."),
    rec("CPI202412-CR-CYOY", "CPI_2024-12_2025-01-15", "CPI_CORE_YOY", 3.3, "UNKNOWN", "UNKNOWN", "Calculated Risk", CR, "1/14/2025 08:12:00 AM", "2025-01-14T13:12:00Z", 1458, "CPI Preview", "The consensus is for CPI to be up 2.9% year-over-year and core CPI to be up 3.3% YoY.", "VERIFIED_PRE_RELEASE", "Clock assumed America/New_York EST. Provider not named."),
]
FS_DEC_CPI = "https://insight.factset.com/consumer-price-index-cpi-for-december-2024-is-projected-to-rise-2.8-year-over-year"
OBS += [
    rec("CPI202412-FS-HYOY", "CPI_2024-12_2025-01-15", "CPI_HEADLINE_YOY", 2.8, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_DEC_CPI, "January 14, 2025", None, None, "Consumer Price Index (CPI) for December 2024 is Projected to Rise 2.8% Year-Over-Year", "The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of December 2024 is 2.8%.", "PRE_RELEASE_DATE_ONLY", "n=8; range 2.80-2.93. Page says Tomorrow (January 15). No clock. Conflicts with FinancialJuice/Calculated Risk 2.9.", sample_n=8, range_low=2.80, range_high=2.93),
    rec("CPI202412-FS-CYOY", "CPI_2024-12_2025-01-15", "CPI_CORE_YOY", 3.3, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_DEC_CPI, "January 14, 2025", None, None, "Consumer Price Index (CPI) for December 2024 is Projected to Rise 2.8% Year-Over-Year", "The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 3.3%.", "PRE_RELEASE_DATE_ONLY", "No MoM fields on this FactSet page. Date only."),
]
MS_DEC = "https://www.morningstar.com/economy/december-cpi-forecasts-predict-stalled-progress-inflation"
OBS += [
    rec("CPI202412-MSFS-HMOM", "CPI_2024-12_2025-01-15", "CPI_HEADLINE_MOM", 0.3, "SURVEY_OTHER", "FactSet", "Morningstar", MS_DEC, "Jan 13, 2025", None, None, "December CPI Forecasts Predict Stalled Progress on Inflation", "Economists predict that the Consumer Price Index rose 0.3% on a monthly basis in December, according to FactSet's consensus estimates.", "PRE_RELEASE_DATE_ONLY", "Morningstar cites a fuller FactSet consensus than the public Insight YoY-only page."),
    rec("CPI202412-MSFS-HYOY", "CPI_2024-12_2025-01-15", "CPI_HEADLINE_YOY", 2.8, "SURVEY_OTHER", "FactSet", "Morningstar", MS_DEC, "Jan 13, 2025", None, None, "December CPI Forecasts Predict Stalled Progress on Inflation", "That would mean the annual inflation rate rose slightly to 2.8% from 2.7% in November.", "PRE_RELEASE_DATE_ONLY", "Matches FactSet Insight YoY 2.8; conflicts with FinancialJuice/Calculated Risk 2.9."),
    rec("CPI202412-MSFS-CMOM", "CPI_2024-12_2025-01-15", "CPI_CORE_MOM", 0.2, "SURVEY_OTHER", "FactSet", "Morningstar", MS_DEC, "Jan 13, 2025", None, None, "December CPI Forecasts Predict Stalled Progress on Inflation", "Economists expect the core measure of inflation (which excludes volatile food and energy prices) to rise 0.2% in December, which would keep the annual rate steady at 3.3%.", "PRE_RELEASE_DATE_ONLY", "Date only. FactSet via Morningstar."),
    rec("CPI202412-MSFS-CYOY", "CPI_2024-12_2025-01-15", "CPI_CORE_YOY", 3.3, "SURVEY_OTHER", "FactSet", "Morningstar", MS_DEC, "Jan 13, 2025", None, None, "December CPI Forecasts Predict Stalled Progress on Inflation", "keep the annual rate steady at 3.3%.", "PRE_RELEASE_DATE_ONLY", "Date only. FactSet via Morningstar."),
]
FJ_DEC = "https://features.financialjuice.com/2025/01/13/us-cpi-prep-12/"
OBS += [
    rec("CPI202412-FJ-HMOM", "CPI_2024-12_2025-01-15", "CPI_HEADLINE_MOM", 0.3, "SURVEY_MEDIAN", "UNKNOWN", "FinancialJuice", FJ_DEC, "January 13, 2025", None, None, "US CPI Prep", "Headline US CPI MoM, the median expectation is 0.3%, from the prior 0.3%. The highest estimate is 0.4%, and the lowest is 0.2%.", "PRE_RELEASE_DATE_ONLY", "Survey of 38 economists; poll vendor not named.", sample_n=38, range_low=0.2, range_high=0.4),
    rec("CPI202412-FJ-HYOY", "CPI_2024-12_2025-01-15", "CPI_HEADLINE_YOY", 2.9, "SURVEY_MEDIAN", "UNKNOWN", "FinancialJuice", FJ_DEC, "January 13, 2025", None, None, "US CPI Prep", "The median expectation for headline US CPI YoY is 2.9%, up from the prior 2.7%. According to a survey of 38 qualified economists, the highest estimate is 3%, and the lowest is 2.6%.", "PRE_RELEASE_DATE_ONLY", "Conflicts with FactSet/Morningstar 2.8.", sample_n=38, range_low=2.6, range_high=3.0),
    rec("CPI202412-FJ-CMOM", "CPI_2024-12_2025-01-15", "CPI_CORE_MOM", 0.2, "SURVEY_MEDIAN", "UNKNOWN", "FinancialJuice", FJ_DEC, "January 13, 2025", None, None, "US CPI Prep", "Core CPI MoM has a median forecast of 0.2%, the prior was 0.3%. The highest estimate is 0.3%, the lowest was 0.2%.", "PRE_RELEASE_DATE_ONLY", "Survey of 38; vendor unnamed.", sample_n=38, range_low=0.2, range_high=0.3),
    rec("CPI202412-FJ-CYOY", "CPI_2024-12_2025-01-15", "CPI_CORE_YOY", 3.3, "SURVEY_MEDIAN", "UNKNOWN", "FinancialJuice", FJ_DEC, "January 13, 2025", None, None, "US CPI Prep", "Core CPI YoY has a median expectation of 3.3%, expected to remain unchanged from the prior 3.3%.", "PRE_RELEASE_DATE_ONLY", "Survey of 38; vendor unnamed.", sample_n=38),
]
OBS.append(
    rec(
        "CPI202412-WF-HMOM",
        "CPI_2024-12_2025-01-15",
        "CPI_HEADLINE_MOM",
        0.4,
        "SINGLE_FORECAST",
        "none",
        "FinancialJuice",
        FJ_DEC,
        "January 13, 2025",
        None,
        None,
        "US CPI Prep",
        "Wells Fargo: forecast of a 0.4% monthly gain in the Consumer Price Index in December.",
        "SINGLE_FORECAST_ONLY",
        "House forecast, not a survey consensus. Included as a contrast case.",
    )
)

# --- CPI Apr 2025 / 2025-05-13 ---
FJ_APR = "https://features.financialjuice.com/2025/05/12/us-cpi-prep-15/"
OBS += [
    rec("CPI202504-FJ-HMOM", "CPI_2025-04_2025-05-13", "CPI_HEADLINE_MOM", 0.3, "UNKNOWN", "UNKNOWN", "FinancialJuice", FJ_APR, "May 12, 2025", None, None, "US CPI Prep", "MoM - Forecast: 0.3% | Prior: -0.1% | Range: 0.6% / 0%", "PRE_RELEASE_DATE_ONLY", "Forecast table; poll vendor and n not disclosed. Date only.", range_low=0.0, range_high=0.6),
    rec("CPI202504-FJ-HYOY", "CPI_2025-04_2025-05-13", "CPI_HEADLINE_YOY", 2.4, "UNKNOWN", "UNKNOWN", "FinancialJuice", FJ_APR, "May 12, 2025", None, None, "US CPI Prep", "YoY - Forecast: 2.4% | Prior: 2.4% | Range: 2.5% / 2.2%", "PRE_RELEASE_DATE_ONLY", "Forecast table; poll vendor and n not disclosed.", range_low=2.2, range_high=2.5),
    rec("CPI202504-FJ-CMOM", "CPI_2025-04_2025-05-13", "CPI_CORE_MOM", 0.3, "UNKNOWN", "UNKNOWN", "FinancialJuice", FJ_APR, "May 12, 2025", None, None, "US CPI Prep", "Core MoM - Forecast: 0.3% | Prior: 0.1% | Range: 0.6% / 0.1%", "PRE_RELEASE_DATE_ONLY", "Forecast table; poll vendor and n not disclosed.", range_low=0.1, range_high=0.6),
    rec("CPI202504-FJ-CYOY", "CPI_2025-04_2025-05-13", "CPI_CORE_YOY", 2.8, "UNKNOWN", "UNKNOWN", "FinancialJuice", FJ_APR, "May 12, 2025", None, None, "US CPI Prep", "Core YoY - Forecast: 2.8% | Prior: 2.8% | Range: 3% / 2.7%", "PRE_RELEASE_DATE_ONLY", "Forecast table; poll vendor and n not disclosed.", range_low=2.7, range_high=3.0),
    rec("CPI202504-WF-HMOM", "CPI_2025-04_2025-05-13", "CPI_HEADLINE_MOM", 0.2, "SINGLE_FORECAST", "none", "FinancialJuice", FJ_APR, "May 12, 2025", None, None, "US CPI Prep", "Wells Fargo: we look for the headline CPI to rise 0.2% in April, leading the year-ago rate to dip to a four-year low of 2.3%.", "SINGLE_FORECAST_ONLY", "House forecast. Differs from the same page Forecast table 0.3% MoM."),
    rec("CPI202504-FS-HYOY", "CPI_2025-04_2025-05-13", "CPI_HEADLINE_YOY", None, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", "https://insight.factset.com/", "not found", None, None, "April 2025 CPI FactSet preview", "", "NOT_FOUND", "No matching public FactSet Insight CPI preview URL was recovered for the April 2025 print. Guessed path 404."),
]

# --- CPI Aug 2025 / 2025-09-11 ---
FS_AUG = "https://insight.factset.com/consumer-price-index-cpi-for-august-2025-is-projected-to-rise-2.9-year-over-year"
MS_AUG = "https://www.morningstar.com/economy/august-cpi-report-forecasts-point-sticky-inflation-tariff-pressures"
REU_PPI = "https://www.reuters.com/business/cooler-us-producer-inflation-hints-softening-demand-2025-09-10/"
OBS += [
    rec("CPI202508-REU-HMOM", "CPI_2025-08_2025-09-11", "CPI_HEADLINE_MOM", 0.3, "SURVEY_MEDIAN", "Reuters", "Reuters", REU_PPI, "WASHINGTON, Sept 10 (Reuters)", None, None, "Cooler US producer inflation hints at softening demand", "A Reuters survey of economists forecast the Consumer Price Index increased 0.3% last month after climbing 0.2% in July.", "PRE_RELEASE_DATE_ONLY", "PPI-day article; body reports PPI actuals and still forecasts Thursday CPI (no 0.4 print). Date only; no clock. Stronger than a generic date page but not VERIFIED_PRE_RELEASE."),
    rec("CPI202508-REU-HYOY", "CPI_2025-08_2025-09-11", "CPI_HEADLINE_YOY", 2.9, "SURVEY_MEDIAN", "Reuters", "Reuters", REU_PPI, "WASHINGTON, Sept 10 (Reuters)", None, None, "Cooler US producer inflation hints at softening demand", "Consumer prices are expected to have advanced 2.9% on a year-over-year basis in August after rising 2.7% in July.", "PRE_RELEASE_DATE_ONLY", "Reuters survey; date-only dateline Sept 10; article does not contain the later 0.4 MoM print."),
    rec("CPI202508-REU-CMOM", "CPI_2025-08_2025-09-11", "CPI_CORE_MOM", 0.3, "SURVEY_MEDIAN", "Reuters", "Reuters", REU_PPI, "WASHINGTON, Sept 10 (Reuters)", None, None, "Cooler US producer inflation hints at softening demand", "Core CPI inflation is predicted to have increased 0.3% for a second straight month.", "PRE_RELEASE_DATE_ONLY", "Reuters survey; date-only."),
    rec("CPI202508-REU-CYOY", "CPI_2025-08_2025-09-11", "CPI_CORE_YOY", 3.1, "SURVEY_MEDIAN", "Reuters", "Reuters", REU_PPI, "WASHINGTON, Sept 10 (Reuters)", None, None, "Cooler US producer inflation hints at softening demand", "That reading would keep the annual increase in core CPI inflation at 3.1%.", "PRE_RELEASE_DATE_ONLY", "Reuters survey; date-only."),
    rec("CPI202508-FS-HYOY", "CPI_2025-08_2025-09-11", "CPI_HEADLINE_YOY", 2.9, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_AUG, "September 10, 2025", None, None, "Consumer Price Index (CPI) for August 2025 is Projected to Rise 2.9% Year-Over-Year", "The median estimate (year-over-year, not seasonally adjusted) for the consumer price index (CPI) for the month of August 2025 is 2.9%.", "PRE_RELEASE_DATE_ONLY", "Page says Tomorrow (September 11). No MoM on this page. Agrees with Reuters YoY."),
    rec("CPI202508-FS-CYOY", "CPI_2025-08_2025-09-11", "CPI_CORE_YOY", 3.1, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_AUG, "September 10, 2025", None, None, "Consumer Price Index (CPI) for August 2025 is Projected to Rise 2.9% Year-Over-Year", "The median estimate (year-over-year, not seasonally adjusted) for the consumer price index excluding food & energy (Core CPI) is 3.1%.", "PRE_RELEASE_DATE_ONLY", "No sample n disclosed on this page."),
    rec("CPI202508-MSFS-HMOM", "CPI_2025-08_2025-09-11", "CPI_HEADLINE_MOM", 0.3, "SURVEY_OTHER", "FactSet", "Morningstar", MS_AUG, "Sep 9, 2025", None, None, "August CPI Report Forecasts Point to Sticky Inflation and Tariff Pressures", "Economists expect the CPI to rise 0.3% on a monthly basis in August and 2.9% year over year, according to the latest consensus estimates from FactSet.", "PRE_RELEASE_DATE_ONLY", "Date only. FactSet via Morningstar. Agrees with Reuters MoM 0.3."),
    rec("CPI202508-MSFS-HYOY", "CPI_2025-08_2025-09-11", "CPI_HEADLINE_YOY", 2.9, "SURVEY_OTHER", "FactSet", "Morningstar", MS_AUG, "Sep 9, 2025", None, None, "August CPI Report Forecasts Point to Sticky Inflation and Tariff Pressures", "Economists expect the CPI to rise 0.3% on a monthly basis in August and 2.9% year over year, according to the latest consensus estimates from FactSet.", "PRE_RELEASE_DATE_ONLY", "Agrees with FactSet Insight and Reuters YoY."),
    rec("CPI202508-MSFS-CMOM", "CPI_2025-08_2025-09-11", "CPI_CORE_MOM", 0.3, "SURVEY_OTHER", "FactSet", "Morningstar", MS_AUG, "Sep 9, 2025", None, None, "August CPI Report Forecasts Point to Sticky Inflation and Tariff Pressures", "Core CPI ... is also expected to come in at 0.3% on a monthly basis for August and 3.1% year over year.", "PRE_RELEASE_DATE_ONLY", "Date only. FactSet via Morningstar."),
    rec("CPI202508-MSFS-CYOY", "CPI_2025-08_2025-09-11", "CPI_CORE_YOY", 3.1, "SURVEY_OTHER", "FactSet", "Morningstar", MS_AUG, "Sep 9, 2025", None, None, "August CPI Report Forecasts Point to Sticky Inflation and Tariff Pressures", "Core CPI ... 3.1% year over year.", "PRE_RELEASE_DATE_ONLY", "Date only. FactSet via Morningstar."),
    rec("CPI202508-AMP-HMOM", "CPI_2025-08_2025-09-11", "CPI_HEADLINE_MOM", 0.4, "SINGLE_FORECAST", "none", "Morningstar", MS_AUG, "Sep 9, 2025", None, None, "August CPI Report Forecasts Point to Sticky Inflation and Tariff Pressures", "Russell Price, chief economist at Ameriprise, expects a hotter-than-consensus 0.4% increase on a monthly basis.", "SINGLE_FORECAST_ONLY", "House forecast explicitly labelled hotter-than-consensus."),
]

# --- EMP Dec 2024 / 2025-01-10 ---
FS_DEC_NFP = "https://insight.factset.com/u.s.-jobs-are-projected-to-rise-by-153000-for-december-2024"
FJ_NFP = "https://features.financialjuice.com/2025/01/07/us-nfp-prep/"
FJ_MJ = "https://features.financialjuice.com/2025/01/10/morning-juice-us-session-prep-243/"
OBS += [
    rec("EMP202412-FS-NFP", "EMPLOYMENT_SITUATION_2024-12_2025-01-10", "NFP_PAYROLL_CHANGE", 153000, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_DEC_NFP, "January 9, 2025", None, None, "U.S. Jobs Are Projected to Rise by 153,000 for December 2024", "The median estimate for total nonfarm payroll employment for the month of December 2024 is 153,000.", "PRE_RELEASE_DATE_ONLY", "n=19; range 125000-200000. Page says Tomorrow BLS will release. Conflicts with FinancialJuice 160k/165k.", sample_n=19, range_low=125000, range_high=200000),
    rec("EMP202412-FS-UE", "EMPLOYMENT_SITUATION_2024-12_2025-01-10", "UNEMPLOYMENT_RATE", 4.2, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_DEC_NFP, "January 9, 2025", None, None, "U.S. Jobs Are Projected to Rise by 153,000 for December 2024", "The median estimate for the unemployment rate for the month of December 2024 is 4.2%.", "PRE_RELEASE_DATE_ONLY", "n=17; range 4.1-4.3.", sample_n=17, range_low=4.1, range_high=4.3),
    rec("EMP202412-FJ-NFP", "EMPLOYMENT_SITUATION_2024-12_2025-01-10", "NFP_PAYROLL_CHANGE", 160000, "SURVEY_MEDIAN", "UNKNOWN", "FinancialJuice", FJ_NFP, "January 7, 2025", None, None, "US NFP Prep", "the median expectation is for it to move down to 160K from 227K. According to a survey of 459 qualified economists, the highest estimate is 205K, and the lowest is 120K.", "PRE_RELEASE_DATE_ONLY", "n=459 is implausibly large for a standard wire poll; quality flag. Lead sentence mislabels the print as November. Conflicts with FactSet 153k and later FJ morning 165k.", sample_n=459, range_low=120000, range_high=205000),
    rec("EMP202412-FJ-UE", "EMPLOYMENT_SITUATION_2024-12_2025-01-10", "UNEMPLOYMENT_RATE", 4.2, "SURVEY_MEDIAN", "UNKNOWN", "FinancialJuice", FJ_NFP, "January 7, 2025", None, None, "US NFP Prep", "As for the Unemployment Rate, the median expectation is for it to remain unchanged at 4.2%.", "PRE_RELEASE_DATE_ONLY", "Vendor unnamed. Agrees with FactSet UE 4.2."),
    rec("EMP202412-FJMJ-NFP", "EMPLOYMENT_SITUATION_2024-12_2025-01-10", "NFP_PAYROLL_CHANGE", 165000, "SURVEY_MEDIAN", "UNKNOWN", "FinancialJuice", FJ_MJ, "January 10, 2025", None, None, "Morning Juice - US Session Prep", "Nonfarm Payrolls - Median Forecast: 165K | Prior: 227K | Range: 268K / 100K", "PRE_RELEASE_DATE_ONLY", "Pre-session copy (Good Morning Traders / what to look out for today) but no clock, so not VERIFIED_PRE_RELEASE. Conflicts with same outlet Jan 7 160k and FactSet 153k.", range_low=100000, range_high=268000),
    rec("EMP202412-FJMJ-UE", "EMPLOYMENT_SITUATION_2024-12_2025-01-10", "UNEMPLOYMENT_RATE", 4.2, "SURVEY_MEDIAN", "UNKNOWN", "FinancialJuice", FJ_MJ, "January 10, 2025", None, None, "Morning Juice - US Session Prep", "Unemployment Rate - Median Forecast: 4.2% | Prior: 4.2% | Range: 4.4% / 4.1%", "PRE_RELEASE_DATE_ONLY", "Date only; pre-session language.", range_low=4.1, range_high=4.4),
    rec("EMP202412-FJMJ-AHEY", "EMPLOYMENT_SITUATION_2024-12_2025-01-10", "AHE_YOY", 4.0, "SURVEY_MEDIAN", "UNKNOWN", "FinancialJuice", FJ_MJ, "January 10, 2025", None, None, "Morning Juice - US Session Prep", "Average Earnings YoY - Median Forecast: 4% | Prior: 4% | Range: 4.2% / 3.8%", "PRE_RELEASE_DATE_ONLY", "AHE MoM not shown on this page.", range_low=3.8, range_high=4.2),
]

# --- EMP May 2025 / 2025-06-06 ---
WTAQ = "https://wtaq.com/2025/06/06/slow-us-job-growth-anticipated-in-may-unemployment-rate-seen-steady/"
FS_MAY = "https://insight.factset.com/total-nonfarm-payrolls-for-may-2025-are-projected-to-rise-by-130000"
OBS += [
    rec("EMP202505-WTAQ-NFP", "EMPLOYMENT_SITUATION_2025-05_2025-06-06", "NFP_PAYROLL_CHANGE", 130000, "SURVEY_MEDIAN", "Reuters", "WTAQ (Reuters reprint)", WTAQ, "Jun 6, 2025 | 12:38 AM", "2025-06-06T05:38:00Z", 412, "Slow US job growth anticipated in May; unemployment rate seen steady", "Nonfarm payrolls likely increased by 130,000 jobs last month after rising 177,000 in April, a Reuters survey of economists showed.", "VERIFIED_PRE_RELEASE", "12:38 AM interpreted as America/Chicago (WTAQ Green Bay). Any US civil timezone at 12:38 AM on 2025-06-06 is still before 12:30Z. Range 75000-190000.", range_low=75000, range_high=190000),
    rec("EMP202505-WTAQ-UE", "EMPLOYMENT_SITUATION_2025-05_2025-06-06", "UNEMPLOYMENT_RATE", 4.2, "SURVEY_MEDIAN", "Reuters", "WTAQ (Reuters reprint)", WTAQ, "Jun 6, 2025 | 12:38 AM", "2025-06-06T05:38:00Z", 412, "Slow US job growth anticipated in May; unemployment rate seen steady", "the unemployment rate holding steady at 4.2% for the third straight month", "VERIFIED_PRE_RELEASE", "Reuters preview reprint. Clock before 08:30 ET."),
    rec("EMP202505-WTAQ-AHEM", "EMPLOYMENT_SITUATION_2025-05_2025-06-06", "AHE_MOM", 0.3, "SURVEY_MEDIAN", "Reuters", "WTAQ (Reuters reprint)", WTAQ, "Jun 6, 2025 | 12:38 AM", "2025-06-06T05:38:00Z", 412, "Slow US job growth anticipated in May; unemployment rate seen steady", "Average hourly earnings are forecast to have increased 0.3% after gaining 0.2% in April.", "VERIFIED_PRE_RELEASE", "Reuters preview reprint. Stage 1 first print AHE MoM was 0.4."),
    rec("EMP202505-WTAQ-AHEY", "EMPLOYMENT_SITUATION_2025-05_2025-06-06", "AHE_YOY", 3.7, "SURVEY_MEDIAN", "Reuters", "WTAQ (Reuters reprint)", WTAQ, "Jun 6, 2025 | 12:38 AM", "2025-06-06T05:38:00Z", 412, "Slow US job growth anticipated in May; unemployment rate seen steady", "In the 12 months through May, wages are estimated to have risen 3.7% after advancing 3.8% in April", "VERIFIED_PRE_RELEASE", "Reuters preview reprint. Stage 1 first print AHE YoY was 3.9."),
    rec("EMP202505-FS-NFP", "EMPLOYMENT_SITUATION_2025-05_2025-06-06", "NFP_PAYROLL_CHANGE", 130000, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_MAY, "June 5, 2025", None, None, "Total Nonfarm Payrolls for May 2025 Are Projected to Rise By 130,000", "The median estimate for total nonfarm payroll employment for the month of May 2025 is 130,000.", "PRE_RELEASE_DATE_ONLY", "n=11; range 110000-165000. Agrees with Reuters 130k. Page says Tomorrow BLS will release May.", sample_n=11, range_low=110000, range_high=165000),
    rec("EMP202505-FS-UE", "EMPLOYMENT_SITUATION_2025-05_2025-06-06", "UNEMPLOYMENT_RATE", 4.2, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_MAY, "June 5, 2025", None, None, "Total Nonfarm Payrolls for May 2025 Are Projected to Rise By 130,000", "The median estimate for the unemployment rate for the month of April 2025 is 4.2%.", "PRE_RELEASE_DATE_ONLY", "UE paragraph says April while the payroll paragraph and closer say May. n=11; range 4.2-4.3. Do not treat the month label as clean.", sample_n=11, range_low=4.2, range_high=4.3),
]

# --- EMP Sep 2025 / 2025-11-20 ---
EUR = "https://www.euronews.com/business/2025/11/20/what-to-expect-from-us-jobs-report-after-lengthy-data-blackout"
FS_SEP = "https://insight.factset.com/total-nonfarm-payrolls-for-september-2025-are-projected-to-rise-by-50000"
OBS += [
    rec("EMP202509-EUR-NFP", "EMPLOYMENT_SITUATION_2025-09_2025-11-20", "NFP_PAYROLL_CHANGE", 50000, "SURVEY_MEDIAN", "FactSet", "Euronews (AP)", EUR, "20/11/2025 - 12:54 GMT+1", "2025-11-20T11:54:00Z", 96, "What to expect from US jobs report after lengthy data blackout?", "Economists predict that US employers added 50,000 jobs in September ... according to a survey by FactSet.", "VERIFIED_PRE_RELEASE", "Clock 12:54 GMT+1 = 11:54Z; official release 13:30Z. AP copy on Euronews. Agrees with FactSet Insight Oct 2 median."),
    rec("EMP202509-EUR-UE", "EMPLOYMENT_SITUATION_2025-09_2025-11-20", "UNEMPLOYMENT_RATE", 4.3, "SURVEY_MEDIAN", "FactSet", "Euronews (AP)", EUR, "20/11/2025 - 12:54 GMT+1", "2025-11-20T11:54:00Z", 96, "What to expect from US jobs report after lengthy data blackout?", "forecasters expect that the unemployment rate remained at a low 4.3%, according to a survey by FactSet.", "VERIFIED_PRE_RELEASE", "Clock demonstrably before 13:30Z."),
    rec("EMP202509-FS-NFP", "EMPLOYMENT_SITUATION_2025-09_2025-11-20", "NFP_PAYROLL_CHANGE", 50000, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_SEP, "October 2, 2025", None, None, "Total Nonfarm Payrolls For September 2025 Are Projected To Rise By 50,000", "The median estimate for total nonfarm payroll employment for the month of September 2025 is 50,000.", "PRE_RELEASE_DATE_ONLY", "Written for the original early-October schedule; release later delayed to Nov 20. n=19; range 30000-80000. Do not treat Oct 2 as the as-of immediately before Nov 20.", sample_n=19, range_low=30000, range_high=80000),
    rec("EMP202509-FS-UE", "EMPLOYMENT_SITUATION_2025-09_2025-11-20", "UNEMPLOYMENT_RATE", 4.3, "SURVEY_MEDIAN", "FactSet", "FactSet Insight", FS_SEP, "October 2, 2025", None, None, "Total Nonfarm Payrolls For September 2025 Are Projected To Rise By 50,000", "The median estimate for the unemployment rate for the month of September 2025 is 4.3%.", "PRE_RELEASE_DATE_ONLY", "n=19; range 4.2-4.4. Stale relative to the delayed Nov 20 print; Euronews/AP Nov 20 still quoted the same 4.3.", sample_n=19, range_low=4.2, range_high=4.4),
    rec("EMP202509-SAN-NFP", "EMPLOYMENT_SITUATION_2025-09_2025-11-20", "NFP_PAYROLL_CHANGE", 75000, "SINGLE_FORECAST", "none", "Euronews (AP)", EUR, "20/11/2025 - 12:54 GMT+1", "2025-11-20T11:54:00Z", 96, "What to expect from US jobs report after lengthy data blackout?", "Stephen Stanley, chief US economist at the bank Santander, ... forecasts that employers added 75,000 jobs.", "SINGLE_FORECAST_ONLY", "House forecast, not the FactSet survey. Clock is valid but type is not consensus."),
]


def main() -> None:
    (HERE / "schema.json").write_text(json.dumps(SCHEMA, indent=2) + "\n", encoding="utf-8")
    (HERE / "observations.json").write_text(json.dumps(OBS, indent=2) + "\n", encoding="utf-8")
    fields = [
        "record_id",
        "event_id",
        "event_type",
        "reference_period",
        "indicator",
        "consensus_value",
        "unit",
        "consensus_type",
        "survey_provider",
        "publisher",
        "source_url",
        "publication_time_original",
        "publication_time_utc",
        "official_release_time_utc",
        "lead_time_minutes",
        "source_title",
        "source_evidence_excerpt",
        "retrieved_at",
        "validation_status",
        "sample_n",
        "range_low",
        "range_high",
        "qa_official_first_print",
        "qa_arithmetic_difference",
        "econoday_consensus_value",
        "notes",
    ]
    with (HERE / "observations.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(OBS)

    verified_events = sorted(
        {r["event_id"] for r in OBS if r["validation_status"] == "VERIFIED_PRE_RELEASE"}
    )
    summary = {
        "pilot_event_count": 6,
        "events": EVENTS,
        "observation_count": len(OBS),
        "status_counts": {},
        "events_with_verified_pre_release": verified_events,
        "econoday_reserved": True,
        "production_code_changed": False,
        "stage1_first_prints_changed": False,
    }
    for r in OBS:
        summary["status_counts"][r["validation_status"]] = (
            summary["status_counts"].get(r["validation_status"], 0) + 1
        )
    (HERE / "events_investigated.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(OBS)} observations")
    print("verified events:", verified_events)
    print("status_counts:", summary["status_counts"])


if __name__ == "__main__":
    main()
