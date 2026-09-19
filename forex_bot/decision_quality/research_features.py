"""Research-only HTF, ADX, and regime features. Never used as live filters."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from forex_bot.indicators import _true_range, compute_indicators


def _asof_mask(df: pd.DataFrame, asof: datetime) -> pd.DataFrame:
    ts = pd.to_datetime(df["time"])
    asof_ts = pd.Timestamp(asof)
    return df.loc[ts <= asof_ts].copy()


def resample_closed_ohlc(m5: pd.DataFrame, rule: str, asof: datetime) -> pd.DataFrame:
    """HTF bars fully closed at ``asof``. Incomplete last group is dropped."""
    hist = _asof_mask(m5, asof)
    if hist.empty:
        return hist
    idx = hist.set_index(pd.to_datetime(hist["time"]))
    ohlc = idx.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    ohlc = ohlc.dropna(how="any")
    if ohlc.empty:
        return ohlc.reset_index().rename(columns={"index": "time"})
    delta = pd.tseries.frequencies.to_offset(rule)
    ohlc = ohlc.loc[(ohlc.index + delta) <= pd.Timestamp(asof)]
    out = ohlc.reset_index()
    return out.rename(columns={out.columns[0]: "time"})


def _trend_label(close: pd.Series, lookback: int = 20) -> str:
    if len(close) < max(5, lookback // 2):
        return "UNCERTAIN"
    n = min(lookback, len(close))
    y = close.iloc[-n:].astype(float).to_numpy()
    x = np.arange(n, dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    atr_like = float(np.std(y)) + 1e-12
    if slope > 0.15 * atr_like / n:
        return "BULLISH"
    if slope < -0.15 * atr_like / n:
        return "BEARISH"
    return "FLAT"


def htf_trend_labels(m5: pd.DataFrame, asof: datetime) -> dict[str, str]:
    """M15 / H1 / H4 direction using only bars available at ``asof``."""
    labels = {"M15": "UNCERTAIN", "H1": "UNCERTAIN", "H4": "UNCERTAIN"}
    for tf, rule in (("M15", "15min"), ("H1", "1h"), ("H4", "4h")):
        frame = resample_closed_ohlc(m5, rule, asof)
        if len(frame) < 5:
            continue
        labels[tf] = _trend_label(frame["close"])
    m5_hist = _asof_mask(m5, asof)
    if len(m5_hist) >= 20:
        labels["M5"] = _trend_label(m5_hist["close"])
    else:
        labels["M5"] = "UNCERTAIN"
    return labels


def htf_alignment(side: str, labels: dict[str, str]) -> str:
    d = (side or "").upper().strip()
    want = "BULLISH" if d == "BUY" else "BEARISH"
    h1 = labels.get("H1", "UNCERTAIN")
    h4 = labels.get("H4", "UNCERTAIN")
    parts: list[str] = []
    if h1 == want:
        parts.append("aligned_h1")
    elif h1 in ("BULLISH", "BEARISH"):
        parts.append("against_h1")
    else:
        parts.append("h1_uncertain")
    if h4 == want:
        parts.append("aligned_h4")
    elif h4 in ("BULLISH", "BEARISH"):
        parts.append("against_h4")
    else:
        parts.append("h4_uncertain")
    if h1 in ("BULLISH", "BEARISH") and h4 in ("BULLISH", "BEARISH"):
        parts.append("h1_h4_agree" if h1 == h4 else "h1_h4_conflict")
    return "|".join(parts)


def wilder_adx(df: pd.DataFrame, period: int = 14) -> float | None:
    if df is None or len(df) < period + 2:
        return None
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = _true_range(high, low, close)
    alpha = 1.0 / period
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100.0 * (plus_dm.ewm(alpha=alpha, adjust=False).mean() / (atr + 1e-12))
    minus_di = 100.0 * (minus_dm.ewm(alpha=alpha, adjust=False).mean() / (atr + 1e-12))
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-12)
    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    val = float(adx.iloc[-1])
    if val != val:
        return None
    return val


def atr_percentile(atr: pd.Series, lookback: int = 100) -> float | None:
    valid = atr.dropna()
    if len(valid) < 10:
        return None
    window = valid.iloc[-lookback:]
    last = float(window.iloc[-1])
    return float((window <= last).mean() * 100.0)


def classify_regime(
    *,
    adx: float | None,
    ema_slope: float | None,
    ema_sep_atr: float | None,
    atr_pct: float | None,
) -> str:
    """Explainable primary regime. HIGH/LOW vol override only when trend is unclear."""
    if atr_pct is not None and atr_pct >= 90:
        return "HIGH_VOLATILITY"
    if atr_pct is not None and atr_pct <= 10:
        return "LOW_VOLATILITY"
    strong = adx is not None and adx >= 25
    sep_ok = ema_sep_atr is not None and abs(ema_sep_atr) >= 0.15
    slope = 0.0 if ema_slope is None or ema_slope != ema_slope else float(ema_slope)
    if strong and sep_ok:
        if slope > 0:
            return "TRENDING_UP"
        if slope < 0:
            return "TRENDING_DOWN"
    if adx is not None and adx < 20:
        return "RANGING"
    return "UNCERTAIN"


def indicator_research_fields(df: pd.DataFrame, lookback: int) -> dict[str, float | None | str]:
    """Compute production indicators plus research-only ADX / slopes on ``df`` (already as-of)."""
    if df.empty:
        return {}
    ind = compute_indicators(df, lookback=lookback)
    last = ind.iloc[-1]
    atr = float(last["atr"]) if "atr" in last and last["atr"] == last["atr"] else None
    ma_fast = float(last["ma_fast"]) if last.get("ma_fast") == last.get("ma_fast") else None
    ma_slow = float(last["ma_slow"]) if last.get("ma_slow") == last.get("ma_slow") else None
    ema_sep_atr = None
    ema_slope = None
    if atr and atr > 0 and ma_fast is not None and ma_slow is not None:
        ema_sep_atr = (ma_fast - ma_slow) / atr
    if ma_fast is not None and len(ind) >= 6:
        prev = float(ind["ma_fast"].iloc[-6])
        if prev == prev:
            ema_slope = ma_fast - prev
    close = ind["close"].astype(float)
    recent = close.iloc[-12:] if len(close) >= 12 else close
    rng = float(recent.max() - recent.min()) if len(recent) else None
    recent_range_atr = (rng / atr) if rng is not None and atr and atr > 0 else None
    dist_mean = None
    if ma_slow is not None and atr and atr > 0:
        dist_mean = (float(close.iloc[-1]) - ma_slow) / atr
    atr_pct = atr_percentile(ind["atr"]) if "atr" in ind.columns else None
    adx = wilder_adx(ind)
    vol_state = "mid"
    if atr_pct is not None:
        if atr_pct >= 80:
            vol_state = "high"
        elif atr_pct <= 20:
            vol_state = "low"
    regime = classify_regime(adx=adx, ema_slope=ema_slope, ema_sep_atr=ema_sep_atr, atr_pct=atr_pct)
    rsi = float(last["rsi"]) if "rsi" in last and last["rsi"] == last["rsi"] else None
    macd = float(last["macd"]) if "macd" in last and last["macd"] == last["macd"] else None
    trend = float(last["trend"]) if "trend" in last and last["trend"] == last["trend"] else None
    return {
        "atr": atr,
        "atr_percentile": atr_pct,
        "ma_fast": ma_fast,
        "ma_slow": ma_slow,
        "rsi": rsi,
        "macd": macd,
        "trend": trend,
        "volatility": atr,
        "ema_slope": ema_slope,
        "ema_separation_atr": ema_sep_atr,
        "adx": adx,
        "distance_from_mean_atr": dist_mean,
        "recent_range_atr": recent_range_atr,
        "volatility_state": vol_state,
        "regime": regime,
    }


def pre_entry_extension_atr(df: pd.DataFrame, side: str, atr: float | None, bars: int = 12) -> float | None:
    """Signed move over ``bars`` in ATR, positive when already extended in the signal direction."""
    if atr is None or atr <= 0 or len(df) < bars + 1:
        return None
    now = float(df["close"].iloc[-1])
    then = float(df["close"].iloc[-1 - bars])
    raw = (now - then) / atr
    if (side or "").upper().strip() == "SELL":
        raw = -raw
    return float(raw)


def distance_from_swing_atr(df: pd.DataFrame, side: str, atr: float | None, bars: int = 20) -> float | None:
    if atr is None or atr <= 0 or len(df) < 3:
        return None
    window = df.iloc[-min(bars, len(df)) :]
    px = float(df["close"].iloc[-1])
    d = (side or "").upper().strip()
    if d == "BUY":
        swing = float(window["low"].min())
        return (px - swing) / atr
    swing = float(window["high"].max())
    return (swing - px) / atr
