"""Stage 11 completion tests. Fixtures/mocks only. No live evidence. No network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_IPATH = Path("reports/decision_quality/_macro_prospective_ingest_stage11.py")
_ISPEC = importlib.util.spec_from_file_location("macro_stage11_ingest", _IPATH)
S11 = importlib.util.module_from_spec(_ISPEC)
_ISPEC.loader.exec_module(S11)

S10 = S11.S10
S8 = S11.S8
S9_PATH = Path("reports/decision_quality/_macro_prospective_ingest_stage9.py")
S9_SPEC = importlib.util.spec_from_file_location("macro_stage9_for_stage11_tests", S9_PATH)
S9 = importlib.util.module_from_spec(S9_SPEC)
S9_SPEC.loader.exec_module(S9)

_RPATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_RSPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_s11", _RPATH)
R = importlib.util.module_from_spec(_RSPEC)
_RSPEC.loader.exec_module(R)

UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
CLOCK = datetime(2026, 10, 2, 12, 40, tzinfo=UTC)
OBS48 = "2026-09-30T12:31:17Z"
OBS24 = "2026-10-01T12:30:43Z"
OBS12 = "2026-10-02T00:30:36Z"
OBS90M = "2026-10-02T11:00:27Z"
OBS1H = "2026-10-02T11:30:44Z"
OBS30M = "2026-10-02T12:00:31Z"
OBS15M = "2026-10-02T12:16:36Z"
OBS5M = "2026-10-02T12:25:12Z"
OBS_POST = "2026-10-02T12:30:48Z"
EV48 = b"FAKE_S8"
EV24 = b"FAKE_S9"
EV12 = b"FAKE_S10"
EV1H = b"FAKE_S11_T1H"
EV30 = b"FAKE_S11_T30M"
EV15 = b"FAKE_S11_T15M"
EV5 = b"FAKE_S11_T5M"


def _rec(tmp_path: Path):
    rec = R.bootstrap_store(tmp_path, clock=lambda: CLOCK)
    R.register_official_upcoming(rec, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    return rec


def _seed_priors(rec):
    S8.ingest_stage8(
        rec=rec,
        evidence_bytes=EV48,
        observed_at_utc=OBS48,
        evidence_filename="t48.bin",
        evidence_sha256=hashlib.sha256(EV48).hexdigest(),
        ingested_at_utc="2026-09-30T21:20:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
    )
    S9.ingest_stage9(
        rec=rec,
        evidence_bytes=EV24,
        observed_at_utc=OBS24,
        evidence_filename="t24.bin",
        evidence_sha256=hashlib.sha256(EV24).hexdigest(),
        ingested_at_utc="2026-10-01T21:20:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
    )
    S10.ingest_stage10(
        rec=rec,
        evidence_bytes=EV12,
        observed_at_utc=OBS12,
        evidence_filename="t12.bin",
        evidence_sha256=hashlib.sha256(EV12).hexdigest(),
        ingested_at_utc="2026-10-02T00:45:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
    )


def _ingest(rec, checkpoint_id, evidence, observed_at, filename="fx.bin"):
    priors = {
        cid: S11.fingerprint(S11.checkpoint_rows(rec, cid)[0] if S11.checkpoint_rows(rec, cid) else None)
        for cid in S11.PRIOR_CHECKPOINTS
    }
    return S11.ingest_stage11_checkpoint(
        rec=rec,
        checkpoint_id=checkpoint_id,
        evidence_bytes=evidence,
        observed_at_utc=observed_at,
        evidence_filename=filename,
        evidence_sha256=hashlib.sha256(evidence).hexdigest(),
        ingested_at_utc="2026-10-02T12:40:00Z",
        evidence_timestamp_basis="fixture",
        artifact_suffix="bin",
        priors=priors,
    )


def test_priors_unchanged_and_valid_late_checkpoints_map(tmp_path):
    rec = _rec(tmp_path)
    _seed_priors(rec)
    before = {cid: json.dumps(S11.checkpoint_rows(rec, cid)[0], sort_keys=True) for cid in S11.PRIOR_CHECKPOINTS}
    t48_yoy = S11.checkpoint_rows(rec, "T0-48h")[0]["calendar_fields"]["components"]["average_hourly_earnings_yoy"]
    t24_yoy = S11.checkpoint_rows(rec, "T0-24h")[0]["calendar_fields"]["components"]["average_hourly_earnings_yoy"]
    assert t48_yoy["consensus_value"] is None
    assert t24_yoy["consensus_value"] is None
    for cid, ev, obs in (("T0-1h", EV1H, OBS1H), ("T0-30m", EV30, OBS30M), ("T0-15m", EV15, OBS15M), ("T0-5m", EV5, OBS5M)):
        assert S11.is_valid_for_checkpoint(obs, cid) is True
        out = _ingest(rec, cid, ev, obs)
        assert out["status"] == "RECORDED"
        assert out["observation"]["observed_at_utc"] == obs
        assert out["observation"]["associated_checkpoint_id"] == cid
        assert out["observation"]["observed_at_utc"] != S11.SCHEDULED[cid]
    assert S11.checkpoint_rows(rec, "T0-36h") == []
    for cid in S11.PRIOR_CHECKPOINTS:
        assert json.dumps(S11.checkpoint_rows(rec, cid)[0], sort_keys=True) == before[cid]
    late_yoy = S11.checkpoint_rows(rec, "T0-1h")[0]["calendar_fields"]["components"]["average_hourly_earnings_yoy"]
    assert late_yoy["consensus_value"] == pytest.approx(3.2)
    assert S11.checkpoint_rows(rec, "T0-48h")[0]["calendar_fields"]["components"]["average_hourly_earnings_yoy"]["consensus_value"] is None
    assert S11.checkpoint_rows(rec, "T0-24h")[0]["calendar_fields"]["components"]["average_hourly_earnings_yoy"]["consensus_value"] is None


def test_unsupported_and_t90m_and_post_t0_cannot_become_checkpoints(tmp_path):
    rec = _rec(tmp_path)
    _seed_priors(rec)
    for cid in S11.UNSUPPORTED_TO_MANUFACTURE:
        with pytest.raises(S11.IngestClosed, match="cannot be manufactured"):
            _ingest(rec, cid, b"NO", "2026-10-02T06:31:00Z")
    with pytest.raises(S11.IngestClosed, match="T-90m"):
        _ingest(rec, "T0-1h", b"NO", OBS90M)
    with pytest.raises(S11.IngestClosed, match="T-90m"):
        _ingest(rec, "T0-2h", b"NO", OBS90M)
    with pytest.raises(S11.IngestClosed, match="post-T0"):
        _ingest(rec, "T0-5m", b"NO", OBS_POST)
    assert S11.classify_observed_at(OBS90M) == S11.T90M_LABEL
    assert S11.classify_observed_at(OBS_POST) == S11.POST_RELEASE_LABEL
    assert S11.is_valid_for_checkpoint(OBS90M, "T0-1h") is False
    assert [o["associated_checkpoint_id"] for o in rec.load_observations()] == ["T0-48h", "T0-24h", "T0-12h"]


def test_values_separation_duplicate_hash_and_surprise_gate(tmp_path):
    rec = _rec(tmp_path)
    _seed_priors(rec)
    first = _ingest(rec, "T0-1h", EV1H, OBS1H)
    comps = first["observation"]["calendar_fields"]["components"]
    assert comps["nonfarm_payroll_change"]["consensus_value"] == 90000
    assert comps["unemployment_rate"]["consensus_value"] == pytest.approx(4.1)
    assert comps["average_hourly_earnings_mom"]["consensus_value"] == pytest.approx(0.3)
    yoy = comps["average_hourly_earnings_yoy"]
    assert yoy["consensus_value"] == pytest.approx(3.2)
    assert yoy["te_forecast_value"] == pytest.approx(3.1)
    assert yoy["consensus_value"] != yoy["te_forecast_value"]
    second = _ingest(rec, "T0-1h", EV1H, OBS1H)
    assert second["status"] == "ALREADY_EXISTS"
    assert len(S11.checkpoint_rows(rec, "T0-1h")) == 1
    with pytest.raises(R.RecorderConflict):
        _ingest(rec, "T0-1h", b"DIFFERENT", OBS1H)
    assert first["observation"]["raw_artifact_sha256"] == hashlib.sha256(EV1H).hexdigest()
    src = tmp_path / "copy.mp4"
    src.write_bytes(EV1H)
    dest = S8.copy_evidence_unchanged(src, tmp_path / "evidence")
    assert S8.sha256_file(src) == S8.sha256_file(dest)
    t15 = _ingest(rec, "T0-15m", EV15, OBS15M)["observation"]
    surprise_no_t5 = S11.strict_final_surprise(t5m=t15, first_prints={"nfp": {"actual_first_print": 119000}})
    assert surprise_no_t5["available"] is False
    assert surprise_no_t5["nfp"] is None
    t5 = _ingest(rec, "T0-5m", EV5, OBS5M)["observation"]
    surprise_no_actual = S11.strict_final_surprise(t5m=t5, first_prints={})
    assert surprise_no_actual["available"] is False
    ok = S11.strict_final_surprise(
        t5m=t5,
        first_prints={
            "nfp": {"actual_first_print": 119000},
            "unemployment": {"actual_first_print": 4.4},
            "ahe_mom": {"actual_first_print": 0.2},
            "ahe_yoy": {"actual_first_print": 3.8},
        },
    )
    assert ok["available"] is True
    assert ok["nfp"] == 119000 - 90000
    assert ok["unemployment_pp"] == pytest.approx(0.3)
    assert ok["ahe_mom_pp"] == pytest.approx(-0.1)
    assert ok["ahe_yoy_pp"] == pytest.approx(0.6)


def test_first_print_and_consensus_cannot_overwrite_each_other(tmp_path):
    rec = _rec(tmp_path)
    _seed_priors(rec)
    t5 = _ingest(rec, "T0-5m", EV5, OBS5M)
    consensus_count = len(rec.load_observations())
    first = rec.capture_first_print(
        macro_event_id="usd_empsit_2026-10-02",
        series_name="nonfarm_payroll_change",
        actual_first_print=119000,
        artifact_bytes=b"BLS FIRST PRINT NFP=119000",
        first_observed_at_utc="2026-10-02T12:31:00Z",
        unit="persons",
        seasonal_adjustment="SA",
        notes="fixture official first print",
    )
    assert first["status"] == "RECORDED"
    assert len(rec.load_observations()) == consensus_count
    assert t5["observation"]["forecast_value"] == 90000
    with pytest.raises(R.RecorderConflict, match="first print cannot be overwritten"):
        rec.capture_first_print(
            macro_event_id="usd_empsit_2026-10-02",
            series_name="nonfarm_payroll_change",
            actual_first_print=999999,
            artifact_bytes=b"REVISION ATTEMPT",
            first_observed_at_utc="2026-10-02T13:00:00Z",
            unit="persons",
        )
    actuals = rec.load_actuals()
    assert len(actuals) == 1
    assert actuals[0]["actual_first_print"] == 119000
    rec.capture_revision(
        macro_event_id="usd_empsit_2026-10-02",
        series_name="nonfarm_payroll_change",
        actual_first_print=100000,
        artifact_bytes=b"LATER REVISION",
        first_observed_at_utc="2026-11-01T12:30:00Z",
        unit="persons",
    )
    first_prints = [a for a in rec.load_actuals() if a["record_kind"] == "FIRST_PRINT"]
    assert first_prints[0]["actual_first_print"] == 119000


def test_no_network_scheduler_production_and_official_gate(tmp_path):
    rec = _rec(tmp_path)
    before_cfg = (REAL_ROOT / "config.json").read_text(encoding="utf-8")
    before_reg = (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8")
    before_task = (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8")
    before_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8")
    _seed_priors(rec)
    _ingest(rec, "T0-1h", EV1H, OBS1H)
    src = Path("reports/decision_quality/_macro_prospective_ingest_stage11.py").read_text(encoding="utf-8").lower()
    assert "import urllib" not in src
    assert "import requests" not in src
    assert "http.client" not in src
    assert "selenium" not in src
    assert "playwright" not in src
    assert "oanda" not in src
    for path in (
        Path("reports/decision_quality/_macro_prospective_scheduler.py"),
        Path("reports/decision_quality/macro_prospective_cli.py"),
        Path("forex_bot/bot_loop.py"),
    ):
        assert "_macro_prospective_ingest_stage11" not in path.read_text(encoding="utf-8")
    S8.assert_activation_unchanged()
    gate = S11.official_first_print_gate()
    assert gate["ready"] is False
    assert gate["requests"] == 0
    assert gate["captured"] is False
    assert (REAL_ROOT / "config.json").read_text(encoding="utf-8") == before_cfg
    assert (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8") == before_reg
    assert (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8") == before_task
    assert (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8") == before_obs
    cfg = json.loads(before_cfg)
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    assert cfg.get("OFFICIAL_BLS_FIRST_PRINT_ENABLED") is False
