"""Offline bid/ask next-bar simulation. No live execution imports."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

SLIPPAGE = {"base": 0.0, "conservative": 0.25, "severe": 0.50, "ablation_no_cost_filter": 0.0}


@dataclass
class Trade:
    pair: str
    direction: str
    entry_i: int
    exit_i: int
    entry_price: float
    exit_price: float
    pnl_quote: float
    pnl_gbp: float
    reason_exit: str
    model_id: str
    regime: str


@dataclass
class Book:
    nav: float
    peak: float
    trades: list[Trade] = field(default_factory=list)
    abstentions: int = 0
    decisions: int = 0
    halted: str | None = None
    open_pos: dict[str, Any] | None = None
    realised: float = 0.0


def _px(row: Any, side: str, which: str) -> float | None:
    col = f"{side}_{which}"
    if col in row.index:
        v = float(row[col])
        if math.isfinite(v):
            return v
    mid = float(row["close"])
    if side == "bid":
        return mid
    return mid


def fill_price(frame: pd.DataFrame, i: int, direction: str, cost: str) -> float | None:
    if i >= len(frame):
        return None
    row = frame.iloc[i]
    slip = SLIPPAGE[cost]
    atr = 0.0
    if "feat_atr" in row.index:
        raw = float(row["feat_atr"])
        if math.isfinite(raw):
            atr = raw
    extra = slip * atr
    if direction == "BUY":
        ask = _px(row, "ask", "open") or _px(row, "ask", "close")
        if ask is None:
            return None
        return float(ask) + extra
    bid = _px(row, "bid", "open") or _px(row, "bid", "close")
    if bid is None:
        return None
    return float(bid) - extra


def mark_exit(
    frame: pd.DataFrame,
    start: int,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    max_hold: int,
) -> tuple[int, float, str]:
    last = min(len(frame) - 1, start + max_hold)
    for j in range(start, last + 1):
        row = frame.iloc[j]
        hi = float(row["high"])
        lo = float(row["low"])
        hit_sl = lo <= sl if direction == "BUY" else hi >= sl
        hit_tp = hi >= tp if direction == "BUY" else lo <= tp
        if hit_sl and hit_tp:
            return j, sl, "ambiguous_same_bar_conservative_sl"
        if hit_sl:
            return j, sl, "stop_loss"
        if hit_tp:
            return j, tp, "take_profit"
    row = frame.iloc[last]
    px: float | None = None
    if "bid_close" in row.index and direction == "BUY":
        cand = float(row["bid_close"])
        if math.isfinite(cand):
            px = cand
    if px is None and "ask_close" in row.index and direction == "SELL":
        cand = float(row["ask_close"])
        if math.isfinite(cand):
            px = cand
    if px is None:
        px = float(row["close"])
    return last, float(px), "time_exit"


def quote_to_gbp(pnl_quote: float, pair: str, gbp_usd: float) -> float:
    if pair.endswith("_USD"):
        return pnl_quote / gbp_usd
    if pair.startswith("USD_"):
        return pnl_quote / gbp_usd
    if pair == "GBP_USD":
        return pnl_quote
    return pnl_quote / gbp_usd
