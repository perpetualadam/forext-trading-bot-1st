"""Synthetic fail-closed tests for the Gate A wheelhouse verifier."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGING = Path(r"C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFY = _load("g14_4_verify")
ACQUIRE = _load("g14_4_acquire")
INVENTORY = _load("g14_4_inventory")
CONTENT = VERIFY.build_synthetic_wheel("demo", "1.0.0")


def _package(filename: str = "demo-1.0.0-py3-none-any.whl", content: bytes = CONTENT, **overrides: object) -> dict[str, object]:
    package: dict[str, object] = {
        "name": "demo",
        "version": "1.0.0",
        "filename": filename,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
        "direct": True,
        "extras": [],
        "markers": None,
        "requires": [],
        "provenance": "synthetic-fixture",
        "url": None,
        "vcs": None,
    }
    package.update(overrides)
    return package


def _manifest(packages: list[dict[str, object]], **overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": VERIFY.SCHEMA_VERSION,
        "synthetic": True,
        "status": VERIFY.SYNTHETIC_STATUS,
        "target": {
            "implementation": "cp",
            "python_major_minor": "3.12",
            "python_patch": "UNKNOWN",
            "os": "linux",
            "arch": "x86_64",
        },
        "source": {
            "index_url": VERIFY.SYNTHETIC_INDEX,
            "source_approved": False,
            "additional_indexes": [],
        },
        "packages": packages,
        "toolchain": {"pip_version": "UNKNOWN", "resolver": "UNKNOWN"},
        "claimed_state": None,
    }
    document.update(overrides)
    return document


def _write(tmp: Path, packages: list[dict[str, object]], content: bytes = CONTENT) -> Path:
    wheelhouse = tmp / "wheelhouse"
    wheelhouse.mkdir(parents=True)
    for package in packages:
        filename = str(package["filename"])
        if "/" in filename or "\\" in filename or ".." in filename or ":" in filename:
            continue
        (wheelhouse / filename).write_bytes(content)
    return wheelhouse


def _expect(tmp: Path, packages: list[dict[str, object]], reason: str, content: bytes = CONTENT) -> None:
    wheelhouse = _write(tmp, packages, content)
    with pytest.raises(VERIFY.VerificationRejected, match=reason):
        VERIFY.verify_wheelhouse(_manifest(packages), wheelhouse)


def test_valid_synthetic_inventory_is_not_a_real_lock(tmp_path: Path) -> None:
    packages = [_package()]
    result = VERIFY.verify_wheelhouse(_manifest(packages), _write(tmp_path, packages))
    assert result["hash_integrity"] == "PASS"
    assert result["source_provenance"] == "SYNTHETIC_NOT_AN_APPROVED_SOURCE"
    assert result["real_wheelhouse_acquired"] == "false"
    assert result["real_dependency_lock_created"] == "false"


def test_missing_extra_and_non_wheel_files_fail(tmp_path: Path) -> None:
    packages = [_package()]
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir(parents=True)
    with pytest.raises(VERIFY.VerificationRejected, match="missing_wheel"):
        VERIFY.verify_wheelhouse(_manifest(packages), wheelhouse)
    wheelhouse = _write(tmp_path / "extra", packages)
    (wheelhouse / "other-1.0.0-py3-none-any.whl").write_bytes(CONTENT)
    with pytest.raises(VERIFY.VerificationRejected, match="extra_wheel"):
        VERIFY.verify_wheelhouse(_manifest(packages), wheelhouse)
    wheelhouse = _write(tmp_path / "notes", packages)
    (wheelhouse / "notes.txt").write_bytes(b"notes\n")
    with pytest.raises(VERIFY.VerificationRejected, match="extra_non_wheel"):
        VERIFY.verify_wheelhouse(_manifest(packages), wheelhouse)


def test_hash_size_and_malformed_digest_fail(tmp_path: Path) -> None:
    bad_hash = _package(sha256="0" * 64)
    _expect(tmp_path / "hash", [bad_hash], "hash_mismatch")
    bad_size = _package(size=1)
    _expect(tmp_path / "size", [bad_size], "size_mismatch")
    malformed = _package(sha256="not-a-hash")
    _expect(tmp_path / "malformed", [malformed], "malformed_sha256")


def test_duplicate_case_path_and_tag_failures(tmp_path: Path) -> None:
    first = _package()
    second = _package()
    _expect(tmp_path / "dup", [first, second], "duplicate_filename")
    folded = _package(filename="Demo-1.0.0-py3-none-any.whl")
    _expect(tmp_path / "case", [first, folded], "case_collision")
    _expect(tmp_path / "travel", [_package(filename="../demo-1.0.0-py3-none-any.whl")], "path_traversal")
    _expect(tmp_path / "abs", [_package(filename="C:/demo-1.0.0-py3-none-any.whl")], "absolute_path")
    _expect(
        tmp_path / "abi",
        [_package(filename="demo-1.0.0-cp312-cp39-manylinux_2_28_x86_64.whl")],
        "unsupported_wheel_tag",
    )
    _expect(tmp_path / "py", [_package(filename="demo-1.0.0-cp311-cp311-manylinux_2_28_x86_64.whl")], "incorrect_python")
    _expect(tmp_path / "arch", [_package(filename="demo-1.0.0-cp312-cp312-win_amd64.whl")], "incorrect_architecture")
    _expect(tmp_path / "sdist", [_package(filename="demo-1.0.0.tar.gz")], "source_distribution")


def test_graph_source_and_metadata_failures(tmp_path: Path) -> None:
    same = _package(filename="demo-1.0.0-py3-none-manylinux_2_28_x86_64.whl")
    _expect(tmp_path / "same", [_package(), same], "duplicate_package")
    other = _package(filename="demo-2.0.0-py3-none-any.whl", version="2.0.0")
    _expect(tmp_path / "conflict", [_package(), other], "conflicting_versions")
    _expect(tmp_path / "edge", [_package(requires=["missing"])], "missing_dependency")
    packages = [_package()]
    wheelhouse = _write(tmp_path / "source", packages)
    manifest = _manifest(packages)
    source_value = manifest["source"]
    assert isinstance(source_value, dict)
    source = dict(source_value)
    source["index_url"] = "https://evil.example/simple"
    manifest["source"] = source
    with pytest.raises(VERIFY.VerificationRejected, match="unknown_source"):
        VERIFY.verify_wheelhouse(manifest, wheelhouse)
    manifest = _manifest(packages)
    source_value = manifest["source"]
    assert isinstance(source_value, dict)
    source = dict(source_value)
    source["additional_indexes"] = ["https://extra.example/simple"]
    manifest["source"] = source
    with pytest.raises(VERIFY.VerificationRejected, match="unapproved_additional_index"):
        VERIFY.verify_wheelhouse(manifest, _write(tmp_path / "index", packages))
    _expect(tmp_path / "url", [_package(url="https://files.example/demo.whl")], "unapproved_direct_url")
    _expect(tmp_path / "vcs", [_package(vcs="git+https://example.invalid/demo.git")], "unapproved_vcs")
    _expect(tmp_path / "prov", [_package(provenance="")], "missing_provenance")
    manifest = _manifest(packages)
    del manifest["packages"]
    with pytest.raises(VERIFY.VerificationRejected, match="incomplete_manifest"):
        VERIFY.verify_wheelhouse(manifest, _write(tmp_path / "schema", packages))
    manifest = _manifest(packages, schema_version="not-a-schema")
    with pytest.raises(VERIFY.VerificationRejected, match="malformed_schema_version"):
        VERIFY.verify_wheelhouse(manifest, _write(tmp_path / "version", packages))
    poisoned = _package(authorization="Bearer synthetic")
    _expect(tmp_path / "cred", [poisoned], "credential_metadata")
    _expect(tmp_path / "backup", [_package(filename="main example .env backup.txt")], "sensitive_backup_filename")
    _expect(tmp_path / "ops", [_package(filename="live_safety_state.json")], "operational_state_filename")
    manifest = _manifest(packages, claimed_state="INDEPENDENT_ARTIFACT_VERIFICATION_COMPLETE")
    with pytest.raises(VERIFY.VerificationRejected, match="false_completion_claim"):
        VERIFY.verify_wheelhouse(manifest, tmp_path / "missing-artifacts")


def test_symlink_and_reparse_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packages = [_package()]
    wheelhouse = _write(tmp_path, packages)
    real = os.lstat

    def linked(path: os.PathLike[str] | str) -> os.stat_result:
        if Path(path).name.endswith(".whl"):
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)  # type: ignore[return-value]
        return real(path)

    monkeypatch.setattr(VERIFY.os, "lstat", linked)
    with pytest.raises(VERIFY.VerificationRejected, match="symlink_or_reparse"):
        VERIFY.verify_wheelhouse(_manifest(packages), wheelhouse)

    def reparse(path: os.PathLike[str] | str) -> os.stat_result:
        if Path(path).name.endswith(".whl"):
            return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)  # type: ignore[return-value]
        return real(path)

    monkeypatch.setattr(VERIFY.os, "lstat", reparse)
    with pytest.raises(VERIFY.VerificationRejected, match="symlink_or_reparse"):
        VERIFY.verify_wheelhouse(_manifest(packages), wheelhouse)


def test_destination_guard_refuses_real_locations(tmp_path: Path) -> None:
    assert ACQUIRE.WHEELHOUSE_CREATED is False
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "preexisting.whl").write_bytes(b"preexisting\n")
    with pytest.raises(ACQUIRE.DestinationRejected, match="destination_not_empty"):
        ACQUIRE.assert_destination_allowed(occupied)
    with pytest.raises(ACQUIRE.DestinationRejected, match="inside_repository"):
        ACQUIRE.assert_destination_allowed(ROOT / "data")
    with pytest.raises(ACQUIRE.DestinationRejected, match="inside_onedrive"):
        ACQUIRE.assert_destination_allowed(Path.home() / "OneDrive" / "not-created")
    with pytest.raises(ACQUIRE.DestinationRejected, match="inside_staging_context"):
        ACQUIRE.assert_destination_allowed(STAGING)


def test_direct_requirements_reconcile_to_nine() -> None:
    rows = INVENTORY.parse_requirements((ROOT / "requirements.txt").read_text(encoding="utf-8"))
    prior = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g14_3/direct_dependency_inventory.json").read_text(encoding="utf-8")
    )
    assert len(rows) == 9
    assert prior["summary"]["direct_requirement_count"] == 9
    assert sum(1 for row in rows if row["exactly_pinned"]) == 0
    assert sum(1 for row in rows if row["hashes_present"]) == 0
    assert all(row["transitive_versions"] == "UNKNOWN" for row in rows)
    assert [row["normalized_name"] for row in rows if row["native_extension_possible"]] == [
        "pandas",
        "numpy",
        "psycopg2-binary",
    ]


def test_helpers_do_not_reference_network_clients() -> None:
    for name in ("g14_4_verify.py", "g14_4_acquire.py", "g14_4_inventory.py"):
        source = Path(__file__).with_name(name).read_text(encoding="utf-8")
        for banned in ("import urllib", "import requests", "import socket", "import subprocess", "import docker"):
            assert banned not in source


def test_staging_context_remains_when_present() -> None:
    if not STAGING.is_dir():
        pytest.skip("local staging directory is absent")
    verifier = _load("g14_1_verify")
    manifest = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g14_1/staged_context_manifest.json").read_text(encoding="utf-8")
    )
    checked = verifier.verify_directory(STAGING, manifest["files"])
    assert checked["file_count"] == 63
    assert checked["independent_verification"] == "PASS"
