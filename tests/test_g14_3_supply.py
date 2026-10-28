"""Offline tests for the G.14.3 supply-chain analysis."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGING = Path(r"C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2")
PREVIOUS = (
    'docker build --pull=false --progress=plain -f '
    '"C:\\Users\\Brian\\AppData\\Local\\Temp\\forext-g14-1-staging-0yifygx2\\Dockerfile" '
    "-t forexttradingbot1st-g14-candidate:d080d89-4a458b4b "
    '"C:\\Users\\Brian\\AppData\\Local\\Temp\\forext-g14-1-staging-0yifygx2"'
)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SUPPLY = _load("g14_3_supply")
VERIFY = _load("g14_1_verify")


def test_direct_requirements_are_unpinned_and_unhashed() -> None:
    records = SUPPLY.parse_requirements((ROOT / "requirements.txt").read_text(encoding="utf-8"))
    summary = SUPPLY.inventory_summary(records)
    assert summary["direct_requirement_count"] == 9
    assert summary["exact_pins"] == 0
    assert summary["minimum_unbounded"] == 9
    assert summary["compatible_releases"] == 0
    assert summary["missing_hashes"] == 9
    assert summary["transitive_versions"] == "UNKNOWN"
    assert summary["complete_transitive_lock"] is False
    assert summary["native_extension_packages"] == ["pandas", "numpy", "psycopg2-binary"]
    uvicorn = next(row for row in records if row["name"] == "uvicorn")
    assert uvicorn["extras"] == ["standard"]
    assert all(row["direct_url"] is None for row in records)
    assert all(row["environment_marker"] is None for row in records)
    assert all(row["source_distribution_fallback_possible"] for row in records)
    assert all(row["installation_hooks_possible"] for row in records)


def test_fabricated_lock_and_digest_claims_are_rejected() -> None:
    problems = SUPPLY.lock_claim_problems(
        {
            "claims_complete_transitive_lock": True,
            "transitive_versions": "UNKNOWN",
            "claims_hashes_verified": True,
            "hashes": [],
            "claims_registry_digest_verified": True,
            "image_id": "sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254",
            "registry_digest": "python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254",
        }
    )
    assert problems == [
        "fabricated_completeness",
        "missing_hashes",
        "unknown_base_digest_claim",
    ]


def test_image_id_is_not_accepted_as_a_registry_digest() -> None:
    image_id = "sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254"
    identity = SUPPLY.classify_base_identity(image_id, [f"python@{image_id}"])
    assert identity["registry_manifest_digest_known"] is False
    assert identity["repo_digest_repeats_image_id"] is True
    assert identity["immutable_from_reference_available"] is False
    assert identity["classification"] == "BASE_IMAGE_DIGEST_UNVERIFIED"
    assert identity["configuration_digest_separately_recorded"] is False
    assert identity["multi_platform_manifest_list_digest"] == "UNKNOWN"


def test_pip_upgrade_and_source_fallback_are_identified() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    findings = SUPPLY.pip_toolchain_findings(dockerfile)
    assert findings["upgrades_pip_without_exact_pin"] is True
    assert findings["known_pip_version"] == "UNKNOWN"
    assert findings["classification"] == "PIP_TOOLCHAIN_VERSION_UNVERIFIED"
    assert SUPPLY.source_fallback_allowed(dockerfile) is True


def test_previous_build_command_is_not_reproducible() -> None:
    assert SUPPLY.previous_command_recommendation(PREVIOUS) == "REPLACE_WITH_LOCKED_OFFLINE_BUILD_PROPOSAL"


def test_recorded_g14_2_evidence_is_not_upgraded() -> None:
    evidence = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g14_2/base_image_preflight.json").read_text(encoding="utf-8")
    )
    assert evidence["classification"] == "BASE_IMAGE_DIGEST_UNVERIFIED"
    assert evidence["repo_digest_equals_image_id"] is True
    assert evidence["sufficient_to_pin_a_future_from_instruction"] is False
    assert evidence["pull_performed"] is False


def test_manifest_inventory_excludes_backup_names_and_matches_digest() -> None:
    manifest = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g14_1/staged_context_manifest.json").read_text(encoding="utf-8")
    )
    canonical = json.dumps({"files": manifest["files"]}, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    assert digest == "8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b"
    assert manifest["total_files"] == 63
    assert manifest["total_bytes"] == 617279
    names = {Path(row["path"]).name for row in manifest["files"]}
    assert "main example .env backup.txt" not in names
    assert "# Copy to .env and fill in. docker.txt" not in names
    assert ".env" not in names


def test_historical_staging_directory_matches(historical_staging_root) -> None:
    manifest = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g14_1/staged_context_manifest.json").read_text(encoding="utf-8")
    )
    checked = VERIFY.verify_directory(historical_staging_root, manifest["files"])
    assert checked["file_count"] == 63
    assert checked["independent_verification"] == "PASS"


def test_historical_packaging_hashes_remain_authorised(historical_packaging_root) -> None:
    expected = {
        "Dockerfile": "4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad",
        ".dockerignore": "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd",
        "requirements.txt": "45bc21ba5d8f336c0da5092024cee96103f0251d7c7f55e70056a7c55d194b0a",
    }
    for rel, digest in expected.items():
        assert hashlib.sha256((historical_packaging_root / rel).read_bytes()).hexdigest() == digest


def test_analysis_module_does_not_reference_network_clients() -> None:
    source = Path(__file__).with_name("g14_3_supply.py").read_text(encoding="utf-8")
    for banned in ("import urllib", "import requests", "import subprocess", "import docker", "import socket"):
        assert banned not in source
