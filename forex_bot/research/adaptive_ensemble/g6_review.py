"""Stage G.6 deployment review writer. Offline. Does not call a broker."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble.g4_integrity import (
    PROTOCOL_HASH,
    assert_g3_intact,
    git_baseline,
    write_json,
)
from forex_bot.research.adaptive_ensemble.g5_audit import (
    PACKAGE_HASH,
    POLICY_HASH,
    verify_g4_hashes,
)

ROOT = Path(__file__).resolve().parents[3]
G6 = ROOT / "data" / "research" / "adaptive_ensemble" / "g6"
CLASSIFICATION = "DEPLOYMENT_REVIEW_FAILED_REPAIRS_REQUIRED"


def image_changeset() -> dict[str, Any]:
    """Files a future `docker build` would ship. Dockerfile copies forex_bot, main.py, requirements.txt."""
    return {
        "dockerfile_copy": ["requirements.txt", "forex_bot/", "main.py"],
        "dockerignore_excludes_research": False,
        "head_contains_g5_gate": False,
        "reproducible_revision": False,
        "tracked_modifications": {
            "docker-compose.yml": "stage_a_live_safety_volume",
            "forex_bot/app.py": "stage_a_startup_fail_closed",
            "forex_bot/bot_loop.py": "stage_f_decision_logging_and_stage_g5_frame_gate",
            "forex_bot/csv_ohlcv.py": "stage_g5_imported_stamp",
            "forex_bot/decision_skip_log.py": "stage_f_skip_log",
            "forex_bot/execution.py": "stage_a_and_stage_f_entry_gate",
            "forex_bot/live_manage.py": "stage_g5_quote_field",
            "forex_bot/oanda_client.py": "stage_g5_acquisition_seals",
            "forex_bot/oanda_exec.py": "stage_a_close_exemption_and_stage_g5_open_quote_gate",
            "forex_bot/rl_agent.py": "stage_f_state_requirement",
            "forex_bot/session_rules.py": "session_window_inclusive_minute",
            "forex_bot/state.py": "stage_g5_cache_downgrade",
            "forex_bot/strategy_meta.py": "stage_a_and_stage_f_selection",
            "forex_bot/telegram_control.py": "stage_a_read_only_safety_snapshot",
        },
        "untracked_packages": {
            "forex_bot/decision_repair/": "stage_f",
            "forex_bot/live_safety.py": "stage_a",
            "forex_bot/live_safety_preflight.py": "stage_a",
            "forex_bot/log_config.py": "stage_a_logging",
            "forex_bot/market_provenance.py": "stage_g5",
            "forex_bot/research/": "stage_g_through_g5_not_imported_by_app_startup",
            "forex_bot/shadow/": "stage_e_shadow",
        },
    }


def mutation_matrix() -> list[dict[str, Any]]:
    return [
        {
            "entry_point": "execute_oanda_market_open / _place_market_order_open_sync",
            "broker_endpoint": "POST /v3/accounts/{id}/orders (OrderCreate MARKET OPEN_ONLY)",
            "effect": "new_exposure",
            "caller": "bot_loop broker branch",
            "authorisation_gate": "assert_new_live_exposure_allowed before and again immediately before request",
            "provenance_gate": "decision frame seal, then require_order_quote",
            "risk_controls": "strategy inactive, preflight, risk latch, exposure, pending reservation, geometry",
            "bypass_risk": "same-process call of bind_live_frame can mint a seal",
            "reachable_in_deployed_config": True,
            "review_result": "reviewed_fail_closed_for_unsealed_data",
        },
        {
            "entry_point": "execute_oanda_market_close / _place_market_order_sync",
            "broker_endpoint": "PUT /v3/accounts/{id}/positions/{instrument}/close",
            "effect": "risk_reducing_close",
            "caller": "trading.execute_trade when execution_kind is live",
            "authorisation_gate": "broker mode required; new-exposure auth is not applied to close",
            "provenance_gate": "not required",
            "risk_controls": "longUnits closes a long; shortUnits closes a short; failure raises",
            "bypass_risk": "does not create the opposite position",
            "reachable_in_deployed_config": True,
            "review_result": "reviewed_not_blocked_by_entry_provenance",
        },
        {
            "entry_point": "stopLossOnFill / takeProfitOnFill on the opening market order",
            "broker_endpoint": "same OrderCreate",
            "effect": "protective_orders_attached_at_entry",
            "caller": "bot_loop via execute_oanda_market_open",
            "authorisation_gate": "same as new exposure",
            "provenance_gate": "same as new exposure",
            "risk_controls": "geometry clearance",
            "bypass_risk": "no later replace endpoint exists",
            "reachable_in_deployed_config": True,
            "review_result": "reviewed_with_entry",
        },
        {
            "entry_point": "broker_sl_tp_hit",
            "broker_endpoint": "none",
            "effect": "local_detection_disabled",
            "caller": "bot_loop manage branch",
            "authorisation_gate": "not applicable",
            "provenance_gate": "not applicable",
            "risk_controls": "OANDA remains authoritative for hard SL/TP",
            "bypass_risk": "missing provenance does not cancel broker-native SL/TP",
            "reachable_in_deployed_config": True,
            "review_result": "reviewed_no_cancel",
        },
        {
            "entry_point": "_reconcile_pending_orders",
            "broker_endpoint": "none (GET OrdersPending only)",
            "effect": "local_status_update",
            "caller": "reconcile_positions_log_only",
            "authorisation_gate": "not applicable",
            "provenance_gate": "not applicable",
            "risk_controls": "does not send OrderCancel",
            "bypass_risk": "none found",
            "reachable_in_deployed_config": True,
            "review_result": "reviewed_read_only",
        },
        {
            "entry_point": "fetch_ohlcv / fetch_pricing_snapshot / live_instruments_candles_request",
            "broker_endpoint": "GET candles or GET pricing",
            "effect": "read",
            "caller": "bot_loop, entry geometry, decision-quality history",
            "authorisation_gate": "not an order",
            "provenance_gate": "live fetch seals; historical range stamps historical; raw history helper returns an unsealed dict",
            "risk_controls": "unsealed frames fail the open gate",
            "bypass_risk": "history helper is not the order function",
            "reachable_in_deployed_config": True,
            "review_result": "reviewed_not_a_mutation",
        },
    ]


def write_reports() -> dict[str, Any]:
    prior = assert_g3_intact()
    g4 = verify_g4_hashes()
    if not g4["policy_verified"] or not g4["package_verified"]:
        raise RuntimeError("G4_HASH_MISMATCH")
    baseline = git_baseline()
    G6.mkdir(parents=True, exist_ok=True)
    safety = {
        "stage": "G.6",
        "running_container_changed": False,
        "docker_commands_issued": False,
        "live_order_authorisation_changed": False,
        "strategies_activated": False,
        "broker_requests": 0,
        "broker_orders_submitted": False,
        "live_database_writes": False,
        "consensus_forecast_modified": False,
        "deployment_performed": False,
        "protocol_hash": PROTOCOL_HASH,
        "protocol_verified": prior["protocol"]["verified"],
        "g3_raw_verified": prior["g3"]["raw_verified"],
        "g3_normalised_verified": prior["g3"]["normalised_verified"],
        "g4_policy_hash": POLICY_HASH,
        "g4_package_hash": PACKAGE_HASH,
        "git_revision": baseline["revision"],
        "porcelain_count": baseline["porcelain_count"],
        "running_image_identity": "not_inspected_no_operational_probe",
    }
    write_json(G6 / "baseline_integrity.json", safety)
    write_json(G6 / "changeset_inventory.json", image_changeset())
    write_json(G6 / "broker_mutation_matrix.json", {"paths": mutation_matrix()})
    write_json(
        G6 / "trust_boundary.json",
        {
            "classification": "TRUST_BOUNDARY_PARTIAL",
            "seal_creation": "bind_live_frame and bind_live_quote after a successful response, or by a direct in-process call",
            "last_bar_only_fingerprint": True,
            "earlier_candle_mutation_invalidates_seal": False,
            "bid_ask_mutation_invalidates_quote": True,
            "caller_supplied_label_rejected": True,
            "cached_quote_downgraded": True,
            "same_process_limitation": "public acquisition helpers can mint a live seal without an HTTP response",
            "malicious_in_process_code": "not a claimed boundary",
        },
    )
    write_json(
        G6 / "toctou.json",
        {
            "frame_checked_before_order_reservation": True,
            "quote_rechecked_inside_order_function": True,
            "auth_rechecked_immediately_before_ordercreate": True,
            "frame_not_rechecked_at_ordercreate": True,
            "cross_process_account_concurrency": "not solved by a process-local seal",
            "multiple_replicas": "compose comment says single worker; seal does not coordinate processes",
        },
    )
    write_json(
        G6 / "protective_management.json",
        {
            "position_monitoring_uses_cached_bid_ask": True,
            "cache_downgrade_removes_prices": False,
            "broker_native_sl_tp_cancelled_when_provenance_missing": False,
            "local_sl_tp_hit_for_broker_positions": False,
            "profit_protection_close_uses_position_close": True,
            "stale_manage_quote_suppresses_software_close": True,
            "missing_candles_skip_the_whole_cycle": "pre_existing_early_return",
            "emergency_close_units": "longUnits or shortUnits of the existing side",
            "pending_order_cancel_endpoint": "not_present",
            "trailing_stop_replace_endpoint": "not_present",
            "restart_restores_live_authorisation": False,
        },
    )
    write_json(
        G6 / "startup_restart.json",
        {
            "effective_authorisation_on_start": "BLOCKED",
            "persisted_allowed_ignored": True,
            "strategies_loaded_from_durable_file": True,
            "observed_durable_strategies_active": False,
            "provenance_not_restored_from_disk": True,
            "cache_not_restored_as_live": True,
            "research_import_does_not_authorise": True,
            "synthetic_fallback_on_candle_failure": False,
        },
    )
    write_json(
        G6 / "deployment_package.json",
        {
            "source_revision": baseline["revision"],
            "revision_contains_repair": False,
            "database_migration": False,
            "candidate_build": "not_executed",
            "current_image_identity": "not_inspected",
            "rollback_target": "none_verified",
            "head_rollback_removes_provenance_gate": True,
            "historical_image_not_a_rollback_target": True,
            "unresolved": [
                "working tree is uncommitted and mixes stages A through G.5",
                "image copy includes forex_bot/research",
                "running image digest was not read",
            ],
        },
    )
    write_json(
        G6 / "deployment_procedure.json",
        {
            "executed": False,
            "steps": [
                "Obtain a separate operator decision. This review is not that decision.",
                "Create a pinned source snapshot of the reviewed tree. Do not build from an unnamed dirty tree.",
                "Keep the mounted live-safety file blocked and the six strategies inactive.",
                "Record the running image digest before any build. Do not build in this stage.",
                "Build a candidate image only in a later approved stage and do not start it.",
                "Run the isolated provenance and close tests against that image.",
                "Verify the image digest.",
                "Confirm no database migration is required.",
                "Prepare rollback to a known-safe image, not to HEAD and not to an unidentified historical image.",
                "Stop for explicit deployment approval.",
            ],
        },
    )
    readiness = {
        "stage": "G.6",
        "classification": CLASSIFICATION,
        "trading_approved": False,
        "deployment_approved": False,
        "trust_boundary": "TRUST_BOUNDARY_PARTIAL",
        "protocol_hash": PROTOCOL_HASH,
        "reason": "No pinned revision contains the repair. A build from this tree would ship mixed uncommitted stages.",
    }
    write_json(G6 / "readiness_manifest.json", readiness)
    return {"baseline": safety, "readiness": readiness, "g4": g4}
