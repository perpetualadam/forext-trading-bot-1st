"""Stage 10 real T-12h ingest tests. Fixtures/mocks only. No live evidence. No network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_IPATH = Path("reports/decision_quality/_macro_prospective_ingest_stage10.py")
_ISPEC = importlib.util.spec_from_file_location("macro_stage10_ingest", _IPATH)
S10 = importlib.util.module_from_spec(_ISPEC)
_ISPEC.loader.exec_module(S10)

S8 = S10.S8

_S9PATH = Path("reports/decision_quality/_macro_prospective_ingest_stage9.py")
_S9SPEC = importlib.util.spec_from_file_location("macro_stage9_for_stage10_tests", _S9PATH)
S9 = importlib.util.module_from_spec(_S9SPEC)
_S9SPEC.loader.exec_module(S9)

_RPATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_RSPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_s10", _RPATH)
R = importlib.util.module_from_spec(_RSPEC)
_RSPEC.loader.exec_module(R)

UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
CLOCK = datetime(2026, 10, 2, 0, 45, tzinfo=UTC)
OBS48 = "2026-09-30T12:31:17Z"
OBS24 = "2026-10-01T12:30:43Z"
OBS12 = "2026-10-02T00:30:36Z"
OBS12_EARLY = "2026-10-02T00:29:59Z"
EVIDENCE48 = b"FAKE_STAGE8_EVIDENCE_NOT_THE_REAL_MP4"
EVIDENCE24 = b"FAKE_STAGE9_EVIDENCE_NOT_THE_REAL_MP4"
EVIDENCE12 = b"FAKE_STAGE10_EVIDENCE_NOT_THE_REAL_MP4"


def _rec(tmp_path: Path):
    rec = R.bootstrap_store(tmp_path, clock=lambda: CLOCK)
    R.register_official_upcoming(rec, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    return rec


def _seed_t48(rec):
    return S8.ingest_stage8(
        rec=rec,
        evidence_bytes=EVIDENCE48,
        observed_at_utc=OBS48,
        evidence_filename="fixture_t48.mp4",
        evidence_sha256=hashlib.sha256(EVIDENCE48).hexdigest(),
        ingested_at_utc="2026-09-30T21:20:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
    )


def _seed_t24(rec):
    return S9.ingest_stage9(
        rec=rec,
        evidence_bytes=EVIDENCE24,
        observed_at_utc=OBS24,
        evidence_filename="fixture_t24.mp4",
        evidence_sha256=hashlib.sha256(EVIDENCE24).hexdigest(),
        ingested_at_utc="2026-10-01T21:20:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
    )


def _ingest_t12(rec, evidence=EVIDENCE12, observed_at=OBS12, filename="fixture_t12.mp4"):
    t48 = S10.checkpoint_rows(rec, "T0-48h")
    t24 = S10.checkpoint_rows(rec, "T0-24h")
    return S10.ingest_stage10(
        rec=rec,
        evidence_bytes=evidence,
        observed_at_utc=observed_at,
        evidence_filename=filename,
        evidence_sha256=hashlib.sha256(evidence).hexdigest(),
        ingested_at_utc="2026-10-02T00:45:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
        prior_t48=S10.fingerprint(t48[0] if t48 else None),
        prior_t24=S10.fingerprint(t24[0] if t24 else None),
    )


def test_priors_preserved_t36_not_backfilled_exactly_one_t12(tmp_path):
    rec = _rec(tmp_path)
    t48_out = _seed_t48(rec)
    t24_out = _seed_t24(rec)
    t48_before = json.dumps(t48_out["observation"], sort_keys=True)
    t24_before = json.dumps(t24_out["observation"], sort_keys=True)
    prior48 = S10.fingerprint(t48_out["observation"])
    prior24 = S10.fingerprint(t24_out["observation"])
    out = _ingest_t12(rec)
    assert out["status"] == "RECORDED"
    rows = [o for o in rec.load_observations() if o["macro_event_id"] == "usd_empsit_2026-10-02"]
    t48 = [o for o in rows if o["associated_checkpoint_id"] == "T0-48h"]
    t36 = [o for o in rows if o["associated_checkpoint_id"] == "T0-36h"]
    t24 = [o for o in rows if o["associated_checkpoint_id"] == "T0-24h"]
    t12 = [o for o in rows if o["associated_checkpoint_id"] == "T0-12h"]
    assert len(t48) == 1
    assert len(t36) == 0
    assert len(t24) == 1
    assert len(t12) == 1
    assert json.dumps(t48[0], sort_keys=True) == t48_before
    assert json.dumps(t24[0], sort_keys=True) == t24_before
    assert S10.fingerprint(t48[0]) == prior48
    assert S10.fingerprint(t24[0]) == prior24
    assert t12[0]["observed_at_utc"] == OBS12
    assert t12[0]["observed_at_utc"] >= "2026-10-02T00:30:00Z"
    assert t12[0]["observed_at_utc"] < "2026-10-02T12:30:00Z"
    t48_yoy = t48[0]["calendar_fields"]["components"]["average_hourly_earnings_yoy"]
    t24_yoy = t24[0]["calendar_fields"]["components"]["average_hourly_earnings_yoy"]
    assert t48_yoy["consensus_value"] is None
    assert t48_yoy["consensus_value_quality"] == "NOT_AVAILABLE"
    assert t24_yoy["consensus_value"] is None
    assert t24_yoy["consensus_value_quality"] == "NOT_AVAILABLE"
    cmp = S10.compare_vintages(
        t24[0], t12[0], ahe_yoy_label="CONSENSUS BECAME AVAILABLE AT T-12H"
    )
    assert cmp == {
        "nfp": "NO CHANGE",
        "unemployment": "NO CHANGE",
        "ahe_mom": "NO CHANGE",
        "ahe_yoy": "CONSENSUS BECAME AVAILABLE AT T-12H",
    }


def test_t12_values_ahe_yoy_present_and_not_forecast(tmp_path):
    rec = _rec(tmp_path)
    _seed_t48(rec)
    _seed_t24(rec)
    out = _ingest_t12(rec)
    obs = out["observation"]
    comps = obs["calendar_fields"]["components"]
    assert comps["nonfarm_payroll_change"]["consensus_value"] == 90000
    assert comps["nonfarm_payroll_change"]["consensus_raw"] == "90K"
    assert comps["unemployment_rate"]["consensus_value"] == pytest.approx(4.1)
    assert comps["average_hourly_earnings_mom"]["consensus_value"] == pytest.approx(0.3)
    yoy = comps["average_hourly_earnings_yoy"]
    assert yoy["consensus_value"] == pytest.approx(3.2)
    assert yoy["consensus_raw"] == "3.2%"
    assert yoy["consensus_value_quality"] == "PRESENT"
    assert yoy["te_forecast_value"] == pytest.approx(3.1)
    assert yoy["te_forecast_raw"] == "3.1%"
    assert yoy["consensus_value"] != yoy["te_forecast_value"]
    assert yoy["consensus_substituted_from_te_forecast"] is False
    assert obs["forecast_value"] == 90000
    assert obs["calendar_fields"]["consensus_field_semantics"] == "SURVEY_CONSENSUS"
    assert obs["calendar_fields"]["forecast_field_semantics"] == "PROVIDER_FORECAST_NOT_CONSENSUS"
    assert obs["expectation_type"] == "SURVEY_CONSENSUS"
    bad = json.loads(json.dumps(S10.DISPLAYED))
    bad["average_hourly_earnings_yoy"]["consensus_raw"] = "3.1%"
    with pytest.raises(S10.IngestClosed, match="must not overwrite Consensus"):
        S10.build_components(bad)
    missing = json.loads(json.dumps(S10.DISPLAYED))
    missing["average_hourly_earnings_yoy"]["consensus_raw"] = None
    with pytest.raises(S10.IngestClosed, match="must be present"):
        S10.build_components(missing)


def test_pre_checkpoint_and_post_t0_fail_closed(tmp_path):
    rec = _rec(tmp_path)
    _seed_t48(rec)
    _seed_t24(rec)
    with pytest.raises(S10.IngestClosed, match="not valid for T0-12h"):
        _ingest_t12(rec, observed_at=OBS12_EARLY)
    with pytest.raises(S10.IngestClosed, match="pre-T0"):
        _ingest_t12(rec, observed_at="2026-10-02T12:30:00Z")
    assert S10.is_valid_t12h(OBS12) is True
    assert S10.is_valid_t12h(OBS12_EARLY) is False
    assert [o["associated_checkpoint_id"] for o in rec.load_observations()] == ["T0-48h", "T0-24h"]


def test_duplicate_cannot_overwrite_and_sha256_stable(tmp_path):
    rec = _rec(tmp_path)
    _seed_t48(rec)
    _seed_t24(rec)
    first = _ingest_t12(rec)
    assert first["observation"]["raw_artifact_sha256"] == hashlib.sha256(EVIDENCE12).hexdigest()
    second = _ingest_t12(rec)
    assert first["status"] == "RECORDED"
    assert second["status"] == "ALREADY_EXISTS"
    t12 = S10.checkpoint_rows(rec, "T0-12h")
    assert len(t12) == 1
    assert t12[0]["observed_at_utc"] == OBS12
    with pytest.raises(R.RecorderConflict):
        _ingest_t12(rec, evidence=b"DIFFERENT_STAGE10_BYTES")
    again = S10.checkpoint_rows(rec, "T0-12h")
    assert len(again) == 1
    assert again[0]["observed_at_utc"] == OBS12
    assert again[0]["raw_artifact_sha256"] == first["observation"]["raw_artifact_sha256"]


def test_copied_bytes_retain_identical_sha256(tmp_path):
    src = tmp_path / "Screen Recording 2026-10-02 013036.mp4"
    payload = b"STAGE10_FAKE_COPY_BYTES"
    src.write_bytes(payload)
    dest = S8.copy_evidence_unchanged(src, tmp_path / "evidence")
    assert S8.sha256_file(src) == S8.sha256_file(dest)
    assert dest.read_bytes() == payload


def test_no_network_scheduler_and_production_unchanged(tmp_path):
    rec = _rec(tmp_path)
    before_cfg = (REAL_ROOT / "config.json").read_text(encoding="utf-8")
    before_reg = (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8")
    before_task = (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8")
    before_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8")
    _seed_t48(rec)
    _seed_t24(rec)
    _ingest_t12(rec)
    src = Path("reports/decision_quality/_macro_prospective_ingest_stage10.py").read_text(encoding="utf-8").lower()
    assert "urllib" not in src
    assert "requests" not in src
    assert "http.client" not in src
    assert "selenium" not in src
    assert "playwright" not in src
    assert "oanda" not in src
    for path in (
        Path("reports/decision_quality/_macro_prospective_scheduler.py"),
        Path("reports/decision_quality/macro_prospective_cli.py"),
        Path("forex_bot/bot_loop.py"),
    ):
        assert "_macro_prospective_ingest_stage10" not in path.read_text(encoding="utf-8")
    S8.assert_activation_unchanged()
    assert (REAL_ROOT / "config.json").read_text(encoding="utf-8") == before_cfg
    assert (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8") == before_reg
    assert (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8") == before_task
    after_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8")
    assert before_obs == after_obs
    cfg = json.loads(before_cfg)
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    te = next(s for s in json.loads(before_reg)["sources"] if s["source_id"] == "trading_economics")
    assert te["enabled"] is False
    assert te["automation_class"] != "APPROVED_AUTOMATION_READY"
