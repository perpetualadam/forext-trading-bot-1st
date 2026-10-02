"""Stage 8 real T-48h ingest tests. Fixtures/mocks only. No live evidence. No network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_IPATH = Path("reports/decision_quality/_macro_prospective_ingest_stage8.py")
_ISPEC = importlib.util.spec_from_file_location("macro_stage8_ingest", _IPATH)
S8 = importlib.util.module_from_spec(_ISPEC)
_ISPEC.loader.exec_module(S8)

_RPATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_RSPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_s8", _RPATH)
R = importlib.util.module_from_spec(_RSPEC)
_RSPEC.loader.exec_module(R)

UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
CLOCK = datetime(2026, 9, 30, 21, 20, tzinfo=UTC)
OBS = "2026-09-30T12:31:17Z"
EVIDENCE = b"FAKE_STAGE8_EVIDENCE_NOT_THE_REAL_MP4"


def _rec(tmp_path: Path):
    rec = R.bootstrap_store(tmp_path, clock=lambda: CLOCK)
    R.register_official_upcoming(rec, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    return rec


def _ingest(rec, evidence=EVIDENCE, observed_at=OBS):
    digest = hashlib.sha256(evidence).hexdigest()
    return S8.ingest_stage8(
        rec=rec,
        evidence_bytes=evidence,
        observed_at_utc=observed_at,
        evidence_filename="fixture.mp4",
        evidence_sha256=digest,
        ingested_at_utc="2026-09-30T21:20:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
    )


def test_components_normalization_and_missing_ahe_yoy(tmp_path):
    rec = _rec(tmp_path)
    out = _ingest(rec)
    obs = out["observation"]
    comps = obs["calendar_fields"]["components"]
    assert comps["nonfarm_payroll_change"]["consensus_value"] == 90000
    assert comps["nonfarm_payroll_change"]["previous_value"] == 162000
    assert comps["nonfarm_payroll_change"]["unit"] == "persons"
    assert comps["unemployment_rate"]["consensus_value"] == pytest.approx(4.1)
    assert comps["average_hourly_earnings_mom"]["consensus_value"] == pytest.approx(0.3)
    yoy = comps["average_hourly_earnings_yoy"]
    assert yoy["consensus_value"] is None
    assert yoy["consensus_raw"] is None
    assert yoy["consensus_value_quality"] == "NOT_AVAILABLE"
    assert yoy["te_forecast_value"] == pytest.approx(3.1)
    assert yoy["consensus_value"] != yoy["te_forecast_value"]
    assert yoy["consensus_substituted_from_te_forecast"] is False
    assert obs["forecast_value"] == 90000
    assert obs["forecast_value"] != 3.1
    assert obs["calendar_fields"]["consensus_field_semantics"] == "SURVEY_CONSENSUS"
    assert obs["calendar_fields"]["forecast_field_semantics"] == "PROVIDER_FORECAST_NOT_CONSENSUS"
    assert obs["expectation_type"] == "SURVEY_CONSENSUS"
    assert obs["observed_at_utc"] == OBS
    assert obs["observed_at_utc"] < "2026-10-02T12:30:00Z"
    assert obs["checkpoint_id"] == "T0-48h"
    assert obs["associated_checkpoint_id"] == "T0-48h"
    assert obs["raw_artifact_sha256"] == hashlib.sha256(EVIDENCE).hexdigest()
    assert obs["retrieval_utc"] == "2026-09-30T21:20:00Z"
    assert obs["retrieval_utc"] != obs["observed_at_utc"]


def test_duplicate_cannot_overwrite_and_observed_at_frozen(tmp_path):
    rec = _rec(tmp_path)
    first = _ingest(rec)
    second = _ingest(rec)
    assert first["status"] == "RECORDED"
    assert second["status"] == "ALREADY_EXISTS"
    rows = rec.load_observations()
    real = [o for o in rows if o["macro_event_id"] == "usd_empsit_2026-10-02"]
    assert len(real) == 1
    assert real[0]["observed_at_utc"] == OBS
    assert real[0]["forecast_value"] == 90000
    with pytest.raises(R.RecorderConflict):
        S8.ingest_stage8(
            rec=rec,
            evidence_bytes=b"DIFFERENT_BYTES",
            observed_at_utc=OBS,
            evidence_filename="fixture.mp4",
            evidence_sha256=hashlib.sha256(b"DIFFERENT_BYTES").hexdigest(),
            ingested_at_utc="2026-09-30T22:00:00Z",
            evidence_timestamp_basis="fixture",
            artifact_suffix="bin",
        )
    again = rec.load_observations()
    assert len(again) == 1
    assert again[0]["observed_at_utc"] == OBS
    assert again[0]["raw_artifact_sha256"] == first["observation"]["raw_artifact_sha256"]


def test_post_t0_and_wrong_checkpoint_fail_closed(tmp_path):
    rec = _rec(tmp_path)
    with pytest.raises(S8.IngestClosed, match="pre-T0"):
        _ingest(rec, observed_at="2026-10-02T12:30:00Z")
    with pytest.raises(S8.IngestClosed, match="T0-48h"):
        _ingest(rec, observed_at="2026-10-01T12:31:00Z")
    assert rec.load_observations() == []


def test_no_network_and_production_unchanged(tmp_path):
    rec = _rec(tmp_path)
    before_cfg = (REAL_ROOT / "config.json").read_text(encoding="utf-8")
    before_reg = (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8")
    before_task = (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8")
    before_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8") if (REAL_ROOT / "observations" / "observations.jsonl").exists() else ""
    _ingest(rec)
    src = Path("reports/decision_quality/_macro_prospective_ingest_stage8.py").read_text(encoding="utf-8").lower()
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
        assert "_macro_prospective_ingest_stage8" not in path.read_text(encoding="utf-8")
    S8.assert_activation_unchanged()
    assert (REAL_ROOT / "config.json").read_text(encoding="utf-8") == before_cfg
    assert (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8") == before_reg
    assert (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8") == before_task
    after_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8") if (REAL_ROOT / "observations" / "observations.jsonl").exists() else ""
    assert before_obs == after_obs
    cfg = json.loads(before_cfg)
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    te = next(s for s in json.loads(before_reg)["sources"] if s["source_id"] == "trading_economics")
    assert te["enabled"] is False
    assert te["automation_class"] != "APPROVED_AUTOMATION_READY"
