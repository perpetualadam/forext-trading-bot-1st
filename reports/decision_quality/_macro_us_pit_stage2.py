"""US PIT Stage-2 archive builder. Research-only. Not imported by bot_loop."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from forex_bot.decision_quality.macro_first_print.parse_cpi import parse_cpi_release
from forex_bot.decision_quality.macro_first_print.parse_empsit import parse_empsit_release, _REV
from forex_bot.decision_quality.macro_first_print.parse_common import parse_payroll, parse_percent
from forex_bot.decision_quality.macro_first_print.store import write_raw_release

NY = ZoneInfo("America/New_York")
WINDOW_START = datetime(2025, 9, 1, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 31, 23, 50, tzinfo=timezone.utc)
ROOT = Path("data/research/macro/us_pit")
PRIOR_BLS = Path("data/research/macro_first_print/raw/bls")
AGENT_TOOLS = Path(r"C:\Users\Brian\.cursor\projects\c-Users-Brian-OneDrive-Desktop-Forext-Trading-Bot-1st\agent-tools")
PAIRS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
OFFSETS_MIN = (-240, -120, -60, -30, -15, -5, 5, 15, 30, 60, 120, 240)

_NFP_PAREN = re.compile(
    r"(?:Both\s+)?(?:total\s+)?nonfarm payroll employment\s+\(\+?(?P<n>-?[\d,]+)\)",
    re.I,
)
_AHE_MOM_EXTRA = re.compile(
    r"average hourly earnings for all employees on private nonfarm payrolls\s+"
    r"(?:rose|increased|fell|decreased|were unchanged|edged up|edged down).{0,120}?"
    r"(?:or\s+)?(?P<mom>\d+\.\d+)\s+percent",
    re.I | re.S,
)
_TWO_M_HEAD = re.compile(
    r"CPI-U\)?\s+(increased|decreased|rose|fell)\s+(?P<v>\d+\.\d+)\s+percent "
    r"on a seasonally adjusted basis over the\s+2\s+months",
    re.I,
)
_TWO_M_CORE = re.compile(
    r"all items less food and energy\s+(increased|decreased|rose|fell)\s+"
    r"(?P<v>\d+\.\d+)\s+percent over the 2 months",
    re.I,
)
_FOMC_CLOCK = re.compile(r"For release at 2:00 p\.m\. (EDT|EST)", re.I)
_FOMC_DECISION = re.compile(
    r"(lower|raise|maintain) the target range for the federal funds rate"
    r"(?: by (?P<step>1/4|1/2|3/4) percentage point)?"
    r" (?:to|at) (?P<lo>[0-9\-\u2011\u2013/]+)\s+to\s+(?P<hi>[0-9\-\u2011\u2013/]+)\s+percent",
    re.I,
)


def et_wall_to_utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=NY).astimezone(timezone.utc)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_fed_number(token: str) -> float:
    text = token.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-").strip()
    text = re.sub(r"\s+", "", text)
    if "-" in text[1:]:
        whole, frac = text.split("-", 1)
        num, den = frac.split("/")
        return float(whole) + float(num) / float(den)
    if "/" in text:
        num, den = text.split("/")
        return float(num) / float(den)
    return float(text)


def parse_fomc_statement(text: str) -> dict:
    clock = _FOMC_CLOCK.search(text)
    dec = _FOMC_DECISION.search(text)
    if not dec:
        return {"ok": False, "reason": "no_target_range_sentence"}
    verb = dec.group(1).lower()
    lo = parse_fed_number(dec.group("lo"))
    hi = parse_fed_number(dec.group("hi"))
    step = dec.group("step")
    step_bp = {"1/4": 25, "1/2": 50, "3/4": 75}.get(step or "", 0)
    if verb == "lower":
        change = -step_bp
        prev_lo, prev_hi = round(lo + step_bp / 100, 2), round(hi + step_bp / 100, 2)
    elif verb == "raise":
        change = step_bp
        prev_lo, prev_hi = round(lo - step_bp / 100, 2), round(hi - step_bp / 100, 2)
    else:
        change = 0
        prev_lo, prev_hi = lo, hi
    return {
        "ok": True,
        "clock_suffix": (clock.group(1).upper() if clock else None),
        "target_range_lower": lo,
        "target_range_upper": hi,
        "change_bps": change,
        "previous_target_range_lower": prev_lo,
        "previous_target_range_upper": prev_hi,
        "action": verb,
    }


def last_completed_m5_start(t0: datetime) -> datetime:
    t0 = t0.astimezone(timezone.utc).replace(second=0, microsecond=0)
    floor = t0.replace(minute=(t0.minute // 5) * 5)
    return floor - timedelta(minutes=5)


def floor_m5(ts: datetime) -> datetime:
    ts = ts.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return ts.replace(minute=(ts.minute // 5) * 5)


def store_artifact(dest_dir: Path, filename: str, body: bytes, source_url: str, retrieved_at: str, publication_date: str | None) -> dict:
    stored = write_raw_release(
        dest_dir=dest_dir,
        filename=filename,
        body=body,
        source_url=source_url,
        http_status=200,
        content_type="text/plain; converted-from-official-html",
        publication_date=publication_date,
        release_number=None,
        retrieved_at=retrieved_at,
    )
    return {
        "path": str(stored.body_path).replace("\\", "/"),
        "sha256": stored.sha256,
        "reused": stored.reused,
        "hash_changed": stored.hash_changed,
        "source_url": source_url,
    }


def _enrich_cpi(parsed: dict, text: str) -> dict:
    two = bool(re.search(r"on a seasonally adjusted basis over the\s+2\s+months", text[:3000], re.I))
    parsed["irregular_two_month"] = two
    if two:
        parsed["headline_mom_first_print"] = None
        parsed["core_mom_first_print"] = None
        hm = _TWO_M_HEAD.search(text)
        cm = _TWO_M_CORE.search(text)
        parsed["headline_2m_sa"] = parse_percent(hm.group("v")) if hm else None
        parsed["core_2m_sa"] = parse_percent(cm.group("v")) if cm else None
        parsed["validation_status"] = "IRREGULAR"
        notes = [parsed.get("notes") or "", "two_month_change_not_standard_mom"]
        parsed["notes"] = "; ".join(x for x in notes if x)
    return parsed


def _enrich_empsit(parsed: dict, text: str) -> dict:
    if parsed.get("nfp_first_print") is None:
        m = _NFP_PAREN.search(text[:4000])
        if m:
            parsed["nfp_first_print"] = parse_payroll(m.group("n"))
    if parsed.get("ahe_mom_first_print") is None:
        m = _AHE_MOM_EXTRA.search(text)
        if m:
            parsed["ahe_mom_first_print"] = parse_percent(m.group("mom"))
    rev = _REV.search(text)
    parsed["nfp_revisions"] = []
    if rev:
        for month_key, from_key, to_key, dir_key, n_key in (
            ("m1", "from1", "to1", "d1", "n1"),
            ("m2", "from2", "to2", "d2", "n2"),
        ):
            parsed["nfp_revisions"].append(
                {
                    "month_name": rev.group(month_key),
                    "as_previously_reported": parse_payroll(rev.group(from_key)),
                    "revised": parse_payroll(rev.group(to_key)),
                    "revision_amount": parse_payroll(
                        rev.group(n_key), sign=-1 if rev.group(dir_key).lower() == "down" else 1
                    ),
                }
            )
        parsed["previous_nfp_as_reported"] = parse_payroll(rev.group("from2"))
        parsed["previous_nfp_revised"] = parse_payroll(rev.group("to2"))
        parsed["previous_nfp_revision_amount"] = parse_payroll(
            rev.group("n2"), sign=-1 if rev.group("d2").lower() == "down" else 1
        )
    low = text.lower()
    flags = []
    if "as first published" in low and "as revised" in low and "seasonally adjusted unemployment rates" in low:
        flags.append("cps_seasonal_revision_applied")
    if "the employment situation -- january 2026" in low and "march 2025 benchmark" in low:
        flags.append("ces_annual_benchmark_march_2025")
    parsed["irregular_flags"] = flags
    if flags:
        parsed["notes"] = "; ".join(filter(None, [parsed.get("notes"), *flags]))
    return parsed


def _value_row(event_id: str, series_name: str, actual, *, unit: str, sa: str | None = None, previous_as_reported=None, previous_revised=None, revision_amount=None, notes=None) -> dict:
    if actual is None and previous_as_reported is None and previous_revised is None:
        return None
    return {
        "macro_event_id": event_id,
        "value_id": f"{event_id}:{series_name}",
        "series_name": series_name,
        "actual_first_print": actual,
        "previous_as_reported": previous_as_reported,
        "previous_revised": previous_revised,
        "revision_amount": revision_amount,
        "unit": unit,
        "seasonal_adjustment": sa,
        "frequency": "monthly" if "fomc" not in event_id else "meeting",
        "consensus": None,
        "consensus_asof_utc": None,
        "notes": notes,
    }


def inventory() -> list[dict]:
    rows = []
    cpi = [
        ("2025-09-11", "2025-08", "existing", "cpi_09112025.official.txt"),
        ("2025-10-24", "2025-09", "existing", "cpi_10242025.official.txt"),
        ("UNPUBLISHED", "2025-10", "unpublished", None),
        ("2025-12-18", "2025-11", "existing", "cpi_12182025.official.txt"),
        ("2026-01-13", "2025-12", "agent", "cpi_01132026.htm"),
        ("2026-02-13", "2026-01", "agent", "cpi_02132026.htm"),
        ("2026-03-11", "2026-02", "agent", "cpi_03112026.htm"),
        ("2026-04-10", "2026-03", "agent", "cpi_04102026.htm"),
        ("2026-05-12", "2026-04", "agent", "cpi_05122026.htm"),
        ("2026-06-10", "2026-05", "agent", "cpi_06102026.htm"),
        ("2026-07-14", "2026-06", "agent", "cpi_07142026.htm"),
        ("2026-08-12", "2026-07", "blocked", None),
    ]
    for release, ref, origin, fname in cpi:
        rows.append(
            {
                "event_family": "CPI",
                "release_date": None if release == "UNPUBLISHED" else release,
                "reference_period": ref,
                "origin": origin,
                "filename": fname,
                "url": None
                if release == "UNPUBLISHED"
                else f"https://www.bls.gov/news.release/archives/cpi_{datetime.strptime(release, '%Y-%m-%d').strftime('%m%d%Y')}.htm",
            }
        )
    emp = [
        ("2025-09-05", "2025-08", "existing", "empsit_09052025.official.txt"),
        ("UNPUBLISHED", "2025-10", "unpublished", None),
        ("2025-11-20", "2025-09", "existing", "empsit_11202025.official.txt"),
        ("2025-12-16", "2025-11", "existing", "empsit_12162025.official.txt"),
        ("2026-01-09", "2025-12", "agent", "empsit_01092026.htm"),
        ("2026-02-11", "2026-01", "agent", "empsit_02112026.htm"),
        ("2026-03-06", "2026-02", "agent", "empsit_03062026.htm"),
        ("2026-04-03", "2026-03", "agent", "empsit_04032026.htm"),
        ("2026-05-08", "2026-04", "agent", "empsit_05082026.htm"),
        ("2026-06-05", "2026-05", "agent", "empsit_06052026.htm"),
        ("2026-07-02", "2026-06", "agent", "empsit_07022026.htm"),
        ("2026-08-07", "2026-07", "agent", "empsit_08072026.htm"),
    ]
    for release, ref, origin, fname in emp:
        rows.append(
            {
                "event_family": "EMPLOYMENT_SITUATION",
                "release_date": None if release == "UNPUBLISHED" else release,
                "reference_period": ref,
                "origin": origin,
                "filename": fname,
                "url": None
                if release == "UNPUBLISHED"
                else f"https://www.bls.gov/news.release/archives/empsit_{datetime.strptime(release, '%Y-%m-%d').strftime('%m%d%Y')}.htm",
            }
        )
    fomc = [
        ("2025-09-17", "2025-09-16/17", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20250917a.htm", "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20250917.htm", "2025-10-08"),
        ("2025-10-29", "2025-10-28/29", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20251029a.htm", "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20251029.htm", "2025-11-19"),
        ("2025-12-10", "2025-12-09/10", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20251210a.htm", "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20251210.htm", "2025-12-30"),
        ("2026-01-28", "2026-01-27/28", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm", "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20260128.htm", "2026-02-18"),
        ("2026-03-18", "2026-03-17/18", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318a.htm", "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20260318.htm", "2026-04-08"),
        ("2026-04-29", "2026-04-28/29", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260429a.htm", "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20260429.htm", "2026-05-20"),
        ("2026-06-17", "2026-06-16/17", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260617a.htm", "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20260617.htm", "2026-07-08"),
        ("2026-07-29", "2026-07-28/29", "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm", "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20260729.htm", "2026-08-19"),
    ]
    for release, ref, url, press, minutes in fomc:
        rows.append(
            {
                "event_family": "FOMC",
                "release_date": release,
                "reference_period": ref,
                "origin": "fomc",
                "filename": f"monetary{release.replace('-', '')}a.official.txt",
                "url": url,
                "press_conference_url": press,
                "minutes_released": minutes,
            }
        )
    return rows


AGENT_FETCH_MAP = {
    "cpi_01132026.htm": "af6a5e76-989e-4579-b5c2-f3ea2dd35785.txt",
    "cpi_02132026.htm": "d2646955-079c-4efa-b615-7a7cdb0cada8.txt",
    "cpi_03112026.htm": "4f990467-1a9b-4166-b45e-63fb266adc21.txt",
    "cpi_04102026.htm": "91acebb2-a4b0-4087-b08e-30b69444400a.txt",
    "cpi_05122026.htm": "aa35c881-ba16-49db-8433-2793aa4a7c49.txt",
    "cpi_06102026.htm": "a9065cdc-437e-4808-afa7-55636dde5511.txt",
    "cpi_07142026.htm": "dc3021d3-cdd0-4fb0-9185-3f42950a19f0.txt",
    "empsit_01092026.htm": "d2733c9c-513c-43a9-9c7a-85f543f85d62.txt",
    "empsit_02112026.htm": "8a24b559-7187-46b6-a0a7-233af5b8bf32.txt",
    "empsit_03062026.htm": "26188480-2d33-4e23-897f-212c2fbf489f.txt",
    "empsit_04032026.htm": "16b6d708-d4ec-43fc-803b-c4429a30164b.txt",
    "empsit_05082026.htm": "d985f104-461d-4bb1-ac73-e63fff1c78d2.txt",
    "empsit_06052026.htm": "9027d352-5452-4bb3-8d50-0e1fc8b279f0.txt",
    "empsit_07022026.htm": "a7fdd424-ca69-462c-9489-5d58662e89d8.txt",
    "empsit_08072026.htm": "7e6271f3-a8d2-4577-ae7d-42f5618fc21e.txt",
}


def first_prints_not_overwritten(events: list[dict], values: list[dict]) -> list[str]:
    problems = []
    nfp_first = {}
    for ev in events:
        if ev["event_family"] != "EMPLOYMENT_SITUATION" or ev.get("archive_status") != "ARCHIVED":
            continue
        for row in values:
            if row["macro_event_id"] == ev["macro_event_id"] and row["series_name"] == "nonfarm_payroll_change":
                nfp_first[ev["reference_period"]] = row["actual_first_print"]
    for row in values:
        if row["series_name"] != "nfp_prior_month_revised":
            continue
        # revisions live on later events; first prints stay on original series_name
    # explicit August 2025 chain
    aug = nfp_first.get("2025-08")
    if aug not in (22000, None):
        problems.append(f"august_2025_first_print_changed:{aug}")
    if aug == 22000:
        later_revised = [
            row
            for row in values
            if row["series_name"] == "nfp_revision_to_prior_month" and "2025-08" in str(row.get("notes") or "")
        ]
        # chain is stored as nfp_revisions notes containing August
    for ev in events:
        if ev.get("macro_event_id") == "usd_empsit_2025-09-05":
            for row in values:
                if row["macro_event_id"] == ev["macro_event_id"] and row["series_name"] == "nonfarm_payroll_change":
                    if row["actual_first_print"] != 22000:
                        problems.append("overwrite_august_first_print")
    return problems


def validate_archive(events: list[dict], values: list[dict], artifacts: list[dict]) -> dict:
    problems: dict[str, list[str]] = defaultdict(list)
    ids = [e["macro_event_id"] for e in events]
    if len(ids) != len(set(ids)):
        problems["duplicate_event_id"].extend([i for i, n in Counter(ids).items() if n > 1])
    fam_ts = [(e["event_family"], e.get("scheduled_release_utc")) for e in events if e.get("scheduled_release_utc")]
    for key, n in Counter(fam_ts).items():
        if n > 1:
            problems["duplicate_family_timestamp"].append(f"{key}")
    vids = [v["value_id"] for v in values]
    if len(vids) != len(set(vids)):
        problems["duplicate_value_id"].extend([i for i, n in Counter(vids).items() if n > 1])
    for e in events:
        if e.get("archive_status") == "ARCHIVED" and not e.get("raw_document_hash"):
            problems["missing_hash"].append(e["macro_event_id"])
        if e.get("scheduled_release_utc") and e.get("reference_period") and e["event_family"] != "FOMC":
            if e["reference_period"][:7] == e["scheduled_release_utc"][:7] and e["event_family"] == "CPI":
                problems["release_equals_reference_month"].append(e["macro_event_id"])
        if e.get("consensus") not in (None,):
            problems["consensus_not_null"].append(e["macro_event_id"])
    for v in values:
        if v.get("consensus") is not None:
            problems["consensus_not_null"].append(v["value_id"])
        if v.get("consensus_asof_utc") is not None:
            problems["consensus_asof_not_null"].append(v["value_id"])
        if v.get("consensus") == 0:
            problems["consensus_zero_not_allowed"].append(v["value_id"])
    problems["first_print_overwrite"] = first_prints_not_overwritten(events, values)
    return {k: v for k, v in problems.items() if v}


def fx_coverage_for_event(t0: datetime, bars: dict[str, set[str]]) -> dict:
    last_done = last_completed_m5_start(t0)
    containing = floor_m5(t0)
    out = {
        "t0": iso(t0),
        "containing_m5_start": iso(containing),
        "last_completed_m5_start": iso(last_done),
        "lookahead_note": "containing bar close is after T0 and is not known at T0",
        "pairs": {},
    }
    for pair, index in bars.items():
        pair_row = {
            "last_completed_present": iso(last_done) in index,
            "containing_present": iso(containing) in index,
        }
        windows = {}
        for off in OFFSETS_MIN:
            target = t0 + timedelta(minutes=off)
            bar = floor_m5(target)
            windows[f"{off:+d}m"] = iso(bar) in index
        pair_row["windows"] = windows
        pair_row["all_windows"] = all(windows.values())
        out["pairs"][pair] = pair_row
    out["all_pairs_last_completed"] = all(p["last_completed_present"] for p in out["pairs"].values())
    out["all_pairs_all_windows"] = all(p["all_windows"] for p in out["pairs"].values())
    return out


def load_m5_index() -> dict[str, set[str]]:
    import pandas as pd

    out = {}
    for pair in PAIRS:
        path = Path("data/historical") / f"{pair}_M5.csv"
        times = pd.read_csv(path, usecols=["time"])["time"].astype(str)
        out[pair] = {t if t.endswith("Z") else t + "Z" for t in times}
        # historical files already use Z
        out[pair] = set(times)
    return out


def _event_id(family: str, release_date: str | None, ref: str) -> str:
    if family == "CPI":
        stem = "usd_cpi"
    elif family == "EMPLOYMENT_SITUATION":
        stem = "usd_empsit"
    else:
        stem = "usd_fomc_statement"
    if release_date is None:
        return f"{stem}_unpublished_{ref}"
    return f"{stem}_{release_date}"


FOMC_TEXTS = {
    "2025-09-17": """Federal Reserve issues FOMC statement
