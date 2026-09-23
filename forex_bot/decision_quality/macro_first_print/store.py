"""Immutable raw-evidence store for official BLS releases. Never overwrites."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from forex_bot.decision_quality.macro_first_print.schema import CSV_COLUMNS, NormalizedEvent

DEFAULT_ROOT = Path("data/research/macro_first_print")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def raw_dir(root: Path | None, event_type: str) -> Path:
    base = Path(root or DEFAULT_ROOT) / "raw" / "bls"
    return base / ("cpi" if event_type == "CPI" else "employment")


def normalized_dir(root: Path | None = None) -> Path:
    return Path(root or DEFAULT_ROOT) / "normalized"


def canonical_raw_name(event_type: str, release_date: str) -> str:
    stamp = datetime.strptime(release_date, "%Y-%m-%d").strftime("%m%d%Y")
    stem = "cpi" if event_type == "CPI" else "empsit"
    return f"{stem}_{stamp}.htm"


def official_text_name(event_type: str, release_date: str) -> str:
    stamp = datetime.strptime(release_date, "%Y-%m-%d").strftime("%m%d%Y")
    stem = "cpi" if event_type == "CPI" else "empsit"
    return f"{stem}_{stamp}.official.txt"


def looks_like_official_release(body: bytes | str) -> bool:
    text = body.decode("utf-8", errors="replace") if isinstance(body, (bytes, bytearray)) else body
    low = text.lower()
    if "access denied" in low and "bot activity" in low:
        return False
    if "page not found" in low and "consumer price index" not in low and "employment situation" not in low:
        return False
    return ("consumer price index" in low) or ("employment situation" in low)


@dataclass(frozen=True)
class StoredRaw:
    body_path: Path
    meta_path: Path
    sha256: str
    http_status: int
    reused: bool
    hash_changed: bool


def write_raw_release(
    *,
    dest_dir: Path,
    filename: str,
    body: bytes,
    source_url: str,
    http_status: int,
    content_type: str | None,
    publication_date: str | None,
    release_number: str | None,
    retrieved_at: str | None = None,
) -> StoredRaw:
    """Write raw bytes + sidecar metadata. Existing bytes are never overwritten."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    body_path = dest_dir / filename
    meta_path = dest_dir / f"{filename}.meta.json"
    digest = sha256_bytes(body)
    retrieved = retrieved_at or utc_now()
    if body_path.exists():
        existing = body_path.read_bytes()
        existing_hash = sha256_bytes(existing)
        if existing_hash == digest:
            return StoredRaw(body_path, meta_path, digest, http_status, True, False)
        alt_name = f"{body_path.stem}_{retrieved.replace(':', '').replace('-', '')}_{digest[:16]}{body_path.suffix}"
        alt_path = dest_dir / alt_name
        alt_meta = dest_dir / f"{alt_name}.meta.json"
        alt_path.write_bytes(body)
        _write_meta(
            alt_meta,
            source_url=source_url,
            retrieved_at=retrieved,
            publication_date=publication_date,
            release_number=release_number,
            raw_filename=alt_name,
            sha256=digest,
            http_status=http_status,
            content_type=content_type,
            bytes_len=len(body),
            hash_changed_from=existing_hash,
        )
        return StoredRaw(alt_path, alt_meta, digest, http_status, False, True)
    body_path.write_bytes(body)
    _write_meta(
        meta_path,
        source_url=source_url,
        retrieved_at=retrieved,
        publication_date=publication_date,
        release_number=release_number,
        raw_filename=filename,
        sha256=digest,
        http_status=http_status,
        content_type=content_type,
        bytes_len=len(body),
        hash_changed_from=None,
    )
    return StoredRaw(body_path, meta_path, digest, http_status, False, False)


def _write_meta(
    path: Path,
    *,
    source_url: str,
    retrieved_at: str,
    publication_date: str | None,
    release_number: str | None,
    raw_filename: str,
    sha256: str,
    http_status: int,
    content_type: str | None,
    bytes_len: int,
    hash_changed_from: str | None,
) -> None:
    payload = {
        "source_url": source_url,
        "retrieved_at_utc": retrieved_at,
        "source_publication_date": publication_date,
        "release_number": release_number,
        "local_raw_filename": raw_filename,
        "sha256": sha256,
        "http_status": int(http_status),
        "content_type": content_type,
        "bytes": bytes_len,
        "hash_changed_from": hash_changed_from,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_meta(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_events_csv(path: Path, events: Iterable[NormalizedEvent]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [e.to_dict() for e in events]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if v is None else v for k, v in row.items()})


def write_events_json(path: Path, events: Iterable[NormalizedEvent]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [e.to_dict() for e in events]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
