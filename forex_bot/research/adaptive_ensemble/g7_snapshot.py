"""Stage G.7 source snapshot. Hashes the Docker COPY set. Does not build an image."""

from __future__ import annotations

import ast
import hashlib
import io
import json
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
G7 = ROOT / "data" / "research" / "adaptive_ensemble" / "g7"
TOOL_VERSION = "g7_snapshot_v1"
TOP_LEVEL = (
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
    "main.py",
    "requirements.txt",
    ".env.example",
)
SECRET_NAMES = {".env", "id_rsa", "credentials.json", "live_safety_state.json"}
EXCLUSION_POLICY = (
    {"path": ".env", "reason": "secret_dotenv"},
    {"path": ".git/", "reason": "vcs"},
    {"path": "data/", "reason": "research_archives_live_safety_state_and_snapshot_output"},
    {"path": "data/ops/live_safety_state.json", "reason": "live_safety_state"},
    {"path": "data/research/adaptive_ensemble/g7/", "reason": "snapshot_output_not_source"},
    {"path": "tests/", "reason": "test_only_not_in_dockerfile_copy"},
    {"path": ".mypy_cache/", "reason": "generated"},
    {"path": ".pytest_cache/", "reason": "generated"},
    {"path": "__pycache__/", "reason": "generated"},
)


class SnapshotBlocked(RuntimeError):
    """The snapshot is not complete or not safe to publish."""


def _posix(path: Path) -> str:
    return path.as_posix()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: dict[str, Any]) -> bytes:
    body = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_digest(payload: dict[str, Any]) -> str:
    return _sha256(_canonical(payload))


def _secret_path(rel: str) -> bool:
    name = Path(rel).name.lower()
    if name in SECRET_NAMES or name.endswith((".pem", ".key")):
        return True
    if name == ".env":
        return True
    return name.startswith(".env.") and name != ".env.example"


def _secret_bytes(data: bytes) -> bool:
    private_key = b"BEGIN " + b"PRIVATE KEY"
    rsa_key = b"BEGIN RSA " + b"PRIVATE KEY"
    return private_key in data or rsa_key in data


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _module_file(module: str) -> Path | None:
    if not module.startswith("forex_bot"):
        return None
    parts = module.split(".")
    file_path = ROOT.joinpath(*parts).with_suffix(".py")
    if file_path.is_file():
        return file_path
    init = ROOT.joinpath(*parts) / "__init__.py"
    if init.is_file():
        return init
    return None


def reachable_modules() -> set[str]:
    """Static imports reachable from the production entrypoints, including function-level imports."""
    queue = ["forex_bot.app", "forex_bot.bot_loop"]
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
    if rel in {"Dockerfile", "main.py", "requirements.txt"}:
        return "PRODUCTION_REQUIRED"
    if rel in {".dockerignore", "docker-compose.yml", ".env.example"}:
        return "PRODUCTION_DEPENDENCY"
    if not rel.startswith("forex_bot/"):
        return "UNKNOWN"
    module = rel[:-3].replace("/", ".") if rel.endswith(".py") else ""
    if module in reachable or module.endswith(".__init__") and module[: -len(".__init__")] in reachable:
        if "/research/" in rel or rel.startswith("forex_bot/research/"):
            return "PRODUCTION_DEPENDENCY"
        return "PRODUCTION_REQUIRED"
    if rel.startswith("forex_bot/research/"):
        return "RESEARCH_ONLY"
    return "UNKNOWN"


def iter_source_files() -> list[Path]:
    found: list[Path] = []
    for name in TOP_LEVEL:
        path = ROOT / name
        if path.is_file():
            found.append(path)
    package = ROOT / "forex_bot"
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise SnapshotBlocked("SNAPSHOT_REPRODUCIBILITY_BLOCKED")
        found.append(path)
    return sorted(found, key=lambda item: _posix(item.relative_to(ROOT)))


def collect_entries() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    reachable = reachable_modules()
    entries: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for path in iter_source_files():
        rel = _posix(path.relative_to(ROOT))
        if rel.startswith("data/"):
            excluded.append({"path": rel, "reason": "outside_copy_set"})
            continue
        data = path.read_bytes()
        if _secret_path(rel) or _secret_bytes(data):
            raise SnapshotBlocked("SNAPSHOT_REPRODUCIBILITY_BLOCKED")
        entries.append(
            {
                "classification": _classify(rel, reachable),
                "path": rel,
                "sha256": _sha256(data),
                "size": len(data),
            }
        )
    entries.sort(key=lambda row: row["path"])
    return entries, excluded


def _git_head() -> str:
    from forex_bot.research.adaptive_ensemble.g4_integrity import git_baseline

    return str(git_baseline()["revision"])


