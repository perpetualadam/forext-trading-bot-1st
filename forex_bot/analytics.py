"""Performance analytics."""

from __future__ import annotations

import numpy as np


class Analytics:
    def __init__(self) -> None:
        self.trades: list[float] = []

    def log_trade(self, pnl: float) -> None:
        self.trades.append(pnl)

    def returns(self) -> np.ndarray:
        return np.array(self.trades, dtype=float)

    def sharpe(self) -> float:
        r = self.returns()
        if len(r) <= 10:
            return 0.0
        std = r.std()
        return float(r.mean() / (std + 1e-6))

    def winrate(self) -> float:
        r = self.returns()
        if len(r) == 0:
            return 0.0
        return float(np.sum(r > 0) / len(r))

    def drawdown(self) -> float:
        if not self.trades:
            return 0.0
        eq = np.cumsum(self.trades)
        peak = np.maximum.accumulate(eq)
        return float(np.max(peak - eq))


analytics = Analytics()
