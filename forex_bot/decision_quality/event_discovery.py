"""Event / opportunity discovery primitives. Research-only. O(N) / O(N h)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.profit_protection import pip_size
from forex_bot.trading import SPREADS, simulated_half_spread

# ---- Frozen from prior feature study. Do not retune. ----
SPLIT_T50 = pd.Timestamp("2026-03-03 12:15:00")
SPLIT_T75 = pd.Timestamp("2026-06-02 05:05:00")

# TRAIN quintile edges for pos_in_range_24 from quant_feature_target_discovery.
POS_RANGE_24_EDGES = (0.0, 0.1911764703070358, 0.4052287579845441, 0.6287128709758706, 0.8314606732231985, 1.0)
POS_RANGE_Q1 = POS_RANGE_24_EDGES[1]
POS_RANGE_Q5 = POS_RANGE_24_EDGES[4]

HORIZONS_MIN = (15, 30, 60, 120, 240, 480)
COST_MULTS = (0.5, 1.0, 1.5, 2.0, 3.0)
ATR_PATH_MULTS = (0.25, 0.50, 1.00)
BREAKOUT_LOOKBACKS = (12, 24, 48)
USD_QUOTE = ("EUR_USD", "GBP_USD", "AUD_USD")
USD_BASE = ("USD_JPY", "USD_CAD", "USD_CHF")
BOOT_SEED = 42
BOOT_REPS = 200

# Predeclared combinations — fixed before results.
COMBOS = (
    "range_bottom_and_lower_reject",
    "range_top_and_upper_reject",
    "range_bottom_and_usd_div",
    "breakout_up_24_and_vol_expand",
    "impulse_bull_and_usd_agree",
)


def assign_split(times: pd.Series) -> np.ndarray:
    t = pd.to_datetime(times)
    return np.where(t <= SPLIT_T50, "train", np.where(t <= SPLIT_T75, "valid", "discovery_test"))


def half_spread_pips(symbol: str) -> float:
    pip = pip_size(symbol)
    return float(simulated_half_spread(symbol)) / pip if pip else 0.0


def enter_true(flag: np.ndarray) -> np.ndarray:
    """True on the first bar of a True run."""
    f = np.asarray(flag, dtype=bool)
    prev = np.empty_like(f)
    prev[0] = False
    prev[1:] = f[:-1]
    return f & ~prev


def enter_true_grouped(flag: np.ndarray, group: np.ndarray) -> np.ndarray:
    """enter_true that resets at each new group (symbol)."""
    f = np.asarray(flag, dtype=bool)
    g = np.asarray(group)
    prev = np.empty_like(f)
    prev[0] = False
    prev[1:] = f[:-1]
    same = np.empty(len(f), dtype=bool)
    same[0] = False
    same[1:] = g[1:] == g[:-1]
    prev = prev & same
    return f & ~prev


def prior_rolling_extrema(values: np.ndarray, window: int, how: str = "max") -> np.ndarray:
    """Rolling max/min of the previous `window` bars. Current bar is excluded."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    out = np.full(n, np.nan)
    if n <= window:
        return out
    lagged = np.concatenate([np.full(1, np.nan), x[:-1]])
    # rolling over lagged so window at i uses x[i-window:i]
    if how == "max":
        rolled = pd.Series(lagged).rolling(window, min_periods=window).max().to_numpy()
    else:
        rolled = pd.Series(lagged).rolling(window, min_periods=window).min().to_numpy()
    return rolled


