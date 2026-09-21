"""In-memory open positions (one per symbol) for price-based PnL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

# Registry keyed by instrument symbol (e.g. EUR_USD).
positions: Dict[str, "Position"] = {}


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


def open_position(pos: Position) -> None:
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
    return positions.pop(symbol, None)


def close_local_position(symbol: str, *, reason: str) -> Optional[Position]:
    """Remove local registry entry (broker-truth reconcile)."""
    p = positions.pop(symbol, None)
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
    p.direction = direction
    p.units = abs(bn)
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
    """Create local Position from broker snapshot (caller supplies sl/tp from sizing rules)."""
    import logging
    import time

    from forex_bot.execution import is_paper_like_kind

    existing = positions.get(symbol.upper().strip())
    if existing is not None and is_paper_like_kind(existing.execution_kind):
        logging.getLogger(__name__).warning(
            "[RECONCILE] refuse import over paper-like %s kind=%s — displace first, do not mutate paper into live",
            symbol,
            existing.execution_kind,
        )
        return

    sym = symbol.upper().strip()
    bn = float(broker_net_units)
    direction = "BUY" if bn > 0 else "SELL"
    units = abs(bn)
    entry = float(avg_price)
    opened = float(open_time) if open_time is not None and open_time > 0 else time.time()
    positions[sym] = Position(
        symbol=sym,
        direction=direction,
        units=units,
        entry_price=entry,
        stop_loss=float(stop_loss),
        take_profit=float(take_profit),
        open_time=opened,
        strategy_name=strategy_name,
        rl_state=rl_state,
        execution_kind=execution_kind,
        broker_order=True,
        broker_trade_ids=broker_trade_ids,
        sl_source=sl_source,
        tp_source=tp_source,
        client_order_id=client_order_id,
        broker_order_id=broker_order_id,
        max_profit_pips=0.0,
        profit_protection_seeded=True,
    )
    logging.getLogger(__name__).info(
        "[RECONCILE IMPORT] Imported broker position %s net=%.4f entry=%.5f sl_src=%s tp_src=%s",
        sym,
        bn,
        entry,
        sl_source,
        tp_source,
    )
