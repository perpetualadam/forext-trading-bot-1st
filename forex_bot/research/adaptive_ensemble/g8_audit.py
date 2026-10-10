"""Independent Stage G.8 audit of the frozen G.7 snapshot.

This module does not call the G.7 verifier and does not rebuild the archive.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
G7_TAR = ROOT / "data" / "research" / "adaptive_ensemble" / "g7" / "source_snapshot.tar"
G7_MANIFEST = ROOT / "data" / "research" / "adaptive_ensemble" / "g7" / "manifest.json"
EXPECTED_MANIFEST = "ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989"
EXPECTED_PROTOCOL = "539cdc083f83393a79d254d21385edc6c48e88eb0f085d4549df9fdd6d431bc0"
EXPECTED_POLICY = "6ea84361d6fec3e1743fce2c238940d9f2fda50b78b1d5e305d07d18650d29d4"
EXPECTED_PACKAGE = "05b56d1ed7736025e86a9e3f94fb44bb49ea6208718aab7af9cfde6977a6c201"
EXPECTED_MEMBERS = 190
SECRET_KEYS = {
    "OANDA_ACCESS_TOKEN",
    "OANDA_API_KEY",
    "OANDA_ACCOUNT_ID",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "TELEGRAM_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TRADING_ECONOMICS_API_KEY",
    "POSTGRES_PASSWORD",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_manifest(payload: dict[str, Any]) -> bytes:
    body = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _secret_note(name: str, data: bytes) -> str | None:
    base = Path(name).name.lower()
    if base == ".env" or base.endswith((".pem", ".key")) or base in {"id_rsa", "credentials.json"}:
        return "sensitive_filename"
    if (b"BEGIN " + b"PRIVATE KEY") in data or (b"BEGIN RSA " + b"PRIVATE KEY") in data:
        return "private_key_marker"
    for raw in data.splitlines():
        line = raw.strip()
        if not line or line.startswith(b"#") or b"=" not in line:
            continue
        key, _, value = line.partition(b"=")
        label = key.decode("utf-8", "replace").strip()
        if label in SECRET_KEYS and value.strip():
            if label == "POSTGRES_PASSWORD" and base == ".env.example":
                return f"example_database_password:len={len(value.strip())}"
            return f"nonempty_assignment:{label}:len={len(value.strip())}"
    return None


def _safety_trace(files: dict[str, bytes]) -> dict[str, bool]:
    app = files.get("forex_bot/app.py", b"")
    loop = files.get("forex_bot/bot_loop.py", b"")
    prov = files.get("forex_bot/market_provenance.py", b"")
    exe = files.get("forex_bot/oanda_exec.py", b"")
    safety = files.get("forex_bot/live_safety.py", b"")
    client = files.get("forex_bot/oanda_client.py", b"")
    manage = files.get("forex_bot/live_manage.py", b"")
    return {
        "process_start_block": b"initialise_fail_closed" in app and b"AUTH_BLOCKED" in safety,
        "strategy_deactivation": b"active" in safety and b"KNOWN_STRATEGY_NAMES" in safety,
        "provenance_v2": b'market_provenance_v2' in prov and b"def frame_digest" in prov,
        "decision_frame_check": b"decision_frame_rejection" in loop,
        "sealed_entry_quote": b"require_order_quote" in exe and b"bind_live_quote" in client,
        "order_gate_before_create": exe.find(b"assert_new_live_exposure_allowed") < exe.find(b"api.request"),
        "protective_close": b"PositionClose" in exe or b"longUnits" in exe,
        "close_failure_raises": b"raise" in exe,
        "startup_fail_closed": b"def initialise_fail_closed" in safety,
        "management_module": b"def resolve_broker_manage_price" in manage and b"def broker_sl_tp_hit" in manage,
        "missing_candle_returns_before_position_block": (
            loop.find(b"if raw is None or raw.empty:") < loop.find(b"if pos:")
        ),
    }


def audit_snapshot(
    tar_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Re-read the archive. Do not trust an in-memory file list from the G.7 writer."""
    archive_path = tar_path or G7_TAR
    manifest_file = manifest_path or G7_MANIFEST
    archive_bytes = archive_path.read_bytes()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest_hash = _sha256(_canonical_manifest(manifest))
    result: dict[str, Any] = {
        "archive_sha256": _sha256(archive_bytes),
        "manifest_sha256": manifest_hash,
        "manifest_sha256_field": manifest.get("manifest_sha256"),
        "git_head_is_not_snapshot_identity": True,
        "member_count": 0,
        "ordered": False,
        "duplicates": [],
        "unsafe_paths": [],
        "unexpected_types": [],
        "executable_members": [],
        "sensitive": [],
        "hash_mismatches": [],
        "missing": [],
        "unexpected": [],
        "safety": {},
        "classification": "SNAPSHOT_VERIFICATION_FAILED",
    }
    if manifest_hash != manifest.get("manifest_sha256") or manifest_hash != EXPECTED_MANIFEST:
        result["reason"] = "manifest_identity_mismatch"
        return result
    if manifest.get("protocol_hash") != EXPECTED_PROTOCOL:
        result["reason"] = "protocol_hash_mismatch"
        return result
    if manifest.get("g4_policy_hash") != EXPECTED_POLICY or manifest.get("g4_package_hash") != EXPECTED_PACKAGE:
        result["reason"] = "g4_hash_mismatch"
        return result
    expected = {}
    for row in manifest.get("files") or []:
        rel = str(row.get("path") or "")
        if not rel or rel in expected:
            result["duplicates"].append(rel)
            result["reason"] = "duplicate_manifest_path"
            return result
        expected[rel] = str(row.get("sha256") or "")
    found: dict[str, bytes] = {}
    names: list[str] = []
    with tarfile.open(archive_path, "r:") as archive:
        result["archive_format"] = "ustar" if archive_bytes[257:262] == b"ustar" else "other"
        for info in archive.getmembers():
            name = info.name.replace("\\", "/")
            names.append(name)
            if name.startswith("/") or ".." in Path(name).parts:
                result["unsafe_paths"].append(name)
                continue
            if info.issym() or info.islnk() or not info.isfile():
                result["unexpected_types"].append(name)
                continue
            if info.mode & 0o111:
                result["executable_members"].append(name)
            if name in found:
                result["duplicates"].append(name)
                continue
            handle = archive.extractfile(info)
            data = b"" if handle is None else handle.read()
            found[name] = data
            note = _secret_note(name, data)
            if note:
                result["sensitive"].append({"path": name, "finding": note})
            if name.endswith("docker-compose.yml") and b"POSTGRES_PASSWORD" in data:
                result["sensitive"].append(
                    {"path": name, "finding": "compose_references_database_password_interpolation"}
                )
            if name in expected and _sha256(data) != expected[name]:
                result["hash_mismatches"].append(name)
    result["member_count"] = len(names)
    result["ordered"] = names == sorted(names)
    result["missing"] = sorted(set(expected) - set(found))
    result["unexpected"] = sorted(set(found) - set(expected))
    result["safety"] = _safety_trace(found)
    clean = (
        result["archive_format"] == "ustar"
        and result["member_count"] == EXPECTED_MEMBERS
        and result["ordered"]
        and not result["duplicates"]
        and not result["unsafe_paths"]
        and not result["unexpected_types"]
        and not result["executable_members"]
        and not result["hash_mismatches"]
        and not result["missing"]
        and not result["unexpected"]
        and not any(
            item["finding"] in {"sensitive_filename", "private_key_marker"}
            or str(item["finding"]).startswith("nonempty_assignment:")
            for item in result["sensitive"]
        )
        and all(result["safety"].values())
    )
    result["classification"] = "SNAPSHOT_INDEPENDENTLY_VERIFIED" if clean else "SNAPSHOT_VERIFICATION_FAILED"
    if result["sensitive"] and clean:
        result["sensitive_disclosed"] = True
    return result
