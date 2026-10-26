"""Stage D.15 database ownership checks. Does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d15_harness import run_d15  # noqa: E402


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d15(tmp_path_factory, "database")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_b01_b13_one_connection_and_failed_initialization(report: dict) -> None:
    cases = report["cases"]
    extra = cases["extra"]
    assert cases["init"]["connect_delta"] == 1
    assert len(set(cases["init"]["ids"])) == 1
    assert extra["before_cursor"]["result_none"] is True
    assert extra["before_cursor"]["published_connection"] is True
    assert extra["before_cursor"]["published_cursor"] is True
    assert extra["after_cursor"]["result_none"] is True
    assert extra["after_cursor"]["published_connection"] is True
    assert extra["after_cursor"]["published_cursor"] is True
    assert extra["after_cursor"]["connections_closed"] is True
    assert extra["after_cursor"]["cursors_closed"] is True
    assert extra["borrower_attributes"] == []


def test_b07_b19_queries_release_and_stopped_workers(report: dict) -> None:
    cases = report["cases"]
    assert cases["inflight"]["release_finished_early"] is False
    assert cases["inflight"]["query_still_held"] is True
    assert cases["inflight"]["release_blocked"] is True
    assert cases["delayed"]["queries"] == []
    assert cases["delayed"]["connect_delta"] == 0
    assert cases["delayed"]["stop"]["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert cases["gate"]["queries"] == []
    assert cases["gate"]["connect_delta"] == 0
    assert cases["foreign"]["waiting"] is True
    assert cases["foreign"]["event_while_held"] is True
    assert cases["foreign"]["queries"] == []
    assert cases["open_connections"] == []
    assert cases["open_cursors"] == []
    assert cases["use_after_close"] == []
    assert report["network_after"] == []
