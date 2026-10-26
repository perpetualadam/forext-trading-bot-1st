"""Write Stage G.13 JSON evidence. Does not build, deploy, or contact the broker."""

from __future__ import annotations

import difflib
import hashlib
import importlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "adaptive_ensemble" / "g13"
ALLOWLIST = ROOT / "data" / "research" / "adaptive_ensemble" / "g10" / "production_allowlist.json"
G7_TAR = ROOT / "data" / "research" / "adaptive_ensemble" / "g7" / "source_snapshot.tar"
G10_TAR = ROOT / "data" / "research" / "adaptive_ensemble" / "g10" / "source_snapshot.tar"

EXPECTED = {
    "g7_archive": "0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82",
    "g7_manifest": "ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989",
    "dockerignore": "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd",
    "g10_archive": "d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277",
    "g10_manifest": "93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf",
    "original_dockerfile": "f8d537d84c8ab004c5fc2cbdc5ef58e8141f5ca66a13be6cc5eac38c7c7006a6",
    "image_database": "98ed215c0a7e7f21ecf938172a45805a3f1b456c5cf49e8d0a8ea9f0d5cbce72",
}
INITIAL_PORCELAIN = [
    " M data/research/macro/consensus_pit/prospective/scheduler/audit.jsonl",
    " M data/research/macro/consensus_pit/prospective/scheduler/state.json",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def tar_member(path: Path, name: str) -> bytes:
    with tarfile.open(path) as archive:
        handle = archive.extractfile(name)
        if handle is None:
            raise RuntimeError(f"missing {name} in {path}")
        return handle.read()


def write(name: str, payload: object) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    integrity = importlib.import_module("forex_bot.research.adaptive_ensemble.g4_integrity")
    g7_snapshot = importlib.import_module("forex_bot.research.adaptive_ensemble.g7_snapshot")
    g10_snapshot = importlib.import_module("forex_bot.research.adaptive_ensemble.g10_snapshot")
    verify_protocol = integrity.verify_protocol
    verify_g3_hashes = integrity.verify_g3_hashes
    OUT.mkdir(parents=True, exist_ok=True)
    allow = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    rows = []
    for row in allow["files"]:
        path = ROOT / row["path"]
        actual = sha256_file(path)
        rows.append(
            {
                "path": row["path"],
                "expected_sha256": row["sha256"],
                "actual_sha256": actual,
                "match": actual == row["sha256"],
                "reason": row["reason"],
                "intentional_repair": row["path"] == "Dockerfile",
            }
        )
    g7_manifest = json.loads((ROOT / "data/research/adaptive_ensemble/g7/manifest.json").read_text(encoding="utf-8"))
    g10_manifest = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g10/source_manifest.json").read_text(encoding="utf-8")
    )
    frozen = {
        "g7_archive": sha256_file(G7_TAR),
        "g7_manifest": g7_snapshot.manifest_digest(g7_manifest),
        "dockerignore": sha256_file(ROOT / ".dockerignore"),
        "g10_archive": sha256_file(G10_TAR),
        "g10_manifest": g10_snapshot.manifest_digest(g10_manifest),
        "original_dockerfile_from_g10_tar": sha256_bytes(tar_member(G10_TAR, "Dockerfile")),
    }
    protocol = verify_protocol()
    g3 = verify_g3_hashes()
    database_hashes = {
        label: sha256_bytes(tar_member(archive, "forex_bot/database.py"))
        for label, archive in (("g7", G7_TAR), ("g10", G10_TAR))
    }
    database_hashes["working_tree"] = sha256_file(ROOT / "forex_bot/database.py")
    database_hashes["running_image_recorded"] = EXPECTED["image_database"]
    safety_hashes = {
        "g7": sha256_bytes(tar_member(G7_TAR, "forex_bot/live_safety.py")),
        "g10": sha256_bytes(tar_member(G10_TAR, "forex_bot/live_safety.py")),
        "working_tree": sha256_file(ROOT / "forex_bot/live_safety.py"),
    }
    new_docker = (ROOT / "Dockerfile").read_bytes()
    old_docker = tar_member(G10_TAR, "Dockerfile").decode("utf-8").splitlines(keepends=True)
    new_lines = new_docker.decode("utf-8").splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(old_docker, new_lines, fromfile="a/Dockerfile", tofile="b/Dockerfile")
    )
    (OUT / "dockerfile_diff.patch").write_text(diff, encoding="utf-8")
    copied = [
        {
            "source": row["path"],
            "destination": "/app/requirements.txt"
            if row["path"] == "requirements.txt"
            else "/app/main.py"
            if row["path"] == "main.py"
            else "/app/" + row["path"],
            "sha256": row["actual_sha256"],
        }
        for row in rows
        if row["path"] not in {"Dockerfile", ".dockerignore"}
    ]
    write(
        "baseline_integrity.json",
        {
            "classification_rule": "BASELINE_INTEGRITY_BLOCKED only for an unexpected frozen-artifact mismatch",
            "git_head": "d080d897945bc44fa37c02caab504ed707146bec",
            "spec_expected_head": "f6c4f40ae6b7614379347ed45141ecd5a3d33642",
            "head_difference": "The operator committed Stages A-G.12.1 after the G.13 prompt was written. The tree was not reset.",
            "initial_porcelain": INITIAL_PORCELAIN,
            "frozen_expected": EXPECTED,
            "frozen_actual": frozen,
            "frozen_match": all(
                frozen[key] == EXPECTED["original_dockerfile" if key == "original_dockerfile_from_g10_tar" else key]
                for key in frozen
            ),
            "manifest_hash_method": "canonical JSON digest excluding the manifest_sha256 field, not the raw file bytes",
            "g3_raw_verified": g3["raw_verified"],
            "g3_normalised_verified": g3["normalised_verified"],
            "g3_preserved_ok": g3["preserved_ok"],
            "protocol_verified": protocol["verified"],
            "protocol_sha256": protocol["actual"],
            "g4_paths_not_modified_by_this_stage": True,
            "original_dockerfile_sha256": EXPECTED["original_dockerfile"],
            "new_dockerfile_sha256": sha256_bytes(new_docker),
            "forensic_archive_recreated": False,
        },
    )
    write(
        "allowlist_revalidation.json",
        {
            "source": "data/research/adaptive_ensemble/g10/production_allowlist.json",
            "recorded_status": allow["status"],
            "image_build_authorised_in_g10": allow["image_build_authorised"],
            "file_count": allow["file_count"],
            "verified_file_count": len(rows),
            "hash_matches": sum(1 for row in rows if row["match"]),
            "intentional_dockerfile_hash_change": True,
            "missing_files": [],
            "unexpected_files": [],
            "hash_mismatches_excluding_intentional_dockerfile": [
                row["path"] for row in rows if not row["match"] and row["path"] != "Dockerfile"
            ],
            "files": rows,
            "runtime_dependency_finding": "Python import closure of main.py and forex_bot.app is exactly the 60 allowlisted Python files.",
            "exclusion_finding": "Research, shadow, decision_quality, tests, credentials, and data paths are absent from the allowlist.",
            "unresolved_questions": [
                "DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED",
                "Static closure does not execute the process.",
                "requirements.txt matches the allowlist, but installed wheel bytes were not rebuilt.",
            ],
        },
    )
    write(
        "runtime_dependency_closure.json",
        {
            "entrypoints": ["main.py", "uvicorn forex_bot.app:app"],
            "python_modules_in_closure": 60,
            "missing_required": [],
            "dynamic_dependency_unresolved": [],
            "uvicorn_string_target": {
                "reference": "forex_bot.app:app",
                "classification": "INCLUDED_AND_VERIFIED",
            },
            "importlib_sites_in_closure": [],
            "subprocess_sites_in_closure": [],
            "file_reads_are_runtime_state": [
                "forex_bot/live_safety.py durable authorisation document",
                "forex_bot/decision_repair account risk, selection cursor, audit jsonl, health, and rl q-table under data/ops",
                "forex_bot/v2_shadow observations, outcomes, and market JSONL under data/research/v2_shadow",
            ],
            "optional_and_excluded": [
                {
                    "path": "forex_bot/live_safety_preflight.py",
                    "classification": "OPTIONAL_AND_EXCLUDED_WITH_JUSTIFICATION",
                    "reason": "Operator preflight tool. Not imported by the startup closure.",
                },
                {
                    "path": "forex_bot/decision_repair/harness.py",
                    "classification": "OPTIONAL_AND_EXCLUDED_WITH_JUSTIFICATION",
                    "reason": "Test harness. Not imported by the startup closure.",
                },
                {
                    "path": "forex_bot/v2_shadow/score_offline.py",
                    "classification": "OPTIONAL_AND_EXCLUDED_WITH_JUSTIFICATION",
                    "reason": "Offline research scorer. Not imported by the packaged writer.",
                },
            ],
            "research_only_excluded": [
                "forex_bot/research/",
                "forex_bot/shadow/",
                "forex_bot/decision_quality/",
                "forex_bot/backtest.py",
                "forex_bot/csv_ohlcv.py",
            ],
            "model_files_packaged": [],
            "nn_pred_loads_external_model": False,
            "classification_summary": "No MISSING_REQUIRED or DYNAMIC_DEPENDENCY_UNRESOLVED module.",
        },
    )
    write(
        "expected_image_manifest.json",
        {
            "kind": "STATIC_PREDICTION",
            "not_a_docker_inventory": True,
            "docker_daemon_context_behaviour": "DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED",
            "application_file_count": len(copied),
            "policy_files_not_copied_into_image": ["Dockerfile", ".dockerignore"],
            "files": copied,
        },
    )
    write(
        "packaging_exclusion_audit.json",
        {
            "method": "Explicit COPY sources compared with the allowlist. Local .dockerignore matcher also reports no copied source as excluded. Daemon context behaviour was not tested.",
            "credentials_excluded": True,
            "research_data_excluded": True,
            "tests_excluded": True,
            "frozen_artifacts_excluded": True,
            "operational_state_excluded": True,
            "git_metadata_excluded": True,
            "onedrive_metadata_excluded": True,
            "broad_package_copy_removed": True,
            "main_py_copies": 1,
            "remaining_risks": [
                "DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED",
                "A future file added beside an allowlisted module is not copied, which is intentional.",
                "Base-image contents and installed wheels were not rebuilt or inventoried.",
            ],
        },
    )
    write(
        "dockerfile_verification.json",
        {
            "static_parser_is_not_a_docker_build": True,
            "ok": True,
            "copy_count": 61,
            "main_py_copies": 1,
            "broad_copy_present": False,
            "wildcard_copy_present": False,
            "entrypoint": 'CMD ["uvicorn", "forex_bot.app:app", "--host", "0.0.0.0", "--port", "8000"]',
            "dependency_install_unchanged": True,
            "workdir": "/app",
            "symlinks_or_reparse_points_in_sources": [],
            "dockerignore_excluded_sources": [],
            "new_dockerfile_sha256": sha256_bytes(new_docker),
        },
    )
    identical = len(set(database_hashes.values())) == 1
    write(
        "database_compatibility.json",
        {
            "live_database_inspected": False,
            "classification": "LIVE_DATABASE_COMPATIBILITY_UNVERIFIED",
            "source_bytes_identical": identical,
            "database_py_sha256": database_hashes,
            "tables_defined_in_identical_source": [
                "trades",
                "reconcile_metadata",
                "operational_event_log",
                "exec_orders",
                "broker_exit_ledger",
                "broker_exit_pending",
            ],
            "additive_statements_in_source": [
                "CREATE TABLE IF NOT EXISTS",
                "ALTER TABLE trades ADD COLUMN IF NOT EXISTS trading_mode",
                "ALTER TABLE trades ADD COLUMN IF NOT EXISTS execution_kind",
                "ALTER TABLE trades ADD COLUMN IF NOT EXISTS diagnostics",
                "ALTER TABLE exec_orders ADD COLUMN IF NOT EXISTS filled_units",
                "CREATE INDEX IF NOT EXISTS",
            ],
            "drop_or_rewrite_statements_in_source": [],
            "startup_ddl": "get_connection executes the statements above and commits once on first connection.",
            "backward_compatibility": "STATICALLY_INFERRED_FROM_IDENTICAL_SOURCE",
            "forward_compatibility": "STATICALLY_INFERRED_FROM_IDENTICAL_SOURCE",
            "unknown_live_schema_state": True,
            "unknown_live_data_contents": True,
            "unverified_runtime_behavior": True,
            "potential_irreversible_change_in_this_source": False,
        },
    )
    write(
        "safety_state_compatibility.json",
        {
            "source": "forex_bot/live_safety.py",
            "source_sha256": safety_hashes,
            "source_bytes_identical_across_g7_g10_and_working_tree": len(set(safety_hashes.values())) == 1,
            "live_file_written": False,
            "schema_version": 1,
            "mandatory_fields": [
                "schema_version == 1",
                "live_order_authorisation.state in BLOCKED|ALLOWED",
                "strategies object containing scalp, trend, mean_reversion, swing_trend, swing_mean_reversion, swing_breakout",
                "each known strategy row has active",
            ],
            "optional_fields": [
                "unknown top-level keys on an otherwise valid document",
                "strategy sample_count, sharpe, disable_reason, changed_at_utc, loaded_from_durable",
            ],
            "unknown_top_level_fields_preserved": True,
            "unknown_fields_inside_known_strategy_rows_preserved": False,
            "existing_strategy_flags_preserved_when_document_valid": True,
            "invalid_or_newer_schema_replaced_with_blank_blocked_document": True,
            "startup_rewrites_document": True,
            "atomic_write": "temp file plus os.replace",
            "persisted_allowed_effective_on_start": "BLOCKED with reason persisted_allowed_ignored_until_operator_action",
            "missing_file_reason": "default_deny_no_durable_state",
            "corrupt_file_reason": "corrupt_or_unreadable_state",
            "strategy_flags_independent_of_effective_order_gate": True,
            "close_actions_not_gated_by_new_exposure_check": True,
            "rollback_risk": "A newer schema_version that this parser rejects is overwritten with a blank BLOCKED document and inactive known strategies.",
        },
    )
    write(
        "shadow_mount_compatibility.json",
        {
            "mount": "/app/data/research/v2_shadow",
            "mount_accessed": False,
            "packaged_writers": [
                "forex_bot/v2_shadow/store.py append_observation",
                "forex_bot/v2_shadow/store.py append_outcome",
                "forex_bot/v2_shadow/market.py persist_completed_candle",
            ],
            "packaged_readers": [
                "forex_bot/v2_shadow/store.py outcome sibling scan",
                "forex_bot/v2_shadow/market.py idempotency key reload",
            ],
            "excluded_reader": "forex_bot/v2_shadow/score_offline.py",
            "formats": {
                "observations": "observations.jsonl",
                "outcomes": "outcomes.jsonl",
                "market": "market/{SYMBOL}_M5.jsonl",
                "market_schema_version": "v2_shadow_market_m5_v1",
                "feature_schema_version": "v2_shadow_input_v1",
            },
            "serialization": "JSON lines, append only, secret-like keys redacted by the writer",
            "authoritative_for_orders": False,
            "compatibility_risks": [
                "A renamed path or required new field can make an older reader skip or reject rows.",
                "Schema strings are constants, not a negotiated migration.",
                "The running image's shadow-module bytes were not re-read. The forensic archive was not recreated.",
            ],
            "recovery_assumption": "UNRESOLVED_OPERATOR_DECISION",
            "unknowns": [
                "Live mount contents",
                "Whether the running image writes the same records",
            ],
        },
    )
    write(
        "deployment_blockers.json",
        {
            "image_build_authorised": False,
            "deployment_authorised": False,
            "rollback_authorised": False,
            "blockers": [
                "DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED",
                "LIVE_DATABASE_COMPATIBILITY_UNVERIFIED",
                "NO_VERIFIED_ROLLBACK_TARGET",
                "ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED",
                "UNRESOLVED_OPERATOR_DECISION for backup location, downtime, and recovery objectives",
                "Broker reconciliation is required before any rollback that follows persistent-state changes",
                "Three historical tests still pin the pre-repair Dockerfile and fail until a later edit updates them",
            ],
        },
    )
    write(
        "test_results.json",
        {
            "commands": [
                "python -m ruff check tests/g13_packaging.py tests/test_g13_packaging.py",
                "python -m mypy tests/g13_packaging.py tests/test_g13_packaging.py",
                "python -m pytest -q --tb=line tests/test_live_safety_repair.py tests/test_execution_safety.py tests/test_decision_repair.py tests/test_decision_repair_f1.py tests/test_decision_repair_f2.py tests/test_market_provenance_g5.py tests/test_market_provenance_g6.py tests/test_market_provenance_g7.py tests/test_g7_snapshot.py tests/test_g8_packaging.py tests/test_g8_missing_candles.py tests/test_g9_management.py tests/test_g9_1_candle_exceptions.py tests/test_g10_snapshot.py tests/test_g11_audit.py tests/test_g12_forensics.py tests/test_g12_1_verify.py tests/test_g13_packaging.py tests/test_v2_shadow.py tests/test_v2_shadow_market.py tests/test_macro_prospective_recorder_stage2.py::test_host_store_is_not_a_bot_container_path",
            ],
            "g13_tests_passed": 16,
            "g13_tests_failed": 0,
            "combined_passed": 239,
            "combined_failed": 3,
            "combined_skipped": 0,
            "warnings": [
                "datetime.utcnow deprecation in bot_loop.py and session_rules.py during existing tests"
            ],
            "ruff_new_modules": "All checks passed",
            "mypy_new_modules": "No errors reported",
            "expected_failures": [
                {
                    "test": "tests/test_g10_snapshot.py::test_official_archive_is_independently_verified_and_not_rewritten",
                    "reason": "Fresh working-tree manifest hash changed because Dockerfile bytes changed. The frozen G.10 archive hash did not change.",
                },
                {
                    "test": "tests/test_g11_audit.py::test_g10_allowlist_has_not_drifted",
                    "reason": "Drift list is exactly Dockerfile. The other 62 allowlist hashes match.",
                },
                {
                    "test": "tests/test_macro_prospective_recorder_stage2.py::test_host_store_is_not_a_bot_container_path",
                    "reason": "The test still expects the removed broad COPY forex_bot ./forex_bot instruction.",
                },
            ],
            "production_source_modified_to_silence_warnings": False,
            "g5_g6_test_side_effects_restored": [
                "data/research/adaptive_ensemble/g5/baseline_integrity.json",
                "data/research/adaptive_ensemble/g6/baseline_integrity.json",
                "data/research/adaptive_ensemble/g6/deployment_package.json",
            ],
        },
    )


if __name__ == "__main__":
    main()
