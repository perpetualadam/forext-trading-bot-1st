"""Versioned Stage G.4 data-quality policy. Does not alter the Stage G protocol."""

from __future__ import annotations

from typing import Any

from forex_bot.research.adaptive_ensemble.protocol import integrity_hash
from forex_bot.research.adaptive_ensemble.simulator_v2 import VERSION
from forex_bot.research.adaptive_ensemble.state_v2 import SCHEMA

POLICY_ID = "stage_g4_data_quality_policy_v1"
PACKAGE_ID = "independent_validation_package_v1"
RUNNER_ID = "independent_validation_runner_v1"
CHANGE_CLASS = "BEHAVIOURAL_EVALUATION_SPEC_REQUIRES_NEW_BASELINE"


def quality_policy(*, definition_hash: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "policy_id": POLICY_ID,
        "change_class": CHANGE_CLASS,
        "modifies_stage_g_protocol": False,
        "definition_hash": definition_hash,
        "max_source_omission_minutes": 60,
        "rules": [
            {"condition": "expected_weekend_closure", "action": "ACCEPT"},
            {"condition": "source_omission_at_most_60_minutes", "action": "QUARANTINE_INTERVAL"},
            {"condition": "unresolved_or_longer_gap", "action": "SKIP_SESSION"},
            {"condition": "pagination_or_normalisation_defect", "action": "STOP_EVALUATION"},
            {"condition": "missing_bid_ask", "action": "STOP_EVALUATION"},
            {"condition": "invalid_spread", "action": "STOP_EVALUATION"},
            {"condition": "price_jump_gt_1pct", "action": "NO_TRADE"},
            {"condition": "incomplete_candle_in_evaluation_set", "action": "STOP_EVALUATION"},
            {"condition": "stale_or_missing_conversion", "action": "NO_TRADE"},
            {"condition": "insufficient_warmup", "action": "NO_TRADE"},
            {"condition": "gap_during_open_position_source_omission", "action": "QUARANTINE_INTERVAL"},
            {"condition": "gap_immediately_before_entry", "action": "NO_TRADE"},
            {"condition": "gap_at_stop_or_target", "action": "QUARANTINE_INTERVAL"},
            {"condition": "partial_session", "action": "SKIP_SESSION"},
            {"condition": "provider_data_anomaly", "action": "STOP_EVALUATION"},
        ],
        "stop_fill": "next observed executable open; never an unobserved stop price inside a hole",
        "no_interpolation": True,
        "no_mid_replacement": True,
        "actions_ignore_trade_outcome": True,
    }
    body["integrity_hash"] = integrity_hash(body)
    return body


def evaluation_package(*, protocol_hash: str, policy_hash: str, definition_hash: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "package_id": PACKAGE_ID,
        "runner_id": RUNNER_ID,
        "not_byte_identical_to_stage_g": True,
        "inherits_stage_g_historical_pnl": False,
        "protocol_hash": protocol_hash,
        "policy_hash": policy_hash,
        "definition_hash": definition_hash,
        "frozen_from_stage_g": [
            "candidate_ids",
            "regime_rules",
            "vote_min_agree",
            "dynamic_eta",
            "weight_bounds",
            "cost_scenarios",
            "no_trade_benchmark",
            "minimum_trades_30",
        ],
        "repaired_g1": SCHEMA,
        "repaired_g2": VERSION,
        "clarified_g4": [
            "fx_trading_day_ny1700_v1",
            POLICY_ID,
            "full_timestamp_side_aware_conversion_audit",
        ],
        "simulator_change_class": "BEHAVIOURAL_REPAIR_REQUIRES_REBASELINE",
        "weight_change_class": "BEHAVIOURAL_REPAIR_REQUIRES_REBASELINE",
        "policy_change_class": CHANGE_CLASS,
        "minimum_complete_sessions": 40,
        "minimum_trades": 30,
        "minimum_trades_status": "NOT_YET_EVALUATED",
        "default_authorised": False,
        "paper_trading": False,
        "live_trading": False,
    }
    body["integrity_hash"] = integrity_hash(body)
    return body
