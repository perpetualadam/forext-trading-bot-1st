"""Official US macro PIT helpers. Research-only. Not imported by bot_loop."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
PIT_STATUSES = (
    "PIT_SAFE",
    "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
    "CURRENT_VALUE_ONLY",
    "REVISION_RISK",
    "UNKNOWN",
)
EVENT_FAMILIES = ("CPI", "EMPLOYMENT_SITUATION", "FOMC")


def et_wall_to_utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """DST-aware America/New_York wall clock -> timezone-aware UTC. Not fixed EST."""
    local = datetime(year, month, day, hour, minute, tzinfo=NY)
    return local.astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_value_record(row: dict) -> list[str]:
    errors: list[str] = []
    required = ("macro_event_id", "event_family", "event_name", "pit_status")
    for key in required:
        if not row.get(key):
            errors.append(f"missing {key}")
    if row.get("event_family") not in EVENT_FAMILIES:
        errors.append("invalid event_family")
    if row.get("pit_status") not in PIT_STATUSES:
        errors.append("invalid pit_status")
    if row.get("consensus") not in (None, "") and not row.get("consensus_asof_utc"):
        errors.append("consensus without consensus_asof_utc")
    return errors


def never_overwrite_first_print(store: dict[str, dict], event_id: str, field: str, new_value) -> dict:
    """Append-only vintage. Existing first-print values are not replaced."""
    key = f"{event_id}|{field}"
    existing = store.get(key)
    if existing is None:
        store[key] = {"value": new_value, "kind": "first_print"}
        return store[key]
    if existing.get("kind") == "first_print" and existing.get("value") != new_value:
        raise ValueError(f"refusing to overwrite first print {key}")
    return existing


def split_event_and_values(event: dict, values: list[dict]) -> dict:
    if not values:
        raise ValueError("event must have at least one value record")
    ids = {v["macro_event_id"] for v in values}
    if ids != {event["macro_event_id"]}:
        raise ValueError("value records must share the parent event id")
    return {"event": event, "values": values}


PROOF_DIR = Path("data/research/macro/pit_proof")
BLS_CPI = Path("data/research/macro_first_print/raw/bls/cpi")
BLS_EMP = Path("data/research/macro_first_print/raw/bls/employment")


def build_proof_sample() -> dict:
    """Copy official artifacts into a NEW research folder. Do not modify source JSONL or first-print originals."""
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    (PROOF_DIR / "artifacts").mkdir(exist_ok=True)
    copies = []
    mapping = {
        "cpi_09112025.official.txt": BLS_CPI / "cpi_09112025.official.txt",
        "cpi_10242025.official.txt": BLS_CPI / "cpi_10242025.official.txt",
        "cpi_12182025.official.txt": BLS_CPI / "cpi_12182025.official.txt",
        "empsit_09052025.official.txt": BLS_EMP / "empsit_09052025.official.txt",
        "empsit_11202025.official.txt": BLS_EMP / "empsit_11202025.official.txt",
        "empsit_12162025.official.txt": BLS_EMP / "empsit_12162025.official.txt",
    }
    for name, src in mapping.items():
        dest = PROOF_DIR / "artifacts" / name
        shutil.copy2(src, dest)
        meta_src = src.with_suffix(src.suffix + ".meta.json")
        if meta_src.exists():
            meta_dest = PROOF_DIR / "artifacts" / (name + ".meta.json")
            shutil.copy2(meta_src, meta_dest)
        copies.append({"name": name, "sha256": sha256_file(dest), "source": str(src)})
    fomc_excerpts = _write_fomc_excerpts()
    copies.extend(fomc_excerpts)
    hash_by_name = {row["name"]: row["sha256"] for row in copies}
    events = _proof_events()
    for event in events:
        for key, artifact in (
            ("usd_cpi_2025-09-11", "cpi_09112025.official.txt"),
            ("usd_cpi_2025-10-24", "cpi_10242025.official.txt"),
            ("usd_cpi_2025-12-18", "cpi_12182025.official.txt"),
            ("usd_empsit_2025-09-05", "empsit_09052025.official.txt"),
            ("usd_empsit_2025-11-20", "empsit_11202025.official.txt"),
            ("usd_empsit_2025-12-16", "empsit_12162025.official.txt"),
            ("usd_fomc_statement_2025-09-17", "fomc_monetary20250917a.excerpt.txt"),
            ("usd_fomc_statement_2025-10-29", "fomc_monetary20251029a.excerpt.txt"),
            ("usd_fomc_statement_2025-12-10", "fomc_monetary20251210a.excerpt.txt"),
        ):
            if event["macro_event_id"] == key:
                event["raw_document_hash"] = hash_by_name[artifact]
                event["consensus"] = None
                event["consensus_asof_utc"] = None

    payload = {
        "schema_version": "macro_pit_proof_v1",
        "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
        "fx_window": {"earliest": "2025-09-01T00:00:00Z", "latest": "2026-08-31T23:50:00Z"},
        "immutability": [
            "Never overwrite a historical observation.",
            "Never replace first print with a revised value.",
            "New revision = new vintage or explicit revision record.",
            "consensus requires consensus_asof_utc; otherwise invalid for surprise.",
        ],
        "copied_artifacts": copies,
        "events": events,
    }
    dest_json = PROOF_DIR / "proof_sample.json"
    dest_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (PROOF_DIR / "README.md").write_text(
        "Research-only official PIT proof sample. Do not use as live trading input.\n"
        "BLS artifacts are copies of hashed official archive conversions.\n"
        "FOMC records cite live official federalreserve.gov HTML retrieved for this audit.\n",
        encoding="utf-8",
    )
    return payload


def _write_fomc_excerpts() -> list[dict]:
    """Store hashed statement excerpts retrieved from official federalreserve.gov HTML."""
    excerpts = {
        "fomc_monetary20250917a.excerpt.txt": (
            "SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20250917a.htm\n"
            "RETRIEVED_FOR: macro_official_pit_stage1 proof sample\n"
            "DATE LINE: September 17, 2025\n"
            "RELEASE CLOCK: For release at 2:00 p.m. EDT\n"
            "DECISION: lower the target range for the federal funds rate by 1/4 percentage point to 4 to 4-1/4 percent.\n"
            "IMPLEMENTATION NOTE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20250917a1.htm\n"
            "IMPLEMENTATION DIRECTIVE: maintain the federal funds rate in a target range of 4 to 4-1/4 percent. Effective September 18, 2025.\n"
            "PRESS CONFERENCE (SEPARATE EVENT): https://www.federalreserve.gov/monetarypolicy/fomcpresconf20250917.htm\n"
            "MINUTES (SEPARATE EVENT, released October 08, 2025): https://www.federalreserve.gov/monetarypolicy/fomcminutes20250917.htm\n"
        ),
        "fomc_monetary20251029a.excerpt.txt": (
            "SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20251029a.htm\n"
            "RETRIEVED_FOR: macro_official_pit_stage1 proof sample\n"
            "DATE LINE: October 29, 2025\n"
            "RELEASE CLOCK: For release at 2:00 p.m. EDT\n"
            "DECISION: lower the target range for the federal funds rate by 1/4 percentage point to 3-3/4 to 4 percent.\n"
            "MINUTES (SEPARATE EVENT, released November 19, 2025)\n"
        ),
        "fomc_monetary20251210a.excerpt.txt": (
            "SOURCE: https://www.federalreserve.gov/newsevents/pressreleases/monetary20251210a.htm\n"
            "RETRIEVED_FOR: macro_official_pit_stage1 proof sample\n"
            "DATE LINE: December 10, 2025\n"
            "RELEASE CLOCK: For release at 2:00 p.m. EST\n"
            "DECISION: lower the target range for the federal funds rate by 1/4 percentage point to 3-1/2 to 3-3/4 percent.\n"
            "MINUTES (SEPARATE EVENT, released December 30, 2025)\n"
        ),
    }
    out = []
    for name, text in excerpts.items():
        dest = PROOF_DIR / "artifacts" / name
        dest.write_text(text, encoding="utf-8")
        out.append({"name": name, "sha256": sha256_file(dest), "source": name.split("_")[1].replace(".excerpt.txt", "")})
    return out


def _proof_events() -> list[dict]:
    cpi_sep = {
        "macro_event_id": "usd_cpi_2025-09-11",
        "source": "BLS",
        "country": "US",
        "currency": "USD",
        "event_family": "CPI",
        "reference_period": "2025-08",
        "scheduled_release_utc": et_wall_to_utc(2025, 9, 11, 8, 30).isoformat(),
        "published_release_utc": None,
        "source_timezone": "America/New_York",
        "source_url_or_reference": "https://www.bls.gov/news.release/archives/cpi_09112025.htm",
        "source_document_id": "USDL-25-1356",
        "embargo_local": "2025-09-11 08:30 ET",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
        "lookahead_known_at_release": "YES",
        "lookahead_later_revision_risk_if_using_this_archive": "NO",
        "vintage_enough": "YES",
        "notes": "Embargo line is scheduled time, not a measured wire print. DST=EDT -> 12:30Z.",
        "values": [
            {"event_name": "headline_cpi_mom_sa", "actual_first_print": 0.4, "previous_as_reported": 0.2, "unit": "percent", "seasonal_adjustment": "SA"},
            {"event_name": "headline_cpi_yoy_nsa", "actual_first_print": 2.9, "previous_as_reported": 2.7, "unit": "percent", "seasonal_adjustment": "NSA"},
            {"event_name": "core_cpi_mom_sa", "actual_first_print": 0.3, "previous_as_reported": 0.3, "unit": "percent", "seasonal_adjustment": "SA"},
            {"event_name": "core_cpi_yoy_nsa", "actual_first_print": 3.1, "previous_as_reported": None, "unit": "percent", "seasonal_adjustment": "NSA"},
        ],
    }
    cpi_oct = {
        "macro_event_id": "usd_cpi_2025-10-24",
        "source": "BLS",
        "country": "US",
        "currency": "USD",
        "event_family": "CPI",
        "reference_period": "2025-09",
        "scheduled_release_utc": et_wall_to_utc(2025, 10, 24, 8, 30).isoformat(),
        "published_release_utc": None,
        "source_timezone": "America/New_York",
        "source_url_or_reference": "https://www.bls.gov/news.release/archives/cpi_10242025.htm",
        "source_document_id": "USDL-25-1502",
        "embargo_local": "2025-10-24 08:30 ET",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
        "lookahead_known_at_release": "YES",
        "lookahead_later_revision_risk_if_using_this_archive": "NO",
        "vintage_enough": "YES",
        "notes": "Release delayed vs usual mid-month clock (appropriations lapse). September collection completed before the lapse. DST=EDT -> 12:30Z.",
        "values": [
            {"event_name": "headline_cpi_mom_sa", "actual_first_print": 0.3, "previous_as_reported": 0.4, "unit": "percent", "seasonal_adjustment": "SA"},
            {"event_name": "headline_cpi_yoy_nsa", "actual_first_print": 3.0, "previous_as_reported": 2.9, "unit": "percent", "seasonal_adjustment": "NSA"},
            {"event_name": "core_cpi_mom_sa", "actual_first_print": 0.2, "previous_as_reported": 0.3, "unit": "percent", "seasonal_adjustment": "SA"},
            {"event_name": "core_cpi_yoy_nsa", "actual_first_print": 3.0, "previous_as_reported": None, "unit": "percent", "seasonal_adjustment": "NSA"},
        ],
    }
    cpi_dec = {
        "macro_event_id": "usd_cpi_2025-12-18",
        "source": "BLS",
        "country": "US",
        "currency": "USD",
        "event_family": "CPI",
        "reference_period": "2025-11",
        "scheduled_release_utc": et_wall_to_utc(2025, 12, 18, 8, 30).isoformat(),
        "published_release_utc": None,
        "source_timezone": "America/New_York",
        "source_url_or_reference": "https://www.bls.gov/news.release/archives/cpi_12182025.htm",
        "source_document_id": "USDL-25-1584",
        "embargo_local": "2025-12-18 08:30 ET",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
        "lookahead_known_at_release": "YES",
        "lookahead_later_revision_risk_if_using_this_archive": "NO",
        "vintage_enough": "YES",
        "notes": "Lead states a 2-month SA change Sep-Nov because October survey data were not collected. headline_cpi_mom_sa is NOT a standard 1-month first print. Do not force MoM.",
        "values": [
            {"event_name": "headline_cpi_2m_sa", "actual_first_print": 0.2, "previous_as_reported": None, "unit": "percent", "seasonal_adjustment": "SA"},
            {"event_name": "headline_cpi_yoy_nsa", "actual_first_print": 2.7, "previous_as_reported": 3.0, "unit": "percent", "seasonal_adjustment": "NSA"},
            {"event_name": "core_cpi_2m_sa", "actual_first_print": 0.2, "previous_as_reported": None, "unit": "percent", "seasonal_adjustment": "SA"},
            {"event_name": "core_cpi_yoy_nsa", "actual_first_print": 2.6, "previous_as_reported": None, "unit": "percent", "seasonal_adjustment": "NSA"},
            {"event_name": "headline_cpi_mom_sa", "actual_first_print": None, "previous_as_reported": None, "unit": "percent", "seasonal_adjustment": "SA", "missing_reason": "release states 2-month SA change, not 1-month MoM"},
        ],
    }
    emp_aug = {
        "macro_event_id": "usd_empsit_2025-09-05",
        "source": "BLS",
        "country": "US",
        "currency": "USD",
        "event_family": "EMPLOYMENT_SITUATION",
        "reference_period": "2025-08",
        "scheduled_release_utc": et_wall_to_utc(2025, 9, 5, 8, 30).isoformat(),
        "source_url_or_reference": "https://www.bls.gov/news.release/archives/empsit_09052025.htm",
        "source_document_id": "USDL-25-1344",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
        "lookahead_known_at_release": "YES",
        "lookahead_later_revision_risk_if_using_this_archive": "NO",
        "vintage_enough": "YES",
        "notes": "August NFP first print +22,000. Later releases revise August; those revisions belong on later events, not here.",
        "values": [
            {"event_name": "nfp_change_first_print", "actual_first_print": 22000, "unit": "persons"},
            {"event_name": "unemployment_rate", "actual_first_print": 4.3, "unit": "percent"},
            {"event_name": "ahe_mom", "actual_first_print": 0.3, "unit": "percent"},
            {"event_name": "ahe_yoy", "actual_first_print": 3.7, "unit": "percent"},
            {"event_name": "previous_nfp_as_previously_reported", "actual_first_print": 73000, "unit": "persons", "notes": "July as previously reported in this release"},
            {"event_name": "previous_nfp_revised", "actual_first_print": 79000, "unit": "persons", "notes": "July revised in this release"},
            {"event_name": "previous_nfp_revision_amount", "actual_first_print": 6000, "unit": "persons"},
        ],
    }
    emp_sep = {
        "macro_event_id": "usd_empsit_2025-11-20",
        "source": "BLS",
        "country": "US",
        "currency": "USD",
        "event_family": "EMPLOYMENT_SITUATION",
        "reference_period": "2025-09",
        "scheduled_release_utc": et_wall_to_utc(2025, 11, 20, 8, 30).isoformat(),
        "source_url_or_reference": "https://www.bls.gov/news.release/archives/empsit_11202025.htm",
        "source_document_id": "USDL-25-1487",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
        "lookahead_known_at_release": "YES",
        "lookahead_later_revision_risk_if_using_this_archive": "NO",
        "vintage_enough": "YES",
        "notes": "Revises August NFP from +22,000 to -4,000. That revision must not overwrite usd_empsit_2025-09-05 nfp_change_first_print.",
        "values": [
            {"event_name": "nfp_change_first_print", "actual_first_print": 119000, "unit": "persons"},
            {"event_name": "unemployment_rate", "actual_first_print": 4.4, "unit": "percent"},
            {"event_name": "ahe_mom", "actual_first_print": 0.2, "unit": "percent"},
            {"event_name": "previous_nfp_as_previously_reported", "actual_first_print": 22000, "unit": "persons", "notes": "August as previously reported"},
            {"event_name": "previous_nfp_revised", "actual_first_print": -4000, "unit": "persons"},
            {"event_name": "previous_nfp_revision_amount", "actual_first_print": -26000, "unit": "persons"},
        ],
    }
    emp_nov = {
        "macro_event_id": "usd_empsit_2025-12-16",
        "source": "BLS",
        "country": "US",
        "currency": "USD",
        "event_family": "EMPLOYMENT_SITUATION",
        "reference_period": "2025-11",
        "scheduled_release_utc": et_wall_to_utc(2025, 12, 16, 8, 30).isoformat(),
        "source_url_or_reference": "https://www.bls.gov/news.release/archives/empsit_12162025.htm",
        "source_document_id": "USDL-25-1581",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
        "lookahead_known_at_release": "YES",
        "lookahead_later_revision_risk_if_using_this_archive": "NO",
        "vintage_enough": "YES",
        "notes": "Unemployment little changed from September (no October household print). Revises August again (-4,000 to -26,000).",
        "values": [
            {"event_name": "nfp_change_first_print", "actual_first_print": 64000, "unit": "persons"},
            {"event_name": "unemployment_rate", "actual_first_print": 4.6, "unit": "percent"},
            {"event_name": "ahe_mom", "actual_first_print": 0.1, "unit": "percent"},
            {"event_name": "ahe_yoy", "actual_first_print": 3.5, "unit": "percent"},
            {"event_name": "previous_nfp_as_previously_reported", "actual_first_print": 119000, "unit": "persons", "notes": "September as previously reported"},
            {"event_name": "previous_nfp_revised", "actual_first_print": 108000, "unit": "persons"},
            {"event_name": "previous_nfp_revision_amount", "actual_first_print": -11000, "unit": "persons"},
        ],
    }
    fomc_sep = {
        "macro_event_id": "usd_fomc_statement_2025-09-17",
        "source": "Federal Reserve Board / FOMC",
        "country": "US",
        "currency": "USD",
        "event_family": "FOMC",
        "reference_period": "2025-09-16/17",
        "meeting_date": "2025-09-17",
        "scheduled_release_utc": et_wall_to_utc(2025, 9, 17, 14, 0).isoformat(),
        "source_url_or_reference": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20250917a.htm",
        "implementation_note_url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20250917a1.htm",
        "press_conference_url": "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20250917.htm",
        "minutes_url": "https://www.federalreserve.gov/monetarypolicy/fomcminutes20250917.htm",
        "minutes_released": "2025-10-08",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
        "lookahead_known_at_release": "YES",
        "lookahead_later_revision_risk_if_using_this_archive": "NO",
        "vintage_enough": "YES",
        "notes": "Statement clock 2:00 p.m. EDT. Press conference and minutes are separate events. Rate decisions are not CES-style monthly revisions. Live re-fetch without a stored hash is UNCERTAIN; this proof uses a hashed excerpt.",
        "values": [
            {"event_name": "ff_target_lower", "actual_first_print": 4.00, "unit": "percent"},
            {"event_name": "ff_target_upper", "actual_first_print": 4.25, "unit": "percent"},
            {"event_name": "ff_target_change_bp", "actual_first_print": -25, "unit": "basis_points"},
            {"event_name": "ff_previous_lower", "actual_first_print": 4.25, "unit": "percent", "notes": "implied by 25bp cut to 4-4.25"},
            {"event_name": "ff_previous_upper", "actual_first_print": 4.50, "unit": "percent"},
        ],
    }
    fomc_oct = {
        "macro_event_id": "usd_fomc_statement_2025-10-29",
        "source": "Federal Reserve Board / FOMC",
        "country": "US",
        "currency": "USD",
        "event_family": "FOMC",
        "reference_period": "2025-10-28/29",
        "meeting_date": "2025-10-29",
        "scheduled_release_utc": et_wall_to_utc(2025, 10, 29, 14, 0).isoformat(),
        "source_url_or_reference": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20251029a.htm",
        "minutes_released": "2025-11-19",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
        "lookahead_known_at_release": "YES",
        "lookahead_later_revision_risk_if_using_this_archive": "NO",
        "vintage_enough": "YES",
        "notes": "Statement clock 2:00 p.m. EDT. Target 3.75-4.00. QT runoff ends Dec 1 per this statement — still the statement event, not a separate timestamp unless a later operational note is used. Live re-fetch without a stored hash is UNCERTAIN; this proof uses a hashed excerpt.",
        "values": [
            {"event_name": "ff_target_lower", "actual_first_print": 3.75, "unit": "percent"},
            {"event_name": "ff_target_upper", "actual_first_print": 4.00, "unit": "percent"},
            {"event_name": "ff_target_change_bp", "actual_first_print": -25, "unit": "basis_points"},
            {"event_name": "ff_previous_lower", "actual_first_print": 4.00, "unit": "percent"},
            {"event_name": "ff_previous_upper", "actual_first_print": 4.25, "unit": "percent"},
        ],
    }
    fomc_dec = {
        "macro_event_id": "usd_fomc_statement_2025-12-10",
        "source": "Federal Reserve Board / FOMC",
        "country": "US",
        "currency": "USD",
        "event_family": "FOMC",
        "reference_period": "2025-12-09/10",
        "meeting_date": "2025-12-10",
        "scheduled_release_utc": et_wall_to_utc(2025, 12, 10, 14, 0).isoformat(),
        "source_url_or_reference": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20251210a.htm",
        "minutes_released": "2025-12-30",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
        "lookahead_known_at_release": "YES",
        "lookahead_later_revision_risk_if_using_this_archive": "NO",
        "vintage_enough": "YES",
        "notes": "Statement clock 2:00 p.m. EST (not EDT). Target 3.50-3.75. Live re-fetch without a stored hash is UNCERTAIN; this proof uses a hashed excerpt.",
        "values": [
            {"event_name": "ff_target_lower", "actual_first_print": 3.50, "unit": "percent"},
            {"event_name": "ff_target_upper", "actual_first_print": 3.75, "unit": "percent"},
            {"event_name": "ff_target_change_bp", "actual_first_print": -25, "unit": "basis_points"},
            {"event_name": "ff_previous_lower", "actual_first_print": 3.75, "unit": "percent"},
            {"event_name": "ff_previous_upper", "actual_first_print": 4.00, "unit": "percent"},
        ],
    }
    return [cpi_sep, cpi_oct, cpi_dec, emp_aug, emp_sep, emp_nov, fomc_sep, fomc_oct, fomc_dec]


if __name__ == "__main__":
    payload = build_proof_sample()
    print("events", len(payload["events"]))
    print("artifacts", len(payload["copied_artifacts"]))
    print("cpi_sep_utc", payload["events"][0]["scheduled_release_utc"])
    print("fomc_sep_utc", payload["events"][6]["scheduled_release_utc"])
    print("fomc_dec_utc", payload["events"][8]["scheduled_release_utc"])
