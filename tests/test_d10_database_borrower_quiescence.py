"""Stage D.10 lifespan and borrower checks. This module does not import app.py."""

from __future__ import annotations

import pytest
from test_d10_telegram_shutdown import run_d10


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d10(tmp_path_factory, "lifespan")
    assert payload.get("error", "") == "", payload.get("traceback", payload.get("error"))
    assert payload["_returncode"] == 0
    return payload


def _case(report: dict, name: str) -> dict:
    return report["cases"][name]


def test_lifespan_guards(report: dict) -> None:
    assert report["network_after"] == []
    assert report["escaped_final"] == []
    assert all(report["guard_checks"].values())
    assert report["commands_enabled"] is True


def test_startup_failure_before_telegram(report: dict) -> None:
    corrupt = _case(report, "corrupt")
    assert corrupt["yielded"] is False
    assert corrupt["connect_calls"] == 0
    assert corrupt["created"] == 0
    assert corrupt["alive_after_application"] is False
    assert "startup aborted" in corrupt["message"]
    broker = _case(report, "broker")
    assert broker["yielded"] is False
    assert broker["message"] == "injected broker construction failure"
    assert broker["alive_after_application"] is False
    assert broker["pg_conn_held"] is False
    assert broker["application_close_calls"] >= 1
    assert broker["pending"] == 0
    assert broker["auth"] == "BLOCKED"
    assert broker["active"] == []


def test_normal_shutdown_stops_fast_poller(report: dict) -> None:
    normal = _case(report, "normal")
    assert normal["yielded"] is True
    assert normal["escaped_type"] == ""
    assert normal["alive_after_application"] is False
    assert normal["pending"] == 0
    assert normal["created"] == 4
    assert normal["pg_conn_held"] is True
    assert normal["application_close_calls"] == 0
    assert normal["auth"] == "BLOCKED"
    assert normal["active"] == []
    assert normal["harness"]["escaped"] == []


def test_blocked_shutdown_leaves_worker_alive(report: dict) -> None:
    row = _case(report, "blocked_shutdown")
    assert row["yielded"] is True
    assert row["blocked_ready"] is True
    assert row["escaped_type"] == ""
    assert row["alive_after_application"] is True
    assert row["pg_conn_held"] is True
    assert row["application_close_calls"] == 0
    assert row["pending"] == 0
    assert row["harness"]["escaped"] == []
    assert "thread" not in " ".join(row["cleanup_errors"]).lower()


def test_cleanup_exceptions_are_recorded(report: dict) -> None:
    health = _case(report, "await_health")
    assert health["escaped_type"] == "RuntimeError"
    assert health["message"] == "injected task await failure"
    assert health["pending"] == 0
    assert "RuntimeError" in health["cleanup_errors"]
    raised = _case(report, "stop_raises")
    assert raised["escaped_type"] == "RuntimeError"
    assert raised["message"] == "injected shutdown failure"
    assert raised["pending"] == 0
    assert raised["pg_conn_held"] is True
    assert "RuntimeError" in raised["cleanup_errors"]
    failed = _case(report, "release_fails")
    assert failed["message"] == "injected broker construction failure"
    assert "RuntimeError" in failed["cleanup_errors"]
    assert failed["pg_conn_held"] is False
    assert failed["harness_closed"] == 1


def test_repeated_lifespan_and_unreachable_window(report: dict) -> None:
    repeat = _case(report, "repeat")
    assert repeat["yielded"] is True
    assert repeat["alive_after_application"] is False
    assert repeat["pending"] == 0
    unreachable = _case(report, "startup_failure_after_telegram")
    assert unreachable["evidence"] == "NOT_REACHABLE_IN_CURRENT_SOURCE"
