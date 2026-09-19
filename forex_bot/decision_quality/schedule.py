"""Quant V2 Experiment D: official schedule metadata. Research-only. No actuals/consensus."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from forex_bot.decision_quality.event_discovery import BOOT_REPS, BOOT_SEED, event_bootstrap_mean
from forex_bot.decision_quality.spread_volume import assign_quintile

NY = ZoneInfo("America/New_York")
LON = ZoneInfo("Europe/London")
TOR = ZoneInfo("America/Toronto")

CATEGORIES = ("INFLATION", "EMPLOYMENT", "CENTRAL_BANK_DECISION")
CURRENCIES = ("USD", "GBP", "CAD")
PERIOD_START = pd.Timestamp("2025-09-01 00:00:00")
PERIOD_END = pd.Timestamp("2026-08-31 23:59:59")

PRE_WINDOWS = (
    ("pre_120_60", 60, 120),
    ("pre_60_30", 30, 60),
    ("pre_30_15", 15, 30),
    ("pre_15_5", 5, 15),
)
POST_WINDOWS = (
    ("post_0_15", 0, 15),
    ("post_15_30", 15, 30),
    ("post_30_60", 30, 60),
    ("post_60_120", 60, 120),
)
HORIZONS_MIN = (15, 30, 60, 120, 240)
PAIR_MAP = {
    "USD": ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"),
    "GBP": ("GBP_USD",),
    "CAD": ("USD_CAD",),
}

EXCLUDED_TOKENS = (
    "real earnings",
    "producer price",
    "ppi",
    "job openings",
    "jolts",
    "gross domestic",
    "gdp",
    "average weekly earnings",
    "employment cost",
    "productivity",
)

NAME_RULES = (
    ("consumer price", "INFLATION"),
    ("cpih", "INFLATION"),
    ("cpi ", "INFLATION"),
    ("cpi)", "INFLATION"),
    ("inflation", "INFLATION"),
    ("employment situation", "EMPLOYMENT"),
    ("labour market", "EMPLOYMENT"),
    ("labor market", "EMPLOYMENT"),
    ("labour force", "EMPLOYMENT"),
    ("labor force", "EMPLOYMENT"),
    ("fomc", "CENTRAL_BANK_DECISION"),
    ("federal open market", "CENTRAL_BANK_DECISION"),
    ("monetary policy committee", "CENTRAL_BANK_DECISION"),
    ("mpc summary", "CENTRAL_BANK_DECISION"),
    ("mpc ", "CENTRAL_BANK_DECISION"),
    ("bank rate", "CENTRAL_BANK_DECISION"),
    ("interest rate announcement", "CENTRAL_BANK_DECISION"),
    ("policy interest rate", "CENTRAL_BANK_DECISION"),
    ("bank of canada rate", "CENTRAL_BANK_DECISION"),
)

ACTIVITY_EDGES = np.array(
    [
        0.005102040816326505,
        0.6428571428571387,
        0.879106438896188,
        1.1380753138075266,
        1.5610972568578514,
        89.38255033556928,
    ]
)
DISP_EDGES = np.array(
    [
        1.65263504079106e-05,
        0.0001566334280648208,
        0.00022407212602446188,
        0.00030227406717171345,
        0.0004242980957975246,
        0.004644260999902006,
    ]
)

NORMALIZATION_VERSION = "d1"
RAW_DIR = Path("data/research/external/raw")
NORM_DIR = Path("data/research/external/normalized")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def local_clock_to_utc(local_naive: datetime, tz_name: str) -> datetime:
    """Interpret a naive local wall clock in tz_name (DST-aware) and return naive UTC."""
    if local_naive.tzinfo is not None:
        raise ValueError("local_naive must be timezone-naive")
    aware = local_naive.replace(tzinfo=ZoneInfo(tz_name))
    return aware.astimezone(timezone.utc).replace(tzinfo=None)


def as_naive_utc(ts) -> datetime:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t.to_pydatetime()


def map_official_name(name: str) -> str | None:
    raw = " ".join(str(name or "").lower().split())
    if not raw:
        return None
    if any(tok in raw for tok in EXCLUDED_TOKENS):
        return None
    for needle, cat in NAME_RULES:
        if needle in raw:
            return cat
    if raw.strip() in {"cpi", "cpih"}:
        return "INFLATION"
    if raw.strip() in {"mpc", "fomc"}:
        return "CENTRAL_BANK_DECISION"
    return None


def classify_precision(has_clock: bool, estimated: bool = False) -> str:
    if estimated:
        return "estimated"
    return "clock" if has_clock else "date_only"


def event_id(currency: str, category: str, scheduled_utc: datetime, source_name: str) -> str:
    key = f"{currency}|{category}|{scheduled_utc.isoformat()}|{source_name}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def minutes_to_event(decision_utc: datetime, scheduled_utc: datetime) -> float:
    return (scheduled_utc - decision_utc).total_seconds() / 60.0


def assign_pre_window(minutes_to: float) -> str | None:
    if not np.isfinite(minutes_to):
        return None
    for wid, lo, hi in PRE_WINDOWS:
        if lo < minutes_to <= hi:
            return wid
    return None


def assign_post_window(minutes_after: float) -> str | None:
    if not np.isfinite(minutes_after):
        return None
    for wid, lo, hi in POST_WINDOWS:
        if lo <= minutes_after < hi:
            return wid
    return None


def first_eligible_post_m5_start(scheduled_utc: datetime) -> datetime:
    """First M5 bar start at or after the official scheduled clock."""
    t = pd.Timestamp(scheduled_utc)
    epoch = pd.Timestamp("1970-01-01")
    seconds = (t - epoch).total_seconds()
    grid = 300.0
    if seconds % grid == 0:
        return t.to_pydatetime()
    ceiled = epoch + pd.Timedelta(seconds=int(seconds // grid + 1) * grid)
    return ceiled.to_pydatetime()


def last_eligible_pre_m5_end(scheduled_utc: datetime) -> datetime:
    """Last completed M5 end strictly before the scheduled clock."""
    start = first_eligible_post_m5_start(scheduled_utc)
    return (pd.Timestamp(start) - pd.Timedelta(minutes=5)).to_pydatetime()


def pairs_for_currency(currency: str) -> tuple[str, ...]:
    return PAIR_MAP[currency]


def is_primary_period(scheduled_utc: datetime) -> bool:
    t = pd.Timestamp(scheduled_utc)
    return PERIOD_START <= t <= PERIOD_END


def clock_key(ts: datetime) -> tuple[int, int]:
    t = as_naive_utc(ts)
    return t.weekday(), t.hour


def find_duplicates(rows: list[dict]) -> list[tuple[str, str]]:
    seen: dict[tuple, str] = {}
    dups = []
    for r in rows:
        key = (r["currency"], r["category"], r["scheduled_ts_utc"])
        eid = r["event_id"]
        if key in seen and seen[key] != eid:
            dups.append((seen[key], eid))
        else:
            seen[key] = eid
    return dups


def exclude_uncertain(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    ok, bad = [], []
    for r in rows:
        if r.get("row_status") == "PRIMARY" and r.get("scheduled_precision") == "clock":
            ok.append(r)
        else:
            bad.append(r)
    return ok, bad


def analysis_fields_clean(row: dict) -> bool:
    forbidden = ("consensus", "forecast", "actual", "surprise", "revised")
    return not any(k in row and row[k] not in (None, "", []) for k in forbidden)


def checksum_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_raw(agency: str, filename: str, payload: bytes, source_url: str, retrieved: str) -> dict:
    dest_dir = RAW_DIR / agency / retrieved[:10]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(payload)
    meta = {
        "agency": agency,
        "filename": filename,
        "source_url": source_url,
        "retrieval_ts_utc": retrieved,
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
        "path": dest.as_posix(),
        "normalization_version": NORMALIZATION_VERSION,
    }
    (dest.with_suffix(dest.suffix + ".identity.json")).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


def parse_bls_ics(text: str) -> list[dict]:
    """Parse official BLS ICS. Only CPI and Employment Situation."""
    events = []
    blocks = re.split(r"\r?\nBEGIN:VEVENT\r?\n", text)
    for block in blocks[1:]:
        summary = _ics_field(block, "SUMMARY")
        dtstart = _ics_field(block, "DTSTART")
        uid = _ics_field(block, "UID")
        cat = map_official_name(summary or "")
        if cat is None:
            continue
        if cat not in ("INFLATION", "EMPLOYMENT"):
            continue
        utc = _ics_dt_to_utc(dtstart)
        if utc is None:
            events.append(_uncertain_row("USD", cat, summary, "BLS", uid, "ics_unparsed_dtstart"))
            continue
        events.append(
            _ok_row(
                "USD",
                cat,
                summary,
                utc,
                "America/New_York",
                "BLS",
                uid or summary,
                "clock",
            )
        )
    return events


def _ics_field(block: str, name: str) -> str | None:
    m = re.search(rf"^{name}(?:;[^:]*)?:(.+)$", block, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().replace("\\,", ",")


def _ics_dt_to_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    # DTSTART;TZID=America/New_York:20260113T083000 or 20260113T133000Z
    if raw.endswith("Z") and "T" in raw:
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ")
    m = re.search(r"(\d{8}T\d{6})$", raw)
    if not m:
        if re.fullmatch(r"\d{8}", raw):
            return None  # date-only
        return None
    local = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S")
    tz_m = re.search(r"TZID=([^:]+)", raw)
    tz = tz_m.group(1) if tz_m else "America/New_York"
    return local_clock_to_utc(local, tz)


def parse_bls_html_schedule(html: str, category_hint: str | None = None) -> list[dict]:
    """BLS year/list pages: Date | Time | Release. Times Eastern."""
    rows = []
    # e.g. Thursday, January 15, 2026 | 08:30 AM | Consumer Price Index for December 2025
    pat = re.compile(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),\s+(\d{4}).{0,80}?"
        r"(\d{1,2}:\d{2}\s*[AP]M).{0,40}?"
        r"(Consumer Price Index|Employment Situation|The Employment Situation)[^<\n]*",
        re.I | re.S,
    )
    for m in pat.finditer(html):
        month, day, year, clock, title = m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
        cat = map_official_name(title)
        if cat is None:
            continue
        if category_hint and cat != category_hint:
            continue
        local = datetime.strptime(f"{month} {day} {year} {clock.upper()}", "%B %d %Y %I:%M %p")
        utc = local_clock_to_utc(local, "America/New_York")
        rows.append(_ok_row("USD", cat, title.strip(), utc, "America/New_York", "BLS", f"{title}|{utc.isoformat()}", "clock"))
    return rows


def parse_fomc_html(html: str) -> list[dict]:
    """FOMC calendar pages. Statement clock 14:00 America/New_York unless the page says otherwise."""
    rows = []
    # Month D-D, YYYY or Month D, YYYY around "FOMC meeting"
    # Also tabular "January 27-28" 2026
    year_blocks = re.split(r"(?=<h\d[^>]*>\s*20\d\d)", html)
    years = re.findall(r">\s*(20\d\d)\s*<", html)
    # Simpler: find date ranges then attach 14:00 ET
    date_pat = re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2})(?:\s*[–-]\s*(\d{1,2}))?,?\s*(20\d\d)",
        re.I,
    )
    # Unscheduled / intermeeting often noted; mark uncertain if "unscheduled" nearby
    for m in date_pat.finditer(html):
        month, d1, d2, year = m.group(1), m.group(2), m.group(3), m.group(4)
        end_day = int(d2 or d1)
        local = datetime.strptime(f"{month} {end_day} {year} 14:00", "%B %d %Y %H:%M")
        utc = local_clock_to_utc(local, "America/New_York")
        ctx = html[max(0, m.start() - 120) : m.end() + 160].lower()
        if "unscheduled" in ctx or "intermeeting" in ctx:
            rows.append(_uncertain_row("USD", "CENTRAL_BANK_DECISION", m.group(0), "FRB", m.group(0), "unscheduled_or_intermeeting"))
            continue
        if "fomc" not in ctx and "federal open market" not in ctx and "meeting" not in ctx:
            continue
        rows.append(
            _ok_row(
                "USD",
                "CENTRAL_BANK_DECISION",
                f"FOMC statement {month} {end_day} {year}",
                utc,
                "America/New_York",
                "FRB",
                f"FOMC|{utc.date().isoformat()}",
                "clock",
            )
        )
    return _dedupe_rows(rows)


def parse_boe_mpc_html(html: str) -> list[dict]:
    """BoE MPC date tables. 12:00 Europe/London."""
    rows = []
    pat = re.compile(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday)\s+(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(20\d\d).{0,200}?(MPC|Monetary Policy)",
        re.I | re.S,
    )
    for m in pat.finditer(html):
        local = datetime.strptime(f"{m.group(2)} {m.group(3)} {m.group(4)} 12:00", "%d %B %Y %H:%M")
        utc = local_clock_to_utc(local, "Europe/London")
        rows.append(
            _ok_row(
                "GBP",
                "CENTRAL_BANK_DECISION",
                f"MPC {m.group(2)} {m.group(3)} {m.group(4)}",
                utc,
                "Europe/London",
                "BOE",
                f"MPC|{utc.date().isoformat()}",
                "clock",
            )
        )
    # Fallback: table cells "Thursday 5 February" under a 2026 heading
    if not rows:
        year = None
        for ym in re.finditer(r"\b(20\d\d)\b", html):
            year = ym.group(1)
        pat2 = re.compile(
            r"(Monday|Tuesday|Wednesday|Thursday|Friday)\s+(\d{1,2})\s+"
            r"(January|February|March|April|May|June|July|August|September|October|November|December)",
            re.I,
        )
        # Only if page is clearly MPC dates
        if "monetary policy committee" in html.lower() or "mpc" in html.lower():
            current_year = None
            for line in re.split(r"<[^>]+>", html):
                ym = re.search(r"\b(20\d\d)\b", line)
                if ym and "20" == ym.group(1)[:2]:
                    # keep last seen year heading
                    if "20" in line:
                        current_year = ym.group(1)
                m = pat2.search(line)
                if m and current_year:
                    local = datetime.strptime(f"{m.group(2)} {m.group(3)} {current_year} 12:00", "%d %B %Y %H:%M")
                    utc = local_clock_to_utc(local, "Europe/London")
                    rows.append(
                        _ok_row(
                            "GBP",
                            "CENTRAL_BANK_DECISION",
                            f"MPC {line.strip()[:80]}",
                            utc,
                            "Europe/London",
                            "BOE",
                            f"MPC|{utc.date().isoformat()}",
                            "clock",
                        )
                    )
    return _dedupe_rows(rows)


def parse_ons_release_list(html: str, category: str) -> list[dict]:
    """ONS previous-release / calendar snippets. 07:00 Europe/London."""
    rows = []
    # ISO dates in JSON-LD or "Released: 17 September 2025"
    for m in re.finditer(
        r"(?:Released|Release date|released on)[:\s]+(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d\d)",
        html,
        re.I,
    ):
        local = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)} 07:00", "%d %B %Y %H:%M")
        utc = local_clock_to_utc(local, "Europe/London")
        title = "CPI" if category == "INFLATION" else "Labour market"
        rows.append(_ok_row("GBP", category, title, utc, "Europe/London", "ONS", f"{title}|{utc.date().isoformat()}", "clock"))
    # data-date="2025-09-17"
    for m in re.finditer(r'(?:releaseDate|datePublished|data-date)"?\s*[:=]\s*"?(20\d\d-\d{2}-\d{2})', html):
        d = datetime.strptime(m.group(1), "%Y-%m-%d")
        local = d.replace(hour=7, minute=0)
        utc = local_clock_to_utc(local, "Europe/London")
        title = "CPI" if category == "INFLATION" else "Labour market"
        rows.append(_ok_row("GBP", category, title, utc, "Europe/London", "ONS", f"{title}|{utc.date().isoformat()}", "clock"))
    return _dedupe_rows(rows)


def parse_statcan_html(html: str, category: str) -> list[dict]:
    """StatCan The Daily / release tables. 08:30 America/New_York."""
    rows = []
    for m in re.finditer(r"(20\d\d-\d{2}-\d{2})", html):
        ctx = html[max(0, m.start() - 80) : m.end() + 80].lower()
        if category == "INFLATION" and "consumer price" not in ctx and "cpi" not in ctx:
            continue
        if category == "EMPLOYMENT" and "labour force" not in ctx and "labor force" not in ctx:
            continue
        d = datetime.strptime(m.group(1), "%Y-%m-%d")
        local = d.replace(hour=8, minute=30)
        utc = local_clock_to_utc(local, "America/New_York")
        title = "Consumer Price Index" if category == "INFLATION" else "Labour Force Survey"
        rows.append(_ok_row("CAD", category, title, utc, "America/New_York", "STATCAN", f"{title}|{utc.date().isoformat()}", "clock"))
    return _dedupe_rows(rows)


def parse_boc_html(html: str) -> list[dict]:
    """Bank of Canada scheduled rate announcements. Official clock 09:45 America/Toronto."""
    rows = []
    if "interest rate announcement" not in html.lower() and "policy interest rate" not in html.lower():
        return rows
    year = None
    for m in re.finditer(
        r"(20\d\d)|(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2})(?:,\s*(20\d\d))?",
        html,
        re.I,
    ):
        if m.group(1) and not m.group(2):
            year = m.group(1)
            continue
        y = m.group(4) or year
        if not y or not m.group(2):
            continue
        local = datetime.strptime(f"{m.group(2)} {m.group(3)} {y} 09:45", "%B %d %Y %H:%M")
        if local.weekday() != 2:  # official BoC rate announcements are Wednesdays
            continue
        utc = local_clock_to_utc(local, "America/Toronto")
        rows.append(
            _ok_row(
                "CAD",
                "CENTRAL_BANK_DECISION",
                f"BoC rate {m.group(2)} {m.group(3)} {y}",
                utc,
                "America/Toronto",
                "BOC",
                f"BOC|{utc.date().isoformat()}",
                "clock",
            )
        )
    return _dedupe_rows(rows)


BLS_RESCHEDULED_UTC = {
    "2025-10-24T12:30:00",  # Sept CPI after lapse
    "2025-11-20T13:30:00",  # Sept Employment after lapse
    "2025-12-16T13:30:00",  # Nov Employment after lapse
    "2025-12-18T13:30:00",  # Nov CPI after lapse
}


def parse_bls_year_lines(text: str) -> list[dict]:
    """Official BLS year-page / table lines with weekday, date, 08:30 AM, title."""
    rows = []
    pat = re.compile(
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),?\s+(20\d\d)\s+(\d{1,2}:\d{2}\s*[AP]M)\s+"
        r"(Consumer Price Index|Employment Situation)[^\n]*",
        re.I,
    )
    for m in pat.finditer(text):
        title = m.group(0)
        if "veteran" in title.lower() or "real earnings" in title.lower():
            continue
        cat = map_official_name(title)
        if cat is None:
            continue
        local = datetime.strptime(
            f"{m.group(1)} {m.group(2)} {m.group(3)} {m.group(4).upper()}",
            "%B %d %Y %I:%M %p",
        )
        utc = local_clock_to_utc(local, "America/New_York")
        row = _ok_row("USD", cat, title.strip(), utc, "America/New_York", "BLS", title.strip(), "clock")
        if utc.isoformat(timespec="seconds") in BLS_RESCHEDULED_UTC:
            row["row_status"] = "RESCHEDULED"
            row["uncertain_reason"] = "official_2025_lapse_delay"
        rows.append(row)
    return _dedupe_rows(rows)


def parse_bls_ref_release_table(text: str, category: str) -> list[dict]:
    """Reference-month / release-date / 08:30 AM tables from official BLS news-release pages."""
    rows = []
    title = "Consumer Price Index" if category == "INFLATION" else "Employment Situation"
    pat = re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d\d)"
        r".{0,40}?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),\s+(20\d\d)"
        r".{0,20}?08:30\s*AM",
        re.I | re.S,
    )
    for m in pat.finditer(text):
        local = datetime.strptime(f"{m.group(3)} {m.group(4)} {m.group(5)} 08:30 AM", "%b %d %Y %I:%M %p")
        utc = local_clock_to_utc(local, "America/New_York")
        row = _ok_row("USD", category, f"{title} {m.group(1)} {m.group(2)}", utc, "America/New_York", "BLS", f"{title}|{utc.date().isoformat()}", "clock")
        if utc.isoformat(timespec="seconds") in BLS_RESCHEDULED_UTC:
            row["row_status"] = "RESCHEDULED"
            row["uncertain_reason"] = "official_2025_lapse_delay"
        rows.append(row)
    return _dedupe_rows(rows)


def parse_ons_version_clocks(html: str, category: str) -> list[dict]:
    rows = []
    title = "CPI" if category == "INFLATION" else "Labour market"
    for m in re.finditer(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d\d)\s+07:00",
        html,
        re.I,
    ):
        local = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)} 07:00", "%d %B %Y %H:%M")
        utc = local_clock_to_utc(local, "Europe/London")
        rows.append(_ok_row("GBP", category, title, utc, "Europe/London", "ONS", f"{title}|{utc.date().isoformat()}", "clock"))
    return _dedupe_rows(rows)


def parse_statcan_named_dates(text: str, category: str) -> list[dict]:
    """PDF or Daily schedule lines: Month D, YYYY after a category header, or ISO dates."""
    rows = []
    title = "Consumer Price Index" if category == "INFLATION" else "Labour Force Survey"
    if category == "INFLATION":
        start = text.find("Consumer Price Index")
        end = text.find("Farm income", start + 10) if start >= 0 else -1
    else:
        start = text.find("Labour Force Survey")
        end = text.find("Labour productivity", start + 10) if start >= 0 else -1
    chunk = text[start:end] if start >= 0 else text
    for m in re.finditer(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(20\d\d)",
        chunk,
        re.I,
    ):
        local = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)} 08:30", "%B %d %Y %H:%M")
        utc = local_clock_to_utc(local, "America/New_York")
        rows.append(_ok_row("CAD", category, title, utc, "America/New_York", "STATCAN", f"{title}|{utc.date().isoformat()}", "clock"))
    for m in re.finditer(r"(CPI|LFS)\s+(20\d\d-\d{2}-\d{2})\s+08:30", text):
        want = "CPI" if category == "INFLATION" else "LFS"
        if m.group(1) != want:
            continue
        d = datetime.strptime(m.group(2), "%Y-%m-%d").replace(hour=8, minute=30)
        utc = local_clock_to_utc(d, "America/New_York")
        rows.append(_ok_row("CAD", category, title, utc, "America/New_York", "STATCAN", f"{title}|{utc.date().isoformat()}", "clock"))
    return _dedupe_rows(rows)


def parse_fomc_meeting_blocks(html: str) -> list[dict]:
    """Official fomccalendars.htm year + month + day-range blocks. Statement 14:00 ET on last meeting day."""
    rows = []
    year = None
    for m in re.finditer(
        r"(20\d\d)\s+FOMC Meetings|fomc-meeting__month[^>]*>\s*<strong>([A-Za-z/]+)</strong>.*?"
        r'fomc-meeting__date[^>]*>\s*([^<]+)',
        html,
        re.S | re.I,
    ):
        if m.group(1):
            year = int(m.group(1))
            continue
        if year is None:
            continue
        month_raw = m.group(2)
        days = m.group(3).strip()
        ctx = html[m.start() : m.end() + 400].lower()
        if "notation" in ctx:
            rows.append(_uncertain_row("USD", "CENTRAL_BANK_DECISION", f"{month_raw} {days} {year}", "FRB", days, "notation_vote"))
            continue
        month = month_raw.split("/")[-1]
        dm = re.search(r"(\d{1,2})\s*[–\-]\s*(\d{1,2})", days)
        end_day = int(dm.group(2) if dm else re.search(r"(\d{1,2})", days).group(1))
        try:
            local = datetime.strptime(f"{month} {end_day} {year} 14:00", "%B %d %Y %H:%M")
        except ValueError:
            rows.append(_uncertain_row("USD", "CENTRAL_BANK_DECISION", f"{month} {days} {year}", "FRB", days, "unparsed_meeting_date"))
            continue
        utc = local_clock_to_utc(local, "America/New_York")
        rows.append(
            _ok_row(
                "USD",
                "CENTRAL_BANK_DECISION",
                f"FOMC statement {month} {end_day} {year}",
                utc,
                "America/New_York",
                "FRB",
                f"FOMC|{utc.date().isoformat()}",
                "clock",
            )
        )
    return _dedupe_rows(rows)


def parse_boe_date_page(html: str) -> list[dict]:
    rows = []
    low = html.lower()
    if "monetary policy committee" not in low and "mpc announcement" not in low and "upcoming-mpc" not in low:
        return rows
    main = re.split(r"Notes to editors|notes to editors", html, maxsplit=1)[0]
    for m in re.finditer(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d\d)",
        main,
        re.I,
    ):
        local = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)} 12:00", "%d %B %Y %H:%M")
        if local.weekday() != 3:  # official MPC announcement dates are Thursdays
            continue
        utc = local_clock_to_utc(local, "Europe/London")
        rows.append(
            _ok_row(
                "GBP",
                "CENTRAL_BANK_DECISION",
                f"MPC {m.group(1)} {m.group(2)} {m.group(3)}",
                utc,
                "Europe/London",
                "BOE",
                f"MPC|{utc.date().isoformat()}",
                "clock",
            )
        )
    # "Thursday 5 February" under a 2026 heading
    current_year = None
    for m in re.finditer(
        r"(20\d\d)|Thursday\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)",
        main,
        re.I,
    ):
        if m.group(1):
            current_year = m.group(1)
            continue
        if not current_year:
            continue
        local = datetime.strptime(f"{m.group(2)} {m.group(3)} {current_year} 12:00", "%d %B %Y %H:%M")
        if local.weekday() != 3:
            continue
        utc = local_clock_to_utc(local, "Europe/London")
        rows.append(
            _ok_row(
                "GBP",
                "CENTRAL_BANK_DECISION",
                f"MPC {m.group(2)} {m.group(3)} {current_year}",
                utc,
                "Europe/London",
                "BOE",
                f"MPC|{utc.date().isoformat()}",
                "clock",
            )
        )
    return _dedupe_rows(rows)


def _ok_row(currency, category, name, utc, tz, agency, ref, precision) -> dict:
    return {
        "event_id": event_id(currency, category, utc, name),
        "currency": currency,
        "category": category,
        "source_event_name": name,
        "scheduled_ts_utc": utc.isoformat(timespec="seconds"),
        "scheduled_tz_source": tz,
        "scheduled_precision": precision,
        "source_agency": agency,
        "source_ref": ref,
        "row_status": "PRIMARY",
        "uncertain_reason": None,
        "consensus": None,
        "forecast": None,
        "actual": None,
        "surprise": None,
        "normalization_version": NORMALIZATION_VERSION,
    }


def _uncertain_row(currency, category, name, agency, ref, reason) -> dict:
    return {
        "event_id": hashlib.sha256(f"UNC|{currency}|{name}|{ref}".encode()).hexdigest()[:16],
        "currency": currency,
        "category": category,
        "source_event_name": name,
        "scheduled_ts_utc": None,
        "scheduled_tz_source": None,
        "scheduled_precision": "unknown",
        "source_agency": agency,
        "source_ref": ref,
        "row_status": "UNCERTAIN",
        "uncertain_reason": reason,
        "consensus": None,
        "forecast": None,
        "actual": None,
        "surprise": None,
        "normalization_version": NORMALIZATION_VERSION,
    }


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        key = (r["currency"], r["category"], r["scheduled_ts_utc"], r["row_status"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def merge_official_rows(*groups: list[dict]) -> list[dict]:
    return _dedupe_rows([r for g in groups for r in g])


def activity_quintile(vol_sess_rel: np.ndarray) -> np.ndarray:
    return assign_quintile(vol_sess_rel, ACTIVITY_EDGES)


def dispersion_quintile(disp_std: np.ndarray) -> np.ndarray:
    return assign_quintile(disp_std, DISP_EDGES)


def event_bootstrap_diff(event_x: np.ndarray, base_x: np.ndarray, *, seed: int = BOOT_SEED, reps: int = BOOT_REPS) -> dict:
    """Event-level mean minus a fixed base mean; bootstrap only the event sample."""
    ev = np.asarray(event_x, dtype=float)
    ev = ev[np.isfinite(ev)]
    base = np.asarray(base_x, dtype=float)
    base = base[np.isfinite(base)]
    if len(ev) < 2 or len(base) == 0:
        return {"n_event": int(len(ev)), "n_base": int(len(base)), "diff": None, "p05": None, "p95": None}
    base_mean = float(np.mean(base))
    diffs = []
    rng = np.random.default_rng(seed)
    n = len(ev)
    for _ in range(reps):
        draw = ev[rng.integers(0, n, size=n)]
        diffs.append(float(np.mean(draw) - base_mean))
    diffs = np.asarray(diffs)
    return {
        "n_event": int(len(ev)),
        "n_base": int(len(base)),
        "diff": float(np.mean(ev) - base_mean),
        "p05": float(np.quantile(diffs, 0.05)),
        "p95": float(np.quantile(diffs, 0.95)),
        "event_mean": float(np.mean(ev)),
        "base_mean": base_mean,
    }


# Silence unused import warning if event_bootstrap_mean is used by tests via re-export
_ = event_bootstrap_mean
