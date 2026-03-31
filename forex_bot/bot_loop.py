"""Evaluation loop, evolution, and daily reporting."""

from __future__ import annotations

import asyncio
import logging
import math
import os
from datetime import datetime

from forex_bot.ai_ensemble import ai
from forex_bot.alerts import alert
from forex_bot.analytics import analytics
from forex_bot.config import Config
from forex_bot.indicators import compute_indicators
from forex_bot.nn_pred import compute_nn_pred
from forex_bot.oanda_client import fetch_ohlcv
from forex_bot.portfolio import PortfolioEngine
from forex_bot.positions import Position, close_position, get_position, open_position
from forex_bot.rl_agent import RLAgent
from forex_bot.session_rules import (
    in_active_session,
    is_live_trading,
    pre_close_adjustment,
    simulation_layers_enabled,
    volatility_ok,
)
from forex_bot.state import current_equity, last_report_day, set_last_report_day
from forex_bot.strategy_meta import select_strategy, seq_model, strategies
from forex_bot.trading import (
    apply_execution_costs,
    apply_latency,
    apply_market_impact,
    calculate_pnl,
    cap_position_units,
    execute_trade,
    portfolio_risk_amount,
    portfolio_risk_cap_exceeded,
    position_sizing,
    sl_tp_distance_for_entry,
    strategy_execution_style,
)

logger = logging.getLogger(__name__)

rl_agent = RLAgent()
portfolio = PortfolioEngine()


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    return int(v) if v else default


