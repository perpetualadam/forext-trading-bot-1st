"""Fail-closed minimal build-context staging. No Docker and no secret reads."""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from pathlib import Path
from typing import Any

REPARSE_POINT = 0x400
OFFLINE = 0x1000
RECALL_ON_OPEN = 0x40000
RECALL_ON_DATA_ACCESS = 0x400000
UNSAFE_ATTRIBUTES = REPARSE_POINT | OFFLINE | RECALL_ON_OPEN | RECALL_ON_DATA_ACCESS
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
BACKUP_NAMES = {
    "main example .env backup.txt",
    "# Copy to .env and fill in. docker.txt",
}
CREDENTIAL_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "id_rsa",
    "id_rsa.pub",
    "live_safety_state.json",
}
FORBIDDEN_PREFIXES = (
    "forex_bot/research/",
    "forex_bot/shadow/",
    "forex_bot/decision_quality/",
    "data/",
    "tests/",
    ".git/",
)
FORBIDDEN_SUFFIXES = (".pem", ".key", ".sqlite", ".sqlite3", ".db", ".bak", ".csv")
POLICY_FILES = {"Dockerfile", ".dockerignore"}
BROAD_SOURCES = {"", ".", "forex_bot", "forex_bot/", "./forex_bot", "./forex_bot/"}


class StagingRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normal(path: str) -> str:
    text = unicodedata.normalize("NFC", path.replace("\\", "/").strip())
    while text.startswith("./"):
        text = text[2:]
    return text


def classify_path(path: str) -> str:
    rel = _normal(path)
    if rel == "Dockerfile":
        return "DOCKERFILE"
    if rel == ".dockerignore":
        return "DOCKERIGNORE"
    if rel == "requirements.txt":
        return "DEPENDENCY_MANIFEST"
    if rel == "main.py":
        return "APPLICATION_ENTRYPOINT"
    if rel.startswith("forex_bot/") and rel.endswith(".py") and not rel.startswith(FORBIDDEN_PREFIXES):
        return "PYTHON_PACKAGE_FILE"
    return "OTHER"


def forbidden_reason(path: str) -> str | None:
    rel = _normal(path)
    name = Path(rel).name
    folded = name.casefold()
    if name in BACKUP_NAMES or folded in {item.casefold() for item in BACKUP_NAMES}:
        return "sensitive_backup"
    if folded in {item.casefold() for item in CREDENTIAL_NAMES} or folded.startswith(".env"):
        return "credential"
    if rel.startswith(FORBIDDEN_PREFIXES) or rel.startswith(".git"):
        return "forbidden_tree"
    if name.lower().endswith(FORBIDDEN_SUFFIXES):
        return "forbidden_suffix"
    parts = [part.split(".", 1)[0].upper() for part in Path(rel).parts]
    if any(part in RESERVED_NAMES for part in parts):
        return "reserved_windows_name"
    if classify_path(rel) == "OTHER":
        return "not_authorised_category"
    return None


def parse_copies(dockerfile: str) -> list[tuple[str, str]]:
    copies: list[tuple[str, str]] = []
    for raw in dockerfile.replace("\r\n", "\n").splitlines():
        line = raw.strip()
        if not line.startswith("COPY"):
            continue
        if line.endswith("\\") or any(token in line for token in ("[", "]", "*")):
            raise StagingRejected("unsupported_copy_syntax")
        parts = line.split()
        if len(parts) != 3 or parts[0] != "COPY":
            raise StagingRejected("unsupported_copy_syntax")
        source, dest = parts[1], parts[2]
        normal = _normal(source)
        if normal in BROAD_SOURCES or normal.endswith("/"):
            raise StagingRejected("broad_copy")
        if ".." in Path(normal).parts or normal.startswith(("/", "../")):
            raise StagingRejected("path_traversal")
        copies.append((normal, dest))
    return copies


def _destination(source: str, dest: str) -> str:
    if dest in {".", "./"}:
        return f"/app/{Path(source).name}"
    if ".." in Path(dest).parts:
        raise StagingRejected("destination_escape")
    if dest.startswith("/"):
        resolved = Path(dest).as_posix()
    else:
        resolved = Path("/app", dest).as_posix()
    if resolved != "/app" and not resolved.startswith("/app/"):
        raise StagingRejected("destination_escape")
    return resolved


def _lstat_regular(path: Path) -> os.stat_result:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        raise StagingRejected(f"symlink:{path.name}")
    attributes = getattr(info, "st_file_attributes", 0)
    if attributes & UNSAFE_ATTRIBUTES:
        raise StagingRejected(f"reparse_or_placeholder:{path.name}")
    if not stat.S_ISREG(info.st_mode):
        raise StagingRejected(f"not_regular:{path.name}")
    return info


def _read_stable(path: Path) -> bytes:
    before = _lstat_regular(path)
    data = path.read_bytes()
    after = _lstat_regular(path)
    if before.st_dev != after.st_dev or before.st_ino != after.st_ino or before.st_size != after.st_size:
        raise StagingRejected(f"source_changed:{path.name}")
    if data != path.read_bytes():
        raise StagingRejected(f"source_changed:{path.name}")
    if len(data) != before.st_size:
        raise StagingRejected(f"source_changed:{path.name}")
    return data


