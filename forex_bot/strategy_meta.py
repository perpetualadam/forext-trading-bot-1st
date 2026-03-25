"""Named strategies, meta-learner weights, and sequence trend model."""

from __future__ import annotations

import logging
import random

import numpy as np

logger = logging.getLogger(__name__)


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


strategies: dict[str, Strategy] = {
    s: Strategy(s) for s in ("scalp", "trend", "mean_reversion")
}


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


def select_strategy() -> str | None:
    weights = allocate()
    if not weights:
        return None
    names = list(weights.keys())
    probs = list(weights.values())
    s = sum(probs)
    if s <= 0:
        return random.choice(names)
    probs = [p / s for p in probs]
    return str(np.random.choice(names, p=probs))
