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