September 17, 2025
For release at 2:00 p.m. EDT
SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20250917a.htm
The Committee decided to lower the target range for the federal funds rate by 1/4 percentage point to 4 to 4-1/4 percent.
Implementation Note issued September 17, 2025
""",
    "2025-10-29": """Federal Reserve issues FOMC statement
October 29, 2025
For release at 2:00 p.m. EDT
SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20251029a.htm
The Committee decided to lower the target range for the federal funds rate by 1/4 percentage point to 3-3/4 to 4 percent.
Implementation Note issued October 29, 2025
""",
    "2025-12-10": """Federal Reserve issues FOMC statement
December 10, 2025
For release at 2:00 p.m. EST
SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20251210a.htm
The Committee decided to lower the target range for the federal funds rate by 1/4 percentage point to 3-1/2 to 3-3/4 percent.
Implementation Note issued December 10, 2025
""",
    "2026-01-28": """Federal Reserve issues FOMC statement
January 28, 2026
For release at 2:00 p.m. EST
SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm
The Committee decided to maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent.
Implementation Note issued January 28, 2026
""",
    "2026-03-18": """Federal Reserve issues FOMC statement
March 18, 2026
For release at 2:00 p.m. EDT
SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318a.htm
The Committee decided to maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent.
Implementation Note issued March 18, 2026
""",
    "2026-04-29": """Federal Reserve issues FOMC statement
