"""Build the 2025 official first-print dataset. Research-only. No production imports."""

from __future__ import annotations

import argparse
from pathlib import Path

from forex_bot.decision_quality.macro_first_print.catalog import (
    CatalogEntry,
    DEFAULT_YEAR_TEXT,
    load_official_2025_catalog,
)
from forex_bot.decision_quality.macro_first_print.fetch import fetch_url, paced_sleep
from forex_bot.decision_quality.macro_first_print.parse_cpi import parse_cpi_release
from forex_bot.decision_quality.macro_first_print.parse_empsit import parse_empsit_release
from forex_bot.decision_quality.macro_first_print.schema import NormalizedEvent
from forex_bot.decision_quality.macro_first_print.store import (
    DEFAULT_ROOT,
    canonical_raw_name,
    looks_like_official_release,
    official_text_name,
    normalized_dir,
    raw_dir,
    utc_now,
    write_events_csv,
    write_events_json,
    write_raw_release,
)
from forex_bot.decision_quality.macro_first_print.validate import counts, quality_checks


def assemble_event(entry: CatalogEntry, parsed: dict, stored) -> NormalizedEvent:
    status = parsed.get("validation_status") or "FAILED"
    notes = [n for n in (parsed.get("notes"), entry.official_note) if n]
    ref = parsed.get("reference_period") or entry.reference_period
    if parsed.get("reference_period") and entry.reference_period and parsed["reference_period"] != entry.reference_period:
        status = "AMBIGUOUS"
        notes.append("reference_period_mismatch")
    embargo = parsed.get("embargo_utc")
    if embargo and entry.scheduled_time_utc:
        if embargo[:19] != entry.scheduled_time_utc[:19]:
            notes.append("embargo_clock_differs_from_schedule")
    event_id = f"{entry.event_type}_{ref}_{entry.release_date}"
    return NormalizedEvent(
        provider="BLS_NEWS_RELEASE_ARCHIVE",
        source_agency="BLS",
        event_id=event_id,
        event_type=entry.event_type,
        release_name=parsed.get("release_name") or entry.release_name,
        reference_period=ref or None,
        scheduled_time_local=entry.scheduled_time_local,
        timezone=entry.timezone,
        scheduled_time_utc=entry.scheduled_time_utc,
        published_date=entry.release_date,
        release_number=parsed.get("release_number"),
        source_url=entry.source_url,
        retrieved_at=None if stored is None else _retrieved(stored),
        raw_file=None if stored is None else stored.body_path.as_posix(),
        raw_sha256=None if stored is None else stored.sha256,
        validation_status=status,
        extraction_locator=parsed.get("extraction_locator"),
        headline_mom_first_print=parsed.get("headline_mom_first_print"),
        headline_yoy_first_print=parsed.get("headline_yoy_first_print"),
        core_mom_first_print=parsed.get("core_mom_first_print"),
        core_yoy_first_print=parsed.get("core_yoy_first_print"),
        previous_headline_mom_as_known=parsed.get("previous_headline_mom_as_known"),
        previous_headline_yoy_as_known=parsed.get("previous_headline_yoy_as_known"),
        nfp_first_print=parsed.get("nfp_first_print"),
        unemployment_rate_first_print=parsed.get("unemployment_rate_first_print"),
        ahe_mom_first_print=parsed.get("ahe_mom_first_print"),
        ahe_yoy_first_print=parsed.get("ahe_yoy_first_print"),
        participation_rate_first_print=parsed.get("participation_rate_first_print"),
        previous_nfp_as_presented=parsed.get("previous_nfp_as_presented"),
        previous_nfp_revision=parsed.get("previous_nfp_revision"),
        two_month_nfp_revision=parsed.get("two_month_nfp_revision"),
        notes=";".join(notes) if notes else None,
    )


def _retrieved(stored) -> str | None:
    meta = stored.meta_path
    if meta.exists():
        import json

        return json.loads(meta.read_text(encoding="utf-8")).get("retrieved_at_utc")
    return None


def parse_raw(event_type: str, raw: str) -> dict:
    if event_type == "CPI":
        return parse_cpi_release(raw)
    return parse_empsit_release(raw)


