"""Stage 11: remaining pre-release employment vintages + official first-print gate.

Ingests only genuinely supported late pre-release checkpoints. Does not manufacture
T-6h/T-4h/T-2h. Does not treat T-90m or post-T0 evidence as a scheduled checkpoint.
Does not enable TE/FF/FORWARD. Official BLS first print is fail-closed unless the
existing adapter policy is already satisfied — Stage 11 does not improvise a live BLS fetch.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import timezone
from pathlib import Path
from typing import Any

_S10_PATH = Path(__file__).with_name("_macro_prospective_ingest_stage10.py")
_S10_SPEC = importlib.util.spec_from_file_location("macro_stage10_for_stage11", _S10_PATH)
S10 = importlib.util.module_from_spec(_S10_SPEC)
assert _S10_SPEC is not None and _S10_SPEC.loader is not None
_S10_SPEC.loader.exec_module(S10)

S8 = S10.S8
R = S10.R
UTC = timezone.utc
EVENT_ID = S10.EVENT_ID
T0_UTC = S10.T0_UTC
PROVIDER = S10.PROVIDER
COLLECTION_METHOD = S10.COLLECTION_METHOD
SOURCE_ID = S10.SOURCE_ID
PROBE_DIR = S10.PROBE_DIR
EVIDENCE_DIR_NAME = S10.EVIDENCE_DIR_NAME

SCHEDULED = {
    "T0-6h": "2026-10-02T06:30:00Z",
    "T0-4h": "2026-10-02T08:30:00Z",
    "T0-2h": "2026-10-02T10:30:00Z",
    "T0-1h": "2026-10-02T11:30:00Z",
    "T0-30m": "2026-10-02T12:00:00Z",
    "T0-15m": "2026-10-02T12:15:00Z",
    "T0-5m": "2026-10-02T12:25:00Z",
}
INGESTABLE = ("T0-1h", "T0-30m", "T0-15m", "T0-5m")
UNSUPPORTED_TO_MANUFACTURE = ("T0-6h", "T0-4h", "T0-2h")
NEXT_BOUNDARY = {
    "T0-6h": "2026-10-02T08:30:00Z",
    "T0-4h": "2026-10-02T10:30:00Z",
    "T0-2h": "2026-10-02T11:30:00Z",
    "T0-1h": "2026-10-02T12:00:00Z",
    "T0-30m": "2026-10-02T12:15:00Z",
    "T0-15m": "2026-10-02T12:25:00Z",
    "T0-5m": T0_UTC,
}
PRIOR_CHECKPOINTS = ("T0-48h", "T0-24h", "T0-12h")
T90M_LABEL = "T0-90m_SUPPLEMENTARY"
POST_RELEASE_LABEL = "POST_T0_CORROBORATION"

CANDIDATE_PATHS = (
    Path.home() / "Videos" / "Screen Recordings" / "Screen Recording 2026-10-02 120027.mp4",
    Path.home() / "Videos" / "Recording 2026-10-02 120030.mp4",
    Path.home() / "Videos" / "Screen Recordings" / "Screen Recording 2026-10-02 123044.mp4",
    Path.home() / "Videos" / "Recording 2026-10-02 123047.mp4",
    Path.home() / "Videos" / "Screen Recordings" / "Screen Recording 2026-10-02 130031.mp4",
    Path.home() / "Videos" / "Recording 2026-10-02 130034.mp4",
    Path.home() / "Videos" / "Screen Recordings" / "Screen Recording 2026-10-02 131635.mp4",
    Path.home() / "Videos" / "Recording 2026-10-02 131638.mp4",
    Path.home() / "Videos" / "Screen Recordings" / "Screen Recording 2026-10-02 133048.mp4",
    Path.home() / "Videos" / "Recording 2026-10-02 133051.mp4",
)


class IngestClosed(S10.IngestClosed):
    pass


def build_components(displayed: dict[str, dict] | None = None) -> dict[str, dict]:
    return S10.build_components(displayed)


def checkpoint_rows(rec: R.ProspectiveRecorder, checkpoint_id: str) -> list[dict]:
    return S10.checkpoint_rows(rec, checkpoint_id)


def fingerprint(obs: dict | None) -> dict[str, Any] | None:
    return S10.fingerprint(obs)


def is_t90m_supplementary(observed_at_utc: str) -> bool:
    obs = R.parse_utc(observed_at_utc)
    t2h = R.parse_utc(SCHEDULED["T0-2h"])
    t1h = R.parse_utc(SCHEDULED["T0-1h"])
    assert obs and t2h and t1h
    return t2h <= obs < t1h


def is_post_t0(observed_at_utc: str) -> bool:
    obs = R.parse_utc(observed_at_utc)
    t0 = R.parse_utc(T0_UTC)
    assert obs and t0
    return obs >= t0


def is_valid_for_checkpoint(observed_at_utc: str, checkpoint_id: str, event: dict | None = None) -> bool:
    if checkpoint_id not in INGESTABLE:
        return False
    if is_post_t0(observed_at_utc):
        return False
    if is_t90m_supplementary(observed_at_utc):
        return False
    obs = R.parse_utc(observed_at_utc)
    sched = R.parse_utc(SCHEDULED[checkpoint_id])
    nxt = R.parse_utc(NEXT_BOUNDARY[checkpoint_id])
    assert obs and sched and nxt
    if obs < sched or obs >= nxt:
        return False
    if event is not None:
        return R.associated_checkpoint_id(event, obs) == checkpoint_id
    return True


def classify_observed_at(observed_at_utc: str, event: dict | None = None) -> str | None:
    if is_post_t0(observed_at_utc):
        return POST_RELEASE_LABEL
    if is_t90m_supplementary(observed_at_utc):
        return T90M_LABEL
    obs = R.parse_utc(observed_at_utc)
    assert obs is not None
    if event is not None:
        return R.associated_checkpoint_id(event, obs)
    for cid in INGESTABLE:
        if is_valid_for_checkpoint(observed_at_utc, cid):
            return cid
    return None


def inspect_candidate(path: Path, event: dict | None = None) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {
            "path": str(path),
            "filename": path.name,
            "found": False,
            "sha256": None,
            "observed_at_utc": None,
            "classification": None,
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
        "classification": classify_observed_at(observed_at, event),
        "bytes": path.stat().st_size,
        "timestamp_basis": (
            "Windows filesystem creation time (st_ctime) truncated to UTC seconds; "
            "same Stage 8-10 provenance rule. Filename is corroboration only."
        ),
    }


def select_canonical_for_checkpoint(candidates: list[dict], checkpoint_id: str) -> dict | None:
    valid = [
        c
        for c in candidates
        if c.get("found") and c.get("classification") == checkpoint_id and c.get("observed_at_utc")
    ]
    if not valid:
        return None
    return sorted(valid, key=lambda c: (c["observed_at_utc"], c["filename"]))[0]


def official_first_print_gate() -> dict[str, Any]:
    """Read-only readiness. Does not enable flags or make a network request."""
    cfg = json.loads((PROBE_DIR / "config.json").read_text(encoding="utf-8"))
    blob = json.loads((PROBE_DIR / "source_registry" / "sources.json").read_text(encoding="utf-8"))
    bls = next(s for s in blob["sources"] if s["source_id"] == "bls_official")
    reasons = [
        "OFFICIAL_BLS_FIRST_PRINT_ENABLED is false",
        "bls_official.enabled is false",
        "bls_official.automation_class is UNSUPPORTED",
        "bls_official.automated_collection_permitted is unknown",
        "OfficialBlsFirstPrintAdapter.is_enabled also requires FORWARD_CONSENSUS_COLLECTION_ENABLED",
        "OfficialBlsFirstPrintAdapter.parse_bls_first_print extracts only NFP, not unemployment/AHE",
        "adapter URL is generic current-page https://www.bls.gov/news.release/empsit.htm, not a date-bound 2026-10-02 archive identity",
        "Stage 4 recorded direct BLS GET historically 403; no approved retry/bypass",
        "Stage 11 must not enable FORWARD, TE, or FF to unlock the adapter",
    ]
    ready = (
        cfg.get("OFFICIAL_BLS_FIRST_PRINT_ENABLED") is True
        and cfg.get("FORWARD_CONSENSUS_COLLECTION_ENABLED") is True
        and bls.get("enabled") is True
        and bls.get("automated_collection_permitted") is True
        and bls.get("automation_class") == "APPROVED_AUTOMATION_READY"
    )
    return {
        "ready": ready,
        "official_source_verified": False,
        "requests": 0,
        "captured": False,
        "reasons": reasons,
        "bls_enabled": bls.get("enabled"),
        "bls_class": bls.get("automation_class"),
        "forward_enabled": cfg.get("FORWARD_CONSENSUS_COLLECTION_ENABLED"),
        "bls_flag": cfg.get("OFFICIAL_BLS_FIRST_PRINT_ENABLED"),
        "adapter_url": S8.A.BLS_EMPSIT_HTML,
    }


def strict_final_surprise(*, t5m: dict | None, first_prints: dict[str, dict] | None) -> dict[str, Any]:
    if t5m is None or (t5m.get("associated_checkpoint_id") or t5m.get("checkpoint_id")) != "T0-5m":
        return {
            "available": False,
            "reason": "strict final-consensus surprise requires a genuine T-5m observation; later/earlier vintages are not substituted",
            "nfp": None,
            "unemployment_pp": None,
            "ahe_mom_pp": None,
            "ahe_yoy_pp": None,
        }
    first_prints = first_prints or {}
    comps = (t5m.get("calendar_fields") or {}).get("components") or {}
    mapping = {
        "nfp": ("nonfarm_payroll_change", "nfp"),
        "unemployment_pp": ("unemployment_rate", "unemployment"),
        "ahe_mom_pp": ("average_hourly_earnings_mom", "ahe_mom"),
        "ahe_yoy_pp": ("average_hourly_earnings_yoy", "ahe_yoy"),
    }
    out: dict[str, Any] = {"available": True, "reason": None}
    for key, (series, actual_key) in mapping.items():
        consensus = (comps.get(series) or {}).get("consensus_value")
        actual_row = first_prints.get(actual_key) or first_prints.get(series) or {}
        actual = actual_row.get("actual_first_print")
        if consensus is None or actual is None:
            out["available"] = False
            out[key] = None
            out["reason"] = "surprise requires both T-5m consensus and official first print for every target series"
            continue
        out[key] = float(actual) - float(consensus)
    if out["available"] is False:
        for key in mapping:
            out[key] = None
    return out


def _validate_timestamp(rec: R.ProspectiveRecorder, observed_at_utc: str, checkpoint_id: str) -> str:
    if is_t90m_supplementary(observed_at_utc):
        raise IngestClosed("T-90m evidence cannot become a scheduled checkpoint")
    if is_post_t0(observed_at_utc):
        raise IngestClosed("post-T0 evidence cannot become pre-release consensus")
    if checkpoint_id not in INGESTABLE:
        raise IngestClosed("checkpoint %s cannot be manufactured" % checkpoint_id)
    event = rec.event_by_id(EVENT_ID)
    if event is None:
        raise IngestClosed("event %s is not registered" % EVENT_ID)
    if event.get("scheduled_release_utc") != T0_UTC:
        raise IngestClosed("T0 mismatch")
    if event.get("checkpoints", {}).get(checkpoint_id) != SCHEDULED[checkpoint_id]:
        raise IngestClosed("%s checkpoint mismatch" % checkpoint_id)
    if not is_valid_for_checkpoint(observed_at_utc, checkpoint_id, event):
        raise IngestClosed("observed_at_utc is not valid for %s" % checkpoint_id)
    associated = R.associated_checkpoint_id(event, R.parse_utc(observed_at_utc))
    if associated != checkpoint_id:
        raise IngestClosed("observed_at_utc does not associate to %s (got %s)" % (checkpoint_id, associated))
    return associated


def ingest_stage11_checkpoint(
    *,
    rec: R.ProspectiveRecorder,
    checkpoint_id: str,
    evidence_bytes: bytes,
    observed_at_utc: str,
    evidence_filename: str,
    evidence_sha256: str,
    ingested_at_utc: str,
    evidence_timestamp_basis: str,
    artifact_suffix: str = "mp4",
    priors: dict[str, dict | None] | None = None,
) -> dict:
    if priors is None:
        priors = {cid: fingerprint(checkpoint_rows(rec, cid)[0] if checkpoint_rows(rec, cid) else None) for cid in PRIOR_CHECKPOINTS}
    t36_before = len(checkpoint_rows(rec, "T0-36h"))
    associated = _validate_timestamp(rec, observed_at_utc, checkpoint_id)
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
        "Stage 11 MANUAL_SCREEN_OBSERVATION of Trading Economics Economic Calendar at %s. "
        "Consensus is the displayed survey-average Consensus column, not TE Forecast. "
        "AHE YoY Consensus is 3.2%% and remains distinct from TE Forecast 3.1%%. "
        "Earlier missing AHE YoY vintages were not rewritten. T-36h was not backfilled."
    ) % checkpoint_id
    out = rec.ingest_observation(
        macro_event_id=EVENT_ID,
        source_id=SOURCE_ID,
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=evidence_bytes,
        artifact_suffix=artifact_suffix,
        observed_at_utc=observed_at_utc,
        checkpoint_id=checkpoint_id,
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
        _assert_priors(rec, priors, t36_before)
        return out
    obs = out.get("observation") or {}
    if obs.get("associated_checkpoint_id") != associated:
        raise IngestClosed("checkpoint association changed during ingest")
    if obs.get("observed_at_utc") != observed_at_utc:
        raise IngestClosed("observed_at_utc was rewritten")
    _assert_priors(rec, priors, t36_before)
    rows = checkpoint_rows(rec, checkpoint_id)
    if len(rows) != 1:
        raise IngestClosed("expected exactly one %s observation, got %s" % (checkpoint_id, len(rows)))
    return out


def _assert_priors(rec: R.ProspectiveRecorder, priors: dict[str, dict | None], t36_before: int) -> None:
    for cid, prior in priors.items():
        rows = checkpoint_rows(rec, cid)
        after = fingerprint(rows[0] if rows else None)
        if prior is not None and after != prior:
            raise IngestClosed("%s observation changed" % cid)
    if len(checkpoint_rows(rec, "T0-36h")) != t36_before:
        raise IngestClosed("T-36h was backfilled")


def _copy_if_needed(src: Path, dest_dir: Path, sha256: str) -> Path:
    dest = S8.copy_evidence_unchanged(src, dest_dir)
    if S8.sha256_file(dest) != sha256:
        raise IngestClosed("copied evidence hash mismatch")
    return dest


def run_live() -> dict:
    S8.assert_activation_unchanged()
    gate = official_first_print_gate()
    rec = R.ProspectiveRecorder(PROBE_DIR)
    event = rec.event_by_id(EVENT_ID)
    if event is None:
        raise IngestClosed("event missing")
    priors = {}
    for cid in PRIOR_CHECKPOINTS:
        rows = checkpoint_rows(rec, cid)
        if not rows:
            raise IngestClosed("%s observation is missing; Stage 11 will not proceed" % cid)
        priors[cid] = fingerprint(rows[0])
    inspected = [inspect_candidate(p, event) for p in CANDIDATE_PATHS]
    created = []
    skipped = []
    ingested_at = R.to_utc_iso(rec.now())
    dest_dir = rec.root / EVIDENCE_DIR_NAME
    for cid in INGESTABLE:
        existing = [
            o
            for o in checkpoint_rows(rec, cid)
            if o.get("expectation_type") == "SURVEY_CONSENSUS"
        ]
        if existing:
            skipped.append({"checkpoint_id": cid, "reason": "already captured"})
            continue
        canonical = select_canonical_for_checkpoint(inspected, cid)
        if canonical is None:
            skipped.append(
                {
                    "checkpoint_id": cid,
                    "reason": (
                        "T-5m screenshot not found in Stage 8-10 evidence locations; timestamp provenance cannot be established"
                        if cid == "T0-5m"
                        else "no valid evidence for checkpoint"
                    ),
                }
            )
            continue
        src = Path(canonical["path"])
        dest = _copy_if_needed(src, dest_dir, canonical["sha256"])
        evidence_bytes = dest.read_bytes()
        if S8.sha256_bytes(evidence_bytes) != canonical["sha256"]:
            raise IngestClosed("imported evidence bytes hash mismatch")
        out = ingest_stage11_checkpoint(
            rec=rec,
            checkpoint_id=cid,
            evidence_bytes=evidence_bytes,
            observed_at_utc=canonical["observed_at_utc"],
            evidence_filename=canonical["filename"],
            evidence_sha256=canonical["sha256"],
            ingested_at_utc=ingested_at,
            evidence_timestamp_basis=canonical["timestamp_basis"],
            artifact_suffix="mp4",
            priors=priors,
        )
        created.append(out)
    supplementary = []
    for label, predicate in (
        (T90M_LABEL, lambda c: c.get("classification") == T90M_LABEL),
        (POST_RELEASE_LABEL, lambda c: c.get("classification") == POST_RELEASE_LABEL),
    ):
        group = [c for c in inspected if c.get("found") and predicate(c)]
        if not group:
            continue
        canonical = sorted(group, key=lambda c: (c["observed_at_utc"], c["filename"]))[0]
        dest = _copy_if_needed(Path(canonical["path"]), dest_dir, canonical["sha256"])
        supplementary.append(
            {
                "label": label,
                "filename": canonical["filename"],
                "imported_path": str(dest).replace("\\", "/"),
                "sha256": canonical["sha256"],
                "observed_at_utc": canonical["observed_at_utc"],
                "observation_created": False,
            }
        )
    S8.assert_activation_unchanged()
    _assert_priors(rec, priors, 0)
    t5m_rows = checkpoint_rows(rec, "T0-5m")
    surprise = strict_final_surprise(t5m=t5m_rows[0] if t5m_rows else None, first_prints={})
    meta = {
        "candidates": inspected,
        "created_checkpoints": [((c.get("observation") or {}).get("checkpoint_id")) for c in created],
        "skipped": skipped,
        "supplementary": supplementary,
        "official_first_print_gate": gate,
        "strict_final_surprise": surprise,
        "priors": priors,
    }
    (dest_dir / "stage11_evidence.meta.json").write_bytes(
        (json.dumps(meta, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    )
    return {
        "status": "RECORDED" if created else "NO_NEW_OBSERVATIONS",
        "created": created,
        "skipped": skipped,
        "supplementary": supplementary,
        "candidates": inspected,
        "official_first_print_gate": gate,
        "strict_final_surprise": surprise,
        "priors": priors,
        "evidence_meta": meta,
    }


if __name__ == "__main__":
    result = run_live()
    print("status=%s" % result.get("status"))
    print("created=%s" % [((c.get("observation") or {}).get("checkpoint_id"), (c.get("observation") or {}).get("observation_id"), (c.get("observation") or {}).get("observed_at_utc")) for c in result.get("created") or []])
    print("skipped=%s" % result.get("skipped"))
    print("supplementary=%s" % result.get("supplementary"))
    print("bls_gate_ready=%s" % (result.get("official_first_print_gate") or {}).get("ready"))
    print("surprise=%s" % result.get("strict_final_surprise"))
