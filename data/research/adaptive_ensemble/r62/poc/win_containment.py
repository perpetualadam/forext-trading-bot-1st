"""Windows job ownership for one synthetic worker.

The process is created suspended, assigned to a job, and resumed only after
assignment. Closing the last job handle is the termination request. Exit is
taken from the process handle, not from the close call.
"""

from __future__ import annotations

import ctypes
import msvcrt
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

CREATE_SUSPENDED = 0x00000004
CREATE_NO_WINDOW = 0x08000000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9
STILL_ACTIVE = 259
DUPLICATE_SAME_ACCESS = 0x00000002
HANDLE_FLAG_INHERIT = 0x00000001
STARTF_USESTDHANDLES = 0x00000100
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3

_KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
_KERNEL.GetCurrentProcess.restype = wintypes.HANDLE
_KERNEL.CreateJobObjectW.restype = wintypes.HANDLE
_KERNEL.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
_KERNEL.OpenProcess.restype = wintypes.HANDLE
_KERNEL.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_KERNEL.DuplicateHandle.restype = wintypes.BOOL
_KERNEL.DuplicateHandle.argtypes = [
    wintypes.HANDLE,
    wintypes.HANDLE,
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.HANDLE),
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.DWORD,
]
_KERNEL.CreatePipe.restype = wintypes.BOOL
_KERNEL.CreatePipe.argtypes = [
    ctypes.POINTER(wintypes.HANDLE),
    ctypes.POINTER(wintypes.HANDLE),
    ctypes.c_void_p,
    wintypes.DWORD,
]


class _BasicLimit(ctypes.Structure):
    _fields_ = [
        ("per_process", ctypes.c_int64),
        ("per_job", ctypes.c_int64),
        ("limit_flags", wintypes.DWORD),
        ("min_ws", ctypes.c_size_t),
        ("max_ws", ctypes.c_size_t),
        ("active_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [("n", ctypes.c_uint64)] * 6


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicLimit),
        ("io", _IoCounters),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process", ctypes.c_size_t),
        ("peak_job", ctypes.c_size_t),
    ]


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("reserved", wintypes.LPWSTR),
        ("desktop", wintypes.LPWSTR),
        ("title", wintypes.LPWSTR),
        ("x", wintypes.DWORD),
        ("y", wintypes.DWORD),
        ("x_size", wintypes.DWORD),
        ("y_size", wintypes.DWORD),
        ("x_chars", wintypes.DWORD),
        ("y_chars", wintypes.DWORD),
        ("fill", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("show", wintypes.WORD),
        ("reserved2_length", wintypes.WORD),
        ("reserved2", ctypes.c_void_p),
        ("stdin", wintypes.HANDLE),
        ("stdout", wintypes.HANDLE),
        ("stderr", wintypes.HANDLE),
    ]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("process", wintypes.HANDLE),
        ("thread", wintypes.HANDLE),
        ("pid", wintypes.DWORD),
        ("tid", wintypes.DWORD),
    ]


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("descriptor", ctypes.c_void_p),
        ("inherit", wintypes.BOOL),
    ]


def _check(ok: object, name: str) -> None:
    if not ok:
        code = ctypes.get_last_error()
        raise OSError(code, name)


def pid_active(pid: int) -> bool:
    if pid <= 0:
        return False
    handle = _KERNEL.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    code = wintypes.DWORD()
    _KERNEL.GetExitCodeProcess(handle, ctypes.byref(code))
    _KERNEL.CloseHandle(handle)
    return code.value == STILL_ACTIVE


