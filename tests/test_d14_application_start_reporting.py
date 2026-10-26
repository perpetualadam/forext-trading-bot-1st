"""Stage D.14 application startup reporting. Does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d14_harness import run_d14  # noqa: E402


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d14(tmp_path_factory, "lifespan")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_a01_a04_normal_and_disabled_have_no_refusal(report: dict) -> None:
    cases = report["cases"]
    assert cases["normal"]["yielded"] is True
    assert cases["normal"]["escaped_type"] == ""
    assert cases["normal"]["cleanup_errors"] == []
    assert cases["normal_warnings"] == 0
    assert cases["disabled"]["yielded"] is True
    assert cases["disabled"]["stored_alive"] is False
    assert cases["disabled_warnings"] == 0
    assert "D12-STOP-01" not in cases["disabled"]["cleanup_errors"]


def test_a07_a16_refusal_is_reported_and_non_fatal(report: dict) -> None:
    cases = report["cases"]
    assert cases["yielded_a"] is True
    assert cases["snap_a"]["stored_alive"] is True
    assert "D12-STOP-01" in cases["snap_a"]["cleanup_errors"]
    assert cases["seen"][0] == "START_STARTED"
    assert cases["seen"][1] == "START_REFUSED_PREVIOUS_WORKER"
    assert cases["yielded_b"] is True
    assert cases["escaped_b"] == ""
    assert cases["same_worker"] is True
    assert cases["snap_b"]["stop_event"] is True
    assert cases["refusal_logged"] is True
    assert cases["refusal_phrase"] is True
    assert cases["connection_reused"] is True
    assert cases["snap_b"]["connection_open"] is True


def test_a17_a21_restart_failure_and_unknown(report: dict) -> None:
    cases = report["cases"]
    assert cases["yielded_c"] is True
    assert cases["fresh_worker"] is True
    assert cases["seen"][2] == "START_STARTED"
    assert cases["third_warnings"] == 0
    assert cases["snap_c_after"]["stored_alive"] is False
    assert "D12-STOP-01" not in cases["snap_c_after"]["cleanup_errors"]
    assert cases["failed_yielded"] is True
    assert cases["failed_escaped"] == ""
    assert cases["failed_phrase"] is True
    assert cases["failed_refusal"] is False
    assert cases["unknown_yielded"] is True
    assert cases["unknown_escaped"] == ""
    assert cases["unknown_phrase"] is True
    assert report["network_after"] == []
    assert report["escaped_final"] == []
