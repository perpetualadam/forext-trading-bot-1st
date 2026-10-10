"""FX trading-day convention for Stage G.4. Clarification, not a Stage G rewrite."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from forex_bot.research.adaptive_ensemble.g4_gaps import BAR, BLOCKING
from forex_bot.research.adaptive_ensemble.protocol import integrity_hash

NY = ZoneInfo("America/New_York")
CONVENTION_ID = "fx_trading_day_ny1700_v1"
REQUIRED_SESSIONS = 40


def ny_1700_utc(day: date) -> datetime:
    local = datetime(day.year, day.month, day.day, 17, 0, tzinfo=NY)
    return local.astimezone(timezone.utc).replace(microsecond=0)


def session_bounds(label: date) -> tuple[datetime, datetime]:
    """Session labeled by the New York date of its 17:00 close.

    Monday's session starts Sunday 17:00 New York. Other weekdays start at
    17:00 New York on the previous calendar date. The close instant is exclusive.
    """
    if label.weekday() >= 5:
        raise ValueError("weekend is not a session label")
    start_day = label - timedelta(days=1)
    return ny_1700_utc(start_day), ny_1700_utc(label)


def session_label(ts: datetime) -> date | None:
    local = ts.astimezone(NY)
    clock = (local.hour, local.minute, local.second)
    if local.weekday() == 5 or (local.weekday() == 6 and clock < (17, 0, 0)):
        return None
    if local.weekday() == 4 and clock >= (17, 0, 0):
        return None
    if clock >= (17, 0, 0):
        return local.date() + timedelta(days=1)
    return local.date()


def definition_document() -> dict[str, Any]:
    body: dict[str, Any] = {
        "convention_id": CONVENTION_ID,
        "status": "CLARIFICATION_NOT_IN_FROZEN_STAGE_G_PROTOCOL",
        "timezone": "America/New_York",
        "boundary": "17:00 local, exclusive end",
        "stored_as": "UTC",
        "monday_open": "Sunday 17:00 America/New_York",
        "weekend_close": "Friday 17:00 America/New_York",
        "dst": "America/New_York rules. 17:00 is 21:00 UTC in EDT and 22:00 UTC in EST.",
        "not_a_weekday_count": True,
        "not_288_bars": True,
        "complete_rule": (
            "A weekday session is COMPLETE only when the acquisition window covers "
            "[start, end), no blocking gap intersects the session, bid/ask on returned "
            "bars is valid, and every returned bar has a fresh side-aware GBP quote. "
            "A source omission of at most 60 minutes is quarantined and does not by "
            "itself reject the session."
        ),
        "partial_rule": "The first and last sessions are PARTIAL_BOUNDARY when the download does not cover them.",
        "minimum_complete_common_sessions": REQUIRED_SESSIONS,
        "threshold_was_not_reduced": True,
    }
    body["integrity_hash"] = integrity_hash(body)
    return body


def _blocks(gap: dict[str, Any], start: datetime, end: datetime) -> bool:
    if gap.get("classification") not in BLOCKING:
        return False
    prev = datetime.fromisoformat(str(gap["previous"]))
    nxt = datetime.fromisoformat(str(gap["next"]))
    missing_start = prev + BAR
    return missing_start < end and start < nxt


def candidate_labels(request_start: datetime, request_end: datetime) -> list[date]:
    labels: list[date] = []
    day = request_start.astimezone(NY).date() - timedelta(days=2)
    last = request_end.astimezone(NY).date() + timedelta(days=2)
    while day <= last:
        if day.weekday() < 5:
            start, end = session_bounds(day)
            if start < request_end and end > request_start:
                labels.append(day)
        day += timedelta(days=1)
    return labels


def closure_dates(request_start: datetime, request_end: datetime) -> list[str]:
    found: list[str] = []
    day = request_start.astimezone(NY).date()
    last = request_end.astimezone(NY).date()
    while day <= last:
        if day.weekday() >= 5:
            found.append(day.isoformat())
        day += timedelta(days=1)
    return found


def build_session_report(
    *,
    request_start: datetime,
    request_end: datetime,
    times_by_pair: dict[str, list[datetime]],
    gaps_by_pair: dict[str, list[dict[str, Any]]],
    conversion_failures: dict[str, set[str]],
) -> dict[str, Any]:
    labels = candidate_labels(request_start, request_end)
    per_pair: dict[str, list[dict[str, Any]]] = {}
    for pair, times in times_by_pair.items():
        rows: list[dict[str, Any]] = []
        gaps = gaps_by_pair.get(pair, [])
        failed = conversion_failures.get(pair, set())
        for label in labels:
            start, end = session_bounds(label)
            present = [item for item in times if start <= item < end]
            if start < request_start or end > request_end:
                status = "PARTIAL_BOUNDARY"
                reason = "acquisition_window"
            elif not present:
                status = "DATA_QUALITY_BLOCKED"
                reason = "no_bars"
            elif any(_blocks(gap, start, end) for gap in gaps):
                status = "DATA_QUALITY_BLOCKED"
                reason = "blocking_gap"
            elif label.isoformat() in failed:
                status = "DATA_QUALITY_BLOCKED"
                reason = "conversion"
            else:
                status = "COMPLETE"
                reason = "covered"
            rows.append(
                {
                    "session": label.isoformat(),
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "bars": len(present),
                    "status": status,
                    "reason": reason,
                }
            )
        per_pair[pair] = rows
    common: list[dict[str, Any]] = []
    for idx, label in enumerate(labels):
        by_pair = {pair: per_pair[pair][idx]["status"] for pair in times_by_pair}
        if any(value == "PARTIAL_BOUNDARY" for value in by_pair.values()):
            status = "PARTIAL_BOUNDARY"
        elif any(value != "COMPLETE" for value in by_pair.values()):
            status = "DATA_QUALITY_BLOCKED"
        else:
            status = "COMPLETE"
        common.append({"session": label.isoformat(), "status": status, "by_pair": by_pair})
    complete_common = sum(1 for row in common if row["status"] == "COMPLETE")
    definition = definition_document()
    return {
        "convention_id": CONVENTION_ID,
        "definition_hash": definition["integrity_hash"],
        "definition": definition,
        "required_complete_sessions": REQUIRED_SESSIONS,
        "threshold_reduced": False,
        "candidate_sessions": len(labels),
        "complete_by_pair": {
            pair: sum(1 for row in rows if row["status"] == "COMPLETE") for pair, rows in per_pair.items()
        },
        "complete_common_sessions": complete_common,
        "partial_sessions": sum(1 for row in common if row["status"] == "PARTIAL_BOUNDARY"),
        "blocked_sessions": sum(1 for row in common if row["status"] == "DATA_QUALITY_BLOCKED"),
        "remaining_to_40": max(0, REQUIRED_SESSIONS - complete_common),
        "expected_closures": closure_dates(request_start, request_end),
        "per_pair": per_pair,
        "common": common,
        "duration_status": "INSUFFICIENT_INDEPENDENT_DURATION" if complete_common < REQUIRED_SESSIONS else "ok",
    }