def train_quantile_edges(values: np.ndarray, qs=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 20:
        return np.array([-np.inf, np.inf])
    return np.quantile(x, qs)


def _future_windows(arr: np.ndarray, h: int) -> np.ndarray:
    """windows[i] = arr[i+1 : i+1+h], nan-padded. Shape (n, h)."""
    a = np.asarray(arr, dtype=float)
    n = len(a)
    pad = np.full(h, np.nan)
    ext = np.concatenate([a[1:], pad])
    return np.lib.stride_tricks.sliding_window_view(ext, h)[:n]


def future_path_block(close: np.ndarray, high: np.ndarray, low: np.ndarray, h: int) -> dict[str, np.ndarray]:
    wh = _future_windows(high, h)
    wl = _future_windows(low, h)
    wc = _future_windows(close, h)
    finite_h = np.isfinite(wh)
    finite_l = np.isfinite(wl)
    fwd_high = np.max(np.where(finite_h, wh, -np.inf), axis=1)
    fwd_low = np.min(np.where(finite_l, wl, np.inf), axis=1)
    fwd_high = np.where(finite_h.any(axis=1), fwd_high, np.nan)
    fwd_low = np.where(finite_l.any(axis=1), fwd_low, np.nan)
    fwd_close = wc[:, -1]
    with np.errstate(all="ignore"):
        argmax_h = np.argmax(np.where(finite_h, wh, -np.inf), axis=1)
        argmin_l = np.argmin(np.where(finite_l, wl, np.inf), axis=1)
    complete = np.isfinite(fwd_close)
    argmax_h = np.where(complete, argmax_h, -1)
    argmin_l = np.where(complete, argmin_l, -1)
    return {
        "fwd_close": fwd_close,
        "fwd_high": fwd_high,
        "fwd_low": fwd_low,
        "bars_to_high": argmax_h + 1,
        "bars_to_low": argmin_l + 1,
        "complete": complete,
        "wh": wh,
        "wl": wl,
    }


def path_order(close: np.ndarray, wh: np.ndarray, wl: np.ndarray, thresh: np.ndarray) -> np.ndarray:
    """UP_FIRST / DOWN_FIRST / NEITHER / AMBIGUOUS. thresh in price units."""
    c = close[:, None]
    t = np.asarray(thresh, dtype=float)[:, None]
    up = wh >= (c + t)
    dn = wl <= (c - t)
    have_up = up.any(axis=1)
    have_dn = dn.any(axis=1)
    first_up = np.where(have_up, up.argmax(axis=1), 10**9)
    first_dn = np.where(have_dn, dn.argmax(axis=1), 10**9)
    out = np.array(["NEITHER"] * len(close), dtype=object)
    only_up = have_up & ~have_dn
    only_dn = have_dn & ~have_up
    both = have_up & have_dn
    out[only_up] = "UP_FIRST"
    out[only_dn] = "DOWN_FIRST"
    out[both & (first_up < first_dn)] = "UP_FIRST"
    out[both & (first_dn < first_up)] = "DOWN_FIRST"
    out[both & (first_up == first_dn)] = "AMBIGUOUS"
    # incomplete rows stay NEITHER if no touch
    return out


def event_bootstrap_mean(values: np.ndarray, seed: int = BOOT_SEED, reps: int = BOOT_REPS) -> dict:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 10:
        return {"n": int(len(x)), "mean": float(np.mean(x)) if len(x) else None, "ci05": None, "ci95": None, "seed": seed}
    rng = np.random.default_rng(seed)
    means = [float(np.mean(rng.choice(x, size=len(x), replace=True))) for _ in range(reps)]
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "ci05": float(np.quantile(means, 0.05)),
        "ci95": float(np.quantile(means, 0.95)),
        "seed": int(seed),
        "reps": int(reps),
    }


def usd_direction_return(symbol: str, ret: np.ndarray) -> np.ndarray:
    """Positive when USD strengthens vs the other currency."""
    r = np.asarray(ret, dtype=float)
    if symbol in USD_QUOTE:
        return -r
    return r


def other_pairs_usd_context(times: pd.Series, symbols: pd.Series, ret: pd.Series) -> pd.DataFrame:
    """Contemporaneous USD context from OTHER pairs only. Completed bars, no future."""
    panel = pd.DataFrame({"time": pd.to_datetime(times), "symbol": symbols.to_numpy(), "ret": ret.to_numpy()})
    wide = panel.pivot_table(index="time", columns="symbol", values="ret", aggfunc="last")
    usd = wide.copy()
    for s in USD_QUOTE:
        if s in usd.columns:
            usd[s] = -wide[s]
    rows = []
    for s in usd.columns:
        others = usd.drop(columns=[s])
        med = others.median(axis=1)
        own = usd[s]
        agr = (np.sign(others).eq(np.sign(own), axis=0)).mean(axis=1)
        disp = others.std(axis=1)
        tmp = pd.DataFrame(
            {
                "time": med.index,
                "symbol": s,
                "usd_own": own.to_numpy(),
                "usd_others_med": med.to_numpy(),
                "usd_others_agree": agr.to_numpy(),
                "usd_others_disp": disp.to_numpy(),
            }
        )
        rows.append(tmp)
    return pd.concat(rows, ignore_index=True)


def session_transition(prev: str, cur: str) -> str:
    if prev == "asia" and cur == "london":
        return "asia_to_london"
    if prev == "london" and cur == "london_ny_overlap":
        return "london_to_overlap"
    if prev == "london_ny_overlap" and cur == "late_new_york":
        return "overlap_to_late_ny"
    return ""
