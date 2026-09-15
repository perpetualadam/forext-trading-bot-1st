"""Evaluation loop, evolution, and daily reporting."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from datetime import datetime, timezone

from forex_bot.ai_ensemble import ai
from forex_bot.alerts import alert
from forex_bot.analytics import analytics
from forex_bot.config import Config
from forex_bot.execution import (
    close_fill_path,
    effective_paper_trading,
    is_paper_like_kind,
    open_fill_path,
    pre_trade_entry_blocked_reason,
)
from forex_bot.indicators import compute_indicators
from forex_bot.nn_pred import compute_nn_pred
import forex_bot.oanda_exec as oanda_exec
from forex_bot.oanda_client import fetch_account_summary, fetch_ohlcv, last_account_summary
from forex_bot.execution_metrics import record_fill_failure, record_fill_quality
from forex_bot.orders import (
    OrderStatus,
    finalize_order_fill,
    generate_client_order_id,
    mark_order_failed_or_cancelled,
    try_begin_order_submission,
)
from forex_bot.portfolio_exposure import (
    approx_gross_usd_notional_for,
    configured_max_gross_usd,
    format_notional_cap_report,
    format_notional_cap_skip_alert,
    format_usd_direction_skip,
    notional_cap_decision,
    notional_pct_of_nav,
    portfolio_gross_notional_pct_of_nav,
    usd_direction_guard_decision,
)
from forex_bot.portfolio import PortfolioEngine
from forex_bot.positions import Position, close_position, get_position, open_position
from forex_bot.profit_protection import (
    apply_profit_protection,
    mark_protection_close_attempt,
    pip_size as _pip_size,
    protection_close_allowed,
    seed_position_mfe,
)
from forex_bot.rl_agent import RLAgent
from forex_bot.session_rules import (
    flatten_for_weekend,
    in_active_session,
    is_live_trading,
    live_window_log_enabled,
    log_live_windows,
    pre_close_adjustment,
    symbol_live_window_status,
    volatility_ok,
)
from forex_bot.operational_events import record_operational_transition_if_changed
from forex_bot.state import (
    current_equity,
    last_report_ts,
    record_mid,
    set_last_report_ts,
    state as state_dict,
)
from forex_bot.strategy_meta import select_strategy, seq_model, strategies
from forex_bot.trading import (
    apply_execution_costs,
    apply_latency,
    apply_market_impact,
    calculate_pnl,
    cap_position_units,
    configured_max_portfolio_risk_pct,
    execute_trade,
    portfolio_risk_amount,
    portfolio_risk_cap_exceeded,
    position_sizing,
    sl_tp_distance_for_entry,
    stop_risk_account_ccy,
    strategy_execution_style,
)

logger = logging.getLogger(__name__)

rl_agent = RLAgent()
portfolio = PortfolioEngine()

_last_performance_log_ts: float = 0.0


def _performance_log_enabled() -> bool:
    return (os.getenv("PERFORMANCE_LOG") or "1").strip().lower() not in ("0", "false", "no", "off")


def _performance_log_interval_sec() -> float:
    try:
        return max(0.0, float((os.getenv("PERFORMANCE_LOG_INTERVAL_SEC") or "0").strip() or "0"))
    except ValueError:
        return 0.0


def _maybe_log_performance_metrics() -> None:
    """One identifiable [PERFORMANCE] line per bot cycle, or throttled by PERFORMANCE_LOG_INTERVAL_SEC."""
    global _last_performance_log_ts
    if not _performance_log_enabled():
        return
    now = time.time()
    interval = _performance_log_interval_sec()
    if interval > 0 and (now - _last_performance_log_ts) < interval:
        return
    _last_performance_log_ts = now
    import forex_bot.positions as posmod

    eq = current_equity()
    pf = analytics.profit_factor()
    if pf is None:
        pf_s = "n/a"
    elif pf == float("inf"):
        pf_s = "inf"
    else:
        pf_s = f"{float(pf):.4f}"
    logger.info(
        "[PERFORMANCE] equity=%.2f sharpe=%.4f win_rate_pct=%.2f winrate=%.4f drawdown=%.2f "
        "closed_trades=%s profit_factor=%s open_positions=%s open_symbols=%s",
        eq,
        analytics.sharpe(),
        analytics.win_rate_pct(),
        analytics.winrate(),
        analytics.drawdown(),
        len(analytics.trades),
        pf_s,
        len(posmod.positions),
        sorted(posmod.positions.keys()),
    )


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    return int(v) if v else default


def _min_position_hold_sec() -> float:
    """Seconds to hold before SL/TP exits apply; 0 = disabled (immediate exit on touch)."""
    try:
        return max(0.0, float((os.getenv("MIN_POSITION_HOLD_SEC") or "0").strip() or "0"))
    except ValueError:
        return 0.0


def _position_log_enabled() -> bool:
    return (os.getenv("POSITION_LOG") or "1").strip().lower() not in ("0", "false", "no", "off")


def _log_open_position_line(symbol: str, pos: Position, price: float) -> None:
    """Lightweight snapshot: no extra API/DB; uses current bar mid from evaluate()."""
    mtm = calculate_pnl(pos, price)
    if mtm > 1e-12:
        side = "winning"
    elif mtm < -1e-12:
        side = "losing"
    else:
        side = "flat"
    age_sec = time.time() - float(pos.open_time)
    pip = _pip_size(symbol)
    if pos.direction == "BUY":
        d_sl = float(price) - float(pos.stop_loss)
        d_tp = float(pos.take_profit) - float(price)
    else:
        d_sl = float(pos.stop_loss) - float(price)
        d_tp = float(price) - float(pos.take_profit)
    p_sl = d_sl / pip if pip else 0.0
    p_tp = d_tp / pip if pip else 0.0
    mh = _min_position_hold_sec()
    if mh > 0:
        hold_part = f"min_hold_remain_sec={max(0.0, mh - age_sec):.0f}"
    else:
        hold_part = "min_hold_remain_sec=n/a"
    logger.info(
        "[POSITION] %s dir=%s age_sec=%.0f mtm_pnl=%.5f side=%s mid=%.5f entry=%.5f "
        "dist_to_sl_price=%.5f dist_to_tp_price=%.5f dist_to_sl_pips=%.1f dist_to_tp_pips=%.1f %s",
        symbol,
        pos.direction,
        age_sec,
        mtm,
        side,
        price,
        pos.entry_price,
        d_sl,
        d_tp,
        p_sl,
        p_tp,
        hold_part,
    )


async def evaluate(symbol: str) -> None:
    """Evaluate: manage open positions (TP/SL) or open new risk-based positions (hybrid + AI + RL)."""
    ohlcv_count = _env_int("HYBRID_OHLCV_COUNT", 200)
    raw = fetch_ohlcv(symbol, count=ohlcv_count)
    if raw is None or raw.empty:
        logger.warning("No OHLCV for %s", symbol)
        return

    price = float(raw["close"].iloc[-1])
    record_mid(symbol, price)

    pos = get_position(symbol)
    weekend_flat = flatten_for_weekend()
    # Session / weekend-flatten gates block *new entries* only — always manage open risk first.
    if pos is None and (not in_active_session(symbol) or weekend_flat):
        if weekend_flat:
            logger.info("%s: skip new open — weekend flatten window (before Friday FX close)", symbol)
        else:
            alert(f"{symbol}: Market closed, skipping trade")
        return

    if pos:
        if _position_log_enabled():
            _log_open_position_line(symbol, pos, price)
        seed_position_mfe(pos, price, raw)
        pp = apply_profit_protection(pos, price, ohlcv=raw)
        sl_tp_hit = False
        if pos.direction == "BUY":
            sl_tp_hit = price <= pos.stop_loss or price >= pos.take_profit
        else:
            sl_tp_hit = price >= pos.stop_loss or price <= pos.take_profit
        protect_hit = bool(pp.should_close)
        if protect_hit and not protection_close_allowed(pos):
            logger.warning(
                "%s: profit-protection close deferred — previous close attempt still cooling down",
                symbol,
            )
            protect_hit = False
        close_hit = sl_tp_hit

        if weekend_flat and not close_hit and not protect_hit:
            alert(f"{symbol}: Weekend flatten — closing before Friday FX close (avoid weekend gap)")

        if close_hit or weekend_flat or protect_hit:
            mh = _min_position_hold_sec()
            if (
                close_hit
                and not weekend_flat
                and not protect_hit
                and mh > 0
                and (time.time() - float(pos.open_time)) < mh
            ):
                logger.debug(
                    "%s: SL/TP touched but min hold %.0fs not met (age=%.1fs)",
                    symbol,
                    mh,
                    time.time() - float(pos.open_time),
                )
                return
            fill_path = close_fill_path(symbol, pos.execution_kind)
            if fill_path == "abort_broker_disabled":
                if protect_hit:
                    mark_protection_close_attempt(pos)
                alert(
                    f"{symbol}: Skip close — live position requires a broker fill but "
                    f"EXECUTION_MODE/USE_OANDA_LIVE is not sending orders (fail closed)"
                )
                logger.error("%s: live close aborted — broker orders disabled", symbol)
                return

            spr_c: float | None
            slp_c: float | None
            impact_amt: float
            exit_price_exec: float
            lat_ms: int

            if fill_path == "simulate":
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
                if fill_path == "broker":
                    alert(
                        f"[EXECUTION] BROKER_CLOSE {symbol} mid={price:.5f} "
                        f"(PositionClose; local mid is pre-fill only)"
                    )
                else:
                    alert(
                        f"[EXECUTION] MID {symbol} close mid={price:.5f} "
                        f"(paper/window_paper; no broker order)"
                    )

            if protect_hit:
                mark_protection_close_attempt(pos)
            close_reason = "sl_tp" if sl_tp_hit else (
                "weekend_flatten" if weekend_flat and not protect_hit else (
                    "profit_protection" if protect_hit else "close"
                )
            )
            diagnostics = None
            try:
                from forex_bot.trade_diagnostics import snapshot_from_position

                diagnostics = snapshot_from_position(
                    pos, exit_reason=close_reason, exit_price=exit_price_exec
                )
            except Exception:
                logger.exception("%s: trade diagnostics snapshot failed (ignored)", symbol)
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
                    diagnostics=diagnostics,
                )
            except Exception as exc:
                logger.exception("%s: close execution/logging failed: %s", symbol, exc)
                return
            close_position(symbol)
            rl_agent.update(pos.rl_state, pos.direction, pnl)
            logger.info(
                "[CLOSE] %s | Dir=%s | Units=%.4f | PnL=%.5f | entry=%.5f exit=%.5f | "
                "state=%s | reason=%s",
                symbol,
                pos.direction,
                pos.units,
                pnl,
                pos.entry_price,
                exit_price_exec,
                pos.rl_state,
                close_reason,
            )
        return

    blocked = pre_trade_entry_blocked_reason()
    if blocked:
        logger.warning("%s: new entry blocked — %s", symbol, blocked)
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

    # RL is a gate: SKIP blocks; BUY/SELL must agree with AI (never override AI side).
    direction = str(ai_decision.get("direction", "BUY")).upper().strip()
    if direction not in ("BUY", "SELL"):
        direction = "BUY"
    rl_action = rl_agent.decide(state)
    if rl_action == "SKIP":
        logger.info("%s: RL decided to skip trade (state=%s)", symbol, state)
        return
    if rl_action in ("BUY", "SELL") and rl_action != direction:
        logger.info(
            "%s: RL gate blocked (rl=%s ai=%s state=%s)",
            symbol,
            rl_action,
            direction,
            state,
        )
        return
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
    if notional_pct_of_nav() <= 0:
        units *= weight * confidence
    units = cap_position_units(units)
    if notional_pct_of_nav() > 0:
        units = math.floor(float(units) + 1e-9)
        if units < 1:
            logger.info(
                "%s: skip — per-trade notional size rounds below 1 OANDA unit (NAV=%.2f)",
                symbol,
                balance,
            )
            return
        logger.info(
            "[SIZE] %s units=%.0f notional≈%.2f USD (per-trade %.2f%% of NAV %.2f; "
            "portfolio cap %.2f%% ≈ %.2f USD)",
            symbol,
            units,
            approx_gross_usd_notional_for(symbol, float(units), float(price)),
            notional_pct_of_nav() * 100.0,
            balance,
            portfolio_gross_notional_pct_of_nav() * 100.0,
            configured_max_gross_usd(),
        )

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
    paper = effective_paper_trading()
    fill_path = open_fill_path(symbol)
    if fill_path == "abort_broker_disabled":
        alert(
            f"{symbol}: Skip open — inside live window but broker orders are disabled "
            f"(set EXECUTION_MODE=live_broker or paper_broker; fail closed, no local live fill)"
        )
        logger.error("%s: live open aborted — broker orders disabled", symbol)
        return
    use_live_fill = fill_path == "broker"
    if use_live_fill:
        exec_kind = "live"
    else:
        exec_kind = "simulated" if paper else "window_paper"

    if is_paper_like_kind(exec_kind):
        from forex_bot.reconciliation import paper_open_blocked_reason

        skip_why = paper_open_blocked_reason(symbol)
        if skip_why:
            logger.warning("[PAPER SKIP] %s | %s", symbol, skip_why)
            return

    use_sim_layers = fill_path == "simulate"
    if live_window_log_enabled():
        win = symbol_live_window_status(symbol)
        logger.info(
            "[LIVE WINDOW] %s %s → exec=%s | local=%s %s | utc=%s | now_local=%s | now_utc=%s | "
            "tz=%s offset=%s | paper=%s",
            symbol,
            "IN" if live_allowed else "OUT",
            exec_kind,
            win["local_window"],
            win["dst_label"],
            win["utc_window"],
            win["now_local"],
            win["now_utc"],
            win["timezone"],
            win["utc_offset"],
            paper,
        )
    # QUOTA: future per-symbol daily caps should run only when use_sim_layers is True
    # LIVE WINDOW CHECK END

    if not use_live_fill and not paper:
        win = symbol_live_window_status(symbol)
        alert(
            f"{symbol}: Outside live window — local {win['local_window']} {win['dst_label']} "
            f"(UTC {win['utc_window']}); now {win['now_local']} {win['dst_label']} / "
            f"{win['now_utc']} UTC — paper-style fills until the window opens "
            f"(hybrid/AI/RL unchanged)"
        )

    approx_add = approx_gross_usd_notional_for(symbol, float(units), float(price))
    cap_decision = notional_cap_decision(approx_add)
    acct = last_account_summary()
    ccy = str(acct.get("currency") or "")
    nav = acct.get("NAV")
    if cap_decision["exceeds"]:
        msg = format_notional_cap_skip_alert(
            symbol, cap_decision, nav=nav, currency=ccy, direction=direction
        )
        alert(msg)
        logger.warning("%s", msg)
        return
    logger.info(
        "%s",
        format_notional_cap_report(
            symbol, cap_decision, nav=nav, currency=ccy, allowed=True, direction=direction
        ),
    )

    # Stop risk in account currency (handles USD_* quote conversion).
    new_risk_at_stop = stop_risk_account_ccy(symbol, float(price), float(sl_d), float(units))
    if portfolio_risk_cap_exceeded(current_equity(), new_risk_at_stop):
        eq = current_equity()
        open_risk = portfolio_risk_amount()
        projected = open_risk + float(new_risk_at_stop)
        cap_pct = configured_max_portfolio_risk_pct()
        cap_amt = max(0.0, float(eq)) * cap_pct
        alert(
            f"{symbol}: Skip open — portfolio stop risk cap\n"
            f"Candidate symbol: {symbol}\n"
            f"Candidate side: {direction}\n"
            f"Current stop-risk exposure: {open_risk:.2f}\n"
            f"Projected stop-risk exposure: {projected:.2f}\n"
            f"Configured cap: {cap_amt:.2f} ({cap_pct * 100:.2f}% of equity {eq:.2f})\n"
            f"Rejection reason: projected stop risk exceeds MAX_PORTFOLIO_RISK_PCT"
        )
        return

    usd_dir_decision = usd_direction_guard_decision(symbol, direction)
    if usd_dir_decision["exceeds"]:
        msg = format_usd_direction_skip(usd_dir_decision)
        alert(msg)
        logger.warning("%s", msg)
        return

    entry_price: float
    spread_amt: float
    slip_amt: float
    impact_amt: float
    position_units: float = float(units)

    broker_oid = ""
    client_order_id = ""
    if fill_path == "broker":
        if is_paper_like_kind(exec_kind):
            logger.error(
                "%s: refuse broker open — fill_path=broker but exec_kind=%s",
                symbol,
                exec_kind,
            )
            return
        client_order_id = generate_client_order_id()
        t_reserve = time.perf_counter()
        if not try_begin_order_submission(
            client_order_id=client_order_id,
            symbol=symbol,
            direction=direction,
            units=float(units),
            metadata={"mid": float(price), "strategy": strategy_name},
        ):
            logger.warning("%s: idempotent skip — duplicate client_order_id or DB conflict", symbol)
            return
        t_sent = time.perf_counter()
        # Pre-compute SL/TP from mid so broker can attach protective orders on fill.
        if direction == "BUY":
            broker_sl = float(price) - float(sl_d)
            broker_tp = float(price) + float(tp_d)
        else:
            broker_sl = float(price) + float(sl_d)
            broker_tp = float(price) - float(tp_d)
        try:
            fill_price, filled_u, oid, _pl = await oanda_exec.execute_oanda_market_open(
                symbol,
                units,
                direction,
                client_order_id,
                stop_loss=broker_sl,
                take_profit=broker_tp,
                execution_kind=exec_kind,
            )
        except Exception as exc:
            record_fill_failure()
            mark_order_failed_or_cancelled(client_order_id)
            logger.warning("[ORDER FAILED] %s open: %s", symbol, exc)
            return
        t_fill = time.perf_counter()
        entry_price = float(fill_price)
        spread_amt = 0.0
        slip_amt = 0.0
        impact_amt = 0.0
        st = OrderStatus.FILLED
        if float(filled_u) + 1e-6 < float(units):
            st = OrderStatus.PARTIAL
            logger.info("[ORDER PARTIAL] %s filled=%.4f requested=%.4f", symbol, filled_u, units)
        position_units = float(filled_u)
        broker_oid = str(oid) if oid else ""
        finalize_order_fill(
            client_order_id,
            broker_order_id=str(oid) if oid else "",
            fill_price=entry_price,
            units_filled=float(filled_u),
            status=st,
            metadata={
                "expected_mid": float(price),
                "slippage_signed": (entry_price - float(price))
                if direction == "BUY"
                else (float(price) - entry_price),
            },
        )
        record_fill_quality(
            expected_price=float(price),
            fill_price=entry_price,
            direction=direction,
            latency_signal_to_send_ms=(t_sent - t_reserve) * 1000.0,
            latency_send_to_fill_ms=(t_fill - t_sent) * 1000.0,
        )
        alert(
            f"[EXECUTION] BROKER_FILL {symbol} open fill={entry_price:.5f} units≈{filled_u:.4f} id={oid} cid={client_order_id}"
        )
    elif use_sim_layers:
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
            f"[EXECUTION] MID {symbol} open mid={price:.5f} "
            f"(paper/window_paper; no broker order; live_allowed={live_allowed} exec_kind={exec_kind})"
        )

    if direction == "BUY":
        stop_loss = entry_price - sl_d
        take_profit = entry_price + tp_d
    else:
        stop_loss = entry_price + sl_d
        take_profit = entry_price - tp_d

    atr_entry = None
    try:
        from forex_bot.indicators import latest_atr_price
        from forex_bot.profit_protection import atr_to_pips, profit_protection_atr_period

        atr_px = latest_atr_price(raw, profit_protection_atr_period())
        if atr_px is not None:
            atr_entry = atr_to_pips(symbol, atr_px)
    except Exception:
        logger.exception("%s: ATR-at-entry snapshot failed (ignored)", symbol)
    open_position(
        Position(
            symbol=symbol,
            direction=direction,
            units=float(position_units),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            open_time=datetime.utcnow().timestamp(),
            strategy_name=strategy_name,
            rl_state=state,
            execution_kind=exec_kind,
            atr_at_entry_pips=atr_entry,
            client_order_id=client_order_id,
            broker_order_id=broker_oid,
            broker_order=fill_path == "broker",
        )
    )
    if fill_path == "broker":
        alert(
            f"[OPEN] {symbol} {direction} units={position_units:.2f} entry={entry_price:.5f} "
            f"mid={price:.5f} SL={stop_loss:.5f} TP={take_profit:.5f} kind={exec_kind} "
            f"broker_order=true cid={client_order_id} broker_id={broker_oid} "
            f"strategy={strategy_name} horizon={horizon}"
        )
    else:
        alert(
            f"[OPEN] {symbol} {direction} units={position_units:.2f} entry={entry_price:.5f} "
            f"mid={price:.5f} SL={stop_loss:.5f} TP={take_profit:.5f} kind={exec_kind} "
            f"broker_order=false strategy={strategy_name} horizon={horizon}"
        )
    logger.info(
        "[AI+RL] %s | OPEN Dir=%s | Units=%.4f | Conf=%.2f | RL_Action=%s | State=%s | %s lb=%s",
        symbol,
        direction,
        position_units,
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
    """Emit DAILY REPORT alert at most once per ``DAILY_REPORT_INTERVAL_SEC`` (default 86400 = 24h). Set 0 to disable."""
    try:
        interval = float((os.getenv("DAILY_REPORT_INTERVAL_SEC") or "86400").strip() or "86400")
    except ValueError:
        interval = 86400.0
    if interval <= 0:
        return
    now = time.time()
    last = last_report_ts()
    if last is not None and (now - last) < interval:
        return
    set_last_report_ts(now)
    eq = current_equity()
    alert(
        f" DAILY REPORT: Equity={eq:.2f} Sharpe={analytics.sharpe():.2f} "
        f"Winrate={analytics.winrate():.2%} Drawdown={analytics.drawdown():.2f}"
    )


async def run_bot() -> None:
    while True:
        try:
            # Reconciliation runs in app.reconciliation_loop only (avoid concurrent mutation).
            await asyncio.to_thread(fetch_account_summary)
            for s in Config.SYMBOLS:
                await evaluate(s)
            state_dict["last_bot_cycle_utc"] = datetime.now(timezone.utc).isoformat()
            record_operational_transition_if_changed()
            portfolio.update(
                {
                    "equity": current_equity(),
                    "sharpe": analytics.sharpe(),
                    "drawdown": analytics.drawdown(),
                    "winrate": analytics.winrate(),
                    "win_rate_pct": analytics.win_rate_pct(),
                }
            )
            if live_window_log_enabled():
                log_live_windows(reason="cycle")
            _maybe_log_performance_metrics()
            evolve()
            daily_report()
        except Exception as exc:
            logger.exception("run_bot iteration error: %s", exc)
        await asyncio.sleep(Config.TRADE_INTERVAL)
