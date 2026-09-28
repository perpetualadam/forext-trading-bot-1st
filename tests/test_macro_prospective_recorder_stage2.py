"""Prospective macro recorder Stage 2. Research-only. No bot_loop / OANDA."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_PATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_SPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_s2", _PATH)
R = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(R)

_CLI_PATH = Path("reports/decision_quality/macro_prospective_cli.py")
_CLI_SPEC = importlib.util.spec_from_file_location("macro_prospective_cli", _CLI_PATH)
CLI = importlib.util.module_from_spec(_CLI_SPEC)
assert _CLI_SPEC is not None and _CLI_SPEC.loader is not None
_CLI_SPEC.loader.exec_module(CLI)

UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")


class _Clock:
    def __init__(self, dt: datetime):
        self.dt = dt

    def __call__(self) -> datetime:
        return self.dt


def _rec(tmp_path: Path, now: datetime | None = None):
    clock = _Clock(now) if now else None
    return R.bootstrap_store(tmp_path, clock=clock)


def test_official_event_registration_and_next_event(tmp_path):
    now = datetime(2026, 9, 28, 21, 30, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    registered = R.register_official_upcoming(rec, now)
    ids = [e["macro_event_id"] for e in registered]
    assert ids == [
        "usd_empsit_2026-10-02",
        "usd_cpi_2026-10-14",
        "usd_fomc_statement_2026-10-28",
    ]
    emp = rec.event_by_id("usd_empsit_2026-10-02")
    assert emp["official_schedule_url"] == "https://www.bls.gov/schedule/news_release/empsit.htm"
    assert emp["scheduled_release_local"] == "2026-10-02T08:30:00"
    assert emp["scheduled_timezone"] == "America/New_York"
    assert emp["scheduled_release_utc"] == "2026-10-02T12:30:00Z"
    assert rec.next_event(now)["macro_event_id"] == "usd_empsit_2026-10-02"
    later = datetime(2026, 10, 3, 0, 0, tzinfo=UTC)
    remaining = R.register_official_upcoming(_rec(tmp_path / "later", later), later)
    assert [e["macro_event_id"] for e in remaining] == [
        "usd_cpi_2026-10-14",
        "usd_fomc_statement_2026-10-28",
    ]
    rec2 = _rec(tmp_path / "later2", later)
    R.register_official_upcoming(rec2, later)
    assert rec2.next_event(later)["macro_event_id"] == "usd_cpi_2026-10-14"


def test_t0_48h_and_eleven_checkpoints(tmp_path):
    now = datetime(2026, 9, 28, 21, 30, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    ev = R.register_official_upcoming(rec, now)[0]
    assert ev["observation_window_start_utc"] == "2026-09-30T12:30:00Z"
    times = ev["checkpoints"]
    assert list(times) == [c[0] for c in R.CHECKPOINTS]
    assert len(times) == 11
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
    armed = rec.load_arming()
    assert armed["events"]["usd_empsit_2026-10-02"]["checkpoints"]["T0-48h"] == "2026-09-30T12:30:00Z"


def test_america_new_york_dst_conversion():
    oct_emp = R.local_to_utc(datetime(2026, 10, 2, 8, 30), "America/New_York")
    oct_cpi = R.local_to_utc(datetime(2026, 10, 14, 8, 30), "America/New_York")
    oct_fomc = R.local_to_utc(datetime(2026, 10, 28, 14, 0), "America/New_York")
    nov_est = R.local_to_utc(datetime(2026, 11, 10, 8, 30), "America/New_York")
    jan_est = R.local_to_utc(datetime(2026, 1, 13, 8, 30), "America/New_York")
    assert R.to_utc_iso(oct_emp) == "2026-10-02T12:30:00Z"
    assert R.to_utc_iso(oct_cpi) == "2026-10-14T12:30:00Z"
    assert R.to_utc_iso(oct_fomc) == "2026-10-28T18:00:00Z"
    assert R.to_utc_iso(nov_est) == "2026-11-10T13:30:00Z"
    assert R.to_utc_iso(jan_est) == "2026-01-13T13:30:00Z"


def test_pre_window_and_collecting_states(tmp_path):
    rec = _rec(tmp_path, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    R.register_official_upcoming(rec, rec.now())
    assert rec.derive_status("usd_empsit_2026-10-02", datetime(2026, 9, 28, 21, 30, tzinfo=UTC)) == "PRE_WINDOW"
    assert rec.derive_status("usd_empsit_2026-10-02", datetime(2026, 9, 30, 12, 30, tzinfo=UTC)) == "COLLECTING_PRE_RELEASE"
    assert rec.derive_status("usd_empsit_2026-10-02", datetime(2026, 10, 1, 12, 30, tzinfo=UTC)) == "COLLECTING_PRE_RELEASE"


def test_checkpoint_future_due_and_missed(tmp_path):
    rec = _rec(tmp_path, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    ev = R.register_official_upcoming(rec, rec.now())[0]
    future_rows = rec.checkpoint_status_rows(ev, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    assert {r["status"] for r in future_rows} == {"FUTURE"}
    due_now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    due_rows = rec.checkpoint_status_rows(ev, due_now)
    by = {r["checkpoint_id"]: r["status"] for r in due_rows}
    assert by["T0-48h"] == "DUE"
    assert by["T0-36h"] == "FUTURE"
    missed_now = datetime(2026, 10, 2, 0, 30, tzinfo=UTC)
    missed_rows = rec.checkpoint_status_rows(ev, missed_now)
    bym = {r["checkpoint_id"]: r["status"] for r in missed_rows}
    assert bym["T0-48h"] == "MISSED_NOT_OBSERVED"
    assert bym["T0-36h"] == "MISSED_NOT_OBSERVED"
    assert bym["T0-24h"] == "MISSED_NOT_OBSERVED"
    assert bym["T0-12h"] == "DUE"
    assert bym["T0-6h"] == "FUTURE"
    rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="manual_operator",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"operator genuine 160k",
        observed_at_utc="2026-10-02T00:31:00Z",
        forecast_value=160000,
        unit="persons",
    )
    captured_rows = rec.checkpoint_status_rows(ev, missed_now)
    byc = {r["checkpoint_id"]: r["status"] for r in captured_rows}
    assert byc["T0-12h"] == "CAPTURED"
    assert byc["T0-24h"] == "MISSED_NOT_OBSERVED"


def test_cli_cannot_backdate_observed_at(tmp_path):
    rec = _rec(tmp_path, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    R.register_official_upcoming(rec, rec.now())
    with pytest.raises(SystemExit, match="OPERATOR_BACKDATE_FORBIDDEN"):
        CLI.main(
            [
                "--root",
                str(tmp_path),
                "ingest",
                "--event",
                "usd_empsit_2026-10-02",
                "--source-id",
                "manual_operator",
                "--expectation-type",
                "SURVEY_CONSENSUS",
                "--series",
                "nonfarm_payroll_change",
                "--forecast-value",
                "160000",
                "--unit",
                "persons",
                "--text",
                "should not land",
                "--observed-at-utc",
                "2026-09-01T00:00:00Z",
            ]
        )
    assert rec.load_observations() == []


def test_operator_ingest_uses_recorder_clock_and_pre_t0_rules(tmp_path):
    clock = _Clock(datetime(2026, 10, 1, 12, 0, tzinfo=UTC))
    rec = R.bootstrap_store(tmp_path, clock=clock)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_local="2026-10-02T08:30:00",
        scheduled_timezone="America/New_York",
        official_source="BLS",
    )
    with pytest.raises(R.RecorderClosed, match="OPERATOR_BACKDATE_FORBIDDEN"):
        rec.operator_ingest(
            macro_event_id="usd_empsit_2026-10-02",
            source_id="manual_operator",
            series_name="nonfarm_payroll_change",
            expectation_type="SURVEY_CONSENSUS",
            artifact_bytes=b"backdate attempt",
            observed_at_utc="2026-09-01T00:00:00Z",
            forecast_value=1,
            unit="persons",
        )
    out = rec.operator_ingest(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="manual_operator",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"clocked 175k",
        forecast_value=175000,
        unit="persons",
        reference_period="2026-09",
    )
    obs = out["observation"]
    assert obs["observed_at_utc"] == "2026-10-01T12:00:00Z"
    assert obs["pre_release"] is True
    assert obs["associated_checkpoint_id"] == "T0-36h"
    assert obs["observed_at_utc"] != obs["checkpoint_utc"]
    t0 = R.parse_utc("2026-10-02T12:30:00Z")
    assert R.is_pre_release(R.parse_utc("2026-10-02T12:29:59Z"), t0) is True
    assert R.is_pre_release(R.parse_utc("2026-10-02T12:30:00Z"), t0) is False
    assert R.is_pre_release(R.parse_utc("2026-10-02T12:30:01Z"), t0) is False
    eq = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="manual_operator",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"at T0",
        observed_at_utc="2026-10-02T12:30:00Z",
        forecast_value=175000,
        unit="persons",
    )
    after = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="manual_operator",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"after T0",
        observed_at_utc="2026-10-02T12:31:00Z",
        forecast_value=175000,
        unit="persons",
    )
    assert eq["observation"]["pre_release"] is False
    assert eq["observation"]["prospective_pit_status"] == "OBSERVED_POST_T0"
    assert after["observation"]["pre_release"] is False
    final = rec.final_pre_release_observation(
        "usd_empsit_2026-10-02", series_name="nonfarm_payroll_change", source_id="manual_operator"
    )
    assert final["observed_at_utc"] == "2026-10-01T12:00:00Z"
    assert final["observation_id"] == obs["observation_id"]


def test_artifact_hash_reuse_and_new_vintage(tmp_path):
    rec = _rec(tmp_path, datetime(2026, 10, 1, 12, 0, tzinfo=UTC))
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    a = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="reuters",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"reuters 175k",
        observed_at_utc="2026-10-01T12:30:00Z",
        forecast_value=175000,
        unit="persons",
    )
    b = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="reuters",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"reuters 175k",
        observed_at_utc="2026-10-02T06:30:00Z",
        forecast_value=175000,
        unit="persons",
    )
    c = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="reuters",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"reuters 165k",
        observed_at_utc="2026-10-02T10:30:00Z",
        forecast_value=165000,
        unit="persons",
    )
    assert a["observation"]["raw_artifact_hash"] == b["observation"]["raw_artifact_hash"]
    assert c["observation"]["raw_artifact_hash"] != a["observation"]["raw_artifact_hash"]
    assert len(rec.load_observations()) == 3
    files = list((tmp_path / "artifacts").glob("*"))
    assert len(files) == 2


def test_restart_idempotent_conflict_and_autonomous_disabled(tmp_path):
    rec = _rec(tmp_path, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    R.register_official_upcoming(rec, rec.now())
    first = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="manual_operator",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"same payload",
        observed_at_utc="2026-10-01T12:30:00Z",
        forecast_value=160000,
        unit="persons",
    )
    again = rec.ingest_manual(
        macro_event_id="usd_empsit_2026-10-02",
        source_id="manual_operator",
        series_name="nonfarm_payroll_change",
        expectation_type="SURVEY_CONSENSUS",
        artifact_bytes=b"same payload",
        observed_at_utc="2026-10-01T12:30:00Z",
        forecast_value=160000,
        unit="persons",
    )
    assert first["status"] == "RECORDED"
    assert again["status"] == "ALREADY_EXISTS"
    with pytest.raises(R.RecorderConflict, match="CONFLICT"):
        rec.ingest_manual(
            macro_event_id="usd_empsit_2026-10-02",
            source_id="manual_operator",
            series_name="nonfarm_payroll_change",
            expectation_type="SURVEY_CONSENSUS",
            artifact_bytes=b"different payload",
            observed_at_utc="2026-10-01T12:30:00Z",
            forecast_value=150000,
            unit="persons",
        )
    recon = R.ProspectiveRecorder(tmp_path, clock=_Clock(datetime(2026, 9, 28, 21, 30, tzinfo=UTC))).reconstruct()
    assert len(recon["events"]) == 3
    assert recon["events"][0]["checkpoints"]["T0-48h"] == "2026-09-30T12:30:00Z"
    assert len(recon["observations"]) == 1
    assert recon["armed_checkpoints"]["events"]["usd_empsit_2026-10-02"]["armed"] is True
    src = rec.source_by_id("reuters")
    assert src["enabled"] is False
    assert rec.collection_enabled() is False
    with pytest.raises(R.RecorderClosed, match="FORWARD_CONSENSUS_COLLECTION_ENABLED is false"):
        rec.ingest_autonomous(
            macro_event_id="usd_empsit_2026-10-02",
            source_id="reuters",
            series_name="nonfarm_payroll_change",
            expectation_type="SURVEY_CONSENSUS",
            artifact_bytes=b"no scrape",
            observed_at_utc="2026-10-01T12:30:00Z",
            forecast_value=160000,
            unit="persons",
        )


def test_status_and_due_are_local_only(tmp_path, monkeypatch):
    rec = _rec(tmp_path, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    R.register_official_upcoming(rec, rec.now())

    def _boom(*_a, **_k):
        raise AssertionError("external request is forbidden from status/due")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    text = rec.format_status()
    due = rec.format_due()
    assert "NEXT EVENT:" in text
    assert "usd_empsit_2026-10-02" in text
    assert "AUTONOMOUS COLLECTION:" in text
    assert "OFF" in text
    assert "TRADING AUTHORITY:" in text
    assert "EXTERNAL REQUESTS:" in text
    assert rec.status_payload()["external_requests"] == 0
    assert rec.due_payload()["external_requests"] == 0
    assert "NO CHECKPOINTS/EVENTS REQUIRE OPERATOR ATTENTION NOW" in due
    rec2 = R.ProspectiveRecorder(tmp_path, clock=_Clock(datetime(2026, 9, 30, 12, 31, tzinfo=UTC)))
    due2 = rec2.format_due()
    assert "DUE: T0-48h" in due2
    src = Path("reports/decision_quality/_macro_prospective_recorder.py").read_text(encoding="utf-8")
    cli = Path("reports/decision_quality/macro_prospective_cli.py").read_text(encoding="utf-8")
    for blob in (src, cli):
        assert "urllib.request" not in blob
        assert "requests.get" not in blob
        assert "httpx" not in blob
    assert CLI.main(["--root", str(tmp_path), "status"]) == 0
    assert CLI.main(["--root", str(tmp_path), "due"]) == 0


def test_no_fake_observations_in_real_registry_and_no_trading_authority():
    obs_path = REAL_ROOT / "observations" / "observations.jsonl"
    text = obs_path.read_text(encoding="utf-8") if obs_path.exists() else ""
    assert text.strip() == ""
    events = json.loads((REAL_ROOT / "events" / "events.json").read_text(encoding="utf-8") or "[]")
    for ev in events:
        assert not str(ev.get("macro_event_id", "")).startswith("fixture_")
        notes = ev.get("notes") or ""
        assert "DRY-RUN FIXTURE" not in notes
    src = Path("reports/decision_quality/_macro_prospective_recorder.py").read_text(encoding="utf-8")
    cli = Path("reports/decision_quality/macro_prospective_cli.py").read_text(encoding="utf-8")
    for name in R.FORBIDDEN_PRODUCTION_IMPORTS:
        assert ("import %s" % name) not in src
        assert ("from %s" % name) not in src
        assert ("import %s" % name) not in cli
        assert ("from %s" % name) not in cli
    loop = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert "macro_prospective_cli" not in loop
    assert "_macro_prospective_recorder" not in loop
    cfg = json.loads((REAL_ROOT / "config.json").read_text(encoding="utf-8"))
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False


def test_first_print_path_ready_without_writing_real_data(tmp_path):
    rec = _rec(tmp_path, datetime(2026, 10, 2, 12, 31, tzinfo=UTC))
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    out = rec.capture_first_print(
        macro_event_id="usd_empsit_2026-10-02",
        series_name="nonfarm_payroll_change",
        actual_first_print=110000,
        artifact_bytes=b"BLS first print placeholder in tmp only",
        first_observed_at_utc="2026-10-02T12:31:00Z",
        unit="persons",
        seasonal_adjustment="SA",
        source_id="bls_official",
    )
    assert out["status"] == "RECORDED"
    assert rec.event_by_id("usd_empsit_2026-10-02") is not None


def test_host_store_is_not_a_bot_container_path():
    """Recorder runtime is the host relative tree. Bot image/compose do not hold it."""
    assert str(R.DEFAULT_ROOT).replace("\\", "/") == "data/research/macro/consensus_pit/prospective"
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "./data/research/v2_shadow:/app/data/research/v2_shadow" in compose
    assert "consensus_pit/prospective" not in compose
    assert "COPY reports" not in dockerfile
    assert "COPY data" not in dockerfile
    assert "COPY forex_bot ./forex_bot" in dockerfile
    loop = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert "macro_prospective" not in loop
    assert (REAL_ROOT / "events" / "events.json").exists()
    events = json.loads((REAL_ROOT / "events" / "events.json").read_text(encoding="utf-8"))
    ids = [e["macro_event_id"] for e in events]
    assert "usd_empsit_2026-10-02" in ids
    assert not (REAL_ROOT / "persistence_test").exists()
