"""Simulated cgroup failures. None of these establish kernel containment."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cgroup_lifecycle import explicit_direct_child_record, simulate  # noqa: E402

FAULTS = (
    "creation_denied",
    "placement_denied",
    "membership_failed",
    "deadline_before_placement",
    "deadline_before_release",
    "worker_exit_before_placement",
    "parent_crash_parked",
    "parent_crash_after_release",
    "grandchild_survives_direct_kill",
    "cgroup_kill_unavailable",
    "cgroup_kill_fails",
    "cgroup_remains_populated",
    "cleanup_fails",
    "path_missing",
)


@pytest.mark.parametrize("fault", FAULTS)
def test_simulated_fault_is_not_kernel_containment(fault: str) -> None:
    result = simulate(fault)
    assert result["evidence"] == "SIMULATED"
    assert result["kernel_containment"] is False
    assert result["equivalent_to_descendant_containment"] is False
    assert result["forked"] is False


def test_owner_crash_after_release_is_not_crash_safe() -> None:
    result = simulate("parent_crash_after_release")
    assert result["crash_safe"] is False
    assert result["cgroup_populated"] is True
    assert result["cleanup"] == "CLEANUP_INCOMPLETE"
    assert result["requires_live_owner_for_cgroup_kill"] is True


def test_direct_kill_does_not_count_as_descendant_containment() -> None:
    result = simulate("grandchild_survives_direct_kill")
    assert result["direct_child_alive"] is False
    assert result["descendant_alive"] is True
    assert result["actual_containment"] == "DIRECT_CHILD_ONLY"


def test_release_is_withheld_when_membership_or_placement_fails() -> None:
    for fault in ("creation_denied", "placement_denied", "membership_failed", "deadline_before_release"):
        result = simulate(fault)
        assert result.get("released", False) is False
        assert result["worker_executed"] is False


def test_explicit_direct_child_record_is_not_full_containment() -> None:
    record = explicit_direct_child_record()
    assert record["requested_policy"] == "DIRECT_CHILD_ONLY_EXPLICIT"
    assert record["actual_containment"] == "DIRECT_CHILD_ONLY"
    assert record["equivalent_to_descendant_containment"] is False
    assert record["kernel_containment"] is False


def test_unknown_fault_is_rejected() -> None:
    with pytest.raises(KeyError):
        simulate("pretend-success")


def test_sources_do_not_touch_trading_credentials_or_privilege() -> None:
    banned = ("forex_bot", "load_dotenv", "diagnostic_supervisor", "sudo", ".env", "api-fxtrade")
    for path in HERE.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8").lower()
        for item in banned:
            assert item not in text
