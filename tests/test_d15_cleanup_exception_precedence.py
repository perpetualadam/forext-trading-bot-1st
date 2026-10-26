"""Stage D.15 cleanup exception precedence. Does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d15_harness import run_d15  # noqa: E402


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d15(tmp_path_factory, "shutdown")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_e01_e14_primary_errors_and_database_ownership(report: dict) -> None:
    cases = report["cases"]
    broker = cases["broker"]
    assert broker["yielded"] is False
    assert broker["escaped_type"] == "RuntimeError"
    assert broker["connection_open"] is False
    assert "D12-STOP-01" not in broker["cleanup_errors"]
    normal = cases["normal"]
    assert normal["yielded"] is True
    assert normal["escaped_type"] == ""
    assert normal["cleanup_errors"] == []
    assert normal["connection_open"] is True
    assert normal["pending"] == 0
    blocked = cases["blocked"]
    assert blocked["escaped_type"] == ""
    assert "D12-STOP-01" in blocked["cleanup_errors"]
    assert blocked["stored_alive"] is True
    assert blocked["connection_open"] is True
    assert blocked["pending"] == 0
    corrupt = cases["corrupt"]
    assert corrupt["yielded"] is False
    assert corrupt["escaped_type"] == "StartupSafetyAbort"
    assert corrupt["connection_open"] is False
    assert cases["authorisation"] == "BLOCKED"
    assert cases["active_strategies"] == []


def test_e03_e19_secondary_cleanup_stays_observable(report: dict) -> None:
    cases = report["cases"]
    raised = cases["stop_raises"]
    assert raised["yielded"] is True
    assert raised["escaped_type"] == "RuntimeError"
    assert "RuntimeError" in raised["cleanup_errors"]
    assert raised["connection_open"] is True
    assert raised["stored_alive"] is False
    awaited = cases["await_health"]
    assert awaited["yielded"] is True
    assert awaited["pending"] == 0
    assert any("RuntimeError" in item for item in awaited["cleanup_errors"])
    release = cases["release_fails"]
    assert release["yielded"] is False
    assert release["escaped_type"] == "RuntimeError"
    assert release["connection_open"] is False
    assert any("RuntimeError" in item for item in release["cleanup_errors"])
    alert = cases["alert_raises"]
    assert alert["escaped_type"] == "RuntimeError"
    assert any("RuntimeError" in item for item in alert["cleanup_errors"])
    assert alert["connection_open"] is True
    cancelled = cases["cancelled"]
    assert cancelled["cancel_type"] == "CancelledError"
    assert cancelled["pending_owned"] == 0
    assert cancelled["stored_alive"] is True
    assert cancelled["connection_open"] is True
    assert report["network_after"] == []
    assert report["escaped_final"] == []
