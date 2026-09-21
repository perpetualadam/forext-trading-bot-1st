"""Live broker position-management quotes and close-decision logging.

No OANDA writes. Paper/backtest do not use this module for candle SL/TP.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any


MANAGE_PRICE_STALE_SEC = 90.0
PRICE_SOURCE_OANDA_CURRENT = "OANDA_CURRENT"
PRICE_SOURCE_POST_ENTRY_CANDLE = "POST_ENTRY_CANDLE"
PRICE_SOURCE_PAPER_CANDLE = "PAPER_CANDLE"
PRICE_SOURCE_UNAVAILABLE = "UNAVAILABLE"


@dataclass
class ManageQuote:
    instrument: str
    bid: float | None = None
    ask: float | None = None
    closeout_bid: float | None = None
    closeout_ask: float | None = None
    time_epoch: float | None = None
    tradeable: bool = True


def closeout_manage_price(quote: ManageQuote | None, direction: str) -> float | None:
    """BUY flattens on closeout bid; SELL flattens on closeout ask."""
    if quote is None:
        return None
    d = (direction or "").upper().strip()
    raw = quote.closeout_ask if d == "SELL" else quote.closeout_bid
    try:
        px = float(raw) if raw is not None else float("nan")
    except (TypeError, ValueError):
        return None
    if not math.isfinite(px) or px <= 0:
        return None
    return px


def quote_age_sec(quote: ManageQuote | None, now: float | None = None) -> float | None:
    if quote is None or quote.time_epoch is None:
        return None
    try:
        return float(now if now is not None else time.time()) - float(quote.time_epoch)
    except (TypeError, ValueError):
        return None


def resolve_broker_manage_price(
    quote: ManageQuote | None,
    direction: str,
    *,
    now: float | None = None,
    max_age_sec: float = MANAGE_PRICE_STALE_SEC,
) -> tuple[float | None, str]:
    """Return (closeout price, source). Never falls back to an M5 close."""
    if quote is None or not quote.tradeable:
        return None, PRICE_SOURCE_UNAVAILABLE
    age = quote_age_sec(quote, now)
    if age is not None and age > float(max_age_sec):
        return None, PRICE_SOURCE_UNAVAILABLE
    px = closeout_manage_price(quote, direction)
    if px is None:
        return None, PRICE_SOURCE_UNAVAILABLE
    return px, PRICE_SOURCE_OANDA_CURRENT


def broker_sl_tp_hit(_pos: Any) -> bool:
    """OANDA is authoritative for hard SL/TP on broker-backed locals."""
    return False


def format_manage_price_line(
    *,
    symbol: str,
    broker_id: str,
    side: str,
    source: str,
    current_price: float | None,
    closeout_bid: float | None = None,
    closeout_ask: float | None = None,
    m5_close: float | None = None,
    m5_time: str = "",
    fill: float | None = None,
    fill_time: str = "",
    current_pips: float | None = None,
    mfe_pips: float | None = None,
    tp_progress: float | None = None,
) -> str:
    def _px(val: float | None) -> str:
        return "n/a" if val is None else f"{float(val):.5f}"

    def _p(val: float | None) -> str:
        return "n/a" if val is None else f"{float(val):+.1f}"

    prog = "n/a" if tp_progress is None else f"{float(tp_progress):.2f}"
    return (
        f"[MANAGE PRICE] symbol={symbol} broker_id={broker_id or ''} side={side} "
        f"source={source} current_price={_px(current_price)} "
        f"closeout_bid={_px(closeout_bid)} closeout_ask={_px(closeout_ask)} "
        f"m5_close={_px(m5_close)} m5_time={m5_time or 'n/a'} "
        f"fill={_px(fill)} fill_time={fill_time or 'n/a'} "
        f"current_pips={_p(current_pips)} mfe_pips={_p(mfe_pips)} tp_progress={prog}"
    )


def format_close_decision_line(
    *,
    symbol: str,
    broker_id: str,
    reason: str,
    entry: float,
    current_price: float | None,
    price_source: str,
    sl: float,
    tp: float,
    mfe_pips: float | None,
    tp_progress: float | None,
    protected_exit_pips: float | None,
    trigger: str,
    sl_tp_hit: bool,
    weekend_flat: bool,
    protect_hit: bool,
    current_side: str,
    proposed_side: str = "n/a",
    rl_action: str = "n/a",
) -> str:
    def _px(val: float | None) -> str:
        return "n/a" if val is None else f"{float(val):.5f}"

    def _p(val: float | None) -> str:
        return "n/a" if val is None else f"{float(val):.1f}"

    prog = "n/a" if tp_progress is None else f"{float(tp_progress):.2f}"
    return (
        f"[CLOSE DECISION] symbol={symbol} broker_id={broker_id or ''} reason={reason} "
        f"entry={float(entry):.5f} current_price={_px(current_price)} price_source={price_source} "
        f"sl={float(sl):.5f} tp={float(tp):.5f} mfe_pips={_p(mfe_pips)} tp_progress={prog} "
        f"protected_exit_pips={_p(protected_exit_pips)} trigger={trigger} "
        f"sl_tp_hit={str(sl_tp_hit).lower()} weekend_flat={str(weekend_flat).lower()} "
        f"protect_hit={str(protect_hit).lower()} current_side={current_side} "
        f"proposed_side={proposed_side} rl_action={rl_action}"
    )
