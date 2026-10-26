"""Stage D.13 lifespan reporting. This module does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d13_harness import run_d13  # noqa: E402

REFUSAL = "Telegram startup refused"


@pytest.fixture(scope="module")
def repeated(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d13(tmp_path_factory, "repeated")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def ownership(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d13(tmp_path_factory, "ownership")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_s24_s27_repeated_lifespan_records_incomplete_stop(repeated: dict) -> None:
    cases = repeated["cases"]
    assert cases["yielded_a"] is True
    assert cases["snap_a"]["stored_alive"] is True
    assert "D12-STOP-01" in cases["snap_a"]["cleanup_errors"]
    assert cases["yielded_b"] is True
    assert cases["escaped_b"] == ""
    assert cases["same_worker"] is True
    assert cases["snap_b"]["stop_event"] is True
    assert "D12-STOP-01" in cases["snap_b"]["cleanup_errors"]
    assert cases["connection_reused_ab"] is True
    assert cases["yielded_c"] is True
    assert cases["fresh_worker"] is True
    assert cases["snap_c_after"]["stored_alive"] is False
    assert "D12-STOP-01" not in cases["snap_c_after"]["cleanup_errors"]
    assert repeated["network_after"] == []
    assert repeated["escaped_final"] == []


def test_s05_s06_start_refusal_is_not_observable(repeated: dict) -> None:
    text = str(repeated["cases"])
    assert REFUSAL not in text
    assert "D12-START-01" not in text


def test_s21_s28_s38_s39_database_ownership(ownership: dict) -> None:
    cases = ownership["cases"]
    assert cases["delayed"]["stop"]["return_value"] == (
        "STOP_INCOMPLETE_WORKER_ALIVE"
    )
    assert cases["delayed"]["connect_delta"] == 0
    assert cases["delayed"]["queries"] == []
    assert cases["gate"]["queries"] == []
    assert cases["gate"]["connect_delta"] == 0
    assert cases["open_connections"] == []
    assert ownership["network_after"] == []
