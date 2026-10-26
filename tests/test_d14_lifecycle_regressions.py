"""Stage D.14 shutdown and ownership regressions. Does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d14_harness import run_d14  # noqa: E402


@pytest.fixture(scope="module")
def shutdown(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d14(tmp_path_factory, "shutdown")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def ownership(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d14(tmp_path_factory, "ownership")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_d13_stop_reporting_remains(shutdown: dict) -> None:
    cases = shutdown["cases"]
    normal = cases["normal"]
    assert normal["yielded"] is True
    assert normal["cleanup_errors"] == []
    assert normal["stored_alive"] is False
    assert normal["connection_open"] is True
    assert normal["pending"] == 0
    blocked = cases["blocked"]
    assert blocked["stored_alive"] is True
    assert blocked["escaped_type"] == ""
    assert "D12-STOP-01" in blocked["cleanup_errors"]
    assert blocked["connection_open"] is True
    assert blocked["pending"] == 0
    assert cases["direct_stop_without_worker"]["return_value"] == "STOP_NOT_RUNNING"
    broker = cases["broker"]
    assert broker["yielded"] is False
    assert broker["connection_open"] is False
    assert "D12-STOP-01" not in broker["cleanup_errors"]
    assert cases["authorisation"] == "BLOCKED"
    assert cases["active_strategies"] == []
    assert shutdown["network_after"] == []
    assert shutdown["escaped_final"] == []


def test_d11_d9_database_protections(ownership: dict) -> None:
    cases = ownership["cases"]
    assert cases["delayed"]["stop"]["return_value"] == "STOP_INCOMPLETE_WORKER_ALIVE"
    assert cases["delayed"]["queries"] == []
    assert cases["delayed"]["connect_delta"] == 0
    assert cases["gate"]["queries"] == []
    assert cases["gate"]["connect_delta"] == 0
    assert cases["inflight"]["release_finished_early"] is False
    assert cases["inflight"]["query_still_held"] is True
    assert cases["inflight"]["release_blocked"] is True
    assert cases["inflight"]["stop"]["return_value"] == (
        "STOP_INCOMPLETE_WORKER_ALIVE"
    )
    assert cases["init"]["connect_delta"] == 1
    assert len(set(cases["init"]["ids"])) == 1
    assert cases["open_connections"] == []
    assert cases["open_cursors"] == []
    assert cases["use_after_close"] == []
    assert ownership["network_after"] == []