def _case_collisions(paths: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    collisions: list[str] = []
    for rel in paths:
        key = unicodedata.normalize("NFC", rel).casefold()
        prior = seen.get(key)
        if prior is not None and prior != rel:
            collisions.append(rel)
        seen[key] = rel
    return collisions


def permitted_inputs(allow_paths: list[str], copies: list[tuple[str, str]]) -> list[str]:
    copy_sources = [source for source, _dest in copies]
    selected = [*POLICY_FILES, *copy_sources]
    allow = {_normal(path) for path in allow_paths}
    permitted: list[str] = []
    for rel in selected:
        normal = _normal(rel)
        if normal not in allow:
            raise StagingRejected(f"copy_not_in_allowlist:{normal}")
        reason = forbidden_reason(normal)
        if reason is not None:
            raise StagingRejected(f"{reason}:{normal}")
        if normal not in permitted:
            permitted.append(normal)
    extra = sorted(allow - set(permitted))
    if extra:
        raise StagingRejected("allowlist_contains_unstaged_paths")
    if _case_collisions(permitted):
        raise StagingRejected("case_collision")
    return sorted(permitted)


def stage_context(
    repo: Path,
    allowlist_paths: list[str],
    allowlist_hashes: dict[str, str],
    *,
    authorised_dockerfile_sha256: str,
    dockerignore_sha256: str,
    output_dir: Path,
    dockerignore_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Copy only authorised inputs. Returns a manifest payload. Does not approve itself."""
    repo_resolved = repo.resolve()
    output_resolved = output_dir.resolve()
    if output_resolved == repo_resolved or repo_resolved in output_resolved.parents:
        raise StagingRejected("staging_inside_repository")
    if "OneDrive" in output_resolved.parts:
        raise StagingRejected("staging_inside_onedrive")
    if not output_dir.is_dir():
        raise StagingRejected("staging_missing")
    if any(output_dir.iterdir()):
        raise StagingRejected("staging_not_empty")
    dockerfile_bytes = _read_stable(repo / "Dockerfile")
    if _sha256(dockerfile_bytes) != authorised_dockerfile_sha256:
        raise StagingRejected("dockerfile_hash")
    copies = parse_copies(dockerfile_bytes.decode("utf-8"))
    destinations: dict[str, str] = {}
    for copy_source, copy_dest in copies:
        target = _destination(copy_source, copy_dest)
        if target in destinations:
            raise StagingRejected(f"duplicate_destination:{target}")
        destinations[target] = copy_source
    if [source for source, _dest in copies].count("main.py") != 1:
        raise StagingRejected("main_py_copies")
    if [source for source, _dest in copies].count("requirements.txt") != 1:
        raise StagingRejected("requirements_copies")
    permitted = permitted_inputs(allowlist_paths, copies)
    if dockerignore_rules is not None:
        from forex_bot.research.adaptive_ensemble.g8_dockerignore import (
            context_excluded,
        )

        for rel in permitted:
            if rel == ".dockerignore":
                continue
            if context_excluded(rel, dockerignore_rules):
                raise StagingRejected(f"dockerignore_excludes_required:{rel}")
    records: list[dict[str, Any]] = []
    opened: list[str] = []
    for rel in permitted:
        source = repo / rel
        if not source.exists() and not source.is_symlink():
            raise StagingRejected(f"missing:{rel}")
        repo_abs = os.path.normcase(os.path.abspath(repo))
        file_abs = os.path.normcase(os.path.abspath(source))
        if os.path.commonpath([repo_abs, file_abs]) != repo_abs:
            raise StagingRejected(f"path_escape:{rel}")
        expected = authorised_dockerfile_sha256 if rel == "Dockerfile" else allowlist_hashes[rel]
        if rel == ".dockerignore" and expected != dockerignore_sha256:
            raise StagingRejected("dockerignore_hash")
        data = _read_stable(source)
        opened.append(rel)
        actual = _sha256(data)
        if actual != expected:
            raise StagingRejected(f"hash_mismatch:{rel}")
        staged_file = output_dir / rel
        staged_file.parent.mkdir(parents=True, exist_ok=True)
        if staged_file.exists():
            raise StagingRejected(f"duplicate_destination:{rel}")
        staged_file.write_bytes(data)
        staged = _read_stable(staged_file)
        if _sha256(staged) != expected:
            raise StagingRejected(f"staged_hash_mismatch:{rel}")
        records.append(
            {
                "path": rel,
                "sha256": expected,
                "size": len(data),
                "category": classify_path(rel),
                "source_path": rel,
                "staged_path": rel,
                "copied_by_dockerfile": rel not in POLICY_FILES,
                "packaging_policy_only": rel in POLICY_FILES,
            }
        )
    records.sort(key=lambda row: row["path"])
    return {"files": records, "opened_paths": opened, "approved": False}
