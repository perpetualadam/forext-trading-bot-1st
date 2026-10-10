"""Stage G.10 consolidated source snapshot.

The archive is the current working-tree source candidate. Git HEAD is metadata
only. This module writes archives; it does not verify them and does not build images.
"""

from __future__ import annotations

import ast
import ctypes
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path
from typing import Any

from forex_bot.market_provenance import MODEL_VERSION
from forex_bot.research.adaptive_ensemble.g4_integrity import (
    PROTOCOL_HASH,
    assert_g3_intact,
)
from forex_bot.research.adaptive_ensemble.g5_audit import (
    PACKAGE_HASH,
    POLICY_HASH,
    verify_g4_hashes,
)

ROOT = Path(__file__).resolve().parents[3]
G10 = ROOT / "data" / "research" / "adaptive_ensemble" / "g10"
SNAPSHOT_ID = "stage_g10_consolidated_source_v1"
TOOL_VERSION = "g10_snapshot_v1"
TOP_LEVEL = (
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
    "main.py",
    "requirements.txt",
    ".env.example",
)
SECRET_NAMES = {".env", "id_rsa", "credentials.json", "live_safety_state.json"}
G7_ARCHIVE = "0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82"
G7_MANIFEST = "ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989"
DOCKERIGNORE_SHA = "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd"


class SnapshotBlocked(RuntimeError):
    """The candidate cannot be frozen."""


