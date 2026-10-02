"""Stage 13: local manual evidence intake. Zero external requests.

Phase A archives a local screenshot/video with filesystem provenance.
Phase B optionally ingests operator-transcribed values against that evidence.
Does not OCR, scrape, or enable adapters.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_REC_PATH = Path(__file__).with_name("_macro_prospective_recorder.py")
_REC_SPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_stage13", _REC_PATH)
R = importlib.util.module_from_spec(_REC_SPEC)
assert _REC_SPEC is not None and _REC_SPEC.loader is not None
_REC_SPEC.loader.exec_module(R)

_AD_PATH = Path(__file__).with_name("_macro_prospective_adapters.py")
_AD_SPEC = importlib.util.spec_from_file_location("macro_prospective_adapters_stage13", _AD_PATH)
A = importlib.util.module_from_spec(_AD_SPEC)
assert _AD_SPEC is not None and _AD_SPEC.loader is not None
_AD_SPEC.loader.exec_module(A)

UTC = timezone.utc
PROBE_DIR = Path("data/research/macro/consensus_pit/prospective")
EVIDENCE_DIR_NAME = "evidence"
INTAKE_SUBDIR = "intake"
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".mp4")
CLOCK_SKEW_TOLERANCE_SECONDS = 120
TIMESTAMP_BASIS = (
    "Windows filesystem creation time (st_ctime) truncated to UTC seconds. "
    "Filename text is corroboration only and is never observed_at_utc."
)
CPI_EXPECTED_COMPONENTS = list(R.CPI_SERIES)


class IntakeClosed(RuntimeError):
    pass


def normalize_checkpoint(raw: str) -> str:
    token = (raw or "").strip().upper().replace("−", "-").replace("_", "-")
    aliases = {
        "T48H": "T0-48h",
        "T-48H": "T0-48h",
        "T0-48H": "T0-48h",
        "T36H": "T0-36h",
        "T-36H": "T0-36h",
        "T0-36H": "T0-36h",
        "T24H": "T0-24h",
        "T-24H": "T0-24h",
        "T0-24H": "T0-24h",
        "T12H": "T0-12h",
        "T-12H": "T0-12h",
        "T0-12H": "T0-12h",
        "T6H": "T0-6h",
        "T-6H": "T0-6h",
        "T0-6H": "T0-6h",
        "T4H": "T0-4h",
        "T-4H": "T0-4h",
        "T0-4H": "T0-4h",
        "T2H": "T0-2h",
        "T-2H": "T0-2h",
        "T0-2H": "T0-2h",
        "T1H": "T0-1h",
        "T-1H": "T0-1h",
        "T0-1H": "T0-1h",
        "T30M": "T0-30m",
        "T-30M": "T0-30m",
        "T0-30M": "T0-30m",
        "T15M": "T0-15m",
        "T-15M": "T0-15m",
        "T0-15M": "T0-15m",
        "T5M": "T0-5m",
        "T-5M": "T0-5m",
        "T0-5M": "T0-5m",
    }
    mapped = aliases.get(token)
    if mapped:
        return mapped
    for cid, _delta in R.CHECKPOINTS:
        if token == cid.upper():
            return cid
    raise IntakeClosed("unsupported checkpoint label: %s" % raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filesystem_times(path: Path, times_fn: Callable[[Path], tuple[datetime, datetime]] | None = None) -> tuple[datetime, datetime]:
    if times_fn is not None:
        created, modified = times_fn(path)
    else:
        st = Path(path).stat()
        created = datetime.fromtimestamp(st.st_ctime, tz=UTC)
        modified = datetime.fromtimestamp(st.st_mtime, tz=UTC)
    created = created.astimezone(UTC).replace(microsecond=0)
    modified = modified.astimezone(UTC).replace(microsecond=0)
    return created, modified


def to_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def evidence_id(event_id: str, checkpoint_id: str, sha256: str) -> str:
    return "%s|%s|%s" % (event_id, checkpoint_id, sha256)


def archive_filename(event_id: str, checkpoint_id: str, sha256: str, ext: str) -> str:
    return "%s__%s__%s%s" % (event_id, checkpoint_id, sha256, ext)


def intake_dir(rec: R.ProspectiveRecorder) -> Path:
    return rec.root / EVIDENCE_DIR_NAME / INTAKE_SUBDIR


def index_path(rec: R.ProspectiveRecorder) -> Path:
    return intake_dir(rec) / "index.jsonl"


def load_index(rec: R.ProspectiveRecorder) -> list[dict]:
    path = index_path(rec)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_index(rec: R.ProspectiveRecorder, row: dict) -> None:
    dest = index_path(rec)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def find_by_sha(rec: R.ProspectiveRecorder, sha256: str) -> list[dict]:
    return [row for row in load_index(rec) if row.get("source_sha256") == sha256]


def find_by_id(rec: R.ProspectiveRecorder, evidence_ref: str) -> dict | None:
    for row in load_index(rec):
        if row.get("evidence_id") == evidence_ref:
            return row
    return None


def atomic_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=dest.name + ".", suffix=".tmp", dir=str(dest.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out, src.open("rb") as inp:
            while True:
                chunk = inp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, dest)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def describe_t48h(rec: R.ProspectiveRecorder, event: dict, now: datetime | None = None) -> dict[str, Any]:
    now = now or rec.now()
    rows = rec.checkpoint_status_rows(event, now)
    t48 = next((r for r in rows if r["checkpoint_id"] == "T0-48h"), None)
    status = (t48 or {}).get("status") or "UNKNOWN"
    mapped = "NOT_YET_DUE" if status == "FUTURE" else status
    return {
        "scheduled_utc": (t48 or {}).get("checkpoint_utc") or (event.get("checkpoints") or {}).get("T0-48h"),
        "is_open": status == "DUE",
        "status": mapped,
        "raw_status": status,
    }


def expected_components(event: dict) -> list[str]:
    fam = event.get("event_family")
    if fam == "CPI":
        return list(R.CPI_SERIES)
    if fam == "EMPLOYMENT_SITUATION":
        return list(R.EMP_SERIES)
    if fam == "FOMC":
        return list(R.FOMC_SERIES)
    return []


def build_components(event: dict, displayed: dict[str, dict] | None) -> dict[str, dict]:
    displayed = displayed or {}
    series_names = expected_components(event)
    if not series_names:
        raise IntakeClosed("no prospective series schema for family %s" % event.get("event_family"))
    out: dict[str, dict[str, Any]] = {}
    for series in series_names:
        row = displayed.get(series) or {}
        consensus_raw = row.get("consensus_raw")
        forecast_raw = row.get("forecast_raw")
        previous_raw = row.get("previous_raw")
        missing = consensus_raw in (None, "")
        if event.get("event_family") == "EMPLOYMENT_SITUATION" and series == "nonfarm_payroll_change":
            consensus_value = None if missing else A.normalize_jobs_value(consensus_raw)
            previous_value = None if previous_raw in (None, "") else A.normalize_jobs_value(previous_raw)
            forecast_value = None if forecast_raw in (None, "") else A.normalize_jobs_value(forecast_raw)
            unit = "persons"
        else:
            consensus_value = None if missing else A.normalize_percent_value(consensus_raw)
            previous_value = None if previous_raw in (None, "") else A.normalize_percent_value(previous_raw)
            forecast_value = None if forecast_raw in (None, "") else A.normalize_percent_value(forecast_raw)
            unit = "percent"
        if missing and consensus_value is not None:
            raise IntakeClosed("blank consensus must not receive a numeric value")
        if missing and forecast_value is not None and consensus_value == forecast_value:
            raise IntakeClosed("Forecast cannot substitute Consensus")
        if (not missing) and forecast_value is not None and consensus_value == forecast_value:
            substituted = False
        else:
            substituted = False
        if missing:
            consensus_value = None
        out[series] = {
            "previous_raw": previous_raw,
            "previous_value": previous_value,
            "consensus_raw": None if missing else consensus_raw,
            "consensus_value": consensus_value,
            "consensus_value_quality": "NOT_AVAILABLE" if missing else "PRESENT",
            "forecast_raw": forecast_raw,
            "forecast_value": forecast_value,
            "forecast_semantics": "PROVIDER_FORECAST_NOT_CONSENSUS",
            "te_forecast_raw": forecast_raw,
            "te_forecast_value": forecast_value,
            "te_forecast_semantics": "PROVIDER_FORECAST_NOT_CONSENSUS",
            "unit": unit,
            "consensus_substituted_from_forecast": substituted,
            "consensus_substituted_from_te_forecast": substituted,
        }
    return out


def _checkpoint_status(rec: R.ProspectiveRecorder, event: dict, checkpoint_id: str) -> str:
    now = rec.now()
    for row in rec.checkpoint_status_rows(event, now):
        if row["checkpoint_id"] == checkpoint_id:
            return row["status"]
    return "UNKNOWN"


def _stage14():
    path = Path(__file__).with_name("_macro_prospective_te_retirement_stage14.py")
    spec = importlib.util.spec_from_file_location("macro_stage14_intake", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def intake(
    *,
    rec: R.ProspectiveRecorder,
    event_id: str,
    checkpoint: str,
    source_file: str | Path,
    dry_run: bool = False,
    times_fn: Callable[[Path], tuple[datetime, datetime]] | None = None,
    clock_skew_seconds: int = CLOCK_SKEW_TOLERANCE_SECONDS,
    displayed: dict[str, dict] | None = None,
    provider_id: str | None = None,
    source_name: str | None = None,
    source_url_if_applicable: str | None = None,
    source_publication_utc: str | None = None,
    source_updated_utc: str | None = None,
) -> dict[str, Any]:
    event = rec.event_by_id(event_id)
    if event is None:
        raise IntakeClosed("event is not registered: %s" % event_id)
    checkpoint_id = normalize_checkpoint(checkpoint)
    if checkpoint_id not in (event.get("checkpoints") or {}):
        raise IntakeClosed("checkpoint %s is not registered on %s" % (checkpoint_id, event_id))
    if checkpoint_id == "T0":
        raise IntakeClosed("T0 is not a pre-release consensus checkpoint")
    src = Path(source_file)
    if not src.exists() or not src.is_file():
        raise IntakeClosed("EVIDENCE_FILE_NOT_FOUND: %s" % src)
    ext = src.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise IntakeClosed("unsupported evidence extension: %s" % ext)
    source_path = str(src.resolve())
    source_sha = sha256_file(src)
    source_bytes = src.stat().st_size
    created, modified = filesystem_times(src, times_fn)
    intake_utc = rec.now().astimezone(UTC).replace(microsecond=0)
    provenance = "FILESYSTEM_CTIME"
    observed_at = created
    if created.year < 1990:
        provenance = "INSUFFICIENT"
        observed_at = None
    if observed_at is not None and (observed_at - intake_utc).total_seconds() > clock_skew_seconds:
        raise IntakeClosed("observed_at_utc is implausibly in the future relative to intake")
    t0 = R.parse_utc(event["scheduled_release_utc"])
    scheduled = R.parse_utc(event["checkpoints"][checkpoint_id])
    assert t0 and scheduled
    associated = None
    pre_release = False
    observation_eligible = False
    reasons: list[str] = []
    observed_iso = to_iso(observed_at) if observed_at is not None else None
    if observed_at is None:
        reasons.append("TIMESTAMP_PROVENANCE=INSUFFICIENT")
    else:
        pre_release = observed_at < t0
        associated = R.associated_checkpoint_id(event, observed_at)
        if not pre_release:
            reasons.append("PRE_RELEASE_ELIGIBLE=NO observed_at_utc >= T0")
        if associated is None and pre_release:
            reasons.append("observed_at_utc is before the first checkpoint; not silently mapped")
        if associated is not None and associated != checkpoint_id:
            reasons.append("CHECKPOINT_MISMATCH associated=%s requested=%s" % (associated, checkpoint_id))
        if associated == checkpoint_id and pre_release:
            observation_eligible = True
    existing_same_sha = find_by_sha(rec, source_sha)
    review_required = False
    already = False
    reused_row = None
    for row in existing_same_sha:
        if row.get("macro_event_id") == event_id and row.get("checkpoint_id") == checkpoint_id:
            already = True
            reused_row = row
        elif row.get("macro_event_id") == event_id and row.get("checkpoint_id") != checkpoint_id:
            review_required = True
            observation_eligible = False
            reasons.append("same SHA-256 submitted under a different checkpoint; review required")
    ck_status = _checkpoint_status(rec, event, checkpoint_id)
    if ck_status == "CAPTURED" and not already:
        observation_eligible = False
        reasons.append("checkpoint already CAPTURED; different evidence cannot overwrite")
    if ck_status == "MISSED_NOT_OBSERVED":
        observation_eligible = False
        reasons.append(
            "LATE_DISCOVERY_NOT_REDESIGNED: MISSED_NOT_OBSERVED is derived, not a sealed state; "
            "Stage 13 will not convert a missed checkpoint into an observation"
        )
    dest_name = archive_filename(event_id, checkpoint_id, source_sha, ext)
    dest = intake_dir(rec) / dest_name
    intended = str(dest).replace("\\", "/")
    capture_delay = None
    if observed_at is not None:
        capture_delay = int((observed_at - scheduled).total_seconds())
    receipt = {
        "status": "INSPECTED" if dry_run else "SECURED",
        "event_id": event_id,
        "checkpoint_id": checkpoint_id,
        "source_file": source_path,
        "source_file_created_utc": to_iso(created),
        "source_file_modified_utc": to_iso(modified),
        "intake_utc": to_iso(intake_utc),
        "observed_at_utc": observed_iso,
        "timestamp_provenance": provenance if observed_at is not None else "INSUFFICIENT",
        "checkpoint_scheduled_utc": event["checkpoints"][checkpoint_id],
        "capture_delay_seconds": capture_delay,
        "pre_release_eligible": bool(pre_release),
        "observation_eligible": bool(observation_eligible),
        "source_sha256": source_sha,
        "archived_sha256": None if dry_run else source_sha,
        "byte_length": source_bytes,
        "archived_path": intended,
        "evidence_id": evidence_id(event_id, checkpoint_id, source_sha),
        "already_existed": already,
        "review_required": review_required,
        "reasons": reasons,
        "http_requests": 0,
        "dry_run": dry_run,
        "associated_checkpoint_id": associated,
        "checkpoint_status": ck_status,
        "provider_id": provider_id,
        "source_name": source_name,
        "source_url_if_applicable": source_url_if_applicable,
        "source_publication_utc": source_publication_utc,
        "source_updated_utc": source_updated_utc,
    }
    if dry_run:
        receipt["status"] = "DRY_RUN"
        return receipt
    if review_required and existing_same_sha and not already:
        prior = existing_same_sha[0]
        receipt.update(
            {
                "status": "REVIEW_REQUIRED",
                "already_existed": True,
                "archived_sha256": prior.get("archived_sha256"),
                "archived_path": prior.get("archived_path"),
                "evidence_id": prior.get("evidence_id"),
            }
        )
        return receipt
    if already and reused_row is not None:
        archived = Path(reused_row["archived_path"])
        if archived.exists():
            archived_sha = sha256_file(archived)
            if archived_sha != source_sha or archived.stat().st_size != source_bytes:
                raise IntakeClosed("existing archived evidence hash/length mismatch")
            receipt.update(
                {
                    "status": "ALREADY_EXISTS",
                    "archived_sha256": archived_sha,
                    "archived_path": reused_row["archived_path"],
                    "evidence_id": reused_row["evidence_id"],
                    "observed_at_utc": reused_row.get("observed_at_utc"),
                    "intake_utc": reused_row.get("intake_utc"),
                    "source_file_created_utc": reused_row.get("source_file_created_utc"),
                    "source_file_modified_utc": reused_row.get("source_file_modified_utc"),
                    "observation_eligible": reused_row.get("observation_eligible"),
                    "pre_release_eligible": reused_row.get("pre_release_eligible"),
                }
            )
            if displayed:
                try:
                    receipt["value_ingest"] = ingest_values(
                        rec=rec,
                        event_id=event_id,
                        checkpoint=checkpoint_id,
                        evidence_ref=reused_row["evidence_id"],
                        displayed=displayed,
                        provider_id=provider_id,
                    )
                except (IntakeClosed, ValueError) as exc:
                    receipt["value_ingest_error"] = str(exc)
            return receipt
    if dest.exists():
        if sha256_file(dest) != source_sha:
            raise IntakeClosed("archive destination exists with different bytes")
        already = True
    else:
        before_src = sha256_file(src)
        atomic_copy(src, dest)
        if sha256_file(src) != before_src:
            dest.unlink(missing_ok=True)
            raise IntakeClosed("original source file changed during copy")
    archived_sha = sha256_file(dest)
    archived_bytes = dest.stat().st_size
    if archived_sha != source_sha or archived_bytes != source_bytes:
        raise IntakeClosed("archived SHA-256 or byte length does not match source")
    row = {
        "evidence_id": receipt["evidence_id"],
        "macro_event_id": event_id,
        "checkpoint_id": checkpoint_id,
        "source_path": source_path,
        "source_filename": src.name,
        "source_sha256": source_sha,
        "archived_sha256": archived_sha,
        "byte_length": source_bytes,
        "archived_path": str(dest).replace("\\", "/"),
        "source_file_created_utc": to_iso(created),
        "source_file_modified_utc": to_iso(modified),
        "intake_utc": to_iso(intake_utc),
        "observed_at_utc": observed_iso,
        "timestamp_provenance": receipt["timestamp_provenance"],
        "timestamp_basis": TIMESTAMP_BASIS,
        "pre_release_eligible": bool(pre_release),
        "observation_eligible": bool(observation_eligible),
        "associated_checkpoint_id": associated,
        "reasons": reasons,
        "extension": ext,
        "http_requests": 0,
        "provider_id": provider_id,
        "source_name": source_name,
        "source_artifact": dest_name,
        "source_url_if_applicable": source_url_if_applicable,
        "source_publication_utc": source_publication_utc,
        "source_updated_utc": source_updated_utc,
    }
    if not already:
        append_index(rec, row)
        meta = dest.with_name(dest.name + ".meta.json")
        meta.write_bytes((json.dumps(row, indent=2) + "\n").encode("utf-8"))
    receipt["archived_sha256"] = archived_sha
    receipt["already_existed"] = already
    if displayed:
        try:
            receipt["value_ingest"] = ingest_values(
                rec=rec,
                event_id=event_id,
                checkpoint=checkpoint_id,
                evidence_ref=receipt["evidence_id"],
                displayed=displayed,
                provider_id=provider_id,
            )
        except (IntakeClosed, ValueError) as exc:
            receipt["value_ingest_error"] = str(exc)
    return receipt


def ingest_values(
    *,
    rec: R.ProspectiveRecorder,
    event_id: str,
    checkpoint: str,
    evidence_ref: str,
    displayed: dict[str, dict],
    provider_id: str | None = None,
) -> dict[str, Any]:
    event = rec.event_by_id(event_id)
    if event is None:
        raise IntakeClosed("event is not registered: %s" % event_id)
    checkpoint_id = normalize_checkpoint(checkpoint)
    ev = find_by_id(rec, evidence_ref)
    if ev is None:
        raise IntakeClosed("evidence reference not found: %s" % evidence_ref)
    if ev.get("macro_event_id") != event_id or ev.get("checkpoint_id") != checkpoint_id:
        raise IntakeClosed("evidence reference does not match event/checkpoint")
    if ev.get("observation_eligible") is not True:
        raise IntakeClosed("evidence is not observation-eligible")
    observed_at = ev.get("observed_at_utc")
    if not observed_at:
        raise IntakeClosed("evidence lacks approved observed_at_utc")
    if observed_at == ev.get("intake_utc"):
        if ev.get("timestamp_provenance") != "FILESYSTEM_CTIME":
            raise IntakeClosed("intake_utc cannot become observed_at_utc")
    if observed_at == ev.get("checkpoint_scheduled_utc") and ev.get("timestamp_provenance") != "FILESYSTEM_CTIME":
        raise IntakeClosed("checkpoint scheduled time cannot become observed_at_utc")
    t0 = R.parse_utc(event["scheduled_release_utc"])
    obs = R.parse_utc(observed_at)
    assert t0 and obs
    if obs >= t0:
        raise IntakeClosed("observed_at_utc >= T0 cannot become consensus")
    associated = R.associated_checkpoint_id(event, obs)
    if associated != checkpoint_id:
        raise IntakeClosed("observed_at_utc does not associate to requested checkpoint")
    S14 = _stage14()
    try:
        resolved = S14.resolve_manual_provider(rec, provider_id)
    except S14.ProviderClosed as exc:
        raise IntakeClosed(str(exc)) from exc
    source_id = resolved["provider_id"]
    src = resolved["source"]
    provider_name = src.get("publisher") or source_id
    components = build_components(event, displayed)
    primary = expected_components(event)[0]
    primary_row = components[primary]
    artifact = Path(ev["archived_path"]).read_bytes()
    suffix = ev.get("extension", "").lstrip(".") or "bin"
    calendar_fields = {
        "collection_method": "MANUAL_SCREEN_OBSERVATION",
        "provider": provider_name,
        "provider_id": source_id,
        "source_name": ev.get("source_name") or provider_name,
        "source_artifact": ev.get("source_artifact") or ev.get("source_filename"),
        "source_url_if_applicable": ev.get("source_url_if_applicable"),
        "source_publication_utc": ev.get("source_publication_utc"),
        "source_updated_utc": ev.get("source_updated_utc"),
        "displayed_columns": ["Actual", "Previous", "Consensus", "Forecast"],
        "consensus_field_semantics": "SURVEY_CONSENSUS",
        "forecast_field_semantics": "PROVIDER_FORECAST_NOT_CONSENSUS",
        "evidence_id": ev["evidence_id"],
        "evidence_sha256": ev["source_sha256"],
        "evidence_timestamp_basis": ev.get("timestamp_basis") or TIMESTAMP_BASIS,
        "components": components,
    }
    out = rec.ingest_observation(
        macro_event_id=event_id,
        source_id=source_id,
        series_name=primary,
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=artifact,
        artifact_suffix=suffix,
        observed_at_utc=observed_at,
        checkpoint_id=checkpoint_id,
        forecast_value=primary_row["consensus_value"],
        value_quality=primary_row["consensus_value_quality"],
        unit=primary_row["unit"],
        retrieval_method="manual",
        observation_kind="FORECASTER",
        calendar_fields=calendar_fields,
        notes="Stage 13/14 manual value ingest referencing secured local evidence. Provider identity is explicit. No OCR.",
        provider_name=provider_name,
        retrieval_utc=ev.get("intake_utc"),
        allow_autonomous=False,
    )
    return {
        "status": out.get("status"),
        "observation_id": (out.get("observation") or {}).get("observation_id") or out.get("observation_id"),
        "observed_at_utc": observed_at,
        "provider_id": source_id,
        "components": components,
    }


def format_receipt(receipt: dict[str, Any]) -> str:
    lines = [
        "MANUAL EVIDENCE SECURED",
        "-----------------------",
        "EVENT_ID:",
        str(receipt.get("event_id") or ""),
        "CHECKPOINT:",
        str(receipt.get("checkpoint_id") or ""),
        "SOURCE_FILE:",
        str(receipt.get("source_file") or ""),
        "SOURCE_FILE_CREATED_UTC:",
        str(receipt.get("source_file_created_utc") or ""),
        "SOURCE_FILE_MODIFIED_UTC:",
        str(receipt.get("source_file_modified_utc") or ""),
        "INTAKE_UTC:",
        str(receipt.get("intake_utc") or ""),
        "OBSERVED_AT_UTC:",
        str(receipt.get("observed_at_utc") or ""),
        "TIMESTAMP_PROVENANCE:",
        str(receipt.get("timestamp_provenance") or ""),
        "CHECKPOINT_SCHEDULED_UTC:",
        str(receipt.get("checkpoint_scheduled_utc") or ""),
        "CAPTURE_DELAY_SECONDS:",
        str(receipt.get("capture_delay_seconds") if receipt.get("capture_delay_seconds") is not None else ""),
        "PRE_RELEASE_ELIGIBLE:",
        "YES" if receipt.get("pre_release_eligible") else "NO",
        "OBSERVATION_ELIGIBLE:",
        "YES" if receipt.get("observation_eligible") else "NO",
        "SOURCE_SHA256:",
        str(receipt.get("source_sha256") or ""),
        "ARCHIVED_SHA256:",
        str(receipt.get("archived_sha256") or ""),
        "BYTE_LENGTH:",
        str(receipt.get("byte_length") or ""),
        "ARCHIVED_PATH:",
        str(receipt.get("archived_path") or ""),
        "EVIDENCE_ID:",
        str(receipt.get("evidence_id") or ""),
        "PROVIDER_ID:",
        str(receipt.get("provider_id") or "(none; required before value ingest)"),
        "SOURCE_NAME:",
        str(receipt.get("source_name") or ""),
        "ALREADY_EXISTED:",
        "YES" if receipt.get("already_existed") else "NO",
        "HTTP_REQUESTS:",
        "0",
        "",
    ]
    if receipt.get("reasons"):
        lines.extend(["NOTES:", "; ".join(receipt["reasons"]), ""])
    if receipt.get("value_ingest_error"):
        lines.extend(["VALUE_INGEST:", "FAILED", str(receipt["value_ingest_error"]), ""])
    elif receipt.get("value_ingest"):
        lines.extend(["VALUE_INGEST:", str(receipt["value_ingest"].get("status")), ""])
    return "\n".join(lines)


def readiness_check(rec: R.ProspectiveRecorder | None = None, event_id: str = "usd_cpi_2026-10-14") -> dict[str, Any]:
    rec = rec or R.ProspectiveRecorder(PROBE_DIR)
    event = rec.event_by_id(event_id)
    now = rec.now()
    t48 = describe_t48h(rec, event, now) if event else {"scheduled_utc": None, "is_open": False, "status": "UNREGISTERED"}
    evidence = rec.root / EVIDENCE_DIR_NAME
    cfg = rec.load_config()
    return {
        "event_registered": event is not None,
        "t0_utc": None if event is None else event.get("scheduled_release_utc"),
        "t48h_scheduled_utc": t48.get("scheduled_utc"),
        "t48h_is_open": t48.get("is_open"),
        "t48h_status": t48.get("status"),
        "checkpoint_currently_due": t48.get("raw_status") == "DUE" if event else False,
        "manual_intake_command": "python -m reports.decision_quality.macro_prospective_cli evidence-intake",
        "manual_value_ingest_command": "python -m reports.decision_quality.macro_prospective_cli evidence-ingest-values",
        "evidence_directory": str(evidence).replace("\\", "/"),
        "evidence_directory_writable": evidence.exists() and os.access(evidence, os.W_OK),
        "consensus_schema": expected_components(event) if event else [],
        "schema_complete": bool(event and expected_components(event)),
        "scheduler_installed": (rec.root / "scheduler" / "windows_task_installed.json").exists(),
        "external_sources_disabled": cfg.get("FORWARD_CONSENSUS_COLLECTION_ENABLED") is False,
        "forward_enabled": cfg.get("FORWARD_CONSENSUS_COLLECTION_ENABLED"),
        "bls_automation": cfg.get("OFFICIAL_BLS_FIRST_PRINT_ENABLED"),
        "trading_economics_currently_live": False,
        "approved_consensus_provider_available": False,
        "provider_status": (event or {}).get("consensus_provider_status") or "PROVIDER_PENDING",
        "consensus_provider_id": (event or {}).get("consensus_provider_id"),
        "manual_collection": (event or {}).get("manual_collection") or "WAITING_FOR_APPROVED_PROVIDER",
        "explicit_provider_id_required": True,
        "http_requests": 0,
    }
