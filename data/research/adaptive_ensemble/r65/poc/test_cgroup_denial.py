"""Portable cgroup-denial regressions. Errno 13 is one denial, not the only one."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cgroup_denial import classify_cgroup_creation, probe_private_child, refuse_strict  # noqa: E402


@pytest.mark.parametrize(
    ("errno", "classification"),
    [(13, "EACCES"), (30, "EROFS"), (1, "EPERM")],
)
def test_known_denial_errnos_stay_distinct_and_fail_closed(tmp_path: Path, errno: int, classification: str) -> None:
    outcome = refuse_strict(tmp_path, classify_cgroup_creation(errno))
    assert outcome["classification"] == classification
    assert outcome["errno"] == errno
    assert outcome["worker_started"] is False
    assert outcome["containment_active"] is False
    assert outcome["side_effect"] is False
    assert outcome["requested_policy"] == "REQUIRE_DESCENDANT_CONTAINMENT"
    assert not (tmp_path / "side.txt").exists()


def test_missing_cgroup_feature_does_not_start_a_worker(tmp_path: Path) -> None:
    outcome = refuse_strict(tmp_path, classify_cgroup_creation(None, feature_missing=True))
    assert outcome["classification"] == "FEATURE_MISSING"
    assert outcome["errno"] is None
    assert outcome["worker_started"] is False
    assert not (tmp_path / "ready.txt").exists()


def test_unclassified_errno_is_not_relabelled_and_still_refuses(tmp_path: Path) -> None:
    outcome = refuse_strict(tmp_path, classify_cgroup_creation(95))
    assert outcome["classification"] == "UNCLASSIFIED_OS_ERROR"
    assert outcome["errno"] == 95
    assert outcome["worker_started"] is False
    assert outcome["containment_active"] is False


def test_a_created_probe_directory_is_not_containment(tmp_path: Path) -> None:
    outcome = refuse_strict(tmp_path, classify_cgroup_creation(None))
    outcome["classification"] = "PROBE_DIRECTORY_CREATED"
    assert outcome["containment_active"] is False
    assert outcome["worker_started"] is False
    assert outcome["equivalent_to_descendant_containment"] is False
    assert not list(tmp_path.glob("side.txt"))


def test_host_probe_reports_the_real_errno_and_does_not_launch(tmp_path: Path) -> None:
    started = time.monotonic()
    outcome = refuse_strict(tmp_path, probe_private_child())
    assert time.monotonic() - started < 5
    assert outcome["worker_started"] is False
    assert outcome["containment_active"] is False
    assert outcome["side_effect"] is False
    assert not (tmp_path / "side.txt").exists()
    if sys.platform.startswith("linux"):
        assert outcome["classification"] in {"EACCES", "EROFS", "EPERM", "FEATURE_MISSING", "UNCLASSIFIED_OS_ERROR", "PROBE_DIRECTORY_CREATED"}
        if outcome["classification"] == "EACCES":
            assert outcome["errno"] == 13
        elif outcome["classification"] == "EROFS":
            assert outcome["errno"] == 30
        elif outcome["classification"] == "EPERM":
            assert outcome["errno"] == 1
        elif outcome["classification"] == "UNCLASSIFIED_OS_ERROR":
            assert isinstance(outcome["errno"], int)
            assert outcome["errno"] not in {1, 13, 30}
    else:
        assert outcome["classification"] == "UNSUPPORTED_PLATFORM"
        assert outcome["worker_started"] is False
