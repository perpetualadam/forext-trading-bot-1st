"""Position sizing, spread/slippage simulation, and execution logging."""

from __future__ import annotations

import asyncio
import logging
import math
import os
from typing import Any

from forex_bot.alerts import alert
from forex_bot.execution import ExecutionMode, get_execution_mode, strict_execution
import forex_bot.oanda_exec as oanda_exec
from forex_bot.analytics import analytics
from forex_bot.config import Config
from forex_bot.database import log_trade_pg
from forex_bot.state import current_equity, update_equity
from forex_bot.positions import Position
from forex_bot.strategy_meta import meta, strategies

logger = logging.getLogger(__name__)


def _alert_prefix_for_execution(execution_kind: str, *, oanda_broker: bool = False) -> str:
    if oanda_broker:
        return "OANDA LIVE"
    if execution_kind == "window_paper":
        return "WINDOW-PAPER"
    return (Config.TRADING_MODE or "practice").upper()


def _env_float(name: str, default: float) -> float:
    v = (os.getenv(name) or "").strip()
    return float(v) if v else default


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    return int(v) if v else default


async def apply_latency() -> int:
    """
    Optional execution delay (ms) from ``LATENCY_MS`` (default 50). Set to 0 to disable.
    Broker-agnostic simulation for queue + network latency.
    """
    ms = _env_int("LATENCY_MS", 50)
    if ms <= 0:
        return 0
    await asyncio.sleep(ms / 1000.0)
    return ms


def apply_market_impact(units: float, base_price: float, direction: str) -> tuple[float, float]:
    """
    Simple depth / liquidity model: larger size moves the effective mid against you.

    Returns ``(adjusted_price, impact_magnitude)``. Tunable via ``MARKET_IMPACT_FACTOR``
    (default ``1e-9``: ~0.03 pip on 30k EUR_USD units — previous 5e-7 was unrealistically large).
    """
    impact_factor = _env_float("MARKET_IMPACT_FACTOR", 0.000000001)
    impact = abs(float(units)) * impact_factor
    d = (direction or "").upper().strip()
    if d == "BUY":
        adjusted = float(base_price) + impact
    else:
        adjusted = float(base_price) - impact
    return adjusted, float(impact)


# Typical half-spread–style costs in price space (instrument-dependent; JPY quotes are larger).
SPREADS: dict[str, float] = {
    "EUR_USD": 0.0001,
    "GBP_USD": 0.00015,
    "USD_JPY": 0.01,
}

# Stop / take-profit distances in *price units* (not pips). Must match instrument scale:
# majors 1 pip = 0.0001; JPY pairs 1 pip = 0.01 (OANDA convention).
# Defaults ≈ 20-pip stop, 40-pip TP (2:1 RR) per pair.
SL_PRICE_DISTANCE: dict[str, float] = {
    "EUR_USD": 0.0020,
    "GBP_USD": 0.0020,
    "USD_JPY": 0.20,
}
TP_RISK_REWARD = 2.0


def sl_tp_price_distances(symbol: str) -> tuple[float, float]:
    """Return ``(stop_distance, take_profit_distance)`` in price for ``symbol``."""
    sym = symbol.upper().strip()
    sl = SL_PRICE_DISTANCE.get(sym, 0.0020)
    tp = sl * TP_RISK_REWARD
    return float(sl), float(tp)


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def sl_tp_distance_for_entry(symbol: str, atr: float | None) -> tuple[float, float]:
    """
    Stop and take-profit **distance** in price units for a new entry.

    If ``USE_ATR_STOPS`` is true and ``atr`` is valid, uses ``SL_ATR_MULT * ATR`` (with
    ``MIN_STOP_DISTANCE_PRICE`` as a floor when set). Otherwise uses fixed per-symbol
    distances from :func:`sl_tp_price_distances` (normalizes across symbols only at a coarse level).
    """
    use_atr = _env_bool("USE_ATR_STOPS", False)
    if use_atr and atr is not None and float(atr) > 0 and not math.isnan(float(atr)):
        mult = _env_float("SL_ATR_MULT", 2.0)
        sl_d = float(atr) * mult
        min_sl = _env_float("MIN_STOP_DISTANCE_PRICE", 0.0)
        if min_sl > 0:
            sl_d = max(sl_d, min_sl)
        tp_d = sl_d * TP_RISK_REWARD
        return float(sl_d), float(tp_d)
    return sl_tp_price_distances(symbol)