def build_manifest() -> dict[str, Any]:
    prior = assert_g3_intact()
    g4 = verify_g4_hashes()
    if not prior["protocol"]["verified"] or not g4["policy_verified"] or not g4["package_verified"]:
        raise SnapshotBlocked("BASELINE_INTEGRITY_BLOCKED")
    entries, excluded = collect_entries()
    payload: dict[str, Any] = {
        "excluded": list(EXCLUSION_POLICY) + excluded,
        "files": entries,
        "g4_package_hash": PACKAGE_HASH,
        "g4_policy_hash": POLICY_HASH,
        "protocol_hash": PROTOCOL_HASH,
        "provenance_version": MODEL_VERSION,
        "snapshot_tool": TOOL_VERSION,
    }
    payload["manifest_sha256"] = manifest_digest(payload)
    return payload


def write_tar(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for row in entries:
            data = (ROOT / row["path"]).read_bytes()
            if _sha256(data) != row["sha256"]:
                raise SnapshotBlocked("SNAPSHOT_REPRODUCIBILITY_BLOCKED")
            info = tarfile.TarInfo(name=row["path"])
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(data))


def snapshot_context(manifest: dict[str, Any]) -> dict[str, Any]:
    """Review context. Not part of the content hash."""
    counts: dict[str, int] = {}
    for row in manifest["files"]:
        label = str(row["classification"])
        counts[label] = counts.get(label, 0) + 1
    baseline = _git_head()
    from forex_bot.research.adaptive_ensemble.g4_integrity import git_baseline

    git = git_baseline()
    return {
        "git_head": baseline,
        "working_tree_dirty": git["porcelain_count"] > 0,
        "porcelain_count": git["porcelain_count"],
        "provenance_version": manifest["provenance_version"],
        "manifest_sha256": manifest["manifest_sha256"],
        "file_count": len(manifest["files"]),
        "classification_counts": counts,
        "unknown_modules": [row["path"] for row in manifest["files"] if row["classification"] == "UNKNOWN"],
        "research_modules": [row["path"] for row in manifest["files"] if row["classification"] == "RESEARCH_ONLY"],
        "dockerfile_copy": ["requirements.txt", "forex_bot/", "main.py"],
        "dockerignore_excludes_env": True,
        "dockerignore_excludes_data": False,
        "image_built": False,
        "snapshot_self_inclusion": False,
    }


def write_snapshot(tar_path: Path | None = None, manifest_path: Path | None = None) -> dict[str, Any]:
    manifest = build_manifest()
    tar_dest = tar_path or (G7 / "source_snapshot.tar")
    manifest_dest = manifest_path or (G7 / "manifest.json")
    if "source_snapshot.tar" in {row["path"] for row in manifest["files"]}:
        raise SnapshotBlocked("SNAPSHOT_REPRODUCIBILITY_BLOCKED")
    write_tar(tar_dest, list(manifest["files"]))
    manifest_dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, sort_keys=True)
    manifest_dest.write_text(text, encoding="utf-8")
    return manifest


def verify_snapshot(tar_path: Path, manifest_path: Path) -> dict[str, Any]:
    """Re-read the archive and the manifest. Do not trust an in-memory file list."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest_digest(manifest) != manifest.get("manifest_sha256"):
        return {"ok": False, "reason": "manifest_hash_mismatch"}
    rows = manifest.get("files")
    if not isinstance(rows, list):
        return {"ok": False, "reason": "manifest_files_missing"}
    expected: dict[str, str] = {}
    for row in rows:
        rel = str(row.get("path") or "")
        if not rel or rel in expected:
            return {"ok": False, "reason": "duplicate_or_blank_manifest_path", "path": rel}
        expected[rel] = str(row.get("sha256") or "")
    found: dict[str, str] = {}
    with tarfile.open(tar_path, "r:") as archive:
        for info in archive.getmembers():
            name = info.name
            if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                return {"ok": False, "reason": "unsafe_path", "path": name}
            if info.issym() or info.islnk():
                return {"ok": False, "reason": "symlink", "path": name}
            if name in found:
                return {"ok": False, "reason": "duplicate_path", "path": name}
            if _secret_path(name):
                return {"ok": False, "reason": "secret_path", "path": name}
            handle = archive.extractfile(info)
            if handle is None:
                return {"ok": False, "reason": "unreadable_member", "path": name}
            data = handle.read()
            if _secret_bytes(data):
                return {"ok": False, "reason": "secret_bytes", "path": name}
            found[name] = _sha256(data)
    missing = sorted(set(expected) - set(found))
    unexpected = sorted(set(found) - set(expected))
    if missing:
        return {"ok": False, "reason": "missing_file", "path": missing[0]}
    if unexpected:
        return {"ok": False, "reason": "unexpected_file", "path": unexpected[0]}
    for rel, digest in expected.items():
        if found[rel] != digest:
            return {"ok": False, "reason": "modified_file", "path": rel}
    return {"ok": True, "reason": "verified", "file_count": len(found)}
