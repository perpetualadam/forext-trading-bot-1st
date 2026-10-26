"""Stage D.12 shutdown-contract checks. This module does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d12_harness import run_d12  # noqa: E402


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d12(tmp_path_factory, "contract")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_guards_and_defaults(report: dict) -> None:
    assert all(report["guard_checks"].values())
    assert report["network_after"] == []
    assert report["escaped_final"] == []
    cases = report["cases"]
    assert cases["authorisation"] == "BLOCKED"
    assert cases["active_strategies"] == []


def test_normal_stop_drains_tasks_and_retains_database(report: dict) -> None:
    row = report["cases"]["normal"]
    assert row["yielded"] is True
    assert row["escaped_type"] == ""
    assert row["stored_alive"] is False
    assert row["pending"] == 0
    assert row["connection_open"] is True
    assert row["application_close_calls"] == 0
    assert row["cleanup_errors"] == []
    assert row["status_in_logs"]["incomplete"] is False


def test_incomplete_stop_is_not_reported_by_the_application(report: dict) -> None:
    row = report["cases"]["blocked"]
    assert row["yielded"] is True
    assert row["escaped_type"] == ""
    assert row["stored_alive"] is True
    assert row["stop_event"] is True
    assert 1.5 <= row["elapsed_sec"] <= 4.5
    assert row["pending"] == 0
    assert row["cleanup_errors"] == []
    assert row["status_in_logs"]["incomplete"] is False
    assert row["connection_open"] is True
    assert row["application_close_calls"] == 0
    assert row["stop_wrapped"] is False


def test_stop_not_running_is_not_a_lifespan_status(report: dict) -> None:
    direct = report["cases"]["direct_stop_without_worker"]
    assert direct["return_value"] == "STOP_NOT_RUNNING"
    for name in ("corrupt", "broker"):
        row = report["cases"][name]
        assert row["yielded"] is False
        assert row["stored_alive"] is False
        assert row["connection_open"] is False


def test_stop_exception_preserves_task_cleanup(report: dict) -> None:
    row = report["cases"]["stop_raises"]
    assert row["yielded"] is True
    assert row["escaped_type"] == "RuntimeError"
    assert row["stop_status_before_raise"] == ["STOP_COMPLETED"]
    assert "RuntimeError" in row["cleanup_errors"]
    assert row["stored_alive"] is False
    assert row["connection_open"] is True


def test_task_await_and_release_and_alert(report: dict) -> None:
    awaited = report["cases"]["await_health"]
    assert awaited["yielded"] is True
    assert awaited["pending"] == 0
    assert any("RuntimeError" in item for item in awaited["cleanup_errors"])
    release = report["cases"]["release_fails"]
    assert release["yielded"] is False
    assert release["connection_open"] is False
    assert any("RuntimeError" in item for item in release["cleanup_errors"])
    alert = report["cases"]["alert_raises"]
    assert alert["escaped_type"] == "RuntimeError"
    assert any("RuntimeError" in item for item in alert["cleanup_errors"])
    assert alert["connection_open"] is True


def test_cancellation_during_blocked_shutdown(report: dict) -> None:
    row = report["cases"]["cancelled"]
    assert row["cancel_type"] == "CancelledError"
    assert row["stored_alive"] is True
    assert row["cleanup_errors"] == []
    assert row["connection_open"] is True
    assert row["pending_owned"] == 0
