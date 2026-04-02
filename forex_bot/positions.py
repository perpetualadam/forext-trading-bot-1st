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


def open_position(pos: Position) -> None:
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
    bn = float(broker_net_units)
    direction = "BUY" if bn > 0 else "SELL"
    p.direction = direction
    p.units = abs(bn)
    import logging

    logging.getLogger(__name__).info(
        "[RECONCILE FIX] Adjusted units to broker | %s net=%.4f dir=%s", symbol, bn, direction
    )
    return True


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
) -> None:
    """Create local Position from broker snapshot (caller supplies sl/tp from sizing rules)."""
    import logging
    import time

    sym = symbol.upper().strip()
    bn = float(broker_net_units)
    direction = "BUY" if bn > 0 else "SELL"
    units = abs(bn)
    entry = float(avg_price)
    positions[sym] = Position(
        symbol=sym,
        direction=direction,
        units=units,
        entry_price=entry,
        stop_loss=float(stop_loss),
        take_profit=float(take_profit),
        open_time=time.time(),
        strategy_name=strategy_name,
        rl_state=rl_state,
        execution_kind=execution_kind,
    )
    logging.getLogger(__name__).info(
        "[RECONCILE IMPORT] Imported broker position %s net=%.4f entry=%.5f", sym, bn, entry
    )
