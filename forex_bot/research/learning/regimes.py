"""Research-only regime detector and strategy comparison. Not a production voter."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.research.learning.protocol import BAR_SECONDS, canonical_hash
from forex_bot.research.learning.supervised import block_interval

RESEARCH_ONLY = True
PRODUCTION_AUTHORISED = False
LOOKBACK = 48
HALF = 24
MA_FAST = 5
MA_SLOW = 20
ATR_PERIOD = 14
BREAKOUT_BARS = 20
HOLD_BARS = 12
EFFICIENCY_TREND = 0.35
EFFICIENCY_RANGE = 0.20
TREND_MOVE_IN_SPREADS = 2.0
RANGE_WIDTH_IN_SPREADS = 4.0
BREAKOUT_BUFFER_IN_SPREADS = 0.5
RANGE_EDGE_FRACTION = 0.25
MIN_REWARD_TO_RISK = 1.0
MIN_REWARD_IN_SPREADS = 2.0
PIP_SIZE = {
    "AUD_USD": 0.0001,
    "EUR_USD": 0.0001,
    "GBP_USD": 0.0001,
    "USD_CAD": 0.0001,
    "USD_CHF": 0.0001,
    "USD_JPY": 0.01,
}
DATASET_SHA256 = {
    "AUD_USD": "e639a1f817e4b91973ccfea0ee0c8c3dd5279c722ea665c531ad309b359165e0",
    "EUR_USD": "3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091",
    "GBP_USD": "ac3ddba51b75f493a08a5ea57e9926e38a5a85b06797de53803e6cd4f8b00d58",
    "USD_CAD": "a88eb2c440691bd5893a8317b64e6beaf87bb6f3c93b0c6e6a4cd16e53aa9c60",
    "USD_CHF": "3901a2d50a63ef5ca4d10858145cca7fd70d20d24420761e1b7d2d09f2a127bc",
    "USD_JPY": "e1b0d3491f873723967315d74e3bd5b707474814a294be4ed50a26e1b8c9805c",
}

PROTOCOL = {
    "stage": "R39",
    "detector_version": "r39.regime.v1",
    "range_version": "r39.range.v1",
    "trend_version": "r39.trend.v1",
    "breakout_version": "r39.breakout.v1",
    "selector_version": "r39.selector.v1",
    "lifecycle_version": "r39.lifecycle.v1",
    "datasets": DATASET_SHA256,
    "pip_size": PIP_SIZE,
    "primary_instrument": "EUR_USD",
    "lookback_bars": LOOKBACK,
    "ma_fast": MA_FAST,
    "ma_slow": MA_SLOW,
    "breakout_bars_excluding_current": BREAKOUT_BARS,
    "hold_bars": HOLD_BARS,
    "efficiency_trend_at_least": EFFICIENCY_TREND,
    "efficiency_range_at_most": EFFICIENCY_RANGE,
    "trend_move_in_spreads": TREND_MOVE_IN_SPREADS,
    "range_width_in_spreads": RANGE_WIDTH_IN_SPREADS,
    "breakout_buffer_in_spreads": BREAKOUT_BUFFER_IN_SPREADS,
    "range_edge_fraction": RANGE_EDGE_FRACTION,
    "min_reward_to_risk": MIN_REWARD_TO_RISK,
    "min_reward_in_spreads": MIN_REWARD_IN_SPREADS,
    "trend_stop_atr": 1.0,
    "trend_target_atr": 1.5,
    "breakout_stop_atr": 1.0,
    "breakout_target_atr": 1.5,
    "range_target": "midpoint_of_prior_range",
    "range_stop": "one_spread_outside_the_touched_boundary",
    "entry": "next_bar_open",
    "buy_entry": "ask_open",
    "buy_exit": "bid",
    "sell_entry": "bid_open",
    "sell_exit": "ask",
    "ambiguous_intrabar": "count_as_stop",
    "one_position_per_strategy_stream": True,
    "train_end_exclusive": "2026-03-01T00:00:00Z",
    "confirmation_start": "2026-05-01T00:00:00Z",
    "mapping": {"TREND": "trend", "RANGE": "range", "BREAKOUT": "breakout", "UNCERTAIN": "NO_TRADE"},
    "bootstrap": {"block_trades": 5, "reps": 200, "seed": 3901},
    "minimum_confirmation_trades": 30,
    "acceptance": "confirmation_mean_above_zero_and_bootstrap_low_above_zero_and_half_pip_mean_above_zero_and_at_least_30_trades_and_positive_mean_on_at_least_3_other_instruments",
    "thresholds_fit_on_evaluation_data": False,
    "maximum_configurations": 4,
    "production_authorised": False,
    "r30_simulator_modified": False,
}

PROTOCOL_SHA256 = canonical_hash(PROTOCOL)


def promotion_allowed() -> bool:
    return False


def reward_to_risk(entry: float, stop: float, target: float, direction: int) -> float | None:
    if direction == 1:
        risk = entry - stop
        reward = target - entry
    elif direction == -1:
        risk = stop - entry
        reward = entry - target
    else:
        return None
    if risk <= 0.0 or reward <= 0.0:
        return None
    return reward / risk


def _contiguous(time_ns: np.ndarray, steps: int) -> np.ndarray:
    ok = np.zeros(len(time_ns), dtype=bool)
    ok[1:] = np.diff(time_ns) == BAR_SECONDS * 1_000_000_000
    rolled = pd.Series(ok).rolling(steps).sum().to_numpy()
    return rolled == steps


def classify_regimes(mid: np.ndarray, high: np.ndarray, low: np.ndarray, spread: np.ndarray, time_ns: np.ndarray) -> np.ndarray:
    """Label each completed bar. Range and breakout boundaries exclude the current bar."""
    price = pd.Series(mid)
    prior_high = pd.Series(high).shift(1).rolling(LOOKBACK).max().to_numpy()
    prior_low = pd.Series(low).shift(1).rolling(LOOKBACK).min().to_numpy()
    net = (price - price.shift(LOOKBACK - 1)).abs().to_numpy()
    path = price.diff().abs().rolling(LOOKBACK - 1).sum().to_numpy()
    efficiency = np.divide(net, path, out=np.full(len(mid), np.nan), where=path > 0)
    move = (price - price.shift(LOOKBACK - 1)).to_numpy()
    roll_high = pd.Series(high).rolling(HALF).max()
    roll_low = pd.Series(low).rolling(HALF).min()
    up_structure = ((roll_high > roll_high.shift(HALF)) & (roll_low > roll_low.shift(HALF))).to_numpy()
    down_structure = ((roll_high < roll_high.shift(HALF)) & (roll_low < roll_low.shift(HALF))).to_numpy()
    finite = np.isfinite(mid) & np.isfinite(high) & np.isfinite(low) & np.isfinite(spread) & (spread >= 0)
    valid = _contiguous(time_ns, LOOKBACK) & finite & np.isfinite(prior_high) & np.isfinite(prior_low) & np.isfinite(efficiency)
    width = prior_high - prior_low
    breakout = valid & ((mid > prior_high + BREAKOUT_BUFFER_IN_SPREADS * spread) | (mid < prior_low - BREAKOUT_BUFFER_IN_SPREADS * spread))
    trend = valid & ~breakout & (efficiency >= EFFICIENCY_TREND) & (np.abs(move) >= TREND_MOVE_IN_SPREADS * spread)
    trend = trend & (((move > 0) & up_structure) | ((move < 0) & down_structure))
    ranging = valid & ~breakout & ~trend & (efficiency <= EFFICIENCY_RANGE) & (width >= RANGE_WIDTH_IN_SPREADS * spread)
    labels = np.full(len(mid), "UNCERTAIN", dtype=object)
    labels[ranging] = "RANGE"
    labels[trend] = "TREND"
    labels[breakout] = "BREAKOUT"
    return labels


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev = np.roll(close, 1)
    prev[0] = np.nan
    true_range = np.nanmax(np.vstack([high - low, np.abs(high - prev), np.abs(low - prev)]), axis=0)
    return pd.Series(true_range).rolling(ATR_PERIOD).mean().to_numpy()


def strategy_signals(mid: np.ndarray, open_: np.ndarray, high: np.ndarray, low: np.ndarray, spread: np.ndarray) -> dict[str, np.ndarray]:
    """BUY=1, SELL=-1, flat=0. The current bar is not part of a breakout or range boundary."""
    close = pd.Series(mid)
    fast = close.rolling(MA_FAST).mean().to_numpy()
    slow = close.rolling(MA_SLOW).mean().to_numpy()
    atr = _atr(high, low, mid)
    prior_high_20 = pd.Series(high).shift(1).rolling(BREAKOUT_BARS).max().to_numpy()
    prior_low_20 = pd.Series(low).shift(1).rolling(BREAKOUT_BARS).min().to_numpy()
    prior_high = pd.Series(high).shift(1).rolling(LOOKBACK).max().to_numpy()
    prior_low = pd.Series(low).shift(1).rolling(LOOKBACK).min().to_numpy()
    path = close.diff().abs().rolling(LOOKBACK - 1).sum().to_numpy()
    net = (close - close.shift(LOOKBACK - 1)).abs().to_numpy()
    efficiency = np.divide(net, path, out=np.full(len(mid), np.nan), where=path > 0)
    trend = np.zeros(len(mid), dtype=np.int8)
    finite_ma = np.isfinite(fast) & np.isfinite(slow)
    trend[finite_ma & (fast > slow) & (mid >= fast)] = 1
    trend[finite_ma & (fast < slow) & (mid <= fast)] = -1
    breakout = np.zeros(len(mid), dtype=np.int8)
    breakout[np.isfinite(prior_high_20) & (mid > prior_high_20)] = 1
    breakout[np.isfinite(prior_low_20) & (mid < prior_low_20)] = -1
    width = prior_high - prior_low
    span = np.divide(mid - prior_low, width, out=np.full(len(mid), np.nan), where=width > 0)
    range_ok = np.isfinite(span) & np.isfinite(efficiency) & (efficiency <= EFFICIENCY_RANGE) & (width >= RANGE_WIDTH_IN_SPREADS * spread)
    inside = (mid > prior_low) & (mid < prior_high)
    buy = range_ok & inside & (span <= RANGE_EDGE_FRACTION) & (mid > open_)
    sell = range_ok & inside & (span >= 1.0 - RANGE_EDGE_FRACTION) & (mid < open_)
    ranging = np.zeros(len(mid), dtype=np.int8)
    ranging[buy & ~sell] = 1
    ranging[sell & ~buy] = -1
    return {"trend": trend, "breakout": breakout, "range": ranging, "atr": atr, "prior_high": prior_high, "prior_low": prior_low}


def select_signals(regimes: np.ndarray, signals: dict[str, np.ndarray]) -> np.ndarray:
    chosen = np.zeros(len(regimes), dtype=np.int8)
    for name, label in (("trend", "TREND"), ("range", "RANGE"), ("breakout", "BREAKOUT")):
        mask = regimes == label
        chosen[mask] = signals[name][mask]
    chosen[regimes == "UNCERTAIN"] = 0
    return chosen


def _levels(direction: int, entry: float, atr: float, support: float, resistance: float, spread: float, kind: str) -> tuple[float, float] | None:
    if kind == "range":
        if not np.isfinite(support) or not np.isfinite(resistance) or resistance <= support:
            return None
        midpoint = (support + resistance) / 2.0
        stop, target = (support - spread, midpoint) if direction == 1 else (resistance + spread, midpoint)
    else:
        if not np.isfinite(atr) or atr <= 0.0:
            return None
        stop, target = (entry - atr, entry + 1.5 * atr) if direction == 1 else (entry + atr, entry - 1.5 * atr)
    ratio = reward_to_risk(entry, stop, target, direction)
    if ratio is None or ratio < MIN_REWARD_TO_RISK or abs(target - entry) < MIN_REWARD_IN_SPREADS * spread:
        return None
    return stop, target


def simulate(direction, kind, *, time_ns, bid_open, ask_open, bid_high, bid_low, ask_high, ask_low, bid_close, ask_close, spread, atr, support, resistance, pip, extra_pips_per_side=0.0, allowed=None) -> dict:
    """One position at a time. A bar that touches both stop and target is booked at the stop."""
    n = len(direction)
    trades = []
    rejected = {"cost_filter": 0, "gap": 0, "entry_invalid": 0}
    excluded = {"gap_unevaluable": 0, "unresolved": 0}
    index = LOOKBACK
    step = BAR_SECONDS * 1_000_000_000
    while index < n - 1:
        side = int(direction[index])
        if side == 0 or (allowed is not None and not bool(allowed[index])):
            index += 1
            continue
        entry_at = index + 1
        if int(time_ns[entry_at]) - int(time_ns[index]) != step:
            rejected["gap"] += 1
            index += 1
            continue
        entry = float(ask_open[entry_at] if side == 1 else bid_open[entry_at])
        rule = kind[index] if isinstance(kind, np.ndarray) else kind
        levels = _levels(side, entry, float(atr[index]), float(support[index]), float(resistance[index]), float(spread[index]), str(rule))
        if levels is None or entry <= 0.0:
            rejected["cost_filter"] += 1
            index += 1
            continue
        stop, target = levels
        if (side == 1 and (entry <= stop or entry >= target)) or (side == -1 and (entry >= stop or entry <= target)):
            rejected["entry_invalid"] += 1
            index += 1
            continue
        exit_price = None
        exit_at = entry_at
        outcome = None
        last = min(n - 1, entry_at + HOLD_BARS - 1)
        for cursor in range(entry_at, last + 1):
            if cursor > entry_at and int(time_ns[cursor]) - int(time_ns[cursor - 1]) != step:
                outcome = "gap_unevaluable"
                exit_at = cursor
                break
            if side == 1:
                hit_stop = float(bid_low[cursor]) <= stop
                hit_target = float(bid_high[cursor]) >= target
                bar_open = float(bid_open[cursor])
                opened_through_stop = bar_open < stop
                opened_through_target = bar_open > target
            else:
                hit_stop = float(ask_high[cursor]) >= stop
                hit_target = float(ask_low[cursor]) <= target
                bar_open = float(ask_open[cursor])
                opened_through_stop = bar_open > stop
                opened_through_target = bar_open < target
            if hit_stop and hit_target:
                outcome = "ambiguous_intrabar"
                exit_price = stop
                exit_at = cursor
                break
            if hit_stop:
                outcome = "stop"
                exit_price = bar_open if opened_through_stop else stop
                exit_at = cursor
                break
            if hit_target:
                outcome = "target"
                exit_price = bar_open if opened_through_target else target
                exit_at = cursor
                break
        if outcome is None:
            outcome = "unresolved" if last < entry_at + HOLD_BARS - 1 else "timeout"
            exit_at = last
            if outcome == "timeout":
                exit_price = float(bid_close[last] if side == 1 else ask_close[last])
        if outcome in {"gap_unevaluable", "unresolved"} or exit_price is None:
            excluded[outcome] = excluded.get(outcome, 0) + 1
            trades.append({"decision": index, "outcome": outcome, "included": False})
            index = n if outcome == "unresolved" else exit_at + 1
            continue
        extra = extra_pips_per_side * pip
        net = ((exit_price - extra) - (entry + extra)) / entry if side == 1 else ((entry - extra) - (exit_price + extra)) / entry
        trades.append({"decision": index, "outcome": outcome, "included": True, "net": float(net), "direction": side, "exit_at": int(exit_at)})
        index = int(exit_at) + 1
    included = [row for row in trades if row["included"]]
    return {
        "trades": included,
        "rejected": rejected,
        "returns": np.array([row["net"] for row in included], dtype=float),
        "ambiguous": sum(row["outcome"] == "ambiguous_intrabar" for row in included),
        "outcomes": {name: sum(row["outcome"] == name for row in included) for name in ("stop", "target", "timeout", "ambiguous_intrabar")},
        "excluded": excluded,
    }


def summarise(returns: np.ndarray, *, ambiguous: int) -> dict:
    if len(returns) == 0:
        return {"n": 0, "mean": None, "bootstrap_low": None, "bootstrap_high": None, "win_rate": None, "profit_factor": None, "max_drawdown": None, "average_win": None, "average_loss": None, "ambiguous": ambiguous}
    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    equity = np.cumsum(returns)
    peak = np.maximum.accumulate(equity)
    interval = block_interval(returns, block=5, reps=200, seed=3901) if len(returns) >= 10 else None
    return {
        "n": int(len(returns)),
        "mean": float(returns.mean()),
        "bootstrap_low": None if interval is None else interval["low"],
        "bootstrap_high": None if interval is None else interval["high"],
        "win_rate": float((returns > 0).mean()),
        "profit_factor": None if len(losses) == 0 or losses.sum() == 0 else float(wins.sum() / abs(losses.sum())),
        "average_win": None if len(wins) == 0 else float(wins.mean()),
        "average_loss": None if len(losses) == 0 else float(losses.mean()),
        "max_drawdown": float((peak - equity).max()),
        "ambiguous": int(ambiguous),
    }


def merits(confirmation: dict, half_pip: dict, other_means: list[float]) -> bool:
    if confirmation["n"] < PROTOCOL["minimum_confirmation_trades"] or half_pip["n"] < PROTOCOL["minimum_confirmation_trades"]:
        return False
    values = (confirmation["mean"], confirmation["bootstrap_low"], half_pip["mean"])
    if any(value is None or value <= 0.0 for value in values):
        return False
    return sum(value > 0.0 for value in other_means) >= 3
