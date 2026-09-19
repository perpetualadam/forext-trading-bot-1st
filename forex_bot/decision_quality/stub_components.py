"""Research-only SMA-state / momentum-sign components. Does not change production."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.indicators import compute_indicators
from forex_bot.profit_protection import pip_size, unrealized_profit_pips

EPS = 1e-6
MOM_THR = 0.0001
HORIZONS_MIN = (5, 15, 30, 60, 120, 240)
AGE_BUCKETS = (
    ("0", lambda a: a == 0),
    ("1", lambda a: a == 1),
    ("2-3", lambda a: (a >= 2) & (a <= 3)),
    ("4-6", lambda a: (a >= 4) & (a <= 6)),
    ("7-12", lambda a: (a >= 7) & (a <= 12)),
    ("13-24", lambda a: (a >= 13) & (a <= 24)),
    ("25+", lambda a: a >= 25),
)
AGE_BUCKET_NAMES = tuple(name for name, _ in AGE_BUCKETS)


def sma_state(ma_fast: np.ndarray, ma_slow: np.ndarray, eps: float = EPS) -> np.ndarray:
    """+1 BUY, -1 SELL, 0 flat. Same comparison as ``_quant_stub_vote``."""
    fast = np.asarray(ma_fast, dtype=float)
    slow = np.asarray(ma_slow, dtype=float)
    out = np.zeros(len(fast), dtype=np.int8)
    valid = np.isfinite(fast) & np.isfinite(slow)
    out[valid & (fast > slow + eps)] = 1
    out[valid & (fast < slow - eps)] = -1
    return out


def bars_since_last_cross(state: np.ndarray) -> np.ndarray:
    """0 on the bar a nonzero state first appears or flips; then 1, 2, ... NaN while flat."""
    s = np.asarray(state, dtype=np.int16)
    n = len(s)
    age = np.full(n, np.nan)
    prev = 0
    cur = np.nan
    for i, v in enumerate(s):
        if v == 0:
            prev = 0
            cur = np.nan
            continue
        if v != prev:
            cur = 0.0
            prev = int(v)
        else:
            cur = cur + 1.0
        age[i] = cur
    return age


def is_crossover(state: np.ndarray) -> np.ndarray:
    age = bars_since_last_cross(state)
    return np.isfinite(age) & (age == 0)


def age_bucket(age: np.ndarray) -> np.ndarray:
    out = np.array([""] * len(age), dtype=object)
    finite = np.isfinite(age)
    a = np.where(finite, age, -1)
    for name, pred in AGE_BUCKETS:
        out[finite & pred(a)] = name
    return out


def episode_ids(state: np.ndarray) -> np.ndarray:
    """Integer id per contiguous nonzero SMA state; -1 while flat."""
    s = np.asarray(state, dtype=np.int16)
    ids = np.full(len(s), -1, dtype=np.int32)
    eid = -1
    prev = 0
    for i, v in enumerate(s):
        if v == 0:
            prev = 0
            continue
        if v != prev:
            eid += 1
            prev = int(v)
        ids[i] = eid
    return ids


def momentum_sign(ret_1: np.ndarray) -> np.ndarray:
    """+1 up, -1 down, 0 flat/nan."""
    r = np.asarray(ret_1, dtype=float)
    out = np.zeros(len(r), dtype=np.int8)
    out[np.isfinite(r) & (r > 0)] = 1
    out[np.isfinite(r) & (r < 0)] = -1
    return out


def magnitude_ok(ret_1: np.ndarray, thr: float = MOM_THR) -> np.ndarray:
    r = np.asarray(ret_1, dtype=float)
    return np.isfinite(r) & (np.abs(r) > thr)


def atr_ok(atr: np.ndarray) -> np.ndarray:
    a = np.asarray(atr, dtype=float)
    return np.isfinite(a) & (a > 0)


def current_stub_allow(state: np.ndarray, ret_1: np.ndarray, atr: np.ndarray) -> np.ndarray:
    """Exact current stub: SMA side exists AND |ret| > 0.0001 AND ATR > 0."""
    return (np.asarray(state) != 0) & magnitude_ok(ret_1) & atr_ok(atr)


def first_qualifying_in_episode(episode: np.ndarray, qualify: np.ndarray) -> np.ndarray:
    """True on the first qualifying bar of each episode (H)."""
    q = np.asarray(qualify, dtype=bool)
    ep = np.asarray(episode)
    out = np.zeros(len(q), dtype=bool)
    seen: set[int] = set()
    for i, (e, ok) in enumerate(zip(ep, q)):
        if ok and e >= 0 and e not in seen:
            out[i] = True
            seen.add(int(e))
    return out


def side_from_state(state_val: int) -> str:
    if state_val > 0:
        return "BUY"
    if state_val < 0:
        return "SELL"
    return ""


def signed_forward_pips(symbol: str, state: np.ndarray, close: np.ndarray, bars_ahead: int) -> np.ndarray:
    """Direction-adjusted mid-to-mid pips. Flat/unavailable → NaN."""
    c = np.asarray(close, dtype=float)
    s = np.asarray(state)
    n = len(c)
    out = np.full(n, np.nan)
    if bars_ahead <= 0:
        return out
    future = np.full(n, np.nan)
    if bars_ahead < n:
        future[: n - bars_ahead] = c[bars_ahead:]
    pip = pip_size(symbol)
    if pip <= 0:
        return out
    buy = s > 0
    sell = s < 0
    have = np.isfinite(c) & np.isfinite(future)
    out[buy & have] = (future[buy & have] - c[buy & have]) / pip
    out[sell & have] = (c[sell & have] - future[sell & have]) / pip
    return out


def signed_forward_atr(state: np.ndarray, close: np.ndarray, atr: np.ndarray, bars_ahead: int) -> np.ndarray:
    c = np.asarray(close, dtype=float)
    a = np.asarray(atr, dtype=float)
    s = np.asarray(state)
    n = len(c)
    out = np.full(n, np.nan)
    future = np.full(n, np.nan)
    if 0 < bars_ahead < n:
        future[: n - bars_ahead] = c[bars_ahead:]
    have = np.isfinite(c) & np.isfinite(future) & np.isfinite(a) & (a > 0)
    raw = np.full(n, np.nan)
    raw[have] = (future[have] - c[have]) / a[have]
    out[s > 0] = raw[s > 0]
    out[s < 0] = -raw[s < 0]
    return out


def build_component_frame(df: pd.DataFrame, symbol: str, lookback: int) -> pd.DataFrame:
    """One row per M5 bar after indicator warmup. Research-only."""
    ind = compute_indicators(df.reset_index(drop=True), lookback=lookback)
    close = ind["close"].to_numpy(dtype=float)
    ma_fast = ind["ma_fast"].to_numpy(dtype=float)
    ma_slow = ind["ma_slow"].to_numpy(dtype=float)
    atr = ind["atr"].to_numpy(dtype=float)
    ret_1 = pd.Series(close).pct_change().to_numpy(dtype=float)
    state = sma_state(ma_fast, ma_slow)
    age = bars_since_last_cross(state)
    ep = episode_ids(state)
    mom = momentum_sign(ret_1)
    mag = magnitude_ok(ret_1)
    allow = current_stub_allow(state, ret_1, atr)
    first_q = first_qualifying_in_episode(ep, allow)
    # Namespace episodes per symbol so pooled nunique is not collapsed.
    ep = np.where(ep >= 0, ep, -1)
    out = pd.DataFrame(
        {
            "time": pd.to_datetime(ind["time"]),
            "symbol": symbol,
            "lookback": lookback,
            "close": close,
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "atr": atr,
            "ret_1": ret_1,
            "state": state,
            "age": age,
            "age_bucket": age_bucket(age),
            "episode": ep,
            "episode_key": np.where(ep >= 0, np.array([f"{symbol}_{int(v)}" for v in ep], dtype=object), ""),
            "is_cross": is_crossover(state),
            "mom_sign": mom,
            "mag_ok": mag,
            "atr_ok": atr_ok(atr),
            "agree": (state != 0) & (mom != 0) & (state == mom),
            "disagree": (state != 0) & (mom != 0) & (state != mom),
            "stub_allow": allow,
            "first_qual": first_q,
            "repeat_qual": allow & ~first_q,
        }
    )
    for minutes in HORIZONS_MIN:
        steps = max(1, minutes // 5)
        out[f"fwd_{minutes}m_pips"] = signed_forward_pips(symbol, state, close, steps)
        out[f"fwd_{minutes}m_atr"] = signed_forward_atr(state, close, atr, steps)
        inv = -state
        out[f"inv_{minutes}m_pips"] = signed_forward_pips(symbol, inv, close, steps)
    return out


def vote_matches_row(row: pd.Series) -> bool:
    """Sanity: production stub allow/side matches component flags."""
    vote = _quant_stub_vote(
        {
            "price": float(row["close"]),
            "ma_fast": float(row["ma_fast"]) if np.isfinite(row["ma_fast"]) else float(row["close"]),
            "ma_slow": float(row["ma_slow"]) if np.isfinite(row["ma_slow"]) else float(row["close"]),
            "returns": float(row["ret_1"]) if np.isfinite(row["ret_1"]) else 0.0,
            "atr": float(row["atr"]) if np.isfinite(row["atr"]) else 0.0,
        }
    )
    if row["state"] == 0:
        return vote["direction"] is None and vote["allow"] is False
    expected = "BUY" if row["state"] > 0 else "SELL"
    return vote["direction"] == expected and bool(vote["allow"]) == bool(row["stub_allow"])


def chrono_masks(times: pd.Series) -> dict[str, np.ndarray]:
    """Global 50/25/25 by timestamp (same cut times for all symbols)."""
    t = pd.to_datetime(times)
    valid = t.notna()
    qs = t[valid].quantile([0.50, 0.75])
    t50, t75 = qs.iloc[0], qs.iloc[1]
    return {
        "train": (t <= t50).to_numpy(),
        "valid": ((t > t50) & (t <= t75)).to_numpy(),
        "test": (t > t75).to_numpy(),
        "cut_50": t50,
        "cut_75": t75,
    }


def fwd_summary(pips: np.ndarray) -> dict:
    x = np.asarray(pips, dtype=float)
    x = x[np.isfinite(x)]
    n = int(len(x))
    if n == 0:
        return {"n": 0, "mean": None, "median": None, "pct_pos": None}
    return {
        "n": n,
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "pct_pos": float(np.mean(x > 0)),
    }


def summarize_group(frame: pd.DataFrame, mask: np.ndarray, horizons: tuple[int, ...] = HORIZONS_MIN) -> dict:
    sub = frame.loc[mask]
    if sub.empty:
        episodes = 0
    elif "episode_key" in sub.columns:
        keys = sub["episode_key"].astype(str)
        episodes = int(keys[keys.str.len() > 0].nunique())
    else:
        episodes = int(sub.loc[sub["episode"] >= 0, "episode"].nunique())
    out: dict = {
        "raw_bar_n": int(mask.sum()),
        "event_state_n": episodes,
    }
    for minutes in horizons:
        col = f"fwd_{minutes}m_pips"
        out[f"{minutes}m"] = fwd_summary(sub[col].to_numpy() if col in sub else np.array([]))
    return out