def _wait_dead(process: int, timeout_ms: int) -> bool:
    _KERNEL.WaitForSingleObject(process, timeout_ms)
    code = wintypes.DWORD()
    _KERNEL.GetExitCodeProcess(process, ctypes.byref(code))
    return code.value != STILL_ACTIVE


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
        self.stdin_closed_while_alive = False
        self._job = 0
        self._process = 0
        self._thread = 0
        self._extra_job = 0
        self._side: Path | None = None
        self._grand: Path | None = None

    def shutdown(self, wait_s: float = 5.0) -> str:
        self.state = "SHUTDOWN_REQUESTED"
        if self._job:
            _KERNEL.CloseHandle(self._job)
            self._job = 0
            self.state = "TERMINATION_ATTEMPTED"
        elif self._process:
            _KERNEL.TerminateProcess(self._process, 1)
            self.state = "TERMINATION_ATTEMPTED"
        if self._process:
            dead = _wait_dead(self._process, int(wait_s * 1000))
            self.exit_verified = dead
            self.state = "EXIT_VERIFIED" if dead else "CLEANUP_INCOMPLETE"
        self._refresh_descendant()
        return self.state

    def close_extra_job_handle(self) -> None:
        if self._extra_job:
            _KERNEL.CloseHandle(self._extra_job)
            self._extra_job = 0

    def close(self) -> None:
        if self.pid and pid_active(self.pid):
            self.harness_intervened = True
            if self._process:
                _KERNEL.TerminateProcess(self._process, 1)
                _wait_dead(self._process, 3000)
        if self.descendant_pid and pid_active(self.descendant_pid):
            self.harness_intervened = True
            self.descendant_alive = True
            handle = _KERNEL.OpenProcess(0x0001, False, self.descendant_pid)
            if handle:
                _KERNEL.TerminateProcess(handle, 1)
                _KERNEL.CloseHandle(handle)
        self.close_extra_job_handle()
        for handle in (self._thread, self._process, self._job):
            if handle:
                _KERNEL.CloseHandle(handle)
        self._thread = 0
        self._process = 0
        self._job = 0
        self._refresh_descendant()

    def _refresh_descendant(self) -> None:
        if self._grand is not None and self._grand.is_file() and not self.descendant_pid:
            text = self._grand.read_text(encoding="utf-8").strip()
            if text.isdigit():
                self.descendant_pid = int(text)
        if self.descendant_pid:
            self.descendant_alive = pid_active(self.descendant_pid)
        if self._side is not None:
            self.side_effect_written = self._side.is_file()


def _command(mode: str, paths: list[Path]) -> str:
    worker = Path(__file__).with_name("synthetic_worker.py")
    parts = [f'"{sys.executable}"', "-B", f'"{worker}"', mode]
    parts.extend(f'"{path}"' for path in paths)
    return " ".join(parts)


def _create_suspended(command: str, startup: _StartupInfo | None = None, inherit: bool = False) -> _ProcessInfo:
    info = _ProcessInfo()
    buffer = ctypes.create_unicode_buffer(command)
    ok = _KERNEL.CreateProcessW(
        None,
        buffer,
        None,
        None,
        inherit,
        CREATE_SUSPENDED | CREATE_NO_WINDOW,
        None,
        None,
        ctypes.byref(startup) if startup is not None else ctypes.byref(_blank_startup()),
        ctypes.byref(info),
    )
    _check(ok, "CreateProcessW")
    return info


def _blank_startup() -> _StartupInfo:
    startup = _StartupInfo()
    startup.cb = ctypes.sizeof(startup)
    return startup


def _make_job() -> int:
    job = _KERNEL.CreateJobObjectW(None, None)
    _check(job, "CreateJobObjectW")
    limit = _ExtendedLimit()
    limit.basic.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = _KERNEL.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(limit),
        ctypes.sizeof(limit),
    )
    _check(ok, "SetInformationJobObject")
    _KERNEL.SetHandleInformation(job, HANDLE_FLAG_INHERIT, 0)
    return job


def _assign(job: int, process: int) -> None:
    _check(_KERNEL.AssignProcessToJobObject(job, process), "AssignProcessToJobObject")


def launch(
    mode: str,
    deadline_at: float,
    directory: Path,
    *,
    before_create=None,
    after_create=None,
    fail_job: bool = False,
    keep_extra_job_handle: bool = False,
) -> Session:
    session = Session()
    session._side = directory / "side.txt"
    session._grand = directory / "grand.txt"
    if before_create is not None:
        before_create()
    if time.monotonic() >= deadline_at:
        session.error = "DEADLINE_BEFORE_CREATE"
        return session
    if mode == "side":
        command = _command(mode, [session._side])
    elif mode == "grand":
        command = _command(mode, [session._grand, directory / "ready.txt"])
    elif mode == "exit":
        command = _command(mode, [])
    else:
        command = _command(mode, [directory / "ready.txt"])
    try:
        created = _create_suspended(command)
    except OSError:
        session.error = "CREATE_FAILED"
        session.state = "NOT_STARTED"
        return session
    session._process = created.process
    session._thread = created.thread
    session.pid = int(created.pid)
    session.state = "WORKER_CREATED"
    if after_create is not None:
        after_create(session.pid)
    if time.monotonic() >= deadline_at:
        session.error = "DEADLINE_BEFORE_RESUME"
        dead = _wait_after_terminate(session)
        session.exit_verified = dead
        session.state = "EXIT_VERIFIED" if dead else "CLEANUP_INCOMPLETE"
        session._refresh_descendant()
        return session
    try:
        if fail_job:
            raise OSError(0, "CONTAINMENT_FAILED")
        session._job = _make_job()
        _assign(session._job, session._process)
    except OSError:
        session.error = "CONTAINMENT_FAILED"
        session.contained = False
        dead = _wait_after_terminate(session)
        session.exit_verified = dead
        session.state = "EXIT_VERIFIED" if dead else "CLEANUP_INCOMPLETE"
        session._refresh_descendant()
        return session
    session.contained = True
    session.state = "WORKER_CONTAINED"
    if keep_extra_job_handle:
        extra = wintypes.HANDLE()
        _check(
            _KERNEL.DuplicateHandle(
                _KERNEL.GetCurrentProcess(),
                session._job,
                _KERNEL.GetCurrentProcess(),
                ctypes.byref(extra),
                0,
                False,
                DUPLICATE_SAME_ACCESS,
            ),
            "DuplicateHandle",
        )
        session._extra_job = extra.value
    if time.monotonic() >= deadline_at:
        session.error = "DEADLINE_BEFORE_RESUME"
        return session.shutdown()
    _KERNEL.ResumeThread(session._thread)
    ready_path = directory / "ready.txt"
    if mode == "exit":
        dead = _wait_dead(session._process, 3000)
        session.exit_verified = dead
        session.ready = False
        session.error = "EXIT_BEFORE_READY"
        session.state = "EXIT_VERIFIED" if dead else "CLEANUP_INCOMPLETE"
        session._refresh_descendant()
        return session
    remaining = deadline_at - time.monotonic()
    appeared = _poll_file(ready_path if mode != "side" else session._side, time.monotonic() + max(0.0, remaining))
    session._refresh_descendant()
    if appeared:
        session.ready = True
        session.state = "WORKER_READY"
        return session
    session.error = "DEADLINE_BEFORE_READY"
    return session.shutdown()