async def evaluate(symbol: str) -> None:
    """Evaluate: manage open positions (TP/SL) or open new risk-based positions (hybrid + AI + RL)."""
    if not in_active_session(symbol):
        alert(f"{symbol}: Market closed, skipping trade")
        return

    ohlcv_count = _env_int("HYBRID_OHLCV_COUNT", 200)
    raw = fetch_ohlcv(symbol, count=ohlcv_count)
    if raw is None or raw.empty:
        logger.warning("No OHLCV for %s", symbol)
        return

    price = float(raw["close"].iloc[-1])

    pos = get_position(symbol)
    if pos:
        close_hit = False
        if pos.direction == "BUY":
            close_hit = price <= pos.stop_loss or price >= pos.take_profit
        else:
            close_hit = price >= pos.stop_loss or price <= pos.take_profit

        if close_hit:
            # LIVE WINDOW CHECK START
            live_allowed = is_live_trading(symbol)
            use_sim_layers = simulation_layers_enabled(symbol, Config.PAPER_TRADING)
            # QUOTA overrides: per-symbol daily caps (when implemented) should only apply when
            # use_sim_layers is True; broker-live path skips quotas.
            _ = live_allowed
            # LIVE WINDOW CHECK END

            spr_c: float | None
            slp_c: float | None
            impact_amt: float
            exit_price_exec: float
            lat_ms: int

            if use_sim_layers:
                # SIMULATION CONTROL START
                lat_ms = await apply_latency()
                route_lb = _env_int("HYBRID_ROUTE_LOOKBACK", 60)
                df_px = compute_indicators(raw, lookback=route_lb)
                atr_v = float(df_px["atr"].iloc[-1])
                if math.isnan(atr_v) or atr_v <= 0:
                    atr_v = 0.0001
                strat_style = strategy_execution_style(pos.strategy_name)
                exit_leg = "SELL" if pos.direction == "BUY" else "BUY"
                mid_impact, impact_amt = apply_market_impact(pos.units, price, exit_leg)
                exit_price_exec, spr_c, slp_c = apply_execution_costs(
                    symbol, exit_leg, mid_impact, atr_v, strat_style
                )
                pnl = calculate_pnl(pos, exit_price_exec)
                alert(
                    f"[EXECUTION] {symbol} close latency={lat_ms}ms impact={impact_amt:.6f} "
                    f"spread={spr_c:.5f} slippage={slp_c:.5f}"
                )
                # SIMULATION CONTROL END
            else:
                lat_ms = 0
                spr_c, slp_c = None, None
                impact_amt = 0.0
                exit_price_exec = float(price)
                pnl = calculate_pnl(pos, exit_price_exec)
                alert(
                    f"[EXECUTION] LIVE_RAW {symbol} close mid={price:.5f} "
                    f"(no latency/impact/spread sim; live_allowed={live_allowed})"
                )

            try:
                pnl = await execute_trade(
                    pos.symbol,
                    pos.strategy_name,
                    pos.direction,
                    pos.units,
                    pos.entry_price,
                    pos.stop_loss,
                    pos.take_profit,
                    realized_pnl=pnl,
                    execution_kind=pos.execution_kind,
                    exit_price=exit_price_exec,
                    spread_component=spr_c,
                    slippage_component=slp_c,
                )
            except Exception as exc:
                logger.exception("%s: close execution/logging failed: %s", symbol, exc)
                return
            close_position(symbol)
            rl_agent.update(pos.rl_state, pos.direction, pnl)
            logger.info(
                "[CLOSE] %s | Dir=%s | Units=%.4f | PnL=%.5f | entry=%.5f exit=%.5f | state=%s",
                symbol,
                pos.direction,
                pos.units,
                pnl,
                pos.entry_price,
                exit_price_exec,
                pos.rl_state,
            )
        return

    route_lookback = _env_int("HYBRID_ROUTE_LOOKBACK", 60)
    df_route = compute_indicators(raw, lookback=route_lookback)

    strategy_name, lookback, horizon = select_strategy(symbol, df_route)
    if strategy_name is None:
        return
    strat = strategies[strategy_name]
    if not strat.active:
        return

    df = compute_indicators(raw, lookback=lookback)
    if not volatility_ok(df):
        alert(f"{symbol}: Volatility outside safe range, skipping trade")
        return

    price = float(df["close"].iloc[-1])
    seq_model.update(symbol, price)
    seq_pred = seq_model.predict(symbol)
    nn_pred = compute_nn_pred(price, seq_pred)

    ma_fast = float(df["ma_fast"].iloc[-1])
    ma_slow = float(df["ma_slow"].iloc[-1])
    atr_v = float(df["atr"].iloc[-1])
    ret_1 = float(df["close"].pct_change().iloc[-1]) if len(df) > 1 else 0.0

    ai_decision = await ai.vote(
        {
            "symbol": symbol,
            "strategy": strategy_name,
            "price": price,
            "nn_pred": nn_pred,
            "seq_pred": seq_pred,
            "horizon": horizon,
            "lookback": lookback,
            "hybrid": horizon != "legacy",
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "sma_fast": ma_fast,
            "sma_slow": ma_slow,
            "returns": ret_1,
            "atr": atr_v,
        },
        symbol,
    )
    if not ai_decision["allow"]:
        return

    trend_v = float(df["trend"].iloc[-1])
    vol_v = float(df["volatility"].iloc[-1])
    if math.isnan(trend_v):
        trend_v = 0.0
    if math.isnan(vol_v):
        vol_v = 0.0
    state = f"{round(trend_v, 4)}_{round(vol_v, 6)}"

    rl_action = rl_agent.decide(state)
    if rl_action == "SKIP":
        logger.info("%s: RL decided to skip trade (state=%s)", symbol, state)
        return

    direction = rl_action if rl_action in ("BUY", "SELL") else str(ai_decision["direction"])
    confidence = float(ai_decision.get("confidence", 0.6))

    weight = portfolio.get_weight(symbol)
    atr_v = float(df["atr"].iloc[-1])
    if math.isnan(atr_v) or atr_v <= 0:
        atr_v = 0.0001
    strat_style = strategy_execution_style(strategy_name)
    sl_d, tp_d = sl_tp_distance_for_entry(symbol, atr_v)
    stop_mid = price - sl_d if direction == "BUY" else price + sl_d

    balance = current_equity()
    units = position_sizing(symbol, price, stop_mid, balance)
    units *= weight * confidence
    units = cap_position_units(units)

    # MICRO_STRATEGY / LOT_SIZE HOOK START (optional — uncomment and implement)
    # sym_u = symbol.upper().replace("-", "_")
    # _lot = (os.getenv(f"LOT_SIZE_OVERRIDE_{sym_u}") or "").strip()
    # if _lot:
    #     units = max(1.0, float(_lot))
    # _micro = (os.getenv(f"MICRO_STRATEGY_{sym_u}") or "").strip()
    # if _micro:
    #     pass  # e.g. scale units or gate entries by label (scalp_1h, etc.)
    # MICRO_STRATEGY / LOT_SIZE HOOK END

    if units < 1e-6:
        return

    if pre_close_adjustment(symbol):
        alert(f"{symbol}: Near session close, reducing position size by 50%")
        units *= 0.5
        if units < 1.0:
            return

    alert(
        f"[HYBRID] {symbol} | horizon={horizon} | lookback={lookback} | "
        f"strategy={strategy_name} | route_lb={route_lookback}"
    )

    # live_allowed = is_live_trading(symbol, use_scalp_window=True)
    # LIVE WINDOW CHECK START
    live_allowed = is_live_trading(symbol)
    use_live_fill = (not Config.PAPER_TRADING) and live_allowed
    if use_live_fill:
        exec_kind = "live"
    else:
        exec_kind = "simulated" if Config.PAPER_TRADING else "window_paper"

    use_sim_layers = simulation_layers_enabled(symbol, Config.PAPER_TRADING)
    # QUOTA: future per-symbol daily caps should run only when use_sim_layers is True
    # LIVE WINDOW CHECK END

    if not use_live_fill and not Config.PAPER_TRADING:
        alert(
            f"{symbol}: Outside live trading window (UTC) — position will use paper-style "
            f"fills until closed (hybrid/AI/RL unchanged)"
        )

    entry_price: float
    spread_amt: float
    slip_amt: float
    impact_amt: float

    if use_sim_layers:
        # SIMULATION CONTROL START
        lat_ms = await apply_latency()
        mid_impact, impact_amt = apply_market_impact(units, price, direction)
        entry_price, spread_amt, slip_amt = apply_execution_costs(
            symbol, direction, mid_impact, atr_v, strat_style
        )
        alert(
            f"[EXECUTION] {symbol} open latency={lat_ms}ms impact={impact_amt:.6f} "
            f"spread={spread_amt:.5f} slippage={slip_amt:.5f}"
        )
        # SIMULATION CONTROL END
    else:
        entry_price = float(price)
        spread_amt = 0.0
        slip_amt = 0.0
        impact_amt = 0.0
        alert(
            f"[EXECUTION] LIVE_RAW {symbol} open mid={price:.5f} "
            f"(no latency/impact/spread sim; live_allowed={live_allowed} exec_kind={exec_kind})"
        )

    if direction == "BUY":
        stop_loss = entry_price - sl_d
        take_profit = entry_price + tp_d
    else:
        stop_loss = entry_price + sl_d
        take_profit = entry_price - tp_d

    new_risk = abs(float(entry_price) - float(stop_loss)) * float(units)
    if portfolio_risk_cap_exceeded(current_equity(), new_risk):
        alert(
            f"{symbol}: Skip open — portfolio stop risk would exceed "
            f"MAX_PORTFOLIO_RISK_PCT (open≈{portfolio_risk_amount():.2f} + new≈{new_risk:.2f} vs cap)."
        )
        return

    open_position(
        Position(
            symbol=symbol,
            direction=direction,
            units=float(units),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            open_time=datetime.utcnow().timestamp(),
            strategy_name=strategy_name,
            rl_state=state,
            execution_kind=exec_kind,
        )
    )
    alert(
        f"[OPEN] {symbol} {direction} units={units:.2f} entry={entry_price:.5f} mid={price:.5f} "
        f"SL={stop_loss:.5f} TP={take_profit:.5f} kind={exec_kind}"
    )
    logger.info(
        "[AI+RL] %s | OPEN Dir=%s | Units=%.4f | Conf=%.2f | RL_Action=%s | State=%s | %s lb=%s",
        symbol,
        direction,
        units,
        confidence,
        rl_action,
        state,
        horizon,
        lookback,
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
            portfolio.update(
                {
                    "equity": current_equity(),
                    "sharpe": analytics.sharpe(),
                    "drawdown": analytics.drawdown(),
                    "winrate": analytics.winrate(),
                    "win_rate_pct": analytics.win_rate_pct(),
                }
            )
            evolve()
            daily_report()
        except Exception as exc:
            logger.exception("run_bot iteration error: %s", exc)
        await asyncio.sleep(Config.TRADE_INTERVAL)
