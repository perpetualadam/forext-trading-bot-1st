"""Frozen R.32 calculations. This module does not read market files or place orders."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np

HORIZONS = (1, 6, 12, 48)
PRIMARY_HORIZON = 12
BLOCK_LENGTH = 20
PERMUTATIONS = 200
BOOTSTRAP_REPLICATES = 400
MIN_QUARTER_EVENTS = 30
PIP = 0.0001
SUM_TOLERANCE = 1e-4
TRADE_TOLERANCE = 1e-6
ORDER_REASONS = frozenset({"stop", "take_profit", "ambiguous_stop"})
QUOTE_REASONS = frozenset(
    {
        "signal_reversal",
        "gap_exit",
        "weekend_flatten",
        "market_closed",
        "end_of_data",
        "stop_gap",
        "take_profit_gap",
    }
)
WINDOWS = (
    ("2025-09_2025-11", datetime(2025, 9, 1, tzinfo=timezone.utc), datetime(2025, 12, 1, tzinfo=timezone.utc)),
    ("2025-12_2026-02", datetime(2025, 12, 1, tzinfo=timezone.utc), datetime(2026, 3, 1, tzinfo=timezone.utc)),
    ("2026-03_2026-05", datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 6, 1, tzinfo=timezone.utc)),
    ("2026-06_2026-08", datetime(2026, 6, 1, tzinfo=timezone.utc), datetime(2026, 9, 1, tzinfo=timezone.utc)),
)
SEEDS = {
    "mean_reversion": {"shuffle": 32001, "coin": 32101, "bootstrap": 32201},
    "swing_mean_reversion": {"shuffle": 32002, "coin": 32102, "bootstrap": 32202},
}


def _seconds(delta: Any) -> float:
    if hasattr(delta, "total_seconds"):
        return float(delta.total_seconds())
    return float(delta / np.timedelta64(1, "s"))


def attribute_trade(trade: dict[str, Any]) -> dict[str, Any]:
    """Split one spread-only trade into price movement and execution difference."""
    direction = str(trade["direction"])
    units = float(trade["units"])
    entry = float(trade["entry_price"])
    exit_price = float(trade["exit_price"])
    entry_mid = float(trade["entry_mid"])
    exit_mid = float(trade["exit_mid"])
    if direction == "BUY":
        price = (exit_mid - entry_mid) * units
        quoted = (exit_price - entry) * units
        entry_half = entry - entry_mid
        exit_half = exit_mid - exit_price
    elif direction == "SELL":
        price = (entry_mid - exit_mid) * units
        quoted = (entry - exit_price) * units
        entry_half = entry_mid - entry
        exit_half = exit_price - exit_mid
    else:
        raise ValueError(f"unknown direction {direction}")
    reason = str(trade["exit_reason"])
    if reason in ORDER_REASONS:
        spread = -entry_half * units
        exit_observed = False
    elif reason in QUOTE_REASONS:
        spread = -(entry_half + exit_half) * units
        exit_observed = True
    else:
        raise ValueError(f"unknown exit reason {reason}")
    execution = quoted - price
    return {
        "price_movement": price,
        "quoted": quoted,
        "execution_difference": execution,
        "spread_component": spread,
        "residual": execution - spread,
        "exit_spread_observed": exit_observed,
        "entry_half": entry_half,
        "exit_half": exit_half,
    }


def totals_match(actual: float, expected: float, tolerance: float = SUM_TOLERANCE) -> bool:
    return abs(actual - expected) <= tolerance


def horizon_complete(times: Sequence[Any], index: int, horizon: int) -> bool:
    """True when bar index+horizon is exactly horizon * 5 minutes later."""
    target = index + horizon
    if target >= len(times):
        return False
    return abs(_seconds(times[target] - times[index]) - 300.0 * horizon) < 1e-6


def window_is_uniform(times: Sequence[Any], index: int, horizon: int) -> bool:
    """True when every step inside the horizon is exactly five minutes."""
    for step in range(horizon):
        if abs(_seconds(times[index + step + 1] - times[index + step]) - 300.0) >= 1e-6:
            return False
    return True


def select_nonoverlapping(events: Sequence[int], horizon: int, complete) -> list[int]:
    """Keep events whose horizon windows do not overlap. `complete(index, horizon)` is required."""
    chosen: list[int] = []
    next_free = 0
    for index in events:
        if index < next_free:
            continue
        if not complete(index, horizon):
            continue
        chosen.append(int(index))
        next_free = int(index) + horizon
    return chosen


def direction_adjusted(direction: str, origin: float, future: float) -> float:
    if direction == "BUY":
        return future - origin
    if direction == "SELL":
        return origin - future
    raise ValueError(f"unknown direction {direction}")


def adjusted_array(raw_moves: Sequence[float], directions: Sequence[str]) -> np.ndarray:
    raw = np.asarray(raw_moves, dtype=float)
    signs = np.array([1.0 if direction == "BUY" else -1.0 for direction in directions], dtype=float)
    if raw.shape != signs.shape:
        raise ValueError("directions do not match returns")
    return raw * signs


def summarize_returns(values: Sequence[float]) -> dict[str, Any]:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "positive_frequency": None,
            "percentiles": {},
            "mean_positive": None,
            "mean_negative": None,
            "std": None,
        }
    positives = array[array > 0]
    negatives = array[array < 0]
    return {
        "count": int(array.size),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "positive_frequency": float(np.mean(array > 0)),
        "percentiles": {str(point): float(np.percentile(array, point)) for point in (10, 25, 50, 75, 90)},
        "mean_positive": float(positives.mean()) if positives.size else None,
        "mean_negative": float(negatives.mean()) if negatives.size else None,
        "std": float(array.std(ddof=1)) if array.size > 1 else None,
    }


def _generator(seed: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(seed))


def shuffle_means(raw_moves: Sequence[float], directions: Sequence[str], seed: int, draws: int = PERMUTATIONS) -> np.ndarray:
    """Permute the observed labels. The paths and the buy/sell counts stay fixed."""
    rng = _generator(seed)
    labels = np.asarray(list(directions))
    raw = np.asarray(list(raw_moves), dtype=float)
    means = np.empty(draws, dtype=float)
    for index in range(draws):
        means[index] = float(np.mean(adjusted_array(raw, labels[rng.permutation(labels.size)])))
    return means


def coin_means(raw_moves: Sequence[float], seed: int, draws: int = PERMUTATIONS) -> np.ndarray:
    """Independent fair coin. Zero is SELL and one is BUY."""
    rng = _generator(seed)
    raw = np.asarray(list(raw_moves), dtype=float)
    means = np.empty(draws, dtype=float)
    for index in range(draws):
        draw = rng.integers(0, 2, size=raw.size)
        labels = np.where(draw == 1, "BUY", "SELL")
        means[index] = float(np.mean(adjusted_array(raw, labels)))
    return means


def linear_percentile(values: Sequence[float], point: float) -> float:
    return float(np.percentile(np.asarray(list(values), dtype=float), point, method="linear"))


def block_interval(
    values: Sequence[float],
    seed: int,
    block: int = BLOCK_LENGTH,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> tuple[float, float] | None:
    """Percentile interval from non-wrapping blocks. None when the sample is shorter than one block."""
    array = np.asarray(list(values), dtype=float)
    count = int(array.size)
    if count < block:
        return None
    rng = _generator(seed)
    blocks = int(math.ceil(count / block))
    means = np.empty(replicates, dtype=float)
    for index in range(replicates):
        starts = rng.integers(0, count - block + 1, size=blocks)
        sample = np.concatenate([array[start : start + block] for start in starts])[:count]
        means[index] = float(sample.mean())
    low, high = np.percentile(means, [2.5, 97.5], method="linear")
    return float(low), float(high)


def quarter_name(stamp: datetime) -> str | None:
    moment = stamp.astimezone(timezone.utc)
    for name, start, end in WINDOWS:
        if start <= moment < end:
            return name
    return None


def decide(
    mean: float | None,
    overlapping_mean: float | None,
    interval: tuple[float, float] | None,
    shuffle_p95: float,
    coin_p95: float,
    median_spread: float,
    quarters: Sequence[dict[str, Any]],
) -> dict[str, str]:
    """Apply the frozen first-match decision. The arguments are already computed."""
    if mean is None:
        return {"decision": "INCONCLUSIVE", "rule": "missing_primary_mean"}
    if mean <= 0:
        return {"decision": "STOP_RESEARCH", "rule": "nonpositive_mean"}
    if overlapping_mean is None:
        return {"decision": "INCONCLUSIVE", "rule": "overlapping_missing"}
    if overlapping_mean < 0:
        return {"decision": "INCONCLUSIVE", "rule": "overlapping_opposite_sign"}
    if interval is None or interval[0] <= 0:
        return {"decision": "INCONCLUSIVE", "rule": "interval_includes_zero_or_missing"}
    eligible = [row for row in quarters if int(row["count"]) >= MIN_QUARTER_EVENTS]
    positive = sum(1 for row in eligible if float(row["mean"]) > 0)
    if (
        mean > shuffle_p95
        and mean > coin_p95
        and len(eligible) >= 3
        and positive >= 3
        and mean > median_spread
    ):
        return {"decision": "CONTINUE_RESEARCH", "rule": "all_gates"}
    return {"decision": "STOP_RESEARCH", "rule": "remaining_gate"}


def excursion(frame: Any, trade: dict[str, Any]) -> dict[str, Any]:
    """Measure observed extremes. A quote exit does not use the exit bar's high or low."""
    reason = str(trade["exit_reason"])
    entry_index = int(trade["entry_index"])
    exit_index = int(trade["exit_index"])
    direction = str(trade["direction"])
    entry_price = float(trade["entry_price"])
    include_exit = reason in ORDER_REASONS or reason == "end_of_data"
    last = exit_index if include_exit else exit_index - 1
    entry_spread = float(frame["ask_open"].iloc[entry_index] - frame["bid_open"].iloc[entry_index])
    exit_spread = None
    if reason not in ORDER_REASONS:
        side = "close" if reason == "end_of_data" else "open"
        exit_spread = float(frame[f"ask_{side}"].iloc[exit_index] - frame[f"bid_{side}"].iloc[exit_index])
    if last < entry_index:
        return {
            "mfe": None,
            "mae": None,
            "empty_path": True,
            "intrabar_order_unknown": reason in ORDER_REASONS,
            "unobserved_interval": False,
            "path_bars": 0,
            "entry_spread": entry_spread,
            "exit_spread": exit_spread,
        }
    times = list(frame["_time"].iloc[entry_index : last + 1])
    unobserved = False
    for left, right in zip(times, times[1:]):
        if abs(_seconds(right - left) - 300.0) >= 1e-6:
            unobserved = True
            break
    if direction == "BUY":
        best = float(frame["bid_high"].iloc[entry_index : last + 1].max()) - entry_price
        worst = entry_price - float(frame["bid_low"].iloc[entry_index : last + 1].min())
    elif direction == "SELL":
        best = entry_price - float(frame["ask_low"].iloc[entry_index : last + 1].min())
        worst = float(frame["ask_high"].iloc[entry_index : last + 1].max()) - entry_price
    else:
        raise ValueError(f"unknown direction {direction}")
    return {
        "mfe": max(0.0, best),
        "mae": max(0.0, worst),
        "empty_path": False,
        "intrabar_order_unknown": reason in ORDER_REASONS,
        "unobserved_interval": unobserved,
        "path_bars": int(last - entry_index + 1),
        "entry_spread": entry_spread,
        "exit_spread": exit_spread,
    }
