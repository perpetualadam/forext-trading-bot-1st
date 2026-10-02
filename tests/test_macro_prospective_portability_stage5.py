"""Stage 5 portability. Research-only. No OANDA / trading / source enablement."""

from __future__ import annotations

import importlib.util
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

_RPATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_RSPEC = importlib.util.spec_from_file_location("macro_prospective_recorder", _RPATH)
R = importlib.util.module_from_spec(_RSPEC)
_RSPEC.loader.exec_module(R)

_SPATH = Path("reports/decision_quality/_macro_prospective_scheduler.py")
_SSPEC = importlib.util.spec_from_file_location("macro_prospective_scheduler", _SPATH)
S = importlib.util.module_from_spec(_SSPEC)
_SSPEC.loader.exec_module(S)

_CPATH = Path("reports/decision_quality/macro_prospective_cli.py")
_CSPEC = importlib.util.spec_from_file_location("macro_prospective_cli", _CPATH)
CLI = importlib.util.module_from_spec(_CSPEC)
_CSPEC.loader.exec_module(CLI)

UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
CORE_PY = (
    Path("reports/decision_quality/_macro_prospective_recorder.py"),
    Path("reports/decision_quality/_macro_prospective_scheduler.py"),
    Path("reports/decision_quality/_macro_prospective_adapters.py"),
    Path("reports/decision_quality/macro_prospective_cli.py"),
)
WRAPPERS = (
    Path("scripts/run_macro_prospective_collect_due.sh"),
    Path("deploy/systemd/forex-macro-prospective.service"),
    Path("deploy/systemd/forex-macro-prospective.timer"),
    Path("deploy/cron/forex-macro-prospective.cron"),
    Path("deploy/docker/collect-due.example.sh"),
)
EVENT_LOGIC_TOKENS = (
    "T0-48h",
    "MISSED_NOT_OBSERVED",
    "checkpoint_utc",
    "observed_at_utc",
    "usd_empsit",
)


class _Clock:
    def __init__(self, dt):
        self.dt = dt

    def __call__(self):
        return self.dt


def _rec(tmp_path, now):
    return R.bootstrap_store(tmp_path, clock=_Clock(now))


def test_windows_and_posix_and_env_data_root(tmp_path, monkeypatch):
    win = R.resolve_data_root(r"C:\research\macro\prospective")
    posix = R.resolve_data_root("/opt/forex-bot/data/research/macro/consensus_pit/prospective")
    assert str(win) == str(Path(r"C:\research\macro\prospective"))
    assert str(posix) == str(Path("/opt/forex-bot/data/research/macro/consensus_pit/prospective"))
    default = R.resolve_data_root(env={})
    assert default.as_posix().endswith("data/research/macro/consensus_pit/prospective")
    assert default.is_absolute()
    assert R.DEFAULT_ROOT.as_posix() == "data/research/macro/consensus_pit/prospective"
    override = tmp_path / "override_store"
    monkeypatch.setenv(R.DATA_DIR_ENV, str(override))
    resolved = R.resolve_data_root()
    assert resolved == override
    rec = CLI._recorder(None)
    assert rec.root == override
    explicit = tmp_path / "explicit"
    assert CLI._recorder(str(explicit)).root == explicit


def test_utc_checkpoints_independent_of_host_timezone():
    t0 = R.parse_utc("2026-10-02T12:30:00Z")
    expected = R.all_checkpoint_times(t0)
    assert expected["T0-48h"] == "2026-09-30T12:30:00Z"
    assert expected["T0-5m"] == "2026-10-02T12:25:00Z"
    if hasattr(time, "tzset"):
        previous = os.environ.get("TZ")
        try:
            for zone in ("UTC", "Europe/London", "America/New_York", "Pacific/Kiritimati"):
                os.environ["TZ"] = zone
                time.tzset()
                assert R.all_checkpoint_times(t0) == expected
        finally:
            if previous is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = previous
            time.tzset()
    march = R.parse_utc("2026-03-08T12:30:00Z")
    assert R.all_checkpoint_times(march)["T0-48h"] == "2026-03-06T12:30:00Z"
    ny_local = datetime(2026, 10, 2, 8, 30)
    from_ny = R.local_to_utc(ny_local, "America/New_York")
    london_view = from_ny.astimezone(ZoneInfo("Europe/London"))
    assert R.to_utc_iso(from_ny) == "2026-10-02T12:30:00Z"
    assert R.all_checkpoint_times(london_view) == expected


def test_collect_due_os_independent_and_zero_requests(tmp_path):
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
    summary = S.ProspectiveScheduler(rec).collect_due()
    assert summary["external_requests"] == 0
    assert rec.collection_enabled() is False
    assert rec.load_observations() == []
    assert any(a.get("result") == "NO_ENABLED_SOURCE" for a in summary["actions"])


