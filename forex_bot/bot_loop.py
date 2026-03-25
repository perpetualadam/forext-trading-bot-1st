"""Evaluation loop, evolution, and daily reporting."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from forex_bot.ai_ensemble import ai
from forex_bot.alerts import alert
from forex_bot.analytics import analytics
from forex_bot.config import Config
from forex_bot.indicators import compute_indicators
from forex_bot.oanda_client import fetch_ohlcv
from forex_bot.session_rules import in_active_session, pre_close_adjustment, volatility_ok
from forex_bot.state import current_equity, last_report_day, set_last_report_day
from forex_bot.strategy_meta import select_strategy, seq_model, strategies
from forex_bot.trading import execute_trade, position_sizing

logger = logging.getLogger(__name__)


async def evaluate(symbol: str) -> None:
    if not in_active_session(symbol):
        alert(f"{symbol}: Market closed, skipping trade")
        return

    df = fetch_ohlcv(symbol)
    if df is None or df.empty:
        logger.warning("No OHLCV for %s", symbol)
        return

    df = compute_indicators(df)
    if not volatility_ok(df):
        alert(f"{symbol}: Volatility outside safe range, skipping trade")
        return

    strategy_name = select_strategy()
    if strategy_name is None:
        return
    strat = strategies[strategy_name]
    if not strat.active:
        return

    price = float(df["close"].iloc[-1])
    seq_model.update(symbol, price)
    seq_pred = seq_model.predict(symbol)
    nn_pred = price + random.uniform(-0.0005, 0.0005)

    ai_decision = await ai.vote(
        {
            "symbol": symbol,
            "strategy": strategy_name,
            "price": price,
            "nn_pred": nn_pred,
            "seq_pred": seq_pred,
        },
        symbol,
    )
    if not ai_decision["allow"]:
        return

    size = position_sizing(symbol, ai_decision)
    if pre_close_adjustment(symbol):
        alert(f"{symbol}: Near session close, reducing trade size by 50%")
        size *= 0.5
        if size < 1:
            return

    direction = str(ai_decision["direction"])
    await execute_trade(
        symbol,
        strategy_name,
        direction,
        size,
        price,
        price - 0.002,
        price + 0.004,
    )


def evolve() -> None:
    for name, strat in strategies.items():
        if len(strat.pnl) < 20:
            continue
        if strat.sharpe() < 0:
            strat.active = False
            logger.info("Strategy disabled (sharpe < 0): %s", name)


def daily_report() -> None:
    today = datetime.now().date()
    if last_report_day() == today:
        return
    set_last_report_day(today)
    eq = current_equity()
    alert(
        f" DAILY REPORT: Equity={eq:.2f} Sharpe={analytics.sharpe():.2f} "
        f"Winrate={analytics.winrate():.2%} Drawdown={analytics.drawdown():.2f}"
    )


async def run_bot() -> None:
    while True:
        try:
            await asyncio.gather(*(evaluate(s) for s in Config.SYMBOLS))
            evolve()
            daily_report()
        except Exception as exc:
            logger.exception("run_bot iteration error: %s", exc)
        await asyncio.sleep(Config.TRADE_INTERVAL)
