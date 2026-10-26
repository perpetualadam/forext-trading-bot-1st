"""Stage D.15 Telegram worker concurrency. Does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d15_harness import run_d15  # noqa: E402

STARTED = "START_STARTED"
ALREADY = "START_ALREADY_RUNNING"
REFUSED = "START_REFUSED_PREVIOUS_WORKER"
DISABLED = "START_DISABLED"
FAILED = "START_FAILED"
INCOMPLETE = "STOP_INCOMPLETE_WORKER_ALIVE"


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d15(tmp_path_factory, "telegram")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_t01_t08_one_worker_and_refused_restart(report: dict) -> None:
    cases = report["cases"]
    refused = cases["refused"]
    assert cases["disabled"] == DISABLED
    assert cases["disabled_threads"] == []
    assert cases["started"] == STARTED
    assert cases["already"] == ALREADY
    assert sorted(cases["concurrent"]) == [ALREADY, STARTED]
    assert cases["concurrent_threads"] == 1
    assert cases["blocked_start"] == STARTED
    assert refused["result"] == REFUSED
    assert refused["same_ident"] is True
    assert refused["stop_event"] is True
    assert refused["threads"] == 1
    assert refused["query_delta"] == 0
    assert cases["overlap_refused"] == REFUSED
    assert cases["overlap_event"] is True
    assert cases["overlap_threads"] == 1
    assert cases["overlap_stop"] == INCOMPLETE


def test_t09_t17_timeout_restart_and_propagated_interrupt(report: dict) -> None:
    cases = report["cases"]
    assert cases["refused"]["stop"]["return_value"] == INCOMPLETE
    assert cases["refused"]["stop"]["alive_after"] is True
    assert cases["refused"]["stop"]["elapsed_sec"] < 4
    assert cases["worker_exit"]["escaped"] == []
    assert cases["replaced"] == STARTED
    assert cases["replaced_fresh"] is True
    assert cases["failed"] == FAILED
    assert cases["failed_stored_cleared"] is True
    assert cases["keyboard_propagated"] is True
    assert cases["recovered"] == STARTED
    assert cases["none_results"] == []


def test_t12_t25_repeated_stops_exceptions_and_no_late_query(report: dict) -> None:
    extra = report["cases"]["extra"]
    repeated = extra["repeated_stop"]
    concurrent = extra["concurrent_stop"]
    assert repeated["started"] == STARTED
    assert repeated["first"] == INCOMPLETE
    assert repeated["second"] == INCOMPLETE
    assert repeated["same_ident"] is True
    assert repeated["alive"] is True
    assert repeated["stop_event"] is True
    assert concurrent["joined"] is True
    assert sorted(concurrent["results"]) == [INCOMPLETE, INCOMPLETE]
    assert concurrent["threads"] == 1
    assert concurrent["same_ident"] is True
    assert extra["poll_exception"]["queries"] == 0
    assert extra["poll_exception"]["escaped"] == []
    assert extra["poll_exception"]["stored_cleared"] is True
    assert extra["database_exception_contained"] is True
    assert extra["database_reply"] == "CommandReply"
    assert extra["stopped_query_delta"] == 0
    assert report["network_after"] == []
    assert report["escaped_final"] == []
