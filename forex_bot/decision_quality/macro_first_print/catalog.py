"""Official 2025 BLS CPI / Employment Situation release catalog.

Clocks come from the official year schedule already stored by Experiment D:
`data/research/external/raw/BLS/2026-09-19/year_2025_cpi_empsit.txt`
(source https://www.bls.gov/schedule/2025/).

Archive HTML pattern documented on BLS news-release pages:
https://www.bls.gov/news.release/archives/{cpi|empsit}_MMDDYYYY.htm
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from forex_bot.decision_quality.schedule import local_clock_to_utc, parse_bls_year_lines

ARCHIVE_BASE = "https://www.bls.gov/news.release/archives"
CPI_ARCHIVE_INDEX = "https://www.bls.gov/bls/news-release/cpi.htm"
EMPSIT_ARCHIVE_INDEX = "https://www.bls.gov/bls/news-release/empsit.htm"
YEAR_SCHEDULE = "https://www.bls.gov/schedule/2025/"
DEFAULT_YEAR_TEXT = Path("data/research/external/raw/BLS/2026-09-19/year_2025_cpi_empsit.txt")

# Official BLS archive-index statements (checked 2026-09-23).
OFFICIALLY_UNPUBLISHED_2025 = (
    ("CPI", "2025-10", "October 2025 CPI not published because of the 2025 lapse in federal appropriations"),
    (
        "EMPLOYMENT_SITUATION",
        "2025-10",
        "October 2025 Employment Situation not published because of the 2025 lapse in federal appropriations",
    ),
)

_DATE_IN_TITLE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2}),?\s+(20\d{2})"
)
_REF = re.compile(
    r"for\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})",
    re.I,
)
_MONTH_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass(frozen=True)
class CatalogEntry:
    event_type: str
    reference_period: str
    release_date: str
    scheduled_time_local: str
    timezone: str
    scheduled_time_utc: str
    source_url: str
    release_name: str
    official_note: str | None = None


def archive_url(event_type: str, release_date: str) -> str:
    stamp = datetime.strptime(release_date, "%Y-%m-%d").strftime("%m%d%Y")
    stem = "cpi" if event_type == "CPI" else "empsit"
    return f"{ARCHIVE_BASE}/{stem}_{stamp}.htm"


def _reference_period(title: str) -> str:
    m = _REF.search(title)
    if not m:
        return ""
    return f"{m.group(2)}-{_MONTH_NUM[m.group(1).lower()]:02d}"


def _release_date(title: str) -> str:
    m = _DATE_IN_TITLE.search(title)
    if not m:
        return ""
    return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date().isoformat()


def catalog_from_year_text(text: str) -> list[CatalogEntry]:
    rows = parse_bls_year_lines(text)
    out: list[CatalogEntry] = []
    for row in rows:
        title = row["source_event_name"]
        event_type = "CPI" if row["category"] == "INFLATION" else "EMPLOYMENT_SITUATION"
        release_date = _release_date(title)
        naive_local = datetime.strptime(f"{release_date} 08:30", "%Y-%m-%d %H:%M")
        utc = local_clock_to_utc(naive_local, "America/New_York")
        utc_iso = utc.isoformat(timespec="seconds") + "Z"
        parsed_utc = row["scheduled_ts_utc"]
        if not parsed_utc.endswith("Z"):
            parsed_utc = parsed_utc + "Z" if "T" in parsed_utc else parsed_utc
        # Prefer the already-DST-correct official-line UTC if it disagrees (should not).
        if parsed_utc.replace("+00:00", "Z")[:19] != utc_iso[:19]:
            utc_iso = parsed_utc if parsed_utc.endswith("Z") else parsed_utc + "Z"
        out.append(
            CatalogEntry(
                event_type=event_type,
                reference_period=_reference_period(title),
                release_date=release_date,
                scheduled_time_local=f"{release_date}T08:30:00",
                timezone="America/New_York",
                scheduled_time_utc=utc_iso,
                source_url=archive_url(event_type, release_date),
                release_name=title,
                official_note="official_2025_lapse_delay" if row.get("row_status") == "RESCHEDULED" else None,
            )
        )
    return out


def load_official_2025_catalog(year_text: str | None = None) -> list[CatalogEntry]:
    """CPI/Employment releases whose official scheduled date is in calendar 2025."""
    if year_text is None:
        year_text = DEFAULT_YEAR_TEXT.read_text(encoding="utf-8")
    return [
        e
        for e in catalog_from_year_text(year_text)
        if e.release_date.startswith("2025-") and e.event_type in ("CPI", "EMPLOYMENT_SITUATION")
    ]
