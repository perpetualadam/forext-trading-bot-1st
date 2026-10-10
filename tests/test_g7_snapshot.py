"""Stage G.7 snapshot generation and independent tamper checks. No Docker."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

from forex_bot.market_provenance import MODEL_VERSION
from forex_bot.research.adaptive_ensemble.g7_snapshot import (
    G7,
    manifest_digest,
    verify_snapshot,
    write_snapshot,
)


def _tar_bytes(members: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _read_members(path: Path) -> list[tuple[str, bytes]]:
    found: list[tuple[str, bytes]] = []
    with tarfile.open(path, "r:") as archive:
        for info in archive.getmembers():
            handle = archive.extractfile(info)
            assert handle is not None
            found.append((info.name, handle.read()))
    return found


def test_snapshot_is_deterministic_and_independently_verified(tmp_path: Path) -> None:
    first_tar = tmp_path / "a.tar"
    first_manifest = tmp_path / "a.json"
    second_tar = tmp_path / "b.tar"
    second_manifest = tmp_path / "b.json"
    first = write_snapshot(first_tar, first_manifest)
    second = write_snapshot(second_tar, second_manifest)
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert hashlib.sha256(first_tar.read_bytes()).hexdigest() == hashlib.sha256(second_tar.read_bytes()).hexdigest()
    checked = verify_snapshot(first_tar, first_manifest)
    assert checked["ok"] is True
    assert first["provenance_version"] == MODEL_VERSION == "market_provenance_v2"
    names = [row["path"] for row in first["files"]]
    assert "forex_bot/market_provenance.py" in names
    assert "Dockerfile" in names
    assert "requirements.txt" in names
    assert "main.py" in names
    assert all(not row["path"].startswith("data/") for row in first["files"])
    assert all(".env" != Path(row["path"]).name for row in first["files"])
    provenance = (Path(__file__).resolve().parents[1] / "forex_bot" / "market_provenance.py").read_text(encoding="utf-8")
    assert 'MODEL_VERSION = "market_provenance_v2"' in provenance
    frozen = json.loads((G7 / "manifest.json").read_text(encoding="utf-8"))
    assert frozen["manifest_sha256"] == "ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989"
    assert verify_snapshot(G7 / "source_snapshot.tar", G7 / "manifest.json")["ok"] is True
    assert frozen["manifest_sha256"] != first["manifest_sha256"]


def test_verifier_detects_each_tamper(tmp_path: Path) -> None:
    tar_path = tmp_path / "base.tar"
    manifest_path = tmp_path / "base.json"
    manifest = write_snapshot(tar_path, manifest_path)
    members = _read_members(tar_path)
    py_index = next(i for i, (name, _data) in enumerate(members) if name.endswith("market_provenance.py"))
    results: dict[str, str] = {}

    changed = list(members)
    name, data = changed[py_index]
    changed[py_index] = (name, data + b"\n")
    tampered = tmp_path / "modified.tar"
    tampered.write_bytes(_tar_bytes(changed))
    results["modified_file"] = str(verify_snapshot(tampered, manifest_path)["reason"])

    bad_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad_manifest["files"][0]["sha256"] = "0" * 64
    bad_path = tmp_path / "bad_manifest.json"
    bad_path.write_text(json.dumps(bad_manifest), encoding="utf-8")
    results["manifest_entry"] = str(verify_snapshot(tar_path, bad_path)["reason"])

    extra = list(members) + [("forex_bot/unexpected_g7.py", b"x = 1\n")]
    extra_path = tmp_path / "extra.tar"
    extra_path.write_bytes(_tar_bytes(extra))
    results["unexpected_file"] = str(verify_snapshot(extra_path, manifest_path)["reason"])

    missing = [item for item in members if item[0] != "Dockerfile"]
    missing_path = tmp_path / "missing.tar"
    missing_path.write_bytes(_tar_bytes(missing))
    results["missing_file"] = str(verify_snapshot(missing_path, manifest_path)["reason"])

    docker = [(item_name, item_data + b"\n" if item_name == "Dockerfile" else item_data) for item_name, item_data in members]
    docker_path = tmp_path / "docker.tar"
    docker_path.write_bytes(_tar_bytes(docker))
    results["dockerfile"] = str(verify_snapshot(docker_path, manifest_path)["reason"])

    first_name, first_data = members[0]
    duplicate = list(members) + [(first_name, first_data)]
    duplicate_path = tmp_path / "duplicate.tar"
    duplicate_path.write_bytes(_tar_bytes(duplicate))
    results["duplicate_path"] = str(verify_snapshot(duplicate_path, manifest_path)["reason"])

    unsafe_path = tmp_path / "unsafe.tar"
    unsafe_path.write_bytes(_tar_bytes(list(members) + [("../outside.py", b"x = 1\n")]))
    results["path_traversal"] = str(verify_snapshot(unsafe_path, manifest_path)["reason"])

    secret_path = tmp_path / "secret.tar"
    secret_path.write_bytes(_tar_bytes(list(members) + [(".env", b"PLACEHOLDER=1\n")]))
    results["secret_path"] = str(verify_snapshot(secret_path, manifest_path)["reason"])

    consistent = json.loads(manifest_path.read_text(encoding="utf-8"))
    consistent["files"][0]["sha256"] = "1" * 64
    consistent["manifest_sha256"] = manifest_digest(consistent)
    consistent_path = tmp_path / "consistent.json"
    consistent_path.write_text(json.dumps(consistent), encoding="utf-8")
    results["consistent_wrong_hash"] = str(verify_snapshot(tar_path, consistent_path)["reason"])

    assert results["modified_file"] == "modified_file"
    assert results["manifest_entry"] == "manifest_hash_mismatch"
    assert results["unexpected_file"] == "unexpected_file"
    assert results["missing_file"] == "missing_file"
    assert results["dockerfile"] == "modified_file"
    assert results["duplicate_path"] == "duplicate_path"
    assert results["path_traversal"] == "unsafe_path"
    assert results["secret_path"] == "secret_path"
    assert results["consistent_wrong_hash"] == "modified_file"
    assert manifest["manifest_sha256"]
