"""Independent staging-directory verifier.

This module enumerates and hashes a staging directory. It does not import
the staging helper and it does not copy files.
"""

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
BACKUP_NAMES = {
    "main example .env backup.txt",
    "# Copy to .env and fill in. docker.txt",
}
POLICY_FILES = {"Dockerfile", ".dockerignore"}
BROAD_SOURCES = {"", ".", "forex_bot", "forex_bot/", "./forex_bot", "./forex_bot/"}
FORBIDDEN_PREFIXES = (
    "forex_bot/research/",
    "forex_bot/shadow/",
    "forex_bot/decision_quality/",
    "data/",
    "tests/",
    ".git/",
)


class VerificationRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _normal(path: str) -> str:
    text = unicodedata.normalize("NFC", path.replace("\\", "/").strip())
    while text.startswith("./"):
        text = text[2:]
    return text


def parse_copies(dockerfile: str) -> list[tuple[str, str]]:
    copies: list[tuple[str, str]] = []
    for raw in dockerfile.replace("\r\n", "\n").splitlines():
        line = raw.strip()
        if not line.startswith("COPY"):
            continue
        if line.endswith("\\") or any(token in line for token in ("[", "]", "*")):
            raise VerificationRejected("unsupported_copy_syntax")
        parts = line.split()
        if len(parts) != 3 or parts[0] != "COPY":
            raise VerificationRejected("unsupported_copy_syntax")
        source = _normal(parts[1])
        if source in BROAD_SOURCES or source.endswith("/"):
            raise VerificationRejected("broad_copy")
        if ".." in Path(source).parts or source.startswith(("/", "../")):
            raise VerificationRejected("path_traversal")
        copies.append((source, parts[2]))
    return copies


def _regular(path: Path) -> None:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & UNSAFE_ATTRIBUTES:
        raise VerificationRejected(f"unsafe_file:{path.name}")
    if not stat.S_ISREG(info.st_mode):
        raise VerificationRejected(f"not_regular:{path.name}")


def verify_directory(
    staging: Path,
    expected: list[dict[str, Any]],
    *,
    dockerignore_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    found: dict[str, str] = {}
    folded: dict[str, str] = {}
    for path in staging.rglob("*"):
        rel = _normal(path.relative_to(staging).as_posix())
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & UNSAFE_ATTRIBUTES:
            raise VerificationRejected(f"unsafe_file:{rel}")
        if stat.S_ISDIR(info.st_mode):
            continue
        _regular(path)
        key = rel.casefold()
        if key in folded and folded[key] != rel:
            raise VerificationRejected("case_collision")
        folded[key] = rel
        name = Path(rel).name
        if name in BACKUP_NAMES or name.casefold().startswith(".env") or rel.startswith(FORBIDDEN_PREFIXES):
            raise VerificationRejected(f"forbidden_present:{rel}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        found[rel] = digest
    expected_paths = {_normal(str(row["path"])) for row in expected}
    if set(found) != expected_paths:
        raise VerificationRejected("path_set_mismatch")
    for row in expected:
        rel = _normal(str(row["path"]))
        if found[rel] != row["sha256"]:
            raise VerificationRejected(f"hash_mismatch:{rel}")
    dockerfile = (staging / "Dockerfile").read_bytes().decode("utf-8")
    copies = parse_copies(dockerfile)
    sources = [source for source, _dest in copies]
    if sources.count("main.py") != 1 or sources.count("requirements.txt") != 1:
        raise VerificationRejected("duplicate_entrypoint_or_requirements")
    for source in sources:
        if source not in found:
            raise VerificationRejected(f"copy_source_missing:{source}")
    for rel in found:
        if rel not in POLICY_FILES and rel not in sources:
            raise VerificationRejected(f"unexpected_file:{rel}")
    if dockerignore_rules is not None:
        from forex_bot.research.adaptive_ensemble.g8_dockerignore import (
            context_excluded,
        )

        for source in sources:
            if context_excluded(source, dockerignore_rules):
                raise VerificationRejected(f"dockerignore_excludes_required:{source}")
    return {
        "file_count": len(found),
        "paths": sorted(found),
        "independent_verification": "PASS",
        "docker_daemon_context_behaviour": "DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED",
    }
