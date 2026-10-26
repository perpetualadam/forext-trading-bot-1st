"""Stage D.14 Telegram startup-result contract. Does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d14_harness import run_d14  # noqa: E402

STARTED = "START_STARTED"
ALREADY = "START_ALREADY_RUNNING"
REFUSED = "START_REFUSED_PREVIOUS_WORKER"
DISABLED = "START_DISABLED"
FAILED = "START_FAILED"


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d14(tmp_path_factory, "direct")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_t01_disabled(report: dict) -> None:
    cases = report["cases"]
    assert cases["disabled"] == DISABLED
    assert cases["disabled_threads"] == []


def test_t02_t03_started_and_already_running(report: dict) -> None:
    cases = report["cases"]
    assert cases["started"] == STARTED
    assert cases["already"] == ALREADY
    assert cases["healthy_event"] is False
    assert cases["healthy_threads"] == 1


def test_t04_t08_refused_previous_worker_then_restart(report: dict) -> None:
    refused = report["cases"]["refused"]
    assert report["cases"]["blocked_start"] == STARTED
    assert refused["stop"]["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert refused["result"] == REFUSED
    assert refused["threads"] == 1
    assert refused["same_ident"] is True
    assert refused["stop_event"] is True
    assert refused["query_delta"] == 0
    assert report["cases"]["replaced"] == STARTED
    assert report["cases"]["replaced_fresh"] is True


def test_t10_t13_concurrent_and_overlap(report: dict) -> None:
    cases = report["cases"]
    assert sorted(cases["concurrent"]) == [ALREADY, STARTED]
    assert cases["concurrent_threads"] == 1
    assert cases["overlap_start"] == STARTED
    assert cases["overlap_refused"] == REFUSED
    assert cases["overlap_event"] is True
    assert cases["overlap_threads"] == 1
    assert cases["overlap_stop"] == "STOP_INCOMPLETE_WORKER_ALIVE"


def test_t14_t16_failures_and_no_none(report: dict) -> None:
    cases = report["cases"]
    assert cases["failed"] == FAILED
    assert cases["failed_stored_cleared"] is True
    assert cases["keyboard_propagated"] is True
    assert cases["recovered"] == STARTED
    assert cases["none_results"] == []
    assert report["network_after"] == []
    assert report["escaped_final"] == []
    assert all(report["guard_checks"].values())
