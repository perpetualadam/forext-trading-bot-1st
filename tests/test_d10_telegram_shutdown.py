"""Stage D.10 Telegram shutdown checks. This module does not import app.py."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).resolve().parent / "d10_telegram_shutdown_runner.py"
EXPECTED = {
    "forex_bot/app.py": (
        "08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44"
    ),
    "forex_bot/database.py": (
        "cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e"
    ),
    "forex_bot/telegram_control.py": (
        "270f2b48bbbc1c50b1bb89ae338716803c5e2772fada3b1aa39153fb8b300014"
    ),
    "forex_bot/live_safety.py": (
        "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44"
    ),
    "forex_bot/strategy_meta.py": (
        "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d"
    ),
}


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
        "PYTEST_CURRENT_TEST": "d10-isolated",
        "LIVE_SAFETY_STATE_PATH": str(safety),
        "D10_WORK_DIR": str(work),
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
        "TELEGRAM_TOKEN": "d10-synthetic-token",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "1001",
        "DISCORD_WEBHOOK_URL": "",
        "POSTGRES_HOST": "d10-invalid-host",
        "POSTGRES_PORT": "1",
        "POSTGRES_USER": "d10",
        "POSTGRES_PASSWORD": "",
        "POSTGRES_PASS": "",
        "POSTGRES_DB": "d10",
    }


def run_d10(tmp_path_factory: pytest.TempPathFactory, mode: str) -> dict:
    for rel, digest in EXPECTED.items():
        assert _sha(ROOT / rel) == digest
    work = tmp_path_factory.mktemp(f"d10-{mode}")
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
    return payload


def _sched(report: dict, name: str) -> dict:
    return report["schedules"][name]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d10(tmp_path_factory, "threads")
    assert payload.get("error", "") == "", payload.get("traceback", payload.get("error"))
    assert payload["_returncode"] == 0
    return payload


def test_baseline_hashes_and_guards(report: dict) -> None:
    assert report["commands_enabled"] is True
    assert report["network_after"] == []
    assert report["escaped_final"] == []
    assert all(report["guard_checks"].values())
    assert all(
        "concensus-forecast" in item.replace("\\", "/").lower()
        for item in report["foreign_project_on_path"]
    )
    assert report["active_strategies"] == []
    assert report["open_connections"] == []
    assert report["open_cursors"] == []
    assert report["use_after_close"] == []


def test_stop_before_start_and_normal_stop(report: dict) -> None:
    idle = _sched(report, "stop_before_start")["application"]
    assert idle["return_value"] is None
    assert idle["alive_after"] is False
    normal = _sched(report, "normal_stop")["application"]
    assert normal["alive_after"] is False
    assert normal["elapsed_sec"] < 1.5
    assert normal["stored_thread_cleared"] is True
    assert _sched(report, "normal_stop")["harness"]["escaped"] == []


def test_repeated_stop_and_start(report: dict) -> None:
    again = _sched(report, "repeated_stop")["application"]
    assert again["return_value"] is None
    assert again["alive_after"] is False
    repeated = _sched(report, "repeated_start")["application"]
    assert repeated["thread_count"] == 1
    assert repeated["started_flag"] is True


def test_stop_returns_while_poll_blocked(report: dict) -> None:
    row = _sched(report, "stop_during_blocked_poll")
    stop = row["application_stop"]
    assert stop["alive_after"] is True
    assert stop["elapsed_sec"] >= 1.5
    assert stop["elapsed_sec"] < 5
    assert stop["return_value"] is None
    assert stop["stored_thread_cleared"] is True
    assert stop["started_flag"] is False
    assert stop["stop_event_set"] is True
    assert row["database_after_stop_before_release"]["connection_open"] is True
    assert row["old_closed"] is True
    assert row["queries_after_release"]
    assert row["queries_after_release"][0]["caller"] == "telegram-control"
    assert row["queries_after_release"][0]["caller_alive"] is True
    assert row["new_connection_id"] != row["old_connection_id"]
    assert row["use_after_close"] == []
    assert row["harness"]["escaped"] == []


def test_second_start_overlaps_surviving_worker(report: dict) -> None:
    row = _sched(report, "restart_after_incomplete_stop")
    assert row["application_stop"]["alive_after"] is True
    assert row["application_stop"]["elapsed_sec"] >= 1.5
    assert row["stop_event_after_second_start"] is False
    assert row["thread_count"] >= 2
    assert row["harness"]["escaped"] == []


def test_release_waits_and_foreign_lock(report: dict) -> None:
    waiting = _sched(report, "release_waits_for_locked_query")
    assert waiting["lock_free_while_query_held"] is False
    assert waiting["release_finished_before_query_release"] is False
    assert waiting["release_finished_after"] is True
    assert waiting["harness"]["escaped"] == []
    foreign = _sched(report, "stop_while_other_thread_holds_lock")
    assert foreign["poller_blocked_on_foreign_lock"] is True
    assert foreign["stop_finished_while_foreign_lock_held"] is False
    assert foreign["harness"]["escaped"] == []


def test_direct_reconnect_and_close_failure(report: dict) -> None:
    direct = _sched(report, "direct_helper_after_release")
    assert direct["old_closed"] is True
    assert direct["new_id"] != direct["old_id"]
    assert direct["use_after_close"] == []
    failed = _sched(report, "release_close_failure")
    assert failed["notes"] == ["RuntimeError"]
    assert failed["global_cleared"] is True
    assert failed["object_still_open"] is True
    assert failed["harness_closed"] == 1


def test_initialization_lock_still_serializes(report: dict) -> None:
    row = _sched(report, "init_lock_overlap")
    assert row["connect_delta"] == 1
    assert len(set(row["ids"])) == 1
