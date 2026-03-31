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


def compute_indicators(
    df: pd.DataFrame,
    lookback: int | None = None,
    *,
    indicator_scale_n: int | None = None,
) -> pd.DataFrame:
    """
    ATR, trend (ma_fast - ma_slow), volatility (= ATR), MACD, Bollinger, RSI.

    If ``lookback`` is None, uses legacy fixed windows (5/20/14).
    If set, scales MA/ATR/RSI periods from ``lookback`` and available bar count.

    ``indicator_scale_n``: when using a **trailing window** of rows (e.g. fast backtest), set this
    to the full bar index length (``idx + 1``) so period lengths match full-history scaling while
    rolling runs only on the window (last row values align with full ``df.iloc[:idx+1]``).
    """
    out = df.copy()
    n = len(out)
    if n == 0:
        return out

    sn = indicator_scale_n if indicator_scale_n is not None else n

    if lookback is None:
        ma_fast_n, ma_slow_n, atr_n, rsi_n = 5, 20, 14, 14
    else:
        lb = max(20, min(int(lookback), max(sn, 20)))
        cap = min(n - 1, sn - 1)
        ma_fast_n = max(3, min(lb // 10, cap))
        ma_slow_n = max(ma_fast_n + 1, min(lb // 2, cap))
        atr_n = max(7, min(lb // 5, min(30, cap)))
        rsi_n = max(7, min(14, lb // 4))

    out["ma_fast"] = out["close"].rolling(ma_fast_n).mean()
    out["ma_slow"] = out["close"].rolling(ma_slow_n).mean()
    out["rsi"] = _rsi(out["close"], rsi_n)
    ema_fast = max(5, min(12, ma_fast_n * 2))
    ema_slow = max(ema_fast + 1, min(26, ma_slow_n))
    ema12 = out["close"].ewm(span=ema_fast, adjust=False).mean()
    ema26 = out["close"].ewm(span=ema_slow, adjust=False).mean()
    out["macd"] = ema12 - ema26
    bb_n = max(10, min(ma_slow_n, n - 1))
    mid = out["close"].rolling(bb_n).mean()
    std_bb = out["close"].rolling(bb_n).std()
    out["boll_up"] = mid + 2 * std_bb
    out["boll_down"] = mid - 2 * std_bb
    out["atr"] = _true_range(out["high"], out["low"], out["close"]).rolling(atr_n).mean()
    out["trend_strength"] = out["ma_fast"] - out["ma_slow"]
    out["trend"] = out["trend_strength"]
    out["volatility"] = out["atr"]
    return out
