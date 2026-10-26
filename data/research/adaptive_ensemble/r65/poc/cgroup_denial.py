"""Fail-closed classification of a private-cgroup mkdir.

Errno 13, 30, and 1 are different operating-system results. Each one still
refuses to start a worker. An unclassified errno stays fail-closed and keeps
its own name. Creating a directory is not containment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REQUIRE_DESCENDANT_CONTAINMENT = "REQUIRE_DESCENDANT_CONTAINMENT"

CLASS_BY_ERRNO = {
    13: "EACCES",
    30: "EROFS",
    1: "EPERM",
}


def classify_cgroup_creation(errno: int | None, *, feature_missing: bool = False) -> dict[str, object]:
    if feature_missing:
        classification = "FEATURE_MISSING"
        recorded = None
    elif errno in CLASS_BY_ERRNO:
        classification = CLASS_BY_ERRNO[int(errno)]
        recorded = int(errno)
    elif errno is None:
        classification = "PROBE_WITHOUT_OS_ERROR"
        recorded = None
    else:
        classification = "UNCLASSIFIED_OS_ERROR"
        recorded = int(errno)
    return {
        "requested_policy": REQUIRE_DESCENDANT_CONTAINMENT,
        "classification": classification,
        "errno": recorded,
        "containment_active": False,
        "worker_started": False,
        "equivalent_to_descendant_containment": False,
    }


def refuse_strict(directory: Path, outcome: dict[str, object]) -> dict[str, object]:
    """Record a refusal. This function does not create a worker or a side-effect file."""
    directory.mkdir(parents=True, exist_ok=True)
    record = dict(outcome)
    record["worker_started"] = False
    record["containment_active"] = False
    record["side_effect"] = False
    record["requested_policy"] = REQUIRE_DESCENDANT_CONTAINMENT
    return record


def probe_private_child() -> dict[str, object]:
    """One mkdir under the current cgroup. A created directory is removed.

    The returned record never reports containment and never starts a worker.
    """
    if not sys.platform.startswith("linux"):
        outcome = classify_cgroup_creation(None, feature_missing=True)
        outcome["classification"] = "UNSUPPORTED_PLATFORM"
        return outcome
    cgroup = _self_cgroup()
    if not cgroup:
        return classify_cgroup_creation(None, feature_missing=True)
    base = Path("/sys/fs/cgroup") / cgroup.lstrip("/")
    if not (base / "cgroup.procs").is_file() or not (base / "cgroup.kill").is_file():
        return classify_cgroup_creation(None, feature_missing=True)
    target = base / f"r65-probe-{os.getpid()}"
    try:
        target.mkdir()
    except OSError as exc:
        return classify_cgroup_creation(exc.errno)
    else:
        try:
            target.rmdir()
        except OSError:
            pass
        outcome = classify_cgroup_creation(None)
        outcome["classification"] = "PROBE_DIRECTORY_CREATED"
        outcome["directory_removed"] = not target.exists()
        return outcome


def _self_cgroup() -> str:
    try:
        text = Path("/proc/self/cgroup").read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        parts = line.split(":")
        if parts and parts[0] == "0":
            return parts[-1]
    return ""
