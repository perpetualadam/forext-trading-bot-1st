"""Deterministic per-strategy rules from the same indicator family as live.

Live direction is produced by AI vote + RL after ``select_strategy``. Those paths
have I/O and mutate live RAM, so shadow uses explicit indicator rules instead.
Results are hypothetical ``shadow_rule`` signals, not live AI decisions.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from forex_bot.indicators import compute_indicators
from forex_bot.shadow.reasons import SCALP_FAMILY, ShadowReason


def lookback_for(strategy: str, scalp_lb: int, swing_lb: int) -> int:
    return scalp_lb if strategy in SCALP_FAMILY else swing_lb


def signal_from_indicators(strategy: str, df: pd.DataFrame) -> tuple[str | None, str]:
    """Return (BUY|SELL|None, detail). None → NO_SIGNAL."""
    if df is None or df.empty or len(df) < 5:
        return None, ShadowReason.INSUFFICIENT_DATA
    row = df.iloc[-1]
    needed = ("close", "ma_fast", "ma_slow", "atr", "boll_up", "boll_down", "high", "low")
    for col in needed:
        if col not in df.columns or pd.isna(row[col]):
            return None, ShadowReason.INSUFFICIENT_DATA
    close = float(row["close"])
    ma_f = float(row["ma_fast"])
    ma_s = float(row["ma_slow"])
    observed = (
        close,
        ma_f,
        ma_s,
        float(row["atr"]),
        float(row["boll_up"]),
        float(row["boll_down"]),
        float(row["high"]),
        float(row["low"]),
    )
    if not all(math.isfinite(v) for v in observed):
        return None, ShadowReason.INSUFFICIENT_DATA
    if strategy in ("trend", "swing_trend"):
        if ma_f > ma_s and close >= ma_f:
            return "BUY", "ma_fast_above_slow"
        if ma_f < ma_s and close <= ma_f:
            return "SELL", "ma_fast_below_slow"
        return None, ShadowReason.NO_SIGNAL
    if strategy in ("mean_reversion", "swing_mean_reversion"):
        if close > float(row["boll_up"]):
            return "SELL", "close_above_boll_up"
        if close < float(row["boll_down"]):
            return "BUY", "close_below_boll_down"
        return None, ShadowReason.NO_SIGNAL
    if strategy == "scalp":
        if ma_f > ma_s and close > ma_f:
            return "BUY", "scalp_momentum_up"
        if ma_f < ma_s and close < ma_f:
            return "SELL", "scalp_momentum_down"
        return None, ShadowReason.NO_SIGNAL
    if strategy == "swing_breakout":
        look = min(20, max(5, len(df) - 2))
        prior = df.iloc[-(look + 1) : -1]
        if prior.empty:
            return None, ShadowReason.INSUFFICIENT_DATA
        hi = float(prior["high"].max())
        lo = float(prior["low"].min())
        if not math.isfinite(hi) or not math.isfinite(lo):
            return None, ShadowReason.INSUFFICIENT_DATA
        if close > hi:
            return "BUY", "close_above_prior_high"
        if close < lo:
            return "SELL", "close_below_prior_low"
        return None, ShadowReason.NO_SIGNAL
    return None, ShadowReason.NO_SIGNAL


def prepare_frame(raw: pd.DataFrame, lookback: int) -> tuple[pd.DataFrame | None, str]:
    if raw is None or raw.empty:
        return None, ShadowReason.INSUFFICIENT_DATA
    need = {"open", "high", "low", "close"}
    if not need.issubset(set(raw.columns)):
        return None, ShadowReason.INSUFFICIENT_DATA
    ready_cols = {"ma_fast", "ma_slow", "atr", "boll_up", "boll_down"}
    if ready_cols.issubset(set(raw.columns)):
        return raw, "ok"
    out = compute_indicators(raw, lookback=lookback)
    if out.empty:
        return None, ShadowReason.INSUFFICIENT_DATA
    return out, "ok"


def last_atr(df: pd.DataFrame) -> float:
    try:
        v = float(df["atr"].iloc[-1])
        return v if v > 0 and not math.isnan(v) else 0.0
    except (KeyError, TypeError, ValueError, IndexError):
        return 0.0


def snapshot_features(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {}
    row = df.iloc[-1]
    keys = ("close", "ma_fast", "ma_slow", "atr", "rsi", "boll_up", "boll_down")
    out: dict[str, Any] = {}
    for k in keys:
        if k in df.columns:
            try:
                v = float(row[k])
                out[k] = None if math.isnan(v) else v
            except (TypeError, ValueError):
                out[k] = None
    return out


def _finite(v: Any) -> bool:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return False
    return not math.isnan(x)


def signal_from_arrays(strategy: str, i: int, pack: dict[str, Any]) -> tuple[str | None, str]:
    """Same rules as ``signal_from_indicators`` using precomputed arrays."""
    n = int(pack["n"])
    if i < 0 or i >= n:
        return None, ShadowReason.INSUFFICIENT_DATA
    close = float(pack["close"][i])
    ma_f = float(pack["ma_fast"][i])
    ma_s = float(pack["ma_slow"][i])
    atr = float(pack["atr"][i])
    bu = float(pack["boll_up"][i])
    bd = float(pack["boll_down"][i])
    if not all(_finite(v) for v in (close, ma_f, ma_s, atr, bu, bd)):
        return None, ShadowReason.INSUFFICIENT_DATA
    if strategy in ("trend", "swing_trend"):
        if ma_f > ma_s and close >= ma_f:
            return "BUY", "ma_fast_above_slow"
        if ma_f < ma_s and close <= ma_f:
            return "SELL", "ma_fast_below_slow"
        return None, ShadowReason.NO_SIGNAL
    if strategy in ("mean_reversion", "swing_mean_reversion"):
        if close > bu:
            return "SELL", "close_above_boll_up"
        if close < bd:
            return "BUY", "close_below_boll_down"
        return None, ShadowReason.NO_SIGNAL
    if strategy == "scalp":
        if ma_f > ma_s and close > ma_f:
            return "BUY", "scalp_momentum_up"
        if ma_f < ma_s and close < ma_f:
            return "SELL", "scalp_momentum_down"
        return None, ShadowReason.NO_SIGNAL
    if strategy == "swing_breakout":
        hi = pack["prior_hi"][i]
        lo = pack["prior_lo"][i]
        if not _finite(hi) or not _finite(lo):
            return None, ShadowReason.INSUFFICIENT_DATA
        if close > float(hi):
            return "BUY", "close_above_prior_high"
        if close < float(lo):
            return "SELL", "close_below_prior_low"
        return None, ShadowReason.NO_SIGNAL
    return None, ShadowReason.NO_SIGNAL


def build_feature_pack(df: pd.DataFrame, lookback: int, history_window: int) -> dict[str, Any]:
    """Causal indicator pack for one lookback. Rolling windows use only rows ≤ i."""
    ind = compute_indicators(df, lookback=lookback)
    n = len(ind)
    win = max(int(history_window or 0), 250, int(lookback) + 5)
    close = ind["close"].to_numpy(dtype=float, copy=False)
    high = ind["high"].to_numpy(dtype=float, copy=False)
    low = ind["low"].to_numpy(dtype=float, copy=False)
    atr = ind["atr"].to_numpy(dtype=float, copy=False)
    quant_ok: np.ndarray = np.ones(n, dtype=bool)
    prior_hi = np.full(n, np.nan)
    prior_lo = np.full(n, np.nan)
    for i in range(n):
        start = max(0, i + 1 - win)
        w = atr[start : i + 1]
        last = atr[i]
        if len(w) >= 20 and not math.isnan(last):
            valid = w[~np.isnan(w)]
            if len(valid) >= 20:
                p90 = float(np.percentile(valid, 90))
                p10 = float(np.percentile(valid, 10))
                if last > p90 * 2.0 or last < p10 * 0.5:
                    quant_ok[i] = False
        length = i + 1 - start
        if length >= 5:
            look = min(20, max(5, length - 2))
            p0 = i - look
            if p0 >= start and p0 < i:
                prior_hi[i] = float(np.max(high[p0:i]))
                prior_lo[i] = float(np.min(low[p0:i]))
    return {
        "n": n,
        "window": win,
        "frame": ind,
        "close": close,
        "high": high,
        "low": low,
        "ma_fast": ind["ma_fast"].to_numpy(dtype=float, copy=False),
        "ma_slow": ind["ma_slow"].to_numpy(dtype=float, copy=False),
        "atr": atr,
        "boll_up": ind["boll_up"].to_numpy(dtype=float, copy=False),
        "boll_down": ind["boll_down"].to_numpy(dtype=float, copy=False),
        "quant_ok": quant_ok,
        "prior_hi": prior_hi,
        "prior_lo": prior_lo,
    }
