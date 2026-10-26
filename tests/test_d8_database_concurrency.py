"""Stage D.8 concurrency and cleanup checks. This module does not import app.py."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).resolve().parent / "d8_concurrency_runner.py"
EXPECTED = {
    "forex_bot/app.py": (
        "08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44"
    ),
    "forex_bot/database.py": (
        "74bb9f5d692ace88bff525f334d7eb8577427bfe75cf5f229f647e60b88979e9"
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
        "PYTEST_CURRENT_TEST": "d8-isolated",
        "LIVE_SAFETY_STATE_PATH": str(safety),
        "D8_WORK_DIR": str(work),
        "PAPER_TRADING": "true",
        "EXECUTION_MODE": "paper",
        "TRADING_MODE": "practice",
        "USE_OANDA_LIVE": "false",
        "TELEGRAM_COMMANDS": "0",
        "TELEGRAM_INBOUND": "0",
        "OANDA_ACCESS_TOKEN": "",
        "OANDA_API_KEY": "",
        "OANDA_ACCOUNT_ID": "",
        "TELEGRAM_TOKEN": "",
        "TELEGRAM_BOT_TOKEN": "",
        "DISCORD_WEBHOOK_URL": "",
        "POSTGRES_HOST": "d8-invalid-host",
        "POSTGRES_PORT": "1",
        "POSTGRES_USER": "d8",
        "POSTGRES_PASSWORD": "",
        "POSTGRES_PASS": "",
        "POSTGRES_DB": "d8",
    }


def _run(tmp_path_factory: pytest.TempPathFactory, mode: str) -> dict:
    for rel, digest in EXPECTED.items():
        assert _sha(ROOT / rel) == digest
    work = tmp_path_factory.mktemp(f"d8-{mode}")
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
    payload["_stderr_tail"] = completed.stderr[-1500:]
    return payload


def _sched(report: dict, name: str) -> dict:
    return report["schedules"][name]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = _run(tmp_path_factory, "concurrency")
    assert payload.get("error", "") == "", payload.get(
        "traceback", payload.get("error")
    )
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def lifespan_report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = _run(tmp_path_factory, "lifespan")
    assert payload.get("error", "") == "", payload.get(
        "traceback", payload.get("error")
    )
    assert payload["_returncode"] == 0
    return payload


def test_t01_t04_baseline_and_fake_driver(report: dict) -> None:
    assert report["get_connection_module"] == "forex_bot.database"
    assert report["foreign_project_on_path"] is False
    assert report["dotenv_calls_at_import"] >= 1
    assert report["guard_checks"]["localhost_denied"] is True
    assert report["guard_checks"]["dns_denied"] is True
    assert report["guard_checks"]["self_pipe_not_reusable"] is True
    assert report["guard_checks"]["ops_denied"] is True
    assert report["guard_checks"]["replace_denied"] is True
    assert report["network"] == []
    for name, row in report["schedules"].items():
        assert row["network"] == []
        assert row["requests"] == 0
        assert row["alive_workers"] == 0, name


def test_t05_t07_unlocked_overlap_abandons_a_connection(report: dict) -> None:
    row = _sched(report, "unlocked_overlap")
    assert row["connect_calls"] == 2
    assert row["abandoned_open"] == 1
    assert row["published_open"] is True
    assert row["pair_consistent"] is True
    assert row["worker_errors"] == []
    assert row["application_closed"] == 0
    assert row["harness_closed"] == 2


def test_t05_locked_caller_does_not_exclude_unlocked_caller(report: dict) -> None:
    row = _sched(report, "unlocked_vs_locked")
    assert row["connect_calls"] == 2
    assert row["abandoned_open"] == 1
    assert row["pair_consistent"] is True
    assert row["application_closed"] == 0
    assert row["harness_closed"] == 2


def test_t11_t12_helpers_holding_the_lock_publish_one_pair(report: dict) -> None:
    row = _sched(report, "both_locked")
    assert row["connect_calls"] == 1
    assert row["abandoned_open"] == 0
    assert row["published_open"] is True
    assert row["pair_consistent"] is True
    assert row["harness_closed"] == 1
    ids = {worker["returned_id"] for worker in row["workers"]}
    assert ids == {row["published_id"]}


def test_t08_t10_mixed_and_double_failure(report: dict) -> None:
    second = _sched(report, "second_fails")
    first = _sched(report, "first_fails")
    both = _sched(report, "both_fail")
    cleanup = _sched(report, "cleanup_fails")
    for row in (second, first):
        assert row["connect_calls"] == 2
        assert row["published_open"] is True
        assert row["abandoned_open"] == 0
        assert row["application_closed"] >= 1
        assert row["harness_closed"] == 1
        assert row["worker_errors"] == []
    assert both["published_id"] is None
    assert both["abandoned_open"] == 0
    assert both["application_closed"] == 2
    assert both["harness_closed"] == 0
    assert both["worker_errors"] == []
    assert cleanup["published_id"] is None
    assert "RuntimeError" in cleanup["partial_notes"]
    assert cleanup["harness_closed"] == 1
    survivor = [
        row
        for row in cleanup["connections"]
        if row["close_calls"] and not row["closed"]
    ]
    assert len(survivor) == 1


def test_t13_t19_release_retry_and_replacement(report: dict) -> None:
    during = _sched(report, "release_during_init")
    borrowed = _sched(report, "release_borrowed")
    replaced = _sched(report, "replace_during_close")
    retry = _sched(report, "retry_after_connect_failure")
    assert during["release_notes_before_publish"] == []
    assert during["published_open"] is True
    assert during["abandoned_open"] == 0
    assert borrowed["borrowed_closed"] is True
    assert borrowed["borrowed_close_calls"] == 1
    assert borrowed["second_release_notes"] == []
    assert borrowed["release_created_connection"] is False
    assert borrowed["harness_closed"] == 0
    assert replaced["old_closed"] is True
    assert replaced["new_open"] is True
    assert replaced["published_id"] == replaced["new_id"]
    assert replaced["published_id"] != replaced["old_id"]
    assert retry["first_none"] is True
    assert retry["published_is_second"] is True
    assert retry["connect_calls"] == 2
    assert retry["abandoned_open"] == 0


def test_t31_t44_lifespan_edges(lifespan_report: dict) -> None:
    cases = lifespan_report["cases"]
    corrupt = cases["corrupt"]
    baseline = cases["baseline"]
    broker = cases["broker"]
    stop = cases["shutdown_stop"]
    health = cases["await_health"]
    before = cases["before_yield"]
    startup_stop = cases["startup_stop"]
    repeat = cases["repeat"]
    assert corrupt["yielded"] is False
    assert corrupt["escaped_type"] == "StartupSafetyAbort"
    assert corrupt["connect_calls"] == 0
    assert corrupt["created"] == 0
    assert baseline["yielded"] is True
    assert baseline["auth"] == "BLOCKED"
    assert baseline["active"] == []
    assert baseline["pending"] == 0
    assert baseline["created"] == 4
    assert baseline["pg_conn_held"] is True
    assert baseline["application_closed"] == 0
    assert baseline["harness_closed"] == 1
    assert broker["pg_conn_held"] is False
    assert broker["application_closed"] >= 1
    assert broker["harness_closed"] == 0
    assert broker["pending"] == 0
    assert stop["yielded"] is True
    assert stop["pending"] == 0
    assert stop["harness_cancelled"] == 0
    assert stop["pg_conn_held"] is True
    assert "RuntimeError" in stop["cleanup_errors"]
    assert "injected shutdown failure" in stop["message"]
    assert health["pending"] == 0
    assert health["harness_cancelled"] == 0
    assert "injected task await failure" in health["message"]
    assert before["pending"] == 0
    assert before["pg_conn_held"] is False
    assert before["harness_cancelled"] == 0
    assert startup_stop["yielded"] is False
    assert startup_stop["pending"] == 0
    assert startup_stop["harness_cancelled"] == 0
    assert startup_stop["pg_conn_held"] is True
    assert startup_stop["application_closed"] == 0
    assert startup_stop["harness_closed"] == 1
    assert "RuntimeError" in startup_stop["cleanup_errors"]
    assert "injected failure before yield" in startup_stop["message"]
    assert repeat["yielded"] is True
    assert repeat["auth"] == "BLOCKED"
    assert repeat["active"] == []
    assert repeat["pending"] == 0
    for case in cases.values():
        assert case["requests"] == 0
