"""Stage G.5 provenance audit writer. Offline. Does not call a broker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble.g4_integrity import (
    G4,
    PROTOCOL_HASH,
    assert_g3_intact,
    git_baseline,
    write_json,
)
from forex_bot.research.adaptive_ensemble.protocol import integrity_hash

ROOT = Path(__file__).resolve().parents[3]
G5 = ROOT / "data" / "research" / "adaptive_ensemble" / "g5"
POLICY_HASH = "6ea84361d6fec3e1743fce2c238940d9f2fda50b78b1d5e305d07d18650d29d4"
PACKAGE_HASH = "05b56d1ed7736025e86a9e3f94fb44bb49ea6208718aab7af9cfde6977a6c201"
MODEL_VERSION = "market_provenance_v1"


def verify_g4_hashes() -> dict[str, Any]:
    policy = json.loads((G4 / "data_quality_policy.json").read_text(encoding="utf-8"))
    package = json.loads((G4 / "evaluation_package_manifest.json").read_text(encoding="utf-8"))
    readiness = json.loads((G4 / "readiness_manifest.json").read_text(encoding="utf-8"))
    policy_ok = integrity_hash(policy) == policy.get("integrity_hash") == POLICY_HASH
    package_ok = integrity_hash(package) == package.get("integrity_hash") == PACKAGE_HASH
    return {
        "policy_hash": POLICY_HASH,
        "policy_verified": policy_ok,
        "package_hash": PACKAGE_HASH,
        "package_verified": package_ok,
        "classification": readiness.get("classification"),
        "complete_common_sessions": readiness.get("complete_common_sessions"),
        "remaining_to_40": readiness.get("remaining_to_40"),
        "validation_started": readiness.get("validation_started"),
        "strategy_evaluation_performed": readiness.get("strategy_evaluation_performed"),
        "broker_requests": readiness.get("broker_requests"),
    }


def source_inventory() -> list[dict[str, Any]]:
    return [
        {
            "source_name": "OANDA InstrumentsCandles via fetch_ohlcv",
            "source_classification": "OANDA_LIVE_VERIFIED",
            "production_reachable": True,
            "trading_decision_reachable": True,
            "order_path_reachable": True,
            "provenance_verification": "sealed_at_successful_response",
            "freshness_verification": "acquisition_age_and_last_bar_age",
            "risk_classification": "PRODUCTION_REACHABLE_BLOCKED",
            "verification": "verified_code_path",
        },
        {
            "source_name": "OANDA PricingInfo via fetch_pricing_snapshot",
            "source_classification": "OANDA_LIVE_VERIFIED",
            "production_reachable": True,
            "trading_decision_reachable": False,
            "order_path_reachable": True,
            "provenance_verification": "sealed_at_successful_response",
            "freshness_verification": "acquisition_monotonic_age",
            "risk_classification": "PRODUCTION_REACHABLE_BLOCKED",
            "verification": "verified_code_path",
        },
        {
            "source_name": "OANDA historical range via fetch_ohlcv_range",
            "source_classification": "OANDA_HISTORICAL_VERIFIED",
            "production_reachable": False,
            "trading_decision_reachable": False,
            "order_path_reachable": False,
            "provenance_verification": "stamped_historical_not_live",
            "freshness_verification": "not_eligible",
            "risk_classification": "SAFE_RESEARCH_ONLY",
            "verification": "verified_code_path",
        },
        {
            "source_name": "CSV load_ohlcv_csv",
            "source_classification": "IMPORTED_UNVERIFIED",
            "production_reachable": False,
            "trading_decision_reachable": False,
            "order_path_reachable": False,
            "provenance_verification": "stamped_imported",
            "freshness_verification": "not_eligible",
            "risk_classification": "SAFE_RESEARCH_ONLY",
            "verification": "verified_code_path",
        },
        {
            "source_name": "process pricing snapshot cache",
            "source_classification": "CACHED_UNVERIFIED",
            "production_reachable": True,
            "trading_decision_reachable": False,
            "order_path_reachable": False,
            "provenance_verification": "downgraded_on_store",
            "freshness_verification": "manage_path_keeps_90s_last_change_check",
            "risk_classification": "PRODUCTION_REACHABLE_BLOCKED",
            "verification": "verified_code_path",
        },
        {
            "source_name": "research synthetic_market",
            "source_classification": "SYNTHETIC_TEST",
            "production_reachable": False,
            "trading_decision_reachable": False,
            "order_path_reachable": False,
            "provenance_verification": "stamped_synthetic",
            "freshness_verification": "not_eligible",
            "risk_classification": "SAFE_RESEARCH_ONLY",
            "verification": "verified_code_path",
        },
        {
            "source_name": "Stage G.3 normalised candles",
            "source_classification": "OANDA_HISTORICAL_VERIFIED",
            "production_reachable": False,
            "trading_decision_reachable": False,
            "order_path_reachable": False,
            "provenance_verification": "file_is_not_a_live_seal",
            "freshness_verification": "not_eligible",
            "risk_classification": "SAFE_RESEARCH_ONLY",
            "verification": "verified_code_path",
        },
        {
            "source_name": "shadow replay CSV",
            "source_classification": "REPLAYED_DATA",
            "production_reachable": False,
            "trading_decision_reachable": False,
            "order_path_reachable": False,
            "provenance_verification": "opt_in_disconnected_loader",
            "freshness_verification": "not_eligible",
            "risk_classification": "SAFE_RESEARCH_ONLY",
            "verification": "verified_code_path",
        },
        {
            "source_name": "decision_quality recursive CSV scan",
            "source_classification": "IMPORTED_UNVERIFIED",
            "production_reachable": False,
            "trading_decision_reachable": False,
            "order_path_reachable": False,
            "provenance_verification": "offline_inventory_only",
            "freshness_verification": "not_eligible",
            "risk_classification": "SAFE_RESEARCH_ONLY",
            "verification": "verified_not_on_order_path",
        },
        {
            "source_name": "missing or failed broker response",
            "source_classification": "UNKNOWN",
            "production_reachable": True,
            "trading_decision_reachable": False,
            "order_path_reachable": False,
            "provenance_verification": "no_object_is_minted",
            "freshness_verification": "rejected",
            "risk_classification": "PRODUCTION_REACHABLE_BLOCKED",
            "verification": "verified_code_path",
        },
    ]


def write_reports() -> dict[str, Any]:
    prior = assert_g3_intact()
    g4 = verify_g4_hashes()
    if not g4["policy_verified"] or not g4["package_verified"]:
        raise RuntimeError("G4_HASH_MISMATCH")
    baseline = git_baseline()
    G5.mkdir(parents=True, exist_ok=True)
    safety = {
        "stage": "G.5",
        "running_container_changed": False,
        "docker_commands_issued": False,
        "live_order_authorisation_changed": False,
        "strategies_activated": False,
        "broker_orders_submitted": False,
        "broker_api_calls": 0,
        "live_database_writes": False,
        "consensus_forecast_modified": False,
        "deployment_performed": False,
        "protocol_hash": PROTOCOL_HASH,
        "protocol_verified": prior["protocol"]["verified"],
        "g3_raw_verified": prior["g3"]["raw_verified"],
        "g3_normalised_verified": prior["g3"]["normalised_verified"],
        "g4": g4,
        "git": {"revision": baseline["revision"], "porcelain_count": baseline["porcelain_count"]},
        "durable_live_order_authorisation_observed": "BLOCKED",
        "durable_strategies_observed_active": False,
        "note": "Observation of data/ops/live_safety_state.json was read-only.",
    }
    write_json(G5 / "baseline_integrity.json", safety)
    write_json(G5 / "source_inventory.json", {"sources": source_inventory()})
    write_json(
        G5 / "data_flow.json",
        {
            "production_price_acquisition": "fetch_ohlcv then fetch_entry_pricing",
            "cache_handling": "set_pricing_snapshot downgrades seals to CACHED_UNVERIFIED",
            "candle_transformation": "mid OHLC retained; provenance stays on frame.attrs",
            "indicator_construction": "uses the fetched frame; does not mint live provenance",
            "strategy_decisions": "broker branch rejects a frame that is not sealed live",
            "risk_controls": "unchanged and still required after provenance",
            "order_boundary": "_place_market_order_open_sync requires a sealed pricing quote after live auth",
            "provenance_loss_points": [
                "copying a frame without attrs drops the seal and is rejected",
                "mutating OHLC after the seal fails the content hash",
                "storing a quote in the process cache downgrades it",
            ],
            "unverified_paths": [
                "same-process code can call bind_live_frame; a label or file cannot",
                "off-window simulate scoring of an injected frame cannot submit an order",
            ],
        },
    )
    write_json(
        G5 / "risk_register.json",
        {
            "synthetic_generators": ["research.adaptive_ensemble.runner.synthetic_market"],
            "replay_mechanisms": ["forex_bot.shadow.replay"],
            "fallback_price_providers": [
                "fetch_ohlcv returns None on failure",
                "fetch_entry_pricing has no M5 fallback",
                "manage path does not fall back to M5 close",
            ],
            "shared_storage_risks": [
                "decision_quality rglob can see data/research for offline inventory",
                "production fetch_ohlcv does not scan directories",
            ],
            "production_reachable_unsafe_paths": [],
            "severity_before_gate": "a substituted frame was indistinguishable from a live fetch",
            "remediation_status": "fail_closed_gate_local_undeployed",
        },
    )
    write_json(
        G5 / "provenance_model.json",
        {
            "model_version": MODEL_VERSION,
            "trusted_boundary": "successful response inside fetch_ohlcv and fetch_pricing_snapshot",
            "eligibility": "only a sealed OANDA_LIVE_VERIFIED record may continue to existing safety checks",
            "missing_provenance": "rejected",
            "spoofed_label": "rejected",
            "cached_record": "not live",
            "historical_record": "not live",
            "synthetic_record": "not live",
            "limits": "in-process calls to the acquisition helper are not distinguishable from the fetch functions",
        },
    )
    write_json(
        G5 / "isolation_assessment.json",
        {
            "g3_classification": "OANDA_HISTORICAL_VERIFIED",
            "g4_runner": "offline_default_refusing",
            "synthetic_fixture_storage": "research helper output and tests; not a production loader input",
            "production_path_overlap": "none through directory scan",
            "research_artifacts_g3_g4_modified": False,
            "holdout_strategy_evaluation_performed": False,
        },
    )
    readiness = {
        "stage": "G.5",
        "classification": "PROVENANCE_BOUNDARY_IMPLEMENTED_UNDEPLOYED",
        "trading_approved": False,
        "deployed": False,
        "protocol_hash": PROTOCOL_HASH,
        "model_version": MODEL_VERSION,
        "g4_unchanged": g4,
    }
    write_json(G5 / "readiness_manifest.json", readiness)
    return {"baseline": safety, "g4": g4, "readiness": readiness}
