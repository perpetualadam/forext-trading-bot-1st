"""Linux direct-child ownership for one synthetic worker.

The child stays parked until it reads the byte R. A cgroup is attempted and,
on this host, expected to be unavailable. pidfd identifies the direct child.
It does not contain descendants. Process groups are not used.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path


def cgroup_probe() -> str:
    try:
        text = Path("/proc/self/cgroup").read_text(encoding="utf-8")
    except OSError as exc:
        return f"CONTAINMENT_UNAVAILABLE:{exc.errno}"
    relative = ""
    for line in text.splitlines():
        parts = line.split(":")
        if parts and parts[0] == "0":
            relative = parts[-1]
            break
    target = Path("/sys/fs/cgroup") / relative.lstrip("/") / f"r62-poc-{os.getpid()}"
    try:
        target.mkdir()
    except OSError as exc:
        return f"CONTAINMENT_UNAVAILABLE:{exc.errno}"
    try:
        target.rmdir()
    except OSError:
        pass
    return "CGROUP_AVAILABLE"


def pid_active(pid: int) -> bool:
    if pid <= 0:
        return False
    stat = Path(f"/proc/{pid}/stat")
    if not stat.is_file():
        return False
    state = stat.read_text(encoding="utf-8").rsplit(")", 1)[-1].split(maxsplit=1)[0]
    return state not in {"Z", "X"}


class Session:
    def __init__(self) -> None:
        self.state = "NOT_STARTED"
        self.error = "NONE"
        self.pid = 0
        self.contained = False
        self.ready = False
        self.exit_verified = False
        self.harness_intervened = False
        self.descendant_pid = 0
        self.descendant_alive = False
        self.side_effect_written = False
        self.cgroup = cgroup_probe()
        self.pidfd = -1
        self._side: Path | None = None
        self._grand: Path | None = None

    def _refresh(self) -> None:
        if self._grand is not None and self._grand.is_file() and not self.descendant_pid:
            text = self._grand.read_text(encoding="utf-8").strip()
            if text.isdigit():
                self.descendant_pid = int(text)
        if self.descendant_pid:
            self.descendant_alive = pid_active(self.descendant_pid)
        if self._side is not None:
            self.side_effect_written = self._side.is_file()

    def shutdown(self, wait_s: float = 5.0) -> str:
        self.state = "SHUTDOWN_REQUESTED"
        if self.pid:
            self.state = "TERMINATION_ATTEMPTED"
            _signal(self.pid, self.pidfd, signal.SIGKILL)
            self.exit_verified = _wait(self.pid, wait_s)
            self.state = "EXIT_VERIFIED" if self.exit_verified else "CLEANUP_INCOMPLETE"
        self._refresh()
        return self.state

    def close(self) -> None:
        self._refresh()
        if self.pid and pid_active(self.pid):
            self.harness_intervened = True
            _signal(self.pid, self.pidfd, signal.SIGKILL)
            _wait(self.pid, 3)
        self._refresh()
        if self.descendant_pid and pid_active(self.descendant_pid):
            self.harness_intervened = True
            try:
                os.kill(self.descendant_pid, signal.SIGKILL)
            except OSError:
                pass
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and pid_active(self.descendant_pid):
                time.sleep(0.02)
        if self.pidfd >= 0:
            os.close(self.pidfd)
            self.pidfd = -1
        self._refresh()


def launch(
    mode: str,
    deadline_at: float,
    directory: Path,
    *,
    before_create=None,
    after_create=None,
) -> Session:
    session = Session()
    session._side = directory / "side.txt"
    session._grand = directory / "grand.txt"
    if before_create is not None:
        before_create()
    if time.monotonic() >= deadline_at:
        session.error = "DEADLINE_BEFORE_CREATE"
        return session
    worker = Path(__file__).with_name("synthetic_worker.py")
    if mode == "side":
        argv = [sys.executable, "-B", str(worker), "side", str(session._side)]
    elif mode == "grand":
        argv = [sys.executable, "-B", str(worker), "grand", str(session._grand), str(directory / "ready.txt")]
    elif mode == "exit":
        argv = [sys.executable, "-B", str(worker), "exit"]
    else:
        argv = [sys.executable, "-B", str(worker), mode, str(directory / "ready.txt")]
    read_end, write_end = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(write_end)
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
    session.state = "WORKER_CREATED"
    if hasattr(os, "pidfd_open"):
        try:
            session.pidfd = os.pidfd_open(pid)
        except OSError:
            session.pidfd = -1
    if after_create is not None:
        after_create(pid)
    if time.monotonic() >= deadline_at:
        session.error = "DEADLINE_BEFORE_RESUME"
        os.close(write_end)
        session.shutdown()
        return session
    os.write(write_end, b"R")
    os.close(write_end)
    if mode == "exit":
        session.exit_verified = _wait(pid, 3)
        session.error = "EXIT_BEFORE_READY"
        session.state = "EXIT_VERIFIED" if session.exit_verified else "CLEANUP_INCOMPLETE"
        session._refresh()
        return session
    ready = session._side if mode == "side" else directory / "ready.txt"
    remaining = deadline_at - time.monotonic()
    if _poll_file(ready, time.monotonic() + max(0.0, remaining)):
        session.ready = True
        session.state = "WORKER_READY"
        session._refresh()
        return session
    session.error = "DEADLINE_BEFORE_READY"
    session.shutdown()
    return session


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