def _existing_official(dest: Path, entry: CatalogEntry):
    from forex_bot.decision_quality.macro_first_print.store import StoredRaw, sha256_bytes

    for name in (
        official_text_name(entry.event_type, entry.release_date),
        canonical_raw_name(entry.event_type, entry.release_date),
    ):
        path = dest / name
        if not path.exists():
            continue
        body = path.read_bytes()
        if not looks_like_official_release(body):
            continue
        return StoredRaw(path, dest / f"{name}.meta.json", sha256_bytes(body), 200, True, False), body
    return None, None


def load_or_fetch_entry(entry: CatalogEntry, *, root: Path, fetch_missing: bool, session=None):
    dest = raw_dir(root, entry.event_type)
    stored, body = _existing_official(dest, entry)
    if stored is not None:
        return stored, body
    if not fetch_missing:
        return None, None
    result = fetch_url(entry.source_url, session=session)
    name = canonical_raw_name(entry.event_type, entry.release_date)
    stored = write_raw_release(
        dest_dir=dest,
        filename=name,
        body=result.content,
        source_url=result.final_url or entry.source_url,
        http_status=result.status,
        content_type=result.content_type,
        publication_date=entry.release_date,
        release_number=None,
        retrieved_at=utc_now(),
    )
    return stored, result.content


def build_2025(*, root: Path | None = None, fetch_missing: bool = False, year_text: str | None = None) -> dict:
    root = Path(root or DEFAULT_ROOT)
    catalog = load_official_2025_catalog(year_text)
    events: list[NormalizedEvent] = []
    fetch_log: list[dict] = []
    for entry in catalog:
        stored, body = load_or_fetch_entry(entry, root=root, fetch_missing=fetch_missing)
        if body is None:
            parsed = {"validation_status": "FAILED", "notes": "raw_missing"}
            events.append(assemble_event(entry, parsed, None))
            fetch_log.append({"url": entry.source_url, "status": "missing_local"})
            continue
        if stored and not stored.reused and fetch_missing:
            paced_sleep()
        text = body.decode("utf-8", errors="replace")
        if stored is not None and hasattr(stored, "http_status") and stored.http_status not in (0, 200) and not stored.reused:
            parsed = {"validation_status": "FAILED", "notes": f"http_{stored.http_status}"}
        elif "page not found" in text.lower() and "CONSUMER PRICE INDEX" not in text and "EMPLOYMENT SITUATION" not in text:
            parsed = {"validation_status": "FAILED", "notes": "archive_not_found"}
        else:
            parsed = parse_raw(entry.event_type, text)
        events.append(assemble_event(entry, parsed, stored))
        fetch_log.append(
            {
                "url": entry.source_url,
                "sha256": None if stored is None else stored.sha256,
                "reused": None if stored is None else stored.reused,
            }
        )
    events.sort(key=lambda e: (e.published_date or "", e.event_type))
    out_dir = normalized_dir(root)
    csv_path = out_dir / "events_2025.csv"
    json_path = out_dir / "events_2025.json"
    write_events_csv(csv_path, events)
    write_events_json(json_path, events)
    return {
        "events": events,
        "catalog": catalog,
        "quality": quality_checks(events),
        "counts": counts(events),
        "csv_path": csv_path,
        "json_path": json_path,
        "fetch_log": fetch_log,
        "year_text": str(DEFAULT_YEAR_TEXT),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build 2025 official BLS first-print research dataset")
    p.add_argument("--fetch", action="store_true", help="Download missing official archive HTML")
    p.add_argument("--root", default=str(DEFAULT_ROOT))
    args = p.parse_args(argv)
    result = build_2025(root=Path(args.root), fetch_missing=args.fetch)
    c = result["counts"]
    print(f"CPI {c['found_cpi']}/{c['expected_cpi']} verified={c['verified_cpi']} ambiguous={c['ambiguous_cpi']}")
    print(
        f"EMP {c['found_employment']}/{c['expected_employment']} "
        f"verified={c['verified_employment']} ambiguous={c['ambiguous_employment']}"
    )
    print(f"wrote {result['csv_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
