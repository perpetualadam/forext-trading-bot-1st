"""Apply the frozen R.31 screening gate. This module does not read market data."""

from __future__ import annotations

from typing import Any

MIN_TRADES = 100
MAX_DRAWDOWN = 0.25


def _factor_passes(summary: dict[str, Any]) -> bool:
    factor = summary.get("profit_factor")
    if isinstance(factor, (int, float)) and not isinstance(factor, bool) and factor > 1:
        return True
    # The simulator omits the factor when there is no losing trade.
    return factor is None and float(summary.get("pnl") or 0) > 0 and int(summary.get("trades") or 0) > 0


def assess(spread_in: dict[str, Any], spread_out: dict[str, Any], slipped_out: dict[str, Any]) -> dict[str, Any]:
    """Return the rejection list. An empty list is the only pass."""
    reasons: list[str] = []
    if int(spread_in.get("trades") or 0) < MIN_TRADES:
        reasons.append("in_sample_trade_count")
    if int(spread_out.get("trades") or 0) < MIN_TRADES:
        reasons.append("out_of_sample_trade_count")
    if float(spread_in.get("pnl") or 0) <= 0:
        reasons.append("in_sample_pnl")
    if float(spread_out.get("pnl") or 0) <= 0:
        reasons.append("out_of_sample_pnl")
    if not _factor_passes(spread_in):
        reasons.append("in_sample_profit_factor")
    if not _factor_passes(spread_out):
        reasons.append("out_of_sample_profit_factor")
    if float(spread_in.get("max_drawdown_fraction") or 1) >= MAX_DRAWDOWN:
        reasons.append("in_sample_drawdown")
    if float(spread_out.get("max_drawdown_fraction") or 1) >= MAX_DRAWDOWN:
        reasons.append("out_of_sample_drawdown")
    if float(slipped_out.get("pnl") or 0) <= 0 or not _factor_passes(slipped_out):
        reasons.append("slippage_out_of_sample")
    return {"merits_validation": not reasons, "rejections": reasons}


def order_passes(rows: list[dict[str, Any]]) -> list[str]:
    """Order only the names that passed. Profit factor, then lower drawdown."""
    passed = [row for row in rows if row.get("merits_validation")]
    def _factor(row: dict[str, Any]) -> float:
        value = row.get("out_of_sample_profit_factor")
        if value is None:
            return float("inf")
        return float(value)

    passed.sort(key=lambda row: (-_factor(row), float(row["out_of_sample_drawdown"]), str(row["strategy"])))
    return [str(row["strategy"]) for row in passed]
