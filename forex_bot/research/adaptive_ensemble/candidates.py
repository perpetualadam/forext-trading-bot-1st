"""Offline strategy candidates. Experimental proxies, not original AI/RL."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

BUY = "BUY"
SELL = "SELL"
NO_TRADE = "NO_TRADE"

FAMILY_PROXY = "EXPERIMENTAL_PROXY_STAGE_G"
FAMILY_BASELINE = "BASELINE_COMPARISON_ONLY"


@dataclass(frozen=True)
class CandidateSignal:
    candidate_id: str
    family: str
    version: str
    direction: str
    confidence: float | None
    invalidation: str | None
    horizon_bars: int
    required_atr: float | None


def as_float(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    x = float(v)
    if not math.isfinite(x):
        return None
    return x


def proxy_trend_ma_slope(snap: dict[str, Any]) -> CandidateSignal:
    slope = as_float(snap.get("ma_slope"))
    atr = as_float(snap.get("atr"))
    h1 = as_float(snap.get("h1_dir"))
    if slope is None or atr is None or atr <= 0:
        return CandidateSignal(
            "proxy_trend_ma_slope_v1", FAMILY_PROXY, "1", NO_TRADE, None, "missing_features", 24, None
        )
    direction = NO_TRADE
    reason: str | None = "slope_too_small"
    if slope > 1.0e-5:
        direction = BUY
        reason = None
    elif slope < -1.0e-5:
        direction = SELL
        reason = None
    want = 1.0 if direction == BUY else -1.0
    if direction != NO_TRADE and h1 is not None and h1 != 0 and h1 != want:
        return CandidateSignal(
            "proxy_trend_ma_slope_v1",
            FAMILY_PROXY,
            "1",
            NO_TRADE,
            None,
            "h1_disagreement",
            24,
            atr,
        )
    conf = min(1.0, abs(slope) / 5.0e-5) if direction != NO_TRADE else None
    return CandidateSignal("proxy_trend_ma_slope_v1", FAMILY_PROXY, "1", direction, conf, reason, 24, atr)


def proxy_rsi_mean_reversion(snap: dict[str, Any]) -> CandidateSignal:
    rsi = as_float(snap.get("rsi"))
    atr = as_float(snap.get("atr"))
    if rsi is None or atr is None or atr <= 0:
        return CandidateSignal(
            "proxy_rsi_mean_reversion_v1", FAMILY_PROXY, "1", NO_TRADE, None, "missing_features", 12, None
        )
    if rsi >= 70:
        return CandidateSignal(
            "proxy_rsi_mean_reversion_v1", FAMILY_PROXY, "1", SELL, min(1.0, (rsi - 70) / 15.0), None, 12, atr
        )
    if rsi <= 30:
        return CandidateSignal(
            "proxy_rsi_mean_reversion_v1", FAMILY_PROXY, "1", BUY, min(1.0, (30 - rsi) / 15.0), None, 12, atr
        )
    return CandidateSignal(
        "proxy_rsi_mean_reversion_v1", FAMILY_PROXY, "1", NO_TRADE, None, "rsi_neutral", 12, atr
    )


def proxy_atr_expansion_breakout(snap: dict[str, Any]) -> CandidateSignal:
    close = as_float(snap.get("close"))
    hi = as_float(snap.get("prior_high"))
    lo = as_float(snap.get("prior_low"))
    atr = as_float(snap.get("atr"))
    atr_pct = as_float(snap.get("atr_pct"))
    if close is None or hi is None or lo is None or atr is None or atr_pct is None or atr <= 0:
        return CandidateSignal(
            "proxy_atr_expansion_breakout_v1", FAMILY_PROXY, "1", NO_TRADE, None, "missing_features", 18, None
        )
    if atr_pct < 0.55:
        return CandidateSignal(
            "proxy_atr_expansion_breakout_v1",
            FAMILY_PROXY,
            "1",
            NO_TRADE,
            None,
            "no_vol_expansion",
            18,
            atr,
        )
    if close > hi:
        return CandidateSignal(
            "proxy_atr_expansion_breakout_v1",
            FAMILY_PROXY,
            "1",
            BUY,
            min(1.0, (close - hi) / (atr + 1e-12)),
            None,
            18,
            atr,
        )
    if close < lo:
        return CandidateSignal(
            "proxy_atr_expansion_breakout_v1",
            FAMILY_PROXY,
            "1",
            SELL,
            min(1.0, (lo - close) / (atr + 1e-12)),
            None,
            18,
            atr,
        )
    return CandidateSignal(
        "proxy_atr_expansion_breakout_v1", FAMILY_PROXY, "1", NO_TRADE, None, "inside_range", 18, atr
    )


GENERATORS = {
    "proxy_trend_ma_slope_v1": proxy_trend_ma_slope,
    "proxy_rsi_mean_reversion_v1": proxy_rsi_mean_reversion,
    "proxy_atr_expansion_breakout_v1": proxy_atr_expansion_breakout,
}

REGIME_MAP = {
    "trending": "proxy_trend_ma_slope_v1",
    "ranging": "proxy_rsi_mean_reversion_v1",
    "breakout": "proxy_atr_expansion_breakout_v1",
    "high_vol_transition": "proxy_atr_expansion_breakout_v1",
    "low_vol_consolidation": None,
    "uncertain": None,
}


def all_signals(snap: dict[str, Any]) -> dict[str, CandidateSignal]:
    return {cid: fn(snap) for cid, fn in GENERATORS.items()}
