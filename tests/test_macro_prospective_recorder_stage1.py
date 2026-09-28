"""Prospective macro recorder Stage 1. Research-only. No bot_loop / OANDA."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_PATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_SPEC = importlib.util.spec_from_file_location("macro_prospective_recorder", _PATH)
R = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(R)


def _rec(tmp_path: Path):
    return R.bootstrap_store(tmp_path)


def _event(rec, eid="usd_empsit_2026-10-02", family="EMPLOYMENT_SITUATION", t0="2026-10-02T12:30:00Z", period="2026-09"):
    return rec.register_event(
        macro_event_id=eid,
        event_family=family,
        event_name="Employment Situation" if family != "CPI" else "Consumer Price Index",
        reference_period=period,
        scheduled_release_utc=t0,
        official_source="BLS",
    )


def test_t0_48h_window_opening_and_checkpoints():
    t0 = R.parse_utc("2026-10-02T12:30:00Z")
    start, end = R.observation_window(t0)
    assert R.to_utc_iso(start) == "2026-09-30T12:30:00Z"
    assert R.to_utc_iso(end) == "2026-10-02T12:30:00Z"
    times = R.all_checkpoint_times(t0)
    assert list(times) == [c[0] for c in R.CHECKPOINTS]
    assert times["T0-48h"] == "2026-09-30T12:30:00Z"
    assert times["T0-36h"] == "2026-10-01T00:30:00Z"
    assert times["T0-24h"] == "2026-10-01T12:30:00Z"
    assert times["T0-12h"] == "2026-10-02T00:30:00Z"
    assert times["T0-6h"] == "2026-10-02T06:30:00Z"
    assert times["T0-4h"] == "2026-10-02T08:30:00Z"
    assert times["T0-2h"] == "2026-10-02T10:30:00Z"
    assert times["T0-1h"] == "2026-10-02T11:30:00Z"
    assert times["T0-30m"] == "2026-10-02T12:00:00Z"
    assert times["T0-15m"] == "2026-10-02T12:15:00Z"
    assert times["T0-5m"] == "2026-10-02T12:25:00Z"
    assert "T0" not in times


def test_utc_dst_correctness():
    winter = R.local_to_utc(datetime(2026, 1, 13, 8, 30), "America/New_York")
    summer = R.local_to_utc(datetime(2026, 7, 14, 8, 30), "America/New_York")
    assert R.to_utc_iso(winter) == "2026-01-13T13:30:00Z"
    assert R.to_utc_iso(summer) == "2026-07-14T12:30:00Z"
    t0 = R.local_to_utc(datetime(2026, 3, 11, 8, 30), "America/New_York")
    start, _ = R.observation_window(t0)
    assert start.tzinfo is not None
    assert (t0 - start) == timedelta(hours=48)
    with pytest.raises(ValueError):
        R.parse_utc("2026-01-13T08:30:00")
    with pytest.raises(ValueError):
        R.to_utc_iso(datetime(2026, 1, 13, 8, 30))


def test_observed_at_pre_equal_post_t0(tmp_path):
    rec = _rec(tmp_path)
    _event(rec)
    t0 = "2026-10-02T12:30:00Z"
    pre = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_a",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"pre 160k",
        observed_at_utc="2026-10-02T12:25:00Z",
        checkpoint_id="T0-5m",
        forecast_value=160000,
        unit="persons",
        source_publication_utc="2026-10-02T12:20:00Z",
    )
    assert pre["observation"]["pre_release"] is True
    assert pre["observation"]["prospective_pit_status"] == "OBSERVED_PRE_T0"
    assert pre["observation"]["observed_at_utc"] != pre["observation"]["source_publication_utc"]
    eq = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_a",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"eq t0",
        observed_at_utc=t0,
        forecast_value=160000,
        unit="persons",
    )
    assert eq["observation"]["pre_release"] is False
    assert eq["observation"]["prospective_pit_status"] == "OBSERVED_POST_T0"
    post = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_a",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"post t0",
        observed_at_utc="2026-10-02T12:40:00Z",
        forecast_value=110000,
        unit="persons",
    )
    assert post["observation"]["prospective_pit_status"] == "OBSERVED_POST_T0"
    final = rec.final_pre_release_observation("usd_empsit_2026-10-02", series_name="nonfarm_payroll_change")
    assert final["observation_id"] == pre["observation"]["observation_id"]
    assert final["observed_at_utc"] == "2026-10-02T12:25:00Z"


def test_immutable_artifacts_sha256_reuse_and_new_vintage(tmp_path):
    rec = _rec(tmp_path)
    _event(rec)
    a = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_a",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"same-bytes",
        observed_at_utc="2026-09-30T12:30:00Z",
        checkpoint_id="T0-48h",
        forecast_value=175000,
        unit="persons",
    )
    b = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_a",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"same-bytes",
        observed_at_utc="2026-10-01T12:30:00Z",
        checkpoint_id="T0-24h",
        forecast_value=175000,
        unit="persons",
    )
    assert a["status"] == "RECORDED" and b["status"] == "RECORDED"
    ha = a["observation"]["raw_artifact_hash"]
    hb = b["observation"]["raw_artifact_hash"]
    assert ha == hb == hashlib.sha256(b"same-bytes").hexdigest()
    assert a["observation"]["observation_id"] != b["observation"]["observation_id"]
    c = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_a",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"changed-bytes",
        observed_at_utc="2026-10-02T06:30:00Z",
        checkpoint_id="T0-6h",
        forecast_value=165000,
        unit="persons",
    )
    assert c["observation"]["raw_artifact_hash"] != ha
    assert Path(a["observation"]["artifact_location"]).read_bytes() == b"same-bytes"
    assert Path(c["observation"]["artifact_location"]).read_bytes() == b"changed-bytes"


def test_restart_safe_and_idempotent_and_conflict(tmp_path):
    rec = _rec(tmp_path)
    _event(rec)
    kwargs = dict(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_a",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"v1",
        observed_at_utc="2026-10-02T11:30:00Z",
        checkpoint_id="T0-1h",
        forecast_value=160000,
        unit="persons",
    )
    first = rec.ingest_manual(**kwargs)
    rec2 = R.ProspectiveRecorder(tmp_path)
    recon = rec2.reconstruct()
    assert len(recon["observations"]) == 1
    assert recon["observations"][0]["observation_id"] == first["observation"]["observation_id"]
    again = rec2.ingest_manual(**kwargs)
    assert again["status"] == "ALREADY_EXISTS"
    assert again["observation_id"] == first["observation"]["observation_id"]
    with pytest.raises(R.RecorderConflict, match="CONFLICT"):
        rec2.ingest_manual(**{**kwargs, "artifact_bytes": b"v2", "forecast_value": 150000})


def test_manual_ingest_and_source_disabled_fail_closed(tmp_path):
    rec = _rec(tmp_path)
    _event(rec)
    out = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="reuters",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"manual reuters 160k",
        observed_at_utc="2026-10-02T11:30:00Z",
        checkpoint_id="T0-1h",
        forecast_value=160000,
        unit="persons",
        retrieval_method="manual",
    )
    assert out["status"] == "RECORDED"
    assert rec.collection_enabled() is False
    assert rec.source_by_id("reuters")["enabled"] is False
    with pytest.raises(R.RecorderClosed, match="FORWARD_CONSENSUS_COLLECTION_ENABLED"):
        rec.ingest_autonomous(
            macro_event_id="usd_empsit_2026-10-02",
            source_id="reuters",
            series_name="nonfarm_payroll_change",
            expectation_type="SURVEY_CONSENSUS",
            artifact_bytes=b"auto",
            observed_at_utc="2026-10-02T11:31:00Z",
            forecast_value=160000,
            unit="persons",
        )
    with pytest.raises(R.RecorderClosed, match="unknown source"):
        rec.ingest_manual(
            macro_event_id="usd_empsit_2026-10-02",
            source_id="not_a_registered_source",
            series_name="nonfarm_payroll_change",
            expectation_type="SURVEY_CONSENSUS",
            artifact_bytes=b"x",
            observed_at_utc="2026-10-02T11:32:00Z",
            forecast_value=1,
            unit="persons",
        )
    rec.config_path.write_text(json.dumps({R.FORWARD_FLAG: True}), encoding="utf-8")
    with pytest.raises(R.RecorderClosed, match="SOURCE_DISABLED"):
        rec.ingest_autonomous(
            macro_event_id="usd_empsit_2026-10-02",
            source_id="reuters",
            series_name="nonfarm_payroll_change",
            expectation_type="SURVEY_CONSENSUS",
            artifact_bytes=b"still disabled",
            observed_at_utc="2026-10-02T11:33:00Z",
            forecast_value=160000,
            unit="persons",
        )


def test_providers_individual_calendar_not_averaged(tmp_path):
    rec = _rec(tmp_path)
    _event(rec)
    rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_a",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"A 160k",
        observed_at_utc="2026-10-02T11:30:00Z",
        checkpoint_id="T0-1h",
        forecast_value=160000,
        unit="persons",
    )
    rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_c",
        series_name="nonfarm_payroll_change",
        expectation_type="INDIVIDUAL_FORECAST",
        artifact_bytes=b"C 150k individual",
        observed_at_utc="2026-10-02T11:30:00Z",
        checkpoint_id="T0-1h",
        forecast_value=150000,
        unit="persons",
    )
    rec.ingest_calendar(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_calendar",
        series_name="nonfarm_payroll_change",
        artifact_bytes=b"calendar 155k",
        observed_at_utc="2026-10-02T11:30:00Z",
        checkpoint_id="T0-1h",
        forecast_value=155000,
        unit="persons",
        calendar_fields={"forecast": 155000, "provider": "Fixture Calendar", "importance": "high"},
    )
    rows = rec.load_observations()
    assert {r["source_publisher"] for r in rows} >= {"Provider A", "Provider C", "Fixture Calendar"}
    assert any(r["expectation_type"] == "INDIVIDUAL_FORECAST" and "CONSENSUS" not in r["expectation_type"] for r in rows)
    assert any(r["expectation_type"] == "ECONOMIC_CALENDAR_FORECAST" for r in rows)
    vals = [r["forecast_value"] for r in rows]
    assert 160000 in vals and 150000 in vals and 155000 in vals
    with pytest.raises(RuntimeError, match="must not be averaged"):
        R.average_providers(rows)


def test_cpi_employment_exact_series_and_missing_not_zero(tmp_path):
    rec = _rec(tmp_path)
    rec.register_event(
        macro_event_id="usd_cpi_2026-10-15",
        event_family="CPI",
        event_name="Consumer Price Index",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-15T12:30:00Z",
        official_source="BLS",
    )
    ok = rec.ingest_manual(
        macro_event_id="usd_cpi_2026-10-15",
        source_id="fixture_provider_a",
        series_name="headline_mom",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"cpi mom 0.3 SA",
        observed_at_utc="2026-10-15T11:30:00Z",
        checkpoint_id="T0-1h",
        forecast_value=0.3,
        unit="percent",
        seasonal_adjustment="SA",
        reference_period="2026-09",
    )
    assert ok["observation"]["prospective_pit_status"] == "OBSERVED_PRE_T0_SOURCE_TIME_UNKNOWN"
    amb = rec.ingest_manual(
        macro_event_id="usd_cpi_2026-10-15",
        source_id="fixture_provider_a",
        series_name="inflation",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"ambiguous inflation",
        observed_at_utc="2026-10-15T11:31:00Z",
        forecast_value=None,
        value_quality="AMBIGUOUS",
        unit="percent",
    )
    assert amb["observation"]["prospective_pit_status"] == "INVALID_SERIES"
    rec.register_event(
        macro_event_id="usd_empsit_dec",
        event_family="EMPLOYMENT_SITUATION",
        event_name="Employment Situation",
        reference_period="2025-12",
        scheduled_release_utc="2026-01-09T13:30:00Z",
        official_source="BLS",
    )
    wrong = rec.ingest_manual(
        macro_event_id="usd_empsit_dec",
        source_id="fixture_provider_a",
        series_name="unemployment_rate",
        expectation_type="SURVEY_MEDIAN",
        artifact_bytes=b"November u-rate 4.5",
        observed_at_utc="2026-01-08T13:30:00Z",
        forecast_value=4.5,
        unit="percent",
        reference_period="2025-11",
    )
    assert wrong["observation"]["prospective_pit_status"] == "INVALID_SERIES"
    with pytest.raises(ValueError, match="must not be encoded as zero"):
        rec.ingest_manual(
            macro_event_id="usd_empsit_dec",
            source_id="fixture_provider_a",
            series_name="nonfarm_payroll_change",
            expectation_type="SURVEY_CONSENSUS",
            artifact_bytes=b"missing",
            observed_at_utc="2026-01-08T13:31:00Z",
            forecast_value=0,
            value_quality="NOT_AVAILABLE",
            unit="persons",
            reference_period="2025-12",
        )


def test_fomc_distribution_not_collapsed(tmp_path):
    rec = _rec(tmp_path)
    rec.register_event(
        macro_event_id="usd_fomc_statement_2026-11-05",
        event_family="FOMC",
        event_name="FOMC statement",
        reference_period="2026-11-04/05",
        scheduled_release_utc="2026-11-05T19:00:00Z",
        official_source="FRB",
    )
    dist = {"hold": 80, "cut_25bp": 20, "n": 100}
    out = rec.ingest_manual(
        macro_event_id="usd_fomc_statement_2026-11-05",
        source_id="fixture_provider_a",
        series_name="expected_policy_decision",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"80/100 hold 20/100 cut 25bp",
        observed_at_utc="2026-11-04T19:00:00Z",
        checkpoint_id="T0-24h",
        forecast_value="hold",
        unit="categorical",
        fomc_distribution=dist,
    )
    assert out["observation"]["forecast_value"] == "hold"
    assert out["observation"]["forecast_value"] != -25
    assert out["observation"]["fomc_distribution"]["hold"] == 80
    rec.ingest_manual(
        macro_event_id="usd_fomc_statement_2026-11-05",
        source_id="fixture_provider_b",
        series_name="cut_25bp_probability",
        expectation_type="MARKET_IMPLIED_EXPECTATION",
        artifact_bytes=b"fedwatch cut 25bp 0.22",
        observed_at_utc="2026-11-04T19:00:00Z",
        checkpoint_id="T0-24h",
        forecast_value=0.22,
        unit="probability",
    )
    with pytest.raises(RuntimeError, match="must not be collapsed"):
        R.collapse_fomc_probability_to_bp(0.9, "cut_25bp")


def test_first_print_immutable_revision_and_post_t0_race(tmp_path):
    rec = _rec(tmp_path)
    _event(rec)
    rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_provider_a",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"final 160k",
        observed_at_utc="2026-10-02T12:25:00Z",
        checkpoint_id="T0-5m",
        forecast_value=160000,
        unit="persons",
    )
    fp = rec.capture_first_print(
        macro_event_id="usd_empsit_2026-10-02",
        series_name="nonfarm_payroll_change",
        actual_first_print=110000,
        artifact_bytes=b"official 110k",
        first_observed_at_utc="2026-10-02T12:31:00Z",
        unit="persons",
        seasonal_adjustment="SA",
    )
    assert fp["status"] == "RECORDED"
    again = rec.capture_first_print(
        macro_event_id="usd_empsit_2026-10-02",
        series_name="nonfarm_payroll_change",
        actual_first_print=110000,
        artifact_bytes=b"official 110k",
        first_observed_at_utc="2026-10-02T12:31:00Z",
        unit="persons",
        seasonal_adjustment="SA",
    )
    assert again["status"] == "ALREADY_EXISTS"
    with pytest.raises(R.RecorderConflict, match="first print cannot be overwritten"):
        rec.capture_first_print(
            macro_event_id="usd_empsit_2026-10-02",
            series_name="nonfarm_payroll_change",
            actual_first_print=90000,
            artifact_bytes=b"revised overwrite attempt",
            first_observed_at_utc="2026-11-01T12:30:00Z",
            unit="persons",
        )
    rev = rec.capture_revision(
        macro_event_id="usd_empsit_2026-10-02",
        series_name="nonfarm_payroll_change",
        actual_first_print=90000,
        artifact_bytes=b"later revision 90k",
        first_observed_at_utc="2026-11-06T13:30:00Z",
        unit="persons",
    )
    assert rev["status"] == "RECORDED"
    assert rev["actual"]["record_kind"] == "REVISION"
    firsts = [a for a in rec.load_actuals() if a["record_kind"] == "FIRST_PRINT"]
    assert firsts[0]["actual_first_print"] == 110000
    rec.ingest_calendar(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="fixture_calendar",
        series_name="nonfarm_payroll_change",
        artifact_bytes=b"calendar now shows actual 110k and overwrites forecast",
        observed_at_utc="2026-10-02T12:40:00Z",
        forecast_value=110000,
        unit="persons",
    )
    final = rec.final_pre_release_observation(
        "usd_empsit_2026-10-02", series_name="nonfarm_payroll_change", source_id="fixture_provider_a"
    )
    assert final["forecast_value"] == 160000
    assert final["observed_at_utc"] == "2026-10-02T12:25:00Z"


def test_no_production_execution_imports_or_authority():
    src = Path("reports/decision_quality/_macro_prospective_recorder.py").read_text(encoding="utf-8")
    for name in R.FORBIDDEN_PRODUCTION_IMPORTS:
        assert ("import %s" % name) not in src
        assert ("from %s" % name) not in src
    loop = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert "prospective_recorder" not in loop
    assert "_macro_prospective_recorder" not in loop
    cfg = json.loads(Path("data/research/macro/consensus_pit/prospective/config.json").read_text(encoding="utf-8"))
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False


def test_dry_run_fixture_evolution_restart_idempotent(tmp_path):
    dry_root = tmp_path / "dry"
    result = R.run_dry_run(dry_root)
    assert result["final_pre_release_a"]["checkpoint_id"] == "T0-5m"
    assert result["final_pre_release_a"]["forecast_value"] == 160000
    assert result["final_unchanged_by_post_t0"] is True
    assert result["first_print"] == 110000
    assert result["post_t0_pit"] == "OBSERVED_POST_T0"
    assert result["surprise_a"]["surprise_raw"] == -50000
    hashes = result["provider_a_hashes"]
    h48 = [h for ck, h, v in hashes if ck == "T0-48h"][0]
    h24 = [h for ck, h, v in hashes if ck == "T0-24h"][0]
    h6 = [h for ck, h, v in hashes if ck == "T0-6h"][0]
    h1 = [h for ck, h, v in hashes if ck == "T0-1h"][0]
    h5 = [h for ck, h, v in hashes if ck == "T0-5m"][0]
    assert h48 == h24
    assert h6 != h48
    assert h1 == h5
    assert h1 != h6
    rec2 = R.ProspectiveRecorder(dry_root)
    recon = rec2.reconstruct()
    assert len(recon["observations"]) == result["n_observations"]
    rerun = R.run_dry_run(dry_root)
    assert rerun["n_observations"] == result["n_observations"]
    rec = R.ProspectiveRecorder(dry_root)
    assert rec.derive_status("fixture_empsit_2026-10-02", R.parse_utc("2026-10-02T12:40:00Z")) in {
        "FIRST_PRINT_CAPTURED",
        "POST_RELEASE_OBSERVATION",
        "COMPLETE",
    }
    rec.register_event(
        macro_event_id="usd_cpi_local",
        event_family="CPI",
        event_name="Consumer Price Index",
        reference_period="2026-09",
        scheduled_release_local="2026-10-15T08:30:00",
        scheduled_timezone="America/New_York",
        official_source="BLS",
    )
    ev = rec.event_by_id("usd_cpi_local")
    assert ev["scheduled_release_utc"] == "2026-10-15T12:30:00Z"
    assert ev["observation_window_start_utc"] == "2026-10-13T12:30:00Z"
    assert rec.derive_status("usd_cpi_local", R.parse_utc("2026-10-10T12:30:00Z")) == "PRE_WINDOW"
    assert rec.derive_status("usd_cpi_local", R.parse_utc("2026-10-14T12:30:00Z")) == "COLLECTING_PRE_RELEASE"
