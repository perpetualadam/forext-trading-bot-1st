"""Stage D.15 consolidated and repeated lifespan checks. Does not import app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d15_harness import run_d15  # noqa: E402


@pytest.fixture(scope="module")
def lifespan(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d15(tmp_path_factory, "lifespan")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def safety(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = run_d15(tmp_path_factory, "safety")
    detail = payload.get("traceback", payload.get("error"))
    assert payload.get("error", "") == "", detail
    assert payload["_returncode"] == 0
    return payload


def test_l01_l13_normal_disabled_and_clean_shutdown(lifespan: dict) -> None:
    cases = lifespan["cases"]
    normal = cases["normal"]
    disabled = cases["disabled"]
    assert normal["yielded"] is True
    assert normal["escaped_type"] == ""
    assert normal["cleanup_errors"] == []
    assert normal["pending"] == 0
    assert normal["connection_open"] is True
    assert normal["stored_alive"] is False
    assert cases["normal_warnings"] == 0
    assert disabled["yielded"] is True
    assert disabled["stored_alive"] is False
    assert cases["disabled_warnings"] == 0
    assert "D12-STOP-01" not in disabled["cleanup_errors"]
    assert lifespan["network_after"] == []
    assert lifespan["escaped_final"] == []
    assert all(lifespan["guard_checks"].values())


def test_l14_l20_incomplete_stop_keeps_worker_and_database(lifespan: dict) -> None:
    snap = lifespan["cases"]["snap_a"]
    assert lifespan["cases"]["yielded_a"] is True
    assert snap["stored_alive"] is True
    assert snap["stop_event"] is True
    assert "D12-STOP-01" in snap["cleanup_errors"]
    assert snap["connection_open"] is True
    assert lifespan["cases"]["owned_pending_after"] == 0


def test_r01_r16_second_lifespan_refuses_same_worker(lifespan: dict) -> None:
    cases = lifespan["cases"]
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
    assert cases["worker_exit"]["escaped"] == []


def test_r17_r26_third_lifespan_starts_a_new_worker(lifespan: dict) -> None:
    cases = lifespan["cases"]
    assert cases["yielded_c"] is True
    assert cases["fresh_worker"] is True
    assert cases["seen"][2] == "START_STARTED"
    assert cases["third_warnings"] == 0
    assert cases["snap_c_after"]["stored_alive"] is False
    assert "D12-STOP-01" not in cases["snap_c_after"]["cleanup_errors"]
    assert cases["snap_c_after"]["connection_open"] is True


def test_l08_l10_handled_and_unknown_start_stay_non_fatal(lifespan: dict) -> None:
    cases = lifespan["cases"]
    assert cases["failed_yielded"] is True
    assert cases["failed_escaped"] == ""
    assert cases["failed_phrase"] is True
    assert cases["failed_refusal"] is False
    assert cases["unknown_yielded"] is True
    assert cases["unknown_escaped"] == ""
    assert cases["unknown_phrase"] is True
    assert cases["failed_snap"]["connection_open"] is True


def test_s01_s19_safety_state_and_strategy_defaults(safety: dict) -> None:
    cases = safety["cases"]
    assert cases["valid"]["initialised"] is True
    assert cases["valid"]["authorisation"] == "BLOCKED"
    assert cases["valid"]["active"] == {
        "scalp": False,
        "trend": False,
        "mean_reversion": False,
        "swing_trend": False,
        "swing_mean_reversion": False,
        "swing_breakout": False,
    }
    assert cases["preserved"] == {"preserve": True}
    assert cases["string_true_inactive"] is True
    assert cases["unconfirmed"] == "PermissionError"
    assert cases["explicit_true"] is True
    assert cases["restored_inactive"] is True
    assert cases["corrupt"]["initialised"] is False
    assert cases["corrupt"]["authorisation"] == "BLOCKED"
    assert cases["corrupt_bytes_kept"] is True
    assert cases["future"]["initialised"] is False
    assert cases["future"]["authorisation"] == "BLOCKED"
    assert cases["future_bytes_kept"] is True
    assert cases["invalid"]["initialised"] is False
    assert cases["invalid"]["authorisation"] == "BLOCKED"
    assert cases["write_failure"]["escaped"] == ""
    assert cases["write_failure"]["initialised"] is False
    assert cases["write_failure"]["authorisation"] == "BLOCKED"
    assert cases["write_failure"]["temporary_left"] is False
    assert safety["network_after"] == []
