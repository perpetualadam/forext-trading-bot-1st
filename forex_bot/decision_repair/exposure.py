"""Conservative pending-order and multi-position exposure snapshot.

Broker-disconnected. Does not cancel, close, or submit orders.
Protective SL/TP are not treated as new exposure. Unknown orders are not zero.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

EXPOSURE_SCHEMA_VERSION = 1
REASON_SNAPSHOT_MISSING = "exposure_snapshot_missing"
REASON_NAV_INVALID = "exposure_nav_invalid"
REASON_PENDING_UNKNOWN = "exposure_pending_unknown"
REASON_POSITION_STALE = "exposure_position_stale"
REASON_RECONCILE = "exposure_reconcile_failed"
REASON_CONVERT = "exposure_value_unconvertible"
REASON_CAP = "exposure_cap_breached"
REASON_UNKNOWN_ORDER = "exposure_unknown_order"
REASON_LATCH = "account_risk_latched"
REASON_RESERVATION = "exposure_reservation_conflict"

ENTRY_TYPES = frozenset({"MARKET", "LIMIT", "STOP", "MARKET_IF_TOUCHED", "STOP_ORDER", "LIMIT_ORDER"})
PROTECTIVE_TYPES = frozenset(
    {"STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP_LOSS", "GUARANTEED_STOP_LOSS", "STOP_LOSS_ORDER", "TAKE_PROFIT_ORDER"}
)
EXIT_TYPES = frozenset({"MARKET_IF_TOUCHED_CLOSE", "CLOSE"})
TERMINAL_OK = frozenset({"CANCELLED", "CANCELED", "REJECTED", "FILLED"})
_RESERVE_LOCK = threading.Lock()
_RESERVATIONS: dict[str, dict[str, Any]] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def classify_order(order: dict[str, Any]) -> str:
    status = str(order.get("status") or order.get("state") or "").upper().strip()
    if status in {"UNKNOWN", "UNAVAILABLE", ""} and not order.get("type"):
        return "unknown"
    if status in {"REJECTED"}:
        return "rejected"
    if status in {"CANCELLED", "CANCELED"}:
        return "cancelled"
    if status in {"FILLED"}:
        return "filled"
    otype = str(order.get("type") or order.get("orderType") or "").upper().strip()
    if otype in PROTECTIVE_TYPES:
        return "protective"
    if otype in EXIT_TYPES:
        return "exit"
    if otype in ENTRY_TYPES:
        return "entry"
    if otype in {"PARTIAL", "PARTIALLY_FILLED"} or status in {"PARTIALLY_FILLED", "PARTIAL_FILL"}:
        return "entry"
    if not otype or otype in {"UNKNOWN"}:
        return "unknown"
    return "unknown"


def remaining_entry_units(order: dict[str, Any]) -> float:
    units = abs(_finite_number(order.get("units") or order.get("remainingUnits")) or 0.0)
    filled = abs(_finite_number(order.get("filledUnits") or order.get("unitsFilled")) or 0.0)
    if filled and units and filled <= units:
        return max(0.0, units - filled)
    return units


@dataclass
class ExposureSnapshot:
    schema_version: int = EXPOSURE_SCHEMA_VERSION
    nav: float | None = None
    unrealised: float | None = None
    realised: float | None = None
    open_position_count: int = 0
    open_trade_refs: list[str] = field(default_factory=list)
    pair_exposure: dict[str, float] = field(default_factory=dict)
    usd_direction_count: dict[str, int] = field(default_factory=dict)
    pending_entry_count: int = 0
    reserved_notional: float = 0.0
    committed_exposure: float = 0.0
    proposed_exposure: float = 0.0
    snapshot_utc: str = ""
    reconcile_status: str = "unknown"
    stale: bool = False
    unknown_order_count: int = 0
    protective_order_count: int = 0
    ready: bool = False
    block_reason: str | None = None


def snapshot_from_broker_view(
    *,
    nav: Any,
    unrealised: Any = 0.0,
    realised: Any = 0.0,
    positions: list[dict[str, Any]] | None,
    pending_orders: list[dict[str, Any]] | None,
    reconcile_status: str = "ok",
    stale: bool = False,
    asof_utc: str | None = None,
    proposed_notional: float = 0.0,
    max_committed: float | None = None,
) -> ExposureSnapshot:
    snap = ExposureSnapshot(snapshot_utc=asof_utc or _utc_now(), reconcile_status=reconcile_status, stale=stale)
    if positions is None or pending_orders is None:
        snap.block_reason = REASON_SNAPSHOT_MISSING
        return snap
    snap.nav = _finite_positive(nav)
    if snap.nav is None:
        snap.block_reason = REASON_NAV_INVALID
        return snap
    snap.unrealised = _finite_number(unrealised)
    snap.realised = _finite_number(realised)
    if snap.unrealised is None:
        snap.block_reason = REASON_CONVERT
        return snap
    if stale:
        snap.block_reason = REASON_POSITION_STALE
        return snap
    if reconcile_status not in {"ok", "clean"}:
        snap.block_reason = REASON_RECONCILE
        return snap

    seen_pos: set[str] = set()
    committed = 0.0
    for pos in positions:
        ref = str(pos.get("id") or pos.get("trade_id") or pos.get("symbol") or "")
        if ref and ref in seen_pos:
            continue
        if ref:
            seen_pos.add(ref)
            snap.open_trade_refs.append(ref)
        symbol = str(pos.get("symbol") or "")
        notional = abs(_finite_number(pos.get("notional") or pos.get("units")) or 0.0)
        snap.pair_exposure[symbol] = snap.pair_exposure.get(symbol, 0.0) + notional
        committed += notional
        side = str(pos.get("usd_direction") or pos.get("direction") or "").upper()
        if side:
            snap.usd_direction_count[side] = snap.usd_direction_count.get(side, 0) + 1
    snap.open_position_count = len(seen_pos) if seen_pos else len(positions)
    snap.committed_exposure = committed

    reserved = 0.0
    for order in pending_orders:
        kind = classify_order(order)
        if kind == "protective":
            snap.protective_order_count += 1
            continue
        if kind in {"cancelled", "rejected", "filled", "exit"}:
            continue
        if kind == "unknown":
            snap.unknown_order_count += 1
            reserved += abs(_finite_number(order.get("notional") or remaining_entry_units(order)) or 0.0)
            continue
        if kind == "entry":
            rem = remaining_entry_units(order)
            notion = abs(_finite_number(order.get("notional")) or rem)
            if rem > 0 or notion > 0:
                snap.pending_entry_count += 1
                reserved += notion
    snap.reserved_notional = reserved
    snap.proposed_exposure = float(proposed_notional)
    total = snap.committed_exposure + snap.reserved_notional + snap.proposed_exposure
    if snap.unknown_order_count:
        snap.block_reason = REASON_UNKNOWN_ORDER
        return snap
    if max_committed is not None and total > float(max_committed) + 1e-9:
        snap.block_reason = REASON_CAP
        return snap
    snap.ready = True
    return snap


def reserve_local(key: str, notional: float) -> bool:
    """Process-local reservation. Not a broker lock. Not cross-process safe."""
    with _RESERVE_LOCK:
        if key in _RESERVATIONS:
            return False
        _RESERVATIONS[key] = {"notional": float(notional), "at": _utc_now()}
        return True


def release_local(key: str) -> None:
    with _RESERVE_LOCK:
        _RESERVATIONS.pop(key, None)


def clear_reservations_for_tests() -> None:
    with _RESERVE_LOCK:
        _RESERVATIONS.clear()


def reserved_total() -> float:
    with _RESERVE_LOCK:
        return sum(float(row.get("notional") or 0.0) for row in _RESERVATIONS.values())


def block_reason_for_snapshot(snap: ExposureSnapshot | None, *, latched: bool = False) -> str | None:
    if latched:
        return REASON_LATCH
    if snap is None:
        return REASON_SNAPSHOT_MISSING
    return snap.block_reason
