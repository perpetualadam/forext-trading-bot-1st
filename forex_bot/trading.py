"""Position sizing, spread/slippage simulation, and execution logging."""

from __future__ import annotations

import random
from typing import Any

from forex_bot.alerts import alert
from forex_bot.analytics import analytics
from forex_bot.config import Config
from forex_bot.database import log_trade_pg
from forex_bot.state import current_equity, update_equity
from forex_bot.strategy_meta import meta, strategies


def position_sizing(symbol: str, decision: dict[str, Any]) -> float:
    _ = symbol, decision
    equity = current_equity()
    return float(min(equity * 0.02, 10000.0))


def simulate_execution(direction: str, price: float, size: float) -> float:
    """Paper path: spread + slippage + random exit noise; returns signed PnL (not per-pip perfect)."""
    spread = 0.0001
    slippage = 0.00005
    if direction == "BUY":
        entry = price + spread + slippage
    else:
        entry = price - spread - slippage
    exit_price = entry + random.uniform(-0.0003, 0.0003)
    if direction == "BUY":
        return float((exit_price - entry) * size)
    return float((entry - exit_price) * size)


async def execute_trade(
    symbol: str,
    strategy_name: str,
    direction: str,
    size: float,
    price: float,
    sl: float,
    tp: float,
    *,
    realized_pnl: float | None = None,
) -> float:
    """
    Log and record a trade. If ``realized_pnl`` is None, uses legacy random PnL (non-paper path).
    Returns realized PnL for RL / callers.
    """
    _ = sl, tp
    if realized_pnl is None:
        pnl = random.uniform(-size * 0.0005, size * 0.001)
    else:
        pnl = float(realized_pnl)

    analytics.log_trade(pnl)
    strategies[strategy_name].update_pnl(pnl)
    meta.update(strategy_name, pnl)
    update_equity(pnl)
    exit_price = price + pnl
    log_trade_pg(symbol, strategy_name, direction, pnl, size, price, exit_price)
    alert(f"[{Config.TRADING_MODE.upper()}] {direction} {symbol} size {size} PnL {pnl:.2f}")
    return pnl
