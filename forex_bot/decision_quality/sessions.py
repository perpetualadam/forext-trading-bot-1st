"""Research-only London session buckets. Does not change live LIVE_* windows."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

# Inclusive London-local hour starts. End hour is exclusive except rollover wraps midnight.
SESSION_BUCKETS = (
    ("asia", 0, 7),
    ("london", 7, 12),
    ("london_ny_overlap", 12, 16),
    ("late_new_york", 16, 21),
    ("rollover_low_liquidity", 21, 24),
)


def london_local(at_utc: datetime) -> datetime:
    if at_utc.tzinfo is None:
        aware = at_utc.replace(tzinfo=timezone.utc)
    else:
        aware = at_utc.astimezone(timezone.utc)
    return aware.astimezone(LONDON)


def classify_session(at_utc: datetime) -> str:
    """Bucket from London wall clock. Times: Asia 00-07, London 07-12, overlap 12-16, late NY 16-21, rollover 21-24."""
    local = london_local(at_utc)
    hour = local.hour
    for name, start, end in SESSION_BUCKETS:
        if start <= hour < end:
            return name
    return "rollover_low_liquidity"


def hour_london(at_utc: datetime) -> int:
    return int(london_local(at_utc).hour)


def hour_utc(at_utc: datetime) -> int:
    if at_utc.tzinfo is None:
        return int(at_utc.hour)
    return int(at_utc.astimezone(timezone.utc).hour)
