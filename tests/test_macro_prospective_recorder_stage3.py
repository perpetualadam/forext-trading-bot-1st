"""Prospective macro recorder Stage 3 scheduler. Research-only. No bot_loop / OANDA / Telegram."""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_PATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_SPEC = importlib.util.spec_from_file_location("macro_prospective_recorder", _PATH)
R = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(R)

_SPATH = Path("reports/decision_quality/_macro_prospective_scheduler.py")
_SSPEC = importlib.util.spec_from_file_location("macro_prospective_scheduler", _SPATH)
S = importlib.util.module_from_spec(_SSPEC)
assert _SSPEC is not None and _SSPEC.loader is not None
_SSPEC.loader.exec_module(S)

_CLI_PATH = Path("reports/decision_quality/macro_prospective_cli.py")
_CLI_SPEC = importlib.util.spec_from_file_location("macro_prospective_cli", _CLI_PATH)
CLI = importlib.util.module_from_spec(_CLI_SPEC)
assert _CLI_SPEC is not None and _CLI_SPEC.loader is not None
_CLI_SPEC.loader.exec_module(CLI)

UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
INSTALLER = Path("scripts/install_macro_prospective_task.ps1")
VERIFY = Path("scripts/verify_macro_prospective_task.ps1")


class _Clock:
    def __init__(self, dt: datetime):
        self.dt = dt

    def __call__(self) -> datetime:
        return self.dt


class _CountingAdapter(S.NeverFetchAdapter):
    def __init__(self, source_id: str):
        super().__init__(source_id)
        self.collect_calls = 0

    def collect(self, event, checkpoint, now):
        self.collect_calls += 1
        return super().collect(event, checkpoint, now)


class _FakeSuccessAdapter(S.CollectionAdapter):
    source_id = "fixture_provider_a"

    def __init__(self):
        self.collect_calls = 0

    def collect(self, event, checkpoint, now):
        self.collect_calls += 1
        return S.CollectionResult(
            status="SUCCESS",
            source_id=self.source_id,
            external_request=True,
            artifact_bytes=b"test-only 175000 persons SA",
            series_name="nonfarm_payroll_change",
            expectation_type="SURVEY_CONSENSUS",
            forecast_value=175000,
            unit="persons",
            reference_period=event.get("reference_period"),
            notes="tmp adapter only",
        )


def _rec(tmp_path: Path, now: datetime):
    return R.bootstrap_store(tmp_path, clock=_Clock(now))


def _enable_fixture_a(rec: R.ProspectiveRecorder) -> None:
    rec.config_path.write_text(json.dumps({R.FORWARD_FLAG: True}, indent=2) + "\n", encoding="utf-8")
    blob = rec.load_registry()
    for src in blob["sources"]:
        if src.get("source_id") == "fixture_provider_a":
            src["enabled"] = True
            src["automated_collection_permitted"] = True
    rec.registry_path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")


def _files_snapshot(root: Path) -> dict[str, str]:
    out = {}
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[str(p.relative_to(root)).replace("\\", "/")] = p.read_bytes().hex()
    return out


