"""Linux direct-child ownership, with cgroup v2 only when this user can create one.

The default policy refuses to exec when descendant containment is required and
no cgroup can be created. An explicit direct-child policy is labeled as such.
Process groups are not used.
"""

from __future__ import annotations

import ctypes
import os
import signal
import sys
import time
from pathlib import Path

from lifecycle_contract import (
    CLEANUP_INCOMPLETE,
    CONTAINMENT_UNAVAILABLE,
    DESCENDANT_CONTAINMENT_ACTIVE,
    DESCENDANT_CONTAINMENT_AVAILABLE,
    DIRECT_CHILD_ONLY,
    Session,
)

PR_SET_PDEATHSIG = 1


def probe(requested_policy: str) -> dict[str, object]:
    available, detail = _cgroup_status()
    unsupported = (
        "process groups do not contain a setsid child",
        "pidfd does not cover grandchildren",
        "PR_SET_PDEATHSIG covers the direct child only",
        "blocked fork is not cancellable",
        "bare-metal Linux, VPS, and container hosts were not probed here",
    )
    if not available:
        unsupported = unsupported + (detail,)
    return {
        "operating_system": sys.platform,
        "mechanisms": ("cgroup-v2", "cgroup.kill") if available else ("park-before-exec", "pidfd", "parent-death-signal"),
        "requested_policy": requested_policy,
        "descendant_available": available,
        "actual_if_requested": DESCENDANT_CONTAINMENT_AVAILABLE if available else CONTAINMENT_UNAVAILABLE,
        "direct_child_level": DIRECT_CHILD_ONLY,
        "descendant_level": DESCENDANT_CONTAINMENT_AVAILABLE if available else CONTAINMENT_UNAVAILABLE,
        "unsupported": unsupported,
        "detail": detail,
    }


def pid_active(pid: int) -> bool:
    if pid <= 0:
        return False
    stat = Path(f"/proc/{pid}/stat")
    if not stat.is_file():
        return False
    state = stat.read_text(encoding="utf-8").rsplit(")", 1)[-1].split(maxsplit=1)[0]
    return state not in {"Z", "X"}


def create(manager, mode: str, deadline_at: float, directory: Path, before_create=None) -> Session:
    session = _blank(manager, directory)
    caps = probe(manager.requested_policy)
    session.mechanisms = tuple(caps["mechanisms"])
    session.unsupported = tuple(caps["unsupported"])
    if before_create is not None:
        before_create()
    if time.monotonic() >= deadline_at:
        session.startup_deadline = "EXPIRED_BEFORE_CREATE"
        session.error = "DEADLINE_BEFORE_CREATE"
        return session
    if manager.require_descendant_containment and not caps["descendant_available"]:
        session.error = "CONTAINMENT_UNAVAILABLE"
        session.actual_containment = CONTAINMENT_UNAVAILABLE
        session.descendant_containment = CONTAINMENT_UNAVAILABLE
        session.state = "NOT_STARTED"
        session.pid = 0
        return session
    if not manager.require_descendant_containment:
        session.actual_containment = DIRECT_CHILD_ONLY
        session.descendant_containment = DIRECT_CHILD_ONLY
    worker = Path(__file__).with_name("synthetic_worker.py")
    argv = _argv(mode, session, worker)
    read_end, write_end = os.pipe()
    parent = os.getpid()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(write_end)
            _arm_death_signal(parent)
            null = os.open(os.devnull, os.O_RDWR)
            os.dup2(null, 0)
            os.dup2(null, 1)
            os.dup2(null, 2)
            if null > 2:
                os.close(null)
            token = os.read(read_end, 1)
            os.close(read_end)
            if token != b"R":
                os._exit(0)
            os.execv(sys.executable, argv)
        finally:
            os._exit(127)
    os.close(read_end)
    session.pid = pid
    session._native = {"pidfd": -1, "park": write_end}
    if hasattr(os, "pidfd_open"):
        try:
            session._native["pidfd"] = os.pidfd_open(pid)
            session.direct_child_ownership = "pidfd"
        except OSError:
            session.direct_child_ownership = "pid-only"
    else:
        session.direct_child_ownership = "pid-only"
        session.unsupported = session.unsupported + ("pidfd_open is not available",)
    session.state = "WORKER_CREATED"
    return session


