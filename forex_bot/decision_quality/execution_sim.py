"""Conservative OHLC path simulation. Never places broker orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from forex_bot.profit_protection import pip_size, unrealized_profit_pips
from forex_bot.trading import simulated_half_spread

# If SL and TP are both inside the same bar and tick order is unknown, do not award TP.
AMBIGUITY_POLICY = "count_ambiguous_and_assume_stop"


@dataclass
class BarTouch:
    hit_sl: bool
    hit_tp: bool
    ambiguous: bool
    exit_reason: str
    exit_price: float | None


def apply_entry_spread(symbol: str, side: str, mid: float) -> tuple[float, float]:
    """BUY pays offer, SELL hits bid using production half-spread. Mid-only data → documented ambiguity."""
    half = float(simulated_half_spread(symbol))
    d = (side or "").upper().strip()
    if d == "BUY":
        return float(mid) + half, half
    return float(mid) - half, half


def bar_touches(
    side: str,
    stop_loss: float,
    take_profit: float,
    high: float,
    low: float,
    *,
    close: float | None = None,
) -> BarTouch:
    d = (side or "").upper().strip()
    hi, lo = float(high), float(low)
    sl, tp = float(stop_loss), float(take_profit)
    if d == "BUY":
        hit_sl = lo <= sl
        hit_tp = hi >= tp
    else:
        hit_sl = hi >= sl
        hit_tp = lo <= tp
    if hit_sl and hit_tp:
        return BarTouch(True, True, True, "ambiguous_sl_tp", sl)
    if hit_sl:
        return BarTouch(True, False, False, "sl", sl)
    if hit_tp:
        return BarTouch(False, True, False, "tp", tp)
    return BarTouch(False, False, False, "", None)


def signed_pips(symbol: str, side: str, entry: float, price: float) -> float:
    return float(unrealized_profit_pips(symbol, side, entry, price))


def excursion_pips(symbol: str, side: str, entry: float, high: float, low: float) -> tuple[float, float]:
    """Return (favorable_pips, adverse_pips) from one bar's range."""
    d = (side or "").upper().strip()
    if d == "BUY":
        fav = signed_pips(symbol, d, entry, high)
        adv = -signed_pips(symbol, d, entry, low)
    else:
        fav = signed_pips(symbol, d, entry, low)
        adv = -signed_pips(symbol, d, entry, high)
    return max(0.0, fav), max(0.0, adv)


def r_multiple(pips: float, sl_pips: float) -> float | None:
    if sl_pips is None or sl_pips <= 0:
        return None
    return float(pips) / float(sl_pips)


def sl_pips(symbol: str, entry: float, stop_loss: float) -> float:
    pip = pip_size(symbol)
    if pip <= 0:
        return 0.0
    return abs(float(entry) - float(stop_loss)) / pip


def parse_bar_time(val) -> datetime:
    ts = pd.Timestamp(val)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()
