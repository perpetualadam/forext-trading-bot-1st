"""Timestamp-safe market features. Decision at completed bar i uses only iloc[:i+1]."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

FEATURE_VERSION = "stage_g_features_v1"
UNAVAILABLE = "UNAVAILABLE"
NOT_EVALUATED = "NOT_EVALUATED"

FEATURE_CATALOG = {
    "market_regime": {
        "definition": "Rule labels from slope, ATR rank, RSI, compression at bar i",
        "lookback": "50 MA + 100 ATR mean + 14 RSI",
        "timestamp": "completed bar i inclusive",
        "missing": "uncertain",
        "normalisation": "none",
        "version": FEATURE_VERSION,
        "leakage_test": "prefix vs full frame",
    },
    "trend": {"lookback": "MA20-MA50 slope over 5 bars", "timestamp": "bar i"},
    "momentum": {"lookback": "RSI14", "timestamp": "bar i"},
    "volatility": {"lookback": "ATR14 and ATR/ATR100", "timestamp": "bar i"},
    "multi_timeframe": {"lookback": "previous completed UTC hour only", "timestamp": "bar i"},
    "market_structure": {"lookback": "prior 20-bar high/low excluding current", "timestamp": "bar i"},
    "sessions": {"lookback": "UTC hour buckets; DST via UTC not local TZ", "timestamp": "bar i"},
    "execution_costs": {"lookback": "bid/ask half-spread / ATR", "timestamp": "bar i"},
    "correlations": {"status": NOT_EVALUATED, "note": "single-pair exploratory runs only"},
    "economic_events": {"status": UNAVAILABLE},
}

SESSION_ASIAN = "asian"
SESSION_LONDON = "london"
SESSION_NY = "new_york"
SESSION_OVERLAP = "london_ny_overlap"
SESSION_OFF = "off"


def _rolling_mean(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full_like(x, np.nan, dtype=float)
    if n <= 0 or len(x) < n:
        return out
    c = np.cumsum(np.nan_to_num(x, nan=0.0))
    c = np.insert(c, 0, 0.0)
    out[n - 1 :] = (c[n:] - c[: -n]) / n
    return out


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev = np.roll(close, 1)
    prev[0] = close[0]
    return np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))


def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_g = _rolling_mean(gain, period)
    avg_l = _rolling_mean(loss, period)
    rs = avg_g / (avg_l + 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))


def session_from_utc(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    hour = ts.astimezone(timezone.utc).hour
    if 7 <= hour < 8:
        return SESSION_LONDON
    if 12 <= hour < 16:
        return SESSION_OVERLAP
    if 8 <= hour < 12:
        return SESSION_LONDON
    if 16 <= hour < 21:
        return SESSION_NY
    if 0 <= hour < 7:
        return SESSION_ASIAN
    return SESSION_OFF


def classify_regime(
    *,
    ma_slope: float,
    atr: float,
    atr_pct: float,
    rsi: float,
    compression: float,
) -> str:
    if not all(math.isfinite(v) for v in (ma_slope, atr, atr_pct, rsi, compression)):
        return "uncertain"
    if atr_pct >= 0.80 and abs(ma_slope) > 0:
        return "high_vol_transition"
    if compression >= 0.70 and atr_pct <= 0.40:
        return "low_vol_consolidation"
    if abs(ma_slope) >= 1.0e-5 and atr_pct >= 0.35:
        return "trending"
    if abs(ma_slope) < 5.0e-6 and 35 <= rsi <= 65:
        return "ranging"
    if atr_pct >= 0.65 and compression <= 0.35:
        return "breakout"
    return "uncertain"


def compute_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorised features on completed bars. Row i uses data through i inclusive."""
    need = {"time", "open", "high", "low", "close"}
    if not need.issubset(df.columns):
        raise ValueError("OHLC+time required")
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(close)
    tr = _true_range(high, low, close)
    atr = _rolling_mean(tr, 14)
    ma_f = _rolling_mean(close, 20)
    ma_s = _rolling_mean(close, 50)
    slope = ma_f - np.roll(ma_f, 5)
    slope[:5] = np.nan
    rsi = _rsi(close, 14)
    ret = np.diff(close, prepend=close[0]) / np.where(np.abs(close) > 1e-12, close, np.nan)
    rvol = _rolling_mean(np.abs(ret), 20)
    rng = high - low
    rng_ma = _rolling_mean(rng, 20)
    compression = 1.0 - np.clip(rng / (rng_ma + 1e-12), 0.0, 2.0) / 2.0
    atr_ma = _rolling_mean(np.where(np.isfinite(atr), atr, 0.0), 100)
    atr_rank = np.clip(atr / (atr_ma + 1e-12) / 2.0, 0.0, 1.0)
    prior_hi = np.full(n, np.nan)
    prior_lo = np.full(n, np.nan)
    for i in range(20, n):
        prior_hi[i] = float(np.max(high[i - 20 : i]))
        prior_lo[i] = float(np.min(low[i - 20 : i]))
    bid = df["bid_close"].to_numpy(dtype=float) if "bid_close" in df.columns else np.full(n, np.nan)
    ask = df["ask_close"].to_numpy(dtype=float) if "ask_close" in df.columns else np.full(n, np.nan)
    half = (ask - bid) / 2.0
    sessions = []
    times = pd.to_datetime(df["time"], utc=True)
    regimes = []
    for i in range(n):
        sessions.append(session_from_utc(times.iloc[i].to_pydatetime()))
        regimes.append(
            classify_regime(
                ma_slope=float(slope[i]) if math.isfinite(slope[i]) else float("nan"),
                atr=float(atr[i]) if math.isfinite(atr[i]) else float("nan"),
                atr_pct=float(atr_rank[i]) if math.isfinite(atr_rank[i]) else float("nan"),
                rsi=float(rsi[i]) if math.isfinite(rsi[i]) else float("nan"),
                compression=float(compression[i]) if math.isfinite(compression[i]) else float("nan"),
            )
        )
    hour = times.dt.floor("h")
    hour_keys = hour.to_numpy()
    hour_open: dict[Any, float] = {}
    hour_close: dict[Any, float] = {}
    order: list[Any] = []
    for i in range(n):
        h = hour_keys[i]
        if h not in hour_open:
            hour_open[h] = float(close[i])
            order.append(h)
        hour_close[h] = float(close[i])
    prev_dir: dict[Any, float] = {}
    for j, h in enumerate(order):
        if j == 0:
            continue
        ph = order[j - 1]
        prev_dir[h] = float(np.sign(hour_close[ph] - hour_open[ph]))
    h1_dir = np.array([prev_dir.get(hour_keys[i], np.nan) for i in range(n)], dtype=float)
    out = df.copy()
    out["feat_ma_fast"] = ma_f
    out["feat_ma_slow"] = ma_s
    out["feat_ma_slope"] = slope
    out["feat_atr"] = atr
    out["feat_atr_pct"] = atr_rank
    out["feat_rsi"] = rsi
    out["feat_rvol"] = rvol
    out["feat_compression"] = compression
    out["feat_prior_high"] = prior_hi
    out["feat_prior_low"] = prior_lo
    out["feat_half_spread"] = half
    out["feat_spread_over_atr"] = half / (atr + 1e-12)
    out["feat_session"] = sessions
    out["feat_regime"] = regimes
    out["feat_h1_dir"] = h1_dir
    out["feat_dow"] = times.dt.dayofweek
    out["feature_version"] = FEATURE_VERSION
    return out


def snapshot_at(frame: pd.DataFrame, i: int) -> dict[str, Any]:
    if i < 0 or i >= len(frame):
        return {"status": UNAVAILABLE}
    row = frame.iloc[i]
    return {
        "status": "ok",
        "i": i,
        "time": str(row["time"]),
        "regime": row["feat_regime"],
        "session": row["feat_session"],
        "ma_slope": row["feat_ma_slope"],
        "atr": row["feat_atr"],
        "rsi": row["feat_rsi"],
        "atr_pct": row["feat_atr_pct"],
        "half_spread": row["feat_half_spread"],
        "spread_over_atr": row["feat_spread_over_atr"],
        "h1_dir": row["feat_h1_dir"],
        "prior_high": row["feat_prior_high"],
        "prior_low": row["feat_prior_low"],
        "close": row["close"],
        "feature_version": FEATURE_VERSION,
        "economic_events": UNAVAILABLE,
    }
