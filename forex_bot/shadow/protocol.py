"""Prospective shadow-validation protocol (REVISED PROPOSAL ONLY).

Not frozen. Not a preregistration. Does not authorise observation, deployment,
or live trading. Stage C minima (20 days / 20 closes / beat buy-and-hold) were
proposals, not validated sample-size calculations.
"""

from __future__ import annotations

from forex_bot.shadow.config import PAIRS, ShadowConfig
from forex_bot.shadow.cost_model import COST_MODEL_VERSION
from forex_bot.shadow.reasons import STRATEGY_NAMES
from forex_bot.shadow.tracks import TRACK_A, TRACK_B

STRATEGIES = STRATEGY_NAMES
CURRENCY_PAIRS = PAIRS
CADENCE = "M5 completed bars, chronological, no future leakage"
PROTOCOL_STATUS = "PROPOSAL_NOT_FROZEN"
PROSPECTIVE_STARTED = False
PROTOCOL_FROZEN = False

# Stage C numbers retained only as the rejected baseline.
STAGE_C_MIN_DAYS = 20
STAGE_C_MIN_CLOSES_PER_STRATEGY = 20

# Revised proposal: live history had 630 broker closes over months, all six
# strategies lost, typical size 1–3 units on ~£97 NAV. 20 closes cannot
# distinguish cost noise from edge, and 6×6 cells need a multiple-comparison plan.
MIN_OBSERVATION_CALENDAR_DAYS = 90
MIN_INDEPENDENT_EVALUATION_DAYS = 60
MIN_CLOSED_TRADES_PER_STRATEGY = 100
MIN_CLOSED_TRADES_PER_STRATEGY_PAIR = 30
TRAIN_FRACTION = 0.40
TUNE_FRACTION = 0.20
EVALUATE_FRACTION = 0.40
COST_MODEL = (
    f"{COST_MODEL_VERSION}: quoted bid/ask half-spread when present; otherwise "
    "max(table half-spread, measured mean |fill-mid|) plus ATR slippage. "
    "GBP via USD then / GBPUSD (fallback 1.35 labelled estimate). "
    "Overnight financing UNAVAILABLE/unmodeled."
)
BASELINE = (
    "No-trade cash (primary). Same-window buy-and-hold per pair with the same "
    "cost/FX model (secondary). Do not treat overlapping strategy-pair cells as independent."
)
DATA_GAPS = (
    "Reject STALE_DATA / INSUFFICIENT_DATA; do not interpolate prices; "
    "count gap days against data-quality, not as silent zeros."
)
UNCERTAINTY = (
    "Report bootstrap 95% intervals on net GBP and Sharpe. Do not claim "
    "significance from small n. Apply a multiplicity correction across 6 "
    "strategies (Bonferroni or hierarchical: family then name)."
)
MAX_DRAWDOWN_BIND = "5% of frozen start NAV (shadow-only). Breach is rejection, not a tuneable target."
COST_SENSITIVITY = (
    "Re-run evaluate window at 0.5×, 1×, 2× the v2 adverse offset. "
    "A result that flips sign under 2× costs does not justify further review."
)
FREEZE_BEFORE_PROSPECTIVE = (
    "Track (A or B), ShadowConfig, signal/quant/RL rules, collision rule, "
    f"cost model {COST_MODEL_VERSION}, pair list, dataset identity hash, "
    "and this protocol version recorded before the first prospective bar. "
    "Model or rule changes void the period."
)
EVIDENCE_AGAINST_REACTIVATION = (
    "Negative or zero-crossing net GBP after costs; drawdown bind breach; "
    "n below minima; worse than cash; lower CI of expectancy includes 0; "
    "Track B results offered as original-bot evidence; missing data above 5% of bars."
)
FURTHER_REVIEW_WITHOUT_LIVE_AUTH = (
    "Track A only, after a frozen protocol, with n met, lower CI of net GBP "
    "above cash and above 0 after 2× cost stress, no DD bind breach. "
    "Review only — never auto-allow live orders. Track B cannot justify live review."
)


def frozen_defaults() -> ShadowConfig:
    """Documented conservative defaults. enabled remains False."""
    return ShadowConfig()


def protocol_tracks() -> tuple[str, str]:
    return TRACK_A, TRACK_B
