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


def test_g10_allowlist_has_not_drifted(tmp_path: Path, historical_packaging_root):
    allow = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g10/production_allowlist.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g10/source_manifest.json").read_text(encoding="utf-8")
    )
    by_path = {row["path"]: row["sha256"] for row in manifest["files"]}
    # Historical drift detection remains. The authorised G.13 Dockerfile repair is
    # the only accepted difference, and its hash is pinned rather than ignored.
    spec = importlib.util.spec_from_file_location("g13_1_baseline", Path(__file__).with_name("g13_1_baseline.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("g13.1 baseline helper is unavailable")
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    assert hashlib.sha256(
        (ROOT / "data/research/adaptive_ensemble/g10/production_allowlist.json").read_bytes()
    ).hexdigest() == baseline.ALLOWLIST_FILE_SHA256
    assert allowlist_drift(allow["files"], by_path, historical_packaging_root) == ["Dockerfile"]
    assert hashlib.sha256((historical_packaging_root / "Dockerfile").read_bytes()).hexdigest() == baseline.AUTHORISED_DOCKERFILE_SHA256
    assert len(allow["files"]) == 63
    allow_report = baseline.evaluate_allowlist(
        allow["files"],
        historical_packaging_root,
        expected_paths={row["path"] for row in allow["files"]},
        manifest_hashes=by_path,
    )
    assert allow_report["ok"], allow_report
    audit = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g10/production_dependency_audit.json").read_text(encoding="utf-8")
    )
    included = {row["path"] for row in allow["files"]}
    assert included.isdisjoint(audit["research_only"])
    assert audit["counts"]["RESEARCH_ONLY"] == 128
    sample = tmp_path / "main.py"
    sample.write_text("changed\n", encoding="utf-8")
    digest = hashlib.sha256(b"original").hexdigest()
    assert allowlist_drift([{"path": "main.py", "sha256": digest}], {"main.py": digest}, tmp_path) == ["main.py"]


def test_frozen_g10_archive_unchanged():
    archive = ROOT / "data/research/adaptive_ensemble/g10/source_snapshot.tar"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == G10_ARCHIVE
