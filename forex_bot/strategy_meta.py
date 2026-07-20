"""
Strategy stack (signal path): optional hybrid ATR routing (scalp vs swing families)
→ meta-learner allocation → named strategies → sequence price model + AI ensemble vote
→ RL tabular gate (SKIP blocks; BUY/SELL must agree with AI direction) → sizing / execution.
Not a separate risk engine; risk is ``POSITION_RISK_PCT`` vs stop distance only.
"""

from __future__ import annotations

import logging
import os
import random

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Original meta-learner keys (scalp-style family)
SCALP_STRATEGY_KEYS = ("scalp", "trend", "mean_reversion")
# Swing horizon family (slower context; same meta-learner update path)
SWING_STRATEGY_KEYS = ("swing_trend", "swing_mean_reversion", "swing_breakout")


class SeqModel:
    def __init__(self, max_len: int = 50) -> None:
        self.history: dict[str, list[float]] = {}
        self._max_len = max_len

    def update(self, symbol: str, price: float) -> None:
        self.history.setdefault(symbol, []).append(price)
        if len(self.history[symbol]) > self._max_len:
            self.history[symbol].pop(0)

    def predict(self, symbol: str) -> float:
        seq = self.history.get(symbol, [])
        if len(seq) < 10:
            return seq[-1] if seq else 0.0
        x = np.arange(len(seq), dtype=float)
        trend = np.polyfit(x, np.array(seq, dtype=float), 1)[0]
        return float(seq[-1] + trend)


seq_model = SeqModel()


class Strategy:
    def __init__(self, name: str) -> None:
        self.name = name
        self.pnl: list[float] = []
        self.active = True

    def update_pnl(self, pnl: float) -> None:
        self.pnl.append(pnl)

    def sharpe(self) -> float:
        r = np.array(self.pnl, dtype=float)
        if len(r) <= 10:
            return 0.0
        return float(r.mean() / (r.std() + 1e-6))


_all_strategy_names = tuple(set(SCALP_STRATEGY_KEYS) | set(SWING_STRATEGY_KEYS))
strategies: dict[str, Strategy] = {s: Strategy(s) for s in _all_strategy_names}


class MetaLearner:
    def __init__(self) -> None:
        self.scores: dict[str, list[float]] = {}

    def update(self, strategy: str, pnl: float) -> None:
        self.scores.setdefault(strategy, []).append(pnl)

    def score(self, strategy: str) -> float:
        data = self.scores.get(strategy, [])
        if len(data) < 10:
            return 0.0
        arr = np.array(data, dtype=float)
        return float(arr.mean() / (arr.std() + 1e-6))


meta = MetaLearner()


def allocate() -> dict[str, float]:
    scores: dict[str, float] = {}
    total = 0.0
    for name, strat in strategies.items():
        if not strat.active:
            continue
        s = max(meta.score(name), 0.0)
        scores[name] = s
        total += s
    if not scores:
        return {}
    if total == 0.0:
        n = len(scores)
        return {k: 1.0 / n for k in scores}
    return {k: v / total for k, v in scores.items()}


def allocate_scoped(allowed: tuple[str, ...]) -> dict[str, float]:
    full = allocate()
    scoped = {k: v for k, v in full.items() if k in allowed}
    if not scoped:
        return {k: 1.0 / len(allowed) for k in allowed}
    t = sum(scoped.values())
    if t <= 0:
        return {k: 1.0 / len(allowed) for k in allowed}
    return {k: v / t for k, v in scoped.items()}


def _select_from_weights(weights: dict[str, float]) -> str | None:
    if not weights:
        return None
    names = list(weights.keys())
    probs = list(weights.values())
    s = sum(probs)
    if s <= 0:
        return random.choice(names)
    probs = [p / s for p in probs]
    return str(np.random.choice(names, p=probs))


def select_strategy_legacy() -> str | None:
    """Original behaviour: all strategies compete via meta-learner."""
    return _select_from_weights(allocate())


def hybrid_enabled(symbol: str) -> bool:
    env_key = f"HYBRID_{symbol.upper().strip()}"
    raw = (os.getenv(env_key) or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    return int(v) if v else default


def _env_float(name: str, default: float) -> float:
    v = (os.getenv(name) or "").strip()
    return float(v) if v else default


def select_strategy(symbol: str, routing_df: pd.DataFrame) -> tuple[str | None, int, str]:
    """
    Choose meta strategy name, indicator lookback, and horizon label.

    Returns:
        (strategy_name, lookback, horizon) where horizon is ``scalp``, ``swing``, or ``legacy``.
    """
    scalp_lb = _env_int("SCALP_LOOKBACK", 50)
    swing_lb = _env_int("SWING_LOOKBACK", 100)
    default_lb = _env_int("DEFAULT_INDICATOR_LOOKBACK", 50)

    if not hybrid_enabled(symbol):
        name = select_strategy_legacy()
        return name, default_lb, "legacy"

    if routing_df.empty or "atr" not in routing_df.columns:
        name = select_strategy_legacy()
        return name, default_lb, "legacy"

    atr_series = routing_df["atr"].dropna()
    if len(atr_series) < 5:
        name = _select_from_weights(allocate_scoped(SCALP_STRATEGY_KEYS))
        return name, scalp_lb, "scalp"

    last_atr = float(routing_df["atr"].iloc[-1])
    med_atr = float(atr_series.median())
    if med_atr <= 0 or (last_atr != last_atr):  # NaN
        name = _select_from_weights(allocate_scoped(SCALP_STRATEGY_KEYS))
        return name, scalp_lb, "scalp"

    threshold = _env_float("HYBRID_ATR_SCALP_THRESHOLD", 1.0)
    if last_atr >= med_atr * threshold:
        pool = SCALP_STRATEGY_KEYS
        lb = scalp_lb
        horizon = "scalp"
    else:
        pool = SWING_STRATEGY_KEYS
        lb = swing_lb
        horizon = "swing"

    name = _select_from_weights(allocate_scoped(pool))
    if name is None:
        name = random.choice(pool)
    return name, lb, horizon
