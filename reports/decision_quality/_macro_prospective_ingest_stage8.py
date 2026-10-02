"""Stage 8: ingest one genuine T-48h manual Trading Economics screen observation.

Research-only. No network. No adapter enablement. Isolated from production trading.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_REC_PATH = Path(__file__).with_name("_macro_prospective_recorder.py")
_REC_SPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_stage8", _REC_PATH)
R = importlib.util.module_from_spec(_REC_SPEC)
assert _REC_SPEC is not None and _REC_SPEC.loader is not None
_REC_SPEC.loader.exec_module(R)

_AD_PATH = Path(__file__).with_name("_macro_prospective_adapters.py")
_AD_SPEC = importlib.util.spec_from_file_location("macro_prospective_adapters_stage8", _AD_PATH)
A = importlib.util.module_from_spec(_AD_SPEC)
assert _AD_SPEC is not None and _AD_SPEC.loader is not None
_AD_SPEC.loader.exec_module(A)

UTC = timezone.utc
EVENT_ID = "usd_empsit_2026-10-02"
CHECKPOINT_ID = "T0-48h"
T0_UTC = "2026-10-02T12:30:00Z"
CHECKPOINT_UTC = "2026-09-30T12:30:00Z"
PROVIDER = "Trading Economics"
COLLECTION_METHOD = "MANUAL_SCREEN_OBSERVATION"
SOURCE_ID = "trading_economics"
ORIGINAL_OPERATOR_FILENAME = "20260930-1230-50.1109214.mp4"
FOUND_FILENAME = "Screen Recording 2026-09-30 133117.mp4"
DEFAULT_EVIDENCE_SRC = Path.home() / "Videos" / "Screen Recordings" / FOUND_FILENAME
EVIDENCE_DIR_NAME = "evidence"
PROBE_DIR = Path("data/research/macro/consensus_pit/prospective")

# Displayed values from the operator's T-48h screen observation. Consensus is not Forecast.
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
        "consensus_raw": None,
        "te_forecast_raw": "3.1%",
    },
}


class IngestClosed(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def observed_at_from_evidence_stat(path: Path) -> str:
    """Second-precision UTC from filesystem creation time. Do not invent milliseconds."""
    st = Path(path).stat()
    created = datetime.fromtimestamp(st.st_ctime, tz=UTC)
    return created.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def copy_evidence_unchanged(src: Path, dest_dir: Path) -> Path:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    src_hash = sha256_file(src)
    if dest.exists():
        if sha256_file(dest) != src_hash:
            raise IngestClosed("evidence destination exists with different bytes")
        return dest
    shutil.copyfile(src, dest)
    if sha256_file(dest) != src_hash:
        raise IngestClosed("evidence copy hash mismatch")
    return dest


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
    if yoy["consensus_value"] is not None or yoy["consensus_value_quality"] != "NOT_AVAILABLE":
        raise IngestClosed("AHE YoY consensus must remain missing")
    if yoy["te_forecast_value"] == 3.1 and yoy["consensus_value"] == 3.1:
        raise IngestClosed("AHE YoY consensus must not become 3.1")
    return out


def _validate_timestamp(rec: R.ProspectiveRecorder, observed_at_utc: str) -> str:
    event = rec.event_by_id(EVENT_ID)
    if event is None:
        raise IngestClosed("event %s is not registered" % EVENT_ID)
    if event.get("scheduled_release_utc") != T0_UTC:
        raise IngestClosed("T0 mismatch")
    if event.get("checkpoints", {}).get(CHECKPOINT_ID) != CHECKPOINT_UTC:
        raise IngestClosed("T-48h checkpoint mismatch")
    t0 = R.parse_utc(event["scheduled_release_utc"])
    obs = R.parse_utc(observed_at_utc)
    assert t0 and obs
    if obs >= t0:
        raise IngestClosed("observed_at_utc is not pre-T0")
    associated = R.associated_checkpoint_id(event, obs)
    if associated != CHECKPOINT_ID:
        raise IngestClosed("observed_at_utc does not associate to T0-48h (got %s)" % associated)
    return associated


def ingest_stage8(
    *,
    rec: R.ProspectiveRecorder,
    evidence_bytes: bytes,
    observed_at_utc: str,
    evidence_filename: str,
    evidence_sha256: str,
    ingested_at_utc: str,
    evidence_timestamp_basis: str,
    artifact_suffix: str = "mp4",
) -> dict:
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
        "Stage 8 MANUAL_SCREEN_OBSERVATION of Trading Economics Economic Calendar. "
        "Consensus is the displayed survey-average Consensus column, not TE Forecast. "
        "AHE YoY Consensus was blank and is stored as NOT_AVAILABLE."
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
        return out
    obs = out.get("observation") or {}
    if obs.get("associated_checkpoint_id") != associated:
        raise IngestClosed("checkpoint association changed during ingest")
    if obs.get("observed_at_utc") != observed_at_utc:
        raise IngestClosed("observed_at_utc was rewritten")
    return out


def assert_activation_unchanged() -> None:
    cfg = json.loads((PROBE_DIR / "config.json").read_text(encoding="utf-8"))
    if cfg.get("FORWARD_CONSENSUS_COLLECTION_ENABLED") is True:
        raise IngestClosed("FORWARD_CONSENSUS_COLLECTION_ENABLED must remain false")
    blob = json.loads((PROBE_DIR / "source_registry" / "sources.json").read_text(encoding="utf-8"))
    te = next(s for s in blob["sources"] if s["source_id"] == "trading_economics")
    if te.get("enabled") is True:
        raise IngestClosed("trading_economics must remain disabled")
    if te.get("automation_class") == "APPROVED_AUTOMATION_READY":
        raise IngestClosed("trading_economics must not be APPROVED_AUTOMATION_READY")
    if any(s.get("source_id") == "forex_factory" and s.get("enabled") is True for s in blob["sources"]):
        raise IngestClosed("forex_factory must not be live")


def run_live(src: Path | None = None) -> dict:
    src = Path(src) if src is not None else DEFAULT_EVIDENCE_SRC
    if not src.exists():
        raise IngestClosed("EVIDENCE_FILE_NOT_FOUND: %s" % src)
    assert_activation_unchanged()
    rec = R.ProspectiveRecorder(PROBE_DIR)
    existing = [
        o
        for o in rec.load_observations()
        if o.get("macro_event_id") == EVENT_ID
        and (o.get("associated_checkpoint_id") or o.get("checkpoint_id")) == CHECKPOINT_ID
        and o.get("expectation_type") == "SURVEY_CONSENSUS"
    ]
    if existing:
        raise IngestClosed("genuine T-48h observation already exists")
    observed_at = observed_at_from_evidence_stat(src)
    evidence_hash = sha256_file(src)
    ingested_at = R.to_utc_iso(rec.now())
    dest = copy_evidence_unchanged(src, rec.root / EVIDENCE_DIR_NAME)
    meta = {
        "original_operator_filename": ORIGINAL_OPERATOR_FILENAME,
        "found_filename": src.name,
        "source_path": str(src),
        "imported_path": str(dest).replace("\\", "/"),
        "sha256": evidence_hash,
        "bytes": src.stat().st_size,
        "observed_at_utc": observed_at,
        "evidence_timestamp_basis": (
            "Windows filesystem creation time (st_ctime) truncated to UTC seconds; "
            "agrees with filename Screen Recording 2026-09-30 133117.mp4 as 13:31:17 BST "
            "and CreationTimeUtc 2026-09-30T12:31:17Z. Media Created displays 13:30 local. "
            "The operator-supplied name 20260930-1230-50.1109214.mp4 was not present."
        ),
        "checkpoint_id": CHECKPOINT_ID,
        "collection_method": COLLECTION_METHOD,
        "provider": PROVIDER,
    }
    (rec.root / EVIDENCE_DIR_NAME / "stage8_evidence.meta.json").write_bytes(
        (json.dumps(meta, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    )
    evidence_bytes = dest.read_bytes()
    if sha256_bytes(evidence_bytes) != evidence_hash:
        raise IngestClosed("imported evidence bytes hash mismatch")
    out = ingest_stage8(
        rec=rec,
        evidence_bytes=evidence_bytes,
        observed_at_utc=observed_at,
        evidence_filename=src.name,
        evidence_sha256=evidence_hash,
        ingested_at_utc=ingested_at,
        evidence_timestamp_basis=meta["evidence_timestamp_basis"],
        artifact_suffix="mp4",
    )
    assert_activation_unchanged()
    out["evidence_meta"] = meta
    return out


if __name__ == "__main__":
    import sys

    result = run_live()
    obs = result.get("observation") or {}
    comps = (obs.get("calendar_fields") or {}).get("components") or {}
    print("status=%s" % result.get("status"))
    print("observation_id=%s" % obs.get("observation_id"))
    print("observed_at_utc=%s" % obs.get("observed_at_utc"))
    print("retrieval_utc=%s" % obs.get("retrieval_utc"))
    print("checkpoint_id=%s" % obs.get("checkpoint_id"))
    print("associated_checkpoint_id=%s" % obs.get("associated_checkpoint_id"))
    print("raw_artifact_sha256=%s" % obs.get("raw_artifact_sha256"))
    print("nfp_consensus=%s" % (comps.get("nonfarm_payroll_change") or {}).get("consensus_value"))
    print("ahe_yoy_quality=%s" % (comps.get("average_hourly_earnings_yoy") or {}).get("consensus_value_quality"))
    sys.exit(0)
