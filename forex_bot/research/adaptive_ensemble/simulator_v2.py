"""adaptive_simulator_v2. Does not alter Stage G simulate.py or its P&L."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble.simulate import SLIPPAGE

VERSION = "adaptive_simulator_v2"
CHANGE_CLASS = "BEHAVIOURAL_REPAIR_REQUIRES_REBASELINE"
WARMUP_BARS = 120
FINANCING = "FINANCING_UNAVAILABLE"
M5_PATH_UNCERTAINTY = "m5_ohlc_cannot_resolve_intra_bar_path"


def _finite_px(row: Any, col: str) -> float | None:
    if col not in row.index:
        return None
    try:
        v = float(row[col])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v <= 0:
        return None
    return v


def executable(row: Any, side: str, which: str) -> float | None:
    """Bid/ask only. Never substitutes mid."""
    return _finite_px(row, f"{side}_{which}")


def _atr(row: Any) -> float:
    raw = _finite_px(row, "feat_atr")
    return float(raw) if raw is not None else 0.0


def _slip(atr: float, cost: str) -> float:
    return float(SLIPPAGE[cost]) * atr


def warmup_reason(frame: pd.DataFrame, i: int) -> str | None:
    if i < WARMUP_BARS:
        return "insufficient_warmup"
    if i >= len(frame):
        return "missing_bar"
    row = frame.iloc[i]
    if _atr(row) <= 0:
        return "insufficient_warmup"
    if "feat_h1_dir" not in row.index:
        return "h1_incomplete"
    try:
        h1f = float(row["feat_h1_dir"])
    except (TypeError, ValueError):
        return "h1_incomplete"
    if not math.isfinite(h1f):
        return "h1_incomplete"
    return None


def entry_fill(
    frame: pd.DataFrame, i: int, direction: str, cost: str
) -> tuple[float | None, str | None]:
    if i >= len(frame):
        return None, "missing_bar"
    row = frame.iloc[i]
    extra = _slip(_atr(row), cost)
    if direction == "BUY":
        ask = executable(row, "ask", "open")
        if ask is None:
            return None, "missing_ask"
        return ask + extra, None
    bid = executable(row, "bid", "open")
    if bid is None:
        return None, "missing_bid"
    return bid - extra, None


def _exit_px(direction: str, raw: float, extra: float) -> float:
    if direction == "BUY":
        return raw - extra
    return raw + extra


def mark_exit_v2(
    frame: pd.DataFrame,
    start: int,
    direction: str,
    sl: float,
    tp: float,
    max_hold: int,
    cost: str,
) -> tuple[int | None, float | None, str]:
    if start >= len(frame):
        return None, None, "missing_bar"
    last = min(len(frame) - 1, start + max_hold)
    for j in range(start, last + 1):
        row = frame.iloc[j]
        extra = _slip(_atr(row), cost)
        if direction == "BUY":
            bid_o = executable(row, "bid", "open")
            bid_h = executable(row, "bid", "high")
            bid_l = executable(row, "bid", "low")
            bid_c = executable(row, "bid", "close")
            if bid_o is None or bid_c is None:
                return None, None, "missing_bid"
            hi = bid_h if bid_h is not None else bid_c
            lo = bid_l if bid_l is not None else bid_c
            open_through_sl = bid_o <= sl
            open_through_tp = bid_o >= tp
            if open_through_sl and open_through_tp:
                return j, _exit_px("BUY", bid_o, extra), "ambiguous_open_conservative_sl_gap"
            if open_through_sl:
                return j, _exit_px("BUY", bid_o, extra), "gap_stop_executable_open"
            if open_through_tp:
                return j, _exit_px("BUY", tp, extra), "gap_target_capped_at_tp"
            hit_sl = lo <= sl
            hit_tp = hi >= tp
            if hit_sl and hit_tp:
                return j, _exit_px("BUY", sl, extra), "ambiguous_same_bar_conservative_sl"
            if hit_sl:
                reason = "stop_loss" if lo == sl else "stop_loss_m5_path_uncertain"
                return j, _exit_px("BUY", sl, extra), reason
            if hit_tp:
                return j, _exit_px("BUY", tp, extra), "take_profit"
        else:
            ask_o = executable(row, "ask", "open")
            ask_h = executable(row, "ask", "high")
            ask_l = executable(row, "ask", "low")
            ask_c = executable(row, "ask", "close")
            if ask_o is None or ask_c is None:
                return None, None, "missing_ask"
            hi = ask_h if ask_h is not None else ask_c
            lo = ask_l if ask_l is not None else ask_c
            open_through_sl = ask_o >= sl
            open_through_tp = ask_o <= tp
            if open_through_sl and open_through_tp:
                return j, _exit_px("SELL", ask_o, extra), "ambiguous_open_conservative_sl_gap"
            if open_through_sl:
                return j, _exit_px("SELL", ask_o, extra), "gap_stop_executable_open"
            if open_through_tp:
                return j, _exit_px("SELL", tp, extra), "gap_target_capped_at_tp"
            hit_sl = hi >= sl
            hit_tp = lo <= tp
            if hit_sl and hit_tp:
                return j, _exit_px("SELL", sl, extra), "ambiguous_same_bar_conservative_sl"
            if hit_sl:
                return j, _exit_px("SELL", sl, extra), "stop_loss_m5_path_uncertain" if hi > sl else "stop_loss"
            if hit_tp:
                return j, _exit_px("SELL", tp, extra), "take_profit"
    row = frame.iloc[last]
    extra = _slip(_atr(row), cost)
    if direction == "BUY":
        bid_c = executable(row, "bid", "close")
        if bid_c is None:
            return None, None, "missing_bid"
        return last, _exit_px("BUY", bid_c, extra), "time_exit"
    ask_c = executable(row, "ask", "close")
    if ask_c is None:
        return None, None, "missing_ask"
    return last, _exit_px("SELL", ask_c, extra), "time_exit"


def financing_note(hold_bars: int) -> str:
    del hold_bars
    return FINANCING
