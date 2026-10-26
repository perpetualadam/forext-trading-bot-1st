"""Lightweight tabular RL hook. An unverified table cannot approve a direction."""

from __future__ import annotations

import math
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
        self.persisted_ok = False

    def _ensure_state(self, state: str) -> dict[str, float]:
        if state not in self.q:
            self.q[state] = {a: 0.0 for a in _ACTIONS}
        return self.q[state]

    def decide(self, state: str) -> str:
        """Return one learned action, or UNAVAILABLE when the policy is not verified.

        ``persisted_ok`` stays false until a caller has loaded a real policy.
        This method does not create that flag and does not sample a random action.
        """
        if not self.persisted_ok:
            return "UNAVAILABLE"
        table = self.q.get(state)
        if not isinstance(table, dict):
            return "UNAVAILABLE"
        scored: dict[str, float] = {}
        for action in _ACTIONS:
            if action not in table:
                return "UNAVAILABLE"
            try:
                value = float(table[action])
            except (TypeError, ValueError):
                return "UNAVAILABLE"
            if not math.isfinite(value):
                return "UNAVAILABLE"
            scored[action] = value
        if all(value == 0.0 for value in scored.values()):
            return "UNAVAILABLE"
        best = max(scored.values())
        winners = [action for action, value in scored.items() if value == best]
        if len(winners) != 1:
            return "UNAVAILABLE"
        return winners[0]

    def update(self, state: str, action: str, reward: float) -> None:
        if action not in _ACTIONS:
            return
        table = self._ensure_state(state)
        old = table[action]
        table[action] = old + self.alpha * (reward - old)

    def snapshot(self) -> dict[str, Any]:
        return {"states": len(self.q), "epsilon": self.epsilon}
