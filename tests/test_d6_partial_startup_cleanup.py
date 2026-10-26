"""Stage D.6 partial-startup cleanup. This module does not import app.py."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).resolve().parent / "d6_partial_startup_runner.py"
EXPECTED = {
    "forex_bot/app.py": "f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4",
    "forex_bot/live_safety.py": "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44",
    "forex_bot/strategy_meta.py": "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d",
    "tests/test_d5_lifespan_isolation.py": "8cf8c712979ad32eac648b4a8f18d65546bf24a72d2a4e6f4f3ff6041bd88dd4",
    "tests/d5_lifespan_runner.py": "0729bea1df8a59d5dde3c66c396a476a0abb80c9c36213f15f08fcb77f2a3b60",
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
        "PYTEST_CURRENT_TEST": "d6-isolated",
        "LIVE_SAFETY_STATE_PATH": str(safety),
        "D6_WORK_DIR": str(work),
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
        "POSTGRES_HOST": "d6-invalid-host",
        "POSTGRES_PORT": "1",
        "POSTGRES_USER": "d6",
        "POSTGRES_PASSWORD": "",
        "POSTGRES_PASS": "",
        "POSTGRES_DB": "d6",
    }


def _run(tmp_path_factory: pytest.TempPathFactory, mode: str) -> dict:
    for rel, digest in EXPECTED.items():
        assert _sha(ROOT / rel) == digest
    work = tmp_path_factory.mktemp(f"d6-{mode}")
    out = work / "report.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), str(out), mode],
        cwd=str(work),
        env=_child_env(work, work / "safety.json"),
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["_returncode"] = completed.returncode
    payload["_stderr_tail"] = completed.stderr[-1500:]
    return payload


def _case(report: dict, name: str) -> dict:
    return report["cases"][name]


def _conn(case: dict) -> dict:
    assert len(case["connections"]) == 1
    return case["connections"][0]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = _run(tmp_path_factory, "lifespan")
    assert payload.get("error", "") == ""
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def repair_report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return _run(tmp_path_factory, "repair")


def test_t01_t02_baseline_shutdown_cancels_tasks(report: dict) -> None:
    case = _case(report, "baseline")
    assert case["yielded"] is True
    assert case["escaped_type"] == ""
    assert case["tasks_created"] == 4
    assert case["tasks_cancelled_by_application"] == 4
    assert case["tasks_pending_after_application"] == 0
    assert case["harness_cancelled"] == 0
    assert case["scheduled"] == ["scheduled:_inner"] * 4
    assert _conn(case)["close_calls"] == 0
    assert case["pg_conn_held"] is True


def test_t03_database_connect_failure_is_nonfatal(report: dict) -> None:
    case = _case(report, "db_connect")
    assert case["yielded"] is True
    assert case["escaped_type"] == ""
    assert case["connections"] == []
    assert case["tasks_cancelled_by_application"] == 4


def test_t04_t05_t06_database_failures_drop_connection_without_close(report: dict) -> None:
    for name in ("db_cursor", "db_execute", "db_commit"):
        case = _case(report, name)
        conn = _conn(case)
        assert case["yielded"] is True
        assert case["escaped_type"] == ""
        assert conn["closed"] is False
        assert conn["close_calls"] == 0
        assert conn["rollbacks"] == 0
        assert case["pg_conn_held"] is False
        assert case["harness_closed_connections"] == 1
        assert case["tasks_pending_after_application"] == 0


def test_t09_t12_fatal_pre_yield_leaves_connection_open(report: dict) -> None:
    for name in ("broker", "before_tasks"):
        case = _case(report, name)
        assert case["yielded"] is False
        assert case["escaped_type"] == "RuntimeError"
        assert case["tasks_created"] == 0
        assert _conn(case)["close_calls"] == 0
        assert case["pg_conn_held"] is True
        assert case["harness_closed_connections"] == 1


def test_t10_t11_t25_account_and_reconcile_are_nonfatal(report: dict) -> None:
    for name in ("account", "reconcile"):
        case = _case(report, name)
        assert case["yielded"] is True
        assert case["escaped_type"] == ""
        assert case["tasks_cancelled_by_application"] == 4


def test_t13_t14_t15_task_creation_failure_leaves_tasks(report: dict) -> None:
    expected = {"after_first": 1, "later_task": 3, "before_yield": 4}
    for name, pending in expected.items():
        case = _case(report, name)
        assert case["yielded"] is False
        assert case["tasks_pending_after_application"] == pending
        assert case["tasks_cancelled_by_application"] == 0
        assert case["harness_cancelled"] == pending


def test_t16_shutdown_failure_skips_task_cancellation(report: dict) -> None:
    case = _case(report, "shutdown_stop")
    assert case["yielded"] is True
    assert case["escaped_type"] == "RuntimeError"
    assert "injected shutdown failure" in case["message"]
    assert case["tasks_pending_after_application"] == 4
    assert case["tasks_cancelled_by_application"] == 0
    assert case["harness_cancelled"] == 4


def test_t18_task_await_failure_skips_later_cancellation(report: dict) -> None:
    case = _case(report, "await_health")
    assert case["yielded"] is True
    assert "injected task await failure" in case["message"]
    assert case["tasks_pending_after_application"] == 3
    assert case["tasks_cancelled_by_application"] == 0
    assert case["harness_cancelled"] == 3


def test_t19_t44_repeat_after_partial_failure_stays_blocked(report: dict) -> None:
    first = _case(report, "repeat_first")
    second = _case(report, "repeat_second")
    assert first["yielded"] is False
    assert first["tasks_pending_after_application"] == 1
    assert second["yielded"] is True
    assert second["file_auth"] == "BLOCKED"
    assert second["auth"] == "BLOCKED"
    assert second["active"] == []
    assert second["tasks_pending_after_application"] == 0


def test_t26_broker_failure_is_not_swallowed(report: dict) -> None:
    case = _case(report, "broker")
    assert case["escaped_type"] == "RuntimeError"
    assert "injected broker construction failure" in case["message"]


def test_t27_through_t45_invariants_and_socketpair(report: dict) -> None:
    guards = report["guard_checks"]
    assert guards["localhost_connect_denied"] is True
    assert guards["external_connect_denied"] is True
    assert guards["dns_denied"] is True
    assert guards["self_pipe_port_not_reusable"] is True
    assert guards["open_ops_denied"] is True
    assert guards["open_env_denied"] is True
    assert guards["replace_ops_denied"] is True
    assert guards["probe_denials_only"] is True
    assert report["foreign_project_on_path"] is False
    assert report["dotenv_calls_at_import"] >= 1
    assert report["get_connection_is_real"] is True
    assert report["network"] == []
    assert report["fs_denials"] == []
    for case in report["cases"].values():
        assert case["auth"] == "BLOCKED"
        assert case["active"] == []
        assert case["file_auth"] == "BLOCKED"
        assert case["network"] == []
        assert case["counts"].get("requests", 0) == 0
        assert not any(str(key).startswith("order_route:") for key in case["counts"])
    assert "blocked_connect" not in getattr(socket.socket.connect, "__name__", "")


def test_t50_repair_module_under_guard(repair_report: dict) -> None:
    assert repair_report.get("error", "") == ""
    assert repair_report["_returncode"] == 0
    assert repair_report["repair_exit_code"] == 0
    assert repair_report["network"] == []
    assert repair_report["guard_checks"]["localhost_connect_denied"] is True
    assert repair_report["guard_checks"]["open_env_denied"] is True
