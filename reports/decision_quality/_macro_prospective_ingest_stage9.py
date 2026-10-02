"""Stage 9: ingest one genuine T-24h manual Trading Economics screen observation.

Reuses Stage 8 component/normalization/copy rules. Does not alter T-48h or backfill T-36h.
Research-only. No network. No adapter enablement.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import timezone
from pathlib import Path
from typing import Any

_S8_PATH = Path(__file__).with_name("_macro_prospective_ingest_stage8.py")
_S8_SPEC = importlib.util.spec_from_file_location("macro_stage8_for_stage9", _S8_PATH)
S8 = importlib.util.module_from_spec(_S8_SPEC)
assert _S8_SPEC is not None and _S8_SPEC.loader is not None
_S8_SPEC.loader.exec_module(S8)

R = S8.R
UTC = timezone.utc
EVENT_ID = S8.EVENT_ID
T0_UTC = S8.T0_UTC
CHECKPOINT_ID = "T0-24h"
CHECKPOINT_UTC = "2026-10-01T12:30:00Z"
T48_CHECKPOINT = "T0-48h"
T36_CHECKPOINT = "T0-36h"
PROVIDER = S8.PROVIDER
COLLECTION_METHOD = S8.COLLECTION_METHOD
SOURCE_ID = S8.SOURCE_ID
PROBE_DIR = S8.PROBE_DIR
EVIDENCE_DIR_NAME = S8.EVIDENCE_DIR_NAME
CANDIDATE_PATHS = (
    Path.home() / "Videos" / "Screen Recordings" / "Screen Recording 2026-10-01 133043.mp4",
    Path.home() / "Videos" / "Recording 2026-10-01 133049.mp4",
)


class IngestClosed(S8.IngestClosed):
    pass


def inspect_candidate(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {
            "path": str(path),
            "filename": path.name,
            "found": False,
            "sha256": None,
            "observed_at_utc": None,
            "valid_for_t24h": False,
            "bytes": None,
        }
    observed_at = S8.observed_at_from_evidence_stat(path)
    digest = S8.sha256_file(path)
    return {
        "path": str(path),
        "filename": path.name,
        "found": True,
        "sha256": digest,
        "observed_at_utc": observed_at,
        "valid_for_t24h": is_valid_t24h(observed_at),
        "bytes": path.stat().st_size,
        "timestamp_basis": (
            "Windows filesystem creation time (st_ctime) truncated to UTC seconds; "
            "same Stage 8 provenance rule. Filename is corroboration only."
        ),
    }


def is_valid_t24h(observed_at_utc: str, event: dict | None = None) -> bool:
    obs = R.parse_utc(observed_at_utc)
    sched = R.parse_utc(CHECKPOINT_UTC)
    t0 = R.parse_utc(T0_UTC)
    assert obs and sched and t0
    if obs < sched or obs >= t0:
        return False
    if event is not None:
        return R.associated_checkpoint_id(event, obs) == CHECKPOINT_ID
    return True


def select_canonical(candidates: list[dict]) -> tuple[dict, list[dict]]:
    found = [c for c in candidates if c.get("found")]
    if not found:
        raise IngestClosed("no candidate evidence files found")
    valid = [c for c in found if c.get("valid_for_t24h")]
    if not valid:
        raise IngestClosed("no candidate is at or after scheduled T-24h")
    valid_sorted = sorted(valid, key=lambda c: (c["observed_at_utc"], c["filename"]))
    canonical = valid_sorted[0]
    canonical_path = canonical.get("path")
    supplementary = [c for c in found if c.get("path") != canonical_path]
    return canonical, supplementary


def _validate_timestamp(rec: R.ProspectiveRecorder, observed_at_utc: str) -> str:
    event = rec.event_by_id(EVENT_ID)
    if event is None:
        raise IngestClosed("event %s is not registered" % EVENT_ID)
    if event.get("scheduled_release_utc") != T0_UTC:
        raise IngestClosed("T0 mismatch")
    if event.get("checkpoints", {}).get(CHECKPOINT_ID) != CHECKPOINT_UTC:
        raise IngestClosed("T-24h checkpoint mismatch")
    t0 = R.parse_utc(event["scheduled_release_utc"])
    obs = R.parse_utc(observed_at_utc)
    assert t0 and obs
    if obs >= t0:
        raise IngestClosed("observed_at_utc is not pre-T0")
    if not is_valid_t24h(observed_at_utc, event):
        raise IngestClosed("observed_at_utc is not valid for T0-24h")
    associated = R.associated_checkpoint_id(event, obs)
    if associated != CHECKPOINT_ID:
        raise IngestClosed("observed_at_utc does not associate to T0-24h (got %s)" % associated)
    return associated


def t48_fingerprint(rec: R.ProspectiveRecorder) -> dict[str, Any] | None:
    rows = [
        o
        for o in rec.load_observations()
        if o.get("macro_event_id") == EVENT_ID
        and (o.get("associated_checkpoint_id") or o.get("checkpoint_id")) == T48_CHECKPOINT
    ]
    if not rows:
        return None
    row = rows[0]
    return {
        "observation_id": row.get("observation_id"),
        "observed_at_utc": row.get("observed_at_utc"),
        "raw_artifact_sha256": row.get("raw_artifact_sha256"),
        "forecast_value": row.get("forecast_value"),
        "logical_id": row.get("logical_id"),
    }


def t36_observations(rec: R.ProspectiveRecorder) -> list[dict]:
    return [
        o
        for o in rec.load_observations()
        if o.get("macro_event_id") == EVENT_ID
        and (o.get("associated_checkpoint_id") or o.get("checkpoint_id")) == T36_CHECKPOINT
    ]


def ingest_stage9(
    *,
    rec: R.ProspectiveRecorder,
    evidence_bytes: bytes,
    observed_at_utc: str,
    evidence_filename: str,
    evidence_sha256: str,
    ingested_at_utc: str,
    evidence_timestamp_basis: str,
    artifact_suffix: str = "mp4",
    prior_t48: dict | None = None,
) -> dict:
    if prior_t48 is None:
        prior_t48 = t48_fingerprint(rec)
    t36_before = len(t36_observations(rec))
    associated = _validate_timestamp(rec, observed_at_utc)
    components = S8.build_components()
    nfp = components["nonfarm_payroll_change"]
    calendar_fields = {
        "collection_method": COLLECTION_METHOD,
        "provider": PROVIDER,
        "displayed_columns": ["Actual", "Previous", "Consensus", "Forecast"],
        "consensus_field_semantics": "SURVEY_CONSENSUS",
        "forecast_field_semantics": "PROVIDER_FORECAST_NOT_CONSENSUS",
        "evidence_filename": evidence_filename,
        "evidence_sha256": evidence_sha256,
        "evidence_timestamp_basis": evidence_timestamp_basis,
        "components": components,
    }
    notes = (
        "Stage 9 MANUAL_SCREEN_OBSERVATION of Trading Economics Economic Calendar at T-24h. "
        "Consensus is the displayed survey-average Consensus column, not TE Forecast. "
        "AHE YoY Consensus was blank and is stored as NOT_AVAILABLE. T-48h was not modified. T-36h was not backfilled."
    )
    out = rec.ingest_observation(
        macro_event_id=EVENT_ID,
        source_id=SOURCE_ID,
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=evidence_bytes,
        artifact_suffix=artifact_suffix,
        observed_at_utc=observed_at_utc,
        checkpoint_id=CHECKPOINT_ID,
        forecast_value=nfp["consensus_value"],
        value_quality="PRESENT",
        unit="persons",
        seasonal_adjustment="SA",
        retrieval_method="manual",
        observation_kind="FORECASTER",
        calendar_fields=calendar_fields,
        notes=notes,
        provider_name=PROVIDER,
        retrieval_utc=ingested_at_utc,
        allow_autonomous=False,
    )
    if out.get("status") == "ALREADY_EXISTS":
        after = t48_fingerprint(rec)
        if prior_t48 is not None and after != prior_t48:
            raise IngestClosed("T-48h observation changed")
        return out
    obs = out.get("observation") or {}
    if obs.get("associated_checkpoint_id") != associated:
        raise IngestClosed("checkpoint association changed during ingest")
    if obs.get("observed_at_utc") != observed_at_utc:
        raise IngestClosed("observed_at_utc was rewritten")
    after = t48_fingerprint(rec)
    if prior_t48 is not None and after != prior_t48:
        raise IngestClosed("T-48h observation changed")
    if len(t36_observations(rec)) != t36_before:
        raise IngestClosed("T-36h was backfilled")
    t24 = [
        o
        for o in rec.load_observations()
        if o.get("macro_event_id") == EVENT_ID
        and (o.get("associated_checkpoint_id") or o.get("checkpoint_id")) == CHECKPOINT_ID
    ]
    if len(t24) != 1:
        raise IngestClosed("expected exactly one T-24h observation, got %s" % len(t24))
    return out


def compare_t48_t24(t48: dict, t24: dict) -> dict[str, str]:
    a = (t48.get("calendar_fields") or {}).get("components") or {}
    b = (t24.get("calendar_fields") or {}).get("components") or {}

    def _status(series: str) -> str:
        left = a.get(series) or {}
        right = b.get(series) or {}
        lq = left.get("consensus_value_quality")
        rq = right.get("consensus_value_quality")
        if lq == "NOT_AVAILABLE" and rq == "NOT_AVAILABLE":
            return "STILL MISSING"
        if left.get("consensus_value") == right.get("consensus_value"):
            return "NO CHANGE"
        return "CHANGED"

    return {
        "nfp": _status("nonfarm_payroll_change"),
        "unemployment": _status("unemployment_rate"),
        "ahe_mom": _status("average_hourly_earnings_mom"),
        "ahe_yoy": _status("average_hourly_earnings_yoy"),
    }


def run_live() -> dict:
    S8.assert_activation_unchanged()
    rec = R.ProspectiveRecorder(PROBE_DIR)
    prior_t48 = t48_fingerprint(rec)
    if prior_t48 is None:
        raise IngestClosed("T-48h observation is missing; Stage 9 will not proceed")
    existing_t24 = [
        o
        for o in rec.load_observations()
        if o.get("macro_event_id") == EVENT_ID
        and (o.get("associated_checkpoint_id") or o.get("checkpoint_id")) == CHECKPOINT_ID
        and o.get("expectation_type") == "SURVEY_CONSENSUS"
    ]
    if existing_t24:
        raise IngestClosed("genuine T-24h observation already exists")
    inspected = [inspect_candidate(p) for p in CANDIDATE_PATHS]
    canonical, supplementary = select_canonical(inspected)
    src = Path(canonical["path"])
    dest = S8.copy_evidence_unchanged(src, rec.root / EVIDENCE_DIR_NAME)
    copy_hash = S8.sha256_file(dest)
    if copy_hash != canonical["sha256"]:
        raise IngestClosed("copied evidence hash mismatch")
    ingested_at = R.to_utc_iso(rec.now())
    meta = {
        "checkpoint_id": CHECKPOINT_ID,
        "collection_method": COLLECTION_METHOD,
        "provider": PROVIDER,
        "candidates": inspected,
        "canonical_filename": canonical["filename"],
        "canonical_source_path": canonical["path"],
        "imported_path": str(dest).replace("\\", "/"),
        "sha256": canonical["sha256"],
        "observed_at_utc": canonical["observed_at_utc"],
        "evidence_timestamp_basis": canonical["timestamp_basis"],
        "selection_reason": (
            "Earliest candidate whose Stage 8 filesystem-ctime UTC second is "
            ">= 2026-10-01T12:30:00Z and associates to T0-24h. "
            "Upload filenames 20261001-1230-38.* were not used."
        ),
        "supplementary_not_ingested": [
            {"filename": s["filename"], "sha256": s["sha256"], "observed_at_utc": s["observed_at_utc"]}
            for s in supplementary
        ],
        "t48_fingerprint_before": prior_t48,
    }
    (rec.root / EVIDENCE_DIR_NAME / "stage9_evidence.meta.json").write_bytes(
        (json.dumps(meta, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    )
    evidence_bytes = dest.read_bytes()
    if S8.sha256_bytes(evidence_bytes) != canonical["sha256"]:
        raise IngestClosed("imported evidence bytes hash mismatch")
    out = ingest_stage9(
        rec=rec,
        evidence_bytes=evidence_bytes,
        observed_at_utc=canonical["observed_at_utc"],
        evidence_filename=canonical["filename"],
        evidence_sha256=canonical["sha256"],
        ingested_at_utc=ingested_at,
        evidence_timestamp_basis=canonical["timestamp_basis"],
        artifact_suffix="mp4",
        prior_t48=prior_t48,
    )
    S8.assert_activation_unchanged()
    if t48_fingerprint(rec) != prior_t48:
        raise IngestClosed("T-48h observation changed after ingest")
    out["evidence_meta"] = meta
    out["candidates"] = inspected
    out["canonical"] = canonical
    out["supplementary"] = supplementary
    t48_row = next(
        o
        for o in rec.load_observations()
        if o.get("observation_id") == prior_t48["observation_id"]
    )
    out["t48_t24_comparison"] = compare_t48_t24(t48_row, out.get("observation") or {})
    return out


if __name__ == "__main__":
    result = run_live()
    obs = result.get("observation") or {}
    comps = (obs.get("calendar_fields") or {}).get("components") or {}
    print("status=%s" % result.get("status"))
    print("observation_id=%s" % obs.get("observation_id"))
    print("observed_at_utc=%s" % obs.get("observed_at_utc"))
    print("retrieval_utc=%s" % obs.get("retrieval_utc"))
    print("checkpoint_id=%s" % obs.get("checkpoint_id"))
    print("canonical=%s" % (result.get("canonical") or {}).get("filename"))
    print("sha256=%s" % obs.get("raw_artifact_sha256"))
    print("nfp_consensus=%s" % (comps.get("nonfarm_payroll_change") or {}).get("consensus_value"))
    print("ahe_yoy_quality=%s" % (comps.get("average_hourly_earnings_yoy") or {}).get("consensus_value_quality"))
    print("comparison=%s" % result.get("t48_t24_comparison"))
