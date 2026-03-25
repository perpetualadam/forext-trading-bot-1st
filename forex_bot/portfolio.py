"""Portfolio weighting hook for per-symbol size scaling (Final Boss++)."""

from __future__ import annotations

from typing import Any


class PortfolioEngine:
    def __init__(self) -> None:
        self.weights: dict[str, float] = {}

    def update(self, stats: dict[str, Any]) -> None:
        """Reserved for dynamic capital allocation (drawdown, Sharpe, exposure)."""
        _ = stats
        # Placeholder: keep weights stable until optimisation rules are added.

    def get_weight(self, symbol: str) -> float:
        return float(self.weights.get(symbol, 1.0))

    def set_weight(self, symbol: str, weight: float) -> None:
        self.weights[symbol] = max(0.0, weight)
