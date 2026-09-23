"""Point-in-time validation. Marketing names are not accepted as proof."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from forex_bot.decision_quality.trading_economics.schema import (
    NormalizedEvent,
    forecast_consensus_raw,
    normalize_record,
    te_forecast_raw,
)
from forex_bot.decision_quality.trading_economics.timestamps import parse_provider_datetime, to_utc_aware


@dataclass
class CheckResult:
    code: str
    passed: bool
    evidence: str
    status: str  # PASS | FAIL | UNKNOWN | INSUFFICIENT


@dataclass
class PitVerdict:
    event_id: str | None
    checks: list[CheckResult] = field(default_factory=list)
    consensus_pre_release_ok: bool = False
    first_print_actual_ok: bool = False
    previous_as_known_ok: bool = False
    last_update_is_vintage: bool = False
    pit_endpoint_differs: bool | None = None
    multiple_snapshots_available: bool = False
    vintage_ok: bool = False
    duplicate_event_ids: tuple[str, ...] = ()
    timestamp_issues: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(c) for c in self.checks]
        return payload


def _norm(record: dict[str, Any] | NormalizedEvent) -> NormalizedEvent:
    if isinstance(record, NormalizedEvent):
        return record
    return normalize_record(record)


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _add(checks: list[CheckResult], code: str, passed: bool, evidence: str, status: str | None = None) -> None:
    checks.append(
        CheckResult(
            code=code,
            passed=passed,
            evidence=evidence,
            status=status or ("PASS" if passed else "FAIL"),
        )
    )


def classify_duplicates(records: list[NormalizedEvent]) -> tuple[str, ...]:
    seen: dict[str, int] = {}
    dups: list[str] = []
    for row in records:
        eid = str(row.event_id or "")
        if not eid:
            continue
        seen[eid] = seen.get(eid, 0) + 1
    for eid, n in seen.items():
        if n > 1:
            dups.append(eid)
    return tuple(sorted(dups))


def validate_single_row(record: dict[str, Any] | NormalizedEvent) -> PitVerdict:
    return validate_event_vintages([record])


def validate_event_vintages(
    records: list[dict[str, Any] | NormalizedEvent],
    *,
    pit_payload: list[dict[str, Any]] | None = None,
    ordinary_payload: list[dict[str, Any]] | None = None,
) -> PitVerdict:
    """Evaluate whether returned rows demonstrate historical vintage integrity.

    A single ordinary calendar row is not sufficient. The official PIT page
    uses the same URL as a historical country/indicator date-range query.
    """
    rows = [_norm(r) for r in records]
    checks: list[CheckResult] = []
    if not rows:
        verdict = PitVerdict(event_id=None)
        _add(checks, "A_consensus_pre_release", False, "no records", "INSUFFICIENT")
        verdict.checks = checks
        return verdict

    event_id = rows[0].event_id
    dups = classify_duplicates(rows)
    ts_issues: list[str] = []
    for row in rows:
        ts_issues.extend(parse_provider_datetime(row.scheduled_time_raw).issues)
        ts_issues.extend(parse_provider_datetime(row.last_update_raw).issues)

    # A. Consensus known before scheduled release?
    consensus_ok = False
    for row in rows:
        forecast = row.forecast_consensus
        te = row.te_forecast
        sched = to_utc_aware(row.scheduled_time_raw)
        last = to_utc_aware(row.last_update_raw)
        if not _present(forecast):
            continue
        if not _present(row.actual) and last is not None and sched is not None and last < sched:
            consensus_ok = True
            _add(
                checks,
                "A_consensus_pre_release",
                True,
                "Forecast present while Actual empty and LastUpdate < scheduled Date",
            )
            break
    if not consensus_ok:
        has_forecast = any(_present(r.forecast_consensus) for r in rows)
        used_te = any(_present(te_forecast_raw(r.to_dict())) for r in rows) and not has_forecast
        if used_te:
            _add(
                checks,
                "A_consensus_pre_release",
                False,
                "TEForecast present but Forecast missing — TEForecast is not consensus",
            )
        elif has_forecast:
            _add(
                checks,
                "A_consensus_pre_release",
                False,
                "Forecast is present but there is no timestamp proving it existed before Date. "
                "LastUpdate is documented as last update/insertion, not consensus-asof.",
                "INSUFFICIENT",
            )
        else:
            _add(checks, "A_consensus_pre_release", False, "Forecast missing", "INSUFFICIENT")

    # B. First-print actual vs today's revised actual.
    first_print_ok = False
    actuals = [r.actual for r in rows if _present(r.actual)]
    distinct_actuals = {str(a) for a in actuals}
    if len(distinct_actuals) >= 2:
        first_print_ok = True
        _add(
            checks,
            "B_first_print_actual",
            True,
            "Multiple snapshots of the same event show different Actual values; earliest Actual can be first print",
        )
    elif actuals:
        _add(
            checks,
            "B_first_print_actual",
            False,
            "Schema documents Actual as 'Latest released value'. A single snapshot cannot prove first print.",
            "INSUFFICIENT",
        )
    else:
        _add(checks, "B_first_print_actual", False, "Actual missing", "INSUFFICIENT")

    # C. Previous as-known vs subsequently revised previous.
    previous_ok = False
    if any(_present(r.revised) and _present(r.previous) and r.revised != r.previous for r in rows):
        _add(
            checks,
            "C_previous_as_known",
            False,
            "Revised differs from Previous. Schema: Previous is 'after revision if applicable'; "
            "Revised is the pre-revision previous. Previous is therefore not as-known-at-time.",
        )
    elif any(_present(r.previous) for r in rows):
        _add(
            checks,
            "C_previous_as_known",
            False,
            "Previous present but schema says it may already include later revision. Not proven as-known.",
            "INSUFFICIENT",
        )
    else:
        _add(checks, "C_previous_as_known", False, "Previous missing", "INSUFFICIENT")

    # D. LastUpdate as vintage clock.
    last_is_vintage = False
    _add(
        checks,
        "D_last_update_vintage",
        False,
        "Official schema: LastUpdate is 'most recent update or insertion', not a consensus vintage.",
        "INSUFFICIENT",
    )

    # E. Distinct PIT endpoint vs ordinary historical calendar.
    pit_differs: bool | None
    if pit_payload is not None and ordinary_payload is not None:
        pit_differs = pit_payload != ordinary_payload
        _add(
            checks,
            "E_pit_endpoint_differs",
            pit_differs,
            "Compared two retrieved payloads for the same event window."
            if pit_differs
            else "PIT-labelled payload equals ordinary historical calendar payload.",
        )
    else:
        pit_differs = None
        _add(
            checks,
            "E_pit_endpoint_differs",
            False,
            "Official PIT page documents the same URL as "
            "/calendar/country/{country}/indicator/{indicator}/{initDate}/{endDate}. "
            "No distinct REST path was found. Comparison not yet run on live payloads.",
            "UNKNOWN",
        )

    # F. Multiple historical snapshots of the same CalendarId.
    retrieved = {r.retrieved_at for r in rows if r.retrieved_at}
    multi_snapshots = len(retrieved) > 1 or (len(rows) > 1 and len(distinct_actuals) > 1)
    _add(
        checks,
        "F_multiple_snapshots",
        multi_snapshots,
        "Multiple retrieved vintages observed."
        if multi_snapshots
        else "No documented as-of parameter. /calendar/calendarid/{id} returns the current row. "
        "Multiple historical snapshots are not demonstrated.",
        "PASS" if multi_snapshots else "UNKNOWN",
    )

    # G. Distinguish pre-release consensus / first print / later revision.
    can_split = consensus_ok and first_print_ok
    _add(
        checks,
        "G_vintage_layers",
        can_split,
        "Pre-release Forecast and a later distinct Actual are both evidenced."
        if can_split
        else "Cannot separate pre-release consensus, first-print actual, and later revision from these rows.",
        "PASS" if can_split else "INSUFFICIENT",
    )

    # TEForecast substitution guard (always recorded).
    te_used_as_consensus = False
    for raw in records:
        if isinstance(raw, dict):
            fc = forecast_consensus_raw(raw)
            te = te_forecast_raw(raw)
            if (fc is None or str(fc).strip() == "") and _present(te):
                te_used_as_consensus = True
    _add(
        checks,
        "teforecast_not_consensus",
        not te_used_as_consensus or any(_present(r.forecast_consensus) for r in rows),
        "TEForecast is stored separately and is not Forecast.",
    )

    vintage_ok = consensus_ok and first_print_ok
    return PitVerdict(
        event_id=str(event_id) if event_id is not None else None,
        checks=checks,
        consensus_pre_release_ok=consensus_ok,
        first_print_actual_ok=first_print_ok,
        previous_as_known_ok=previous_ok,
        last_update_is_vintage=last_is_vintage,
        pit_endpoint_differs=pit_differs,
        multiple_snapshots_available=multi_snapshots,
        vintage_ok=vintage_ok,
        duplicate_event_ids=dups,
        timestamp_issues=tuple(sorted(set(ts_issues))),
    )


def local_family_match(event_name: str | None, category: str | None, hints: tuple[str, ...]) -> bool:
    blob = f"{event_name or ''} {category or ''}".lower()
    return any(h in blob for h in hints)