def test_portable_lock_busy_stale_and_atomic_tmp_cannot_corrupt(tmp_path):
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
    lock.release()
    sched.lock_path.write_text(
        json.dumps({"pid": 999999, "heartbeat_utc": "2026-09-30T10:00:00Z", "started_utc": "2026-09-30T10:00:00Z"}),
        encoding="utf-8",
    )
    stale = S.ProcessLock(sched.lock_path, rec.now)
    assert stale.acquire() == "STALE_RECOVERED"
    stale.release()
    original = {"last_run_utc": "2026-09-30T12:00:00Z", "processed": {"keep": True}}
    S.atomic_write_json(sched.state_path, original)
    leftover = sched.state_path.parent / (sched.state_path.name + ".tmp")
    leftover.write_text("{not-json", encoding="utf-8")
    pid_tmp = sched.state_path.parent / ("%s.1.tmp" % sched.state_path.name)
    pid_tmp.write_text("{also-not-json", encoding="utf-8")
    loaded = sched.load_state()
    assert loaded["last_run_utc"] == "2026-09-30T12:00:00Z"
    assert loaded["processed"] == {"keep": True}
    src = Path("reports/decision_quality/_macro_prospective_scheduler.py").read_text(encoding="utf-8")
    assert "ctypes" not in src
    assert "windll" not in src
    assert "fcntl" not in src
    assert "msvcrt" not in src


def test_wrappers_have_no_event_logic_and_set_workdir_interval():
    service = Path("deploy/systemd/forex-macro-prospective.service").read_text(encoding="utf-8")
    timer = Path("deploy/systemd/forex-macro-prospective.timer").read_text(encoding="utf-8")
    cron = Path("deploy/cron/forex-macro-prospective.cron").read_text(encoding="utf-8")
    wrapper = Path("scripts/run_macro_prospective_collect_due.sh").read_text(encoding="utf-8")
    docker = Path("deploy/docker/collect-due.example.sh").read_text(encoding="utf-8")
    installer = Path("scripts/install_macro_prospective_task.ps1").read_text(encoding="utf-8")
    for path in WRAPPERS:
        text = path.read_text(encoding="utf-8")
        for tok in EVENT_LOGIC_TOKENS:
            assert tok not in text
        assert "OrderCreate" not in text
        assert "oanda" not in text.lower()
    assert "Type=oneshot" in service
    assert "WorkingDirectory=/path/to/forex-bot" in service
    assert "macro_prospective_cli collect-due" in service
    assert "OnUnitActiveSec=5min" in timer
    assert "Persistent=true" in timer
    assert "*/5 * * * *" in cron
    assert "run_macro_prospective_collect_due.sh" in cron
    assert "cd --" in wrapper or "cd " in wrapper
    assert "collect-due" in wrapper
    assert "WorkingDirectory" in installer
    assert "New-TimeSpan -Minutes 5" in installer
    assert "collect-due" in installer
    spec = S.installer_spec(python_executable="python", workdir=str(Path(".").resolve()))
    assert spec["interval_minutes"] == 5
    assert spec["arguments"].endswith("collect-due")


def test_core_python_has_no_host_paths_or_os_scheduler_imports():
    for path in CORE_PY:
        src = path.read_text(encoding="utf-8")
        assert "C:\\" not in src
        assert "WindowsApps" not in src
        assert "schtasks" not in src
        assert "Register-ScheduledTask" not in src
        assert "systemctl" not in src
        assert "crontab" not in src
        assert "Brian" not in src
        assert "ctypes" not in src
        for name in S.FORBIDDEN_PRODUCTION_IMPORTS:
            assert ("import %s" % name) not in src
            assert ("from %s" % name) not in src
    loop = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert "macro_prospective" not in loop


def test_autonomous_disabled_real_registry_observations_unchanged():
    cfg = json.loads((REAL_ROOT / "config.json").read_text(encoding="utf-8"))
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    rec = R.ProspectiveRecorder(REAL_ROOT)
    assert rec.collection_enabled() is False
    events = json.loads((REAL_ROOT / "events" / "events.json").read_text(encoding="utf-8"))
    assert [e["macro_event_id"] for e in events] == [
        "usd_empsit_2026-10-02",
        "usd_cpi_2026-10-14",
        "usd_fomc_statement_2026-10-28",
    ]
    obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(ln) for ln in obs.splitlines() if ln.strip()]
    assert {r["associated_checkpoint_id"] for r in rows} <= {"T0-48h", "T0-24h", "T0-12h"}
    for row in rows:
        assert row["macro_event_id"] == "usd_empsit_2026-10-02"
        assert row["expectation_type"] == "SURVEY_CONSENSUS"
        assert row["retrieval_method"] == "manual"
    src = rec.source_by_id("trading_economics")
    assert src["enabled"] is False
    assert src.get("automation_class") != "APPROVED_AUTOMATION_READY"
    A_PATH = Path("reports/decision_quality/_macro_prospective_adapters.py")
    aspec = importlib.util.spec_from_file_location("macro_prospective_adapters", A_PATH)
    A = importlib.util.module_from_spec(aspec)
    aspec.loader.exec_module(A)
    assert A.SOURCE_AUDIT
    assert not any(row["classification"] == "APPROVED_AUTOMATION_READY" for row in A.SOURCE_AUDIT)
    bls = A.OfficialBlsFirstPrintAdapter()
    assert bls.is_enabled(rec)[0] is False
