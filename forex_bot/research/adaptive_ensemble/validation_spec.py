"""Prospective evaluation specification. Does not start evaluation or collection."""

from __future__ import annotations

from typing import Any

from forex_bot.research.adaptive_ensemble.protocol import PROTOCOL, PROTOCOL_ID

SPEC_ID = "stage_g1_future_validation_spec_v1"


def future_validation_spec(*, protocol_hash: str, model_manifest_hash: str) -> dict[str, Any]:
    return {
        "spec_id": SPEC_ID,
        "status": "FROZEN_NOT_STARTED",
        "paper_trading": False,
        "scheduled": False,
        "protocol_id": PROTOCOL_ID,
        "protocol_hash": protocol_hash,
        "model_manifest_hash": model_manifest_hash,
        "frozen_feature_definitions": "stage_g_features_v1",
        "frozen_candidate_ids": list(PROTOCOL["candidates"]),
        "frozen_ensemble_parameters": {
            "vote_min_agree": 2,
            "dynamic_eta": 0.15,
            "weight_bounds": [0.05, 5.0],
            "decision_stride": PROTOCOL["execution"]["decision_stride"],
            "state_schema_for_new_runs": "exp_weights_v2",
        },
        "frozen_execution_assumptions": dict(PROTOCOL["execution"]),
        "gbp_conversion": "timestamped RateTable required; else GBP_CONVERSION_UNVERIFIED and evaluation incomplete",
        "data_acquisition_source": "DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL until operator authorises a read-only feed",
        "data_quality_requirements": [
            "UTC chronological unique timestamps",
            "bid<=ask and valid OHLC",
            "no incomplete bars in the evaluation set",
            "no interpolated executable quotes",
            "gaps classified weekend vs unexpected",
        ],
        "minimum_warmup_history_bars": 120,
        "minimum_evaluation_duration": "40 complete FX trading days after 2026-08-31T23:50:00Z",
        "minimum_trade_count": 30,
        "do_not_reduce_sample_to_fit_existing_data": True,
        "primary_metrics": [
            "net_pnl_gbp",
            "max_drawdown",
            "profit_factor",
            "abstention_rate",
        ],
        "secondary_metrics": [
            "gross_pnl_gbp",
            "win_rate",
            "trade_count",
            "per_pair",
            "per_regime",
            "cost_sensitivity",
        ],
        "statistical_uncertainty": "time-series block resampling of non-overlapping trade exits; no independent-trade p-values",
        "cost_scenarios": list(PROTOCOL["cost_scenarios"]),
        "no_trade_benchmark": True,
        "failure_conditions": [
            "quality FAIL on any evaluation pair",
            "MODEL_STATE_INVALID or INCOMPATIBLE during a restart",
            "conversion unverified for a pair that traded",
            "overlap with Stage E/G timestamps labelled as independent",
            "any parameter change after seeing validation data",
        ],
        "model_state_recovery_policy": "fresh equal weights only at first decision of a new run_id; restarts fail closed",
        "contamination_policy": "timestamps <= 2026-08-31T23:50:00Z are PREVIOUSLY_EXAMINED; later data that influenced G/G.1 design is NEWLY_ACQUIRED_BUT_EXPOSED",
        "missing_data_policy": "do not interpolate; skip decision; record reason; stop pair if unexpected gap invalidates the feature window",
        "protocol_amendments": "new spec version required; never overwrite this spec after a validation run begins",
        "stop_conditions": [
            "Insufficient independent data",
            "Quality or conversion failure",
            "No-trade remains the better benchmark after severe costs",
            "Sign flip under severe costs",
        ],
        "conditions_required_before_validation_may_begin": [
            "Operator-approved read-only data source or local files with timestamps after 2026-08-31T23:50:00Z",
            "Provenance hashes and quality PASS",
            "Independence label POTENTIALLY_INDEPENDENT and not exposed to model selection",
            "Timestamped GBP conversion quotes covering the window",
            "exp_weights_v2 run identity",
            "Explicit human approval of a separate stage",
            "No live broker execution connection",
        ],
        "current_independent_data": "insufficient",
    }
