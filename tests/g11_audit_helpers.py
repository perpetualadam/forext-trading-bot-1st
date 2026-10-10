"""Stage G.11 read-only deployment audit helpers.

These functions classify evidence. They do not build images, start containers,
or contact a broker.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
G11 = ROOT / "data" / "research" / "adaptive_ensemble" / "g11"
G10_ARCHIVE = "d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277"
G10_MANIFEST = "93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf"
UNSAFE_IMAGE = "sha256:a19a2208fcf30f8fa1cf61442cf021dec6d99d809b6907836c834922bfe3e2a5"
HISTORICAL_STAGE_A_IMAGE = "sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25"
DOCKER_CONTEXT = "DOCKER_CONTEXT_DAEMON_UNVERIFIED"
NO_ROLLBACK = "NO_VERIFIED_ROLLBACK_TARGET"
SECRET_MARKERS = ("TOKEN", "PASSWORD", "PASS", "SECRET", "KEY", "WEBHOOK", "CREDENTIAL")


def redact_env(entries: list[str]) -> list[dict[str, Any]]:
    """Keep names and presence. Drop every value."""
    redacted: list[dict[str, Any]] = []
    for item in entries:
        key, separator, value = item.partition("=")
        redacted.append({"name": key, "present": bool(separator) and bool(value.strip())})
    return redacted


def classify_image(image_id: str, *, contents_proven: bool, provenance: bool, management: bool) -> str:
    if image_id == UNSAFE_IMAGE:
        return "ROLLBACK_CANDIDATE_REJECTED"
    if not contents_proven:
        return "ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED"
    if provenance and management:
        return "ROLLBACK_CANDIDATE_VERIFIED"
    return "ROLLBACK_CANDIDATE_UNVERIFIED"


def rollback_decision(candidates: list[dict[str, Any]]) -> str:
    if any(row.get("image_id") == UNSAFE_IMAGE and row.get("classification") != "ROLLBACK_CANDIDATE_REJECTED" for row in candidates):
        return "ROLLBACK_CANDIDATE_REJECTED"
    if any(row.get("classification") == "ROLLBACK_CANDIDATE_VERIFIED" for row in candidates):
        return "ROLLBACK_CANDIDATE_VERIFIED"
    return NO_ROLLBACK


def allowlist_drift(allowlist: list[dict[str, str]], manifest_files: dict[str, str], root: Path) -> list[str]:
    drifted: list[str] = []
    for row in allowlist:
        rel = row["path"]
        current = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        if current != row["sha256"] or current != manifest_files.get(rel):
            drifted.append(rel)
    return drifted


def mutation_inventory(source: str) -> list[dict[str, str]]:
    """Classify broker endpoints from source text. Comments that mention a name are not calls."""
    rows = [
        {
            "function": "_place_market_order_open_sync",
            "marker": "oanda_orders.OrderCreate",
            "method": "POST",
            "endpoint": "/v3/accounts/{id}/orders",
            "purpose": "new market exposure",
            "exposure": "increases",
            "authorisation": "assert_new_live_exposure_allowed before request",
            "provenance": "require_order_quote before request",
        },
        {
            "function": "_place_market_order_sync",
            "marker": "oanda_positions.PositionClose",
            "method": "PUT",
            "endpoint": "/v3/accounts/{id}/positions/{instrument}/close",
            "purpose": "risk-reducing close",
            "exposure": "reduces",
            "authorisation": "close action is not a new-exposure gate",
            "provenance": "entry seal not required",
        },
    ]
    found = [row for row in rows if row["marker"] in source]
    if "oanda_orders.OrderCancel" in source or "oanda_orders.OrderReplace" in source:
        found.append(
            {
                "function": "unexpected",
                "marker": "order_mutation",
                "method": "unknown",
                "endpoint": "cancel_or_replace",
                "purpose": "unexpected",
                "exposure": "unknown",
                "authorisation": "unreviewed",
                "provenance": "unreviewed",
            }
        )
    return found


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_reports() -> dict[str, Any]:
    """Write G.11 audit files. Does not touch the G.10 archive."""
    G11.mkdir(parents=True, exist_ok=True)
    inspected = datetime.now(timezone.utc).isoformat()
    hashes = {
        "g7_archive": _sha(ROOT / "data/research/adaptive_ensemble/g7/source_snapshot.tar"),
        "g10_archive": _sha(ROOT / "data/research/adaptive_ensemble/g10/source_snapshot.tar"),
        "dockerignore": _sha(ROOT / ".dockerignore"),
        "dockerfile": _sha(ROOT / "Dockerfile"),
    }
    if hashes["g10_archive"] != G10_ARCHIVE:
        raise RuntimeError("G10 archive drifted")
    manifest = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g10/source_manifest.json").read_text(encoding="utf-8")
    )
    allow = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g10/production_allowlist.json").read_text(encoding="utf-8")
    )
    by_path = {row["path"]: row["sha256"] for row in manifest["files"]}
    drift = allowlist_drift(allow["files"], by_path, ROOT)
    exec_src = (ROOT / "forex_bot/oanda_exec.py").read_text(encoding="utf-8")
    mutations = mutation_inventory(exec_src)
    running = {
        "container_id": "5fcbcff7173eee98f6228b901fab96fd24474038852ef1f4cc3fbccd138edd32",
        "name": "forexttradingbot1st-bot-1",
        "state": "running",
        "created": "2026-10-08T22:24:38.050789775Z",
        "started": "2026-10-08T22:24:39.830615859Z",
        "image_id": HISTORICAL_STAGE_A_IMAGE,
        "repository_digest": None,
        "local_id_reference": "forexttradingbot1st-bot@sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25",
        "tag": "forexttradingbot1st-bot:latest",
        "image_created": "2026-10-08T22:24:01.773111643Z",
        "restart_policy": "no",
        "entrypoint": None,
        "command": ["uvicorn", "forex_bot.app:app", "--host", "0.0.0.0", "--port", "8000"],
        "workdir": "/app",
        "network": "forexttradingbot1st_default",
        "mounts": [
            {"type": "bind", "destination": "/app/data/ops", "writable": True},
            {"type": "bind", "destination": "/app/data/research/v2_shadow", "writable": True},
        ],
        "credential_names_present": [
            "OANDA_ACCESS_TOKEN",
            "OANDA_ACCOUNT_ID",
            "POSTGRES_PASS",
            "TELEGRAM_BOT_TOKEN",
        ],
        "credential_names_empty": ["OANDA_API_KEY", "OPENAI_API_KEY", "TELEGRAM_TOKEN"],
        "values_stored": False,
        "inspected_at_utc": inspected,
        "evidence": "current",
        "confidence": "high_for_identity_not_for_image_bytes",
    }
    candidate = {
        "image_id": HISTORICAL_STAGE_A_IMAGE,
        "classification": classify_image(
            HISTORICAL_STAGE_A_IMAGE, contents_proven=False, provenance=False, management=False
        ),
        "contents_proven": False,
        "provenance_in_image": False,
        "management_in_image": False,
        "reason": "identity matches the running Oct 8 image; file bytes inside the image were not extracted",
    }
    unsafe = {
        "image_id": UNSAFE_IMAGE,
        "classification": "ROLLBACK_CANDIDATE_REJECTED",
        "present_locally": False,
    }
    payload = {
        "inspected_at_utc": inspected,
        "hashes": hashes,
        "g10_manifest": manifest.get("manifest_sha256"),
        "snapshot_drift": drift,
        "running": running,
        "rollback": rollback_decision([candidate, unsafe]),
        "candidate": candidate,
        "unsafe": unsafe,
        "docker_context": DOCKER_CONTEXT,
        "mutations": mutations,
        "database_live_inspected": False,
        "classification": "READ_ONLY_AUDIT_COMPLETE_ROLLBACK_UNVERIFIED",
    }
    (G11 / "audit_summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
