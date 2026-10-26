"""Broker order lifecycle: in-memory registry + optional PostgreSQL idempotency (exec_orders)."""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class LocalOrder:
    """client_order_id is the idempotency key; broker_order_id is fill tx or broker pending id."""

    client_order_id: str
    symbol: str
    direction: str
    units_requested: float
    units_filled: float
    status: OrderStatus
    avg_fill_price: float | None
    created_ts: float
    broker_order_id: str = ""
    source: str = "bot"
    detail: str = ""


# Primary index: client_order_id (idempotency)
orders_by_client_id: dict[str, LocalOrder] = {}


def generate_client_order_id() -> str:
    return f"cid-{uuid.uuid4().hex}"


def register_order(o: LocalOrder) -> None:
    orders_by_client_id[o.client_order_id] = o


def get_order_by_client_id(client_order_id: str) -> LocalOrder | None:
    return orders_by_client_id.get(client_order_id)


def get_order_by_broker_id(broker_order_id: str) -> LocalOrder | None:
    if not broker_order_id:
        return None
    for o in orders_by_client_id.values():
        if o.broker_order_id == broker_order_id:
            return o
    return None


def update_order(
    client_order_id: str,
    *,
    status: OrderStatus | None = None,
    units_filled: float | None = None,
    avg_fill_price: float | None = None,
    broker_order_id: str | None = None,
    detail: str | None = None,
) -> None:
    o = orders_by_client_id.get(client_order_id)
    if not o:
        return
    if status is not None:
        o.status = status
    if units_filled is not None:
        o.units_filled = units_filled
    if avg_fill_price is not None:
        o.avg_fill_price = avg_fill_price
    if broker_order_id is not None:
        o.broker_order_id = broker_order_id
    if detail is not None:
        o.detail = detail


def remove_order(client_order_id: str) -> None:
    orders_by_client_id.pop(client_order_id, None)


