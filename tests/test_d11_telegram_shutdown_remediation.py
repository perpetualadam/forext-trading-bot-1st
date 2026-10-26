"""Stage D.11 Telegram shutdown checks. This module does not import app.py."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).resolve().parent / "d11_telegram_shutdown_runner.py"
UNCHANGED = {
    "forex_bot/app.py": (
        "08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44"
    ),
    "forex_bot/database.py": (
        "cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e"
    ),
    "forex_bot/live_safety.py": (
        "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44"
    ),
    "forex_bot/strategy_meta.py": (
        "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d"
    ),
}
OLD_TELEGRAM = "270f2b48bbbc1c50b1bb89ae338716803c5e2772fada3b1aa39153fb8b300014"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _child_env(work: Path, safety: Path) -> dict[str, str]:
    inherited = {
        key: os.environ[key]
        for key in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "TEMP",
            "TMP",
            "SYSTEMDRIVE",
            "APPDATA",
            "LOCALAPPDATA",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
        )
        if key in os.environ
    }
    return {
        **inherited,
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_CURRENT_TEST": "d11-isolated",
        "LIVE_SAFETY_STATE_PATH": str(safety),
        "D11_WORK_DIR": str(work),
        "PAPER_TRADING": "true",
        "EXECUTION_MODE": "paper",
        "TRADING_MODE": "practice",
        "USE_OANDA_LIVE": "false",
        "TELEGRAM_COMMANDS": "1",
        "TELEGRAM_INBOUND": "0",
        "TELEGRAM_POLL_TIMEOUT_SEC": "1",
        "OANDA_ACCESS_TOKEN": "",
        "OANDA_API_KEY": "",
        "OANDA_ACCOUNT_ID": "",
        "TELEGRAM_TOKEN": "d11-synthetic-token",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "1001",
        "DISCORD_WEBHOOK_URL": "",
        "POSTGRES_HOST": "d11-invalid-host",
        "POSTGRES_PORT": "1",
        "POSTGRES_USER": "d11",
        "POSTGRES_PASSWORD": "",
        "POSTGRES_PASS": "",
        "POSTGRES_DB": "d11",
    }


def run_d11(tmp_path_factory: pytest.TempPathFactory, mode: str) -> dict:
    for rel, digest in UNCHANGED.items():
        assert _sha(ROOT / rel) == digest
    telegram = _sha(ROOT / "forex_bot/telegram_control.py")
    assert telegram != OLD_TELEGRAM
    work = tmp_path_factory.mktemp(f"d11-{mode}")
    out = work / "report.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), str(out), mode],
        cwd=str(work),
        env=_child_env(work, work / "safety.json"),
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["_returncode"] = completed.returncode
    payload["_stderr_tail"] = completed.stderr[-2000:]
    payload["_telegram_sha256"] = telegram
    return payload


def _sched(report: dict, name: str) -> dict:
    return report["schedules"][name]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d11(tmp_path_factory, "threads")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_guards_and_safety_defaults(report: dict) -> None:
    assert report["guard_checks"]
    assert all(report["guard_checks"].values())
    assert report["network_after"] == []
    assert report["commands_enabled"] is True
    assert report["active_strategies"] == []
    assert report["authorisation"] == "BLOCKED"
    assert report["escaped_final"] == []
    assert report["open_connections"] == []
    assert report["open_cursors"] == []
    assert report["use_after_close"] == []


def test_s01_normal_stop_completes(report: dict) -> None:
    row = _sched(report, "S01_S05_S11_normal_stop")["application"]
    assert row["return_value"] == "STOP_COMPLETED"
    assert row["alive_after"] is False
    assert row["stored_thread_cleared"] is True
    assert row["elapsed_sec"] < 1.0


def test_s02_stop_before_start(report: dict) -> None:
    row = _sched(report, "S02_stop_before_start")["application"]
    assert row["return_value"] == "STOP_NOT_RUNNING"
    assert row["elapsed_sec"] < 0.5


def test_s03_repeated_stop(report: dict) -> None:
    row = _sched(report, "S03_repeated_stop")["application"]
    assert row["return_value"] == "STOP_NOT_RUNNING"
    assert row["alive_after"] is False


def test_s04_repeated_start_is_single_worker(report: dict) -> None:
    row = _sched(report, "S04_repeated_start")
    assert row["thread_count"] == 1
    assert row["stop_event_set"] is False


def test_s12_blocked_stop_keeps_worker(report: dict) -> None:
    row = _sched(report, "S06_S12_S18_S23_S32_S33_S34")
    stop = row["application_stop"]
    assert stop["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert stop["alive_after"] is True
    assert stop["stored_alive"] is True
    assert stop["stored_thread_cleared"] is False
    assert stop["stop_event_set"] is True
    assert 1.5 <= stop["elapsed_sec"] <= 3.5


def test_s19_restart_after_worker_exit(report: dict) -> None:
    row = _sched(report, "S19_restart_after_exit")
    assert row["event_was_set_before_restart"] is True
    assert row["thread_count"] == 1
    assert row["application_stop"]["return_value"] == "STOP_COMPLETED"
    assert row["application_stop"]["alive_after"] is False


def test_s15_restart_while_alive_does_not_duplicate(report: dict) -> None:
    row = _sched(report, "S15_S16_S17_restart_while_alive")
    stop = row["application_stop"]
    assert stop["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert stop["stored_alive"] is True
    assert row["event_after_second_start"] is True
    assert row["thread_count"] == 1
    assert row["stored_ident_before"] == row["stored_ident_after"]


def test_s20_concurrent_starts(report: dict) -> None:
    row = _sched(report, "S20_concurrent_starts")
    assert row["thread_count"] == 1


def test_s21_concurrent_stops_keep_one_worker(report: dict) -> None:
    row = _sched(report, "S21_concurrent_stops")
    assert row["returns"] == [
        "STOP_INCOMPLETE_WORKER_ALIVE",
        "STOP_INCOMPLETE_WORKER_ALIVE",
    ]
    assert row["stored_alive"] is True
    assert row["thread_count"] == 1
    assert row["stop_event"] is True


def test_s22_concurrent_start_and_stop(report: dict) -> None:
    row = _sched(report, "S22_concurrent_start_and_stop")
    assert row["start_returned"] is True
    assert row["stop"]["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert row["thread_count"] == 1
    assert row["stop_event"] is True


def test_s26_stop_between_updates_skips_database(report: dict) -> None:
    row = _sched(report, "S07_S26_stop_between_updates")
    assert row["queries"] == []
    assert row["connect_delta"] == 0
    assert row["worker"]["escaped"] == []
    assert row["stop"]["return_value"] == "STOP_COMPLETED"


def test_s37_poll_exception_exits_without_query(report: dict) -> None:
    row = _sched(report, "S37_poll_exception_during_shutdown")
    assert row["stop"]["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert row["stop"]["stored_alive"] is True
    assert row["queries"] == []
    assert row["worker"]["escaped"] == []
    assert row["stored_after"] is True


def test_self_stop_does_not_deadlock(report: dict) -> None:
    row = _sched(report, "self_stop_does_not_join_current_thread")
    assert row["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert row["worker_alive"] is False
    assert row["restart_thread_count"] == 1
    assert row["restart_ident"] != row["old_ident"]
