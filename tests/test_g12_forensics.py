"""Synthetic image-layer tests. The running image is not read."""

from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("g12_forensics", Path(__file__).with_name("g12_forensics.py"))
_forensics = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_forensics)
RUNNING_IMAGE = _forensics.RUNNING_IMAGE
UNSAFE_IMAGE = _forensics.UNSAFE_IMAGE
ForensicRefusal = _forensics.ForensicRefusal
assert_export_approved = _forensics.assert_export_approved
layer_tar = _forensics.layer_tar
merge_layers = _forensics.merge_layers
parse_save_manifest = _forensics.parse_save_manifest
redact_finding = _forensics.redact_finding
rollback_verdict = _forensics.rollback_verdict
select_files = _forensics.select_files


def test_approval_gate_blocks_real_image_export():
    with pytest.raises(ForensicRefusal):
        assert_export_approved(None, RUNNING_IMAGE)
    with pytest.raises(ForensicRefusal):
        assert_export_approved("OPERATOR_APPROVED_IMAGE_SAVE", UNSAFE_IMAGE)


def test_whiteout_hides_lower_file_without_erasing_the_lower_blob():
    lower = layer_tar([("app/a.txt", b"old", "file"), ("app/secret.txt", b"token=hidden", "file")])
    upper = layer_tar([("app/.wh.secret.txt", b"", "file"), ("app/a.txt", b"new", "file")])
    merged = merge_layers([lower, upper])
    assert merged["app/a.txt"] == b"new"
    assert "app/secret.txt" not in merged
    assert b"token=hidden" in lower


def test_opaque_directory_replaces_lower_children():
    lower = layer_tar([("pkg/old.py", b"old", "file"), ("pkg/keep.py", b"keep", "file")])
    upper = layer_tar([("pkg/.wh..wh..opq", b"", "file"), ("pkg/new.py", b"new", "file")])
    merged = merge_layers([lower, upper])
    assert set(merged) == {"pkg/new.py"}


def test_unsafe_members_are_rejected():
    with pytest.raises(ValueError, match="unsafe_path"):
        merge_layers([layer_tar([("../x", b"a", "file")])])
    with pytest.raises(ValueError, match="unsafe_path"):
        merge_layers([layer_tar([("/tmp/x", b"a", "file")])])
    with pytest.raises(ValueError, match="unsupported_member"):
        merge_layers([layer_tar([("a.txt", b"", "symlink")])])
    with pytest.raises(ValueError, match="unsupported_member"):
        merge_layers([layer_tar([("a.txt", b"", "hardlink")])])
    with pytest.raises(ValueError, match="unsupported_member"):
        merge_layers([layer_tar([("a.fifo", b"", "fifo")])])


def test_duplicate_member_in_one_layer_is_rejected():
    first = layer_tar([("a.txt", b"one", "file")])
    second = layer_tar([("a.txt", b"two", "file")])
    # Concatenated tar archives are two layers only if passed separately.
    # A single archive with two entries is built here.
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for payload in (b"one", b"two"):
            info = tarfile.TarInfo("a.txt")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(ValueError, match="duplicate_member"):
        merge_layers([buffer.getvalue()])
    assert first != second


def test_selective_hash_and_secret_redaction():
    tree = merge_layers([layer_tar([("forex_bot/app.py", b"print(1)\n", "file")])])
    selected = select_files(tree, {"forex_bot/app.py", "forex_bot/missing.py"})
    assert "forex_bot/missing.py" not in selected
    assert len(selected["forex_bot/app.py"]) == 64
    report = redact_finding("OANDA_ACCESS_TOKEN=should-not-appear\n")
    assert report["credential_assignment"] is True
    assert report["value_stored"] is False
    assert "should-not-appear" not in json.dumps(report)


def test_layer_order_and_rollback_rules():
    save = io.BytesIO()
    with tarfile.open(fileobj=save, mode="w") as archive:
        payload = json.dumps([{"Layers": ["a/layer.tar", "b/layer.tar"]}]).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    assert parse_save_manifest(save.getvalue()) == ["a/layer.tar", "b/layer.tar"]
    assert rollback_verdict(contents_proven=False, database_proven=False, procedure_reviewed=False) == (
        "ROLLBACK_CANDIDATE_UNVERIFIED"
    )
    assert rollback_verdict(contents_proven=True, database_proven=False, procedure_reviewed=False) == (
        "ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED"
    )
