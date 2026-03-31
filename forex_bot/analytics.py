"""Performance analytics."""

from __future__ import annotations

import numpy as np

from forex_bot.config import Config


class Analytics:
    def __init__(self) -> None:
        self.trades: list[float] = []

    def log_trade(self, pnl: float) -> None:
        self.trades.append(pnl)

    def returns(self) -> np.ndarray:
        return np.array(self.trades, dtype=float)

    def sharpe(self) -> float:
        """
        Mean trade PnL divided by std dev of trade PnLs (not annualized Sharpe).

        With few trades or tiny variance this is noisy; treat as a rough score, not a fund Sharpe.
        """
        r = self.returns()
        if len(r) <= 10:
            return 0.0
        std = r.std()
        return float(r.mean() / (std + 1e-6))

    def winrate(self) -> float:
        """
        Fraction of closed trades with strictly positive PnL, in ``[0, 1]``.

        Example: ``0.54`` means **54%** wins — not 0.54%. Use :meth:`win_rate_pct` for 0–100.
        """
        r = self.returns()
        if len(r) == 0:
            return 0.0
        return float(np.sum(r > 0) / len(r))

    def win_rate_pct(self) -> float:
        """Win rate as a percentage number in ``[0, 100]`` (e.g. ``54.0`` for 54%)."""
        return float(self.winrate() * 100.0)

    def avg_win(self) -> float:
        """Mean PnL of winning trades (0 if none)."""
        r = self.returns()
        wins = r[r > 0]
        return float(np.mean(wins)) if len(wins) else 0.0

    def avg_loss(self) -> float:
        """Mean PnL of losing trades (negative; 0 if none)."""
        r = self.returns()
        losses = r[r < 0]
        return float(np.mean(losses)) if len(losses) else 0.0

    def profit_factor(self) -> float | None:
        """
        Gross profit / gross loss (absolute). ``None`` if there are no losses (infinite or undefined).
        Values above 1.0 mean gross wins exceed gross losses.
        """
        r = self.returns()
        gp = float(np.sum(r[r > 0]))
        gl = float(np.sum(r[r < 0]))
        gross_loss = abs(gl)
        if gross_loss < 1e-12:
            return None if gp <= 1e-12 else float("inf")
        return gp / gross_loss

    def drawdown(self) -> float:
        """
        Maximum peak-to-trough drop of **equity** (same units as :func:`forex_bot.state.current_equity`).

        Uses ``Config.BASE_BALANCE + cumulative trade PnL`` after each closed trade. The previous
        implementation used ``cumsum(trades)`` only (no starting balance), which **did not** match
        equity and could disagree badly with reported equity / drawdown intuition.
        """
        if not self.trades:
            return 0.0
        initial = float(Config.BASE_BALANCE)
        eq = initial + np.cumsum(np.array(self.trades, dtype=float))
        peak = np.maximum.accumulate(eq)
        return float(np.max(peak - eq))


analytics = Analytics()
