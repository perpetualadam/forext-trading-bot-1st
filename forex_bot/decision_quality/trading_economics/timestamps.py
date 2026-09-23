"""Explicit UTC conversion for provider timestamps. No live FX join."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

# Schema docs say Date is UTC. That is a documented claim, not a measured fact.
DOCUMENTED_TZ_CLAIM = "UTC"


@dataclass(frozen=True)
class TimestampReport:
    raw: str | None
    utc: str | None
    assumed_timezone: str | None
    issues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_offset(text: str) -> bool:
    s = text.strip()
    if s.endswith("Z") or s.endswith("z"):
        return True
    if len(s) >= 6 and (s[-6] in "+-") and s[-3] == ":":
        return True
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
        return True
    return False


def parse_provider_datetime(raw: str | None) -> TimestampReport:
    if raw is None or str(raw).strip() == "":
        return TimestampReport(raw=raw, utc=None, assumed_timezone=None, issues=("missing_timestamp",))
    text = str(raw).strip()
    issues: list[str] = []
    assumed = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return TimestampReport(raw=text, utc=None, assumed_timezone=None, issues=("unparseable_timestamp",))
    if parsed.tzinfo is None:
        if not _has_offset(text):
            issues.append("naive_datetime_no_offset")
            issues.append("timezone_assumed_from_documentation_utc_claim")
            assumed = DOCUMENTED_TZ_CLAIM
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            issues.append("offset_parse_failed")
            return TimestampReport(raw=text, utc=None, assumed_timezone=None, issues=tuple(issues))
    else:
        assumed = None
    utc = parsed.astimezone(timezone.utc)
    if utc.dst() is not None:
        # UTC itself has no DST; flag only if the original offset is not UTC
        # and lands on a US DST transition while naive.
        pass
    if "naive_datetime_no_offset" in issues:
        # DST cannot be resolved without a named zone.
        issues.append("dst_ambiguity_unresolved_without_named_zone")
    return TimestampReport(
        raw=text,
        utc=utc.isoformat().replace("+00:00", "Z"),
        assumed_timezone=assumed,
        issues=tuple(issues),
    )


def scheduled_utc(event: Any) -> TimestampReport:
    raw = getattr(event, "scheduled_time_raw", None)
    if isinstance(event, dict):
        raw = event.get("scheduled_time_raw") or event.get("Date")
    return parse_provider_datetime(raw)


def last_update_utc(event: Any) -> TimestampReport:
    raw = getattr(event, "last_update_raw", None)
    if isinstance(event, dict):
        raw = event.get("last_update_raw") or event.get("LastUpdate")
    return parse_provider_datetime(raw)


def to_utc_aware(raw: str | None) -> datetime | None:
    report = parse_provider_datetime(raw)
    if not report.utc:
        return None
    return datetime.fromisoformat(report.utc.replace("Z", "+00:00"))


def us_eastern_release_clock(utc: datetime) -> datetime:
    """Research helper only — convert a UTC instant to America/New_York. Not a live join."""
    if utc.tzinfo is None:
        raise ValueError("refusing naive datetime; convert to UTC first")
    return utc.astimezone(ZoneInfo("America/New_York"))
