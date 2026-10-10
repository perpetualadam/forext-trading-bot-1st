"""Write Stage G.12.1 artifacts from an independent archive read. Does not delete the archive."""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path(r"C:\Users\Brian\AppData\Local\Temp\forex-bot-g12-forensics\image_save.tar")
OUT = ROOT / "data" / "research" / "adaptive_ensemble" / "g12_1"
EXPECTED_SIZE = 111919104
EXPECTED_ARCHIVE = "ba6f8c3659a599bba1a1b322384ae462dc4d43e8de5a73b7f1001ecca606c948"
EXPECTED_IMAGE = "sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25"
EXPECTED_FILES = {
    "forex_bot/live_safety.py": "6e59666960dfec0ff379343c8973e389363faaab49278d9806c160a18ebe8f4f",
    "forex_bot/app.py": "77888f0fa40b5a2935913be6d9b8770c1df0aa204d21c72537cef9e01ac0f70d",
    "forex_bot/database.py": "98ed215c0a7e7f21ecf938172a45805a3f1b456c5cf49e8d0a8ea9f0d5cbce72",
    "main.py": "4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb",
    "forex_bot/bot_loop.py": "89aa67b6dfeb079b3c074ba59cd347d83239ccb24dc49b3b9c3369895b56c3ce",
    "forex_bot/oanda_exec.py": "7c712eeccfce36eae0682de084ee33f79bb35f39004ea39b4015b3f674eae078",
    "forex_bot/oanda_client.py": "288f352e8fda6434beb284789bdf88d43f582a67dadfa4e5147b6cee1333d603",
    "forex_bot/live_manage.py": "bbb3b01c057d5d4db1d3893090e69585f5c0774deeab69c08012d416a905cd03",
    "forex_bot/decision_skip_log.py": "54139a60d41d4be9b76b9f597b395ba0f8a16fc1ac518ed54f2b7a9c1f05b340",
    "forex_bot/market_provenance.py": None,
}
SIGNIFICANCE = {
    "forex_bot/live_safety.py": "Stage A fail-closed live-order gate",
    "forex_bot/app.py": "Process startup calls the fail-closed initialiser",
    "forex_bot/database.py": "Startup connection can execute CREATE/ALTER statements",
    "main.py": "Process entry module",
    "forex_bot/bot_loop.py": "Candle-failure path decides whether management still runs",
    "forex_bot/oanda_exec.py": "Broker order and position mutation module",
    "forex_bot/oanda_client.py": "Broker quote and candle acquisition client",
    "forex_bot/live_manage.py": "Open-position management helper",
    "forex_bot/decision_skip_log.py": "Decision skip reason log",
    "forex_bot/market_provenance.py": "G.7 quote-provenance module",
}


