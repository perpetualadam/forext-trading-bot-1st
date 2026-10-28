"""Stage D.12 repeated-lifespan checks. This module does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d12_harness import run_d12  # noqa: E402


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d12(tmp_path_factory, "repeated")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_second_lifespan_refuses_a_second_worker(report: dict) -> None:
    cases = report["cases"]
    assert cases["yielded_a"] is True
    assert cases["snap_a"]["stored_alive"] is True
    assert cases["snap_a"]["cleanup_errors"] == ["D12-STOP-01"]
    assert cases["yielded_b"] is True
    assert cases["escaped_b"] == ""
    assert cases["same_worker"] is True
    assert cases["thread_count_b"] == 1
    assert cases["snap_b"]["stored_alive"] is True
    assert cases["snap_b"]["stop_event"] is True
    assert cases["snap_b"]["cleanup_errors"] == ["D12-STOP-01"]
    assert cases["snap_b"]["status_in_logs"]["incomplete"] is True
    assert 1.5 <= cases["elapsed_b"] <= 4.5


def test_second_lifespan_reuses_the_database(report: dict) -> None:
    cases = report["cases"]
    assert cases["connection_reused_ab"] is True
    assert cases["snap_a"]["connection_open"] is True
    assert cases["snap_b"]["application_close_calls"] == 0


def test_third_lifespan_starts_after_the_old_worker_exits(report: dict) -> None:
    cases = report["cases"]
    assert cases["worker_exit_before_c"]["escaped"] == []
    assert cases["yielded_c"] is True
    assert cases["escaped_c"] == ""
    assert cases["fresh_worker"] is True
    assert cases["thread_count_c"] == 1
    assert cases["snap_c_after"]["stored_alive"] is False
    assert cases["snap_c_after"]["cleanup_errors"] == []
    assert report["network_after"] == []
    assert report["escaped_final"] == []
