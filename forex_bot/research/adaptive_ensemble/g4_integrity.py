"""Stage G.4 local integrity checks. Does not call a broker."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble.protocol import integrity_hash, load_protocol
from forex_bot.research.adaptive_ensemble.provenance import sha256_file

ROOT = Path(__file__).resolve().parents[3]
G3 = ROOT / "data" / "research" / "adaptive_ensemble" / "g3"
G4 = ROOT / "data" / "research" / "adaptive_ensemble" / "g4"
PROTOCOL_HASH = "539cdc083f83393a79d254d21385edc6c48e88eb0f085d4549df9fdd6d431bc0"
PRESERVED = {
    "assessment.json": "3bc892971202f28e7e58f72144871d9694dbaded5c6dfa425ec8cd11fa6d2c9c",
    "evaluation_results.json": "c4d0cfc754ce1cd8fb32c57912462cf73f7ec9772c4153bcc609da0d998d2dd9",
    "protocol_v1.json": "c2da7b8b90e2fc6a8eb015c5e94981c88de6fa2820e2d11580b0f3f9d062ea56",
    "g1_readiness": "13553a9e9d476b3ea39521c7fc9634b0aa3c3ffecd4c065b3fdb784c12612f16",
}
G2_READINESS_PREFIX = "ef95a9630d29ebbb"


class IntegrityBlocked(RuntimeError):
    """Raised when Stage G.3 bytes do not match the acquisition manifest."""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _git(args: list[str]) -> str:
    try:
        out = subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.strip()


def git_baseline() -> dict[str, Any]:
    porcelain = _git(["status", "--porcelain"])
    lines = [ln for ln in porcelain.splitlines() if ln.strip()]
    return {
        "revision": _git(["rev-parse", "HEAD"]),
        "porcelain_count": len(lines),
        "porcelain": lines,
    }


def verify_protocol() -> dict[str, Any]:
    doc = load_protocol(ROOT / "data" / "research" / "adaptive_ensemble" / "protocol_v1.json")
    actual = integrity_hash(doc)
    return {
        "protocol_id": doc.get("protocol_id"),
        "expected": PROTOCOL_HASH,
        "actual": actual,
        "verified": actual == PROTOCOL_HASH == doc.get("integrity_hash"),
    }


def verify_g3_hashes() -> dict[str, Any]:
    manifest_path = G3 / "acquisition_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_bad: list[dict[str, str]] = []
    norm_bad: list[dict[str, str]] = []
    for page in manifest.get("raw_pages") or []:
        path = ROOT / str(page["path"])
        actual = sha256_file(path)
        if actual != page.get("sha256"):
            raw_bad.append({"path": str(page["path"]), "expected": str(page.get("sha256")), "actual": actual})
    for quality in manifest.get("quality") or []:
        rel = quality.get("path")
        expected = quality.get("sha256")
        if not rel or not expected:
            norm_bad.append({"path": str(rel), "expected": str(expected), "actual": "missing_manifest_hash"})
            continue
        actual = sha256_file(ROOT / str(rel))
        if actual != expected:
            norm_bad.append({"path": str(rel), "expected": str(expected), "actual": actual})
    preserved_now = {
        "assessment.json": sha256_file(ROOT / "data" / "research" / "adaptive_ensemble" / "assessment.json"),
        "evaluation_results.json": sha256_file(
            ROOT / "data" / "research" / "adaptive_ensemble" / "evaluation_results.json"
        ),
        "protocol_v1.json": sha256_file(ROOT / "data" / "research" / "adaptive_ensemble" / "protocol_v1.json"),
        "g1_readiness": sha256_file(ROOT / "data" / "research" / "adaptive_ensemble" / "g1" / "readiness_manifest.json"),
        "g2_readiness": sha256_file(ROOT / "data" / "research" / "adaptive_ensemble" / "g2" / "readiness_manifest.json"),
    }
    preserved_ok = all(preserved_now[key] == PRESERVED[key] for key in PRESERVED)
    g2_prefix_ok = preserved_now["g2_readiness"].startswith(G2_READINESS_PREFIX)
    return {
        "raw_mismatch": raw_bad,
        "normalised_mismatch": norm_bad,
        "raw_verified": not raw_bad,
        "normalised_verified": not norm_bad,
        "preserved_hashes": preserved_now,
        "preserved_ok": preserved_ok and g2_prefix_ok,
        "requests": manifest.get("requests"),
        "environment": manifest.get("environment"),
    }


def assert_g3_intact() -> dict[str, Any]:
    report = verify_g3_hashes()
    proto = verify_protocol()
    if not proto["verified"] or not report["raw_verified"] or not report["normalised_verified"]:
        raise IntegrityBlocked("DATA_INTEGRITY_BLOCKED")
    if not report["preserved_ok"]:
        raise IntegrityBlocked("DATA_INTEGRITY_BLOCKED")
    return {"protocol": proto, "g3": report}
