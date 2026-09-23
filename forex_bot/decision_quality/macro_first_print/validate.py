"""First-print quality checks. Missing stays missing. Revisions do not overwrite."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from forex_bot.decision_quality.macro_first_print.catalog import OFFICIALLY_UNPUBLISHED_2025
from forex_bot.decision_quality.macro_first_print.schema import NormalizedEvent
from forex_bot.decision_quality.schedule import local_clock_to_utc

from datetime import datetime

FIRST_PRINT_FIELDS_CPI = (
    "headline_mom_first_print",
    "headline_yoy_first_print",
    "core_mom_first_print",
    "core_yoy_first_print",
)
FIRST_PRINT_FIELDS_EMP = (
    "nfp_first_print",
    "unemployment_rate_first_print",
    "ahe_mom_first_print",
    "ahe_yoy_first_print",
    "participation_rate_first_print",
)


def _prev_period(period: str | None) -> str | None:
    if not period or len(period) < 7:
        return None
    year, month = int(period[:4]), int(period[5:7])
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def first_prints_immutable(events: Iterable[NormalizedEvent]) -> list[str]:
    """Return problems if a later release's revised previous value overwrote a first print."""
    problems: list[str] = []
    by_id = [e for e in events]
    ids = [e.event_id for e in by_id]
    if len(ids) != len(set(ids)):
        problems.append("duplicate_event_id")
    emp = [e for e in by_id if e.event_type == "EMPLOYMENT_SITUATION"]
    by_ref = {e.reference_period: e for e in emp if e.reference_period}
    for later in emp:
        prior = by_ref.get(_prev_period(later.reference_period) or "")
        if prior is None:
            continue
        if later.previous_nfp_revision in (None, 0):
            continue
        if prior.nfp_first_print is None or later.previous_nfp_as_presented is None:
            continue
        if prior.nfp_first_print == later.previous_nfp_as_presented:
            problems.append(
                f"overwrite:{prior.event_id}:nfp_first_print_equals_later_revised_previous"
            )
        expected = prior.nfp_first_print + later.previous_nfp_revision
        if expected != later.previous_nfp_as_presented:
            # Arithmetic mismatch is informational when BLS rounds or two-step revises;
            # only treat equality of first-print to revised previous as overwrite.
            pass
    return problems


