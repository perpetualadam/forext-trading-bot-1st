"""Position sizing and simulated execution (matches original paper PnL flow)."""

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


async def execute_trade(
    symbol: str,
    strategy_name: str,
    direction: str,
    size: float,
    price: float,
    sl: float,
    tp: float,
) -> None:
    _ = sl, tp
    pnl = random.uniform(-size * 0.0005, size * 0.001)
    analytics.log_trade(pnl)
    strategies[strategy_name].update_pnl(pnl)
    meta.update(strategy_name, pnl)
    update_equity(pnl)
    exit_price = price + pnl
    log_trade_pg(symbol, strategy_name, direction, pnl, size, price, exit_price)
    alert(f"[{Config.TRADING_MODE.upper()}] {direction} {symbol} size {size} PnL {pnl:.2f}")
