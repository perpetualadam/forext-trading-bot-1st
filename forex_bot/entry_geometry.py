"""Live broker entry SL/TP: preserve ATR/2R distances, re-anchor to executable prices.

Paper / window_paper / simulated / backtest do not use this module for fills.
Existing-position management stays in ``live_manage`` (closeoutBid / closeoutAsk).
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from forex_bot.live_manage import ManageQuote, quote_age_sec
from forex_bot.profit_protection import pip_size
from forex_bot.trading import TP_RISK_REWARD

logger = logging.getLogger(__name__)

# Fresh GET immediately before OrderCreate. Cycle-start snapshots are too old.
ENTRY_QUOTE_STALE_SEC = 5.0
PRICE_SOURCE_OANDA_PRICING = "OANDA_PRICING"
PRICE_SOURCE_M5_MID = "M5_MID"


@dataclass(frozen=True)
class LiveEntryGeometry:
    symbol: str
    side: str
    signal_mid: float
    executable_reference: float
    price_source: str
    sl: float
    tp: float
    sl_text: str
    tp_text: str
    risk_distance: float
    reward_distance: float
    expected_r: float
    risk_pips: float
    reward_pips: float
    spread: float | None
    spread_pips: float | None
    quote_age_ms: float | None
    bid: float | None
    ask: float | None
    atr: float | None = None


def live_broker_geometry_required(fill_path: str) -> bool:
    """True only when a real OANDA OrderCreate will be sent (live_broker / paper_broker)."""
    return (fill_path or "").strip().lower() == "broker"


def format_broker_price(symbol: str, price: float) -> str:
    """Same precision as ``oanda_exec._format_oanda_price``: JPY 3dp, else 5dp."""
    s = (symbol or "").upper().replace("-", "_")
    if "JPY" in s:
        return f"{float(price):.3f}"
    return f"{float(price):.5f}"


def apply_broker_price_precision(symbol: str, price: float) -> float:
    return float(format_broker_price(symbol, price))


def executable_entry_reference(quote: ManageQuote | None, direction: str) -> float | None:
    """BUY market pays the ask; SELL market hits the bid. Not closeout prices."""
    if quote is None:
        return None
    d = (direction or "").upper().strip()
    raw = quote.ask if d == "BUY" else quote.bid
    try:
        px = float(raw) if raw is not None else float("nan")
    except (TypeError, ValueError):
        return None
    if not math.isfinite(px) or px <= 0:
        return None
    return px


def construct_absolute_sl_tp(
    entry_reference: float,
    direction: str,
    sl_distance: float,
    tp_distance: float,
) -> tuple[float, float]:
    """Anchor intended distances to ``entry_reference``. Does not change ATR or R methodology."""
    ref = float(entry_reference)
    sl_d = float(sl_distance)
    tp_d = float(tp_distance)
    if (direction or "").upper().strip() == "BUY":
        return ref - sl_d, ref + tp_d
    return ref + sl_d, ref - tp_d


def m5_anchored_sl_tp(
    signal_mid: float,
    direction: str,
    sl_distance: float,
    tp_distance: float,
) -> tuple[float, float]:
    """Legacy (defective) live attach: absolute SL/TP around M5 mid."""
    return construct_absolute_sl_tp(signal_mid, direction, sl_distance, tp_distance)


def orientation_valid(direction: str, sl: float, reference: float, tp: float) -> bool:
    d = (direction or "").upper().strip()
    if d == "BUY":
        return sl < reference < tp
    if d == "SELL":
        return tp < reference < sl
    return False


def geometry_r(direction: str, reference: float, sl: float, tp: float) -> float | None:
    d = (direction or "").upper().strip()
    if d == "BUY":
        risk = reference - sl
        reward = tp - reference
    elif d == "SELL":
        risk = sl - reference
        reward = reference - tp
    else:
        return None
    if risk <= 0 or not math.isfinite(risk) or not math.isfinite(reward):
        return None
    return reward / risk


def fill_based_geometry(
    symbol: str,
    direction: str,
    fill: float,
    sl: float,
    tp: float,
) -> tuple[float | None, float | None, float | None]:
    """Return (risk_pips, reward_pips, actual_r) from fill to attached levels."""
    pip = pip_size(symbol)
    d = (direction or "").upper().strip()
    if d == "BUY":
        risk = float(fill) - float(sl)
        reward = float(tp) - float(fill)
    elif d == "SELL":
        risk = float(sl) - float(fill)
        reward = float(fill) - float(tp)
    else:
        return None, None, None
    risk_pips = risk / pip if pip else None
    reward_pips = reward / pip if pip else None
    actual_r = (reward / risk) if risk > 0 else None
    return risk_pips, reward_pips, actual_r


def _quote_usable(
    quote: ManageQuote | None,
    *,
    now: float | None,
    max_age_sec: float,
) -> str | None:
    """Return a skip reason, or None if the quote may be used."""
    if quote is None:
        return "missing_quote"
    if not quote.tradeable:
        return "not_tradeable"
    if quote.time_epoch is None:
        return "missing_quote_time"
    age = quote_age_sec(quote, now)
    if age is None:
        return "missing_quote_time"
    if age < -2.0:
        return "quote_clock_skew"
    if age > float(max_age_sec):
        return "stale_quote"
    return None


def resolve_live_entry_geometry(
    symbol: str,
    direction: str,
    sl_distance: float,
    tp_distance: float,
    signal_mid: float,
    *,
    quote: ManageQuote | None,
    now: float | None = None,
    max_age_sec: float = ENTRY_QUOTE_STALE_SEC,
    atr: float | None = None,
) -> tuple[LiveEntryGeometry | None, str | None]:
    """Build rounded broker SL/TP around a fresh executable price. Fail closed on None."""
    skip = _quote_usable(quote, now=now, max_age_sec=max_age_sec)
    if skip:
        return None, skip
    ref = executable_entry_reference(quote, direction)
    if ref is None:
        return None, "missing_executable_price"
    if not math.isfinite(float(sl_distance)) or float(sl_distance) <= 0:
        return None, "invalid_risk_distance"
    if not math.isfinite(float(tp_distance)) or float(tp_distance) <= 0:
        return None, "invalid_reward_distance"
    raw_sl, raw_tp = construct_absolute_sl_tp(ref, direction, sl_distance, tp_distance)
    sl = apply_broker_price_precision(symbol, raw_sl)
    tp = apply_broker_price_precision(symbol, raw_tp)
    ref_r = apply_broker_price_precision(symbol, ref)
    if not orientation_valid(direction, sl, ref_r, tp):
        return None, "invalid_orientation_after_rounding"
    expected = geometry_r(direction, ref_r, sl, tp)
    if expected is None or expected <= 0:
        return None, "invalid_expected_r"
    pip = pip_size(symbol)
    bid = getattr(quote, "bid", None)
    ask = getattr(quote, "ask", None)
    spread = None
    if bid is not None and ask is not None:
        try:
            spread = float(ask) - float(bid)
        except (TypeError, ValueError):
            spread = None
    age = quote_age_sec(quote, now)
    risk = abs(ref_r - sl)
    reward = abs(tp - ref_r)
    return (
        LiveEntryGeometry(
            symbol=symbol,
            side=(direction or "").upper().strip(),
            signal_mid=float(signal_mid),
            executable_reference=ref_r,
            price_source=PRICE_SOURCE_OANDA_PRICING,
            sl=sl,
            tp=tp,
            sl_text=format_broker_price(symbol, sl),
            tp_text=format_broker_price(symbol, tp),
            risk_distance=risk,
            reward_distance=reward,
            expected_r=float(expected),
            risk_pips=(risk / pip) if pip else float("nan"),
            reward_pips=(reward / pip) if pip else float("nan"),
            spread=spread,
            spread_pips=(spread / pip) if spread is not None and pip else None,
            quote_age_ms=None if age is None else age * 1000.0,
            bid=float(bid) if bid is not None else None,
            ask=float(ask) if ask is not None else None,
            atr=float(atr) if atr is not None and math.isfinite(float(atr)) else None,
        ),
        None,
    )


def fetch_fresh_entry_quote(symbol: str) -> ManageQuote | None:
    """Dedicated PricingInfo GET for one instrument. Never writes. No M5 fallback."""
    from forex_bot.oanda_client import fetch_pricing_snapshot, oanda_instrument

    try:
        snap = fetch_pricing_snapshot([symbol])
    except Exception:
        logger.exception("entry PricingInfo failed for %s", symbol)
        return None
    if not snap:
        return None
    inst = oanda_instrument(symbol)
    return snap.get(inst) or snap.get(symbol)


def format_entry_geometry_line(geom: LiveEntryGeometry) -> str:
    atr = "n/a" if geom.atr is None else f"{geom.atr:.6f}"
    spr = "n/a" if geom.spread_pips is None else f"{geom.spread_pips:.2f}"
    age = "n/a" if geom.quote_age_ms is None else f"{geom.quote_age_ms:.0f}"
    return (
        f"[ENTRY GEOMETRY] symbol={geom.symbol} side={geom.side} "
        f"signal_mid={geom.signal_mid:.5f} executable_reference={geom.executable_reference:.5f} "
        f"price_source={geom.price_source} atr={atr} "
        f"risk_distance_pips={geom.risk_pips:.2f} sl={geom.sl_text} tp={geom.tp_text} "
        f"expected_r={geom.expected_r:.4f} spread_pips={spr} quote_age_ms={age}"
    )


def format_entry_geometry_skip(symbol: str, direction: str, reason: str) -> str:
    return (
        f"[ENTRY GEOMETRY SKIP] symbol={symbol} side={direction} reason={reason} "
        f"fail_closed=true (no broker OrderCreate; no M5 fallback)"
    )


def format_entry_fill_geometry_line(
    *,
    symbol: str,
    side: str,
    reference: float,
    fill: float,
    sl: float,
    tp: float,
    broker_id: str,
    transaction_id: str,
) -> str:
    pip = pip_size(symbol)
    fill_delta = (float(fill) - float(reference)) if (side or "").upper() == "BUY" else (
        float(reference) - float(fill)
    )
    fill_delta_pips = fill_delta / pip if pip else float("nan")
    risk_pips, reward_pips, actual_r = fill_based_geometry(symbol, side, fill, sl, tp)
    r_s = "n/a" if actual_r is None else f"{actual_r:.4f}"
    rk = "n/a" if risk_pips is None else f"{risk_pips:.2f}"
    rw = "n/a" if reward_pips is None else f"{reward_pips:.2f}"
    return (
        f"[ENTRY FILL GEOMETRY] symbol={symbol} side={side} "
        f"reference={float(reference):.5f} fill={float(fill):.5f} "
        f"fill_delta_pips={fill_delta_pips:.2f} sl={format_broker_price(symbol, sl)} "
        f"tp={format_broker_price(symbol, tp)} actual_risk_pips={rk} "
        f"actual_reward_pips={rw} actual_r={r_s} broker_id={broker_id} "
        f"transaction_id={transaction_id}"
    )


def intended_tp_distance(sl_distance: float) -> float:
    """Production TP distance: ``TP_RISK_REWARD`` × risk distance. Not a new multiplier."""
    return float(sl_distance) * float(TP_RISK_REWARD)


def now_epoch() -> float:
    return time.time()


def quote_from_parts(
    *,
    instrument: str,
    bid: float | None,
    ask: float | None,
    time_epoch: float | None,
    tradeable: bool = True,
    closeout_bid: float | None = None,
    closeout_ask: float | None = None,
) -> ManageQuote:
    return ManageQuote(
        instrument=instrument,
        bid=bid,
        ask=ask,
        closeout_bid=closeout_bid,
        closeout_ask=closeout_ask,
        time_epoch=time_epoch,
        tradeable=tradeable,
    )

