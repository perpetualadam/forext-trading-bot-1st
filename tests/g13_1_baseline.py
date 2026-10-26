"""Stage G.13.1 packaging baseline checks. Offline only."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUTHORISED_DOCKERFILE_SHA256 = "4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad"
HISTORICAL_DOCKERFILE_SHA256 = "f8d537d84c8ab004c5fc2cbdc5ef58e8141f5ca66a13be6cc5eac38c7c7006a6"
G10_ARCHIVE_SHA256 = "d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277"
G10_MANIFEST_SHA256 = "93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf"
G7_ARCHIVE_SHA256 = "0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82"
G7_MANIFEST_SHA256 = "ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989"
DOCKERIGNORE_SHA256 = "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd"
ALLOWLIST_FILE_SHA256 = "b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4"
ALLOWLIST_COUNT = 63

FORBIDDEN_PREFIXES = (
    "forex_bot/research/",
    "forex_bot/shadow/",
    "forex_bot/decision_quality/",
    "tests/",
    "data/",
)
FORBIDDEN_NAMES = {".env", "credentials.json", "id_rsa", "live_safety_state.json"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _packaging():
    name = "g13_packaging"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("g13_packaging.py"))
        if spec is None or spec.loader is None:
            raise RuntimeError("g13 packaging checker is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def compare_snapshot_files(
    fresh_files: list[dict[str, Any]],
    recorded_files: list[dict[str, Any]],
    *,
    authorised_dockerfile: str = AUTHORISED_DOCKERFILE_SHA256,
    historical_dockerfile: str = HISTORICAL_DOCKERFILE_SHA256,
) -> dict[str, Any]:
    fresh = {str(row["path"]): str(row["sha256"]) for row in fresh_files}
    recorded = {str(row["path"]): str(row["sha256"]) for row in recorded_files}
    missing = sorted(set(recorded) - set(fresh))
    extra = sorted(set(fresh) - set(recorded))
    changed = sorted(path for path in set(fresh) & set(recorded) if fresh[path] != recorded[path])
    problems: list[str] = []
    if missing:
        problems.append("missing_snapshot_files")
    if extra:
        problems.append("unexpected_snapshot_files")
    if changed != ["Dockerfile"]:
        problems.append("unexpected_source_drift")
    if fresh.get("Dockerfile") != authorised_dockerfile:
        problems.append("dockerfile_hash")
    if recorded.get("Dockerfile") != historical_dockerfile:
        problems.append("historical_dockerfile_pin")
    return {
        "ok": not problems,
        "problems": problems,
        "changed": changed,
        "missing": missing,
        "extra": extra,
    }


def evaluate_allowlist(
    rows: list[dict[str, Any]],
    root: Path,
    *,
    expected_paths: set[str],
    manifest_hashes: dict[str, str],
    authorised_dockerfile: str = AUTHORISED_DOCKERFILE_SHA256,
    historical_dockerfile: str = HISTORICAL_DOCKERFILE_SHA256,
) -> dict[str, Any]:
    problems: list[str] = []
    paths = [str(row["path"]) for row in rows]
    if len(paths) != len(set(paths)) or set(paths) != expected_paths:
        problems.append("allowlist_paths")
    for row in rows:
        rel = str(row["path"])
        pinned = str(row["sha256"])
        manifest_hash = manifest_hashes.get(rel)
        candidate = root / rel
        if not candidate.is_file():
            problems.append(f"missing:{rel}")
            continue
        current = sha256_file(candidate)
        if rel == "Dockerfile":
            if pinned != historical_dockerfile:
                problems.append("allowlist_dockerfile_pin_changed")
            if manifest_hash != historical_dockerfile:
                problems.append("manifest_dockerfile_pin_changed")
            if current != authorised_dockerfile:
                problems.append("dockerfile_hash")
            continue
        if manifest_hash is None or current != pinned or current != manifest_hash:
            problems.append(f"drift:{rel}")
    return {"ok": not problems, "problems": problems}


def _normal_source(source: str) -> str:
    text = source.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text


def packaging_problems(
    dockerfile: str,
    paths: list[str],
    root: Path,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    checker = _packaging()
    result = checker.verify_dockerfile(dockerfile, paths=paths, root=root, rules=rules)
    findings = list(result.get("findings") or [])
    text = dockerfile.replace("\r\n", "\n")
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("COPY"):
            continue
        if line.endswith("\\") or "[" in line or "]" in line:
            findings.append("unsupported_copy_syntax")
    try:
        copies = checker.parse_copies(text)
    except ValueError as exc:
        findings.append(f"unsupported_copy:{exc}")
        copies = []
    sources = [source for source, _dest in copies]
    if sources.count("requirements.txt") != 1:
        findings.append("requirements_not_copied_once")
    for source, _dest in copies:
        normal = _normal_source(source)
        name = Path(normal).name.lower()
        if normal.startswith(FORBIDDEN_PREFIXES) or name in FORBIDDEN_NAMES:
            findings.append(f"forbidden_source:{source}")
    unique = list(dict.fromkeys(findings))
    return {
        "ok": not unique and bool(result.get("ok")),
        "findings": unique,
        "copy_count": result.get("copy_count"),
        "main_py_copies": result.get("main_py_copies"),
    }
