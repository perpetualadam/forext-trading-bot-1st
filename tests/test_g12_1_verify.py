"""Offline checks for the independent G.12.1 reader. The real archive is not deleted."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("g12_1_verify", Path(__file__).with_name("g12_1_verify.py"))
_verify = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_verify)
ForensicIntegrityError = _verify.ForensicIntegrityError
assert_cleanup_approved = _verify.assert_cleanup_approved
function_calls = _verify.function_calls
mutation_sites = _verify.mutation_sites
redact_text = _verify.redact_text
stage_classification = _verify.stage_classification
verify_save = _verify.verify_save


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _layer(entries: list[tuple[str, bytes]]) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, payload in entries:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    raw = buffer.getvalue()
    return gzip.compress(raw), _sha(raw)


def _save(layers: list[tuple[bytes, str]], *, diff_ids: list[str] | None = None, duplicate: bool = False) -> bytes:
    names: list[str] = []
    blobs: list[tuple[str, bytes]] = []
    actual_diffs: list[str] = []
    for compressed, diff in layers:
        digest = _sha(compressed)
        names.append("blobs/sha256/" + digest)
        blobs.append((digest, compressed))
        actual_diffs.append(diff)
    config = {
        "rootfs": {"type": "layers", "diff_ids": ["sha256:" + item for item in (diff_ids or actual_diffs)]},
        "config": {},
    }
    config_bytes = json.dumps(config).encode("utf-8")
    config_digest = _sha(config_bytes)
    manifest = [{"Config": "blobs/sha256/" + config_digest, "Layers": names + (names[:1] if duplicate else [])}]
    index = {"manifests": [{"digest": "sha256:" + "ab" * 32}]}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        def add(name: str, payload: bytes) -> None:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))

        add("manifest.json", json.dumps(manifest).encode("utf-8"))
        add("index.json", json.dumps(index).encode("utf-8"))
        add("blobs/sha256/" + config_digest, config_bytes)
        for digest, payload in blobs:
            add("blobs/sha256/" + digest, payload)
    return buffer.getvalue()


def _write(directory: Path, name: str, blob: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(blob)
    return path


def test_cleanup_requires_a_separate_approval():
    with pytest.raises(PermissionError):
        assert_cleanup_approved(None)


def test_whiteout_and_opaque_layers(tmp_path: Path):
    first, first_diff = _layer(
        [("app/forex_bot/old.py", b"old"), ("app/forex_bot/live_safety.py", b"gate")]
    )
    second, second_diff = _layer(
        [("app/forex_bot/.wh.old.py", b""), ("app/forex_bot/live_safety.py", b"gate2")]
    )
    result = verify_save(_write(tmp_path, "whiteout.tar", _save([(first, first_diff), (second, second_diff)])))
    assert "forex_bot/old.py" not in result["files"]
    assert result["files"]["forex_bot/live_safety.py"] == _sha(b"gate2")
    assert "forex_bot/live_safety.py" in result["replaced_application_paths"]
    opaque, opaque_diff = _layer(
        [("app/forex_bot/.wh..wh..opq", b""), ("app/forex_bot/app.py", b"new")]
    )
    replaced = verify_save(_write(tmp_path, "opaque.tar", _save([(first, first_diff), (opaque, opaque_diff)])))
    assert set(replaced["files"]) == {"forex_bot/app.py"}


def test_rejects_bad_archive_structure(tmp_path: Path):
    layer, diff = _layer([("app/main.py", b"print(1)\n")])
    with pytest.raises(ForensicIntegrityError):
        verify_save(_write(tmp_path, "missing.tar", b"not a tar"))
    bad = _save([(layer, diff)], diff_ids=["0" * 64])
    with pytest.raises(ForensicIntegrityError, match="diff id"):
        verify_save(_write(tmp_path, "diff.tar", bad))
    with pytest.raises(ForensicIntegrityError, match="duplicate"):
        verify_save(_write(tmp_path, "dup-ref.tar", _save([(layer, diff)], duplicate=True)))
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        payload = b"{}"
        info = tarfile.TarInfo("manifest.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(ForensicIntegrityError):
        verify_save(_write(tmp_path, "manifest.tar", buffer.getvalue()))


def test_rejects_unsafe_and_duplicate_members(tmp_path: Path):
    unsafe, unsafe_diff = _layer([("../main.py", b"x")])
    with pytest.raises(ForensicIntegrityError, match="unsafe path"):
        verify_save(_write(tmp_path, "path.tar", _save([(unsafe, unsafe_diff)])))
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as archive:
        for payload in (b"one", b"two"):
            info = tarfile.TarInfo("app/main.py")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    compressed = gzip.compress(raw.getvalue())
    with pytest.raises(ForensicIntegrityError, match="duplicate member"):
        verify_save(_write(tmp_path, "member.tar", _save([(compressed, _sha(raw.getvalue()))])))


def test_missing_layer_and_blob_digest(tmp_path: Path):
    layer, diff = _layer([("app/main.py", b"print(1)\n")])
    compressed_digest = hashlib.sha256(layer).hexdigest()
    config = {"rootfs": {"type": "layers", "diff_ids": ["sha256:" + diff]}, "config": {}}
    config_bytes = json.dumps(config).encode("utf-8")
    config_digest = hashlib.sha256(config_bytes).hexdigest()
    manifest = [{"Config": "blobs/sha256/" + config_digest, "Layers": ["blobs/sha256/" + "ab" * 32]}]
    index = {"manifests": [{"digest": "sha256:" + "cd" * 32}]}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, payload in (
            ("manifest.json", json.dumps(manifest).encode("utf-8")),
            ("index.json", json.dumps(index).encode("utf-8")),
            ("blobs/sha256/" + config_digest, config_bytes),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(ForensicIntegrityError):
        verify_save(_write(tmp_path, "missing-layer.tar", buffer.getvalue()))
    bad_manifest = [{"Config": "blobs/sha256/" + config_digest, "Layers": ["blobs/sha256/" + compressed_digest]}]
    bad_config = {"rootfs": {"type": "layers", "diff_ids": ["sha256:" + diff]}, "config": {}}
    bad_config_bytes = json.dumps(bad_config).encode("utf-8")
    bad_config_digest = hashlib.sha256(bad_config_bytes).hexdigest()
    bad_manifest[0]["Config"] = "blobs/sha256/" + bad_config_digest
    bad_buffer = io.BytesIO()
    with tarfile.open(fileobj=bad_buffer, mode="w") as archive:
        for name, payload in (
            ("manifest.json", json.dumps(bad_manifest).encode("utf-8")),
            ("index.json", json.dumps(index).encode("utf-8")),
            ("blobs/sha256/" + bad_config_digest, bad_config_bytes),
            ("blobs/sha256/" + compressed_digest, b"not-the-layer"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(ForensicIntegrityError, match="blob digest"):
        verify_save(_write(tmp_path, "bad-blob.tar", bad_buffer.getvalue()))


def test_markers_mutations_and_redaction():
    source = """
