"""Stable shadow reason codes. Never reported as live broker orders."""

from __future__ import annotations

from enum import StrEnum


class ShadowReason(StrEnum):
    NO_SIGNAL = "NO_SIGNAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STALE_DATA = "STALE_DATA"
    QUANT_REJECT = "QUANT_REJECT"
    SESSION_REJECT = "SESSION_REJECT"
    RISK_REJECT = "RISK_REJECT"
    SPREAD_REJECT = "SPREAD_REJECT"
    SIZE_INFEASIBLE = "SIZE_INFEASIBLE"
    SHADOW_ENTRY = "SHADOW_ENTRY"
    SHADOW_EXIT = "SHADOW_EXIT"
    SHADOW_DISABLED = "SHADOW_DISABLED"
    ALREADY_OPEN = "ALREADY_OPEN"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"
    CONCURRENT_LIMIT = "CONCURRENT_LIMIT"
    USD_CONCENTRATION = "USD_CONCENTRATION"
    DUPLICATE_BAR = "DUPLICATE_BAR"
    NOT_REPRODUCIBLE = "NOT_REPRODUCIBLE"
    PARTIALLY_REPRODUCIBLE = "PARTIALLY_REPRODUCIBLE"
    EXPERIMENTAL_HEURISTIC = "EXPERIMENTAL_HEURISTIC"


STRATEGY_NAMES: tuple[str, ...] = (
    "scalp",
    "trend",
    "mean_reversion",
    "swing_trend",
    "swing_mean_reversion",
    "swing_breakout",
)

SCALP_FAMILY: frozenset[str] = frozenset({"scalp", "trend", "mean_reversion"})
SWING_FAMILY: frozenset[str] = frozenset(
    {"swing_trend", "swing_mean_reversion", "swing_breakout"}
)
