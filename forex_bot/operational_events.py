"""
Append-only, bounded ring of operational state transitions (not every poll).

First observation establishes a baseline without emitting an event; subsequent calls only append
when :func:`~forex_bot.operational_state.derive_operational_state` changes.

Optional: mirror each transition to PostgreSQL (``PERSIST_OPERATIONAL_EVENTS``) and optionally
hydrate the deque from the last N rows on startup (``LOAD_OPERATIONAL_EVENTS_FROM_DB``).
"""

from __future__ import annotations

import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any

from forex_bot.operational_state import OperationalState, derive_operational_state, operational_state_payload

logger = logging.getLogger(__name__)

_last_recorded: OperationalState | None = None


def _max_len() -> int:
    raw = (os.getenv("OPERATIONAL_EVENT_MAX") or "100").strip()
    try:
        n = int(raw or "100")
        return max(1, min(n, 10_000))
    except ValueError:
        return 100


def _persist_enabled() -> bool:
    return (os.getenv("PERSIST_OPERATIONAL_EVENTS") or "").strip().lower() in ("1", "true", "yes", "on")


def _load_cache_from_db_enabled() -> bool:
    return (os.getenv("LOAD_OPERATIONAL_EVENTS_FROM_DB") or "").strip().lower() in ("1", "true", "yes", "on")


_events: deque[dict[str, Any]] = deque(maxlen=_max_len())


def _ensure_deque() -> deque[dict[str, Any]]:
    global _events
    m = _max_len()
    if _events.maxlen != m:
        _events = deque(_events, maxlen=m)
    return _events


def get_operational_events() -> list[dict[str, Any]]:
    """Newest events are last (append order). May include ``id`` when rows were loaded from DB."""
    return list(_ensure_deque())


def reset_operational_events_for_tests() -> None:
    """Clear buffer and baseline (tests only)."""
    global _last_recorded, _events
    _last_recorded = None
    _events = deque(maxlen=_max_len())


def _persist_event_to_db(ev: dict[str, Any]) -> None:
    if not _persist_enabled():
        return
    from forex_bot.database import append_operational_event_log

    append_operational_event_log(
        ts_utc_iso=ev["ts_utc"],
        from_state=ev.get("from_state"),
        to_state=ev["to_state"],
        detail=str(ev.get("detail") or ""),
    )


def load_operational_events_cache_from_db() -> None:
    """
    After DB connect and ``lifespan_phase`` is ``running``, optionally refill deque and baseline.

    Prevents spurious transitions vs last persisted ``to_state`` when the process restarts.
    """
    global _last_recorded, _events
    if not _load_cache_from_db_enabled():
        return
    from forex_bot.database import fetch_recent_operational_event_logs

    rows = fetch_recent_operational_event_logs(_max_len())
    if not rows:
        logger.info("operational events: no rows to load from DB")
        return
    out: list[dict[str, Any]] = []
    for r in rows:
        item = {
            "ts_utc": r["ts_utc"],
            "from_state": r.get("from_state"),
            "to_state": r["to_state"],
            "detail": r.get("detail") or "",
        }
        if r.get("id") is not None:
            item["id"] = r["id"]
        out.append(item)
    _events = deque(out, maxlen=_max_len())
    try:
        _last_recorded = OperationalState(rows[-1]["to_state"])
    except ValueError:
        logger.warning("operational events: unknown to_state %r, baseline cleared", rows[-1].get("to_state"))
        _last_recorded = None
    logger.info("operational events: loaded %s row(s) from DB into cache", len(out))


def record_operational_transition_if_changed() -> None:
    """
    Record one event when derived state changes vs last call. Idempotent when unchanged.

    Call from GET /system and/or end of bot loop — duplicates are suppressed by comparing to
    ``_last_recorded``; first call only sets baseline (no event).
    """
    global _last_recorded
    q = _ensure_deque()
    s = derive_operational_state()
    if _last_recorded is None:
        _last_recorded = s
        return
    if s == _last_recorded:
        return
    payload = operational_state_payload()
    ev = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "from_state": _last_recorded.value,
        "to_state": s.value,
        "detail": payload.get("operational_state_detail", ""),
    }
    q.append(ev)
    _last_recorded = s
    _persist_event_to_db(ev)


def operational_events_payload() -> dict[str, Any]:
    """For /system: recent transitions + cap + persistence flags."""
    return {
        "operational_events": get_operational_events(),
        "operational_event_max": _max_len(),
        "operational_events_persist_enabled": _persist_enabled(),
        "operational_events_load_from_db_enabled": _load_cache_from_db_enabled(),
    }
