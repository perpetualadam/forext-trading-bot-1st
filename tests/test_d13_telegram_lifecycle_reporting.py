"""Stage D.13 Telegram lifecycle reporting. This module does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d13_harness import run_d13  # noqa: E402


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d13(tmp_path_factory, "contract")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def extra(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d13(tmp_path_factory, "extra")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_s01_s02_s08_s13_normal_stop_has_no_warning(report: dict) -> None:
    row = report["cases"]["normal"]
    assert row["yielded"] is True
    assert row["escaped_type"] == ""
    assert row["stored_alive"] is False
    assert row["pending"] == 0
    assert row["connection_open"] is True
    assert row["application_close_calls"] == 0
    assert row["cleanup_errors"] == []
    assert row["status_in_logs"]["worker_alive_words"] is False
    assert report["network_after"] == []
    assert report["escaped_final"] == []
    assert report["cases"]["authorisation"] == "BLOCKED"
    assert report["cases"]["active_strategies"] == []


def test_s10_s11_s12_s17_s18_s23_incomplete_stop_is_recorded(report: dict) -> None:
    row = report["cases"]["blocked"]
    assert row["yielded"] is True
    assert row["escaped_type"] == ""
    assert row["stored_alive"] is True
    assert row["stop_event"] is True
    assert row["pending"] == 0
    assert row["connection_open"] is True
    assert row["application_close_calls"] == 0
    assert "D12-STOP-01" in row["cleanup_errors"]
    assert row["status_in_logs"]["worker_alive_words"] is True
    assert 1.5 <= row["elapsed_sec"] <= 4.5


def test_s09_s14_stop_not_running_direct(report: dict) -> None:
    assert report["cases"]["direct_stop_without_worker"]["return_value"] == (
        "STOP_NOT_RUNNING"
    )


def test_s16_s19_s20_stop_exception_and_primary_failure(report: dict) -> None:
    raised = report["cases"]["stop_raises"]
    assert raised["yielded"] is True
    assert raised["escaped_type"] == "RuntimeError"
    assert raised["stop_status_before_raise"] == ["STOP_COMPLETED"]
    assert "RuntimeError" in raised["cleanup_errors"]
    assert "D12-STOP-01" not in raised["cleanup_errors"]
    assert raised["stored_alive"] is False
    assert raised["connection_open"] is True
    awaited = report["cases"]["await_health"]
    assert awaited["pending"] == 0
    assert any("RuntimeError" in item for item in awaited["cleanup_errors"])
    broker = report["cases"]["broker"]
    assert broker["yielded"] is False
    assert broker["escaped_type"] == "RuntimeError"
    assert broker["connection_open"] is False
    assert "D12-STOP-01" not in broker["cleanup_errors"]
    cancelled = report["cases"]["cancelled"]
    assert cancelled["cancel_type"] == "CancelledError"
    assert cancelled["pending_owned"] == 0
    assert cancelled["connection_open"] is True
    assert "D12-STOP-01" in cancelled["cleanup_errors"]


def test_s03_disabled_and_s15_unknown_and_s04_start_raise(extra: dict) -> None:
    disabled = extra["cases"]["disabled"]
    assert disabled["yielded"] is True
    assert disabled["escaped_type"] == ""
    assert disabled["stored_alive"] is False
    assert "D12-STOP-01" not in disabled["cleanup_errors"]
    unknown = extra["cases"]["unknown_stop"]
    assert unknown["escaped_type"] == ""
    assert "D12-STOP-UNKNOWN" in unknown["cleanup_errors"]
    assert unknown["stored_alive"] is False
    failed = extra["cases"]["start_failed"]
    assert failed["escaped_type"] == "RuntimeError"
    assert "D12-STOP-01" not in failed["cleanup_errors"]
    assert extra["network_after"] == []
    assert extra["escaped_final"] == []
