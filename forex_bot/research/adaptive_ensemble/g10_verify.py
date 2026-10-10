"""Independent Stage G.10 archive reader.

This module does not call the snapshot writer or its digest helper.
It re-reads the tar and recomputes the documented canonical manifest hash.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

SNAPSHOT_ID = "stage_g10_consolidated_source_v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: dict[str, Any]) -> bytes:
    body = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _fail(reason: str, **extra: Any) -> dict[str, Any]:
    result = {"ok": False, "reason": reason}
    result.update(extra)
    return result


def _ustar(archive_bytes: bytes) -> bool:
    return len(archive_bytes) >= 262 and archive_bytes[257:262] == b"ustar"


def _unsafe_name(name: str) -> bool:
    if name.startswith(("/", "\\")) or ":" in name[:3]:
        return True
    parts = name.replace("\\", "/").split("/")
    return any(part == ".." for part in parts)


def verify_archive(
    tar_path: Path,
    manifest_path: Path,
    *,
    expected_archive_sha256: str | None = None,
) -> dict[str, Any]:
    archive_bytes = tar_path.read_bytes()
    archive_sha = _sha256(archive_bytes)
    if expected_archive_sha256 is not None and archive_sha != expected_archive_sha256:
        return _fail("archive_hash")
    if not _ustar(archive_bytes):
        return _fail("archive_format")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("snapshot_id") != SNAPSHOT_ID:
        return _fail("snapshot_identity")
    expected_digest = _sha256(_canonical(manifest))
    if expected_digest != manifest.get("manifest_sha256"):
        return _fail("manifest_hash")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        return _fail("manifest_files")
    expected: dict[str, dict[str, Any]] = {}
    names: list[str] = []
    for row in rows:
        rel = str(row.get("path") or "")
        if not rel or rel in expected or _unsafe_name(rel):
            return _fail("manifest_path", path=rel)
        expected[rel] = row
        names.append(rel)
    if names != sorted(names):
        return _fail("manifest_order")
    found: dict[str, str] = {}
    sizes: dict[str, int] = {}
    member_names: list[str] = []
    payload = 0
    with tarfile.open(tar_path, "r:") as archive:
        for info in archive.getmembers():
            name = info.name
            member_names.append(name)
            if _unsafe_name(name):
                return _fail("unsafe_path", path=name)
            if info.issym() or info.islnk() or info.isdir() or info.ischr() or info.isblk() or info.isfifo():
                return _fail("unsupported_member", path=name)
            if info.type not in (tarfile.REGTYPE, tarfile.AREGTYPE):
                return _fail("unsupported_member", path=name)
            if name in found:
                return _fail("duplicate_path", path=name)
            if info.mtime != 0 or info.uid != 0 or info.gid != 0:
                return _fail("metadata", path=name)
            if (info.mode & 0o777) != 0o644 or info.uname not in ("", None) or info.gname not in ("", None):
                return _fail("metadata", path=name)
            handle = archive.extractfile(info)
            if handle is None:
                return _fail("unreadable_member", path=name)
            data = handle.read()
            if len(data) != info.size:
                return _fail("size", path=name)
            found[name] = _sha256(data)
            sizes[name] = len(data)
            payload += len(data)
    if member_names != sorted(member_names):
        return _fail("member_order")
    missing = sorted(set(expected) - set(found))
    unexpected = sorted(set(found) - set(expected))
    if missing:
        return _fail("missing_file", path=missing[0])
    if unexpected:
        return _fail("unexpected_file", path=unexpected[0])
    for rel, row in expected.items():
        if found[rel] != row.get("sha256"):
            return _fail("file_hash", path=rel)
        if int(row.get("size") or -1) != sizes[rel]:
            return _fail("size", path=rel)
    declared = int(manifest.get("payload_bytes") or -1)
    declared_count = int(manifest.get("source_file_count") or -1)
    if payload != declared or declared_count != len(found):
        return _fail("payload", payload=payload, declared=declared)
    return {
        "ok": True,
        "reason": "verified",
        "archive_sha256": archive_sha,
        "manifest_sha256": expected_digest,
        "file_count": len(found),
        "payload_bytes": payload,
        "format": "ustar",
    }
