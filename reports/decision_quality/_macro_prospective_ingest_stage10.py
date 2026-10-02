"""Stage 10: ingest one genuine T-12h manual Trading Economics screen observation.

Reuses Stage 8/9 copy/hash/normalization rules. Does not alter T-48h, T-36h, or T-24h.
AHE YoY Consensus is now 3.2% and must stay distinct from TE Forecast 3.1%.
Research-only. No network. No adapter enablement.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import timezone
from pathlib import Path
from typing import Any

_S8_PATH = Path(__file__).with_name("_macro_prospective_ingest_stage8.py")
_S8_SPEC = importlib.util.spec_from_file_location("macro_stage8_for_stage10", _S8_PATH)
S8 = importlib.util.module_from_spec(_S8_SPEC)
assert _S8_SPEC is not None and _S8_SPEC.loader is not None
_S8_SPEC.loader.exec_module(S8)

R = S8.R
A = S8.A
UTC = timezone.utc
EVENT_ID = S8.EVENT_ID
T0_UTC = S8.T0_UTC
CHECKPOINT_ID = "T0-12h"
CHECKPOINT_UTC = "2026-10-02T00:30:00Z"
T48_CHECKPOINT = "T0-48h"
T36_CHECKPOINT = "T0-36h"
T24_CHECKPOINT = "T0-24h"
PROVIDER = S8.PROVIDER
COLLECTION_METHOD = S8.COLLECTION_METHOD
SOURCE_ID = S8.SOURCE_ID
PROBE_DIR = S8.PROBE_DIR
EVIDENCE_DIR_NAME = S8.EVIDENCE_DIR_NAME
CANDIDATE_PATHS = (
    Path.home() / "Videos" / "Screen Recordings" / "Screen Recording 2026-10-02 013036.mp4",
    Path.home() / "Videos" / "Recording 2026-10-02 013041.mp4",
)

DISPLAYED = {
    "nonfarm_payroll_change": {
        "returned_event_name": "Non Farm Payrolls",
        "previous_raw": "162K",
        "consensus_raw": "90K",
        "te_forecast_raw": "90.0K",
    },
    "unemployment_rate": {
        "returned_event_name": "Unemployment Rate",
        "previous_raw": "4.1%",
        "consensus_raw": "4.1%",
        "te_forecast_raw": "4.1%",
    },
    "average_hourly_earnings_mom": {
        "returned_event_name": "Average Hourly Earnings MoM",
        "previous_raw": "0.3%",
        "consensus_raw": "0.3%",
        "te_forecast_raw": "0.2%",
    },
    "average_hourly_earnings_yoy": {
        "returned_event_name": "Average Hourly Earnings YoY",
        "previous_raw": "3.1%",
        "consensus_raw": "3.2%",
        "te_forecast_raw": "3.1%",
    },
}


class IngestClosed(S8.IngestClosed):
    pass


def build_components(displayed: dict[str, dict] | None = None) -> dict[str, dict]:
    displayed = displayed or DISPLAYED
    out: dict[str, dict[str, Any]] = {}
    for series, row in displayed.items():
        consensus_raw = row.get("consensus_raw")
        missing = consensus_raw in (None, "")
        if series == "nonfarm_payroll_change":
            consensus_value = None if missing else A.normalize_jobs_value(consensus_raw)
            previous_value = A.normalize_jobs_value(row["previous_raw"])
            te_value = A.normalize_jobs_value(row["te_forecast_raw"])
            unit = "persons"
        else:
            consensus_value = None if missing else A.normalize_percent_value(consensus_raw)
            previous_value = A.normalize_percent_value(row["previous_raw"])
            te_value = A.normalize_percent_value(row["te_forecast_raw"])
            unit = "percent"
        if missing and consensus_value is not None:
            raise IngestClosed("missing consensus must not receive a numeric value")
        if missing and te_value is not None and consensus_value == te_value:
            raise IngestClosed("missing consensus must not be replaced by TE Forecast")
        if (not missing) and te_value is not None and consensus_value == te_value and series == "average_hourly_earnings_yoy":
            raise IngestClosed("AHE YoY TE Forecast must not overwrite Consensus")
        out[series] = {
            "returned_event_name": row["returned_event_name"],
            "previous_raw": row["previous_raw"],
            "previous_value": previous_value,
            "consensus_raw": consensus_raw,
            "consensus_value": consensus_value,
            "consensus_value_quality": "NOT_AVAILABLE" if missing else "PRESENT",
            "te_forecast_raw": row["te_forecast_raw"],
            "te_forecast_value": te_value,
            "te_forecast_semantics": "PROVIDER_FORECAST_NOT_CONSENSUS",
            "unit": unit,
            "consensus_substituted_from_te_forecast": False,
        }
    yoy = out["average_hourly_earnings_yoy"]
    if yoy["consensus_value_quality"] != "PRESENT" or yoy["consensus_value"] is None:
        raise IngestClosed("AHE YoY consensus must be present at T-12h")
    if yoy["consensus_value"] != 3.2:
        raise IngestClosed("AHE YoY consensus must be 3.2")
    if yoy["te_forecast_value"] != 3.1:
        raise IngestClosed("AHE YoY TE Forecast must remain 3.1")
    if yoy["consensus_value"] == yoy["te_forecast_value"]:
        raise IngestClosed("AHE YoY Consensus must stay distinct from TE Forecast")
    return out


def inspect_candidate(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {
            "path": str(path),
            "filename": path.name,
            "found": False,
            "sha256": None,
            "observed_at_utc": None,
            "valid_for_t12h": False,
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
        "valid_for_t12h": is_valid_t12h(observed_at),
        "bytes": path.stat().st_size,
        "timestamp_basis": (
            "Windows filesystem creation time (st_ctime) truncated to UTC seconds; "
            "same Stage 8/9 provenance rule. Filename is corroboration only."
        ),
    }


def is_valid_t12h(observed_at_utc: str, event: dict | None = None) -> bool:
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
    valid = [c for c in found if c.get("valid_for_t12h")]
    if not valid:
        raise IngestClosed("no candidate is at or after scheduled T-12h")
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
        raise IngestClosed("T-12h checkpoint mismatch")
    t0 = R.parse_utc(event["scheduled_release_utc"])
    obs = R.parse_utc(observed_at_utc)
    assert t0 and obs
    if obs >= t0:
        raise IngestClosed("observed_at_utc is not pre-T0")
    if not is_valid_t12h(observed_at_utc, event):
        raise IngestClosed("observed_at_utc is not valid for T0-12h")
    associated = R.associated_checkpoint_id(event, obs)
    if associated != CHECKPOINT_ID:
        raise IngestClosed("observed_at_utc does not associate to T0-12h (got %s)" % associated)
    return associated


def checkpoint_rows(rec: R.ProspectiveRecorder, checkpoint_id: str) -> list[dict]:
    return [
        o
        for o in rec.load_observations()
        if o.get("macro_event_id") == EVENT_ID
        and (o.get("associated_checkpoint_id") or o.get("checkpoint_id")) == checkpoint_id
    ]


def fingerprint(obs: dict | None) -> dict[str, Any] | None:
    if not obs:
        return None
    return {
        "observation_id": obs.get("observation_id"),
        "observed_at_utc": obs.get("observed_at_utc"),
        "raw_artifact_sha256": obs.get("raw_artifact_sha256"),
        "forecast_value": obs.get("forecast_value"),
        "logical_id": obs.get("logical_id"),
        "ahe_yoy_consensus": ((obs.get("calendar_fields") or {}).get("components") or {})
        .get("average_hourly_earnings_yoy", {})
        .get("consensus_value"),
        "ahe_yoy_quality": ((obs.get("calendar_fields") or {}).get("components") or {})
        .get("average_hourly_earnings_yoy", {})
        .get("consensus_value_quality"),
    }


def ingest_stage10(
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
    prior_t24: dict | None = None,
) -> dict:
    if prior_t48 is None:
        t48_rows = checkpoint_rows(rec, T48_CHECKPOINT)
        prior_t48 = fingerprint(t48_rows[0] if t48_rows else None)
    if prior_t24 is None:
        t24_rows = checkpoint_rows(rec, T24_CHECKPOINT)
        prior_t24 = fingerprint(t24_rows[0] if t24_rows else None)
    t36_before = len(checkpoint_rows(rec, T36_CHECKPOINT))
    associated = _validate_timestamp(rec, observed_at_utc)
    components = build_components()
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
        "Stage 10 MANUAL_SCREEN_OBSERVATION of Trading Economics Economic Calendar at T-12h. "
        "Consensus is the displayed survey-average Consensus column, not TE Forecast. "
        "AHE YoY Consensus is 3.2% and is distinct from TE Forecast 3.1%. "
        "T-48h and T-24h AHE YoY remain missing. T-36h was not backfilled."
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
        _assert_priors_unchanged(rec, prior_t48, prior_t24, t36_before)
        return out
    obs = out.get("observation") or {}
    if obs.get("associated_checkpoint_id") != associated:
        raise IngestClosed("checkpoint association changed during ingest")
    if obs.get("observed_at_utc") != observed_at_utc:
        raise IngestClosed("observed_at_utc was rewritten")
    _assert_priors_unchanged(rec, prior_t48, prior_t24, t36_before)
    t12 = checkpoint_rows(rec, CHECKPOINT_ID)
    if len(t12) != 1:
        raise IngestClosed("expected exactly one T-12h observation, got %s" % len(t12))
    return out


def _assert_priors_unchanged(
    rec: R.ProspectiveRecorder,
    prior_t48: dict | None,
    prior_t24: dict | None,
    t36_before: int,
) -> None:
    t48_rows = checkpoint_rows(rec, T48_CHECKPOINT)
    t24_rows = checkpoint_rows(rec, T24_CHECKPOINT)
    if prior_t48 is not None and fingerprint(t48_rows[0] if t48_rows else None) != prior_t48:
        raise IngestClosed("T-48h observation changed")
    if prior_t24 is not None and fingerprint(t24_rows[0] if t24_rows else None) != prior_t24:
        raise IngestClosed("T-24h observation changed")
    if len(checkpoint_rows(rec, T36_CHECKPOINT)) != t36_before:
        raise IngestClosed("T-36h was backfilled")


def _component_status(left: dict, right: dict, *, became_available_label: str | None = None) -> str:
    lq = left.get("consensus_value_quality")
    rq = right.get("consensus_value_quality")
    if lq == "NOT_AVAILABLE" and rq == "NOT_AVAILABLE":
        return "STILL MISSING"
    if lq == "NOT_AVAILABLE" and rq == "PRESENT":
        return became_available_label or "CONSENSUS BECAME AVAILABLE"
    if left.get("consensus_value") == right.get("consensus_value"):
        return "NO CHANGE"
    return "CHANGED"


def compare_vintages(earlier: dict, later: dict, *, ahe_yoy_label: str | None = None) -> dict[str, str]:
    a = (earlier.get("calendar_fields") or {}).get("components") or {}
    b = (later.get("calendar_fields") or {}).get("components") or {}
    return {
        "nfp": _component_status(a.get("nonfarm_payroll_change") or {}, b.get("nonfarm_payroll_change") or {}),
        "unemployment": _component_status(a.get("unemployment_rate") or {}, b.get("unemployment_rate") or {}),
        "ahe_mom": _component_status(
            a.get("average_hourly_earnings_mom") or {}, b.get("average_hourly_earnings_mom") or {}
        ),
        "ahe_yoy": _component_status(
            a.get("average_hourly_earnings_yoy") or {},
            b.get("average_hourly_earnings_yoy") or {},
            became_available_label=ahe_yoy_label,
        ),
    }


def run_live() -> dict:
    S8.assert_activation_unchanged()
    rec = R.ProspectiveRecorder(PROBE_DIR)
    t48_rows = checkpoint_rows(rec, T48_CHECKPOINT)
    t24_rows = checkpoint_rows(rec, T24_CHECKPOINT)
    if not t48_rows:
        raise IngestClosed("T-48h observation is missing; Stage 10 will not proceed")
    if not t24_rows:
        raise IngestClosed("T-24h observation is missing; Stage 10 will not proceed")
    prior_t48 = fingerprint(t48_rows[0])
    prior_t24 = fingerprint(t24_rows[0])
    existing_t12 = [
        o
        for o in checkpoint_rows(rec, CHECKPOINT_ID)
        if o.get("expectation_type") == "SURVEY_CONSENSUS"
    ]
    if existing_t12:
        raise IngestClosed("genuine T-12h observation already exists")
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
            "Earliest candidate whose Stage 8/9 filesystem-ctime UTC second is "
            ">= 2026-10-02T00:30:00Z and associates to T0-12h. "
            "Upload filename 20261002-0030-19.7514577.mp4 was not used."
        ),
        "supplementary_not_ingested": [
            {"filename": s["filename"], "sha256": s["sha256"], "observed_at_utc": s["observed_at_utc"]}
            for s in supplementary
        ],
        "t48_fingerprint_before": prior_t48,
        "t24_fingerprint_before": prior_t24,
    }
    (rec.root / EVIDENCE_DIR_NAME / "stage10_evidence.meta.json").write_bytes(
        (json.dumps(meta, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    )
    evidence_bytes = dest.read_bytes()
    if S8.sha256_bytes(evidence_bytes) != canonical["sha256"]:
        raise IngestClosed("imported evidence bytes hash mismatch")
    out = ingest_stage10(
        rec=rec,
        evidence_bytes=evidence_bytes,
        observed_at_utc=canonical["observed_at_utc"],
        evidence_filename=canonical["filename"],
        evidence_sha256=canonical["sha256"],
        ingested_at_utc=ingested_at,
        evidence_timestamp_basis=canonical["timestamp_basis"],
        artifact_suffix="mp4",
        prior_t48=prior_t48,
        prior_t24=prior_t24,
    )
    S8.assert_activation_unchanged()
    _assert_priors_unchanged(rec, prior_t48, prior_t24, 0)
    out["evidence_meta"] = meta
    out["candidates"] = inspected
    out["canonical"] = canonical
    out["supplementary"] = supplementary
    t48_row = next(o for o in rec.load_observations() if o.get("observation_id") == prior_t48["observation_id"])
    t24_row = next(o for o in rec.load_observations() if o.get("observation_id") == prior_t24["observation_id"])
    t12_row = out.get("observation") or {}
    out["t48_t24_comparison"] = compare_vintages(t48_row, t24_row)
    out["t24_t12_comparison"] = compare_vintages(
        t24_row, t12_row, ahe_yoy_label="CONSENSUS BECAME AVAILABLE AT T-12H"
    )
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
    print("ahe_yoy_consensus=%s" % (comps.get("average_hourly_earnings_yoy") or {}).get("consensus_value"))
    print("ahe_yoy_forecast=%s" % (comps.get("average_hourly_earnings_yoy") or {}).get("te_forecast_value"))
    print("t48_t24=%s" % result.get("t48_t24_comparison"))
    print("t24_t12=%s" % result.get("t24_t12_comparison"))