def initialise_fail_closed():
    _set_effective_blocked()

def _place_market_order_open_sync():
    assert_new_live_exposure_allowed()
    oanda_orders.OrderCreate()

def _place_market_order_sync():
    oanda_positions.PositionClose()
"""
    assert function_calls(source, "initialise_fail_closed") == ["_set_effective_blocked"]
    labels = function_calls(source, "_place_market_order_open_sync")
    assert labels.index("assert_new_live_exposure_allowed") < labels.index("oanda_orders.OrderCreate")
    assert {row["call"] for row in mutation_sites(source)} == {
        "oanda_orders.OrderCreate",
        "oanda_positions.PositionClose",
    }
    report = redact_text("OANDA_ACCESS_TOKEN=hidden-value\n")
    assert report["credential_assignment"] is True
    assert "hidden-value" not in json.dumps(report)
    assert stage_classification(archive_ok=False, layers_ok=True, files_ok=True) == "FORENSIC_ARCHIVE_INTEGRITY_FAILED"
    assert stage_classification(archive_ok=True, layers_ok=False, files_ok=True) == "FORENSIC_LAYER_INTEGRITY_FAILED"
    assert stage_classification(archive_ok=True, layers_ok=True, files_ok=False) == (
        "INDEPENDENT_FORENSICS_PARTIAL_CLEANUP_BLOCKED"
    )
    verified = stage_classification(archive_ok=True, layers_ok=True, files_ok=True)
    assert verified == "INDEPENDENT_FORENSICS_VERIFIED_CLEANUP_APPROVAL_REQUIRED"
    assert "ROLLBACK_AUTHORISED" not in verified
