"""Stage 1 directional-replacement research. No production writes, no orders."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.decision_quality.feature_discovery import (
    apply_bins,
    classification_scores,
    fit_logreg,
    predict_logreg,
    train_quintile_edges,
)
from forex_bot.decision_quality.history_cache import cache_path, read_canonical_csv
from forex_bot.decision_quality.stub_components import (
    HORIZONS_MIN,
    chrono_masks,
    current_stub_allow,
    first_qualifying_in_episode,
    episode_ids,
    sma_state,
)
from forex_bot.indicators import compute_indicators
from forex_bot.profit_protection import pip_size
from forex_bot.symbols import DEFAULT_FOREX_SYMBOLS

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "research" / "directional_replacement_stage1"
LIVE_JSON = ROOT / "reports" / "decision_quality" / "_live_trade_failure_analysis.json"
LIVE_BOUNDARY = pd.Timestamp("2026-09-21T22:00:04Z")

FROZEN_LOOKBACK = {
    "USD_JPY": 50,
    "EUR_USD": 100,
    "GBP_USD": 100,
    "AUD_USD": 100,
    "USD_CAD": 100,
    "USD_CHF": 100,
}
SYMBOLS = tuple(DEFAULT_FOREX_SYMBOLS)
HOUR_BUCKETS = ((0, 3), (4, 7), (8, 11), (12, 15), (16, 19), (20, 23))
SKIP_THRESH = (0.55, 0.60, 0.65)
EPS = 1e-6
PRIMARY_H = 60


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        x = float(obj)
        return None if not math.isfinite(x) else round(x, 6)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if obj is None:
        return None
    return obj


def usd_dir(symbol: str, side: str) -> str:
    side = (side or "").upper()
    if symbol.startswith("USD_"):
        return "LONG_USD" if side == "BUY" else "SHORT_USD"
    if symbol.endswith("_USD"):
        return "SHORT_USD" if side == "BUY" else "LONG_USD"
    return "UNKNOWN"


def hour_bucket(hour: int) -> str:
    for a, b in HOUR_BUCKETS:
        if a <= hour <= b:
            return f"{a:02d}-{b:02d}"
    return "other"


def wilder_adx_series(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    alpha = 1.0 / period
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100.0 * (plus_dm.ewm(alpha=alpha, adjust=False).mean() / (atr + 1e-12))
    minus_di = 100.0 * (minus_dm.ewm(alpha=alpha, adjust=False).mean() / (atr + 1e-12))
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-12)
    return dx.ewm(alpha=alpha, adjust=False).mean()


def fwd_stats(pips: np.ndarray, r: np.ndarray | None = None) -> dict:
    x = np.asarray(pips, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return {"n": 0}
    wins = x[x > 0]
    losses = x[x < 0]
    gl = float(np.abs(losses.sum())) if len(losses) else 0.0
    out = {
        "n": int(len(x)),
        "hit": float(np.mean(x > 0)),
        "mean_pips": float(np.mean(x)),
        "median_pips": float(np.median(x)),
        "sum_pips": float(np.sum(x)),
        "profit_factor": (float(wins.sum()) / gl) if gl > 0 else None,
    }
    if r is not None:
        rr = np.asarray(r, dtype=float)
        rr = rr[np.isfinite(rr)]
        if len(rr):
            out["mean_r"] = float(np.mean(rr))
            out["median_r"] = float(np.median(rr))
    return out


def load_symbol(symbol: str) -> pd.DataFrame:
    df = read_canonical_csv(cache_path(symbol))
    if df.empty:
        raise FileNotFoundError(f"missing cache {symbol}")
    lb = FROZEN_LOOKBACK[symbol]
    mid = df[["time", "open", "high", "low", "close", "volume"]].copy()
    ind = compute_indicators(mid, lookback=lb)
    pip = pip_size(symbol)
    close = ind["close"].to_numpy(dtype=float)
    ma_fast = ind["ma_fast"].to_numpy(dtype=float)
    ma_slow = ind["ma_slow"].to_numpy(dtype=float)
    atr = ind["atr"].to_numpy(dtype=float)
    ret_1 = pd.Series(close).pct_change().to_numpy(dtype=float)
    state = sma_state(ma_fast, ma_slow)
    allow = current_stub_allow(state, ret_1, atr)
    first = first_qualifying_in_episode(episode_ids(state), allow)
    bid_c = pd.to_numeric(df["bid_close"], errors="coerce").to_numpy(dtype=float)
    ask_c = pd.to_numeric(df["ask_close"], errors="coerce").to_numpy(dtype=float)
    spread = (ask_c - bid_c) / pip
    sma_diff = ma_fast - ma_slow
    sma_diff_atr = np.where((np.isfinite(atr)) & (atr > 0), sma_diff / atr, np.nan)
    atr_pips = atr / pip
    risk_pips = 2.0 * atr_pips
    macd = ind["macd"].to_numpy(dtype=float)
    macd_sig = pd.Series(macd).ewm(span=9, adjust=False).mean().to_numpy(dtype=float)
    bb_w = (ind["boll_up"] - ind["boll_down"]).to_numpy(dtype=float)
    bb_pos = np.where(bb_w > 0, (close - ind["boll_down"].to_numpy(dtype=float)) / bb_w, np.nan)
    roll_high = pd.Series(close).rolling(36, min_periods=6).max().to_numpy(dtype=float)
    roll_low = pd.Series(close).rolling(36, min_periods=6).min().to_numpy(dtype=float)
    times = pd.to_datetime(ind["time"], utc=True)
    hours = times.dt.hour.to_numpy()
    dow = times.dt.dayofweek.to_numpy()
    vol = pd.to_numeric(ind.get("volume", df["volume"]), errors="coerce").to_numpy(dtype=float)
    rel_vol = vol / pd.Series(vol).rolling(36, min_periods=6).mean().to_numpy(dtype=float)
    adx = wilder_adx_series(ind["high"], ind["low"], ind["close"]).to_numpy(dtype=float)
    out = pd.DataFrame(
        {
            "time": times,
            "symbol": symbol,
            "lookback": lb,
            "close": close,
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "sma_diff": sma_diff,
            "sma_diff_atr": sma_diff_atr,
            "sma_slope": pd.Series(ma_fast).diff(6).to_numpy(dtype=float),
            "px_sma_fast": (close - ma_fast) / pip,
            "px_sma_slow": (close - ma_slow) / pip,
            "rsi": ind["rsi"].to_numpy(dtype=float),
            "macd": macd,
            "macd_signal": macd_sig,
            "macd_hist": macd - macd_sig,
            "bb_pos": bb_pos,
            "adx": adx,
            "atr": atr,
            "atr_pips": atr_pips,
            "atr_over_price": np.where(close > 0, atr / close, np.nan),
            "ret_1": ret_1,
            "ret_5": pd.Series(close).pct_change(1).to_numpy(dtype=float),
            "ret_15": pd.Series(close).pct_change(3).to_numpy(dtype=float),
            "ret_30": pd.Series(close).pct_change(6).to_numpy(dtype=float),
            "ret_60": pd.Series(close).pct_change(12).to_numpy(dtype=float),
            "ret_120": pd.Series(close).pct_change(24).to_numpy(dtype=float),
            "rv_30": pd.Series(ret_1).rolling(6).std().to_numpy(dtype=float),
            "dist_high_atr": np.where((np.isfinite(atr)) & (atr > 0), (roll_high - close) / atr, np.nan),
            "dist_low_atr": np.where((np.isfinite(atr)) & (atr > 0), (close - roll_low) / atr, np.nan),
            "spread_pips": spread,
            "spread_over_atr": np.where((np.isfinite(atr_pips)) & (atr_pips > 0), spread / atr_pips, np.nan),
            "volume": vol,
            "rel_vol": rel_vol,
            "hour_utc": hours,
            "hour_bucket": [hour_bucket(int(h)) for h in hours],
            "dow": dow,
            "state": state,
            "stub_allow": allow,
            "first_qual": first,
            "stub_side": np.where(state > 0, "BUY", np.where(state < 0, "SELL", "")),
            "stub_strength": np.abs(sma_diff_atr),
            "risk_pips": risk_pips,
        }
    )
    n = len(out)
    for minutes in HORIZONS_MIN:
        steps = minutes // 5
        bid_f = np.full(n, np.nan)
        ask_f = np.full(n, np.nan)
        if steps < n:
            bid_f[: n - steps] = bid_c[steps:]
            ask_f[: n - steps] = ask_c[steps:]
        buy = (bid_f - ask_c) / pip
        sell = (bid_c - ask_f) / pip
        out[f"buy_{minutes}"] = buy
        out[f"sell_{minutes}"] = sell
        orig = np.where(state > 0, buy, np.where(state < 0, sell, np.nan))
        inv = np.where(state > 0, sell, np.where(state < 0, buy, np.nan))
        out[f"orig_{minutes}"] = orig
        out[f"inv_{minutes}"] = inv
        out[f"orig_r_{minutes}"] = np.where(risk_pips > 0, orig / risk_pips, np.nan)
        out[f"inv_r_{minutes}"] = np.where(risk_pips > 0, inv / risk_pips, np.nan)
        out[f"up_{minutes}"] = bid_f > ask_c
        out[f"down_{minutes}"] = ask_f < bid_c
        out[f"flat_{minutes}"] = ~(out[f"up_{minutes}"] | out[f"down_{minutes}"]) & np.isfinite(buy)
    out["usd_dir"] = [usd_dir(symbol, s) for s in out["stub_side"]]
    out["atr_regime_raw"] = out["atr_over_price"]
    # Sanity: production stub matches state+allow on a sample of allowed rows.
    chk = out.loc[out["stub_allow"]].head(3)
    for _, row in chk.iterrows():
        vote = _quant_stub_vote(
            {
                "price": float(row["close"]),
                "ma_fast": float(row["ma_fast"]),
                "ma_slow": float(row["ma_slow"]),
                "returns": float(row["ret_1"]),
                "atr": float(row["atr"]),
            }
        )
        if vote["direction"] != row["stub_side"] or not vote["allow"]:
            raise RuntimeError(f"stub mismatch {symbol} {row['time']}")
    return out


def attach_cross_usd(frames: dict[str, pd.DataFrame]) -> None:
    usd_map = {}
    for sym, df in frames.items():
        side = df["stub_side"].to_numpy()
        usd = np.array([usd_dir(sym, s) if s else "" for s in side], dtype=object)
        times = pd.to_datetime(df["time"], utc=True)
        usd_map[sym] = pd.Series(usd, index=times)
    for sym, df in frames.items():
        times = pd.to_datetime(df["time"], utc=True)
        long_c = np.zeros(len(df), dtype=float)
        short_c = np.zeros(len(df), dtype=float)
        for other, series in usd_map.items():
            if other == sym:
                continue
            aligned = series.reindex(times)
            long_c += (aligned.to_numpy() == "LONG_USD").astype(float)
            short_c += (aligned.to_numpy() == "SHORT_USD").astype(float)
        df["xusd_long"] = long_c
        df["xusd_short"] = short_c
        df["xusd_net"] = long_c - short_c
        own = df["usd_dir"].to_numpy()
        df["xusd_agree"] = np.where(
            own == "LONG_USD",
            long_c > short_c,
            np.where(own == "SHORT_USD", short_c > long_c, False),
        )
        df["xusd_disagree"] = np.where(
            own == "LONG_USD",
            short_c > long_c,
            np.where(own == "SHORT_USD", long_c > short_c, False),
        )


def event_frame(frames: dict[str, pd.DataFrame], col: str = "first_qual") -> pd.DataFrame:
    parts = [df.loc[df[col]].copy() for df in frames.values()]
    out = pd.concat(parts, ignore_index=True)
    out = out.sort_values("time").reset_index(drop=True)
    return out


def split_assign(events: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cuts = chrono_masks(events["time"])
    events = events.copy()
    events["split"] = "test"
    events.loc[cuts["train"], "split"] = "train"
    events.loc[cuts["valid"], "split"] = "valid"
    meta = {
        "cut_50": str(pd.Timestamp(cuts["cut_50"])),
        "cut_75": str(pd.Timestamp(cuts["cut_75"])),
        "n_train": int(cuts["train"].sum()),
        "n_valid": int(cuts["valid"].sum()),
        "n_test": int(cuts["test"].sum()),
    }
    return events, meta


def inversion_block(df: pd.DataFrame) -> dict:
    out = {}
    for minutes in HORIZONS_MIN:
        out[str(minutes)] = {
            "original": fwd_stats(df[f"orig_{minutes}"].to_numpy(), df[f"orig_r_{minutes}"].to_numpy()),
            "inverted": fwd_stats(df[f"inv_{minutes}"].to_numpy(), df[f"inv_r_{minutes}"].to_numpy()),
        }
    return out


def breakdown_inversion(df: pd.DataFrame, field: str) -> dict:
    out = {}
    for name, sub in df.groupby(field, dropna=False):
        out[str(name)] = inversion_block(sub)
    return out


def strength_buckets(events: pd.DataFrame) -> dict:
    train = events.loc[events["split"] == "train", "stub_strength"].to_numpy()
    edges = train_quintile_edges(train)
    labels = np.array(["Q1", "Q2", "Q3", "Q4", "Q5"])
    idx = apply_bins(events["stub_strength"].to_numpy(), edges)
    idx = np.clip(idx, 0, 4)
    events = events.copy()
    events["strength_q"] = labels[idx]
    result = {"edges": [float(x) for x in edges], "by_split": {}}
    for split in ("train", "valid", "test"):
        sub = events.loc[events["split"] == split]
        result["by_split"][split] = {}
        hits = []
        for q in labels:
            cell = sub.loc[sub["strength_q"] == q]
            stats = fwd_stats(cell[f"orig_{PRIMARY_H}"].to_numpy(), cell[f"orig_r_{PRIMARY_H}"].to_numpy())
            result["by_split"][split][q] = stats
            if stats.get("n", 0):
                hits.append(stats.get("hit"))
        result["by_split"][split]["monotonic_hit"] = bool(
            hits and all(hits[i] <= hits[i + 1] + 1e-12 for i in range(len(hits) - 1))
        )
    return result


def subgroup_table(events: pd.DataFrame, field: str) -> dict:
    out = {}
    for name, sub in events.groupby(field, dropna=False):
        cell = {"n": int(len(sub))}
        for split in ("train", "valid", "test"):
            part = sub.loc[sub["split"] == split]
            cell[split] = fwd_stats(part[f"orig_{PRIMARY_H}"].to_numpy(), part[f"orig_r_{PRIMARY_H}"].to_numpy())
        tr, va, te = cell["train"], cell["valid"], cell["test"]
        stable = (
            tr.get("n", 0) >= 80
            and va.get("n", 0) >= 40
            and te.get("n", 0) >= 40
            and (tr.get("mean_pips") or 0) > 0
            and (va.get("mean_pips") or 0) > 0
            and (te.get("mean_pips") or 0) > 0
        )
        cell["stable_positive"] = bool(stable)
        out[str(name)] = cell
    return out


def feature_matrix(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    cols = [
        "sma_diff_atr",
        "rsi",
        "ret_5",
        "ret_15",
        "ret_30",
        "atr_over_price",
        "spread_over_atr",
        "bb_pos",
        "adx",
        "xusd_net",
        "dist_high_atr",
        "dist_low_atr",
        "rv_30",
    ]
    hour = df["hour_utc"].to_numpy(dtype=float)
    extra = np.column_stack(
        [
            np.sin(2 * np.pi * hour / 24.0),
            np.cos(2 * np.pi * hour / 24.0),
            np.where(df["stub_side"].to_numpy() == "BUY", 1.0, -1.0),
            np.where(df["usd_dir"].to_numpy() == "LONG_USD", 1.0, -1.0),
        ]
    )
    names = cols + ["hour_sin", "hour_cos", "stub_side", "usd_side"]
    X = df[cols].to_numpy(dtype=float)
    X = np.column_stack([X, extra])
    return X, names


def standardize_train(X_train: np.ndarray, X: np.ndarray) -> np.ndarray:
    mu = np.nanmean(X_train, axis=0)
    sd = np.nanstd(X_train, axis=0)
    sd = np.where((np.isfinite(sd)) & (sd > 1e-12), sd, 1.0)
    mu = np.where(np.isfinite(mu), mu, 0.0)
    Z = (X - mu) / sd
    return np.where(np.isfinite(Z), Z, 0.0)


def economic_from_p(df: pd.DataFrame, p: np.ndarray, lo: float, hi: float, minutes: int = PRIMARY_H) -> dict:
    buy = p >= hi
    sell = p <= lo
    skip = ~(buy | sell)
    px = np.where(buy, df[f"buy_{minutes}"].to_numpy(), np.where(sell, df[f"sell_{minutes}"].to_numpy(), np.nan))
    rr = np.where(df["risk_pips"].to_numpy() > 0, px / df["risk_pips"].to_numpy(), np.nan)
    stats = fwd_stats(px, rr)
    stats["coverage"] = float((buy | sell).mean()) if len(p) else 0.0
    stats["n_buy"] = int(buy.sum())
    stats["n_sell"] = int(sell.sum())
    stats["n_skip"] = int(skip.sum())
    return stats


def fit_depth2_stump(X: np.ndarray, y: np.ndarray) -> dict:
    """Greedy depth-2 tree. Split candidates = train quintiles. TRAIN only."""
    n, k = X.shape
    best = None
    for j in range(k):
        edges = train_quintile_edges(X[:, j])
        for thr in edges[1:-1]:
            left = X[:, j] <= thr
            if left.sum() < 50 or (~left).sum() < 50:
                continue
            score = 0.0
            for mask in (left, ~left):
                p = float(y[mask].mean()) if mask.any() else 0.5
                p = min(max(p, 1e-6), 1 - 1e-6)
                score += float(mask.sum()) * -(p * math.log(p) + (1 - p) * math.log(1 - p))
            if best is None or score < best[0]:
                best = (score, j, float(thr), float(y[left].mean()), float(y[~left].mean()))
    if best is None:
        return {"feat": 0, "thr": 0.0, "p_left": 0.5, "p_right": 0.5}
    return {"feat": int(best[1]), "thr": best[2], "p_left": best[3], "p_right": best[4]}


def predict_stump(X: np.ndarray, tree: dict) -> np.ndarray:
    left = X[:, tree["feat"]] <= tree["thr"]
    return np.where(left, tree["p_left"], tree["p_right"])


def live_block() -> dict:
    raw = json.loads(LIVE_JSON.read_text(encoding="utf-8"))
    scored = [
        t
        for t in raw["trades"]
        if t.get("exit_class") in ("BROKER_STOP_LOSS", "BROKER_TAKE_PROFIT", "BOT_PROFIT_PROTECTION")
    ]
    out = {
        "n_scored": len(scored),
        "window": {"start": raw.get("boundary_utc"), "note": "corrected-build holdout; not used for fitting"},
        "inversion": {},
        "by_symbol": {},
        "by_side": {},
        "by_strategy": {},
        "by_hour": {},
        "by_usd": {},
        "booked": {
            "mean_r": raw.get("mfe") and None,
        },
        "rl": {
            "filled_trades": len(scored),
            "vetoed_recorded": 0,
            "note": "Filled live trades passed the same-side RL gate by construction. Vetoed stub candidates are not persisted in trades/exec_orders.",
        },
        "live_used_for_model_selection": False,
    }
    for minutes in HORIZONS_MIN:
        orig = []
        inv = []
        orig_r = []
        inv_r = []
        for t in scored:
            cell = (t.get("forward") or {}).get(str(minutes)) or {}
            r = cell.get("r")
            pips = cell.get("pips")
            if r is None:
                continue
            orig_r.append(float(r))
            inv_r.append(-float(r))
            if pips is not None:
                orig.append(float(pips))
                inv.append(-float(pips))
        out["inversion"][str(minutes)] = {
            "original": fwd_stats(np.array(orig), np.array(orig_r)),
            "inverted": fwd_stats(np.array(inv), np.array(inv_r)),
            "note": "Live forwards already include executable-side path from the forensic study. Inversion is sign flip of that series (spread already paid on original entry).",
        }

    def _grp(key):
        groups = defaultdict(list)
        for t in scored:
            groups[str(t.get(key) or "unknown")].append(t)
        table = {}
        for name, items in groups.items():
            rs = [float(x["realised_r"]) for x in items if x.get("realised_r") is not None]
            fwd = []
            for x in items:
                cell = (x.get("forward") or {}).get(str(PRIMARY_H)) or {}
                if cell.get("r") is not None:
                    fwd.append(float(cell["r"]))
            table[name] = {
                "n": len(items),
                "booked_mean_r": float(np.mean(rs)) if rs else None,
                "fwd60_mean_r": float(np.mean(fwd)) if fwd else None,
                "fwd60_hit": float(np.mean(np.array(fwd) > 0)) if fwd else None,
            }
        return table

    out["by_symbol"] = _grp("symbol")
    out["by_side"] = _grp("side")
    out["by_strategy"] = _grp("strategy")
    out["by_hour"] = _grp("hour_utc")
    out["by_usd"] = _grp("usd_dir")
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = {}
    print("loading historical M5", flush=True)
    for sym in SYMBOLS:
        frames[sym] = load_symbol(sym)
        print(sym, len(frames[sym]), "allow", int(frames[sym]["stub_allow"].sum()), flush=True)
    attach_cross_usd(frames)
    events = event_frame(frames, "first_qual")
    events, split_meta = split_assign(events)
    print("events", len(events), split_meta, flush=True)

    all_allow = event_frame(frames, "stub_allow")
    all_allow, all_split = split_assign(all_allow)

    hist = {
        "dataset": {
            "source": "data/historical/*_M5.csv",
            "range": "2025-09-01 through 2026-08-31 complete M5 bid/ask",
            "lookbacks": FROZEN_LOOKBACK,
            "event_rule": "first qualifying stub-allow bar of each SMA episode",
            "target": "UP if bid[t+h] > ask[t]; DOWN if ask[t+h] < bid[t]; else ECONOMICALLY_FLAT",
            "cost": "executable BUY=(bid_future-ask_entry)/pip; SELL=(bid_entry-ask_future)/pip",
            "risk_r": "2 * ATR_pips at entry (research 2xATR stop, not live P/L)",
            "splits": split_meta,
            "live_holdout": "2026-09-21T22:00:04Z corrected-build trades; not used for fitting",
        },
        "n_events": int(len(events)),
        "inversion_first_qual": {},
        "inversion_all_allow_sensitivity": {},
        "inversion_breakdowns": {},
        "strength": {},
        "subgroups": {},
        "models": {},
        "skip_gate": {},
        "cross_usd": {},
        "features_included": [
            "sma_fast",
            "sma_slow",
            "sma_diff",
            "sma_diff/atr",
            "sma_slope_30m",
            "price-sma_fast",
            "price-sma_slow",
            "rsi",
            "macd",
            "macd_signal (9-span of existing macd)",
            "macd_hist",
            "bollinger_position",
            "adx (research wilder, not live)",
            "atr",
            "atr/price",
            "ret 5/15/30/60/120m",
            "rv_30",
            "dist recent high/low ATR",
            "spread",
            "spread/atr",
            "volume",
            "rel_vol",
            "hour UTC",
            "dow",
            "stub side",
            "usd dir",
            "cross-pair USD counts",
        ],
        "features_unavailable": [
            "production strategy label on historical bars (select_strategy is RNG/meta; not reconstructed)",
            "live ma_fast/ma_slow (not persisted; cache ends 2026-08-31 so live features not rebuilt)",
            "RL veto records",
        ],
    }

    for split in ("train", "valid", "test"):
        hist["inversion_first_qual"][split] = inversion_block(events.loc[events["split"] == split])
        hist["inversion_all_allow_sensitivity"][split] = {
            str(PRIMARY_H): inversion_block(all_allow.loc[all_allow["split"] == split]).get(str(PRIMARY_H))
        }

    hist["inversion_breakdowns"] = {
        "symbol": breakdown_inversion(events, "symbol"),
        "stub_side": breakdown_inversion(events, "stub_side"),
        "usd_dir": breakdown_inversion(events, "usd_dir"),
        "hour_bucket": breakdown_inversion(events, "hour_bucket"),
    }
    hist["strength"] = strength_buckets(events)
    hist["subgroups"] = {
        "symbol": subgroup_table(events, "symbol"),
        "stub_side": subgroup_table(events, "stub_side"),
        "usd_dir": subgroup_table(events, "usd_dir"),
        "hour_bucket": subgroup_table(events, "hour_bucket"),
    }

    # train-only regime edges
    for raw_col, name in (
        ("atr_over_price", "vol"),
        ("spread_over_atr", "spread"),
        ("ret_30", "ret30"),
        ("stub_strength", "trend"),
    ):
        edges = train_quintile_edges(events.loc[events["split"] == "train", raw_col].to_numpy())
        idx = np.clip(apply_bins(events[raw_col].to_numpy(), edges), 0, 4)
        events[f"{name}_q"] = np.array(["Q1", "Q2", "Q3", "Q4", "Q5"])[idx]
        hist["subgroups"][f"{name}_q"] = subgroup_table(events, f"{name}_q")

    # models — TRAIN only
    train = events.loc[events["split"] == "train"].reset_index(drop=True)
    X_all, feat_names = feature_matrix(events)
    y_all = events[f"up_{PRIMARY_H}"].to_numpy(dtype=float)
    finite = np.isfinite(events[f"buy_{PRIMARY_H}"].to_numpy())
    train_m = (events["split"] == "train").to_numpy() & finite
    X_std = standardize_train(X_all[train_m], X_all)
    w = fit_logreg(X_std[train_m], y_all[train_m], l2=1.0, steps=250, lr=0.15)
    p = predict_logreg(X_std, w)
    events["p_up"] = p
    tree = fit_depth2_stump(X_std[train_m], y_all[train_m])
    p_tree = predict_stump(X_std, tree)
    events["p_up_tree"] = p_tree

    hist["models"]["features"] = feat_names
    hist["models"]["logreg_weights"] = {"bias": float(w[0]), "w": [float(x) for x in w[1:]]}
    hist["models"]["tree"] = {**tree, "feat_name": feat_names[tree["feat"]]}
    hist["models"]["scores"] = {}
    hist["models"]["economics"] = {}
    for split in ("train", "valid", "test"):
        m = (events["split"] == split).to_numpy() & finite
        hist["models"]["scores"][split] = {
            "logreg": classification_scores(y_all[m], p[m]),
            "tree": classification_scores(y_all[m], p_tree[m]),
            "always_up": classification_scores(y_all[m], np.full(int(m.sum()), y_all[train_m].mean())),
        }
        sub = events.loc[m]
        # follow model at 0.5
        hist["models"]["economics"][split] = {
            "logreg_always": economic_from_p(sub, sub["p_up"].to_numpy(), 0.5, 0.5),
            "tree_always": economic_from_p(sub, sub["p_up_tree"].to_numpy(), 0.5, 0.5),
            "stub": fwd_stats(sub[f"orig_{PRIMARY_H}"].to_numpy(), sub[f"orig_r_{PRIMARY_H}"].to_numpy()),
            "invert": fwd_stats(sub[f"inv_{PRIMARY_H}"].to_numpy(), sub[f"inv_r_{PRIMARY_H}"].to_numpy()),
        }
        # calibration 5 bins
        bins = np.digitize(sub["p_up"].to_numpy(), [0.2, 0.4, 0.5, 0.6, 0.8], right=True)
        cal = []
        for b in range(6):
            mask = bins == b
            if mask.sum() < 10:
                continue
            cal.append(
                {
                    "bin": int(b),
                    "n": int(mask.sum()),
                    "mean_p": float(sub["p_up"].to_numpy()[mask].mean()),
                    "up_rate": float(y_all[m][mask].mean()),
                }
            )
        hist["models"]["scores"][split]["calibration"] = cal

    hist["skip_gate"] = {}
    for thr in SKIP_THRESH:
        hist["skip_gate"][str(thr)] = {}
        for split in ("train", "valid", "test"):
            sub = events.loc[(events["split"] == split) & finite]
            hist["skip_gate"][str(thr)][split] = economic_from_p(
                sub, sub["p_up"].to_numpy(), 1.0 - thr, thr
            )

    # strength filter Q5 only (train edges already applied)
    hist["strength_filter_q5"] = {}
    q5 = events.loc[events.get("trend_q", events.get("strength_q", "Q5")) == "Q5"] if "trend_q" in events else events
    if "trend_q" in events.columns:
        q5 = events.loc[events["trend_q"] == "Q5"]
    else:
        q5 = events.iloc[0:0]
    for split in ("train", "valid", "test"):
        sub = q5.loc[q5["split"] == split] if len(q5) else q5
        hist["strength_filter_q5"][split] = fwd_stats(
            sub[f"orig_{PRIMARY_H}"].to_numpy() if len(sub) else np.array([]),
            sub[f"orig_r_{PRIMARY_H}"].to_numpy() if len(sub) else np.array([]),
        )

    hist["cross_usd"] = {
        "agree": subgroup_table(events, "xusd_agree"),
        "net_sign": {},
    }
    events["xusd_sign"] = np.where(events["xusd_net"] > 0, "NET_LONG_USD", np.where(events["xusd_net"] < 0, "NET_SHORT_USD", "NET_FLAT"))
    hist["cross_usd"]["net_sign"] = subgroup_table(events, "xusd_sign")
    # follow broad USD: if net long USD, take LONG_USD side of candidate
    usd_follow = []
    usd_r = []
    for _, row in events.iterrows():
        net = row["xusd_net"]
        if not np.isfinite(row[f"buy_{PRIMARY_H}"]):
            continue
        if net > 0:
            # LONG_USD: BUY on USD_*, SELL on *_USD
            px = row[f"buy_{PRIMARY_H}"] if row["symbol"].startswith("USD_") else row[f"sell_{PRIMARY_H}"]
        elif net < 0:
            px = row[f"sell_{PRIMARY_H}"] if row["symbol"].startswith("USD_") else row[f"buy_{PRIMARY_H}"]
        else:
            continue
        usd_follow.append(px)
        usd_r.append(px / row["risk_pips"] if row["risk_pips"] else np.nan)
    # split-wise USD follow
    hist["cross_usd"]["follow_net"] = {}
    for split in ("train", "valid", "test"):
        sub = events.loc[events["split"] == split]
        vals = []
        rs = []
        for _, row in sub.iterrows():
            net = row["xusd_net"]
            if not np.isfinite(row.get(f"buy_{PRIMARY_H}", np.nan)):
                continue
            if abs(net) < 1:
                continue
            if net > 0:
                px = row[f"buy_{PRIMARY_H}"] if str(row["symbol"]).startswith("USD_") else row[f"sell_{PRIMARY_H}"]
            else:
                px = row[f"sell_{PRIMARY_H}"] if str(row["symbol"]).startswith("USD_") else row[f"buy_{PRIMARY_H}"]
            vals.append(px)
            rs.append(px / row["risk_pips"] if row["risk_pips"] else np.nan)
        hist["cross_usd"]["follow_net"][split] = fwd_stats(np.array(vals), np.array(rs))

    live = live_block()
    payload = {
        "historical": hist,
        "live": live,
        "contamination": {
            "live_used_for_fitting": False,
            "live_used_for_threshold_search": False,
            "thresholds_predeclared": list(SKIP_THRESH),
            "live_still_untouched_holdout": True,
        },
    }
    path = OUT_DIR / "results.json"
    path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    events[
        [
            "time",
            "symbol",
            "split",
            "stub_side",
            "usd_dir",
            "stub_strength",
            "p_up",
            f"orig_{PRIMARY_H}",
            f"inv_{PRIMARY_H}",
            f"up_{PRIMARY_H}",
            f"down_{PRIMARY_H}",
        ]
    ].to_csv(OUT_DIR / "events_first_qual.csv", index=False)
    print("wrote", path, flush=True)


if __name__ == "__main__":
    main()
