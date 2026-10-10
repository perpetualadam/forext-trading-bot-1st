"""Offline image-layer fixtures for Stage G.12.

This module does not talk to Docker and does not read the running image.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from typing import Any

UNSAFE_IMAGE = "sha256:a19a2208fcf30f8fa1cf61442cf021dec6d99d809b6907836c834922bfe3e2a5"
RUNNING_IMAGE = "sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25"
APPROVAL_TOKEN = "OPERATOR_APPROVED_IMAGE_SAVE"


class ForensicRefusal(PermissionError):
    """The real image filesystem is not approved for reading."""


def assert_export_approved(approval: str | None, image_id: str) -> None:
    if image_id == UNSAFE_IMAGE:
        raise ForensicRefusal("ROLLBACK_CANDIDATE_REJECTED")
    if approval != APPROVAL_TOKEN or image_id != RUNNING_IMAGE:
        raise ForensicRefusal("IMAGE_FORENSICS_APPROVAL_REQUIRED")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unsafe_name(name: str) -> bool:
    if name.startswith(("/", "\\")) or ":" in name[:3]:
        return True
    return any(part == ".." for part in name.replace("\\", "/").split("/"))


def layer_tar(members: list[tuple[str, bytes | None, str]]) -> bytes:
    """Build one synthetic layer. kind is file, symlink, hardlink, or fifo."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data, kind in members:
            info = tarfile.TarInfo(name=name)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            if kind == "file":
                payload = data or b""
                info.size = len(payload)
                info.type = tarfile.REGTYPE
                archive.addfile(info, io.BytesIO(payload))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "elsewhere"
                archive.addfile(info)
            elif kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = "elsewhere"
                archive.addfile(info)
            else:
                info.type = tarfile.FIFOTYPE
                archive.addfile(info)
    return buffer.getvalue()


def _read_layer(blob: bytes) -> list[tuple[str, bool, bytes]]:
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:") as archive:
        members = archive.getmembers()
        seen: set[str] = set()
        rows: list[tuple[str, bool, bytes]] = []
        for info in members:
            if _unsafe_name(info.name):
                raise ValueError("unsafe_path")
            if info.name in seen:
                raise ValueError("duplicate_member")
            seen.add(info.name)
            if info.issym() or info.islnk() or info.ischr() or info.isblk() or info.isfifo():
                raise ValueError("unsupported_member")
            if not (info.isfile() or info.isdir()):
                raise ValueError("unsupported_member")
            payload = b""
            if info.isfile():
                handle = archive.extractfile(info)
                payload = b"" if handle is None else handle.read()
            rows.append((info.name, info.isfile(), payload))
        return rows


def merge_layers(layers: list[bytes]) -> dict[str, bytes]:
    """Apply OCI whiteouts. A later delete hides a lower file; it does not erase the lower blob."""
    tree: dict[str, bytes] = {}
    for blob in layers:
        members = _read_layer(blob)
        opaque: set[str] = set()
        whiteouts: set[str] = set()
        files: list[tuple[str, bytes]] = []
        for name, is_file, payload in members:
            name = name.replace("\\", "/").rstrip("/")
            base = name.rsplit("/", 1)[-1]
            parent = name.rsplit("/", 1)[0] if "/" in name else ""
            if base == ".wh..wh..opq":
                opaque.add(parent)
            elif base.startswith(".wh."):
                target = base[4:]
                whiteouts.add(target if not parent else parent + "/" + target)
            elif is_file:
                files.append((name, payload))
        for directory in opaque:
            prefix = directory + "/" if directory else ""
            tree = {path: data for path, data in tree.items() if path != directory and not path.startswith(prefix)}
        for path in whiteouts:
            prefix = path + "/"
            tree = {item: data for item, data in tree.items() if item != path and not item.startswith(prefix)}
        for path, data in files:
            tree[path] = data
    return tree


def select_files(tree: dict[str, bytes], wanted: set[str]) -> dict[str, str]:
    return {path: _sha(tree[path]) for path in sorted(wanted) if path in tree}


def redact_finding(text: str) -> dict[str, Any]:
    blocked = False
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        label = key.strip()
        if separator and value.strip() and label in {"OANDA_ACCESS_TOKEN", "POSTGRES_PASSWORD", "POSTGRES_PASS"}:
            blocked = True
    return {"credential_assignment": blocked, "value_stored": False}


def rollback_verdict(*, contents_proven: bool, database_proven: bool, procedure_reviewed: bool) -> str:
    if contents_proven and database_proven and procedure_reviewed:
        return "ROLLBACK_CANDIDATE_VERIFIED"
    if contents_proven:
        return "ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED"
    return "ROLLBACK_CANDIDATE_UNVERIFIED"


def parse_save_manifest(blob: bytes) -> list[str]:
    """Read a synthetic docker-save archive and return layer paths in order."""
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:") as archive:
        handle = archive.extractfile("manifest.json")
        if handle is None:
            raise ValueError("manifest_missing")
        manifest = json.loads(handle.read().decode("utf-8"))
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("manifest_shape")
    layers = manifest[0].get("Layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("layers_missing")
    return [str(item) for item in layers]