def establish(session: Session) -> Session:
    if session.state != "WORKER_CREATED":
        return session
    if session.requested_policy.endswith("EXPLICIT") or session.actual_containment == DIRECT_CHILD_ONLY:
        session.actual_containment = DIRECT_CHILD_ONLY
        session.descendant_containment = DIRECT_CHILD_ONLY
        session.state = "WORKER_CONTAINED"
        return session
    placed, detail = _place_in_cgroup(session)
    if not placed:
        session.actual_containment = CONTAINMENT_UNAVAILABLE
        session.descendant_containment = CONTAINMENT_UNAVAILABLE
        session.error = "CONTAINMENT_UNAVAILABLE"
        session.unsupported = session.unsupported + (detail,)
        session.state = "OWNERSHIP_UNCERTAIN"
        return session
    session.actual_containment = DESCENDANT_CONTAINMENT_ACTIVE
    session.descendant_containment = DESCENDANT_CONTAINMENT_ACTIVE
    session.mechanisms = ("cgroup-v2", "cgroup.kill", "park-before-exec")
    session.state = "WORKER_CONTAINED"
    return session


def start(session: Session, deadline_at: float, *, before_release=None) -> Session:
    if before_release is not None:
        before_release(session.pid)
    if session.actual_containment not in {DESCENDANT_CONTAINMENT_ACTIVE, DIRECT_CHILD_ONLY}:
        session.error = session.error or "RELEASE_REFUSED"
        return session
    if time.monotonic() >= deadline_at:
        session.startup_deadline = "EXPIRED_BEFORE_RELEASE"
        session.error = "DEADLINE_BEFORE_RELEASE"
        _drop_park(session)
        return session
    park = session._native.get("park", -1)
    if park >= 0:
        os.write(park, b"R")
        os.close(park)
        session._native["park"] = -1
    session.state = "WORKER_RELEASED"
    return session


def wait_ready(session: Session, deadline_at: float) -> Session:
    if session.error == "DEADLINE_BEFORE_RELEASE" or session.state != "WORKER_RELEASED":
        return session
    target = session._side if session._ready is None else session._ready
    appeared = False if target is None else _poll_file(target, deadline_at)
    refresh(session)
    if appeared:
        session.ready = True
        session.worker_executed = True
        session.state = "WORKER_READY"
        return session
    if session.pid and not pid_active(session.pid):
        session.error = "EXIT_BEFORE_READY"
        session.exit_verified = True
        session.exit_verification = "EXIT_VERIFIED"
        session.state = "EXIT_VERIFIED"
        return session
    session.startup_deadline = "EXPIRED_BEFORE_READY"
    session.error = "DEADLINE_BEFORE_READY"
    terminate(session)
    verify_exit(session)
    return session


def terminate(session: Session) -> Session:
    session.state = "TERMINATION_ATTEMPTED"
    _drop_park(session)
    if session.cgroup_path:
        try:
            Path(session.cgroup_path, "cgroup.kill").write_text("1", encoding="utf-8")
        except OSError:
            pass
    if session.pid:
        _signal(session.pid, session._native.get("pidfd", -1), signal.SIGKILL)
    return session


def verify_exit(session: Session, deadline_s: float = 5.0) -> Session:
    if not session.pid:
        session.exit_verified = True
        session.exit_verification = "EXIT_VERIFIED"
        session.state = "EXIT_VERIFIED"
        return session
    dead = _wait(session.pid, deadline_s)
    session.exit_verified = dead
    session.exit_verification = "EXIT_VERIFIED" if dead else CLEANUP_INCOMPLETE
    session.state = "EXIT_VERIFIED" if dead else CLEANUP_INCOMPLETE
    session.cleanup = session.state
    refresh(session)
    return session


def cleanup(session: Session) -> Session:
    refresh(session)
    if session.pid and pid_active(session.pid):
        session.harness_intervened = True
        _signal(session.pid, session._native.get("pidfd", -1), signal.SIGKILL)
        _wait(session.pid, 3)
    if session.descendant_pid and pid_active(session.descendant_pid):
        session.harness_intervened = True
        session.descendant_alive = True
        try:
            os.kill(session.descendant_pid, signal.SIGKILL)
        except OSError:
            pass
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and pid_active(session.descendant_pid):
            time.sleep(0.02)
    pidfd = session._native.get("pidfd", -1)
    if pidfd >= 0:
        os.close(pidfd)
        session._native["pidfd"] = -1
    _drop_park(session)
    refresh(session)
    return session


