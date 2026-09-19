"""Leakage-safe vectorized feature/target builders. Research-only. O(N)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from forex_bot.csv_ohlcv import load_ohlcv_csv
from forex_bot.decision_quality.history_cache import classify_gap, default_historical_dir
from forex_bot.decision_quality.sessions import SESSION_BUCKETS, classify_session
from forex_bot.decision_quality.stub_components import bars_since_last_cross, sma_state
from forex_bot.indicators import _rsi, _true_range
from forex_bot.profit_protection import pip_size
from forex_bot.symbols import DEFAULT_FOREX_SYMBOLS
from forex_bot.trading import simulated_half_spread

SYMBOLS = tuple(DEFAULT_FOREX_SYMBOLS)
HORIZONS_MIN = (5, 15, 30, 60, 120, 240)
LONDON = ZoneInfo("Europe/London")
EPS = 1e-12

# Predeclared small MA set — not searched.
SMA_FAST = 5
SMA_MID = 20
SMA_SLOW = 50
EMA_FAST = 12
EMA_SLOW = 26
ATR_N = 14
RANGE_SHORT = 24
RANGE_LONG = 72
RV_SHORT = 12
RV_LONG = 48

FEATURE_FAMILIES = {
    "price_action": (
        "ret_1",
        "ret_2",
        "ret_3",
        "ret_6",
        "ret_12",
        "ret_24",
        "ret_1_atr",
        "ret_6_atr",
        "ret_12_atr",
        "ret_24_atr",
        "ret_1_abs",
        "ret_1_sign",
    ),
    "trend": (
        "sma5_20_diff_atr",
        "sma20_50_diff_atr",
        "sma5_slope_atr",
        "sma20_slope_atr",
        "ema12_26_diff_atr",
        "sma_state",
        "bars_since_sma_cross",
    ),
    "momentum": ("dret_1", "rsi14"),
    "volatility": (
        "atr14",
        "atr_over_price",
        "rv_short",
        "rv_long",
        "rv_ratio",
        "range_atr",
        "tr_atr",
        "atr_pctile",
    ),
    "candle": ("body_atr", "signed_body_atr", "upper_wick_atr", "lower_wick_atr", "close_loc"),
    "extension": ("dist_sma20_atr", "dist_sma50_atr", "dist_rollmean24_atr", "pos_in_range_24"),
    "breakout": (
        "dist_high_24_atr",
        "dist_low_24_atr",
        "dist_high_72_atr",
        "dist_low_72_atr",
        "new_high_24",
        "new_low_24",
    ),
    "htf": ("h1_ret", "h4_ret", "h1_slope_atr", "h4_slope_atr", "h1_state", "m15_ret", "m5_vs_h1"),
    "session_regime": ("hour_sin", "hour_cos", "london_hour_sin", "london_hour_cos", "adx14"),
}

ALL_FEATURES = tuple(c for cols in FEATURE_FAMILIES.values() for c in cols)
SIGNED_FEATURES = (
    "ret_1",
    "ret_6",
    "ret_12",
    "ret_24",
    "ret_1_atr",
    "ret_6_atr",
    "sma5_20_diff_atr",
    "sma5_slope_atr",
    "ema12_26_diff_atr",
    "dist_sma20_atr",
    "signed_body_atr",
    "h1_ret",
    "h1_state",
    "m5_vs_h1",
    "sma_state",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_symbol(symbol: str, data_dir: Path | None = None) -> dict:
    path = (data_dir or default_historical_dir()) / f"{symbol}_M5.csv"
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    df = load_ohlcv_csv(path)
    t = pd.to_datetime(df["time"])
    dups = int(t.duplicated().sum())
    mono = bool(t.is_monotonic_increasing)
    gaps = {"none": 0, "expected_weekend": 0, "unexpected": 0}
    times = [x.to_pydatetime() for x in t]
    for a, b in zip(times, times[1:]):
        gaps[classify_gap(a, b)] += 1
    incomplete = 0
    if "complete" in raw.columns:
        flag = raw["complete"].astype(str).str.lower()
        incomplete = int(flag.isin(("0", "false", "no", "f", "incomplete")).sum())
    return {
        "symbol": symbol,
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "rows": int(len(df)),
        "earliest": t.iloc[0].isoformat() if len(df) else None,
        "latest": t.iloc[-1].isoformat() if len(df) else None,
        "duplicates": dups,
        "monotonic": mono,
        "incomplete_flagged": incomplete,
        "gaps": gaps,
        "has_bid": "bid_close" in raw.columns,
        "has_ask": "ask_close" in raw.columns,
    }


def _wilder_adx_series(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = _true_range(high, low, close)
    alpha = 1.0 / period
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100.0 * (plus_dm.ewm(alpha=alpha, adjust=False).mean() / (atr + EPS))
    minus_di = 100.0 * (minus_dm.ewm(alpha=alpha, adjust=False).mean() / (atr + EPS))
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + EPS)
    return dx.ewm(alpha=alpha, adjust=False).mean()


def _closed_htf(m5: pd.DataFrame, rule: str, minutes: int) -> pd.DataFrame:
    idx = m5.set_index(pd.to_datetime(m5["time"]))
    ohlc = idx.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna(how="any")
    if ohlc.empty:
        return pd.DataFrame(columns=["end", "htf_close", "htf_open", "htf_ret", "htf_slope", "htf_state"])
    close = ohlc["close"].astype(float)
    out = pd.DataFrame(
        {
            "end": ohlc.index + pd.Timedelta(minutes=minutes),
            "htf_close": close.to_numpy(),
            "htf_open": ohlc["open"].to_numpy(),
            "htf_ret": close.pct_change().to_numpy(),
            "htf_slope": (close - close.shift(3)).to_numpy(),
            "htf_state": np.sign((close - ohlc["open"].astype(float)).to_numpy()),
        }
    )
    return out.sort_values("end").reset_index(drop=True)


def _join_closed_htf(m5: pd.DataFrame, htf: pd.DataFrame, prefix: str) -> pd.DataFrame:
    left = pd.DataFrame({"time": pd.to_datetime(m5["time"])})
    empty_cols = ("close", "ret", "slope", "state")
    if htf.empty:
        for col in empty_cols:
            left[f"{prefix}_{col}"] = np.nan
        return left
    right = htf.rename(
        columns={
            "htf_close": f"{prefix}_close",
            "htf_ret": f"{prefix}_ret",
            "htf_slope": f"{prefix}_slope",
            "htf_state": f"{prefix}_state",
        }
    )
    merged = pd.merge_asof(
        left.sort_values("time"),
        right[["end", f"{prefix}_close", f"{prefix}_ret", f"{prefix}_slope", f"{prefix}_state"]],
        left_on="time",
        right_on="end",
        direction="backward",
    )
    return merged


def build_symbol_frame(symbol: str, data_dir: Path | None = None) -> pd.DataFrame:
    """One row per completed M5 bar. Features use data through t only. Targets use t+h."""
    path = (data_dir or default_historical_dir()) / f"{symbol}_M5.csv"
    df = load_ohlcv_csv(path).reset_index(drop=True)
    n = len(df)
    close = df["close"].astype(float)
    opn = df["open"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    pip = pip_size(symbol)
    atr = _true_range(high, low, close).rolling(ATR_N).mean()
    tr = _true_range(high, low, close)
    sma5 = close.rolling(SMA_FAST).mean()
    sma20 = close.rolling(SMA_MID).mean()
    sma50 = close.rolling(SMA_SLOW).mean()
    ema12 = close.ewm(span=EMA_FAST, adjust=False).mean()
    ema26 = close.ewm(span=EMA_SLOW, adjust=False).mean()
    ret1 = close.pct_change(1)
    out = pd.DataFrame(
        {
            "time": pd.to_datetime(df["time"]),
            "symbol": symbol,
            "open": opn,
            "high": high,
            "low": low,
            "close": close,
            "ret_1": ret1,
            "ret_2": close.pct_change(2),
            "ret_3": close.pct_change(3),
            "ret_6": close.pct_change(6),
            "ret_12": close.pct_change(12),
            "ret_24": close.pct_change(24),
            "ret_1_atr": (close - close.shift(1)) / (atr + EPS),
            "ret_6_atr": (close - close.shift(6)) / (atr + EPS),
            "ret_12_atr": (close - close.shift(12)) / (atr + EPS),
            "ret_24_atr": (close - close.shift(24)) / (atr + EPS),
            "ret_1_abs": ret1.abs(),
            "ret_1_sign": np.sign(ret1.to_numpy()),
            "sma5_20_diff_atr": (sma5 - sma20) / (atr + EPS),
            "sma20_50_diff_atr": (sma20 - sma50) / (atr + EPS),
            "sma5_slope_atr": (sma5 - sma5.shift(6)) / (atr + EPS),
            "sma20_slope_atr": (sma20 - sma20.shift(6)) / (atr + EPS),
            "ema12_26_diff_atr": (ema12 - ema26) / (atr + EPS),
            "sma_state": sma_state(sma5.to_numpy(), sma20.to_numpy()),
            "bars_since_sma_cross": bars_since_last_cross(sma_state(sma5.to_numpy(), sma20.to_numpy())),
            "dret_1": ret1 - ret1.shift(1),
            "rsi14": _rsi(close, 14),
            "atr14": atr,
            "atr_over_price": atr / (close.abs() + EPS),
            "rv_short": ret1.rolling(RV_SHORT).std(),
            "rv_long": ret1.rolling(RV_LONG).std(),
            "range_atr": (high - low) / (atr + EPS),
            "tr_atr": tr / (atr + EPS),
            "atr_pctile": atr.rolling(100).rank(pct=True),
            "body_atr": (close - opn).abs() / (atr + EPS),
            "signed_body_atr": (close - opn) / (atr + EPS),
            "upper_wick_atr": (high - np.maximum(close, opn)) / (atr + EPS),
            "lower_wick_atr": (np.minimum(close, opn) - low) / (atr + EPS),
            "close_loc": (close - low) / (high - low + EPS),
            "dist_sma20_atr": (close - sma20) / (atr + EPS),
            "dist_sma50_atr": (close - sma50) / (atr + EPS),
            "dist_rollmean24_atr": (close - close.rolling(RANGE_SHORT).mean()) / (atr + EPS),
            "pos_in_range_24": (close - low.rolling(RANGE_SHORT).min())
            / (high.rolling(RANGE_SHORT).max() - low.rolling(RANGE_SHORT).min() + EPS),
            "dist_high_24_atr": (high.rolling(RANGE_SHORT).max() - close) / (atr + EPS),
            "dist_low_24_atr": (close - low.rolling(RANGE_SHORT).min()) / (atr + EPS),
            "dist_high_72_atr": (high.rolling(RANGE_LONG).max() - close) / (atr + EPS),
            "dist_low_72_atr": (close - low.rolling(RANGE_LONG).min()) / (atr + EPS),
            "new_high_24": (high >= high.rolling(RANGE_SHORT).max().shift(1)).astype(float),
            "new_low_24": (low <= low.rolling(RANGE_SHORT).min().shift(1)).astype(float),
            "adx14": _wilder_adx_series(high, low, close, 14),
        }
    )
    out["rv_ratio"] = out["rv_short"] / (out["rv_long"] + EPS)
    ts = out["time"]
    hour = ts.dt.hour.to_numpy()
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    out["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    aware = ts.dt.tz_localize("UTC") if ts.dt.tz is None else ts.dt.tz_convert("UTC")
    lh = aware.dt.tz_convert("Europe/London").dt.hour.to_numpy()
    out["london_hour_sin"] = np.sin(2 * np.pi * lh / 24.0)
    out["london_hour_cos"] = np.cos(2 * np.pi * lh / 24.0)
    out["hour_utc"] = hour
    out["session"] = [classify_session(x.to_pydatetime()) for x in ts]

    m15 = _join_closed_htf(df, _closed_htf(df, "15min", 15), "m15")
    h1 = _join_closed_htf(df, _closed_htf(df, "1h", 60), "h1")
    h4 = _join_closed_htf(df, _closed_htf(df, "4h", 240), "h4")
    out["m15_ret"] = m15["m15_ret"].to_numpy()
    out["h1_ret"] = h1["h1_ret"].to_numpy()
    out["h4_ret"] = h4["h4_ret"].to_numpy()
    out["h1_slope_atr"] = (h1["h1_slope"] / (atr + EPS)).to_numpy()
    out["h4_slope_atr"] = (h4["h4_slope"] / (atr + EPS)).to_numpy()
    out["h1_state"] = h1["h1_state"].to_numpy()
    out["m5_vs_h1"] = out["ret_6"] * out["h1_state"]

    for minutes in HORIZONS_MIN:
        steps = minutes // 5
        fut = close.shift(-steps)
        out[f"y_px_{minutes}m"] = fut - close
        out[f"y_pct_{minutes}m"] = (fut - close) / (close + EPS)
        out[f"y_pips_{minutes}m"] = (fut - close) / pip
        out[f"y_atr_{minutes}m"] = (fut - close) / (atr + EPS)
        out[f"y_dir_{minutes}m"] = np.sign((fut - close).to_numpy())
    out["spread_pips"] = float(simulated_half_spread(symbol)) / pip * 2.0
    out["half_spread_pips"] = float(simulated_half_spread(symbol)) / pip
    out["bar_i"] = np.arange(n, dtype=np.int32)
    return out


def freeze_splits(times: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp]:
    t = pd.to_datetime(times)
    qs = t.quantile([0.50, 0.75])
    return pd.Timestamp(qs.iloc[0]), pd.Timestamp(qs.iloc[1])


def assign_split(times: pd.Series, t50: pd.Timestamp, t75: pd.Timestamp) -> np.ndarray:
    t = pd.to_datetime(times)
    return np.where(t <= t50, "train", np.where(t <= t75, "valid", "discovery_test"))


def summarize_numeric(s: pd.Series) -> dict:
    x = pd.to_numeric(s, errors="coerce")
    return {
        "count": int(x.notna().sum()),
        "missing": int(x.isna().sum()),
        "mean": float(x.mean()) if x.notna().any() else None,
        "std": float(x.std()) if x.notna().sum() > 1 else None,
        "p01": float(x.quantile(0.01)) if x.notna().any() else None,
        "p10": float(x.quantile(0.10)) if x.notna().any() else None,
        "p25": float(x.quantile(0.25)) if x.notna().any() else None,
        "median": float(x.median()) if x.notna().any() else None,
        "p75": float(x.quantile(0.75)) if x.notna().any() else None,
        "p90": float(x.quantile(0.90)) if x.notna().any() else None,
        "p99": float(x.quantile(0.99)) if x.notna().any() else None,
    }


def train_quintile_edges(train_values: np.ndarray) -> np.ndarray:
    x = np.asarray(train_values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 10:
        return np.array([-np.inf, np.inf])
    return np.quantile(x, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0])


def apply_bins(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    # clip to train support so test extremes land in first/last bin
    inner = edges[1:-1]
    return np.digitize(x, inner, right=True)


def fit_logreg(X: np.ndarray, y: np.ndarray, l2: float = 1.0, steps: int = 250, lr: float = 0.15) -> np.ndarray:
    """L2-regularized logistic regression. TRAIN only. Fixed hyperparameters."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    n, k = X.shape
    w = np.zeros(k + 1)
    for _ in range(steps):
        z = np.clip(X @ w[1:] + w[0], -30, 30)
        p = 1.0 / (1.0 + np.exp(-z))
        err = p - y
        w[1:] -= lr * (X.T @ err / n + l2 * w[1:])
        w[0] -= lr * float(err.mean())
    return w