def _load():
    spec = importlib.util.spec_from_file_location("g12_1_verify", Path(__file__).with_name("g12_1_verify.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(name: str, payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _scan(module, paths: list[Path]) -> dict:
    flagged: list[str] = []
    inspected: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".md", ".py"}:
            continue
        inspected.append(str(path.relative_to(ROOT)).replace("\\", "/"))
        result = module.redact_text(path.read_text(encoding="utf-8", errors="replace"))
        if result["private_key_banner"] or result["credential_assignment"]:
            flagged.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    return {
        "credential_assignment_or_private_key_banner": flagged,
        "files_inspected": inspected,
        "values_disclosed": False,
        "values_stored": False,
    }


def main() -> None:
    module = _load()
    stamp = datetime.now(timezone.utc).isoformat()
    digest, size = module.sha256_path(ARCHIVE)
    archive_ok = size == EXPECTED_SIZE and digest == EXPECTED_ARCHIVE
    if not archive_ok:
        _write(
            "archive_verification.json",
            {
                "actual_sha256": digest,
                "actual_size": size,
                "classification": "FORENSIC_ARCHIVE_INTEGRITY_FAILED",
                "expected_sha256": EXPECTED_ARCHIVE,
                "expected_size": EXPECTED_SIZE,
                "path": str(ARCHIVE),
                "verified_at_utc": stamp,
            },
        )
        print("FORENSIC_ARCHIVE_INTEGRITY_FAILED")
        return
    result = module.verify_save(ARCHIVE)
    layers_ok = (
        result["layer_count"] == 9
        and result["image_id"] == EXPECTED_IMAGE
        and all(row["verified"] for row in result["layers"])
        and len({row["reference"] for row in result["layers"]}) == 9
    )
    rows = []
    files_ok = True
    for path, expected in EXPECTED_FILES.items():
        actual = result["files"].get(path)
        present = path in result["files"]
        if expected is None:
            match = not present
        else:
            match = actual == expected
        files_ok = files_ok and match
        g7 = module.pin_hash(ROOT / "data/research/adaptive_ensemble/g7/source_snapshot.tar", path)
        g10 = module.pin_hash(ROOT / "data/research/adaptive_ensemble/g10/source_snapshot.tar", path)
        rows.append(
            {
                "actual_image_sha256": actual,
                "expected_g12_sha256": expected,
                "g10_sha256": g10,
                "g7_sha256": g7,
                "match_expected_g12": match,
                "matches_g10": actual is not None and actual == g10,
                "matches_g7": actual is not None and actual == g7,
                "path": path,
                "present": present,
                "safety_significance": SIGNIFICANCE[path],
            }
        )
    prior = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g12/image_byte_comparison.json").read_text(encoding="utf-8")
    )
    prior_rows = {item["path"]: item.get("image_sha256") for item in prior["comparisons"]}
    discrepancies = [
        row["path"]
        for row in rows
        if prior_rows.get(row["path"]) != row["actual_image_sha256"] or not row["match_expected_g12"]
    ]
    classification = module.stage_classification(
        archive_ok=archive_ok,
        layers_ok=layers_ok,
        files_ok=files_ok and not discrepancies,
    )
    controls = module.inspect_controls(result["bodies"])
    inventory = module.mutation_inventory(result["bodies"]["forex_bot/oanda_exec.py"])
    attrs = os.lstat(ARCHIVE).st_file_attributes
    rechecked, rechecked_size = module.sha256_path(ARCHIVE)
    secret_paths = [path for path in (ROOT / "data/research/adaptive_ensemble/g12").rglob("*") if path.is_file()]
    secret_paths.extend(ROOT.joinpath("tests").glob("g12*.py"))
    secret_paths.extend(ROOT.joinpath("tests").glob("test_g12*.py"))
    secret = _scan(module, secret_paths)
    review = (
        "POTENTIAL_SECRET_EXPOSURE_REQUIRES_REVIEW"
        if secret["credential_assignment_or_private_key_banner"]
        else "NO_SECRET_EXPOSURE_DETECTED_IN_SCANNED_SCOPE"
    )
    non_public = [item["path"] for item in result["sensitive_names"] if item["classification"] != "public_ca_bundle"]
    public_ca_count = sum(item["classification"] == "public_ca_bundle" for item in result["sensitive_names"])
    if non_public:
        review = "POTENTIAL_SECRET_EXPOSURE_REQUIRES_REVIEW"
    _write(
        "archive_verification.json",
        {
            "archive_sha256": digest,
            "archive_size": size,
            "config_digest": result["config_digest"],
            "config_env_names_only": result["config_env_names"],
            "config_values_stored": False,
            "expected_image_id": EXPECTED_IMAGE,
            "image_id": result["image_id"],
            "layer_count": result["layer_count"],
            "path": str(ARCHIVE),
            "rechecked_sha256": rechecked,
            "rechecked_size": rechecked_size,
            "regular_file": ARCHIVE.is_file() and not ARCHIVE.is_symlink() and not bool(attrs & 0x400),
            "verified_at_utc": stamp,
            "verifier": "tests/g12_1_verify.py",
        },
    )
    _write(
        "layer_verification.json",
        {"layers": result["layers"], "verified_at_utc": stamp},
    )
    _write(
        "merged_filesystem_verification.json",
        {
            "application_file_count": len(result["application_paths"]),
            "application_links": result["application_links"],
            "hidden_application_paths": result["hidden_application_paths"],
            "opaque_directory_handling": "parent contents removed before the layer's new files are applied",
            "provenance_mentions": result["provenance_mentions"],
            "replaced_application_paths": result["replaced_application_paths"],
            "verified_at_utc": stamp,
            "whiteout_handling": "a .wh.name entry removes that path and its children from the merged tree",
        },
    )
    _write(
        "safety_file_comparison.json",
        {"discrepancies_vs_g12_report": discrepancies, "files": rows, "verified_at_utc": stamp},
    )
    _write("broker_mutation_inventory.json", {"controls": controls, "paths": inventory, "verified_at_utc": stamp})
    _write(
        "secret_review.json",
        {
            "classification": review,
            "non_public_sensitive_names": non_public,
            "public_ca_certificate_names": public_ca_count,
            "report_scan": secret,
            "scope_limitation": "Scanned archive member names, image environment names, and project reports. This is not proof that no secret exists.",
            "verified_at_utc": stamp,
        },
    )
    _write(
        "rollback_compatibility.json",
        {
            "candidate_classification": "ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED",
            "candidate_image": result["image_id"],
            "database_py_matches_g7_and_g10": rows[
                next(index for index, row in enumerate(rows) if row["path"] == "forex_bot/database.py")
            ]["matches_g7"]
            and rows[next(index for index, row in enumerate(rows) if row["path"] == "forex_bot/database.py")][
                "matches_g10"
            ],
            "live_database": "LIVE_DATABASE_COMPATIBILITY_UNVERIFIED",
            "rollback_procedure": "ROLLBACK_PROCEDURE_UNVERIFIED",
            "safe_rollback_verified": False,
            "startup_can_execute_ddl_text": controls["database_executes_ddl"],
            "startup_rewrites_mounted_safety_json": controls["initialise_persists_state"],
            "verified_at_utc": stamp,
        },
    )
    cleanup_ok = (
        classification == "INDEPENDENT_FORENSICS_VERIFIED_CLEANUP_APPROVAL_REQUIRED"
        and review == "NO_SECRET_EXPOSURE_DETECTED_IN_SCANNED_SCOPE"
        and rechecked == EXPECTED_ARCHIVE
        and rechecked_size == EXPECTED_SIZE
        and "OneDrive" not in str(ARCHIVE)
    )
    request = OUT / "cleanup_approval_request.md"
    if cleanup_ok:
        request.write_text(
            "\n".join(
                [
                    "# Archive cleanup request",
                    "",
                    "Stage G.12.1 has not deleted this file.",
                    "",
                    f"- Path: `{ARCHIVE}`",
                    f"- Size: `{EXPECTED_SIZE}` bytes",
                    f"- SHA-256: `{EXPECTED_ARCHIVE}`",
                    "- Regular file: yes",
                    "- Parent directory retained: `C:\\Users\\Brian\\AppData\\Local\\Temp\\forex-bot-g12-forensics`",
                    "- Deletion reversible: no",
                    "- Evidence that remains: `data/research/adaptive_ensemble/g12/` and `data/research/adaptive_ensemble/g12_1/`",
                    "- Sensitive-data concern remaining: no credential value was stored in the scanned reports",
                    "- Proposed command:",
                    "",
                    '```powershell',
                    'Remove-Item -LiteralPath "C:\\Users\\Brian\\AppData\\Local\\Temp\\forex-bot-g12-forensics\\image_save.tar"',
                    "```",
                    "",
                    "Cleanup approved: no",
                    "Cleanup performed: no",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        request.write_text(
            "# Archive cleanup request\n\nCleanup is blocked. The archive was not deleted.\n",
            encoding="utf-8",
        )
    print(classification)
    print("files_ok", files_ok, "layers_ok", layers_ok, "discrepancies", discrepancies)
    print("review", review)


if __name__ == "__main__":
    main()
