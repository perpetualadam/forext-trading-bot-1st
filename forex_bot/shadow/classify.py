"""Stage E classification rules. Frozen before the full result grid is read.

These thresholds are not fitted to held-out P&L. A timing replay of one
EUR_USD held-out path was used only to confirm runtime, not to set rules.
"""

from __future__ import annotations

from typing import Any

RESULT_LABEL = "EXPERIMENTAL_HEURISTIC_OFFLINE"
MIN_TRADES = 50
NAV = 97.15
PF_MIN = 1.2
DD_FRAC_MAX = 0.05
SEVERE_NET_FLOOR_FRAC = -0.02
SINGLE_PAIR_SHARE_MAX = 0.70


def classify_strategy(row: dict[str, Any]) -> str:
    """row keys: heldout_n, heldout_net, heldout_pf, heldout_dd, cons_net, severe_net,
    val_net, ci_lo, ci_hi, top_pair_share, evidence_tag
    """
    n = int(row.get("heldout_n") or 0)
    if n < MIN_TRADES:
        return "INSUFFICIENT_EVIDENCE"
    net = float(row.get("heldout_net") or 0.0)
    cons = float(row.get("cons_net") or net)
    severe = float(row.get("severe_net") or net)
    pf = row.get("heldout_pf")
    dd = float(row.get("heldout_dd") or 0.0)
    val = float(row.get("val_net") or 0.0)
    ci_lo = row.get("ci_lo")
    share = float(row.get("top_pair_share") or 0.0)
    if net <= 0 or cons <= 0:
        return "NO_CREDIBLE_EDGE"
    if pf is None or float(pf) < PF_MIN:
        return "NO_CREDIBLE_EDGE"
    if dd > NAV * DD_FRAC_MAX:
        return "NO_CREDIBLE_EDGE"
    if severe < NAV * SEVERE_NET_FLOOR_FRAC:
        return "NO_CREDIBLE_EDGE"
    if val <= 0:
        return "NO_CREDIBLE_EDGE"
    if ci_lo is not None and float(ci_lo) <= 0:
        return "INSUFFICIENT_EVIDENCE"
    if share > SINGLE_PAIR_SHARE_MAX:
        return "NO_CREDIBLE_EDGE"
    return "OFFLINE_REVIEW_CANDIDATE"


def overall_decision(classes: dict[str, str], *, simulator_ok: bool, data_ok: bool) -> str:
    if not simulator_ok:
        return "SIMULATOR_REPAIR_REQUIRED"
    if not data_ok:
        return "MORE_OFFLINE_DATA_REQUIRED"
    if any(c == "OFFLINE_REVIEW_CANDIDATE" for c in classes.values()):
        return "PROSPECTIVE_SHADOW_REVIEW_JUSTIFIED"
    return "STOP_EXPERIMENTAL_STRATEGY_FAMILY"