def predict_logreg(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    z = np.clip(np.asarray(X) @ w[1:] + w[0], -30, 30)
    return 1.0 / (1.0 + np.exp(-z))


def classification_scores(y_true: np.ndarray, p: np.ndarray) -> dict:
    y = np.asarray(y_true, dtype=int)
    pred = (p >= 0.5).astype(int)
    acc = float((pred == y).mean()) if len(y) else None
    pos = y == 1
    neg = y == 0
    tpr = float(pred[pos].mean()) if pos.any() else None
    tnr = float((1 - pred[neg]).mean()) if neg.any() else None
    bal = None if tpr is None or tnr is None else 0.5 * (tpr + tnr)
    pclip = np.clip(p, 1e-6, 1 - 1e-6)
    ll = float(-(y * np.log(pclip) + (1 - y) * np.log(1 - pclip)).mean()) if len(y) else None
    # Mann-Whitney AUC
    auc = None
    if pos.any() and neg.any():
        ranks = pd.Series(p).rank().to_numpy()
        auc = float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * neg.sum()))
    return {"accuracy": acc, "balanced_accuracy": bal, "log_loss": ll, "auc": auc, "n": int(len(y))}


def block_bootstrap_mean(values: np.ndarray, block: int, n_boot: int, seed: int) -> dict:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < block * 2:
        return {"n": int(len(x)), "mean": float(np.mean(x)) if len(x) else None, "ci05": None, "ci95": None}
    n = len(x)
    n_blocks = int(np.ceil(n / block))
    rng = np.random.default_rng(seed)
    starts = np.arange(0, n - block + 1)
    means = []
    for _ in range(n_boot):
        idx = rng.choice(starts, size=n_blocks, replace=True)
        sample = np.concatenate([x[i : i + block] for i in idx])[:n]
        means.append(float(np.mean(sample)))
    return {
        "n": int(n),
        "mean": float(np.mean(x)),
        "ci05": float(np.quantile(means, 0.05)),
        "ci95": float(np.quantile(means, 0.95)),
        "block": int(block),
        "n_boot": int(n_boot),
        "seed": int(seed),
    }
