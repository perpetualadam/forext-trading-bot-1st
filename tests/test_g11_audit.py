"""Stage G.11 audit checks. No Docker daemon and no broker calls."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "g11_audit_helpers",
    Path(__file__).with_name("g11_audit_helpers.py"),
)
_helpers = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_helpers)
G10_ARCHIVE = _helpers.G10_ARCHIVE
HISTORICAL_STAGE_A_IMAGE = _helpers.HISTORICAL_STAGE_A_IMAGE
NO_ROLLBACK = _helpers.NO_ROLLBACK
UNSAFE_IMAGE = _helpers.UNSAFE_IMAGE
allowlist_drift = _helpers.allowlist_drift
classify_image = _helpers.classify_image
mutation_inventory = _helpers.mutation_inventory
redact_env = _helpers.redact_env
rollback_decision = _helpers.rollback_decision

ROOT = Path(__file__).resolve().parents[1]


def test_redaction_drops_secret_values():
    secret = "token-value-must-not-leak"
    redacted = redact_env(["OANDA_ACCESS_TOKEN=" + secret, "EMPTY="])
    encoded = json.dumps(redacted)
    assert secret not in encoded
    assert redacted[0]["present"] is True
    assert redacted[1]["present"] is False


def test_unsafe_image_is_rejected_and_tag_is_not_identity():
    assert classify_image(UNSAFE_IMAGE, contents_proven=True, provenance=True, management=True) == (
        "ROLLBACK_CANDIDATE_REJECTED"
    )
    assert (
        classify_image(HISTORICAL_STAGE_A_IMAGE, contents_proven=False, provenance=False, management=False)
        == "ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED"
    )
    decision = rollback_decision(
        [
            {"image_id": HISTORICAL_STAGE_A_IMAGE, "classification": "ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED"},
            {"image_id": UNSAFE_IMAGE, "classification": "ROLLBACK_CANDIDATE_REJECTED"},
        ]
    )
    assert decision == NO_ROLLBACK


def test_mutation_inventory_keeps_open_and_close_only():
    source = (ROOT / "forex_bot/oanda_exec.py").read_text(encoding="utf-8")
    rows = mutation_inventory(source)
    markers = {row["marker"] for row in rows}
    assert markers == {"oanda_orders.OrderCreate", "oanda_positions.PositionClose"}
    assert "oanda_orders.OrderCancel" not in source


def test_g10_allowlist_has_not_drifted(tmp_path: Path):
    allow = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g10/production_allowlist.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g10/source_manifest.json").read_text(encoding="utf-8")
    )
    by_path = {row["path"]: row["sha256"] for row in manifest["files"]}
    assert allowlist_drift(allow["files"], by_path, ROOT) == []
    assert len(allow["files"]) == 63
    sample = tmp_path / "main.py"
    sample.write_text("changed\n", encoding="utf-8")
    digest = hashlib.sha256(b"original").hexdigest()
    assert allowlist_drift([{"path": "main.py", "sha256": digest}], {"main.py": digest}, tmp_path) == ["main.py"]


def test_frozen_g10_archive_unchanged():
    archive = ROOT / "data/research/adaptive_ensemble/g10/source_snapshot.tar"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == G10_ARCHIVE
