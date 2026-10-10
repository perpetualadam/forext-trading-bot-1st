"""Unvalidated multi-pair scaffolding. Not a profitability engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forex_bot.research.adaptive_ensemble.protocol import PROTOCOL

PAIRS = list(PROTOCOL["pairs"])
READINESS = "MULTI_PAIR_VALIDATION_NOT_READY"


@dataclass
class PortfolioLimits:
    max_open_positions: int = 2
    max_shared_usd_units: float = 2000.0
    start_nav_gbp: float = 97.0


@dataclass
class OpenSlot:
    pair: str
    direction: str
    units: float
    usd_sign: int


@dataclass
class PortfolioState:
    nav: float
    peak: float
    open: dict[str, OpenSlot] = field(default_factory=dict)
    realised_gbp: float | None = None
    halted: str | None = None
    conversion_status: str = "GBP_CONVERSION_UNVERIFIED"


def usd_sign(pair: str, direction: str) -> int:
    """Long USD is +1. XXX_USD BUY is short USD; USD_YYY BUY is long USD."""
    buy = direction == "BUY"
    if pair.endswith("_USD"):
        return -1 if buy else 1
    if pair.startswith("USD_"):
        return 1 if buy else -1
    return 0


def can_open(state: PortfolioState, limits: PortfolioLimits, pair: str, direction: str, units: float) -> str | None:
    if pair in state.open:
        return "duplicate_pair_exposure"
    if pair not in PAIRS:
        return "unknown_pair"
    if len(state.open) >= limits.max_open_positions:
        return "position_cap"
    signed = usd_sign(pair, direction) * units
    current = sum(s.usd_sign * s.units for s in state.open.values())
    if abs(current + signed) > limits.max_shared_usd_units:
        return "shared_usd_cap"
    return None


def align_clocks(pair_times: dict[str, list[str]]) -> dict[str, Any]:
    sets = {p: set(ts) for p, ts in pair_times.items()}
    if not sets:
        return {"status": "UNAVAILABLE", "intersection": 0}
    inter = set.intersection(*sets.values()) if sets else set()
    union = set.union(*sets.values()) if sets else set()
    missing = {p: sorted(union - s)[:5] for p, s in sets.items()}
    return {
        "status": "ok" if inter else "misaligned",
        "intersection_n": len(inter),
        "union_n": len(union),
        "missing_examples": missing,
        "tie_break_order": list(PAIRS),
    }


def readiness_assessment() -> dict[str, Any]:
    return {
        "status": READINESS,
        "pairs_supported_inventory": PAIRS,
        "cross_pair_clock_alignment": "helper_only",
        "shared_currency_exposure": "usd_sign_cap_unvalidated",
        "capital_allocation": "NOT_IMPLEMENTED_equal_units_only",
        "portfolio_nav": "blocked_on_GBP_CONVERSION_UNVERIFIED",
        "portfolio_risk_constraints": "scaffolding_caps_only",
        "pending_candidate_ordering": "protocol pair list",
        "deterministic_tie_break": "protocol pair list then candidate id",
        "missing_pair_data": "skip pair; do not invent bars",
        "optimiser": "none",
        "reason": (
            "Architecture stubs exist, but six-pair evaluation cannot be reported: "
            "no independent post-2026-08-31 dataset, conversion rates unverified, "
            "and portfolio caps are unvalidated research scaffolding."
        ),
    }