def _norm_symbol(symbol: str) -> str:
    return (symbol or "").upper().strip().replace("-", "_")


def is_usd_base_pair(symbol: str) -> bool:
    """True for USD_JPY-style pairs (USD is base; P&L in quote needs / mid for USD account)."""
    s = _norm_symbol(symbol)
    return s.startswith("USD_") and len(s) > 4


def quote_pnl_to_account_ccy(symbol: str, quote_pnl: float, mid_price: float) -> float:
    """
    Convert instrument quote-currency P&L to approximate account USD.

    - EUR_USD / GBP_USD: quote is already USD.
    - USD_JPY: quote is JPY → divide by mid (JPY per USD).
    """
    px = abs(float(mid_price))
    if px < 1e-15:
        return 0.0
    if is_usd_base_pair(symbol):
        return float(quote_pnl) / px
    return float(quote_pnl)


def stop_risk_account_ccy(symbol: str, mid_price: float, stop_distance: float, units: float) -> float:
    """Approximate account-currency loss if stop is hit for ``units``."""
    d = abs(float(stop_distance))
    u = abs(float(units))
    if is_usd_base_pair(symbol):
        px = abs(float(mid_price))
        if px < 1e-15:
            return 0.0
        return (d / px) * u
    return d * u


def pnl_account_ccy(
    symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    units: float,
) -> float:
    """Realized / mark-to-market PnL in approximate account USD."""
    u = abs(float(units))
    d = (direction or "").upper().strip()
    if d == "BUY":
        quote_pnl = (float(exit_price) - float(entry_price)) * u
    else:
        quote_pnl = (float(entry_price) - float(exit_price)) * u
    return quote_pnl_to_account_ccy(symbol, quote_pnl, float(exit_price))


def position_risk_dollars(pos: Position) -> float:
    """Approximate account-currency loss if stop is hit (unsigned)."""
    stop_d = abs(float(pos.entry_price) - float(pos.stop_loss))
    return stop_risk_account_ccy(pos.symbol, float(pos.entry_price), stop_d, float(pos.units))


def portfolio_risk_amount() -> float:
    from forex_bot.positions import positions as posmap

    return float(sum(position_risk_dollars(p) for p in posmap.values()))


def portfolio_risk_fraction(equity: float) -> float:
    eq = max(0.0, float(equity))
    if eq < 1e-12:
        return 0.0
    return portfolio_risk_amount() / eq


def configured_max_portfolio_risk_pct() -> float:
    """Configured portfolio stop-risk cap (0 = feature off)."""
    return _env_float("MAX_PORTFOLIO_RISK_PCT", 0.05)


def portfolio_risk_cap_exceeded(equity: float, additional_risk: float) -> bool:
    """
    True if open positions' risk at stops plus ``additional_risk`` exceeds
    ``equity * MAX_PORTFOLIO_RISK_PCT``. Disabled when ``MAX_PORTFOLIO_RISK_PCT`` <= 0.
    """
    cap = configured_max_portfolio_risk_pct()
    if cap <= 0:
        return False
    max_risk = max(0.0, float(equity)) * cap
    if max_risk < 1e-12:
        return True
    return portfolio_risk_amount() + float(additional_risk) > max_risk + 1e-9


def cap_position_units(units: float) -> float:
    """Clamp units when ``MAX_POSITION_UNITS`` > 0."""
    m = _env_float("MAX_POSITION_UNITS", 0.0)
    if m <= 0:
        return float(units)
    return min(float(units), m)


