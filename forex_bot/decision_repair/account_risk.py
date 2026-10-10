"""Account-level daily-loss and drawdown latch with order-independent event replay.

Realised P&L events are stored and reconstructed in canonical broker order.
NAV / unrealised snapshots are separate and are never invented from transactions.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.decision_repair import RISK_SCHEMA_VERSION

DEFAULT_PATH = Path("data") / "research" / "decision_repair" / "account_risk.json"
MAX_EVENTS = 4000
MAX_SNAPSHOTS = 2000
MAX_QUARANTINE = 200
REASON_LATCHED = "account_risk_latched"
REASON_EQUITY_MISSING = "account_equity_unavailable"
REASON_EQUITY_INVALID = "account_equity_invalid"
REASON_UNREALISED_MISSING = "account_unrealised_unavailable"
REASON_DAILY_REALISED = "daily_realised_loss_limit"
REASON_DAILY_TOTAL = "daily_total_loss_limit"
REASON_MAX_DD = "max_drawdown_limit"
REASON_INCONSISTENT = "risk_state_inconsistent"
REASON_EVENT_TIME = "risk_event_time_unavailable"
REASON_EVENT_ID = "risk_event_id_unavailable"
REASON_CONFLICT = "risk_event_conflict"
INTEGRITY_OK = "ok"
INTEGRITY_UNAVAILABLE = "UNAVAILABLE"
INTEGRITY_INCONSISTENT = "INCONSISTENT"
_LOCK = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def risk_path() -> Path:
    raw = (os.getenv("DECISION_REPAIR_RISK_PATH") or "").strip()
    return Path(raw) if raw else DEFAULT_PATH


def _env_frac(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def default_limits() -> dict[str, float]:
    return {
        "daily_realised_pct": _env_frac("DECISION_REPAIR_DAILY_REALISED_PCT", 0.02),
        "daily_total_pct": _env_frac("DECISION_REPAIR_DAILY_TOTAL_PCT", 0.03),
        "max_dd_pct": _env_frac("DECISION_REPAIR_MAX_DD_PCT", 0.05),
    }


def _finite_positive(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed) or parsed <= 0:
        return None
    return parsed


def _finite_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def parse_broker_time(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_broker_seq(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        seq = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if seq < 0:
        return None
    return seq


def canonical_sort_key(event: dict[str, Any]) -> tuple[str, int, str]:
    """Broker time, then numeric tx seq (missing seq sorts last), then event id."""
    time_key = str(event.get("broker_time_utc") or "")
    seq = event.get("broker_seq")
    seq_key = int(seq) if isinstance(seq, int) else 10**18
    return (time_key, seq_key, str(event.get("event_id") or ""))


def integrity_hash(payload: dict[str, Any]) -> str:
    clone = {k: v for k, v in payload.items() if k != "integrity_hash"}
    text = json.dumps(clone, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def blank_document(*, equity: float | None = None) -> dict[str, Any]:
    now = _utc_now()
    doc: dict[str, Any] = {
        "schema_version": RISK_SCHEMA_VERSION,
        "events": [],
        "nav_snapshots": [],
        "quarantine": [],
        "cleared_events": [],
        "peak_equity": equity,
        "day_baselines": {},
        "latched": False,
        "latch_reason": None,
        "latched_at_utc": None,
        "integrity": INTEGRITY_OK,
        "limits": default_limits(),
        "updated_utc": now.isoformat(),
    }
    doc["integrity_hash"] = integrity_hash(doc)
    return doc


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return blank_document()
    try:
        blob = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        doc = blank_document()
        _latch(doc, "corrupt_risk_state")
        doc["integrity"] = INTEGRITY_UNAVAILABLE
        return doc
    if not isinstance(blob, dict) or int(blob.get("schema_version") or 0) != RISK_SCHEMA_VERSION:
        doc = blank_document()
        _latch(doc, "incompatible_risk_state")
        doc["integrity"] = INTEGRITY_UNAVAILABLE
        return doc
    expected = str(blob.get("integrity_hash") or "")
    if not expected or integrity_hash(blob) != expected:
        doc = blank_document()
        _latch(doc, "corrupt_risk_state")
        doc["integrity"] = INTEGRITY_UNAVAILABLE
        return doc
    return blob


def _save(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc["integrity_hash"] = integrity_hash({k: v for k, v in doc.items() if k != "integrity_hash"})
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _latch(doc: dict[str, Any], reason: str) -> None:
    if doc.get("latched"):
        return
    doc["latched"] = True
    doc["latch_reason"] = reason
    doc["latched_at_utc"] = _utc_now().isoformat()


def _mark_inconsistent(doc: dict[str, Any], reason: str) -> None:
    doc["integrity"] = INTEGRITY_INCONSISTENT
    _latch(doc, reason)


def reconstruct_day_realised(events: list[dict[str, Any]], utc_day: str) -> float:
    total = 0.0
    for event in events:
        if str(event.get("utc_day") or "") == utc_day:
            total += float(event.get("realised_delta") or 0.0)
    return total


def _record_nav(
    doc: dict[str, Any],
    *,
    equity: float | None,
    unrealised: float | None,
    for_day: str | None = None,
) -> None:
    equity_ok = _finite_positive(equity)
    if equity_ok is None:
        return
    snap = {
        "asof_utc": _utc_now().isoformat(),
        "nav": equity_ok,
        "unrealised": _finite_number(unrealised),
    }
    snaps = list(doc.get("nav_snapshots") or [])
    snaps.append(snap)
    doc["nav_snapshots"] = snaps[-MAX_SNAPSHOTS:]
    peak = doc.get("peak_equity")
    doc["peak_equity"] = equity_ok if peak is None else max(float(peak), equity_ok)
    today = _utc_now().date().isoformat()
    baselines = dict(doc.get("day_baselines") or {})
    if today not in baselines:
        baselines[today] = equity_ok
    if for_day and for_day not in baselines:
        baselines[for_day] = equity_ok
    doc["day_baselines"] = baselines


def _apply_limits(doc: dict[str, Any], *, equity: float | None, unrealised: float) -> None:
    if doc.get("latched"):
        return
    if doc.get("integrity") != INTEGRITY_OK:
        _latch(doc, str(doc.get("latch_reason") or REASON_INCONSISTENT))
        return
    limits = doc.get("limits") or default_limits()
    today = _utc_now().date().isoformat()
    events = list(doc.get("events") or [])
    baselines = doc.get("day_baselines") or {}
    peak = doc.get("peak_equity")
    days = {today} | {str(event.get("utc_day") or "") for event in events}
    days.discard("")
    for day in days:
        realised = reconstruct_day_realised(events, day)
        start = baselines.get(day)
        if start is None:
            continue
        start_f = float(start)
        if start_f > 0 and realised <= -abs(float(limits.get("daily_realised_pct", 0.02))) * start_f:
            _latch(doc, REASON_DAILY_REALISED)
            return
        if day == today:
            total = realised + float(unrealised)
            if start_f > 0 and total <= -abs(float(limits.get("daily_total_pct", 0.03))) * start_f:
                _latch(doc, REASON_DAILY_TOTAL)
                return
    if peak is None or equity is None:
        return
    peak_f = float(peak)
    if peak_f > 0 and (peak_f - float(equity)) / peak_f >= abs(float(limits.get("max_dd_pct", 0.05))):
        _latch(doc, REASON_MAX_DD)


def observe(
    *,
    event_id: str,
    realised_delta: float,
    equity: float | None,
    unrealised: float | None = 0.0,
    broker_time_utc: str | None = None,
    broker_seq: int | str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    dest = path or risk_path()
    with _LOCK:
        doc = _load(dest)
        if not event_id or not str(event_id).strip():
            _quarantine(doc, {"reason": REASON_EVENT_ID, "payload": {"realised_delta": realised_delta}})
            _mark_inconsistent(doc, REASON_EVENT_ID)
            _save(dest, doc)
            return doc
        parsed_time = parse_broker_time(broker_time_utc)
        if parsed_time is None:
            _quarantine(doc, {"reason": REASON_EVENT_TIME, "event_id": event_id})
            _mark_inconsistent(doc, REASON_EVENT_TIME)
            _save(dest, doc)
            return doc
        seq = parse_broker_seq(broker_seq)
        incoming = {
            "event_id": str(event_id).strip(),
            "broker_time_utc": parsed_time.isoformat(),
            "broker_seq": seq,
            "ingested_utc": _utc_now().isoformat(),
            "realised_delta": float(realised_delta),
            "utc_day": parsed_time.date().isoformat(),
        }
        events = list(doc.get("events") or [])
        existing = next((row for row in events if row.get("event_id") == incoming["event_id"]), None)
        if existing is not None:
            if _event_payload(existing) != _event_payload(incoming):
                _quarantine(doc, {"reason": REASON_CONFLICT, "event_id": incoming["event_id"]})
                _mark_inconsistent(doc, REASON_CONFLICT)
                _save(dest, doc)
                return doc
            _record_nav(doc, equity=equity, unrealised=unrealised, for_day=str(incoming["utc_day"]))
            _apply_limits(doc, equity=_finite_positive(equity), unrealised=float(_finite_number(unrealised) or 0.0))
            doc["updated_utc"] = _utc_now().isoformat()
            _save(dest, doc)
            return doc
        events.append(incoming)
        events.sort(key=canonical_sort_key)
        doc["events"] = events[-MAX_EVENTS:]
        _record_nav(doc, equity=equity, unrealised=unrealised, for_day=str(incoming["utc_day"]))
        equity_ok = _finite_positive(equity)
        upl = _finite_number(unrealised) or 0.0
        _apply_limits(doc, equity=equity_ok, unrealised=upl)
        doc["updated_utc"] = _utc_now().isoformat()
        _save(dest, doc)
        return doc


def _event_payload(event: dict[str, Any]) -> tuple[Any, ...]:
    return (
        event.get("event_id"),
        event.get("broker_time_utc"),
        event.get("broker_seq"),
        float(event.get("realised_delta") or 0.0),
    )


def _quarantine(doc: dict[str, Any], row: dict[str, Any]) -> None:
    held = list(doc.get("quarantine") or [])
    held.append({**row, "ingested_utc": _utc_now().isoformat()})
    doc["quarantine"] = held[-MAX_QUARANTINE:]


def block_reason(
    *,
    equity: float | None,
    unrealised: float | None = 0.0,
    path: Path | None = None,
) -> str | None:
    dest = path or risk_path()
    with _LOCK:
        doc = _load(dest)
        if equity is None:
            _latch(doc, REASON_EQUITY_MISSING)
            _save(dest, doc)
            return REASON_EQUITY_MISSING
        equity_ok = _finite_positive(equity)
        if equity_ok is None:
            _latch(doc, REASON_EQUITY_INVALID)
            _save(dest, doc)
            return REASON_EQUITY_INVALID
        upl = _finite_number(unrealised)
        if unrealised is None or upl is None:
            _latch(doc, REASON_UNREALISED_MISSING)
            _save(dest, doc)
            return REASON_UNREALISED_MISSING
        _record_nav(doc, equity=equity_ok, unrealised=upl)
        _apply_limits(doc, equity=equity_ok, unrealised=upl)
        doc["updated_utc"] = _utc_now().isoformat()
        _save(dest, doc)
        if doc.get("latched"):
            return str(doc.get("latch_reason") or REASON_LATCHED)
        return None


def operator_clear_latch(*, operator_confirmed: bool, path: Path | None = None) -> None:
    if not operator_confirmed:
        raise PermissionError("operator_confirmed=True is required")
    dest = path or risk_path()
    with _LOCK:
        doc = _load(dest)
        cleared = list(doc.get("cleared_events") or [])
        cleared.extend(list(doc.get("events") or []))
        doc["cleared_events"] = cleared[-MAX_EVENTS:]
        doc["events"] = []
        doc["quarantine"] = []
        doc["latched"] = False
        doc["latch_reason"] = None
        doc["latched_at_utc"] = None
        doc["integrity"] = INTEGRITY_OK
        doc["updated_utc"] = _utc_now().isoformat()
        _save(dest, doc)
