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
    from forex_bot.database import insert_exec_order_pending_if_absent

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
    from forex_bot.database import update_exec_order_row

    st = status.value
    update_exec_order_row(
        client_order_id=client_order_id,
        status=st,
        fill_price=fill_price,
        broker_order_id=broker_order_id,
        metadata=metadata,
        filled_units=units_filled,
    )
    update_order(
        client_order_id,
        status=status,
        units_filled=units_filled,
        avg_fill_price=fill_price,
        broker_order_id=broker_order_id,
    )


def mark_order_failed_or_cancelled(client_order_id: str) -> None:
    from forex_bot.database import update_exec_order_row

    update_exec_order_row(
        client_order_id=client_order_id, status="CANCELLED", metadata={"reason": "execution_failed"}
    )
    update_order(client_order_id, status=OrderStatus.CANCELLED, detail="execution_failed")


def load_open_orders_from_db_into_memory() -> int:
    """Rebuild non-terminal orders after restart."""
    from forex_bot.database import fetch_exec_orders_open_for_recovery

    rows = fetch_exec_orders_open_for_recovery()
    n = 0
    for r in rows:
        cid = str(r.get("client_order_id") or "")
        if not cid or cid in orders_by_client_id:
            continue
        try:
            st = OrderStatus(str(r.get("status") or "PENDING").upper())
        except ValueError:
            st = OrderStatus.PENDING
        try:
            ts = float(time.time())
        except Exception:
            ts = time.time()
        fu = r.get("filled_units")
        units_filled = float(fu) if fu is not None else 0.0
        register_order(
            LocalOrder(
                client_order_id=cid,
                symbol=str(r.get("symbol") or ""),
                direction=str(r.get("side") or "BUY"),
                units_requested=float(r.get("units") or 0),
                units_filled=units_filled,
                status=st,
                avg_fill_price=float(r["fill_price"]) if r.get("fill_price") is not None else None,
                created_ts=ts,
                broker_order_id=str(r.get("broker_order_id") or ""),
                source="db_recovery",
                detail="loaded from exec_orders",
            )
        )
        n += 1
    if n:
        logger.info("exec_orders: loaded %s open/partial row(s) into memory", n)
    return n


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
