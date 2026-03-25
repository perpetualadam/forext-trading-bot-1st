"""Lightweight tabular RL hook (bandit-style Q updates per discrete state)."""

from __future__ import annotations

import random
from typing import Any

_ACTIONS = ("BUY", "SELL", "SKIP")


class RLAgent:
    def __init__(
        self,
        *,
        alpha: float = 0.15,
        epsilon: float = 0.25,
    ) -> None:
        self.q: dict[str, dict[str, float]] = {}
        self.alpha = alpha
        self.epsilon = epsilon

    def _ensure_state(self, state: str) -> dict[str, float]:
        if state not in self.q:
            self.q[state] = {a: 0.0 for a in _ACTIONS}
        return self.q[state]

    def decide(self, state: str) -> str:
        table = self._ensure_state(state)
        if random.random() < self.epsilon:
            return random.choice(_ACTIONS)
        best = max(table.values())
        candidates = [a for a, v in table.items() if v == best]
        return random.choice(candidates)

    def update(self, state: str, action: str, reward: float) -> None:
        if action not in _ACTIONS:
            return
        table = self._ensure_state(state)
        old = table[action]
        table[action] = old + self.alpha * (reward - old)

    def snapshot(self) -> dict[str, Any]:
        return {"states": len(self.q), "epsilon": self.epsilon}
