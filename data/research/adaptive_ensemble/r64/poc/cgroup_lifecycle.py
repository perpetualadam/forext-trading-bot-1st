"""Cgroup v2 lifecycle. The kernel path runs only after a private child cgroup exists.

Simulated faults never create a process and never write cgroup.kill.
A kill request aimed at the caller's current cgroup is refused.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

from cgroup_probe import CGROUP_DELEGATION_UNAVAILABLE, current_cgroup_path, probe_host

REQUIRE_DESCENDANT_CONTAINMENT = "REQUIRE_DESCENDANT_CONTAINMENT"
DIRECT_CHILD_ONLY_EXPLICIT = "DIRECT_CHILD_ONLY_EXPLICIT"


def strict_open(directory: Path, deadline_at: float) -> dict[str, object]:
    """Refuse worker execution unless a private delegated cgroup was created."""
    directory.mkdir(parents=True, exist_ok=True)
    report = probe_host()
    if not report["delegated"]:
        return {
            "requested_policy": REQUIRE_DESCENDANT_CONTAINMENT,
            "actual_containment": "CONTAINMENT_UNAVAILABLE",
            "status": report["status"],
            "error": CGROUP_DELEGATION_UNAVAILABLE,
            "evidence": "REAL",
            "kernel_containment": False,
            "forked": False,
            "worker_executed": False,
            "pid": 0,
            "equivalent_to_descendant_containment": False,
            "side_effect": False,
            "reason": report["reason"],
        }
    if time.monotonic() >= deadline_at:
        return _refused("DEADLINE_BEFORE_CREATE")
    return run_contained(directory, deadline_at)


def kill_is_refused(path: Path, *, owned: bool) -> str:
    """Permit a kill file only for a private child of the caller's cgroup."""
    current = current_cgroup_path()
    if not owned or current is None:
        return "CGROUP_KILL_REFUSED"
    try:
        candidate = path.resolve()
        here = current.resolve()
    except OSError:
        return "CGROUP_KILL_REFUSED"
    if candidate == here or candidate in here.parents:
        return "CGROUP_KILL_REFUSED"
    if here not in candidate.parents:
        return "CGROUP_KILL_REFUSED"
    if not path.is_dir() or not (path / "cgroup.kill").is_file():
        return "CGROUP_KILL_UNAVAILABLE"
    return "CGROUP_KILL_PERMITTED"


def simulate(fault: str) -> dict[str, object]:
    """State-machine results. evidence is SIMULATED. This is not kernel containment."""
    base = {
        "evidence": "SIMULATED",
        "kernel_containment": False,
        "requested_policy": REQUIRE_DESCENDANT_CONTAINMENT,
        "equivalent_to_descendant_containment": False,
        "forked": False,
        "worker_executed": False,
        "harness_intervened": False,
        "crash_safe": False,
    }
    table: dict[str, dict[str, object]] = {
        "creation_denied": {"error": "CGROUP_CREATION_DENIED", "state": "NOT_STARTED", "actual_containment": "CONTAINMENT_UNAVAILABLE"},
        "placement_denied": {"error": "CGROUP_PLACEMENT_DENIED", "state": "WORKER_PARKED", "released": False, "actual_containment": "CONTAINMENT_UNAVAILABLE"},
        "membership_failed": {"error": "MEMBERSHIP_NOT_CONFIRMED", "state": "OWNERSHIP_UNCERTAIN", "released": False},
        "deadline_before_placement": {"error": "DEADLINE_BEFORE_PLACEMENT", "state": "NOT_STARTED", "released": False},
        "deadline_before_release": {"error": "DEADLINE_BEFORE_RELEASE", "state": "WORKER_CONTAINED", "released": False, "side_effect": False},
        "worker_exit_before_placement": {"error": "EXIT_BEFORE_PLACEMENT", "state": "EXIT_VERIFIED", "released": False, "exit_verified": True},
        "parent_crash_parked": {"error": "OWNER_EXIT_BEFORE_RELEASE", "state": "NOT_RELEASED", "released": False, "cgroup_populated": False},
        "parent_crash_after_release": {
            "error": "OWNER_EXIT_AFTER_RELEASE",
            "state": "CLEANUP_INCOMPLETE",
            "released": True,
            "cgroup_populated": True,
            "crash_safe": False,
            "cleanup": "CLEANUP_INCOMPLETE",
            "requires_live_owner_for_cgroup_kill": True,
        },
        "grandchild_survives_direct_kill": {
            "error": "DESCENDANT_SURVIVED_DIRECT_KILL",
            "state": "CLEANUP_INCOMPLETE",
            "direct_child_alive": False,
            "descendant_alive": True,
            "actual_containment": "DIRECT_CHILD_ONLY",
        },
        "cgroup_kill_unavailable": {"error": "CGROUP_KILL_UNAVAILABLE", "state": "CLEANUP_INCOMPLETE", "cleanup": "CLEANUP_INCOMPLETE"},
        "cgroup_kill_fails": {"error": "CGROUP_KILL_FAILED", "state": "CLEANUP_INCOMPLETE", "cleanup": "CLEANUP_INCOMPLETE"},
        "cgroup_remains_populated": {"error": "CGROUP_STILL_POPULATED", "state": "CLEANUP_INCOMPLETE", "cgroup_populated": True, "removed": False},
        "cleanup_fails": {"error": "CGROUP_CLEANUP_FAILED", "state": "CLEANUP_INCOMPLETE", "removed": False},
        "path_missing": {"error": "CGROUP_PATH_MISSING", "state": "OWNERSHIP_UNCERTAIN", "kill_written": False},
    }
    if fault not in table:
        raise KeyError(fault)
    return base | table[fault]


