"""Live broker entry SL/TP: preserve ATR/2R distances, re-anchor to executable prices.

Paper / window_paper / simulated / backtest do not use this module for fills.
Existing-position management stays in ``live_manage`` (closeoutBid / closeoutAsk).
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from forex_bot.live_manage import ManageQuote, quote_age_sec
from forex_bot.profit_protection import pip_size
from forex_bot.trading import TP_RISK_REWARD

logger = logging.getLogger(__name__)

# Historical last-change threshold. NOT a fetch-freshness gate and NOT used to
# reject a successfully fetched ClientPrice. Official OANDA ClientPrice.time is
# when that Price was created / last changed, not HTTP GET age.
ENTRY_QUOTE_STALE_SEC = 5.0
PRICE_SOURCE_OANDA_PRICING = "OANDA_PRICING"
PRICE_SOURCE_M5_MID = "M5_MID"
# Evidence-approved exact validity only. Skip when clearance <= this value.
# Do not add a positive pip/spread/ATR buffer.
REQUIRED_SL_TRIGGER_CLEARANCE = 0.0
SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE = "insufficient_sl_trigger_clearance"


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
    price_last_change_age_ms: float | None
    bid: float | None
    ask: float | None
    atr: float | None = None
    request_duration_ms: float | None = None
    price_time: str | None = None
    fetch_age_ms: float | None = None
    trigger_side: str | None = None
    trigger_price: float | None = None
    trigger_clearance: float | None = None
    trigger_clearance_pips: float | None = None
    required_clearance_pips: float = REQUIRED_SL_TRIGGER_CLEARANCE


@dataclass(frozen=True)
class EntryPricingFetch:
    """Result of a dedicated PricingInfo GET immediately before OrderCreate."""

    quote: ManageQuote | None
    skip_reason: str | None
    request_started_mono: float
    response_received_mono: float
    request_duration_ms: float

    def fetch_age_ms(self, now_mono: float | None = None) -> float:
        now = time.perf_counter() if now_mono is None else float(now_mono)
        return max(0.0, (now - float(self.response_received_mono)) * 1000.0)


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


def classify_book_price(raw: object, missing_reason: str) -> tuple[float | None, str | None]:
    """Finite positive price, or fail-closed reason. No spread reconstruction."""
    if raw is None:
        return None, missing_reason
    try:
        px = float(raw)
    except (TypeError, ValueError):
        return None, "malformed_price"
    if not math.isfinite(px) or px <= 0:
        return None, "malformed_price"
    return px, None


def sl_trigger_side(direction: str) -> str | None:
    """OANDA DEFAULT SL trigger: long SL vs bid, short SL vs ask."""
    d = (direction or "").upper().strip()
    if d == "BUY":
        return "bid"
    if d == "SELL":
        return "ask"
    return None


def sl_trigger_price(direction: str, bid: float, ask: float) -> float | None:
    side = sl_trigger_side(direction)
    if side == "bid":
        return float(bid)
    if side == "ask":
        return float(ask)
    return None


def sl_trigger_clearance(direction: str, sl: float, bid: float, ask: float) -> float | None:
    """Positive means the rounded SL is strictly inside the trigger side."""
    d = (direction or "").upper().strip()
    if d == "BUY":
        return float(bid) - float(sl)
    if d == "SELL":
        return float(sl) - float(ask)
    return None


def has_sl_trigger_clearance(clearance: float | None) -> bool:
    if clearance is None:
        return False
    try:
        cl = float(clearance)
    except (TypeError, ValueError):
        return False
    return math.isfinite(cl) and cl > REQUIRED_SL_TRIGGER_CLEARANCE


def sl_trigger_clearance_skip_reason(
    direction: str, sl: float, bid: float, ask: float
) -> str | None:
    cl = sl_trigger_clearance(direction, sl, bid, ask)
    if cl is None or not math.isfinite(cl):
        return "malformed_price"
    if not has_sl_trigger_clearance(cl):
        return SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE
    return None


def classify_executable_reference(
    quote: ManageQuote | None, direction: str
) -> tuple[float | None, str | None]:
    """Return (executable price, skip reason). BUY=ask, SELL=bid. No M5 fallback."""
    if quote is None:
        return None, "instrument_missing"
    d = (direction or "").upper().strip()
    if d == "BUY":
        return classify_book_price(quote.ask, "executable_ask_missing")
    if d == "SELL":
        return classify_book_price(quote.bid, "executable_bid_missing")
    return None, "invalid_geometry"


def executable_entry_reference(quote: ManageQuote | None, direction: str) -> float | None:
    """BUY market pays the ask; SELL market hits the bid. Not closeout prices."""
    px, _reason = classify_executable_reference(quote, direction)
    return px


def format_client_price_time(time_epoch: float | None) -> str | None:
    if time_epoch is None:
        return None
    try:
        return datetime.fromtimestamp(float(time_epoch), tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _is_timeout_error(exc: BaseException) -> bool:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        name = type(cur).__name__.lower()
        if isinstance(cur, TimeoutError) or "timeout" in name:
            return True
        text = str(cur).lower()
        if "timed out" in text or "timeout" in text:
            return True
        cur = cur.__cause__ or getattr(cur, "__context__", None)
    return False


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


def _quote_usable_for_entry(quote: ManageQuote | None) -> str | None:
    """Return a skip reason, or None if the freshly fetched quote may be used.

    ClientPrice.time / last-change age is not a reject. Fetch success is
    established by ``fetch_entry_pricing`` immediately before this check.
    """
    if quote is None:
        return "instrument_missing"
    if not quote.tradeable:
        return "not_tradeable"
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
    request_duration_ms: float | None = None,
    fetch_age_ms: float | None = None,
) -> tuple[LiveEntryGeometry | None, str | None]:
    """Build rounded broker SL/TP around a freshly fetched executable price. Fail closed on None.

    ``max_age_sec`` is unused: ClientPrice.time is last-change, not fetch age.
    """
    del max_age_sec  # last-change age must not reject a valid freshly fetched quote
    skip = _quote_usable_for_entry(quote)
    if skip:
        return None, skip
    ref, ref_skip = classify_executable_reference(quote, direction)
    if ref is None:
        return None, ref_skip or "malformed_price"
    d = (direction or "").upper().strip()
    bid_px, bid_skip = classify_book_price(getattr(quote, "bid", None), "executable_bid_missing")
    ask_px, ask_skip = classify_book_price(getattr(quote, "ask", None), "executable_ask_missing")
    if bid_px is None:
        return None, bid_skip or "executable_bid_missing"
    if ask_px is None:
        return None, ask_skip or "executable_ask_missing"
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
    spread = float(ask_px) - float(bid_px)
    last_change_age = quote_age_sec(quote, now)
    risk = abs(ref_r - sl)
    reward = abs(tp - ref_r)
    trig_side = sl_trigger_side(d)
    trig_px = sl_trigger_price(d, bid_px, ask_px)
    clearance = sl_trigger_clearance(d, sl, bid_px, ask_px)
    trig_skip = sl_trigger_clearance_skip_reason(d, sl, bid_px, ask_px)
    geom = LiveEntryGeometry(
        symbol=symbol,
        side=d,
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
        spread_pips=(spread / pip) if pip else None,
        price_last_change_age_ms=(
            None if last_change_age is None else last_change_age * 1000.0
        ),
        bid=float(bid_px),
        ask=float(ask_px),
        atr=float(atr) if atr is not None and math.isfinite(float(atr)) else None,
        request_duration_ms=request_duration_ms,
        price_time=format_client_price_time(getattr(quote, "time_epoch", None)),
        fetch_age_ms=fetch_age_ms,
        trigger_side=trig_side,
        trigger_price=trig_px,
        trigger_clearance=clearance,
        trigger_clearance_pips=(clearance / pip) if clearance is not None and pip else None,
        required_clearance_pips=REQUIRED_SL_TRIGGER_CLEARANCE,
    )
    if trig_skip:
        return geom, trig_skip
    return geom, None


def fetch_entry_pricing(symbol: str) -> EntryPricingFetch:
    """Dedicated PricingInfo GET for one instrument immediately before OrderCreate.

    Never writes. No cache. No M5 fallback. HTTP timeout/failure is fail-closed.
    There is no extra request-duration reject: the existing OANDA connect/read
    timeout already bounds a hung GET.
    """
    from forex_bot.oanda_client import fetch_pricing_snapshot, oanda_instrument

    started = time.perf_counter()
    try:
        snap = fetch_pricing_snapshot([symbol], raise_on_error=True)
    except Exception as exc:
        ended = time.perf_counter()
        reason = "pricing_timeout" if _is_timeout_error(exc) else "pricing_request_failed"
        logger.exception("entry PricingInfo %s for %s", reason, symbol)
        return EntryPricingFetch(
            quote=None,
            skip_reason=reason,
            request_started_mono=started,
            response_received_mono=ended,
            request_duration_ms=(ended - started) * 1000.0,
        )
    ended = time.perf_counter()
    duration_ms = (ended - started) * 1000.0
    inst = oanda_instrument(symbol)
    quote = None
    if snap:
        quote = snap.get(inst) or snap.get(symbol)
    if quote is None:
        return EntryPricingFetch(
            quote=None,
            skip_reason="instrument_missing",
            request_started_mono=started,
            response_received_mono=ended,
            request_duration_ms=duration_ms,
        )
    return EntryPricingFetch(
        quote=quote,
        skip_reason=None,
        request_started_mono=started,
        response_received_mono=ended,
        request_duration_ms=duration_ms,
    )


def fetch_fresh_entry_quote(symbol: str) -> ManageQuote | None:
    """Dedicated PricingInfo GET. Returns None on any fail-closed fetch outcome."""
    return fetch_entry_pricing(symbol).quote


def format_entry_geometry_line(geom: LiveEntryGeometry) -> str:
    atr = "n/a" if geom.atr is None else f"{geom.atr:.6f}"
    spr = "n/a" if geom.spread_pips is None else f"{geom.spread_pips:.2f}"
    last = (
        "n/a"
        if geom.price_last_change_age_ms is None
        else f"{geom.price_last_change_age_ms:.0f}"
    )
    req = "n/a" if geom.request_duration_ms is None else f"{geom.request_duration_ms:.0f}"
    pt = geom.price_time or "n/a"
    bid_s = "n/a" if geom.bid is None else f"{geom.bid:.5f}"
    ask_s = "n/a" if geom.ask is None else f"{geom.ask:.5f}"
    return (
        f"[ENTRY GEOMETRY] symbol={geom.symbol} side={geom.side} "
        f"signal_mid={geom.signal_mid:.5f} executable_reference={geom.executable_reference:.5f} "
        f"price_source={geom.price_source} bid={bid_s} ask={ask_s} "
        f"spread_pips={spr} request_duration_ms={req} price_time={pt} "
        f"price_last_change_age_ms={last} "
        f"risk_distance_pips={geom.risk_pips:.2f} sl={geom.sl_text} tp={geom.tp_text} "
        f"expected_r={geom.expected_r:.4f} atr={atr}"
    )


def format_sl_trigger_clearance_skip(geom: LiveEntryGeometry) -> str:
    spr = "n/a" if geom.spread is None else f"{geom.spread:.6f}"
    spr_p = "n/a" if geom.spread_pips is None else f"{geom.spread_pips:.2f}"
    cl_p = "n/a" if geom.trigger_clearance_pips is None else f"{geom.trigger_clearance_pips:.4f}"
    trig_px = "n/a" if geom.trigger_price is None else f"{geom.trigger_price:.5f}"
    last = (
        "n/a"
        if geom.price_last_change_age_ms is None
        else f"{geom.price_last_change_age_ms:.0f}"
    )
    bid_s = "n/a" if geom.bid is None else f"{geom.bid:.5f}"
    ask_s = "n/a" if geom.ask is None else f"{geom.ask:.5f}"
    return (
        f"[ENTRY GEOMETRY SKIP] symbol={geom.symbol} side={geom.side} "
        f"reason={SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE} "
        f"bid={bid_s} ask={ask_s} spread={spr} "
        f"executable_reference={geom.executable_reference:.5f} "
        f"trigger_side={geom.trigger_side or 'n/a'} trigger_price={trig_px} "
        f"sl={geom.sl_text} tp={geom.tp_text} "
        f"risk_distance_pips={geom.risk_pips:.2f} spread_pips={spr_p} "
        f"trigger_clearance_pips={cl_p} "
        f"required_clearance_pips={geom.required_clearance_pips:.1f} "
        f"intended_r={geom.expected_r:.4f} "
        f"price_time={geom.price_time or 'n/a'} "
        f"price_last_change_age_ms={last} "
        f"fail_closed=true"
    )


def format_entry_geometry_skip(
    symbol: str,
    direction: str,
    reason: str,
    geom: LiveEntryGeometry | None = None,
) -> str:
    if reason == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE and geom is not None:
        return format_sl_trigger_clearance_skip(geom)
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