def test_no_active_event_no_work_zero_requests(tmp_path):
    now = datetime(2026, 9, 28, 21, 30, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    R.register_official_upcoming(rec, now)
    adapter = _CountingAdapter("reuters")
    sched = S.ProspectiveScheduler(rec, adapters=[adapter])
    summary = sched.collect_due()
    assert summary["exit_code"] == 0
    assert summary["external_requests"] == 0
    assert adapter.collect_calls == 0
    assert any(a.get("status") == "NO_EVENT_ACTIVE" for a in summary["actions"])
    assert rec.load_observations() == []


def test_due_checkpoint_recognized_and_predefined_only(tmp_path):
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    sched = S.ProspectiveScheduler(rec)
    summary = sched.collect_due()
    due_actions = [a for a in summary["actions"] if a.get("status") == "CHECKPOINT_DUE"]
    assert due_actions
    assert due_actions[0]["checkpoint_id"] == "T0-48h"
    ids = [a.get("checkpoint_id") for a in summary["actions"] if a.get("checkpoint_id")]
    assert set(ids) <= set(S.CHECKPOINT_IDS)
    assert "T0" not in ids


def test_disabled_unknown_and_global_flag_make_zero_requests(tmp_path):
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    adapters = [_CountingAdapter("reuters"), _CountingAdapter("factset_insight"), _CountingAdapter("missing_source")]
    sched = S.ProspectiveScheduler(rec, adapters=adapters)
    summary = sched.collect_due()
    assert rec.collection_enabled() is False
    src = rec.source_by_id("reuters")
    assert src["enabled"] is False
    assert src["automated_collection_permitted"] != True
    assert summary["external_requests"] == 0
    assert all(a.collect_calls == 0 for a in adapters)
    due = [a for a in summary["actions"] if a.get("status") == "CHECKPOINT_DUE"][0]
    assert due["result"] == "NO_ENABLED_SOURCE"
    assert due["observation"] == "NO_OBSERVATION_RECORDED"
    assert rec.load_observations() == []
    assert list((tmp_path / "artifacts").glob("*")) == []


def test_due_processed_once_and_repeat_idempotent(tmp_path):
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    sched = S.ProspectiveScheduler(rec)
    first = sched.collect_due()
    second = sched.collect_due()
    assert first["exit_code"] == 0
    assert any(a.get("result") == "NO_ENABLED_SOURCE" for a in first["actions"])
    assert any(a.get("status") == "ALREADY_PROCESSED" for a in second["actions"])
    assert rec.load_observations() == []
    recon = S.ProspectiveScheduler(R.ProspectiveRecorder(tmp_path, clock=_Clock(now))).reconstruct()
    assert "usd_empsit_2026-10-02|T0-48h" in recon["state"]["processed"]


def test_overlapping_events_processed_independently(tmp_path):
    now = datetime(2026, 9, 30, 14, 1, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    rec.register_event(
        macro_event_id="usd_cpi_2026-10-02",
        event_family="CPI",
        event_name="Consumer Price Index",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T14:00:00Z",
        official_source="BLS",
    )
    summary = S.ProspectiveScheduler(rec).collect_due()
    due = {(a["macro_event_id"], a["checkpoint_id"]) for a in summary["actions"] if a.get("status") == "CHECKPOINT_DUE"}
    assert ("usd_empsit_2026-10-02", "T0-48h") in due
    assert ("usd_cpi_2026-10-02", "T0-48h") in due


def test_observed_at_preserved_not_backdated(tmp_path):
    now = datetime(2026, 9, 30, 12, 34, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    _enable_fixture_a(rec)
    fake = _FakeSuccessAdapter()
    summary = S.ProspectiveScheduler(rec, adapters=[fake]).collect_due()
    obs = rec.load_observations()
    assert fake.collect_calls == 1
    assert len(obs) == 1
    assert obs[0]["observed_at_utc"] == "2026-09-30T12:34:00Z"
    assert obs[0]["checkpoint_utc"] == "2026-09-30T12:30:00Z"
    assert obs[0]["observed_at_utc"] != obs[0]["checkpoint_utc"]
    assert obs[0]["raw_artifact_hash"] == R.sha256_bytes(b"test-only 175000 persons SA")
    assert (tmp_path / "artifacts" / ("%s.txt" % obs[0]["raw_artifact_hash"])).exists() or list((tmp_path / "artifacts").glob(obs[0]["raw_artifact_hash"] + "*"))
    due = [a for a in summary["actions"] if a.get("status") == "CHECKPOINT_DUE"][0]
    assert due["observed_at_utc"] == "2026-09-30T12:34:00Z"


def test_expired_interval_missed_not_backfilled(tmp_path):
    now = datetime(2026, 10, 1, 12, 35, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    adapter = _CountingAdapter("reuters")
    summary = S.ProspectiveScheduler(rec, adapters=[adapter]).collect_due()
    missed = [a for a in summary["actions"] if a.get("status") == "CHECKPOINT_MISSED"]
    ids = {a["checkpoint_id"] for a in missed}
    assert "T0-48h" in ids
    assert "T0-36h" in ids
    due = [a for a in summary["actions"] if a.get("status") == "CHECKPOINT_DUE"]
    assert any(a.get("checkpoint_id") == "T0-24h" and a.get("result") == "NO_ENABLED_SOURCE" for a in due)
    assert adapter.collect_calls == 0
    assert rec.load_observations() == []
    rows = {r["checkpoint_id"]: r["status"] for r in rec.checkpoint_status_rows(rec.event_by_id("usd_empsit_2026-10-02"), now)}
    assert rows["T0-48h"] == "MISSED_NOT_OBSERVED"


def test_atomic_state_write_recovery(tmp_path):
    now = datetime(2026, 9, 28, 21, 30, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    sched = S.ProspectiveScheduler(rec)
    original = {"last_run_utc": "2026-09-28T21:00:00Z", "processed": {"x": 1}}
    S.atomic_write_json(sched.state_path, original)
    tmp = sched.state_path.with_name(sched.state_path.name + ".tmp")
    tmp.write_text("{not-json", encoding="utf-8")
    loaded = sched.load_state()
    assert loaded["last_run_utc"] == "2026-09-28T21:00:00Z"
    assert loaded["processed"] == {"x": 1}


def test_process_lock_busy_and_stale_recovery(tmp_path):
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    sched = S.ProspectiveScheduler(rec)
    lock = S.ProcessLock(sched.lock_path, rec.now)
    assert lock.acquire() == "OWNED"
    busy = S.ProspectiveScheduler(rec).collect_due()
    assert busy["lock"] == "BUSY"
    assert any(a.get("status") == "LOCK_BUSY" for a in busy["actions"])
    lock.release()

    stale = S.ProcessLock(sched.lock_path, rec.now)
    sched.lock_path.parent.mkdir(parents=True, exist_ok=True)
    sched.lock_path.write_text(
        json.dumps(
            {
                "pid": 999999,
                "started_utc": "2026-09-30T10:00:00Z",
                "heartbeat_utc": "2026-09-30T10:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    assert stale.acquire() == "STALE_RECOVERED"
    stale.release()
    recovered = S.ProspectiveScheduler(rec).collect_due()
    assert recovered["lock"] in {"OWNED", "STALE_RECOVERED"}
    assert recovered["exit_code"] == 0


def test_dry_run_zero_requests_zero_state_changes(tmp_path):
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    before = _files_snapshot(tmp_path)
    adapter = _CountingAdapter("reuters")
    summary = S.ProspectiveScheduler(rec, adapters=[adapter]).collect_due(dry_run=True)
    after = _files_snapshot(tmp_path)
    assert summary["dry_run"] is True
    assert summary["external_requests"] == 0
    assert adapter.collect_calls == 0
    assert rec.load_observations() == []
    assert before == after
    assert not (tmp_path / "scheduler" / "state.json").exists()


def test_status_and_due_remain_read_only(tmp_path, monkeypatch):
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )

    def _boom(*_a, **_k):
        raise AssertionError("external request forbidden")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    obs_before = rec.load_observations()
    text = S.ProspectiveScheduler(rec).format_status()
    due = rec.format_due()
    assert rec.load_observations() == obs_before
    assert not (tmp_path / "scheduler" / "state.json").exists()
    assert "SCHEDULER:" in text
    assert "MANUAL ACTION REQUIRED:" in text
    assert "DUE: T0-48h" in due
    assert CLI.main(["--root", str(tmp_path), "status"]) == 0
    assert CLI.main(["--root", str(tmp_path), "due"]) == 0
    assert CLI.main(["--root", str(tmp_path), "collect-due", "--dry-run"]) == 0


def test_collect_due_cannot_access_trading_and_ingest_semantics_preserved():
    for path in (
        Path("reports/decision_quality/_macro_prospective_scheduler.py"),
        Path("reports/decision_quality/macro_prospective_cli.py"),
        Path("scripts/install_macro_prospective_task.ps1"),
    ):
        src = path.read_text(encoding="utf-8")
        for name in S.FORBIDDEN_PRODUCTION_IMPORTS:
            assert ("import %s" % name) not in src
            assert ("from %s" % name) not in src
        assert "urllib.request" not in src
        assert "requests.get" not in src
        assert "httpx" not in src
        assert "oanda_exec" not in src
        assert "OrderCreate" not in src
    loop = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert "macro_prospective_scheduler" not in loop
    assert "macro_prospective_cli" not in loop


def test_windows_installer_resolves_python_workdir_interval_and_is_not_executed():
    text = INSTALLER.read_text(encoding="utf-8")
    verify = VERIFY.read_text(encoding="utf-8")
    assert "import sys; print(sys.executable)" in text
    assert r"C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st" in text
    assert "WorkingDirectory" in text
    assert "New-TimeSpan -Minutes 5" in text
    assert "collect-due" in text
    assert "Register-ScheduledTask" in text
    assert "IgnoreNew" in text
    assert "StartWhenAvailable" in text
    assert "Get-ScheduledTask" in verify
    spec = S.installer_spec(
        python_executable=r"C:\Python313\python.exe",
        workdir=r"C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st",
    )
    assert spec["interval_minutes"] == 5
    assert spec["python_executable"] == r"C:\Python313\python.exe"
    assert spec["working_directory"].replace("/", "\\").endswith("Forext Trading Bot 1st")
    assert spec["arguments"].endswith("collect-due")
    assert spec["installs_during_tests"] is False


def test_real_registry_untouched_no_fake_observations():
    obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8") if (REAL_ROOT / "observations" / "observations.jsonl").exists() else ""
    assert obs.strip() == ""
    events = json.loads((REAL_ROOT / "events" / "events.json").read_text(encoding="utf-8"))
    assert [e["macro_event_id"] for e in events] == [
        "usd_empsit_2026-10-02",
        "usd_cpi_2026-10-14",
        "usd_fomc_statement_2026-10-28",
    ]
    cfg = json.loads((REAL_ROOT / "config.json").read_text(encoding="utf-8"))
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    marker = REAL_ROOT / "scheduler" / "windows_task_installed.json"
    if marker.exists():
        blob = json.loads(marker.read_text(encoding="utf-8-sig"))
        assert blob.get("task_name") == "ForexMacroProspectiveCollectDue"
    else:
        assert cfg.get("windows_task_installed") is False


def test_cli_collect_due_dry_run_on_tmp(tmp_path):
    now = datetime(2026, 9, 28, 21, 30, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    R.register_official_upcoming(rec, now)
    rc = CLI.main(["--root", str(tmp_path), "collect-due", "--dry-run"])
    assert rc == 0
    assert rec.load_observations() == []
    assert not (tmp_path / "scheduler" / "state.json").exists()