def strategy_execution_style(strategy_name: str) -> str:
    """Rough bucket for spread multipliers: scalp vs swing-style strategies."""
    return "scalp" if "scalp" in strategy_name.lower() else "swing"


def apply_execution_costs(
    symbol: str,
    direction: str,
    price: float,
    volatility: float,
    strategy_type: str,
) -> tuple[float, float, float]:
    """
    Return executable price after spread + volatility-scaled slippage, plus components.

    ``volatility`` is typically ATR in price terms. ``direction`` is the trade side (BUY pays offer, SELL hits bid).
    """
    spread = SPREADS.get(symbol.upper().strip(), 0.0001)
    spread *= _env_float("SPREAD_MULTIPLIER", 1.0)
    if strategy_type == "scalp":
        spread *= 1.2
    else:
        spread *= 0.8

    vol = float(volatility)
    if math.isnan(vol) or vol <= 0:
        vol = 0.0001
    # Deterministic ATR-scaled slippage (no randomness; tune via SLIPPAGE_ATR_FRACTION default 0.3).
    atr_frac = _env_float("SLIPPAGE_ATR_FRACTION", 0.3)
    slippage = vol * atr_frac
    slippage *= _env_float("SLIPPAGE_MULTIPLIER", 1.0)

    d = (direction or "").upper().strip()
    if d == "BUY":
        execution_price = price + spread + slippage
    else:
        execution_price = price - spread - slippage
    return float(execution_price), float(spread), float(slippage)


def position_sizing(
    symbol: str,
    price: float,
    stop_loss_price: float,
    balance: float,
    *,
    risk_pct: float | None = None,
) -> float:
    """
    Risk-based position size: ``units ≈ (equity * risk_pct) / account_risk_per_unit``.

    - **Not** affected by ``TRADING_MODE`` (practice vs live); that only selects OANDA API host.
      Broker margin / max position is **not** modeled here (OANDA may reject oversized orders).
    - ``POSITION_RISK_PCT`` (default 1%%) is **capped** by ``POSITION_RISK_PCT_MAX`` (default 1%%)
      so a mis-set env cannot risk e.g. 5%% per trade without raising the cap explicitly.
    - Sizing uses ``max(balance, 0)`` so negative equity does not flip sign.
    - Optional ``MIN_STOP_DISTANCE_PRICE``: floor the stop distance (price units) so tiny
      structural stops cannot explode ``units`` when volatility or symbol scale changes.
    - For ``USD_*`` pairs, stop distance in quote is converted to USD via ``/ mid``.
    """
    rp = risk_pct if risk_pct is not None else _env_float("POSITION_RISK_PCT", 0.01)
    max_rp = _env_float("POSITION_RISK_PCT_MAX", 0.01)
    rp = min(max(0.0, rp), max_rp)

    balance_eff = max(0.0, float(balance))
    if balance_eff < 1e-12:
        return 0.0

    risk_amount = balance_eff * rp
    stop_distance = abs(float(price) - float(stop_loss_price))
    min_stop = _env_float("MIN_STOP_DISTANCE_PRICE", 0.0)
    if min_stop > 0:
        stop_distance = max(stop_distance, min_stop)
    if stop_distance < 1e-15:
        return 0.0
    risk_per_unit = stop_risk_account_ccy(symbol, float(price), stop_distance, 1.0)
    if risk_per_unit < 1e-15:
        return 0.0
    units = risk_amount / risk_per_unit
    return max(units, 1.0)


def calculate_pnl(position: Position, current_price: float) -> float:
    """Mark-to-market PnL in approximate account USD for an open FX position."""
    return pnl_account_ccy(
        position.symbol,
        position.direction,
        float(position.entry_price),
        float(current_price),
        float(position.units),
    )


def simulate_execution(direction: str, price: float, size: float) -> float:
    """Deterministic paper PnL from spread + slippage only (no random exit noise)."""
    return simulate_execution_deterministic(direction, price, size)


