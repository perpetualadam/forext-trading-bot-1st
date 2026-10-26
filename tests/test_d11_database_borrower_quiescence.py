"""Stage D.11 database borrower checks. Lifespan imports happen in the child."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "d11_shutdown_tests",
    Path(__file__).with_name("test_d11_telegram_shutdown_remediation.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run_d11 = _MODULE.run_d11


def _sched(report: dict, name: str) -> dict:
    return report["schedules"][name]


@pytest.fixture(scope="module")
def threads(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d11(tmp_path_factory, "threads")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def lifespan(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d11(tmp_path_factory, "lifespan")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_delayed_poll_does_not_query_after_release(threads: dict) -> None:
    row = _sched(threads, "S06_S12_S18_S23_S32_S33_S34")
    assert row["old_closed"] is True
    assert row["queries_after_release"] == []
    assert row["connect_delta"] == 0
    assert row["published_after"] is None
    assert row["use_after_close"] == []
    assert row["worker_after_delayed_poll"]["escaped"] == []
    assert row["stored_after_exit"] is True


def test_stop_before_database_entry(threads: dict) -> None:
    row = _sched(threads, "S08_S27_S28_stop_before_database_entry")
    assert row["queries"] == []
    assert row["connect_delta"] == 0
    assert row["published"] is False


def test_stop_while_waiting_for_lock_skips_query(threads: dict) -> None:
    row = _sched(threads, "S09_stop_while_waiting_for_lock")
    assert row["poller_waiting_before_query"] is True
    assert row["stop_event_while_foreign_lock_held"] is True
    assert row["queries"] == []
    assert row["application"]["return_value"] == "STOP_COMPLETED"


def test_inflight_query_blocks_release_until_finished(threads: dict) -> None:
    row = _sched(threads, "S10_S29_S30_inflight_query")
    assert row["lock_free_while_query_held"] is False
    assert row["release_finished_before_query_release"] is False
    assert row["query_still_held_when_stop_returned"] is True
    assert row["release_still_blocked_after_stop_returned"] is True
    assert row["stop"]["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert row["release_finished_after"] is True
    assert row["worker_after_query_release"]["escaped"] == []


def test_release_after_completed_stop(threads: dict) -> None:
    row = _sched(threads, "S31_release_after_completed_stop")
    assert row["stop"]["return_value"] == "STOP_COMPLETED"
    assert row["closed"] is True
    assert row["threads"] == []


def test_database_exception_stays_inside_command(threads: dict) -> None:
    row = _sched(threads, "S38_database_exception")
    assert row["escaped"] is False
    assert row["queries"] == 0


def test_closed_objects_are_not_reused_by_direct_helper(threads: dict) -> None:
    row = _sched(threads, "S35_S36_direct_helper_after_release")
    assert row["old_closed"] is True
    assert row["new_id"] != row["old_id"]
    assert row["use_after_close"] == []


def test_d9_lock_overlap_still_single_connection(threads: dict) -> None:
    row = _sched(threads, "init_lock_overlap")
    assert row["connect_delta"] == 1
    assert len(set(row["ids"])) == 1


def _case(lifespan: dict, name: str) -> dict:
    return lifespan["cases"][name]


def test_startup_failure_before_telegram_releases_database(lifespan: dict) -> None:
    for name in ("corrupt", "broker"):
        row = _case(lifespan, name)
        assert row["yielded"] is False
        assert row["alive_after_application"] is False
        assert row["pg_conn_held"] is False
        assert row["pending"] == 0
        assert row["stop_results"] == []


def test_normal_shutdown_retains_database_and_stops_worker(lifespan: dict) -> None:
    row = _case(lifespan, "normal")
    assert row["yielded"] is True
    assert row["escaped_type"] == ""
    assert row["stop_results"] == ["STOP_COMPLETED"]
    assert row["alive_after_application"] is False
    assert row["stored_alive"] is False
    assert row["pg_conn_held"] is True
    assert row["application_close_calls"] == 0
    assert row["pending"] == 0
    assert row["cleanup_errors"] == []
    assert row["auth"] == "BLOCKED"
    assert row["active"] == []


def test_repeated_lifespan(lifespan: dict) -> None:
    row = _case(lifespan, "repeat")
    assert row["yielded"] is True
    assert row["stop_results"] == ["STOP_COMPLETED"]
    assert row["pending"] == 0
    assert row["alive_after_application"] is False


def test_blocked_shutdown_is_observable_and_does_not_query(lifespan: dict) -> None:
    row = _case(lifespan, "blocked_shutdown")
    assert row["yielded"] is True
    assert row["escaped_type"] == ""
    assert row["blocked_ready"] is True
    assert row["stop_results"] == ["STOP_INCOMPLETE_WORKER_ALIVE"]
    assert row["alive_after_application"] is True
    assert row["stored_alive"] is True
    assert row["stop_event"] is True
    assert row["pg_conn_held"] is True
    assert row["application_close_calls"] == 0
    assert row["cleanup_errors"] == []
    probe = row["post_application_probe"]
    assert probe["label"] == "composed_after_lifespan_returned"
    assert probe["queries"] == []
    assert probe["connect_delta"] == 0
    assert probe["published_id"] is None
    assert probe["worker_exit"]["escaped"] == []
    assert probe["use_after_close"] == []


def test_stop_exception_still_cleans_tasks(lifespan: dict) -> None:
    row = _case(lifespan, "stop_raises")
    assert row["escaped_type"] == "RuntimeError"
    assert row["stop_results"] == ["STOP_COMPLETED"]
    assert any("RuntimeError" in item for item in row["cleanup_errors"])
    assert row["pending"] == 0
    assert row["alive_after_application"] is False
    assert row["pg_conn_held"] is True


def test_task_await_exception_still_cleans_remaining_tasks(lifespan: dict) -> None:
    row = _case(lifespan, "await_health")
    assert row["yielded"] is True
    assert any("RuntimeError" in item for item in row["cleanup_errors"])
    assert row["pending"] == 0
    assert row["stop_results"] == ["STOP_COMPLETED"]


def test_release_exception_on_startup_failure(lifespan: dict) -> None:
    row = _case(lifespan, "release_fails")
    assert row["yielded"] is False
    assert row["pg_conn_held"] is False
    assert any("RuntimeError" in item for item in row["cleanup_errors"])
    assert row["stop_results"] == []


def test_startup_after_telegram_remains_unreachable(lifespan: dict) -> None:
    row = _case(lifespan, "startup_failure_after_telegram")
    assert row["evidence"] == "NOT_REACHABLE_IN_CURRENT_SOURCE"


def test_lifespan_network_stays_empty(lifespan: dict) -> None:
    assert lifespan["network_after"] == []
    assert all(lifespan["guard_checks"].values())
