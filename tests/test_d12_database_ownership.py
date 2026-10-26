"""Stage D.12 database-ownership checks. This module does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d12_harness import run_d12  # noqa: E402


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d12(tmp_path_factory, "ownership")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_direct_stop_without_a_worker(report: dict) -> None:
    assert report["cases"]["not_running"]["return_value"] == "STOP_NOT_RUNNING"


def test_delayed_poll_does_not_reconnect(report: dict) -> None:
    row = report["cases"]["delayed"]
    assert row["stop"]["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert row["stop"]["stored_alive"] is True
    assert row["old_closed"] is True
    assert row["queries"] == []
    assert row["connect_delta"] == 0
    assert row["published_id"] is None
    assert row["worker"]["escaped"] == []


def test_stop_before_database_entry(report: dict) -> None:
    row = report["cases"]["gate"]
    assert row["queries"] == []
    assert row["connect_delta"] == 0


def test_stop_while_waiting_for_the_database_lock(report: dict) -> None:
    row = report["cases"]["foreign"]
    assert row["waiting"] is True
    assert row["event_while_held"] is True
    assert row["queries"] == []
    assert row["stop"]["return_value"] == "STOP_COMPLETED"


def test_release_waits_for_the_inflight_query(report: dict) -> None:
    row = report["cases"]["inflight"]
    assert row["release_finished_early"] is False
    assert row["query_still_held"] is True
    assert row["release_blocked"] is True
    assert row["stop"]["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"


def test_initialization_lock_and_final_accounting(report: dict) -> None:
    assert report["cases"]["init"]["connect_delta"] == 1
    assert len(set(report["cases"]["init"]["ids"])) == 1
    assert report["cases"]["open_connections"] == []
    assert report["cases"]["open_cursors"] == []
    assert report["cases"]["use_after_close"] == []
    assert report["network_after"] == []
    assert all(report["guard_checks"].values())
