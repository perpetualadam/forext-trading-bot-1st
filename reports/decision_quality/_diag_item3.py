"""Directional forward returns ignoring SL/TP. Uses persisted 5-60m; candle-joins 120/240m."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from forex_bot.decision_quality.checkpoint import BASELINE_SYMBOLS, load_json, load_result_artifact
from forex_bot.decision_quality.data import load_symbol_frame
from forex_bot.decision_quality.invariants import signed_pips
from forex_bot.decision_quality.walk_forward import chronological_splits
from forex_bot.profit_protection import pip_size

print("ITEM3_START", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

CK = load_json(Path("reports/decision_quality/baseline_checkpoint.json"))
HIST = Path("data/historical")
PERSISTED = (5, 15, 30, 60)
CANDLE = (120, 240)


def attach_long_horizons(symbol: str, trades) -> None:
    df = load_symbol_frame(HIST / f"{symbol}_M5.csv")
    times = {df["time"].iloc[i].to_pydatetime(): i for i in range(len(df))}
    for t in trades:
        i = times.get(t.entry_time)
        if i is None:
            ts = t.entry_time.replace(tzinfo=None) if getattr(t.entry_time, "tzinfo", None) else t.entry_time
            # fallback: Timestamp equality
            match = df.index[df["time"] == t.entry_time]
            i = int(match[0]) if len(match) else None
        if i is None:
            continue
        side = t.snapshot.side
        entry = float(t.snapshot.entry_price)
        atr = t.snapshot.atr
        pip = pip_size(symbol)
        for minutes in CANDLE:
            j = i + minutes // 5
            if j >= len(df):
                continue
            px = float(df["close"].iloc[j])
            pips = signed_pips(symbol, side, entry, px)
            t.forward[f"{minutes}m_pips"] = pips
            t.forward[f"{minutes}m_hit"] = bool(pips > 0)
            if atr and atr > 0 and pip:
                t.forward[f"{minutes}m_atr"] = (pips * pip) / atr


def stats(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    a = np.asarray(vals, dtype=float)
    return {
        "n": int(len(a)),
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "pct_pos": float((a > 0).mean()),
        "p10": float(np.percentile(a, 10)),
        "p25": float(np.percentile(a, 25)),
        "p75": float(np.percentile(a, 75)),
        "p90": float(np.percentile(a, 90)),
    }


def collect(trades, minutes: int, unit: str) -> list[float]:
    key = f"{minutes}m_pips" if unit == "pips" else f"{minutes}m_atr"
    out = []
    for t in trades:
        v = t.forward.get(key)
        if v is None and unit == "atr":
            pips = t.forward.get(f"{minutes}m_pips")
            atr = t.snapshot.atr
            pip = pip_size(t.snapshot.symbol)
            if pips is not None and atr and atr > 0 and pip:
                v = (pips * pip) / atr
        if v is not None:
            out.append(float(v))
    return out


def show(label: str, trades) -> None:
    print(f"## {label} n_trades={len(trades)}")
    for minutes in PERSISTED + CANDLE:
        for unit in ("pips", "atr"):
            s = stats(collect(trades, minutes, unit))
            if s["n"] == 0:
                print(f"  {minutes}m {unit}: n=0")
                continue
            print(
                f"  {minutes}m {unit}: n={s['n']} mean={s['mean']:.5f} med={s['median']:.5f} "
                f"pct_pos={s['pct_pos']:.4f} p10={s['p10']:.5f} p25={s['p25']:.5f} "
                f"p75={s['p75']:.5f} p90={s['p90']:.5f}"
            )


all_t = []
by_sym = {}
for sym in BASELINE_SYMBOLS:
    trades = load_result_artifact(Path(CK["units"][f"{sym}|baseline"]["result_path"])).trades
    attach_long_horizons(sym, trades)
    by_sym[sym] = trades
    all_t.extend(trades)

show("OVERALL", all_t)
for side in ("BUY", "SELL"):
    show(side, [t for t in all_t if t.snapshot.side == side])
for sym in BASELINE_SYMBOLS:
    show(sym, by_sym[sym])
splits = chronological_splits(all_t)
for part in ("train", "valid", "test"):
    show(part, splits[part])

print("ITEM3_END", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