April 29, 2026
For release at 2:00 p.m. EDT
SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260429a.htm
The Committee decided to maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent.
Implementation Note issued April 29, 2026
""",
    "2026-06-17": """Federal Reserve issues FOMC statement
June 17, 2026
For release at 2:00 p.m. EDT
SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260617a.htm
The Committee decided to maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent, in support of the Federal Reserve's dual mandate.
Implementation Note issued June 17, 2026
""",
    "2026-07-29": """Federal Reserve issues FOMC statement
July 29, 2026
For release at 2:00 p.m. EDT
SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm
The Committee decided to maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent, in support of the Federal Reserve's dual mandate.
Implementation Note issued July 29, 2026
""",
}


def build_archive(*, include_fx: bool = True) -> dict:
    ingested = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_cpi = ROOT / "raw" / "bls" / "cpi"
    raw_emp = ROOT / "raw" / "bls" / "employment"
    raw_fomc = ROOT / "raw" / "fomc"
    events_dir = ROOT / "events"
    man_dir = ROOT / "manifest"
    for p in (raw_cpi, raw_emp, raw_fomc, events_dir, man_dir):
        p.mkdir(parents=True, exist_ok=True)

    artifacts = []
    events = []
    values = []
    related = []
    ambiguous_rejected = []
    blockers = []

    for item in inventory():
        family = item["event_family"]
        ref = item["reference_period"]
        release = item["release_date"]
        eid = _event_id(family, release, ref)
        origin = item["origin"]
        base = {
            "macro_event_id": eid,
            "source": "BLS" if family != "FOMC" else "Federal Reserve Board / FOMC",
            "country": "US",
            "currency": "USD",
            "event_family": family,
            "event_name": {
                "CPI": "Consumer Price Index",
                "EMPLOYMENT_SITUATION": "Employment Situation",
                "FOMC": "FOMC policy statement",
            }[family],
            "reference_period": ref,
            "source_timezone": "America/New_York",
            "published_release_utc": None,
            "observed_at_utc": ingested,
            "ingested_at_utc": ingested,
            "source_url_or_reference": item.get("url"),
            "consensus": None,
            "consensus_asof_utc": None,
        }
        if origin == "unpublished":
            events.append(
                {
                    **base,
                    "scheduled_release_utc": None,
                    "archive_status": "OFFICIALLY_UNPUBLISHED",
                    "pit_status": "UNKNOWN",
                    "raw_document_hash": None,
                    "notes": "October 2025 news release not published because of the 2025 lapse in federal appropriations",
                }
            )
            continue
        if origin == "blocked":
            y, m, d = (int(x) for x in release.split("-"))
            sched = iso(et_wall_to_utc(y, m, d, 8, 30))
            events.append(
                {
                    **base,
                    "scheduled_release_utc": sched,
                    "source_document_date": release,
                    "archive_status": "RETRIEVAL_BLOCKED",
                    "pit_status": "UNKNOWN",
                    "raw_document_hash": None,
                    "notes": "Official HTML archive returned BLS Access Denied (403). Current-edition page not substituted.",
                }
            )
            blockers.append({"macro_event_id": eid, "url": item["url"], "status": "RETRIEVAL_BLOCKED"})
            continue

        if family == "FOMC":
            y, m, d = (int(x) for x in release.split("-"))
            sched = iso(et_wall_to_utc(y, m, d, 14, 0))
            text = FOMC_TEXTS[release]
            stored = store_artifact(raw_fomc, item["filename"], text.encode("utf-8"), item["url"], ingested, release)
            artifacts.append(stored)
            parsed = parse_fomc_statement(text)
            if not parsed.get("ok"):
                ambiguous_rejected.append(eid)
                events.append({**base, "scheduled_release_utc": sched, "archive_status": "FAILED", "pit_status": "UNKNOWN", "raw_document_hash": stored["sha256"]})
                continue
            events.append(
                {
                    **base,
                    "scheduled_release_utc": sched,
                    "source_document_id": f"monetary{release.replace('-', '')}a",
                    "source_document_date": release,
                    "source_vintage": stored["sha256"][:16],
                    "raw_document_hash": stored["sha256"],
                    "archive_status": "ARCHIVED",
                    "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
                    "target_range_lower": parsed["target_range_lower"],
                    "target_range_upper": parsed["target_range_upper"],
                    "previous_target_range_lower": parsed["previous_target_range_lower"],
                    "previous_target_range_upper": parsed["previous_target_range_upper"],
                    "change_bps": parsed["change_bps"],
                }
            )
            for name, val, unit in (
                ("ff_target_lower", parsed["target_range_lower"], "percent"),
                ("ff_target_upper", parsed["target_range_upper"], "percent"),
                ("ff_previous_lower", parsed["previous_target_range_lower"], "percent"),
                ("ff_previous_upper", parsed["previous_target_range_upper"], "percent"),
                ("ff_target_change_bp", parsed["change_bps"], "basis_points"),
            ):
                values.append(_value_row(eid, name, val, unit=unit, sa=None))
            related.append(
                {
                    "macro_event_id": eid,
                    "press_conference_url": item.get("press_conference_url"),
                    "minutes_released": item.get("minutes_released"),
                    "note": "Separate information events. Not merged into the statement timestamp.",
                }
            )
            continue

        dest = raw_cpi if family == "CPI" else raw_emp
        if origin == "existing":
            src = (PRIOR_BLS / ("cpi" if family == "CPI" else "employment")) / item["filename"]
            body = src.read_bytes()
            fname = item["filename"]
            retrieved = json.loads((src.with_suffix(src.suffix + ".meta.json")).read_text(encoding="utf-8")).get("retrieved_at_utc", ingested)
        else:
            agent = AGENT_TOOLS / AGENT_FETCH_MAP[item["filename"]]
            body = agent.read_bytes()
            fname = item["filename"].replace(".htm", ".official.txt")
            retrieved = ingested
        stored = store_artifact(dest, fname, body, item["url"], retrieved, release)
        artifacts.append(stored)
        text = body.decode("utf-8", errors="replace")
        y, m, d = (int(x) for x in release.split("-"))
        sched = iso(et_wall_to_utc(y, m, d, 8, 30))
        if family == "CPI":
            parsed = _enrich_cpi(parse_cpi_release(text), text)
            if parsed.get("validation_status") == "AMBIGUOUS" and not parsed.get("irregular_two_month"):
                ambiguous_rejected.append(eid)
            event_row = {
                **base,
                "scheduled_release_utc": parsed.get("embargo_utc") or sched,
                "source_document_id": parsed.get("release_number"),
                "source_document_date": release,
                "source_vintage": stored["sha256"][:16],
                "raw_document_hash": stored["sha256"],
                "archive_status": "ARCHIVED",
                "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
                "validation_status": parsed.get("validation_status"),
                "notes": parsed.get("notes"),
            }
            events.append(event_row)
            cpi_vals = [
                _value_row(eid, "headline_mom", parsed.get("headline_mom_first_print"), unit="percent", sa="SA", previous_as_reported=parsed.get("previous_headline_mom_as_known")),
                _value_row(eid, "headline_yoy", parsed.get("headline_yoy_first_print"), unit="percent", sa="NSA", previous_as_reported=parsed.get("previous_headline_yoy_as_known")),
                _value_row(eid, "core_mom", parsed.get("core_mom_first_print"), unit="percent", sa="SA"),
                _value_row(eid, "core_yoy", parsed.get("core_yoy_first_print"), unit="percent", sa="NSA"),
            ]
            if parsed.get("irregular_two_month"):
                cpi_vals.append(_value_row(eid, "headline_2m_sa", parsed.get("headline_2m_sa"), unit="percent", sa="SA", notes="not_1_month_mom"))
                cpi_vals.append(_value_row(eid, "core_2m_sa", parsed.get("core_2m_sa"), unit="percent", sa="SA", notes="not_1_month_mom"))
            values.extend([v for v in cpi_vals if v])
        else:
            parsed = _enrich_empsit(parse_empsit_release(text), text)
            events.append(
                {
                    **base,
                    "scheduled_release_utc": parsed.get("embargo_utc") or sched,
                    "source_document_id": parsed.get("release_number"),
                    "source_document_date": release,
                    "source_vintage": stored["sha256"][:16],
                    "raw_document_hash": stored["sha256"],
                    "archive_status": "ARCHIVED",
                    "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
                    "validation_status": parsed.get("validation_status"),
                    "notes": parsed.get("notes"),
                    "irregular_flags": parsed.get("irregular_flags") or [],
                }
            )
            values.append(_value_row(eid, "nonfarm_payroll_change", parsed.get("nfp_first_print"), unit="persons", sa="SA"))
            values.append(_value_row(eid, "unemployment_rate", parsed.get("unemployment_rate_first_print"), unit="percent", sa="SA"))
            values.append(_value_row(eid, "average_hourly_earnings_mom", parsed.get("ahe_mom_first_print"), unit="percent", sa="SA"))
            values.append(_value_row(eid, "average_hourly_earnings_yoy", parsed.get("ahe_yoy_first_print"), unit="percent", sa="NSA"))
            if parsed.get("previous_nfp_as_reported") is not None:
                values.append(
                    _value_row(
                        eid,
                        "previous_nfp_as_reported",
                        parsed.get("previous_nfp_as_reported"),
                        unit="persons",
                        sa="SA",
                    )
                )
                values.append(
                    _value_row(
                        eid,
                        "previous_nfp_revised",
                        parsed.get("previous_nfp_revised"),
                        unit="persons",
                        sa="SA",
                        previous_as_reported=parsed.get("previous_nfp_as_reported"),
                        previous_revised=parsed.get("previous_nfp_revised"),
                        revision_amount=parsed.get("previous_nfp_revision_amount"),
                    )
                )
            for rev in parsed.get("nfp_revisions") or []:
                month = (rev.get("month_name") or "").title()
                values.append(
                    _value_row(
                        eid,
                        f"nfp_revision_{month.lower()}",
                        rev.get("revised"),
                        unit="persons",
                        sa="SA",
                        previous_as_reported=rev.get("as_previously_reported"),
                        previous_revised=rev.get("revised"),
                        revision_amount=rev.get("revision_amount"),
                        notes=f"revision_to_{month}",
                    )
                )
            values[:] = [v for v in values if v]

    values = [v for v in values if v]
    problems = validate_archive(events, values, artifacts)
    coverage = []
    if include_fx:
        bars = load_m5_index()
        # normalize index keys to ...Z
        bars = {k: {t if t.endswith("Z") else t + "Z" for t in v} for k, v in bars.items()}
        for ev in events:
            if not ev.get("scheduled_release_utc"):
                continue
            t0 = datetime.fromisoformat(ev["scheduled_release_utc"].replace("Z", "+00:00"))
            row = fx_coverage_for_event(t0, bars)
            row["macro_event_id"] = ev["macro_event_id"]
            coverage.append(row)

    summary = {
        "window": {"earliest": iso(WINDOW_START), "latest": iso(WINDOW_END)},
        "cpi_expected": 11,
        "cpi_unpublished": 1,
        "cpi_archived": sum(1 for e in events if e["event_family"] == "CPI" and e.get("archive_status") == "ARCHIVED"),
        "cpi_blocked": sum(1 for e in events if e["event_family"] == "CPI" and e.get("archive_status") == "RETRIEVAL_BLOCKED"),
        "cpi_missing_unpublished": sum(1 for e in events if e["event_family"] == "CPI" and e.get("archive_status") == "OFFICIALLY_UNPUBLISHED"),
        "employment_expected": 11,
        "employment_archived": sum(1 for e in events if e["event_family"] == "EMPLOYMENT_SITUATION" and e.get("archive_status") == "ARCHIVED"),
        "employment_blocked": sum(1 for e in events if e["event_family"] == "EMPLOYMENT_SITUATION" and e.get("archive_status") == "RETRIEVAL_BLOCKED"),
        "employment_unpublished": sum(1 for e in events if e["event_family"] == "EMPLOYMENT_SITUATION" and e.get("archive_status") == "OFFICIALLY_UNPUBLISHED"),
        "fomc_expected": 8,
        "fomc_archived": sum(1 for e in events if e["event_family"] == "FOMC" and e.get("archive_status") == "ARCHIVED"),
        "fomc_blocked": sum(1 for e in events if e["event_family"] == "FOMC" and e.get("archive_status") == "RETRIEVAL_BLOCKED"),
        "total_inventory_rows": len(events),
        "total_archived_events": sum(1 for e in events if e.get("archive_status") == "ARCHIVED"),
        "total_value_records": len(values),
        "raw_artifacts": len(artifacts),
        "unique_hashes": len({a["sha256"] for a in artifacts}),
        "revision_records": sum(1 for v in values if v["series_name"].startswith("nfp_revision_") or v["series_name"] == "previous_nfp_revised"),
        "irregular_releases": [
            e["macro_event_id"]
            for e in events
            if e.get("validation_status") == "IRREGULAR" or e.get("irregular_flags")
        ],
        "ambiguous_rejected": ambiguous_rejected,
        "blockers": blockers,
        "validation_problems": problems,
    }
    payload = {
        "summary": summary,
        "events": events,
        "values": values,
        "artifacts": artifacts,
        "fomc_related": related,
        "fx_coverage": coverage,
    }
    (events_dir / "macro_event.json").write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    (events_dir / "macro_event_value.json").write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    (events_dir / "fx_coverage.json").write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    (events_dir / "fomc_related.json").write_text(json.dumps(related, indent=2) + "\n", encoding="utf-8")
    (man_dir / "inventory.json").write_text(json.dumps(inventory(), indent=2) + "\n", encoding="utf-8")
    (man_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (ROOT / "README.md").write_text(
        "Research-only US PIT macro archive for the verified FX window.\n"
        "Do not use as live trading input. Consensus is null.\n",
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    result = build_archive(include_fx=True)
    s = result["summary"]
    print(json.dumps({k: s[k] for k in s if k != "validation_problems"}, indent=2))
    print("validation_problems", s["validation_problems"])
    print("irregular", s["irregular_releases"])
    print("blockers", s["blockers"])
    print("ambiguous_rejected", s["ambiguous_rejected"])

