"""Stage 9 real T-24h ingest tests. Fixtures/mocks only. No live evidence. No network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_IPATH = Path("reports/decision_quality/_macro_prospective_ingest_stage9.py")
_ISPEC = importlib.util.spec_from_file_location("macro_stage9_ingest", _IPATH)
S9 = importlib.util.module_from_spec(_ISPEC)
_ISPEC.loader.exec_module(S9)

S8 = S9.S8

_RPATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_RSPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_s9", _RPATH)
R = importlib.util.module_from_spec(_RSPEC)
_RSPEC.loader.exec_module(R)

UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
CLOCK = datetime(2026, 10, 1, 21, 20, tzinfo=UTC)
OBS48 = "2026-09-30T12:31:17Z"
OBS24 = "2026-10-01T12:30:43Z"
OBS24_LATER = "2026-10-01T12:30:54Z"
OBS24_EARLY = "2026-10-01T12:29:59Z"
EVIDENCE48 = b"FAKE_STAGE8_EVIDENCE_NOT_THE_REAL_MP4"
EVIDENCE24 = b"FAKE_STAGE9_EVIDENCE_NOT_THE_REAL_MP4"


def _rec(tmp_path: Path):
    rec = R.bootstrap_store(tmp_path, clock=lambda: CLOCK)
    R.register_official_upcoming(rec, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    return rec


def _seed_t48(rec):
    digest = hashlib.sha256(EVIDENCE48).hexdigest()
    return S8.ingest_stage8(
        rec=rec,
        evidence_bytes=EVIDENCE48,
        observed_at_utc=OBS48,
        evidence_filename="fixture_t48.mp4",
        evidence_sha256=digest,
        ingested_at_utc="2026-09-30T21:20:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
    )


def _ingest_t24(rec, evidence=EVIDENCE24, observed_at=OBS24, filename="fixture_t24.mp4"):
    digest = hashlib.sha256(evidence).hexdigest()
    return S9.ingest_stage9(
        rec=rec,
        evidence_bytes=evidence,
        observed_at_utc=observed_at,
        evidence_filename=filename,
        evidence_sha256=digest,
        ingested_at_utc="2026-10-01T21:20:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
        prior_t48=S9.t48_fingerprint(rec),
    )


def _cand(filename, observed_at, valid, found=True, digest="aa"):
    return {
        "path": "/tmp/" + filename,
        "filename": filename,
        "found": found,
        "sha256": digest,
        "observed_at_utc": observed_at,
        "valid_for_t24h": valid,
    }


def test_t48_preserved_t36_not_backfilled_exactly_one_t24(tmp_path):
    rec = _rec(tmp_path)
    first = _seed_t48(rec)
    t48_before = json.dumps(first["observation"], sort_keys=True)
    prior = S9.t48_fingerprint(rec)
    out = _ingest_t24(rec)
    assert out["status"] == "RECORDED"
    rows = [o for o in rec.load_observations() if o["macro_event_id"] == "usd_empsit_2026-10-02"]
    t48 = [o for o in rows if o["associated_checkpoint_id"] == "T0-48h"]
    t36 = [o for o in rows if o["associated_checkpoint_id"] == "T0-36h"]
    t24 = [o for o in rows if o["associated_checkpoint_id"] == "T0-24h"]
    assert len(t48) == 1
    assert len(t36) == 0
    assert len(t24) == 1
    assert json.dumps(t48[0], sort_keys=True) == t48_before
    assert S9.t48_fingerprint(rec) == prior
    assert t48[0]["observed_at_utc"] == OBS48
    assert t48[0]["raw_artifact_sha256"] == hashlib.sha256(EVIDENCE48).hexdigest()
    assert t24[0]["observed_at_utc"] == OBS24
    assert t24[0]["observed_at_utc"] < "2026-10-02T12:30:00Z"
    assert t24[0]["checkpoint_id"] == "T0-24h"
    cmp = S9.compare_t48_t24(t48[0], t24[0])
    assert cmp == {
        "nfp": "NO CHANGE",
        "unemployment": "NO CHANGE",
        "ahe_mom": "NO CHANGE",
        "ahe_yoy": "STILL MISSING",
    }


def test_values_consensus_not_forecast_and_ahe_yoy_missing(tmp_path):
    rec = _rec(tmp_path)
    _seed_t48(rec)
    out = _ingest_t24(rec)
    obs = out["observation"]
    comps = obs["calendar_fields"]["components"]
    assert comps["nonfarm_payroll_change"]["consensus_value"] == 90000
    assert comps["nonfarm_payroll_change"]["consensus_raw"] == "90K"
    assert comps["nonfarm_payroll_change"]["previous_raw"] == "162K"
    assert comps["nonfarm_payroll_change"]["te_forecast_raw"] == "90.0K"
    assert comps["unemployment_rate"]["consensus_value"] == pytest.approx(4.1)
    assert comps["unemployment_rate"]["previous_raw"] == "4.1%"
    assert comps["average_hourly_earnings_mom"]["consensus_value"] == pytest.approx(0.3)
    yoy = comps["average_hourly_earnings_yoy"]
    assert yoy["consensus_value"] is None
    assert yoy["consensus_raw"] is None
    assert yoy["consensus_value_quality"] == "NOT_AVAILABLE"
    assert yoy["te_forecast_value"] == pytest.approx(3.1)
    assert yoy["te_forecast_raw"] == "3.1%"
    assert yoy["consensus_value"] != yoy["te_forecast_value"]
    assert yoy["consensus_substituted_from_te_forecast"] is False
    assert obs["forecast_value"] == 90000
    assert obs["forecast_value"] != 3.1
    assert obs["calendar_fields"]["consensus_field_semantics"] == "SURVEY_CONSENSUS"
    assert obs["calendar_fields"]["forecast_field_semantics"] == "PROVIDER_FORECAST_NOT_CONSENSUS"
    assert obs["expectation_type"] == "SURVEY_CONSENSUS"
    assert obs["calendar_fields"]["collection_method"] == "MANUAL_SCREEN_OBSERVATION"
    assert obs["calendar_fields"]["provider"] == "Trading Economics"


def test_canonical_selection_rejects_pre_checkpoint_prefers_earliest_valid():
    early = _cand("early.mp4", OBS24_EARLY, False)
    first = _cand("first.mp4", OBS24, True, digest="11")
    later = _cand("later.mp4", OBS24_LATER, True, digest="22")
    canonical, supplementary = S9.select_canonical([later, early, first])
    assert canonical["filename"] == "first.mp4"
    assert canonical["observed_at_utc"] == OBS24
    assert {s["filename"] for s in supplementary} == {"early.mp4", "later.mp4"}
    with pytest.raises(S9.IngestClosed, match="at or after scheduled"):
        S9.select_canonical([early])
    assert S9.is_valid_t24h(OBS24) is True
    assert S9.is_valid_t24h(OBS24_EARLY) is False
    assert S9.is_valid_t24h("2026-10-02T12:30:00Z") is False


def test_pre_checkpoint_cannot_ingest_t24(tmp_path):
    rec = _rec(tmp_path)
    _seed_t48(rec)
    with pytest.raises(S9.IngestClosed, match="not valid for T0-24h"):
        _ingest_t24(rec, observed_at=OBS24_EARLY)
    with pytest.raises(S9.IngestClosed, match="pre-T0"):
        _ingest_t24(rec, observed_at="2026-10-02T12:30:00Z")
    rows = rec.load_observations()
    assert [o["associated_checkpoint_id"] for o in rows] == ["T0-48h"]
    assert S9.t36_observations(rec) == []


def test_duplicate_cannot_overwrite_and_sha256_stable(tmp_path):
    rec = _rec(tmp_path)
    _seed_t48(rec)
    first = _ingest_t24(rec)
    assert first["observation"]["raw_artifact_sha256"] == hashlib.sha256(EVIDENCE24).hexdigest()
    second = _ingest_t24(rec)
    assert first["status"] == "RECORDED"
    assert second["status"] == "ALREADY_EXISTS"
    rows = rec.load_observations()
    t24 = [o for o in rows if o["associated_checkpoint_id"] == "T0-24h"]
    assert len(t24) == 1
    assert t24[0]["observed_at_utc"] == OBS24
    with pytest.raises(R.RecorderConflict):
        _ingest_t24(rec, evidence=b"DIFFERENT_STAGE9_BYTES")
    again = rec.load_observations()
    t24b = [o for o in again if o["associated_checkpoint_id"] == "T0-24h"]
    assert len(t24b) == 1
    assert t24b[0]["observed_at_utc"] == OBS24
    assert t24b[0]["raw_artifact_sha256"] == first["observation"]["raw_artifact_sha256"]


def test_copied_bytes_retain_identical_sha256(tmp_path):
    src = tmp_path / "Screen Recording 2026-10-01 133043.mp4"
    payload = b"STAGE9_FAKE_COPY_BYTES"
    src.write_bytes(payload)
    dest = S8.copy_evidence_unchanged(src, tmp_path / "evidence")
    assert S8.sha256_file(src) == S8.sha256_file(dest)
    assert S8.sha256_file(src) == hashlib.sha256(payload).hexdigest()
    assert dest.read_bytes() == payload


def test_no_network_scheduler_and_production_unchanged(tmp_path):
    rec = _rec(tmp_path)
    before_cfg = (REAL_ROOT / "config.json").read_text(encoding="utf-8")
    before_reg = (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8")
    before_task = (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8")
    before_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8")
    before_sched = (REAL_ROOT / "scheduler" / "state.json").read_text(encoding="utf-8")
    _seed_t48(rec)
    _ingest_t24(rec)
    src = Path("reports/decision_quality/_macro_prospective_ingest_stage9.py").read_text(encoding="utf-8").lower()
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
        assert "_macro_prospective_ingest_stage9" not in path.read_text(encoding="utf-8")
    S8.assert_activation_unchanged()
    assert (REAL_ROOT / "config.json").read_text(encoding="utf-8") == before_cfg
    assert (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8") == before_reg
    assert (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8") == before_task
    assert (REAL_ROOT / "scheduler" / "state.json").read_text(encoding="utf-8") == before_sched
    after_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8")
    assert before_obs == after_obs
    cfg = json.loads(before_cfg)
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    te = next(s for s in json.loads(before_reg)["sources"] if s["source_id"] == "trading_economics")
    assert te["enabled"] is False
    assert te["automation_class"] != "APPROVED_AUTOMATION_READY"
    ff = [s for s in json.loads(before_reg)["sources"] if s["source_id"] == "forex_factory"]
    assert not ff or ff[0].get("enabled") is not True
