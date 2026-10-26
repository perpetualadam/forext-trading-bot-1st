"""OS-backed recovery-owner lock. A caller statement is not liveness evidence.

The lock is an exclusive, non-blocking file lock held for the life of an
in-progress recovery claim. Process exit releases it. A PID or a timestamp
does not. This module does not contact a broker and does not grant trading.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path


class RecoveryOwnerLock:
    """Exclusive lock on the journal's recovery sidecar. Not a trading permit."""

    def __init__(self, journal_path: str) -> None:
        self.path = lock_path_for(journal_path)
        self._handle = None

    def try_acquire(self) -> bool:
        """Return true only when this process becomes the sole lock holder."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() < 1:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            handle.close()


def lock_path_for(journal_path: str) -> Path:
    target = Path(journal_path).resolve()
    return target.with_name(target.name + ".recovery.lock")


def lock_identity(journal_path: str) -> str:
    return hashlib.sha256(str(lock_path_for(journal_path)).encode("utf-8")).hexdigest()


def host_boot_id() -> str:
    """Boot identity when the OS provides one. A constant means reboot is not detected."""
    linux_boot = Path("/proc/sys/kernel/random/boot_id")
    if linux_boot.exists():
        try:
            value = linux_boot.read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
        if value:
            return "linux:" + value
    if os.name == "nt":
        return "windows:boot-id-unavailable"
    return "boot-id-unavailable"


def current_process_start() -> str | None:
    described = _process_start(os.getpid())
    if described in {None, "unknown"}:
        return None
    return described


def owner_process_status(pid: int | None, recorded_start: str | None) -> str:
    """Classify a recorded owner. ``unrecorded`` means the row has no PID."""
    if pid is None:
        return "unrecorded"
    described = _process_start(int(pid))
    if described is None:
        return "dead"
    if described == "unknown":
        return "unknown"
    if recorded_start and described != recorded_start:
        return "pid_reused"
    if recorded_start and described == recorded_start:
        return "alive"
    return "unknown"


def _process_start(pid: int) -> str | None:
    if os.name == "nt":
        return _windows_start(pid)
    return _linux_start(pid)


def _linux_start(pid: int) -> str | None:
    stat_path = Path(f"/proc/{pid}/stat")
    if not stat_path.exists():
        return None
    try:
        text = stat_path.read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    end = text.rfind(")")
    if end < 0:
        return "unknown"
    fields = text[end + 2 :].split()
    if len(fields) < 20:
        return "unknown"
    if fields[0] == "Z":
        return None
    return fields[19]


def _windows_start(pid: int) -> str | None:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class _FileTime(ctypes.Structure):
        _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]

    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        error = ctypes.get_last_error()
        if error in {5, 87}:
            return "unknown" if error == 5 else None
        return None
    created = _FileTime()
    exited = _FileTime()
    kernel_time = _FileTime()
    user_time = _FileTime()
    ok = kernel.GetProcessTimes(
        handle,
        ctypes.byref(created),
        ctypes.byref(exited),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    )
    kernel.CloseHandle(handle)
    if not ok:
        return "unknown"
    if exited.high or exited.low:
        return None
    return f"{created.high}:{created.low}"