def try_begin_order_submission(
    *,
    client_order_id: str,
    symbol: str,
    direction: str,
    units: float,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Reserve idempotency key (memory + DB). Returns False if duplicate — do not send to broker.
    """
    if client_order_id in orders_by_client_id:
        logger.warning("[ORDER] idempotent skip (memory): %s", client_order_id)
        return False
    from forex_bot.database import (
        insert_exec_order_pending_if_absent,
        reservation_status_block_reason,
    )

    symbol_key = symbol.upper().strip()
    from forex_bot.positions import get_position

    if get_position(symbol_key) is not None:
        logger.warning("[ORDER] open position blocks %s on %s", client_order_id, symbol_key)
        return False
    for existing in orders_by_client_id.values():
        if existing.symbol != symbol_key:
            continue
        if reservation_status_block_reason(existing.status.value):
            logger.warning("[ORDER] active reservation blocks %s on %s", client_order_id, symbol_key)
            return False
    if not insert_exec_order_pending_if_absent(
        client_order_id=client_order_id,
        symbol=symbol,
        side=direction,
        units=units,
        metadata=metadata,
    ):
        return False
    register_order(
        LocalOrder(
            client_order_id=client_order_id,
            symbol=symbol.upper().strip(),
            direction=direction.upper().strip(),
            units_requested=float(units),
            units_filled=0.0,
            status=OrderStatus.PENDING,
            avg_fill_price=None,
            created_ts=time.time(),
            broker_order_id="",
            source="bot",
            detail="",
        )
    )
    return True


def finalize_order_fill(
    client_order_id: str,
    *,
    broker_order_id: str,
    fill_price: float,
    units_filled: float,
    status: OrderStatus = OrderStatus.FILLED,
    metadata: dict[str, Any] | None = None,
) -> None:
    from forex_bot.database import (
        note_unconfirmed_exposure,
        persist_exec_orders_enabled,
        refuse_reservation_after_database_fault,
        update_exec_order_row,
    )

    order = orders_by_client_id.get(client_order_id)
    st = status.value
    meta = dict(metadata or {})
    if status in (OrderStatus.FILLED, OrderStatus.PARTIAL):
        meta["exposure_safety"] = "UNCONFIRMED"
    wrote = update_exec_order_row(
        client_order_id=client_order_id,
        status=st,
        fill_price=fill_price,
        broker_order_id=broker_order_id,
        metadata=meta,
        filled_units=units_filled,
    )
    update_order(
        client_order_id,
        status=status,
        units_filled=units_filled,
        avg_fill_price=fill_price,
        broker_order_id=broker_order_id,
    )
    if order is not None and status in (OrderStatus.FILLED, OrderStatus.PARTIAL):
        note_unconfirmed_exposure(order.symbol, client_order_id)
        if persist_exec_orders_enabled() and wrote is not True:
            refuse_reservation_after_database_fault()


def mark_order_failed_or_cancelled(client_order_id: str) -> None:
    from forex_bot.database import (
        client_order_is_unresolved,
        release_reservation_hold,
        update_exec_order_row,
    )

    current = orders_by_client_id.get(client_order_id)
    if client_order_is_unresolved(client_order_id) or (
        current is not None and current.status == OrderStatus.UNRESOLVED
    ):
        logger.warning("[ORDER] unresolved outcome kept for %s", client_order_id)
        return
    symbol = current.symbol if current is not None else ""
    update_exec_order_row(
        client_order_id=client_order_id, status="CANCELLED", metadata={"reason": "execution_failed"}
    )
    update_order(client_order_id, status=OrderStatus.CANCELLED, detail="execution_failed")
    if symbol:
        release_reservation_hold(symbol)


def _recovery_side(value: object) -> str:
    text = str(value or "").strip().upper()
    if text in ("BUY", "SELL"):
        return text
    return ""


def ingest_recovery_snapshot(rows: object, readable: bool) -> int:
    """Load a recovery snapshot. Unreadable or unknown status fails closed."""
    from forex_bot.database import (
        OrderRecoveryUnreadable,
        force_order_recovery_fail_closed,
        note_blocking_reservation,
        note_unconfirmed_exposure,
        restore_unresolved_intent,
    )

    if not readable or not isinstance(rows, list):
        force_order_recovery_fail_closed()
        raise OrderRecoveryUnreadable("order recovery snapshot unreadable")
    prepared: list[LocalOrder] = []
    unresolved: list[tuple[str, str]] = []
    blocking: list[tuple[str, str]] = []
    exposure: list[tuple[str, str]] = []
    seen: dict[str, tuple[str, str]] = {}
    for r in rows:
        if not isinstance(r, dict) or "status" not in r or "symbol" not in r:
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("order recovery row corrupt")
        cid = str(r.get("client_order_id") or "")
        if not cid:
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("order recovery row missing client id")
        try:
            status = OrderStatus(str(r.get("status") or "").upper())
        except ValueError:
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("order recovery status unrecognised")
        identity = (str(r.get("symbol") or "").upper(), status.value)
        previous = seen.get(cid)
        if previous is not None:
            if previous != identity:
                force_order_recovery_fail_closed()
                raise OrderRecoveryUnreadable("order recovery rows conflict")
            continue
        seen[cid] = identity
        fu = r.get("filled_units")
        prepared.append(
            LocalOrder(
                client_order_id=cid,
                symbol=str(r.get("symbol") or "").upper(),
                direction=_recovery_side(r.get("side")),
                units_requested=float(r.get("units") or 0),
                units_filled=float(fu) if fu is not None else 0.0,
                status=status,
                avg_fill_price=float(r["fill_price"]) if r.get("fill_price") is not None else None,
                created_ts=time.time(),
                broker_order_id=str(r.get("broker_order_id") or ""),
                source="db_recovery",
                detail="loaded from exec_orders",
            )
        )
        if r.get("snapshot_stale") is True:
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("order recovery snapshot stale")
        raw_meta = r.get("metadata", None)
        if raw_meta is None:
            meta = {}
        elif isinstance(raw_meta, dict):
            meta = raw_meta
        else:
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("order recovery metadata malformed")
        marker = str(meta.get("exposure_safety") or "").strip().upper()
        if marker and marker not in ("UNCONFIRMED", "CONFIRMED_FLAT"):
            force_order_recovery_fail_closed()
            raise OrderRecoveryUnreadable("order recovery exposure marker unrecognised")
        if status in (OrderStatus.PENDING, OrderStatus.PARTIAL, OrderStatus.UNRESOLVED):
            blocking.append((str(r.get("symbol") or ""), cid))
        if status == OrderStatus.UNRESOLVED:
            unresolved.append((str(r.get("symbol") or ""), cid))
        if marker == "UNCONFIRMED" or (
            status == OrderStatus.FILLED and marker != "CONFIRMED_FLAT"
        ):
            exposure.append((str(r.get("symbol") or ""), cid))
    for symbol, cid in blocking:
        note_blocking_reservation(symbol, cid)
    for symbol, cid in unresolved:
        restore_unresolved_intent(symbol, cid)
    for symbol, cid in exposure:
        note_unconfirmed_exposure(symbol, cid)
    n = 0
    for order in prepared:
        if order.client_order_id in orders_by_client_id:
            continue
        register_order(order)
        n += 1
    if n:
        logger.info("exec_orders: loaded %s open order row(s) into memory", n)
    return n


def record_synthetic_fill_position(
    *,
    symbol: str,
    client_order_id: str,
    direction: str,
    units: float,
    price: float,
) -> str:
    """Record a synthetic fill. Incomplete evidence does not create a position.

    This does not call a broker. A recorded position still leaves the
    exposure hold in place until an explicit flat confirmation.
    """
    from forex_bot.database import note_unconfirmed_exposure
    from forex_bot.positions import Position, get_position, open_position

    sym = symbol.upper().strip()
    side = str(direction or "").strip().upper()
    note_unconfirmed_exposure(sym, client_order_id or sym)
    if side not in ("BUY", "SELL") or not client_order_id or float(units) <= 0 or float(price) <= 0:
        return "blocked"
    current = get_position(sym)
    if current is not None:
        if abs(float(current.units) - float(units)) > 1e-6 or current.direction != side:
            return "conflict"
        return "recorded"
    try:
        open_position(
            Position(
                symbol=sym,
                direction=side,
                units=float(units),
                entry_price=float(price),
                stop_loss=0.0,
                take_profit=0.0,
                open_time=time.time(),
                strategy_name="synthetic",
                rl_state="synthetic",
                execution_kind="synthetic",
                client_order_id=client_order_id,
                broker_order=False,
            )
        )
    except Exception:
        logger.exception("synthetic fill position was not recorded")
        return "blocked"
    return "recorded"


def load_open_orders_from_db_into_memory() -> int:
    """Rebuild non-terminal orders after restart."""
    from forex_bot.database import (
        OrderRecoveryUnreadable,
        fetch_exec_orders_open_for_recovery,
        force_order_recovery_fail_closed,
    )

    try:
        rows = fetch_exec_orders_open_for_recovery()
    except OrderRecoveryUnreadable:
        force_order_recovery_fail_closed()
        logger.error("exec_orders: recovery unreadable — new broker entries remain blocked")
        return 0
    try:
        return ingest_recovery_snapshot(rows, True)
    except OrderRecoveryUnreadable:
        force_order_recovery_fail_closed()
        logger.error("exec_orders: recovery snapshot rejected — new broker entries remain blocked")
        return 0


def orders_summary() -> dict[str, Any]:
    by_status: dict[str, int] = {}
    for o in orders_by_client_id.values():
        k = o.status.value
        by_status[k] = by_status.get(k, 0) + 1
    return {
        "order_count": len(orders_by_client_id),
        "by_status": by_status,
        "pending_client_order_ids": [
            o.client_order_id for o in orders_by_client_id.values() if o.status == OrderStatus.PENDING
        ],
    }


def reset_orders_for_tests() -> None:
    orders_by_client_id.clear()
