"""Quant V2 Experiment A primitives: historical spread and activity. Research-only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.decision_quality.event_discovery import assign_split, enter_true_grouped
from forex_bot.profit_protection import pip_size
from forex_bot.trading import simulated_half_spread

# Frozen V1 event edges — do not retune.
POS_RANGE_Q1 = 0.1911764703070358
POS_RANGE_Q5 = 0.8314606732231985
SIGNED_BODY_Q1 = -0.5223880569725391
SIGNED_BODY_Q5 = 0.5316455664795035
ATR_PCTILE_Q5 = 0.86

QUINTILE_QS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def modeled_half_spread_price(symbol: str) -> float:
    """V1 simulated entry cost in price units (half-spread)."""
    return float(simulated_half_spread(symbol))


def modeled_half_spread_pips(symbol: str) -> float:
    pip = pip_size(symbol)
    return modeled_half_spread_price(symbol) / pip if pip else 0.0


def full_close_spread(ask_close: np.ndarray, bid_close: np.ndarray) -> np.ndarray:
    """ask_close - bid_close at the same completed bar. Not a tick path."""
    return np.asarray(ask_close, dtype=float) - np.asarray(bid_close, dtype=float)


def half_close_spread(ask_close: np.ndarray, bid_close: np.ndarray) -> np.ndarray:
    return full_close_spread(ask_close, bid_close) / 2.0


def to_pips(price_delta: np.ndarray, symbol: str) -> np.ndarray:
    pip = pip_size(symbol)
    return np.asarray(price_delta, dtype=float) / pip if pip else np.full(len(price_delta), np.nan)


def flag_invalid_spread(full_spread: np.ndarray) -> dict[str, np.ndarray]:
    """Report impossible values. Does not overwrite the series."""
    x = np.asarray(full_spread, dtype=float)
    return {
        "missing": ~np.isfinite(x),
        "zero": np.isfinite(x) & (x == 0.0),
        "negative": np.isfinite(x) & (x < 0.0),
    }


def train_quantile_edges(values: np.ndarray, qs=QUINTILE_QS) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 20:
        return np.array([-np.inf, np.inf])
    return np.quantile(x, qs)


def assign_quintile(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """1..5 using frozen edges. NaN stays 0."""
    x = np.asarray(values, dtype=float)
    e = np.asarray(edges, dtype=float)
    out = np.zeros(len(x), dtype=int)
    if len(e) < 6:
        return out
    finite = np.isfinite(x)
    # clip into bins; last edge inclusive
    bins = np.digitize(x, e[1:-1], right=False) + 1
    bins = np.clip(bins, 1, 5)
    out[finite] = bins[finite]
    return out


def lagged_rolling_median(values: np.ndarray, window: int, group: np.ndarray) -> np.ndarray:
    """Median of the previous `window` values; current bar excluded. Resets per group."""
    s = pd.Series(np.asarray(values, dtype=float))
    g = pd.Series(group)
    lagged = s.groupby(g, sort=False).shift(1)
    return lagged.groupby(g, sort=False).transform(lambda x: x.rolling(window, min_periods=window).median()).to_numpy()


def two_sided_hurdle(mfe_up: np.ndarray, mfe_dn: np.ndarray, cost: np.ndarray) -> np.ndarray:
    """UP_ONLY / DOWN_ONLY / BOTH / NEITHER using contemporaneous cost (same units)."""
    up = np.asarray(mfe_up, dtype=float) >= np.asarray(cost, dtype=float)
    dn = np.asarray(mfe_dn, dtype=float) >= np.asarray(cost, dtype=float)
    out = np.array(["NEITHER"] * len(up), dtype=object)
    out[up & ~dn] = "UP_ONLY"
    out[~up & dn] = "DOWN_ONLY"
    out[up & dn] = "BOTH"
    bad = ~np.isfinite(mfe_up) | ~np.isfinite(mfe_dn) | ~np.isfinite(cost) | (np.asarray(cost, dtype=float) <= 0)
    out[bad] = "INVALID"
    return out


def apply_frozen_edges(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Same assign_quintile — later partitions must use TRAIN edges unchanged."""
    return assign_quintile(values, edges)
