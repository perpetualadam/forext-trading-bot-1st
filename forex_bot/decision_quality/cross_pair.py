"""Quant V2 Experiment B primitives: cross-pair factor/residual. Research-only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.decision_quality.event_discovery import USD_BASE, USD_QUOTE

RETURN_BARS = (1, 3, 6, 12)  # 5m, 15m, 30m, 60m — predeclared
PRIMARY_BARS = 6  # 30m USD-oriented return for the common factor
LAGS = (1, 2, 3)


def is_usd_quote(symbol: str) -> bool:
    return symbol in USD_QUOTE


def instrument_to_usd(symbol: str, instrument_ret: np.ndarray) -> np.ndarray:
    """Positive = USD strengthens. EUR/GBP/AUD flip; JPY/CAD/CHF keep sign."""
    r = np.asarray(instrument_ret, dtype=float)
    return -r if is_usd_quote(symbol) else r


def usd_to_instrument(symbol: str, usd_ret: np.ndarray) -> np.ndarray:
    r = np.asarray(usd_ret, dtype=float)
    return -r if is_usd_quote(symbol) else r


def reversal_instrument_side(symbol: str, residual_usd: float) -> str:
    """If residual_usd > 0 (idiosyncratic USD strength), reversal is instrument BUY for quote pairs."""
    if not np.isfinite(residual_usd) or residual_usd == 0:
        return "NONE"
    want_usd_down = residual_usd > 0  # fade idiosyncratic USD strength
    if is_usd_quote(symbol):
        return "BUY" if want_usd_down else "SELL"
    return "SELL" if want_usd_down else "BUY"


def synchronized_panel(frames: dict[str, pd.DataFrame], value_col: str) -> pd.DataFrame:
    """Inner-join on time. No forward-fill."""
    series = []
    for sym, df in frames.items():
        s = df.set_index(pd.to_datetime(df["time"]))[value_col].rename(sym)
        series.append(s)
    return pd.concat(series, axis=1, join="inner").sort_index()


def leave_one_out_median(wide: pd.DataFrame) -> pd.DataFrame:
    """Each column is the median of the other columns. Target excluded."""
    out = pd.DataFrame(index=wide.index, columns=wide.columns, dtype=float)
    for col in wide.columns:
        out[col] = wide.drop(columns=[col]).median(axis=1)
    return out


def train_pca1(train_x: np.ndarray) -> dict:
    """First PC of TRAIN matrix (n, k). Freeze mean and loadings. Sign: +corr with row mean."""
    x = np.asarray(train_x, dtype=float)
    ok = np.isfinite(x).all(axis=1)
    x = x[ok]
    if len(x) < 20:
        raise ValueError("insufficient TRAIN rows for PCA")
    mean = x.mean(axis=0)
    xc = x - mean
    _, _, vt = np.linalg.svd(xc, full_matrices=False)
    w = vt[0].copy()
    scores = xc @ w
    if np.corrcoef(scores, xc.mean(axis=1))[0, 1] < 0:
        w = -w
    return {"mean": mean, "weights": w}


def apply_pca1(x: np.ndarray, fit: dict) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return (x - fit["mean"]) @ fit["weights"]


def train_betas(y: np.ndarray, factor: np.ndarray) -> float:
    """OLS slope of y on factor, TRAIN finite pairs only. No intercept beyond centered PCA."""
    m = np.isfinite(y) & np.isfinite(factor)
    if m.sum() < 20:
        return 0.0
    f = factor[m]
    yy = y[m]
    var = np.var(f)
    if var <= 0:
        return 0.0
    return float(np.cov(yy, f, ddof=0)[0, 1] / var)


def residual(y: np.ndarray, factor: np.ndarray, beta: float) -> np.ndarray:
    return np.asarray(y, dtype=float) - float(beta) * np.asarray(factor, dtype=float)


def cross_section_std(wide: pd.DataFrame) -> pd.Series:
    return wide.std(axis=1, ddof=0)


def cross_section_iqr(wide: pd.DataFrame) -> pd.Series:
    return wide.quantile(0.75, axis=1) - wide.quantile(0.25, axis=1)


def usd_ranks(wide: pd.DataFrame) -> pd.DataFrame:
    """1 = strongest USD-oriented return, k = weakest. Ties: average rank then floor via method first."""
    return wide.rank(axis=1, ascending=False, method="first")
