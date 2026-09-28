"""Research-only forward consensus snapshot store. Collection disabled by default."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

FORWARD_DIR = Path("data/research/macro/consensus_pit/forward")
CONFIG_PATH = FORWARD_DIR / "config.json"
REGISTRY_PATH = FORWARD_DIR / "source_registry.json"
SCHEMA_PATH = FORWARD_DIR / "schema.json"
SNAPSHOTS_PATH = FORWARD_DIR / "snapshots.jsonl"
ARTIFACTS_DIR = FORWARD_DIR / "artifacts"
OBSERVATIONS_PATH = FORWARD_DIR / "observations.jsonl"

REQUIRED_FIELDS = (
    "snapshot_id",
    "macro_event_id",
    "event_family",
    "series_name",
    "reference_period",
    "expectation_type",
    "forecast_value",
    "unit",
    "source_publisher",
    "source_reference",
    "source_publication_utc",
    "source_updated_utc",
    "observed_at_utc",
    "official_release_utc",
    "minutes_to_release",
    "raw_artifact_hash",
    "artifact_location",
    "snapshot_sequence",
    "pit_status",
    "retrieval_method",
    "notes",
)


def parse_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collection_enabled(path: Path = CONFIG_PATH) -> bool:
    return bool(load_config(path).get("FORWARD_CONSENSUS_COLLECTION_ENABLED") is True)


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def all_sources_disabled(path: Path = REGISTRY_PATH) -> bool:
    blob = load_registry(path)
    return all(not src.get("enabled") for src in blob.get("sources", []))


def minutes_to_release(observed_at_utc: str, official_release_utc: str) -> int | None:
    obs, t0 = parse_utc(observed_at_utc), parse_utc(official_release_utc)
    if obs is None or t0 is None:
        return None
    return int((t0 - obs).total_seconds() // 60)


def assert_observed_at_is_our_clock(record: dict) -> None:
    if record.get("observed_at_utc") == record.get("source_publication_utc") and record.get("notes"):
        if "replaced" in str(record.get("notes")).lower():
            raise AssertionError("observed_at_utc must never be replaced by source publication time")
    if not record.get("observed_at_utc"):
        raise AssertionError("observed_at_utc is required")


def prospective_pit_status(observed_at_utc: str, official_release_utc: str) -> str:
    obs, t0 = parse_utc(observed_at_utc), parse_utc(official_release_utc)
    if obs is None or t0 is None:
        return "UNCERTAIN"
    if obs < t0:
        return "PIT_SAFE"
    return "REJECT_POST_RELEASE"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=True) + "\n")


def load_snapshots(path: Path) -> list[dict]:
    return _read_jsonl(path)


def content_key(record: dict) -> tuple:
    return (
        record.get("macro_event_id"),
        record.get("series_name"),
        record.get("source_publisher"),
        record.get("expectation_type"),
        record.get("raw_artifact_hash"),
    )


def next_sequence(existing: list[dict], macro_event_id: str, series_name: str, source_publisher: str) -> int:
    seqs = [
        int(r.get("snapshot_sequence") or 0)
        for r in existing
        if r.get("macro_event_id") == macro_event_id
        and r.get("series_name") == series_name
        and r.get("source_publisher") == source_publisher
    ]
    return (max(seqs) + 1) if seqs else 1


def average_forecasts(records: list[dict]) -> None:
    raise RuntimeError("Providers must not be averaged. Store Reuters, FactSet, Dow Jones separately.")


def store_observed_artifact(
    *,
    artifacts_dir: Path,
    artifact_bytes: bytes,
    suggested_name: str,
) -> tuple[str, str]:
    digest = sha256_bytes(artifact_bytes)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / f"{digest[:16]}_{suggested_name}"
    if path.exists():
        existing = path.read_bytes()
        if existing != artifact_bytes:
            raise RuntimeError("Hash collision with different bytes")
    else:
        path.write_bytes(artifact_bytes)
    return str(path).replace("\\", "/"), digest


def append_snapshot(
    *,
    store_path: Path,
    observations_path: Path,
    artifacts_dir: Path,
    artifact_bytes: bytes,
    artifact_name: str,
    fields: dict[str, Any],
    collection_flag_path: Path = CONFIG_PATH,
    allow_store_without_collection: bool = True,
) -> dict:
    """Append-only snapshot. Identical bytes reuse content snapshot; new observation is always logged."""
    if collection_enabled(collection_flag_path):
        raise RuntimeError("Live collection is not implemented in this research stage.")
    if not allow_store_without_collection:
        raise RuntimeError("FORWARD_CONSENSUS_COLLECTION_ENABLED is false.")

    loc, digest = store_observed_artifact(
        artifacts_dir=artifacts_dir,
        artifact_bytes=artifact_bytes,
        suggested_name=artifact_name,
    )
    observed = fields["observed_at_utc"]
    source_pub = fields.get("source_publication_utc")
    if observed is None:
        raise ValueError("observed_at_utc is required")
    if source_pub and observed == source_pub and fields.get("force_replace_observed_with_source"):
        raise ValueError("observed_at_utc must never be replaced by source_publication_utc")

    existing = load_snapshots(store_path)
    t0 = fields["official_release_utc"]
    rec = {k: fields.get(k) for k in REQUIRED_FIELDS}
    rec["raw_artifact_hash"] = digest
    rec["artifact_location"] = loc
    rec["minutes_to_release"] = minutes_to_release(observed, t0)
    rec["pit_status"] = fields.get("pit_status") or prospective_pit_status(observed, t0)
    rec["source_publication_utc"] = source_pub
    rec["source_updated_utc"] = fields.get("source_updated_utc")
    rec["observed_at_utc"] = observed
    assert_observed_at_is_our_clock(rec)

    match = next((r for r in existing if r.get("raw_artifact_hash") == digest and content_key(r)[0:4] == (
        rec["macro_event_id"], rec["series_name"], rec["source_publisher"], rec["expectation_type"]
    )), None)
    if match is not None:
        observation = {
            "observation_id": str(uuid4()),
            "snapshot_id": match["snapshot_id"],
            "observed_at_utc": observed,
            "deduped_identical_bytes": True,
            "raw_artifact_hash": digest,
            "source_publication_utc": source_pub,
        }
        _append_jsonl(observations_path, observation)
        return {**match, "deduped_identical_bytes": True, "latest_observation": observation}

    rec["snapshot_id"] = fields.get("snapshot_id") or str(uuid4())
    rec["snapshot_sequence"] = next_sequence(
        existing, rec["macro_event_id"], rec["series_name"], rec["source_publisher"]
    )
    for key in REQUIRED_FIELDS:
        if key not in rec:
            rec[key] = None
    _append_jsonl(store_path, rec)
    observation = {
        "observation_id": str(uuid4()),
        "snapshot_id": rec["snapshot_id"],
        "observed_at_utc": observed,
        "deduped_identical_bytes": False,
        "raw_artifact_hash": digest,
        "source_publication_utc": source_pub,
    }
    _append_jsonl(observations_path, observation)
    return {**rec, "deduped_identical_bytes": False, "latest_observation": observation}


def final_pre_release_snapshot(
    snapshots: list[dict],
    *,
    macro_event_id: str,
    series_name: str | None = None,
    source_publisher: str | None = None,
) -> dict | None:
    """Latest snapshot OUR system observed with observed_at_utc < T0. Never post-T0."""
    cand = []
    for rec in snapshots:
        if rec.get("macro_event_id") != macro_event_id:
            continue
        if series_name is not None and rec.get("series_name") != series_name:
            continue
        if source_publisher is not None and rec.get("source_publisher") != source_publisher:
            continue
        obs = parse_utc(rec.get("observed_at_utc"))
        t0 = parse_utc(rec.get("official_release_utc"))
        if obs is None or t0 is None:
            continue
        if obs >= t0:
            continue
        if rec.get("pit_status") == "REJECT_POST_RELEASE":
            continue
        cand.append(rec)
    if not cand:
        return None
    cand.sort(key=lambda r: parse_utc(r["observed_at_utc"]))
    return cand[-1]


def providers_preserved(snapshots: list[dict], macro_event_id: str, series_name: str) -> list[str]:
    pubs = []
    for rec in snapshots:
        if rec.get("macro_event_id") == macro_event_id and rec.get("series_name") == series_name:
            pubs.append(rec.get("source_publisher"))
    return pubs
