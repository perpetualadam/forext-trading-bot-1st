"""Technical indicators on OHLCV DataFrames."""

from __future__ import annotations

import pandas as pd


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ma_fast"] = out["close"].rolling(5).mean()
    out["ma_slow"] = out["close"].rolling(20).mean()
    out["rsi"] = _rsi(out["close"], 14)
    ema12 = out["close"].ewm(span=12, adjust=False).mean()
    ema26 = out["close"].ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    mid = out["close"].rolling(20).mean()
    std20 = out["close"].rolling(20).std()
    out["boll_up"] = mid + 2 * std20
    out["boll_down"] = mid - 2 * std20
    out["atr"] = _true_range(out["high"], out["low"], out["close"]).rolling(14).mean()
    out["trend_strength"] = out["ma_fast"] - out["ma_slow"]
    # Aliases for Final Boss++ / RL state strings
    out["trend"] = out["trend_strength"]
    out["volatility"] = out["atr"]
    return out
