"""Research-only Fibonacci vs ordinary retracement-depth experiment.

Does not import bot_loop / OANDA execution. Does not change the live stub, RL,
V2 shadow, or SL/TP. Reuses the EMA-retracement causal swing and occupancy engine.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from forex_bot.decision_quality.ema_retracement import (
    RESEARCH_SYMBOLS,
    SWING_LOOKBACK,
    build_ema_frame,
    evaluate_config,
    load_m5_with_book,
    swing_retrace_mask,
)
from forex_bot.decision_quality.stub_components import chrono_masks

# Frozen before outcome evaluation. Do not edit after seeing results.
EMA_FAST = 50
EMA_SLOW = 200
SWING_BARS = SWING_LOOKBACK  # 24; not optimized
CONTROL_DEPTHS: tuple[float, ...] = (
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
)
FIB_DEPTHS: tuple[float, ...] = (0.236, 0.382, 0.618, 0.786)
NEIGHBORS: dict[float, tuple[float, float]] = {
    0.236: (0.20, 0.25),
    0.382: (0.35, 0.40),
    0.618: (0.60, 0.65),
    0.786: (0.75, 0.80),
}
PLACEBO_SEED = 42
PLACEBO_N = 8
PLACEBO_DEPTHS: tuple[float, ...] = (0.257, 0.277, 0.463, 0.657, 0.664, 0.672, 0.715, 0.785)

# Predeclared neighbor-advantage threshold (R). Not tuned after outcomes.
NEIGHBOR_R_MARGIN = 0.05


def generate_placebo_depths(
    seed: int = PLACEBO_SEED,
    n: int = PLACEBO_N,
) -> tuple[float, ...]:
    """Deterministic non-grid depths in [0.20, 0.80]. Frozen by PLACEBO_SEED / PLACEBO_N."""
    reserved = set(CONTROL_DEPTHS) | set(FIB_DEPTHS)
    rng = np.random.default_rng(int(seed))
    out: list[float] = []
    for raw in rng.uniform(0.20, 0.80, size=500):
        depth = round(float(raw), 3)
        if depth < 0.20 or depth > 0.80:
            continue
        if depth in reserved or depth in out:
            continue
        out.append(depth)
        if len(out) == int(n):
            break
    if len(out) != int(n):
        raise RuntimeError("placebo generation failed to fill the frozen count")
    return tuple(sorted(out))


def swing_window_bounds(index: int, lookback: int = SWING_BARS) -> tuple[int, int]:
    """Inclusive start, exclusive end. End is index+1 so bar ``index`` is included and index+1 is not."""
    start = max(0, int(index) - int(lookback) + 1)
    end = int(index) + 1
    return start, end


def retrace_fraction(
    *,
    side: int,
    close: float,
    swing_high: float,
    swing_low: float,
) -> float | None:
    rng = float(swing_high) - float(swing_low)
    if rng <= 0 or not np.isfinite(rng):
        return None
    if side > 0:
        return (float(swing_high) - float(close)) / rng
    if side < 0:
        return (float(close) - float(swing_low)) / rng
    return None


def resume_after_pull(
    state: np.ndarray,
    close: np.ndarray,
    fast: np.ndarray,
    pull: np.ndarray,
) -> np.ndarray:
    """First close-through-fast-EMA after the first pull of each EMA-state episode."""
    n = len(state)
    resume = np.zeros(n, dtype=bool)
    had = False
    fired = False
    prev = 0
    for i in range(n):
        s = int(state[i])
        if s == 0 or s != prev:
            had = False
            fired = False
            prev = s
            if s == 0:
                continue
        if bool(pull[i]):
            had = True
        if had and not fired and np.isfinite(close[i]) and np.isfinite(fast[i]):
            if (s > 0 and close[i] > fast[i]) or (s < 0 and close[i] < fast[i]):
                resume[i] = True
                fired = True
    return resume


def depth_resume_mask(frame: pd.DataFrame, depth: float) -> np.ndarray:
    pull = swing_retrace_mask(
        frame["state"].to_numpy(),
        frame["close"].to_numpy(dtype=float),
        frame["high"].to_numpy(dtype=float),
        frame["low"].to_numpy(dtype=float),
        frame["ema_slow"].to_numpy(dtype=float),
        lookback=SWING_BARS,
        depth=float(depth),
    )
    return resume_after_pull(
        frame["state"].to_numpy(),
        frame["close"].to_numpy(dtype=float),
        frame["ema_fast"].to_numpy(dtype=float),
        pull,
    )


def _level_name(kind: str, depth: float) -> str:
    if kind == "fib":
        return f"fib_{int(round(depth * 1000))}_resume"
    if kind == "placebo":
        return f"placebo_{int(round(depth * 1000))}_resume"
    return f"control_{int(round(depth * 100))}_resume"


def neighbor_table(by_depth: dict[float, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fib, (lo, hi) in NEIGHBORS.items():
        row: dict[str, Any] = {"fib": fib, "lower": lo, "upper": hi}
        for split in ("train", "valid", "test", "overall"):
            fib_r = (by_depth.get(fib) or {}).get(split, {}).get("expectancy_r")
            lo_r = (by_depth.get(lo) or {}).get(split, {}).get("expectancy_r")
            hi_r = (by_depth.get(hi) or {}).get(split, {}).get("expectancy_r")
            row[f"{split}_fib_r"] = fib_r
            row[f"{split}_lower_r"] = lo_r
            row[f"{split}_upper_r"] = hi_r
            beats = (
                fib_r is not None
                and lo_r is not None
                and hi_r is not None
                and fib_r > lo_r + NEIGHBOR_R_MARGIN
                and fib_r > hi_r + NEIGHBOR_R_MARGIN
            )
            row[f"{split}_fib_beats_both"] = bool(beats)
        rows.append(row)
    return rows


def classify_conclusion(neighbors: list[dict[str, Any]], by_depth: dict[float, dict[str, Any]]) -> str:
    """Frozen decision rule. Not a 'best Fib level' picker."""
    fib_specific = False
    for row in neighbors:
        if row.get("valid_fib_beats_both") and row.get("test_fib_beats_both"):
            fib_specific = True
            break
    if fib_specific:
        return "C"
    rs = []
    depths = []
    for depth, splits in by_depth.items():
        if depth in FIB_DEPTHS:
            continue
        exp = (splits.get("test") or {}).get("expectancy_r")
        if exp is not None:
            depths.append(depth)
            rs.append(exp)
    if len(rs) >= 6:
        corr = float(np.corrcoef(np.array(depths), np.array(rs))[0, 1])
        if np.isfinite(corr) and abs(corr) >= 0.45:
            return "B"
        # Generic effect if test expectancy varies smoothly more than 0.08 R peak-to-trough.
        if max(rs) - min(rs) >= 0.08:
            return "B"
    return "A"


def run_experiment(data_dir: Path | None = None) -> dict[str, Any]:
    if generate_placebo_depths() != PLACEBO_DEPTHS:
        raise RuntimeError("placebo depths drifted from the frozen tuple")

    raw = {s: load_m5_with_book(s, data_dir) for s in RESEARCH_SYMBOLS}
    frames = {s: build_ema_frame(src, s, EMA_FAST, EMA_SLOW) for s, src in raw.items()}
    pooled_times = pd.concat([f["time"] for f in frames.values()], ignore_index=True)
    cuts = chrono_masks(pooled_times)

    levels: list[tuple[str, float]] = (
        [("control", d) for d in CONTROL_DEPTHS]
        + [("fib", d) for d in FIB_DEPTHS]
        + [("placebo", d) for d in PLACEBO_DEPTHS]
    )
    configs = []
    by_depth: dict[float, dict[str, Any]] = {}
    for kind, depth in levels:
        masks = {s: depth_resume_mask(f, depth) for s, f in frames.items()}
        result = evaluate_config(
            _level_name(kind, depth),
            kind,
            {
                "ema": [EMA_FAST, EMA_SLOW],
                "swing_lookback": SWING_BARS,
                "depth": depth,
                "kind": kind,
                "resume": "close_vs_fast_ema",
                "dedup": "first_swing_retrace_per_ema_episode_then_first_resume",
            },
            frames,
            masks,
            cuts,
        )
        payload = asdict(result)
        configs.append(payload)
        by_depth[depth] = {
            "kind": kind,
            "name": result.name,
            "train": result.economic["train"],
            "valid": result.economic["valid"],
            "test": result.economic["test"],
            "overall": result.economic["overall"],
            "buy": result.economic["buy"],
            "sell": result.economic["sell"],
            "symbol": result.economic["symbol"],
            "forward_60m": {
                split: (result.forward["overall"][split].get("60m") or {})
                for split in ("all", "train", "valid", "test")
            },
        }

    neighbors = neighbor_table(by_depth)
    conclusion = classify_conclusion(neighbors, by_depth)
    labels = {
        "A": "NO RETRACEMENT-DEPTH EDGE",
        "B": "GENERIC RETRACEMENT-DEPTH EFFECT, NOT FIB-SPECIFIC",
        "C": "FIB-SPECIFIC EFFECT WORTH INDEPENDENT VALIDATION",
    }
    return {
        "experiment": "Fibonacci vs ordinary retracement depth",
        "production_impact": "NONE",
        "spec": {
            "ema": [EMA_FAST, EMA_SLOW],
            "swing_lookback": SWING_BARS,
            "swing_index": "high/low[max(0,i-lookback+1):i+1]; current bar included; i+1 excluded",
            "control": list(CONTROL_DEPTHS),
            "fibonacci": list(FIB_DEPTHS),
            "placebo_seed": PLACEBO_SEED,
            "placebo_n": PLACEBO_N,
            "placebo": list(PLACEBO_DEPTHS),
            "neighbors": {str(k): list(v) for k, v in NEIGHBORS.items()},
            "neighbor_r_margin": NEIGHBOR_R_MARGIN,
            "tolerance": "none; qualify on retrace_fraction >= depth",
            "direction_source": "EMA50/200 state; depth never sets BUY/SELL",
        },
        "cuts": {"train_le": str(cuts["cut_50"]), "valid_le": str(cuts["cut_75"])},
        "book_coverage": {
            s: {
                "rows": int(len(src)),
                "bid_close_finite": int(pd.to_numeric(src["bid_close"], errors="coerce").notna().sum()),
            }
            for s, src in raw.items()
        },
        "configs": configs,
        "by_depth": {str(k): v for k, v in by_depth.items()},
        "fib_vs_neighbor": neighbors,
        "conclusion_code": conclusion,
        "conclusion": labels[conclusion],
    }
