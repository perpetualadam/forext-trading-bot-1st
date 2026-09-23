"""Research-only EMA trend / retracement / resumption signals.

Does not import bot_loop execution, does not change live voting, and does not
place orders. Frozen SMA baseline reuses ``stub_components`` / ``compute_indicators``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from forex_bot.decision_quality.execution_sim import bar_touches
from forex_bot.decision_quality.history_cache import cache_path, read_canonical_csv
from forex_bot.decision_quality.stub_components import (
    HORIZONS_MIN,
    build_component_frame,
    chrono_masks,
    episode_ids,
    first_qualifying_in_episode,
    fwd_summary,
    signed_forward_atr,
    signed_forward_pips,
    sma_state,
)
from forex_bot.indicators import _true_range, compute_indicators
from forex_bot.profit_protection import pip_size
from forex_bot.symbols import DEFAULT_FOREX_SYMBOLS

RESEARCH_SYMBOLS: tuple[str, ...] = tuple(DEFAULT_FOREX_SYMBOLS)

# Frozen lookbacks from the published SMA-state study (not re-optimized).
FROZEN_LOOKBACK: dict[str, int] = {
    "USD_JPY": 50,
    "EUR_USD": 100,
    "GBP_USD": 100,
    "AUD_USD": 100,
    "USD_CAD": 100,
    "USD_CHF": 100,
}

# Predeclared EMA pairs. Not searched beyond this list.
EMA_PAIRS: tuple[tuple[int, int], ...] = ((20, 50), (50, 100), (50, 200))

# Retracement / resumption thresholds (predeclared).
EXT_ATR = 0.50
ZONE_ATR = 0.25
ZONE_FLOOR_ATR = -0.10
SWING_LOOKBACK = 24
SWING_DEPTH = 0.50

# Research economic geometry: matches live defaults when USE_ATR_STOPS=true,
# SL_ATR_MULT=2, TP_RISK_REWARD=2. Computed here so the study does not read .env.
SL_ATR_MULT = 2.0
TP_R = 2.0

EPS = 1e-6


def indicator_sma_periods(lookback: int, n_bars: int) -> tuple[int, int]:
    """Same period scaling as ``compute_indicators(..., lookback=lookback)``."""
    sn = max(int(n_bars), 20)
    lb = max(20, min(int(lookback), max(sn, 20)))
    cap = min(n_bars - 1, sn - 1)
    ma_fast_n = max(3, min(lb // 10, cap))
    ma_slow_n = max(ma_fast_n + 1, min(lb // 2, cap))
    return ma_fast_n, ma_slow_n


def load_m5_with_book(symbol: str, data_dir: Path | None = None) -> pd.DataFrame:
    path = cache_path(symbol, data_dir)
    df = read_canonical_csv(path)
    if df.empty:
        raise FileNotFoundError(f"no M5 cache for {symbol}: {path}")
    return df.reset_index(drop=True)


def _ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=int(span), adjust=False).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return _true_range(df["high"], df["low"], df["close"]).rolling(int(period)).mean()


def ma_state(fast: np.ndarray, slow: np.ndarray, eps: float = EPS) -> np.ndarray:
    return sma_state(fast, slow, eps=eps)


def signed_dist_atr(close: np.ndarray, slow: np.ndarray, atr: np.ndarray, state: np.ndarray) -> np.ndarray:
    """Positive = price extended in the trend direction vs slow EMA, in ATR."""
    c = np.asarray(close, dtype=float)
    s = np.asarray(slow, dtype=float)
    a = np.asarray(atr, dtype=float)
    st = np.asarray(state)
    raw = np.full(len(c), np.nan)
    ok = np.isfinite(c) & np.isfinite(s) & np.isfinite(a) & (a > 0)
    raw[ok] = (c[ok] - s[ok]) / a[ok]
    out = np.full(len(c), np.nan)
    out[st > 0] = raw[st > 0]
    out[st < 0] = -raw[st < 0]
    return out


def scan_pullback_resume(
    state: np.ndarray,
    signed_dist: np.ndarray,
    close: np.ndarray,
    fast: np.ndarray,
    *,
    ext_thr: float = EXT_ATR,
    zone: float = ZONE_ATR,
    floor: float = ZONE_FLOOR_ATR,
) -> tuple[np.ndarray, np.ndarray]:
    """First retrace-zone bar and first resume-after-retrace bar per EMA episode."""
    n = len(state)
    pull = np.zeros(n, dtype=bool)
    resume = np.zeros(n, dtype=bool)
    max_ext = -np.inf
    had_pull = False
    pull_fired = False
    resume_fired = False
    prev = 0
    for i in range(n):
        s = int(state[i])
        if s == 0 or s != prev:
            max_ext = -np.inf
            had_pull = False
            pull_fired = False
            resume_fired = False
            prev = s
            if s == 0:
                continue
        d = float(signed_dist[i]) if np.isfinite(signed_dist[i]) else float("nan")
        if not np.isfinite(d):
            continue
        if d > max_ext:
            max_ext = d
        in_zone = (d <= zone) and (d >= floor) and (max_ext >= ext_thr)
        if in_zone:
            had_pull = True
            if not pull_fired:
                pull[i] = True
                pull_fired = True
        if had_pull and not resume_fired:
            cf = float(close[i])
            ff = float(fast[i])
            if np.isfinite(cf) and np.isfinite(ff):
                if (s > 0 and cf > ff) or (s < 0 and cf < ff):
                    resume[i] = True
                    resume_fired = True
    return pull, resume


def swing_retrace_mask(
    state: np.ndarray,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    slow: np.ndarray,
    *,
    lookback: int = SWING_LOOKBACK,
    depth: float = SWING_DEPTH,
) -> np.ndarray:
    """Causal 50% (or ``depth``) retrace of the last ``lookback`` impulse, trend still intact."""
    n = len(close)
    out = np.zeros(n, dtype=bool)
    fired: set[int] = set()
    ep = episode_ids(state)
    for i in range(n):
        s = int(state[i])
        e = int(ep[i])
        if s == 0 or e < 0 or e in fired:
            continue
        lo = max(0, i - int(lookback) + 1)
        window_h = np.asarray(high[lo : i + 1], dtype=float)
        window_l = np.asarray(low[lo : i + 1], dtype=float)
        c = float(close[i])
        sl = float(slow[i])
        if not (np.isfinite(c) and np.isfinite(sl) and np.isfinite(window_h).all()):
            continue
        hi = float(np.nanmax(window_h))
        lw = float(np.nanmin(window_l))
        rng = hi - lw
        if rng <= 0:
            continue
        if s > 0:
            retr = (hi - c) / rng
            intact = c > sl
        else:
            retr = (c - lw) / rng
            intact = c < sl
        if retr >= depth and intact:
            out[i] = True
            fired.add(e)
    return out


def mean_reversion_mask(close: np.ndarray, ema: np.ndarray, atr: np.ndarray, *, z: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """First |close-EMA|/ATR cross beyond ``z``. Side: fade the displacement."""
    c = np.asarray(close, dtype=float)
    e = np.asarray(ema, dtype=float)
    a = np.asarray(atr, dtype=float)
    n = len(c)
    score = np.full(n, np.nan)
    ok = np.isfinite(c) & np.isfinite(e) & np.isfinite(a) & (a > 0)
    score[ok] = (c[ok] - e[ok]) / a[ok]
    side = np.zeros(n, dtype=np.int8)
    entry = np.zeros(n, dtype=bool)
    armed = True
    last_side = 0
    for i in range(n):
        sc = score[i]
        if not np.isfinite(sc):
            armed = True
            last_side = 0
            continue
        this = -1 if sc > 0 else 1
        if abs(sc) < z:
            armed = True
            last_side = 0
            continue
        if this != last_side:
            armed = True
        if not armed:
            continue
        side[i] = this
        entry[i] = True
        armed = False
        last_side = this
    return entry, side


def attach_forwards(frame: pd.DataFrame, symbol: str, state_col: str = "state") -> pd.DataFrame:
    close = frame["close"].to_numpy(dtype=float)
    atr = frame["atr"].to_numpy(dtype=float)
    state = frame[state_col].to_numpy()
    out = frame
    for minutes in HORIZONS_MIN:
        steps = max(1, minutes // 5)
        out[f"fwd_{minutes}m_pips"] = signed_forward_pips(symbol, state, close, steps)
        out[f"fwd_{minutes}m_atr"] = signed_forward_atr(state, close, atr, steps)
    return out


def build_ema_frame(df: pd.DataFrame, symbol: str, fast_n: int, slow_n: int) -> pd.DataFrame:
    close = pd.to_numeric(df["close"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    fast = _ema(close, fast_n)
    slow = _ema(close, slow_n)
    atr = _atr(df)
    state = ma_state(fast.to_numpy(), slow.to_numpy())
    signed = signed_dist_atr(close.to_numpy(), slow.to_numpy(), atr.to_numpy(), state)
    pull, resume = scan_pullback_resume(state, signed, close.to_numpy(), fast.to_numpy())
    swing = swing_retrace_mask(state, close.to_numpy(), high.to_numpy(), low.to_numpy(), slow.to_numpy())
    swing_resume = np.zeros(len(df), dtype=bool)
    # Resume after swing retrace: reuse scanner but seed pull from swing mask.
    had = False
    fired = False
    prev = 0
    cl = close.to_numpy()
    fa = fast.to_numpy()
    for i, s in enumerate(state):
        s = int(s)
        if s == 0 or s != prev:
            had = False
            fired = False
            prev = s
            if s == 0:
                continue
        if swing[i]:
            had = True
        if had and not fired and np.isfinite(cl[i]) and np.isfinite(fa[i]):
            if (s > 0 and cl[i] > fa[i]) or (s < 0 and cl[i] < fa[i]):
                swing_resume[i] = True
                fired = True
    ep = episode_ids(state)
    age0 = np.zeros(len(df), dtype=bool)
    seen: set[int] = set()
    for i, e in enumerate(ep):
        if e >= 0 and e not in seen and state[i] != 0:
            age0[i] = True
            seen.add(int(e))
    out = pd.DataFrame(
        {
            "time": pd.to_datetime(df["time"]),
            "symbol": symbol,
            "close": close.to_numpy(dtype=float),
            "high": high.to_numpy(dtype=float),
            "low": low.to_numpy(dtype=float),
            "atr": atr.to_numpy(dtype=float),
            "ema_fast": fast.to_numpy(dtype=float),
            "ema_slow": slow.to_numpy(dtype=float),
            "state": state,
            "episode": ep,
            "signed_dist_atr": signed,
            "trend_cross": age0,
            "pull_atr": pull,
            "resume_atr": resume,
            "pull_swing50": swing,
            "resume_swing50": swing_resume,
        }
    )
    for col in ("bid_close", "ask_close", "bid_high", "bid_low", "ask_high", "ask_low"):
        if col in df.columns:
            out[col] = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    return attach_forwards(out, symbol)


def build_frozen_baseline(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    lookback = FROZEN_LOOKBACK[symbol]
    mid = df[["time", "open", "high", "low", "close"]].copy()
    frame = build_component_frame(mid, symbol, lookback)
    for col in ("bid_close", "ask_close", "bid_high", "bid_low", "ask_high", "ask_low"):
        if col in df.columns:
            frame[col] = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    return frame


def build_mean_reversion_frame(df: pd.DataFrame, symbol: str, ema_n: int = 50, z: float = 2.0) -> pd.DataFrame:
    close = pd.to_numeric(df["close"], errors="coerce")
    ema = _ema(close, ema_n)
    atr = _atr(df)
    entry, side = mean_reversion_mask(close.to_numpy(), ema.to_numpy(), atr.to_numpy(), z=z)
    out = pd.DataFrame(
        {
            "time": pd.to_datetime(df["time"]),
            "symbol": symbol,
            "close": close.to_numpy(dtype=float),
            "high": pd.to_numeric(df["high"], errors="coerce").to_numpy(dtype=float),
            "low": pd.to_numeric(df["low"], errors="coerce").to_numpy(dtype=float),
            "atr": atr.to_numpy(dtype=float),
            "state": side,
            "mr_entry": entry,
        }
    )
    for col in ("bid_close", "ask_close", "bid_high", "bid_low", "ask_high", "ask_low"):
        if col in df.columns:
            out[col] = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    return attach_forwards(out, symbol)


def _book_entry(row: pd.Series, side: str) -> float:
    d = (side or "").upper()
    if d == "BUY" and np.isfinite(row.get("ask_close", np.nan)):
        return float(row["ask_close"])
    if d == "SELL" and np.isfinite(row.get("bid_close", np.nan)):
        return float(row["bid_close"])
    mid = float(row["close"])
    pip = pip_size(str(row.get("symbol") or "EUR_USD"))
    half = pip  # 1-pip fallback only if book missing
    return mid + half if d == "BUY" else mid - half


def _bar_extremes_for_side(row: pd.Series, side: str) -> tuple[float, float]:
    """Trigger-side extremes: long vs bid, short vs ask. Fall back to mid high/low."""
    d = (side or "").upper()
    if d == "BUY":
        hi = row.get("bid_high", np.nan)
        lo = row.get("bid_low", np.nan)
    else:
        hi = row.get("ask_high", np.nan)
        lo = row.get("ask_low", np.nan)
    if not (np.isfinite(hi) and np.isfinite(lo)):
        return float(row["high"]), float(row["low"])
    return float(hi), float(lo)


def simulate_occupancy_trades(frame: pd.DataFrame, signal: np.ndarray, symbol: str) -> list[dict[str, Any]]:
    """Sequential one-position-at-a-time 2R SL/TP using book prices when present."""
    trades: list[dict[str, Any]] = []
    n = len(frame)
    i = 0
    while i < n:
        if not bool(signal[i]):
            i += 1
            continue
        row = frame.iloc[i]
        st = int(row["state"])
        if st == 0:
            i += 1
            continue
        side = "BUY" if st > 0 else "SELL"
        atr = float(row["atr"]) if np.isfinite(row["atr"]) else float("nan")
        if not np.isfinite(atr) or atr <= 0:
            i += 1
            continue
        entry = _book_entry(row, side)
        sl_d = SL_ATR_MULT * atr
        tp_d = sl_d * TP_R
        sl = entry - sl_d if side == "BUY" else entry + sl_d
        tp = entry + tp_d if side == "BUY" else entry - tp_d
        exit_px = None
        reason = "open"
        hold = 0
        j = i + 1
        while j < n:
            nxt = frame.iloc[j]
            hi, lo = _bar_extremes_for_side(nxt, side)
            touch = bar_touches(side, sl, tp, hi, lo)
            hold += 1
            if touch.hit_sl or touch.hit_tp:
                exit_px = float(touch.exit_price) if touch.exit_price is not None else sl
                reason = "ambiguous_sl" if touch.ambiguous else touch.exit_reason
                break
            j += 1
        if exit_px is None:
            last = frame.iloc[n - 1]
            if side == "BUY" and np.isfinite(last.get("bid_close", np.nan)):
                exit_px = float(last["bid_close"])
            elif side == "SELL" and np.isfinite(last.get("ask_close", np.nan)):
                exit_px = float(last["ask_close"])
            else:
                exit_px = float(last["close"])
            reason = "eod"
            hold = max(hold, n - i - 1)
            j = n - 1
        signed = (exit_px - entry) if side == "BUY" else (entry - exit_px)
        r_mult = signed / sl_d if sl_d > 0 else float("nan")
        trades.append(
            {
                "symbol": symbol,
                "side": side,
                "time": row["time"],
                "entry": entry,
                "exit": exit_px,
                "r": float(r_mult),
                "reason": reason,
                "hold_bars": int(hold),
                "win": bool(np.isfinite(r_mult) and r_mult > 0),
            }
        )
        i = j + 1
    return trades


def trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "n": 0,
            "buy": 0,
            "sell": 0,
            "win_rate": None,
            "expectancy_r": None,
            "profit_factor": None,
            "total_r": None,
            "avg_hold_bars": None,
            "avg_hold_min": None,
        }
    r = np.array([t["r"] for t in trades], dtype=float)
    r = r[np.isfinite(r)]
    wins = r[r > 0]
    losses = r[r < 0]
    gp = float(wins.sum()) if len(wins) else 0.0
    gl = float(-losses.sum()) if len(losses) else 0.0
    pf = None
    if gl > 0:
        pf = gp / gl
    elif gp > 0:
        pf = float("inf")
    holds = [t["hold_bars"] for t in trades]
    return {
        "n": int(len(trades)),
        "buy": int(sum(1 for t in trades if t["side"] == "BUY")),
        "sell": int(sum(1 for t in trades if t["side"] == "SELL")),
        "win_rate": float(np.mean([t["win"] for t in trades])),
        "expectancy_r": float(np.mean(r)) if len(r) else None,
        "profit_factor": pf,
        "total_r": float(np.sum(r)) if len(r) else None,
        "avg_hold_bars": float(np.mean(holds)) if holds else None,
        "avg_hold_min": float(np.mean(holds) * 5.0) if holds else None,
    }


def signal_forward_stats(frame: pd.DataFrame, mask: np.ndarray) -> dict[str, Any]:
    sub = frame.loc[mask]
    out: dict[str, Any] = {"event_n": int(mask.sum())}
    if "episode" in sub.columns:
        out["episode_n"] = int(sub.loc[sub["episode"] >= 0, "episode"].nunique()) if not sub.empty else 0
    buy = int(((frame["state"] > 0) & mask).sum())
    sell = int(((frame["state"] < 0) & mask).sum())
    out["buy"] = buy
    out["sell"] = sell
    for minutes in HORIZONS_MIN:
        col = f"fwd_{minutes}m_pips"
        out[f"{minutes}m"] = fwd_summary(sub[col].to_numpy() if col in sub.columns else np.array([]))
    return out


def split_trades(trades: list[dict[str, Any]], cuts: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    t50, t75 = cuts["cut_50"], cuts["cut_75"]
    out = {"train": [], "valid": [], "test": []}
    for t in trades:
        ts = pd.Timestamp(t["time"])
        if ts <= t50:
            out["train"].append(t)
        elif ts <= t75:
            out["valid"].append(t)
        else:
            out["test"].append(t)
    return out


@dataclass(frozen=True)
class ConfigResult:
    name: str
    family: str
    params: dict[str, Any]
    forward: dict[str, Any]
    economic: dict[str, Any]


def _partition_forward(frame: pd.DataFrame, mask: np.ndarray, cuts: dict[str, Any]) -> dict[str, Any]:
    times = pd.to_datetime(frame["time"])
    parts = {
        "all": mask,
        "train": mask & (times <= cuts["cut_50"]).to_numpy(),
        "valid": mask & ((times > cuts["cut_50"]) & (times <= cuts["cut_75"])).to_numpy(),
        "test": mask & (times > cuts["cut_75"]).to_numpy(),
    }
    return {k: signal_forward_stats(frame, m) for k, m in parts.items()}


def evaluate_config(
    name: str,
    family: str,
    params: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    masks: dict[str, np.ndarray],
    cuts: dict[str, Any],
) -> ConfigResult:
    pooled = pd.concat(frames.values(), ignore_index=True)
    pooled_mask = np.concatenate([masks[s] for s in frames])
    forward = {"overall": _partition_forward(pooled, pooled_mask, cuts), "symbol": {}}
    all_trades: list[dict[str, Any]] = []
    per_sym_econ: dict[str, Any] = {}
    for sym, frame in frames.items():
        m = masks[sym]
        forward["symbol"][sym] = signal_forward_stats(frame, m)
        trades = simulate_occupancy_trades(frame, m, sym)
        all_trades.extend(trades)
        per_sym_econ[sym] = trade_stats(trades)
    split = split_trades(all_trades, cuts)
    economic = {
        "overall": trade_stats(all_trades),
        "train": trade_stats(split["train"]),
        "valid": trade_stats(split["valid"]),
        "test": trade_stats(split["test"]),
        "symbol": per_sym_econ,
        "buy": trade_stats([t for t in all_trades if t["side"] == "BUY"]),
        "sell": trade_stats([t for t in all_trades if t["side"] == "SELL"]),
    }
    return ConfigResult(name=name, family=family, params=params, forward=forward, economic=economic)


def run_experiment(data_dir: Path | None = None) -> dict[str, Any]:
    raw: dict[str, pd.DataFrame] = {}
    frozen_frames: dict[str, pd.DataFrame] = {}
    for symbol in RESEARCH_SYMBOLS:
        src = load_m5_with_book(symbol, data_dir)
        raw[symbol] = src
        frozen_frames[symbol] = build_frozen_baseline(src, symbol)

    pooled_times = pd.concat([f["time"] for f in frozen_frames.values()], ignore_index=True)
    cuts = chrono_masks(pooled_times)

    results: list[ConfigResult] = []

    # Frozen SMA baseline — first qualifying bar (H) and every stub bar (J).
    h_masks = {s: f["first_qual"].to_numpy(dtype=bool) for s, f in frozen_frames.items()}
    j_masks = {s: f["stub_allow"].to_numpy(dtype=bool) for s, f in frozen_frames.items()}
    results.append(
        evaluate_config(
            "baseline_sma_first_qual",
            "frozen_baseline",
            {"lookback": dict(FROZEN_LOOKBACK), "rule": "first_stub_qual_H"},
            frozen_frames,
            h_masks,
            cuts,
        )
    )
    results.append(
        evaluate_config(
            "baseline_sma_every_stub",
            "frozen_baseline",
            {"lookback": dict(FROZEN_LOOKBACK), "rule": "every_stub_bar_J"},
            frozen_frames,
            j_masks,
            cuts,
        )
    )

    ema_store: dict[tuple[int, int], dict[str, pd.DataFrame]] = {}
    for fast_n, slow_n in EMA_PAIRS:
        built = {s: build_ema_frame(raw[s], s, fast_n, slow_n) for s in RESEARCH_SYMBOLS}
        ema_store[(fast_n, slow_n)] = built
        results.append(
            evaluate_config(
                f"ema{fast_n}_{slow_n}_trend_cross",
                "ema_trend",
                {"ema": [fast_n, slow_n], "rule": "first_bar_of_ema_state"},
                built,
                {s: f["trend_cross"].to_numpy(dtype=bool) for s, f in built.items()},
                cuts,
            )
        )

    # Primary pullback+resume on all three pairs; pull-only and swing on 50/200 only.
    for fast_n, slow_n in EMA_PAIRS:
        built = ema_store[(fast_n, slow_n)]
        results.append(
            evaluate_config(
                f"ema{fast_n}_{slow_n}_pull_resume",
                "ema_pull_resume",
                {
                    "ema": [fast_n, slow_n],
                    "retrace": "atr_zone",
                    "ext_atr": EXT_ATR,
                    "zone_atr": ZONE_ATR,
                    "resume": "close_vs_fast_ema",
                },
                built,
                {s: f["resume_atr"].to_numpy(dtype=bool) for s, f in built.items()},
                cuts,
            )
        )

    built200 = ema_store[(50, 200)]
    results.append(
        evaluate_config(
            "ema50_200_pull_only",
            "ema_pull",
            {"ema": [50, 200], "retrace": "atr_zone", "resume": None},
            built200,
            {s: f["pull_atr"].to_numpy(dtype=bool) for s, f in built200.items()},
            cuts,
        )
    )
    results.append(
        evaluate_config(
            "ema50_200_swing50_resume",
            "ema_pull_resume",
            {"ema": [50, 200], "retrace": "swing_50pct", "swing_lookback": SWING_LOOKBACK, "resume": "close_vs_fast_ema"},
            built200,
            {s: f["resume_swing50"].to_numpy(dtype=bool) for s, f in built200.items()},
            cuts,
        )
    )

    mr_frames = {s: build_mean_reversion_frame(raw[s], s) for s in RESEARCH_SYMBOLS}
    results.append(
        evaluate_config(
            "mean_reversion_ema50_z2",
            "mean_reversion",
            {"ema": 50, "z": 2.0, "rule": "fade_|close-ema|/atr>=2"},
            mr_frames,
            {s: f["mr_entry"].to_numpy(dtype=bool) for s, f in mr_frames.items()},
            cuts,
        )
    )

    book_cov = {}
    for s, src in raw.items():
        book_cov[s] = {
            "rows": int(len(src)),
            "has_bid_ask": bool("bid_close" in src.columns and "ask_close" in src.columns),
            "bid_close_finite": int(pd.to_numeric(src.get("bid_close"), errors="coerce").notna().sum())
            if "bid_close" in src.columns
            else 0,
        }

    return {
        "cuts": {
            "train_le": str(cuts["cut_50"]),
            "valid_le": str(cuts["cut_75"]),
        },
        "book_coverage": book_cov,
        "sma_periods": {s: indicator_sma_periods(FROZEN_LOOKBACK[s], len(raw[s])) for s in RESEARCH_SYMBOLS},
        "configs": [asdict(r) for r in results],
    }


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, float):
        if obj == float("inf"):
            return "inf"
        if obj != obj:
            return None
    return obj