def simulate_execution_deterministic(direction: str, price: float, size: float) -> float:
    """Spread + slippage model; exit at synthetic mid (no randomness)."""
    spread = 0.0001
    slippage = 0.00005
    if direction == "BUY":
        entry = price + spread + slippage
    else:
        entry = price - spread - slippage
    exit_price = entry
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
    execution_kind: str = "simulated",
    exit_price: float | None = None,
    spread_component: float | None = None,
    slippage_component: float | None = None,
) -> float:
    """
    Log and record a trade. ``price`` is entry for a close; ``exit_price`` if given is the modelled exit.

    ``execution_kind``: ``"live"`` (inside ``LIVE_*`` with ``PAPER_TRADING`` false), ``"simulated"``
    (paper mode), or ``"window_paper"`` (live account, outside window). Drives Postgres and alert tags.

    If ``realized_pnl`` is None: **paper** mode uses deterministic simulation; **broker** modes
    require ``realized_pnl`` (raises when missing if ``STRICT_EXECUTION``).

    When ``execution_kind`` is ``live`` and broker orders are enabled, attempts a real OANDA market
    close and uses broker ``pl`` / fill price. On broker close failure, **raises** so callers do not
    drop local state while the broker position may still be open.
    """
    _ = sl, tp
    oanda_broker = False
    exit_px_model = float("nan")
    if realized_pnl is None:
        mode = get_execution_mode()
        if mode == ExecutionMode.PAPER:
            pnl = simulate_execution_deterministic(direction, price, size)
        else:
            msg = (
                "realized_pnl is required when EXECUTION_MODE is paper_broker or live_broker "
                "(legacy: set PAPER_TRADING=true for paper-only simulation)"
            )
            if strict_execution():
                raise ValueError(msg)
            logger.error("%s; using deterministic sim as non-strict fallback", msg)
            pnl = simulate_execution_deterministic(direction, price, size)
    else:
        pnl = float(realized_pnl)
        exit_px_model = float(exit_price) if exit_price is not None else float("nan")
        if (
            execution_kind == "live"
            and oanda_exec.use_oanda_live()
            and exit_price is not None
        ):
            # Live broker close must succeed; do not fall back to model and clear local state.
            pnl, exit_px_model = await oanda_exec.execute_oanda_market_close(
                symbol, size, direction, price
            )
            oanda_broker = True
            alert(
                f"[OANDA LIVE] {symbol} {direction} {size:.2f} units PnL={pnl:.2f}"
            )

    analytics.log_trade(pnl)
    strat = strategies.get(strategy_name)
    if strat is not None:
        strat.update_pnl(pnl)
        meta.update(strategy_name, pnl)
    else:
        logger.warning(
            "execute_trade: unknown strategy %r — skipping strategy/meta PnL update",
            strategy_name,
        )
    update_equity(pnl)
    if exit_price is not None:
        if not math.isnan(exit_px_model):
            exit_px = exit_px_model
        else:
            exit_px = float(exit_price)
    elif size and abs(size) > 1e-12:
        if direction == "BUY":
            exit_px = price + pnl / size
        else:
            exit_px = price - pnl / size
    else:
        exit_px = price + pnl
    log_trade_pg(
        symbol,
        strategy_name,
        direction,
        pnl,
        size,
        price,
        exit_px,
        execution_kind=execution_kind,
    )
    tag = _alert_prefix_for_execution(execution_kind, oanda_broker=oanda_broker)
    if exit_price is not None:
        extra = ""
        if spread_component is not None and slippage_component is not None:
            extra = f" spread={spread_component:.5f} slippage={slippage_component:.5f}"
        alert(
            f"[CLOSE] [{tag}] {direction} {symbol} size {size} PnL {pnl:.2f}{extra} "
            f"entry={price:.5f} exit={exit_px:.5f}"
        )
    else:
        alert(f"[{tag}] {direction} {symbol} size {size} PnL {pnl:.2f}")
    return pnl