def _wait_after_terminate(session: Session) -> bool:
    session.state = "TERMINATION_ATTEMPTED"
    if session._process:
        _KERNEL.TerminateProcess(session._process, 1)
        return _wait_dead(session._process, 5000)
    return False


def _poll_file(path: Path, deadline_at: float) -> bool:
    while time.monotonic() < deadline_at:
        if path.is_file() and path.stat().st_size > 0:
            return True
        time.sleep(0.02)
    return path.is_file() and path.stat().st_size > 0


def blocked_stdin_is_not_closed(directory: Path) -> dict[str, object]:
    """A full stdin write must be released by job close, not by close() on the owner thread."""
    read = wintypes.HANDLE()
    write = wintypes.HANDLE()
    security = _SecurityAttributes()
    security.length = ctypes.sizeof(security)
    security.inherit = True
    _check(
        _KERNEL.CreatePipe(ctypes.byref(read), ctypes.byref(write), ctypes.byref(security), 0),
        "CreatePipe",
    )
    _KERNEL.SetHandleInformation(write, HANDLE_FLAG_INHERIT, 0)
    nul = _KERNEL.CreateFileW("NUL", GENERIC_WRITE, 1, None, OPEN_EXISTING, 0, None)
    startup = _StartupInfo()
    startup.cb = ctypes.sizeof(startup)
    startup.flags = STARTF_USESTDHANDLES
    startup.stdin = read
    startup.stdout = nul
    startup.stderr = nul
    command = f'"{sys.executable}" -B -c "import time; time.sleep(60)"'
    job = _make_job()
    created = _create_suspended(command, startup, inherit=True)
    _KERNEL.CloseHandle(read)
    started = time.monotonic()
    writer_done = threading.Event()
    closed_flag = {"closed": False}

    def _write() -> None:
        descriptor = msvcrt.open_osfhandle(int(write.value), os.O_BINARY)
        try:
            os.write(descriptor, b"X" * (256 * 1024))
        except OSError:
            pass
        writer_done.set()

    try:
        _assign(job, created.process)
        _KERNEL.ResumeThread(created.thread)
        thread = threading.Thread(target=_write, daemon=True)
        thread.start()
        time.sleep(0.2)
        _KERNEL.CloseHandle(job)
        job = 0
        thread.join(3)
        dead = _wait_dead(created.process, 3000)
        return {
            "writer_finished": writer_done.is_set(),
            "stdin_closed_while_alive": closed_flag["closed"],
            "exit_verified": dead,
            "elapsed": time.monotonic() - started,
            "pid_active": pid_active(int(created.pid)),
        }
    finally:
        if job:
            _KERNEL.CloseHandle(job)
        if created.process and not writer_done.is_set():
            _KERNEL.TerminateProcess(created.process, 1)
        if created.thread:
            _KERNEL.CloseHandle(created.thread)
        if created.process:
            _KERNEL.CloseHandle(created.process)
        if nul:
            _KERNEL.CloseHandle(nul)


def launch_pipe_check(directory: Path) -> dict[str, object]:
    directory.mkdir(parents=True, exist_ok=True)
    return blocked_stdin_is_not_closed(directory)