def explicit_direct_child_record() -> dict[str, object]:
    return {
        "requested_policy": DIRECT_CHILD_ONLY_EXPLICIT,
        "actual_containment": "DIRECT_CHILD_ONLY",
        "equivalent_to_descendant_containment": False,
        "kernel_containment": False,
        "evidence": "POLICY_RECORD",
        "justified_for": "r61-diagnostic-worker-current-source",
    }


def run_contained(directory: Path, deadline_at: float) -> dict[str, object]:
    """Kernel lifecycle. Entered only when probe_host reports delegated True."""
    report = probe_host()
    if not report["delegated"]:
        return strict_open(directory, deadline_at)
    base = Path(str(report["base"]))
    private = base / f"r64-run-{os.getpid()}-{time.monotonic_ns()}"
    owned = False
    pid = 0
    pidfd = -1
    park = -1
    try:
        private.mkdir()
        owned = True
        if time.monotonic() >= deadline_at:
            return _refused("DEADLINE_BEFORE_PLACEMENT")
        read_end, park = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(park)
                token = os.read(read_end, 1)
                os.close(read_end)
                if token != b"R":
                    os._exit(0)
                worker = Path(__file__).with_name("synthetic_worker.py")
                os.execv(sys.executable, [sys.executable, "-B", str(worker), "grand", str(directory / "grand.txt"), str(directory / "ready.txt")])
            finally:
                os._exit(127)
        os.close(read_end)
        if hasattr(os, "pidfd_open"):
            pidfd = os.pidfd_open(pid)
        if time.monotonic() >= deadline_at:
            return _stop_unreleased(pid, pidfd, "DEADLINE_BEFORE_PLACEMENT")
        try:
            (private / "cgroup.procs").write_text(str(pid), encoding="utf-8")
        except OSError:
            return _stop_unreleased(pid, pidfd, "CGROUP_PLACEMENT_DENIED")
        members = (private / "cgroup.procs").read_text(encoding="utf-8").split()
        if str(pid) not in members:
            return _stop_unreleased(pid, pidfd, "MEMBERSHIP_NOT_CONFIRMED")
        if time.monotonic() >= deadline_at:
            return _stop_unreleased(pid, pidfd, "DEADLINE_BEFORE_RELEASE")
        os.write(park, b"R")
        os.close(park)
        park = -1
        decision = kill_is_refused(private, owned=True)
        if decision != "CGROUP_KILL_PERMITTED":
            _signal(pid, pidfd)
            return {"error": decision, "state": "CLEANUP_INCOMPLETE", "evidence": "REAL", "kernel_containment": False, "forked": True}
        (private / "cgroup.kill").write_text("1", encoding="utf-8")
        dead = _wait(pid, 5)
        still = (private / "cgroup.procs").read_text(encoding="utf-8").strip()
        return {
            "error": "NONE" if dead and not still else "CGROUP_STILL_POPULATED",
            "state": "EXIT_VERIFIED" if dead and not still else "CLEANUP_INCOMPLETE",
            "evidence": "REAL",
            "kernel_containment": bool(dead and not still),
            "forked": True,
            "pid": pid,
            "requested_policy": REQUIRE_DESCENDANT_CONTAINMENT,
            "actual_containment": "DESCENDANT_CONTAINMENT_ACTIVE" if dead and not still else "CLEANUP_INCOMPLETE",
        }
    finally:
        if park >= 0:
            os.close(park)
            park = -1
        if pid and _alive(pid):
            _signal(pid, pidfd)
            _wait(pid, 3)
        if pidfd >= 0:
            os.close(pidfd)
        if owned:
            _rmdir_if_empty(private)


def _refused(error: str) -> dict[str, object]:
    return {
        "requested_policy": REQUIRE_DESCENDANT_CONTAINMENT,
        "actual_containment": "CONTAINMENT_UNAVAILABLE",
        "error": error,
        "evidence": "REAL",
        "kernel_containment": False,
        "forked": False,
        "worker_executed": False,
        "equivalent_to_descendant_containment": False,
    }


def _stop_unreleased(pid: int, pidfd: int, error: str) -> dict[str, object]:
    _signal(pid, pidfd)
    dead = _wait(pid, 3)
    return {
        "error": error,
        "state": "EXIT_VERIFIED" if dead else "CLEANUP_INCOMPLETE",
        "evidence": "REAL",
        "kernel_containment": False,
        "forked": True,
        "released": False,
        "worker_executed": False,
        "exit_verified": dead,
        "pid": pid,
    }


def _signal(pid: int, pidfd: int) -> None:
    if pidfd >= 0 and hasattr(os, "pidfd_send_signal"):
        try:
            os.pidfd_send_signal(pidfd, signal.SIGKILL)
            return
        except OSError:
            pass
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _wait(pid: int, wait_s: float) -> bool:
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        try:
            found, _status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return True
        if found == pid:
            return True
        time.sleep(0.02)
    return not _alive(pid)


def _alive(pid: int) -> bool:
    stat = Path(f"/proc/{pid}/stat")
    if not stat.is_file():
        return False
    state = stat.read_text(encoding="utf-8").rsplit(")", 1)[-1].split(maxsplit=1)[0]
    return state not in {"Z", "X"}


def _rmdir_if_empty(path: Path) -> None:
    events = path / "cgroup.events"
    try:
        text = events.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if "populated 0" not in text and (path / "cgroup.procs").is_file():
        procs = (path / "cgroup.procs").read_text(encoding="utf-8").strip()
        if procs:
            return
    try:
        path.rmdir()
    except OSError:
        pass
