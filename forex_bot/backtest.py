"""
Historical backtest across preset macro regimes (stress + calm years).

Uses OANDA ``from``/``to`` candles **or** a local OHLCV CSV (``--csv`` / ``BACKTEST_CSV``).
Same signal path as :func:`forex_bot.bot_loop.evaluate` with historical bar times.
Run: ``python -m forex_bot.backtest --help``

TODO (execution parity): optional broker-style order lifecycle + slippage/latency simulation;
current path remains bar-close fills unless extended here.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

# Set before ai_ensemble import so ensemble init can log backtest mode.
os.environ["FOREX_BACKTEST"] = "1"

from forex_bot.ai_ensemble import ai
from forex_bot.alerts import alert
from forex_bot.analytics import Analytics
from forex_bot.config import Config
from forex_bot.csv_ohlcv import filter_ohlcv_date_range, load_ohlcv_csv
from forex_bot.experiment import experiment_snapshot_with_voters
from forex_bot.indicators import compute_indicators
from forex_bot.nn_pred import compute_nn_pred
from forex_bot.oanda_client import fetch_ohlcv_range
from forex_bot.portfolio import PortfolioEngine
from forex_bot.positions import Position, close_position, get_position, open_position
import forex_bot.positions as posmod
from forex_bot.rl_agent import RLAgent
from forex_bot.session_rules import (
    in_active_session_at,
    pre_close_adjustment_at,
    simulation_layers_enabled,
    volatility_ok,
)
import forex_bot.state as st
from forex_bot.strategy_meta import (
    SCALP_STRATEGY_KEYS,
    SWING_STRATEGY_KEYS,
    MetaLearner,
    SeqModel,
    Strategy,
    select_strategy,
)
import forex_bot.strategy_meta as sm
import forex_bot.trading as trading_mod
from forex_bot.trading import (
    apply_execution_costs,
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


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    return int(v) if v else default


def _env_bool(name: str, default: bool) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def _min_position_hold_sec() -> float:
    try:
        return max(0.0, float((os.getenv("MIN_POSITION_HOLD_SEC") or "0").strip() or "0"))
    except ValueError:
        return 0.0


def _parse_ts(val: Any) -> datetime:
    p = pd.Timestamp(val)
    if p.tzinfo is not None:
        p = p.tz_convert("UTC").tz_localize(None)
    return p.to_pydatetime()


def _max_drawdown(equity: list[float]) -> float:
    if len(equity) < 2:
        return 0.0
    arr = np.array(equity, dtype=float)
    peak = np.maximum.accumulate(arr)
    dd = peak - arr
    return float(np.max(dd))


def _sharpe_from_pnls(pnls: list[float]) -> float:
    r = np.array(pnls, dtype=float)
    if len(r) < 2:
        return 0.0
    std = float(r.std())
    if std < 1e-12:
        return 0.0
    return float(r.mean() / std)


@dataclass
class RegimePeriod:
    """Named UTC window for scenario testing."""

    id: str
    label: str
    start: datetime
    end: datetime


# Curated macro windows (UTC) for scenario testing — **not** “from OANDA founding until now”.
# OANDA’s company history goes back to the 1990s; REST candle retention is per-instrument and
# granularity (often many years for majors, but not guaranteed back to the 1990s for M5). These
# ranges start at 2011 so typical EUR_USD M5 history is available; trim or shift if your feed is shorter.
REGIME_PERIODS: tuple[RegimePeriod, ...] = (
    RegimePeriod(
        "euro_crisis_2011",
        "Euro debt stress / risk-off (2011–2012)",
        datetime(2011, 8, 1, 0, 0, 0),
        datetime(2012, 6, 30, 23, 59, 59),
    ),
    RegimePeriod(
        "usd_rally_2014",
        "USD strength / EM stress (2014–2015)",
        datetime(2014, 6, 1, 0, 0, 0),
        datetime(2015, 3, 31, 23, 59, 59),
    ),
    RegimePeriod(
        "brexit_2016",
        "Brexit referendum volatility (2016)",
        datetime(2016, 5, 1, 0, 0, 0),
        datetime(2016, 12, 31, 23, 59, 59),
    ),
    RegimePeriod(
        "covid_2020",
        "COVID crash & rebound (2020)",
        datetime(2020, 2, 15, 0, 0, 0),
        datetime(2020, 6, 30, 23, 59, 59),
    ),
    RegimePeriod(
        "inflation_2022",
        "Fed hikes / inflation regime (2022)",
        datetime(2022, 1, 1, 0, 0, 0),
        datetime(2022, 12, 31, 23, 59, 59),
    ),
    RegimePeriod(
        "calm_2024",
        "Comparatively calmer year (2024)",
        datetime(2024, 1, 1, 0, 0, 0),
        datetime(2024, 12, 31, 23, 59, 59),
    ),
)


@dataclass
class RegimeBacktestResult:
    regime_id: str
    label: str
    bars: int
    decisions: int
    trades_closed: int
    total_pnl: float
    sharpe_trades: float
    max_drawdown: float
    final_equity: float
    equity_curve: list[float] = field(default_factory=list)


def _evolve_strategies() -> None:
    for _, strat in sm.strategies.items():
        if len(strat.pnl) < 20:
            continue
        if strat.sharpe() < 0:
            strat.active = False


async def _backtest_bar(
    symbol: str,
    raw: pd.DataFrame,
    now_utc: datetime,
    *,
    rl: RLAgent,
    portfolio: PortfolioEngine,
    bar_seed: int,
    indicator_scale_n: int | None = None,
) -> None:
    """One evaluate-equivalent step using historical ``now_utc`` (mirrors ``bot_loop.evaluate``)."""
    random.seed(bar_seed)
    np.random.seed(bar_seed % (2**32))

    if not in_active_session_at(symbol, now_utc):
        return

    ohlcv_count = _env_int("HYBRID_OHLCV_COUNT", 200)
    if len(raw) < max(30, ohlcv_count // 4):
        return

    _scale_kw: dict[str, Any] = {}
    if indicator_scale_n is not None:
        _scale_kw["indicator_scale_n"] = indicator_scale_n

    price = float(raw["close"].iloc[-1])
    pos = get_position(symbol)

    if pos:
        close_hit = False
        if pos.direction == "BUY":
            close_hit = price <= pos.stop_loss or price >= pos.take_profit
        else:
            close_hit = price >= pos.stop_loss or price <= pos.take_profit

        if close_hit:
            mh = _min_position_hold_sec()
            if mh > 0 and (now_utc.timestamp() - float(pos.open_time)) < mh:
                return
            live_allowed = False  # paper backtest
            use_sim_layers = simulation_layers_enabled(symbol, True)

            spr_c: float | None
            slp_c: float | None
            impact_amt: float
            exit_price_exec: float
            lat_ms: int

            if use_sim_layers:
                lat_ms = await trading_mod.apply_latency()
                route_lb = _env_int("HYBRID_ROUTE_LOOKBACK", 60)
                df_px = compute_indicators(raw, lookback=route_lb, **_scale_kw)
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
            else:
                lat_ms = 0
                spr_c, slp_c = None, None
                impact_amt = 0.0
                exit_price_exec = float(price)
                pnl = calculate_pnl(pos, exit_price_exec)

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
                logger.exception("%s: close execution failed: %s", symbol, exc)
                return
            close_position(symbol)
            rl.update(pos.rl_state, pos.direction, pnl)
        return

    route_lookback = _env_int("HYBRID_ROUTE_LOOKBACK", 60)
    df_route = compute_indicators(raw, lookback=route_lookback, **_scale_kw)
    strategy_name, lookback, horizon = select_strategy(symbol, df_route)
    if strategy_name is None:
        return
    strat = sm.strategies[strategy_name]
    if not strat.active:
        return

    df = compute_indicators(raw, lookback=lookback, **_scale_kw)
    if not volatility_ok(df):
        return

    price = float(df["close"].iloc[-1])
    sm.seq_model.update(symbol, price)
    seq_pred = sm.seq_model.predict(symbol)
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

    rl_action = rl.decide(state)
    if rl_action == "SKIP":
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

    balance = st.current_equity()
    units = position_sizing(symbol, price, stop_mid, balance)
    units *= weight * confidence
    units = cap_position_units(units)

    if units < 1e-6:
        return

    if pre_close_adjustment_at(symbol, now_utc):
        units *= 0.5
        if units < 1.0:
            return

    exec_kind = "simulated"
    use_sim_layers = simulation_layers_enabled(symbol, True)

    entry_price: float
    spread_amt: float
    slip_amt: float
    impact_amt: float

    if use_sim_layers:
        await trading_mod.apply_latency()
        mid_impact, impact_amt = apply_market_impact(units, price, direction)
        entry_price, spread_amt, slip_amt = apply_execution_costs(
            symbol, direction, mid_impact, atr_v, strat_style
        )
    else:
        entry_price = float(price)
        spread_amt = 0.0
        slip_amt = 0.0
        impact_amt = 0.0

    if direction == "BUY":
        stop_loss = entry_price - sl_d
        take_profit = entry_price + tp_d
    else:
        stop_loss = entry_price + sl_d
        take_profit = entry_price - tp_d

    new_risk = abs(float(entry_price) - float(stop_loss)) * float(units)
    if portfolio_risk_cap_exceeded(st.current_equity(), new_risk):
        logger.info(
            "Backtest skip open %s: portfolio cap (open≈%.2f + new≈%.2f)",
            symbol,
            portfolio_risk_amount(),
            new_risk,
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
            open_time=now_utc.timestamp(),
            strategy_name=strategy_name,
            rl_state=state,
            execution_kind=exec_kind,
        )
    )


async def run_regime_backtest(
    regime: RegimePeriod,
    symbol: str,
    granularity: str,
    *,
    initial_equity: float,
    base_seed: int,
    step_bars: int,
    csv_df: pd.DataFrame | None = None,
) -> RegimeBacktestResult | None:
    """Load history for ``regime`` from CSV or OANDA, then run the bot logic bar-by-bar."""
    if csv_df is not None:
        logger.info(
            "Slicing CSV for regime %s %s → %s (granularity=%s ignored for CSV)",
            regime.id,
            regime.start.date(),
            regime.end.date(),
            granularity,
        )
        sys.stdout.flush()
        df = filter_ohlcv_date_range(csv_df, regime.start, regime.end)
    else:
        logger.info(
            "Fetching OANDA candles %s %s → %s (this may take a while)...",
            symbol,
            regime.start.date(),
            regime.end.date(),
        )
        sys.stdout.flush()
        df = fetch_ohlcv_range(
            symbol,
            regime.start,
            regime.end,
            granularity=granularity,
        )
    if df is None or df.empty:
        logger.warning("No data for regime %s (%s)", regime.id, regime.label)
        return None

    warmup = max(_env_int("HYBRID_OHLCV_COUNT", 200), _env_int("HYBRID_ROUTE_LOOKBACK", 60) + 50)
    if len(df) <= warmup:
        logger.warning(
            "Regime %s: only %s bars (need > %s for warmup); skipping.",
            regime.id,
            len(df),
            warmup,
        )
        return RegimeBacktestResult(
            regime_id=regime.id,
            label=regime.label,
            bars=len(df),
            decisions=0,
            trades_closed=0,
            total_pnl=0.0,
            sharpe_trades=0.0,
            max_drawdown=0.0,
            final_equity=initial_equity,
            equity_curve=[initial_equity],
        )

    # --- isolate global state (restore in finally) ---
    import forex_bot.analytics as analytics_mod
    import forex_bot.bot_loop as bot_loop_mod
    import forex_bot.database as dbmod

    old_strategies = sm.strategies
    old_meta = sm.meta
    old_seq = sm.seq_model
    old_positions = dict(posmod.positions)
    old_curve = list(st.state["equity_curve"])
    old_analytics = analytics_mod.analytics
    old_pg = dbmod.log_trade_pg
    old_alert = trading_mod.alert
    old_apply_lat = trading_mod.apply_latency
    old_paper = Config.PAPER_TRADING
    old_portfolio = bot_loop_mod.portfolio

    _all_names = tuple(set(SCALP_STRATEGY_KEYS) | set(SWING_STRATEGY_KEYS))
    sm.strategies = {s: Strategy(s) for s in _all_names}
    sm.meta = MetaLearner()
    sm.seq_model = SeqModel()
    trading_mod.strategies = sm.strategies
    trading_mod.meta = sm.meta

    analytics_mod.analytics = Analytics()
    trading_mod.analytics = analytics_mod.analytics
    dbmod.log_trade_pg = lambda *a, **k: None
    trading_mod.log_trade_pg = dbmod.log_trade_pg
    trading_mod.alert = lambda *a, **k: None

    async def _zero_latency() -> int:
        return 0

    trading_mod.apply_latency = _zero_latency

    posmod.positions.clear()
    st.state["equity_curve"] = [initial_equity]
    Config.PAPER_TRADING = True

    portfolio = PortfolioEngine()
    bot_loop_mod.portfolio = portfolio
    rl = RLAgent()

    decisions = 0
    total_steps = max(0, (len(df) - warmup + step_bars - 1) // step_bars)
    logger.info(
        "Simulating %s: %s bars after warmup, ~%s evaluation steps...",
        regime.id,
        len(df),
        total_steps,
    )
    sys.stdout.flush()

    equity_snapshots: list[float] = [initial_equity]

    use_win = _env_bool("BACKTEST_FAST_WINDOW", True)
    win = max(_env_int("BACKTEST_INDICATOR_WINDOW", 1500), warmup + 500)
    if use_win:
        logger.info(
            "Backtest fast path: trailing indicator window=%s bars (BACKTEST_FAST_WINDOW=false for exact full-bar replay)",
            win,
        )

    try:
        for idx in range(warmup, len(df), step_bars):
            if use_win:
                start = max(0, idx + 1 - win)
                raw = df.iloc[start : idx + 1].copy().reset_index(drop=True)
                scale_n = idx + 1
            else:
                raw = df.iloc[: idx + 1].copy().reset_index(drop=True)
                scale_n = None
            now_utc = _parse_ts(df["time"].iloc[idx])
            bar_seed = base_seed + idx * 10007 + hash(regime.id) % (2**31)
            await _backtest_bar(
                symbol,
                raw,
                now_utc,
                rl=rl,
                portfolio=portfolio,
                bar_seed=bar_seed,
                indicator_scale_n=scale_n,
            )
            decisions += 1
            equity_snapshots.append(st.current_equity())
            if decisions % 80 == 0:
                _evolve_strategies()
            if decisions > 0 and decisions % 500 == 0:
                logger.info(
                    "Progress %s: %s / ~%s steps (equity %.2f)",
                    regime.id,
                    decisions,
                    total_steps,
                    st.current_equity(),
                )
                sys.stdout.flush()

        trades_closed = len(analytics_mod.analytics.trades)
        total_pnl = float(sum(analytics_mod.analytics.trades)) if analytics_mod.analytics.trades else 0.0
        sharpe = _sharpe_from_pnls(analytics_mod.analytics.trades)
        mdd = _max_drawdown(equity_snapshots)

        return RegimeBacktestResult(
            regime_id=regime.id,
            label=regime.label,
            bars=len(df),
            decisions=decisions,
            trades_closed=trades_closed,
            total_pnl=total_pnl,
            sharpe_trades=sharpe,
            max_drawdown=mdd,
            final_equity=st.current_equity(),
            equity_curve=list(equity_snapshots),
        )
    finally:
        sm.strategies = old_strategies
        sm.meta = old_meta
        sm.seq_model = old_seq
        trading_mod.strategies = old_strategies
        trading_mod.meta = old_meta
        posmod.positions.clear()
        posmod.positions.update(old_positions)
        st.state["equity_curve"] = old_curve
        analytics_mod.analytics = old_analytics
        trading_mod.analytics = old_analytics
        dbmod.log_trade_pg = old_pg
        trading_mod.log_trade_pg = old_pg
        trading_mod.alert = old_alert
        trading_mod.apply_latency = old_apply_lat
        Config.PAPER_TRADING = old_paper
        bot_loop_mod.portfolio = old_portfolio


async def run_multi_regime_backtest(
    symbol: str,
    *,
    granularity: str = "M5",
    regime_ids: set[str] | None = None,
    initial_equity: float | None = None,
    seed: int | None = None,
    step_bars: int | None = None,
    csv_path: str | None = None,
) -> list[RegimeBacktestResult]:
    """Run all preset regimes (or filter by ``regime_ids``). Optional ``csv_path`` skips OANDA."""
    eq = initial_equity if initial_equity is not None else float(Config.BASE_BALANCE)
    sd = seed if seed is not None else _env_int("BACKTEST_SEED", 42)
    step = step_bars if step_bars is not None else _env_int("BACKTEST_STEP_BARS", 1)

    csv_df: pd.DataFrame | None = None
    if csv_path:
        csv_df = load_ohlcv_csv(csv_path)

    selected: tuple[RegimePeriod, ...] = REGIME_PERIODS
    if regime_ids:
        selected = tuple(r for r in REGIME_PERIODS if r.id in regime_ids)
        if not selected:
            logger.warning("No matching regime ids in %s; known: %s", regime_ids, [r.id for r in REGIME_PERIODS])

    out: list[RegimeBacktestResult] = []
    n_regimes = len(selected)
    for i, regime in enumerate(selected, start=1):
        logger.info(
            "Backtest regime %s/%s: %s (%s)",
            i,
            n_regimes,
            regime.id,
            regime.label,
        )
        res = await run_regime_backtest(
            regime,
            symbol,
            granularity,
            initial_equity=eq,
            base_seed=sd,
            step_bars=step,
            csv_df=csv_df,
        )
        if res:
            out.append(res)
            eq = res.final_equity
    return out


def _print_report(results: list[RegimeBacktestResult], symbol: str) -> None:
    print(f"\n=== Backtest report: {symbol} ===\n")
    if not results:
        print("No results (no data or API failure).")
        return
    total_pnl = sum(r.total_pnl for r in results)
    print(f"{'Regime':<22} {'Bars':>6} {'Trades':>7} {'PnL':>12} {'Sharpe':>8} {'MaxDD':>10} {'FinalEq':>12}")
    print("-" * 92)
    for r in results:
        print(
            f"{r.regime_id:<22} {r.bars:>6} {r.trades_closed:>7} {r.total_pnl:>12.2f} "
            f"{r.sharpe_trades:>8.3f} {r.max_drawdown:>10.2f} {r.final_equity:>12.2f}"
        )
    print("-" * 92)
    print(f"{'COMBINED (sum PnL)':<22} {'':<6} {'':<7} {total_pnl:>12.2f}")
    print()


def _alert_backtest_summary(results: list[RegimeBacktestResult], symbol: str) -> None:
    """Telegram/Discord via :func:`alert` (same credentials as live bot)."""
    if not results:
        alert(f"BACKTEST COMPLETE | {symbol} — no results (no data or API failure).")
        return
    total_pnl = sum(r.total_pnl for r in results)
    lines = [
        f"BACKTEST COMPLETE | {symbol}",
        f"regimes={len(results)} combined_PnL={total_pnl:.2f}",
        "",
    ]
    for r in results:
        lines.append(
            f"{r.regime_id}: PnL {r.total_pnl:.2f} trades {r.trades_closed} "
            f"Sharpe {r.sharpe_trades:.3f} MaxDD {r.max_drawdown:.2f} final_eq {r.final_equity:.2f}"
        )
    body = "\n".join(lines)
    if len(body) > 3500:
        body = body[:3497] + "..."
    alert(body)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # oandapyV20 logs every REST call at INFO; backtests issue many chunked requests.
    logging.getLogger("oandapyV20").setLevel(logging.WARNING)
    p = argparse.ArgumentParser(
        description="Multi-regime historical backtest (OANDA API or local OHLCV CSV).",
    )
    p.add_argument("--symbol", default="EUR_USD", help="Instrument label for reports (CSV mode: informational)")
    p.add_argument(
        "--granularity",
        default="M5",
        help="OANDA candle granularity when not using --csv (default M5)",
    )
    p.add_argument(
        "--csv",
        metavar="PATH",
        default=None,
        help="OHLCV CSV (time,open,high,low,close); skips OANDA. Overrides BACKTEST_CSV env.",
    )
    p.add_argument(
        "--regimes",
        default="all",
        help="Comma-separated regime ids, or 'all' (see REGIME_PERIODS in backtest.py)",
    )
    p.add_argument("--seed", type=int, default=None, help="Random seed (default BACKTEST_SEED or 42)")
    p.add_argument("--equity", type=float, default=None, help="Starting equity (default Config.BASE_BALANCE)")
    p.add_argument("--step-bars", type=int, default=None, help="Evaluate every N bars (default BACKTEST_STEP_BARS or 1)")
    p.add_argument(
        "--fast",
        action="store_true",
        help="Fewer OANDA requests (5000/bar chunk, no delay), optional coarser steps (step>=5 if --step-bars omitted)",
    )
    args = p.parse_args()

    print(
        "Backtest: starting (imports done; fetching candles + simulation can take many minutes).",
        flush=True,
    )

    regime_ids: set[str] | None = None
    if args.regimes.strip().lower() != "all":
        regime_ids = {x.strip() for x in args.regimes.split(",") if x.strip()}

    seed = args.seed if args.seed is not None else _env_int("BACKTEST_SEED", 42)
    step = args.step_bars if args.step_bars is not None else _env_int("BACKTEST_STEP_BARS", 1)
    csv_path = (args.csv or (os.getenv("BACKTEST_CSV") or "").strip()) or None

    if args.fast and not csv_path:
        os.environ.setdefault("OANDA_CHUNK_DELAY_SEC", "0")
        os.environ.setdefault("OANDA_MAX_CANDLES_PER_REQUEST", "5000")
        if args.step_bars is None:
            step = max(_env_int("BACKTEST_STEP_BARS", 5), 5)
        print(
            f"Backtest --fast: step_bars={step} (set OANDA_MAX_CANDLES_PER_REQUEST / BACKTEST_FAST_WINDOW in .env to tune)",
            flush=True,
        )

    regimes_str = args.regimes.strip()
    exp = experiment_snapshot_with_voters(ai)
    logger.info("Experiment (A/B): %s", exp)
    print(f"Experiment (A/B): {exp}", flush=True)
    src = f"csv={csv_path}" if csv_path else f"OANDA granularity={args.granularity}"
    alert(
        f"BACKTEST STARTED | symbol={args.symbol} {src} "
        f"regimes={regimes_str} seed={seed} step_bars={step} | "
        f"ensemble={exp['ensemble_mode']} local={exp['local_voters']} ext={exp['external_voters']} "
        f"nn_pred={exp['nn_pred_mode']}"
    )

    results = asyncio.run(
        run_multi_regime_backtest(
            args.symbol,
            granularity=args.granularity,
            regime_ids=regime_ids,
            initial_equity=args.equity,
            seed=seed,
            step_bars=step,
            csv_path=csv_path,
        )
    )
    _print_report(results, args.symbol)
    _alert_backtest_summary(results, args.symbol)


if __name__ == "__main__":
    # Imports above can take 10–30s on first run; this line appears only after they finish.
    print("forex_bot.backtest loaded. Starting...", flush=True)
    main()
