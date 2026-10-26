"""Causal features from completed candles only."""

from __future__ import annotations

import pandas as pd

from forex_bot.research.learning.protocol import (
    ATR_PERIOD,
    FEATURE_SCHEMA_VERSION,
    MA_FAST,
    MA_SLOW,
    MOMENTUM_WINDOW,
    RANGE_WINDOW,
    VOLATILITY_WINDOW,
)

FEATURE_COLUMNS = (
    "return_1",
    "rolling_vol_20",
    "atr_14",
    "ma_distance",
    "momentum_12",
    "spread",
    "hour_utc",
    "session_code",
    "range_20",
    "volume",
)


def session_code(hour: pd.Series) -> pd.Series:
    """Bucket the bar's own UTC hour. 0 Asia, 1 London, 2 New York, 3 late."""
    code = pd.Series(3, index=hour.index, dtype="float64")
    code = code.mask(hour < 7, 0.0)
    code = code.mask((hour >= 7) & (hour < 12), 1.0)
    code = code.mask((hour >= 12) & (hour < 17), 2.0)
    return code


def causal_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Features at row T use bars 0..T. They do not use T+1 or later."""
    mid = (frame["bid_close"] + frame["ask_close"]) / 2.0
    previous = mid.shift(1)
    true_range = pd.concat(
        [
            frame["bid_high"] - frame["bid_low"],
            (frame["bid_high"] - previous).abs(),
            (frame["bid_low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    fast = mid.rolling(MA_FAST, min_periods=MA_FAST).mean()
    slow = mid.rolling(MA_SLOW, min_periods=MA_SLOW).mean()
    returns = mid / previous - 1.0
    volume = frame["volume"] if "volume" in frame.columns else pd.Series(float("nan"), index=frame.index)
    out = pd.DataFrame(
        {
            "return_1": returns,
            "rolling_vol_20": returns.rolling(VOLATILITY_WINDOW, min_periods=VOLATILITY_WINDOW).std(),
            "atr_14": true_range.rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean(),
            "ma_distance": (fast - slow) / mid,
            "momentum_12": mid / mid.shift(MOMENTUM_WINDOW) - 1.0,
            "spread": frame["ask_close"] - frame["bid_close"],
            "hour_utc": frame["time"].dt.hour.astype("float64"),
            "session_code": session_code(frame["time"].dt.hour),
            "range_20": (
                frame["bid_high"].rolling(RANGE_WINDOW, min_periods=RANGE_WINDOW).max()
                - frame["bid_low"].rolling(RANGE_WINDOW, min_periods=RANGE_WINDOW).min()
            )
            / mid,
            "volume": pd.to_numeric(volume, errors="coerce"),
        },
        index=frame.index,
    )
    finite = out.apply(pd.to_numeric, errors="coerce")
    out["feature_valid"] = finite.notna().all(axis=1) & (out["spread"] >= 0)
    out["feature_schema_version"] = FEATURE_SCHEMA_VERSION
    return out


def leaky_future_return(frame: pd.DataFrame) -> pd.DataFrame:
    """Synthetic leakage fixture. The next midpoint return is copied into the current row."""
    out = causal_features(frame)
    mid = (frame["bid_close"] + frame["ask_close"]) / 2.0
    out["return_1"] = mid.shift(-1) / mid - 1.0
    out["feature_valid"] = out["return_1"].notna()
    return out


def prefix_matches(builder, frame: pd.DataFrame, index: int) -> bool:
    """True when row `index` is unchanged after later rows are removed."""
    full = builder(frame).iloc[index]
    short = builder(frame.iloc[: index + 1].copy()).iloc[-1]
    for name in FEATURE_COLUMNS:
        left = full[name]
        right = short[name]
        if pd.isna(left) and pd.isna(right):
            continue
        if pd.isna(left) or pd.isna(right) or abs(float(left) - float(right)) > 1e-12:
            return False
    return True
