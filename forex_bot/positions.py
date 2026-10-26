"""In-memory open positions (one per symbol) for price-based PnL."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

# Registry keyed by instrument symbol (e.g. EUR_USD).
positions: Dict[str, "Position"] = {}
_book_lock = threading.Lock()


@dataclass
class Position:
    symbol: str
    direction: str  # "BUY" or "SELL"
    units: float
    entry_price: float
    stop_loss: float
    take_profit: float
    open_time: float
    strategy_name: str
    rl_state: str
    execution_kind: str  # carried to close for Postgres / alerts
    client_order_id: str = ""
    broker_order_id: str = ""
    broker_order: bool = False
    broker_trade_ids: str = ""
    sl_source: str = "local"
    tp_source: str = "local"
    max_profit_pips: float = 0.0
    profit_protection_active: bool = False
    profit_protection_seeded: bool = False
    profit_protection_last_logged_mfe: float = -1.0
    profit_protection_close_attempt_ts: float = 0.0
    profit_protection_exit_pips: float | None = None
    min_profit_pips: float = 0.0
    max_adverse_pips: float = 0.0
    atr_at_entry_pips: float | None = None
    protect_activated_mfe_pips: float | None = None
    protect_activated_atr_pips: float | None = None
    protect_activated_giveback_pips: float | None = None
    protect_activated_exit_pips: float | None = None
    atr_fallback_used: bool = False
    observation_only: bool = False
    position_instance_id: str = ""
    position_generation: int = 0


# Broker discoveries. Not the book used by position management.
broker_observations: Dict[str, "Position"] = {}

# Kinds assigned by the existing open paths. reconcile_import is not one of them.
_MANAGED_EXECUTION_KINDS = frozenset(
    {"paper", "simulated", "window_paper", "live", "synthetic"}
)


def position_management_permitted(pos: object | None) -> bool:
    """True only for an existing paper or bot-opened row.

    A reconciliation import, a forged execution kind, a trade id, and the
    presence of a local row do not grant this. Unknown kinds fail closed.
    """
    if pos is None:
        return False
    if bool(getattr(pos, "observation_only", False)) or bool(getattr(pos, "recovery_quarantine", False)):
        return False
    kind = (getattr(pos, "execution_kind", None) or "").strip().lower()
    if kind == "reconcile_import":
        return False
    return kind in _MANAGED_EXECUTION_KINDS


def ensure_position_identity(pos: Position) -> None:
    """Assign a stable instance id. This is not a Python object address."""
    with _book_lock:
        if not getattr(pos, "position_instance_id", ""):
            pos.position_instance_id = uuid.uuid4().hex
        if int(getattr(pos, "position_generation", 0) or 0) < 1:
            pos.position_generation = 1


def open_position(pos: Position) -> None:
    with _book_lock:
        if not pos.position_instance_id:
            pos.position_instance_id = uuid.uuid4().hex
        if int(pos.position_generation or 0) < 1:
            pos.position_generation = 1
        prev = positions.get(pos.symbol)
        if prev is not None:
            import logging

            logging.getLogger(__name__).warning(
                "[POSITION REPLACE] %s old_kind=%s old_broker=%s → new_kind=%s new_broker=%s "
                "(one local slot per symbol; identities are not merged)",
                pos.symbol,
                prev.execution_kind,
                getattr(prev, "broker_order", False),
                pos.execution_kind,
                getattr(pos, "broker_order", False),
            )
        positions[pos.symbol] = pos


def get_position(symbol: str) -> Optional[Position]:
    return positions.get(symbol)


def close_position(symbol: str) -> Optional[Position]:
    with _book_lock:
        resident = positions.get(symbol)
        if resident is not None and not position_management_permitted(resident):
            import logging

            logging.getLogger(__name__).warning(
                "[POSITION] refuse local delete of observation-only %s kind=%s",
                symbol,
                getattr(resident, "execution_kind", ""),
            )
            return None
        if resident is not None and (getattr(resident, "execution_kind", "") or "").strip().lower() == "live":
            import logging

            logging.getLogger(__name__).warning(
                "[POSITION] refuse symbol-only live delete %s",
                symbol,
            )
            return None
        return positions.pop(symbol, None)


def _identity_units(value: object) -> Decimal | None:
    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return None
    if not dec.is_finite():
        return None
    return dec


def close_confirmed_live_position(symbol: str, operation: Any) -> Optional[Position]:
    """Pop a live row only when it is still the confirmed operation's position.

    The comparison and the pop share ``_book_lock``, which also covers replacement.
    """
    from forex_bot.close_journal import JournalUnavailable, active_journal
    from forex_bot.startup_recovery import current_fencing_epoch, live_management_permitted
    from forex_bot.symbols import normalize_oanda_symbol

    if current_fencing_epoch() is not None and not live_management_permitted():
        return None
    try:
        journal = active_journal()
        row = journal.get(str(getattr(operation, "operation_id", "") or ""))
    except JournalUnavailable:
        return None
    if row is None or row["confirmation_state"] != "CLOSE_FULLY_CONFIRMED":
        return None
    if row["account_binding"] != str(getattr(operation, "account_scope", "") or ""):
        return None
    if not row["transaction_ids"]:
        return None
    requested = _identity_units(row["requested_units"])
    confirmed = _identity_units(row["confirmed_units"])
    remaining = _identity_units(row["remaining_units"])
    if requested is None or confirmed is None or remaining is None:
        return None
    if confirmed != requested or remaining != Decimal("0"):
        return None
    key = normalize_oanda_symbol(symbol)
    if row["instrument"] != key:
        return None
    with _book_lock:
        book_key = symbol if symbol in positions else key
        resident = positions.get(book_key)
        if resident is None or not position_management_permitted(resident):
            return None
        if (getattr(resident, "execution_kind", "") or "").strip().lower() != "live":
            return None
        if resident.position_instance_id != row["position_instance_id"]:
            return None
        if int(resident.position_generation or 0) != int(row["position_generation"]):
            return None
        if (resident.direction or "").upper() != row["direction"]:
            return None
        if _identity_units(resident.units) != requested:
            return None
        trade_ids = [part.strip() for part in (resident.broker_trade_ids or "").split(",") if part.strip()]
        if trade_ids != [row["trade_id"]]:
            return None
        if normalize_oanda_symbol(resident.symbol) != row["instrument"]:
            return None
        held_key = book_key
    epoch = current_fencing_epoch()
    if epoch is not None:
        if not live_management_permitted():
            return None
        try:
            journal.finalise(row["operation_id"], expected_epoch=epoch)
        except JournalUnavailable:
            return None
    with _book_lock:
        resident = positions.get(held_key)
        if resident is None or resident.position_instance_id != row["position_instance_id"]:
            return None
        if not position_management_permitted(resident):
            return None
        removed = positions.pop(held_key, None)
    if removed is None:
        return None
    if epoch is None:
        try:
            journal.finalise(row["operation_id"])
        except JournalUnavailable:
            import logging

            logging.getLogger(__name__).warning(
                "[POSITION] local identity delete succeeded before journal finalise %s",
                key,
            )
    return removed


def close_local_position(symbol: str, *, reason: str) -> Optional[Position]:
    """Remove a managed local row. Observation-only rows stay."""
    p = close_position(symbol)
    if p is not None:
        import logging

        logging.getLogger(__name__).info("[RECONCILE FIX] Closed local position %s (%s)", symbol, reason)
    return p


def adjust_position_units_to_broker(symbol: str, broker_net_units: float) -> bool:
    """
    Align local units/direction to signed broker net (positive = long).
    Returns True if updated.
    """
    p = positions.get(symbol)
    if not p:
        return False
    if not position_management_permitted(p):
        import logging

        logging.getLogger(__name__).warning(
            "[RECONCILE] refuse unit adjust on observation-only %s kind=%s",
            symbol,
            getattr(p, "execution_kind", ""),
        )
        return False
    from forex_bot.execution import is_paper_like_kind

    if is_paper_like_kind(p.execution_kind):
        import logging

        logging.getLogger(__name__).warning(
            "[RECONCILE] refuse unit adjust on paper-like %s kind=%s (not the broker trade)",
            symbol,
            p.execution_kind,
        )
        return False
    bn = float(broker_net_units)
    direction = "BUY" if bn > 0 else "SELL"
    with _book_lock:
        current = positions.get(symbol)
        if current is not p:
            return False
        current.direction = direction
        current.units = abs(bn)
        current.position_generation = int(current.position_generation or 0) + 1
    import logging

    logging.getLogger(__name__).info(
        "[RECONCILE FIX] Adjusted units to broker | %s net=%.4f dir=%s", symbol, bn, direction
    )
    return True


# Last displaced paper rows (diagnostics only; not used for live risk/close).
_displaced_paper: list[dict] = []


def last_displaced_paper() -> list[dict]:
    return list(_displaced_paper)


def _paper_snapshot(pos: "Position") -> dict:
    return {
        "symbol": pos.symbol,
        "direction": pos.direction,
        "units": float(pos.units),
        "entry_price": float(pos.entry_price),
        "execution_kind": pos.execution_kind,
        "broker_order": bool(getattr(pos, "broker_order", False)),
        "client_order_id": getattr(pos, "client_order_id", "") or "",
        "broker_order_id": getattr(pos, "broker_order_id", "") or "",
    }


def displace_paper_position(symbol: str, *, reason: str) -> dict | None:
    """Remove a paper-like active slot. Does not touch broker-backed rows."""
    from forex_bot.execution import is_paper_like

    sym = symbol.upper().strip()
    p = positions.get(sym)
    if p is None or not is_paper_like(p):
        return None
    snap = _paper_snapshot(p)
    snap["reason"] = reason
    _displaced_paper.append(snap)
    if len(_displaced_paper) > 50:
        del _displaced_paper[:-50]
    positions.pop(sym, None)
    import logging

    logging.getLogger(__name__).warning(
        "[RECONCILE CONFLICT] %s displaced local paper state kind=%s entry=%.5f units=%.4f (%s)",
        sym,
        p.execution_kind,
        p.entry_price,
        p.units,
        reason,
    )
    return snap


def import_position_from_broker(
    symbol: str,
    broker_net_units: float,
    avg_price: float,
    stop_loss: float,
    take_profit: float,
    *,
    strategy_name: str = "reconcile_import",
    rl_state: str = "import",
    execution_kind: str = "reconcile_import",
    broker_trade_ids: str = "",
    sl_source: str = "local_fallback",
    tp_source: str = "local_fallback",
    client_order_id: str = "",
    broker_order_id: str = "",
    open_time: float | None = None,
) -> None:
    """Record a broker discovery outside the managed book.

    ``execution_kind`` is ignored. The record is always observation-only.
    """
    import logging
    import time

    from forex_bot.execution import is_paper_like_kind

    sym = symbol.upper().strip()
    existing = positions.get(sym)
    if existing is not None and is_paper_like_kind(existing.execution_kind):
        logging.getLogger(__name__).warning(
            "[RECONCILE] paper row preserved for %s kind=%s; broker position stays observation-only",
            symbol,
            existing.execution_kind,
        )
    elif existing is not None and position_management_permitted(existing):
        logging.getLogger(__name__).warning(
            "[RECONCILE] managed row preserved for %s kind=%s; broker position stays observation-only",
            symbol,
            existing.execution_kind,
        )
    supplied_kind = (execution_kind or "").strip().lower()
    if supplied_kind not in ("", "reconcile_import"):
        logging.getLogger(__name__).warning(
            "[RECONCILE] ignored execution_kind=%s for %s; discovery stays observation-only",
            supplied_kind,
            sym,
        )

    bn = float(broker_net_units)
    direction = "BUY" if bn > 0 else "SELL"
    units = abs(bn)
    entry = float(avg_price)
    opened = float(open_time) if open_time is not None and open_time > 0 else time.time()
    broker_observations[sym] = Position(
        symbol=sym,
        direction=direction,
        units=units,
        entry_price=entry,
        stop_loss=float(stop_loss),
        take_profit=float(take_profit),
        open_time=opened,
        strategy_name=strategy_name,
        rl_state=rl_state,
        execution_kind="reconcile_import",
        broker_order=True,
        observation_only=True,
        broker_trade_ids=broker_trade_ids,
        sl_source=sl_source,
        tp_source=tp_source,
        client_order_id=client_order_id,
        broker_order_id=broker_order_id,
        max_profit_pips=0.0,
        profit_protection_seeded=True,
    )
    logging.getLogger(__name__).info(
        "[RECONCILE OBSERVE] broker position %s net=%.4f entry=%.5f sl_src=%s tp_src=%s "
        "recorded as observation-only",
        sym,
        bn,
        entry,
        sl_source,
        tp_source,
    )