def refresh(session: Session) -> None:
    if session._grand is not None and session._grand.is_file() and not session.descendant_pid:
        text = session._grand.read_text(encoding="utf-8").strip()
        if text.isdigit():
            session.descendant_pid = int(text)
    if session.descendant_pid:
        session.descendant_alive = pid_active(session.descendant_pid)
    if session._side is not None and session._side.is_file() and session._side.stat().st_size > 0:
        session.side_effect_written = True
        session.worker_executed = True


def _blank(manager, directory: Path) -> Session:
    directory.mkdir(parents=True, exist_ok=True)
    session = Session()
    session.requested_policy = manager.requested_policy
    session._side = directory / "side.txt"
    session._grand = directory / "grand.txt"
    session._ready = directory / "ready.txt"
    return session


def _argv(mode: str, session: Session, worker: Path) -> list[str]:
    base = [sys.executable, "-B", str(worker), mode]
    if mode == "side":
        session._ready = None
        return base + [str(session._side)]
    if mode == "grand":
        return base + [str(session._grand), str(session._ready)]
    if mode == "exit":
        session._ready = None
        return base
    return base + [str(session._ready)]


def _cgroup_status() -> tuple[bool, str]:
    try:
        text = Path("/proc/self/cgroup").read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"CONTAINMENT_UNAVAILABLE:{exc.errno}"
    relative = ""
    for line in text.splitlines():
        parts = line.split(":")
        if parts and parts[0] == "0":
            relative = parts[-1]
            break
    target = Path("/sys/fs/cgroup") / relative.lstrip("/") / f"r63-poc-{os.getpid()}"
    try:
        target.mkdir()
    except OSError as exc:
        return False, f"CONTAINMENT_UNAVAILABLE:{exc.errno}"
    kill = target / "cgroup.kill"
    present = kill.is_file()
    try:
        target.rmdir()
    except OSError:
        pass
    if not present:
        return False, "CONTAINMENT_UNAVAILABLE:no-cgroup.kill"
    return True, "CGROUP_V2_DELEGATED"


def _place_in_cgroup(session: Session) -> tuple[bool, str]:
    text = Path("/proc/self/cgroup").read_text(encoding="utf-8")
    relative = ""
    for line in text.splitlines():
        parts = line.split(":")
        if parts and parts[0] == "0":
            relative = parts[-1]
            break
    target = Path("/sys/fs/cgroup") / relative.lstrip("/") / f"r63-poc-{os.getpid()}-{session.pid}"
    try:
        target.mkdir()
    except OSError as exc:
        return False, f"CONTAINMENT_UNAVAILABLE:{exc.errno}"
    try:
        (target / "cgroup.procs").write_text(str(session.pid), encoding="utf-8")
    except OSError as exc:
        try:
            target.rmdir()
        except OSError:
            pass
        return False, f"CONTAINMENT_UNAVAILABLE:{exc.errno}"
    if not (target / "cgroup.kill").is_file():
        return False, "CONTAINMENT_UNAVAILABLE:no-cgroup.kill"
    session.cgroup_path = str(target)
    return True, "CGROUP_V2_DELEGATED"


def _arm_death_signal(parent_pid: int) -> None:
    if os.getppid() != parent_pid:
        os._exit(0)
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        if libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
            os._exit(0)
    except OSError:
        os._exit(0)
    if os.getppid() != parent_pid:
        os._exit(0)


def _drop_park(session: Session) -> None:
    park = session._native.get("park", -1)
    if park is not None and park >= 0:
        os.close(park)
        session._native["park"] = -1


def _signal(pid: int, pidfd: int, sig: int) -> None:
    if pidfd >= 0 and hasattr(os, "pidfd_send_signal"):
        try:
            os.pidfd_send_signal(pidfd, sig)
            return
        except OSError:
            pass
    try:
        os.kill(pid, sig)
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
    return not pid_active(pid)


def _poll_file(path: Path, deadline_at: float) -> bool:
    while time.monotonic() < deadline_at:
        if path.is_file() and path.stat().st_size > 0:
            return True
        time.sleep(0.02)
    return path.is_file() and path.stat().st_size > 0
