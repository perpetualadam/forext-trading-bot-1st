"""Deterministic simulated fills, costs, and GBP conversion. No broker I/O."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from forex_bot.shadow.config import ShadowConfig
from forex_bot.shadow.cost_model import adverse_offset, conservative_half_spread
from forex_bot.shadow.reasons import SCALP_FAMILY
from forex_bot.symbols import normalize_oanda_symbol, quote_currency


def pip_size(symbol: str) -> float:
    return 0.01 if quote_currency(symbol) == "JPY" else 0.0001


def half_spread(symbol: str, cfg: ShadowConfig) -> float:
    _ = cfg
    return conservative_half_spread(symbol)


def usd_direction(symbol: str, side: str) -> str | None:
    s = normalize_oanda_symbol(symbol)
    d = (side or "").upper().strip()
    if d not in ("BUY", "SELL") or "_" not in s:
        return None
    base, quote = s.split("_", 1)
    if quote == "USD" and base != "USD":
        return "SHORT" if d == "BUY" else "LONG"
    if base == "USD" and quote != "USD":
        return "LONG" if d == "BUY" else "SHORT"
    return None


def quote_pnl_to_usd(symbol: str, quote_pnl: float, mid: float) -> float:
    s = normalize_oanda_symbol(symbol)
    px = abs(float(mid))
    if px < 1e-15:
        return 0.0
    base, quote = s.split("_", 1)
    if quote == "USD":
        return float(quote_pnl)
    if base == "USD":
        return float(quote_pnl) / px
    return float(quote_pnl)


def usd_to_gbp(usd: float, gbp_usd_mid: float | None, cfg: ShadowConfig) -> float:
    fx = float(gbp_usd_mid) if gbp_usd_mid and gbp_usd_mid > 0 else cfg.gbp_usd_fallback
    if fx < 1e-12:
        return 0.0
    return float(usd) / fx


def executable_price(
    symbol: str,
    direction: str,
    mid: float,
    atr: float,
    strategy: str,
    cfg: ShadowConfig,
    *,
    bid: float | None = None,
    ask: float | None = None,
) -> tuple[float, float, float]:
    """Adverse spread + slippage. Estimate unless bid/ask are supplied. Not a broker fill."""
    spread, slip, _src = adverse_offset(
        symbol,
        bid=bid,
        ask=ask,
        atr=float(atr) if atr > 0 and not math.isnan(atr) else 0.0,
        slippage_atr_fraction=cfg.slippage_atr_fraction,
    )
    if bid is None or ask is None:
        fam = cfg.scalp_spread_mult if strategy in SCALP_FAMILY else cfg.swing_spread_mult
        spread *= fam
    if slip <= 0:
        vol = float(atr) if atr > 0 and not math.isnan(atr) else 0.0001
        slip = vol * cfg.slippage_atr_fraction
    d = (direction or "").upper()
    px = float(mid) + spread + slip if d == "BUY" else float(mid) - spread - slip
    return float(px), float(spread), float(slip)


def stop_risk_gbp(
    symbol: str,
    mid: float,
    stop_distance: float,
    units: float,
    gbp_usd_mid: float | None,
    cfg: ShadowConfig,
) -> float:
    d = abs(float(stop_distance))
    u = abs(float(units))
    s = normalize_oanda_symbol(symbol)
    base, quote = s.split("_", 1)
    if quote == "USD":
        usd = d * u
    elif base == "USD":
        px = abs(float(mid))
        usd = (d / px) * u if px > 1e-15 else 0.0
    else:
        usd = d * u
    return usd_to_gbp(usd, gbp_usd_mid, cfg)


def units_for_notional(
    symbol: str,
    mid: float,
    nav_gbp: float,
    cfg: ShadowConfig,
    gbp_usd_mid: float | None = None,
) -> float:
    """Whole OANDA units targeting ``notional_pct_of_nav`` of NAV in GBP face value."""
    target_gbp = max(0.0, float(nav_gbp)) * cfg.notional_pct_of_nav
    s = normalize_oanda_symbol(symbol)
    px = abs(float(mid))
    if target_gbp <= 0 or px <= 0:
        return 0.0
    base, quote = s.split("_", 1)
    fx = float(gbp_usd_mid) if gbp_usd_mid and gbp_usd_mid > 0 else cfg.gbp_usd_fallback
    usd = target_gbp * fx
    if quote == "USD":
        units = usd / px
    elif base == "USD":
        units = usd
    else:
        units = target_gbp
    return float(int(units))


def conservative_intrabar_exit(
    direction: str,
    sl: float,
    tp: float,
    bar_open: float,
    bar_high: float,
    bar_low: float,
) -> tuple[str | None, float | None]:
    """If SL and TP both trade in the bar, assume SL (worse). Gaps through SL fill at open."""
    d = (direction or "").upper()
    if d == "BUY":
        gap_sl = bar_open <= sl
        hit_sl = bar_low <= sl
        hit_tp = bar_high >= tp
        if gap_sl:
            return "stop_loss", float(bar_open)
        if hit_sl and hit_tp:
            return "stop_loss", float(sl)
        if hit_sl:
            return "stop_loss", float(sl)
        if hit_tp:
            return "take_profit", float(tp)
        return None, None
    gap_sl = bar_open >= sl
    hit_sl = bar_high >= sl
    hit_tp = bar_low <= tp
    if gap_sl:
        return "stop_loss", float(bar_open)
    if hit_sl and hit_tp:
        return "stop_loss", float(sl)
    if hit_sl:
        return "stop_loss", float(sl)
    if hit_tp:
        return "take_profit", float(tp)
    return None, None


def mae_mfe_pips(
    symbol: str,
    direction: str,
    entry: float,
    bar_high: float,
    bar_low: float,
    mae: float,
    mfe: float,
) -> tuple[float, float]:
    pip = pip_size(symbol)
    if pip <= 0:
        return mae, mfe
    d = (direction or "").upper()
    if d == "BUY":
        adverse = (entry - bar_low) / pip
        fav = (bar_high - entry) / pip
    else:
        adverse = (bar_high - entry) / pip
        fav = (entry - bar_low) / pip
    return max(mae, adverse), max(mfe, fav)


@dataclass
class ShadowPosition:
    symbol: str
    strategy: str
    direction: str
    units: float
    entry_time: datetime
    entry_mid: float
    entry_price: float
    spread: float
    slippage: float
    stop_loss: float
    take_profit: float
    signal_bar_time: datetime
    fill_bar_time: datetime
    mae_pips: float = 0.0
    mfe_pips: float = 0.0
    label: str = "SIMULATED_SHADOW_NOT_BROKER"

    def key(self) -> tuple[str, str]:
        return (self.symbol, self.strategy)


@dataclass
class ShadowFill:
    kind: str
    reason: str
    symbol: str
    strategy: str
    direction: str
    timestamp: datetime
    mid: float
    price: float
    units: float
    spread: float
    slippage: float
    stop_loss: float | None
    take_profit: float | None
    gross_gbp: float
    costs_gbp: float
    net_gbp: float
    mae_pips: float | None = None
    mfe_pips: float | None = None
    exit_reason: str | None = None
    simulated: bool = True
    extra: dict[str, float] = field(default_factory=dict)


def utc_iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()