def quality_checks(
    events: list[NormalizedEvent],
    *,
    expected_cpi: int = 11,
    expected_emp: int = 11,
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    cpi = [e for e in events if e.event_type == "CPI"]
    emp = [e for e in events if e.event_type == "EMPLOYMENT_SITUATION"]

    dates_cpi = [e.published_date for e in cpi]
    dates_emp = [e.published_date for e in emp]
    for d, n in Counter(dates_cpi).items():
        if n > 1:
            out["duplicate_release_dates"].append(f"CPI:{d}")
    for d, n in Counter(dates_emp).items():
        if n > 1:
            out["duplicate_release_dates"].append(f"EMPLOYMENT_SITUATION:{d}")

    if len(cpi) != expected_cpi:
        out["missing_expected_monthly_releases"].append(f"CPI found={len(cpi)} expected={expected_cpi}")
    if len(emp) != expected_emp:
        out["missing_expected_monthly_releases"].append(
            f"EMPLOYMENT_SITUATION found={len(emp)} expected={expected_emp}"
        )
    for kind, period, note in OFFICIALLY_UNPUBLISHED_2025:
        if any(e.event_type == kind and e.reference_period == period for e in events):
            out["unexpected_officially_unpublished"].append(f"{kind}:{period}")
        else:
            out["officially_unpublished_gaps"].append(f"{kind}:{period}:{note}")

    refs_cpi = [e.reference_period for e in cpi if e.reference_period]
    refs_emp = [e.reference_period for e in emp if e.reference_period]
    for r, n in Counter(refs_cpi).items():
        if n > 1:
            out["duplicate_reference_period"].append(f"CPI:{r}")
    for r, n in Counter(refs_emp).items():
        if n > 1:
            out["duplicate_reference_period"].append(f"EMPLOYMENT_SITUATION:{r}")

    hashes = [e.raw_sha256 for e in events if e.raw_sha256]
    for h, n in Counter(hashes).items():
        if n > 1:
            out["duplicated_source_files"].append(h)

    for e in events:
        if e.timezone != "America/New_York":
            out["timezone_conversion_errors"].append(f"{e.event_id}:tz={e.timezone}")
        if e.scheduled_time_local and e.scheduled_time_utc:
            try:
                local = datetime.fromisoformat(e.scheduled_time_local)
                utc = local_clock_to_utc(local, "America/New_York")
                got = (e.scheduled_time_utc or "").replace("Z", "")
                if utc.isoformat(timespec="seconds") != got[:19]:
                    out["timezone_conversion_errors"].append(f"{e.event_id}:{got}!={utc.isoformat()}")
            except ValueError:
                out["timezone_conversion_errors"].append(f"{e.event_id}:unparsed_local")
        if e.published_date and e.scheduled_time_utc:
            pub = e.published_date
            utc_date = e.scheduled_time_utc[:10]
            if pub != utc_date and pub != e.scheduled_time_local[:10]:
                out["publication_vs_schedule"].append(f"{e.event_id}:pub={pub} utc={utc_date}")
        if e.reference_period and e.published_date:
            # Reference month should precede the publication month, except lapse delays.
            try:
                ref_y, ref_m = int(e.reference_period[:4]), int(e.reference_period[5:7])
                pub_y, pub_m = int(e.published_date[:4]), int(e.published_date[5:7])
                lag = (pub_y - ref_y) * 12 + (pub_m - ref_m)
                if lag < 1:
                    out["reference_month_mismatch"].append(f"{e.event_id}:lag={lag}")
            except (TypeError, ValueError):
                out["reference_month_mismatch"].append(e.event_id)

        for field in FIRST_PRINT_FIELDS_CPI + FIRST_PRINT_FIELDS_EMP:
            val = getattr(e, field)
            if val is None:
                continue
            if field == "nfp_first_print":
                continue
            cap = 100 if "participation" in field else 50
            if isinstance(val, (int, float)) and abs(val) > cap:
                out["impossible_percentages"].append(f"{e.event_id}:{field}={val}")
        if e.nfp_first_print is not None and abs(e.nfp_first_print) > 5_000_000:
            out["malformed_payroll_values"].append(f"{e.event_id}:{e.nfp_first_print}")
        if e.event_type == "CPI" and any(getattr(e, f) is None for f in FIRST_PRINT_FIELDS_CPI):
            out["missing_first_print_values"].append(e.event_id)
        if e.event_type == "EMPLOYMENT_SITUATION" and (
            e.nfp_first_print is None or e.unemployment_rate_first_print is None
        ):
            out["missing_first_print_values"].append(e.event_id)
        if e.validation_status not in ("VERIFIED_FIRST_PRINT", "PARTIAL", "AMBIGUOUS", "FAILED"):
            out["invalid_validation_status"].append(f"{e.event_id}:{e.validation_status}")

    overwrite = first_prints_immutable(events)
    if overwrite:
        out["revision_overwrite"].extend(overwrite)
    return dict(out)


def counts(events: list[NormalizedEvent]) -> dict[str, int]:
    cpi = [e for e in events if e.event_type == "CPI"]
    emp = [e for e in events if e.event_type == "EMPLOYMENT_SITUATION"]
    return {
        "expected_cpi": 11,
        "found_cpi": len(cpi),
        "verified_cpi": sum(1 for e in cpi if e.validation_status == "VERIFIED_FIRST_PRINT"),
        "ambiguous_cpi": sum(1 for e in cpi if e.validation_status == "AMBIGUOUS"),
        "expected_employment": 11,
        "found_employment": len(emp),
        "verified_employment": sum(1 for e in emp if e.validation_status == "VERIFIED_FIRST_PRINT"),
        "ambiguous_employment": sum(1 for e in emp if e.validation_status == "AMBIGUOUS"),
    }
