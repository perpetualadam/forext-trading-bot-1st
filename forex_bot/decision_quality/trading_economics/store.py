"""Immutable raw-response store. Never writes the API key."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.decision_quality.trading_economics.client import redact_url
from forex_bot.decision_quality.trading_economics.events import PlannedRequest, public_url


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def default_raw_dir(root: Path | None = None) -> Path:
    base = root or Path("data/research/trading_economics")
    return Path(base) / "raw"


def default_normalized_dir(root: Path | None = None) -> Path:
    base = root or Path("data/research/trading_economics")
    return Path(base) / "normalized"


@dataclass(frozen=True)
class StoredRaw:
    body_path: Path
    meta_path: Path
    sha256: str
    record_count: int


def write_raw_response(
    *,
    raw_dir: Path,
    req: PlannedRequest,
    body: bytes,
    status: int,
    record_count: int,
    retrieved_at: datetime | None = None,
    response_url: str = "",
) -> StoredRaw:
    """Write a new raw file. Existing files are never overwritten."""
    retrieved = retrieved_at or datetime.now(timezone.utc)
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=timezone.utc)
    digest = sha256_bytes(body)
    stamp = retrieved.strftime("%Y%m%dT%H%M%SZ")
    stem = f"{stamp}_{req.family_id}_{digest[:16]}"
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    body_path = raw_dir / f"{stem}.json"
    meta_path = raw_dir / f"{stem}.meta.json"
    if body_path.exists() or meta_path.exists():
        raise FileExistsError(f"refusing to overwrite {body_path.name}")
    body_path.write_bytes(body)
    meta = {
        "retrieved_at_utc": retrieved.isoformat(),
        "method": req.method,
        "endpoint": req.path,
        "url": redact_url(response_url or public_url(req)),
        "request_parameters": {
            "country": req.country,
            "start": req.start,
            "end": req.end,
            "slug": req.slug,
            "path_kind": req.path_kind,
            "query": dict(req.query),
            "family_id": req.family_id,
        },
        "http_status": int(status),
        "record_count": int(record_count),
        "sha256": digest,
        "body_filename": body_path.name,
        "api_key_stored": False,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return StoredRaw(body_path=body_path, meta_path=meta_path, sha256=digest, record_count=record_count)


def write_normalized(path: Path, rows: list[dict[str, Any]]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return path