def _posix(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_manifest_bytes(payload: dict[str, Any]) -> bytes:
    body = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_digest(payload: dict[str, Any]) -> str:
    return _sha256(canonical_manifest_bytes(payload))


def _secret_path(rel: str) -> bool:
    name = Path(rel).name.lower()
    if name in SECRET_NAMES or name.endswith((".pem", ".key")):
        return True
    return name.startswith(".env.") and name != ".env.example"


def _secret_bytes(data: bytes) -> bool:
    private_key = b"BEGIN " + b"PRIVATE KEY"
    return private_key in data or (b"BEGIN RSA " + b"PRIVATE KEY") in data


def _reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    if attrs == 0xFFFFFFFF:
        return False
    return bool(attrs & 0x400)


def _unsafe_link(path: Path) -> bool:
    try:
        return _reparse_point(path)
    except OSError:
        return True


def iter_source_files() -> list[Path]:
    found: list[Path] = []
    for name in TOP_LEVEL:
        path = ROOT / name
        if not path.is_file():
            raise SnapshotBlocked("required_source_missing:" + name)
        if _unsafe_link(path):
            raise SnapshotBlocked("unsafe_link:" + name)
        found.append(path)
    package = ROOT / "forex_bot"
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if _unsafe_link(path):
            raise SnapshotBlocked("unsafe_link:" + _posix(path))
        found.append(path)
    found.sort(key=lambda item: _posix(item))
    return found


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _module_file(module: str) -> Path | None:
    if not module.startswith("forex_bot"):
        return None
    parts = module.split(".")
    direct = ROOT.joinpath(*parts).with_suffix(".py")
    init = ROOT.joinpath(*parts, "__init__.py")
    if direct.is_file():
        return direct
    if init.is_file():
        return init
    return None


def production_reachable() -> set[str]:
    queue = ["forex_bot.app", "forex_bot.bot_loop", "main"]
    seen: set[str] = set()
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        path = _module_file(module)
        if path is None:
            continue
        for imported in _imports(path):
            if imported != "forex_bot" and not imported.startswith("forex_bot."):
                continue
            parts = imported.split(".")
            for index in range(1, len(parts) + 1):
                queue.append(".".join(parts[:index]))
    return seen


def _classify(rel: str, reachable: set[str]) -> str:
    if rel in {"Dockerfile", "main.py", "requirements.txt", ".dockerignore"}:
        return "PACKAGING_OR_ENTRY"
    if rel in {"docker-compose.yml", ".env.example"}:
        return "REVIEW_TEMPLATE"
    module = rel[:-3].replace("/", ".") if rel.endswith(".py") else ""
    module = module.removesuffix(".__init__")
    if module in reachable:
        return "PRODUCTION_REACHABLE"
    if rel.startswith(("forex_bot/research/", "forex_bot/decision_quality/", "forex_bot/shadow/")):
        return "RESEARCH_SOURCE"
    if rel in {
        "forex_bot/backtest.py",
        "forex_bot/csv_ohlcv.py",
        "forex_bot/oanda_candles_read.py",
        "forex_bot/decision_repair/harness.py",
        "forex_bot/live_safety_preflight.py",
    }:
        return "NON_RUNTIME_SOURCE"
    return "SOURCE_NOT_IN_STARTUP_CLOSURE"


def _baseline_or_stop() -> None:
    prior = assert_g3_intact()
    g4 = verify_g4_hashes()
    if not (
        prior["protocol"]["verified"]
        and prior["g3"]["raw_verified"]
        and prior["g3"]["normalised_verified"]
        and g4["policy_verified"]
        and g4["package_verified"]
    ):
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    if MODEL_VERSION != "market_provenance_v2":
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    g7_tar = ROOT / "data/research/adaptive_ensemble/g7/source_snapshot.tar"
    g7_manifest = json.loads(
        (ROOT / "data/research/adaptive_ensemble/g7/manifest.json").read_text(encoding="utf-8")
    )
    if _sha256(g7_tar.read_bytes()) != G7_ARCHIVE or g7_manifest.get("manifest_sha256") != G7_MANIFEST:
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    if _sha256((ROOT / ".dockerignore").read_bytes()) != DOCKERIGNORE_SHA:
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    repair = (ROOT / "forex_bot/bot_loop.py").read_text(encoding="utf-8")
    if "_contain_candle_exception" not in repair or "class CycleIntegrityError" not in repair:
        raise SnapshotBlocked("repair_missing")
    if "except AssertionError:" not in repair:
        raise SnapshotBlocked("repair_missing")


def collect_entries() -> list[dict[str, Any]]:
    reachable = production_reachable()
    entries: list[dict[str, Any]] = []
    for path in iter_source_files():
        rel = _posix(path)
        if rel.startswith(("data/", "data/research/adaptive_ensemble/g10/")):
            raise SnapshotBlocked("snapshot_output_in_source_set")
        data = path.read_bytes()
        if _secret_path(rel) or _secret_bytes(data):
            raise SnapshotBlocked("secret_in_source_set:" + rel)
        entries.append(
            {
                "classification": _classify(rel, reachable),
                "path": rel,
                "sha256": _sha256(data),
                "size": len(data),
            }
        )
    entries.sort(key=lambda row: row["path"])
    return entries


def build_manifest() -> dict[str, Any]:
    _baseline_or_stop()
    entries = collect_entries()
    payload: dict[str, Any] = {
        "archive_format": "ustar",
        "files": entries,
        "g4_package_hash": PACKAGE_HASH,
        "g4_policy_hash": POLICY_HASH,
        "payload_bytes": sum(int(row["size"]) for row in entries),
        "protocol_hash": PROTOCOL_HASH,
        "provenance_version": MODEL_VERSION,
        "snapshot_id": SNAPSHOT_ID,
        "snapshot_tool": TOOL_VERSION,
        "source_file_count": len(entries),
    }
    payload["manifest_sha256"] = manifest_digest(payload)
    return payload


def write_tar(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for row in entries:
            data = (ROOT / row["path"]).read_bytes()
            if _sha256(data) != row["sha256"] or len(data) != int(row["size"]):
                raise SnapshotBlocked("source_changed_during_archive")
            info = tarfile.TarInfo(name=row["path"])
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.type = tarfile.REGTYPE
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.linkname = ""
            archive.addfile(info, io.BytesIO(data))


def write_candidate(tar_path: Path, manifest_path: Path) -> dict[str, Any]:
    """Write one candidate. Callers choose the paths. Tests must not use the official paths."""
    manifest = build_manifest()
    official = {G10 / "source_snapshot.tar", G10 / "source_manifest.json"}
    if tar_path.resolve() in official or manifest_path.resolve() in official:
        raise SnapshotBlocked("official_snapshot_is_frozen_use_finalise_once")
    write_tar(tar_path, list(manifest["files"]))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def finalise_official() -> dict[str, Any]:
    """One-shot freeze of the official G.10 archive. Not for tests."""
    manifest = build_manifest()
    tar_path = G10 / "source_snapshot.tar"
    manifest_path = G10 / "source_manifest.json"
    staging_tar = G10 / "_staging_source_snapshot.tar"
    staging_manifest = G10 / "_staging_source_manifest.json"
    write_tar(staging_tar, list(manifest["files"]))
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    staging_manifest.write_text(text, encoding="utf-8")
    staging_tar.replace(tar_path)
    staging_manifest.replace(manifest_path)
    return manifest
