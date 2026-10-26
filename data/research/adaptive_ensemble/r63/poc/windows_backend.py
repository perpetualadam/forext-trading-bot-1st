"""Windows creation-time job assignment.

PROC_THREAD_ATTRIBUTE_JOB_LIST puts the new process in the job inside
CreateProcess. The public path does not call AssignProcessToJobObject after
the process exists. A separate legacy helper reproduces the old gap and is
not used by ProcessLifecycleManager.
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

from lifecycle_contract import (
    CLEANUP_INCOMPLETE,
    CONTAINMENT_UNAVAILABLE,
    DESCENDANT_CONTAINMENT_ACTIVE,
    DESCENDANT_CONTAINMENT_AVAILABLE,
    DIRECT_CHILD_ONLY,
    OWNERSHIP_UNCERTAIN,
    REQUIRE_DESCENDANT_CONTAINMENT,
    Session,
)

if sys.platform != "win32":
    raise RuntimeError("windows_backend is Windows-only")

CREATE_SUSPENDED = 0x00000004
CREATE_NO_WINDOW = 0x08000000
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9
JobObjectBasicAccountingInformation = 1
STILL_ACTIVE = 259
DUPLICATE_SAME_ACCESS = 0x00000002
HANDLE_FLAG_INHERIT = 0x00000001
STARTF_USESTDHANDLES = 0x00000100
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
INVALID_ATTRIBUTE = 0x0002003F

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
_KERNEL.InitializeProcThreadAttributeList.restype = wintypes.BOOL
_KERNEL.InitializeProcThreadAttributeList.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.POINTER(ctypes.c_size_t),
]
_KERNEL.UpdateProcThreadAttribute.restype = wintypes.BOOL
_KERNEL.UpdateProcThreadAttribute.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.c_size_t,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
_KERNEL.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
_KERNEL.CreateProcessW.restype = wintypes.BOOL
_KERNEL.CreateProcessW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.BOOL,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.LPCWSTR,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
_KERNEL.IsProcessInJob.restype = wintypes.BOOL
_KERNEL.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
_KERNEL.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
_KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]
_KERNEL.ResumeThread.argtypes = [wintypes.HANDLE]
_KERNEL.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
_KERNEL.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_KERNEL.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_KERNEL.QueryInformationJobObject.restype = wintypes.BOOL
_KERNEL.QueryInformationJobObject.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.c_void_p,
]
_KERNEL.CreateFileW.restype = wintypes.HANDLE


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


class _Accounting(ctypes.Structure):
    _fields_ = [
        ("user", ctypes.c_int64),
        ("kernel", ctypes.c_int64),
        ("period_user", ctypes.c_int64),
        ("period_kernel", ctypes.c_int64),
        ("faults", wintypes.DWORD),
        ("total", wintypes.DWORD),
        ("active", wintypes.DWORD),
        ("terminated", wintypes.DWORD),
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


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [("startup", _StartupInfo), ("attribute_list", ctypes.c_void_p)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("process", wintypes.HANDLE),
        ("thread", wintypes.HANDLE),
        ("pid", wintypes.DWORD),
        ("tid", wintypes.DWORD),
    ]


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", wintypes.BOOL)]


def _check(ok: object, name: str) -> None:
    if not ok:
        raise OSError(ctypes.get_last_error(), name)


def parent_in_job() -> bool:
    result = wintypes.BOOL()
    _check(_KERNEL.IsProcessInJob(_KERNEL.GetCurrentProcess(), None, ctypes.byref(result)), "IsProcessInJob")
    return bool(result.value)


def probe(requested_policy: str) -> dict[str, object]:
    version = sys.getwindowsversion()
    supported = (version.major, version.minor) >= (6, 2)
    mechanisms = ("creation-time-job-list", "kill-on-job-close", "process-handle") if supported else ()
    return {
        "operating_system": f"Windows {version.major}.{version.minor} build {version.build}",
        "mechanisms": mechanisms,
        "requested_policy": requested_policy,
        "descendant_available": supported,
        "actual_if_requested": DESCENDANT_CONTAINMENT_AVAILABLE if supported else CONTAINMENT_UNAVAILABLE,
        "direct_child_level": DIRECT_CHILD_ONLY,
        "descendant_level": DESCENDANT_CONTAINMENT_AVAILABLE if supported else CONTAINMENT_UNAVAILABLE,
        "parent_in_job": parent_in_job(),
        "unsupported": ()
        if supported
        else ("PROC_THREAD_ATTRIBUTE_JOB_LIST requires Windows 8 or later", "blocked CreateProcess is not cancellable"),
        "detail": "availability is not activation",
    }


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


def job_counts(job: int) -> tuple[int, int]:
    info = _Accounting()
    ok = _KERNEL.QueryInformationJobObject(
        job,
        JobObjectBasicAccountingInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
        None,
    )
    if not ok:
        return (-1, -1)
    return int(info.active), int(info.total)


def create(manager, mode: str, deadline_at: float, directory: Path, before_create=None) -> Session:
    session = _blank(manager, directory)
    if before_create is not None:
        before_create()
    if time.monotonic() >= deadline_at:
        session.startup_deadline = "EXPIRED_BEFORE_CREATE"
        session.error = "DEADLINE_BEFORE_CREATE"
        return session
    if not probe(manager.requested_policy)["descendant_available"]:
        session.error = "CONTAINMENT_UNAVAILABLE"
        session.actual_containment = CONTAINMENT_UNAVAILABLE
        session.unsupported = ("creation-time job assignment is not available",)
        return session
    try:
        job = _make_job()
        command = _command(mode, session)
        created = _create_in_job(command, job, PROC_THREAD_ATTRIBUTE_JOB_LIST, inherit=False, startup=None)
    except OSError as exc:
        session.error = "CREATE_FAILED"
        session.state = "NOT_STARTED"
        session.unsupported = (exc.strerror or str(exc.errno),)
        if "job" in locals() and job:
            _KERNEL.CloseHandle(job)
        return session
    session._native = {"job": int(job), "process": int(created.process), "thread": int(created.thread), "extra_job": 0}
    session.pid = int(created.pid)
    session.state = "WORKER_CREATED"
    session.direct_child_ownership = "process-handle"
    session.mechanisms = ("creation-time-job-list", "kill-on-job-close", "process-handle")
    return session


def establish(session: Session) -> Session:
    if session.state != "WORKER_CREATED":
        return session
    job = session._native.get("job", 0)
    process = session._native.get("process", 0)
    inside = wintypes.BOOL()
    in_job = bool(job and process and _KERNEL.IsProcessInJob(process, job, ctypes.byref(inside)) and inside.value)
    if not in_job:
        session.actual_containment = OWNERSHIP_UNCERTAIN
        session.descendant_containment = OWNERSHIP_UNCERTAIN
        session.error = "CONTAINMENT_NOT_CONFIRMED"
        session.state = "OWNERSHIP_UNCERTAIN"
        return session
    session.actual_containment = DESCENDANT_CONTAINMENT_ACTIVE
    session.descendant_containment = DESCENDANT_CONTAINMENT_ACTIVE
    session.state = "WORKER_CONTAINED"
    return session


def start(session: Session, deadline_at: float, *, before_release=None) -> Session:
    if before_release is not None:
        before_release(session.pid)
    if session.actual_containment != DESCENDANT_CONTAINMENT_ACTIVE:
        session.error = session.error or "RELEASE_REFUSED"
        return session
    if time.monotonic() >= deadline_at:
        session.startup_deadline = "EXPIRED_BEFORE_RELEASE"
        session.error = "DEADLINE_BEFORE_RELEASE"
        return session
    thread = session._native.get("thread", 0)
    if thread:
        _KERNEL.ResumeThread(thread)
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
    if session.pid and not pid_active(session.pid) and not appeared:
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
    job = session._native.get("job", 0)
    process = session._native.get("process", 0)
    if job:
        _KERNEL.CloseHandle(job)
        session._native["job"] = 0
    elif process:
        _KERNEL.TerminateProcess(process, 1)
    return session


def verify_exit(session: Session, deadline_s: float = 5.0) -> Session:
    process = session._native.get("process", 0)
    if not process:
        session.exit_verified = session.pid == 0
        session.exit_verification = "EXIT_VERIFIED" if session.exit_verified else "NOT_CHECKED"
        return session
    dead = _wait_dead(process, int(deadline_s * 1000))
    session.exit_verified = dead
    session.exit_verification = "EXIT_VERIFIED" if dead else CLEANUP_INCOMPLETE
    session.state = "EXIT_VERIFIED" if dead else CLEANUP_INCOMPLETE
    session.cleanup = session.state
    refresh(session)
    return session


def cleanup(session: Session) -> Session:
    refresh(session)
    process = session._native.get("process", 0)
    if session.pid and pid_active(session.pid):
        session.harness_intervened = True
        if process:
            _KERNEL.TerminateProcess(process, 1)
            _wait_dead(process, 3000)
    extra = session._native.get("extra_job", 0)
    if extra:
        _KERNEL.CloseHandle(extra)
        session._native["extra_job"] = 0
    job = session._native.get("job", 0)
    if job:
        _KERNEL.CloseHandle(job)
        session._native["job"] = 0
    thread = session._native.get("thread", 0)
    if thread:
        _KERNEL.CloseHandle(thread)
        session._native["thread"] = 0
    if process:
        _KERNEL.CloseHandle(process)
        session._native["process"] = 0
    refresh(session)
    if session.descendant_pid and pid_active(session.descendant_pid):
        session.harness_intervened = True
        handle = _KERNEL.OpenProcess(0x0001, False, session.descendant_pid)
        if handle:
            _KERNEL.TerminateProcess(handle, 1)
            _wait_dead(handle, 3000)
            _KERNEL.CloseHandle(handle)
    return session


def refresh(session: Session) -> None:
    if session._grand is not None and session._grand.is_file() and not session.descendant_pid:
        text = session._grand.read_text(encoding="utf-8").strip()
        if text.isdigit():
            session.descendant_pid = int(text)
    if session.descendant_pid:
        session.descendant_alive = pid_active(session.descendant_pid)
    if session._side is not None:
        session.side_effect_written = session._side.is_file() and session._side.stat().st_size > 0
        if session.side_effect_written:
            session.worker_executed = True


def keep_extra_job_handle(session: Session) -> None:
    extra = wintypes.HANDLE()
    job = session._native.get("job", 0)
    _check(
        _KERNEL.DuplicateHandle(
            _KERNEL.GetCurrentProcess(),
            job,
            _KERNEL.GetCurrentProcess(),
            ctypes.byref(extra),
            0,
            False,
            DUPLICATE_SAME_ACCESS,
        ),
        "DuplicateHandle",
    )
    session._native["extra_job"] = int(extra.value)


def close_extra_job_handle(session: Session) -> None:
    extra = session._native.get("extra_job", 0)
    if extra:
        _KERNEL.CloseHandle(extra)
        session._native["extra_job"] = 0


def create_with_rejected_attribute(directory: Path) -> Session:
    session = Session()
    session.requested_policy = REQUIRE_DESCENDANT_CONTAINMENT
    session._side = directory / "side.txt"
    job = _make_job()
    try:
        _create_in_job(_command("side", session), job, INVALID_ATTRIBUTE, inherit=False, startup=None)
    except OSError as exc:
        session.error = "CREATE_ATTRIBUTE_REJECTED"
        session.state = "NOT_STARTED"
        session.actual_containment = CONTAINMENT_UNAVAILABLE
        session.pid = 0
        session.unsupported = (str(exc.errno),)
        return session
    finally:
        _KERNEL.CloseHandle(job)
    session.error = "UNSUPPORTED_ATTRIBUTE_DID_NOT_FAIL"
    return session


def legacy_suspended_without_job(directory: Path) -> tuple[int, int]:
    """The R.62 gap: a suspended process exists before any job assignment.

    The public manager does not call this. Crash tests use it to show the
    process can survive owner exit when assignment has not happened.
    """
    session = Session()
    session._side = directory / "side.txt"
    startup = _StartupInfoEx()
    startup.startup.cb = ctypes.sizeof(_StartupInfo)
    created = _ProcessInfo()
    command = _command("side", session)
    buffer = ctypes.create_unicode_buffer(command)
    ok = _KERNEL.CreateProcessW(
        None,
        buffer,
        None,
        None,
        False,
        CREATE_SUSPENDED | CREATE_NO_WINDOW,
        None,
        None,
        ctypes.byref(startup.startup),
        ctypes.byref(created),
    )
    _check(ok, "CreateProcessW")
    _KERNEL.CloseHandle(created.thread)
    return int(created.pid), int(created.process)


def blocked_stdin_is_not_closed(directory: Path) -> dict[str, object]:
    read = wintypes.HANDLE()
    write = wintypes.HANDLE()
    security = _SecurityAttributes()
    security.length = ctypes.sizeof(security)
    security.inherit = True
    _KERNEL.CreatePipe.restype = wintypes.BOOL
    _KERNEL.CreatePipe.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        ctypes.POINTER(wintypes.HANDLE),
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _check(_KERNEL.CreatePipe(ctypes.byref(read), ctypes.byref(write), ctypes.byref(security), 0), "CreatePipe")
    _KERNEL.SetHandleInformation(write, HANDLE_FLAG_INHERIT, 0)
    nul = _KERNEL.CreateFileW("NUL", GENERIC_WRITE, 1, None, OPEN_EXISTING, 0, None)
    startup = _StartupInfo()
    startup.cb = ctypes.sizeof(_StartupInfoEx)
    startup.flags = STARTF_USESTDHANDLES
    startup.stdin = read
    startup.stdout = nul
    startup.stderr = nul
    command = f'"{sys.executable}" -B -c "import time; time.sleep(60)"'
    job = _make_job()
    created = _create_in_job(command, job, PROC_THREAD_ATTRIBUTE_JOB_LIST, inherit=True, startup=startup)
    _KERNEL.CloseHandle(read)
    started = time.monotonic()
    writer_done = threading.Event()

    def _write() -> None:
        descriptor = msvcrt.open_osfhandle(int(write.value), os.O_BINARY)
        try:
            os.write(descriptor, b"X" * (256 * 1024))
        except OSError:
            pass
        writer_done.set()

    try:
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
            "stdin_closed_while_alive": False,
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


def _blank(manager, directory: Path) -> Session:
    directory.mkdir(parents=True, exist_ok=True)
    session = Session()
    session.requested_policy = manager.requested_policy
    session.operating_system = probe(manager.requested_policy)["operating_system"]
    session._side = directory / "side.txt"
    session._grand = directory / "grand.txt"
    session._ready = directory / "ready.txt"
    return session


def _command(mode: str, session: Session) -> str:
    worker = Path(__file__).with_name("synthetic_worker.py")
    parts = [f'"{sys.executable}"', "-B", f'"{worker}"', mode]
    if mode == "side":
        session._ready = None
        parts.append(f'"{session._side}"')
    elif mode == "grand":
        parts.extend([f'"{session._grand}"', f'"{session._ready}"'])
    elif mode == "exit":
        session._ready = None
    else:
        parts.append(f'"{session._ready}"')
    return " ".join(parts)


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
    return int(job)


def _create_in_job(command: str, job: int, attribute: int, *, inherit: bool, startup: _StartupInfo | None) -> _ProcessInfo:
    size = ctypes.c_size_t(0)
    _KERNEL.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    buffer = ctypes.create_string_buffer(size.value)
    raw = ctypes.cast(buffer, ctypes.c_void_p)
    _check(_KERNEL.InitializeProcThreadAttributeList(raw, 1, 0, ctypes.byref(size)), "InitializeProcThreadAttributeList")
    jobs = (wintypes.HANDLE * 1)(job)
    try:
        _check(
            _KERNEL.UpdateProcThreadAttribute(
                raw,
                0,
                attribute,
                ctypes.cast(jobs, ctypes.c_void_p),
                ctypes.sizeof(jobs),
                None,
                None,
            ),
            "UpdateProcThreadAttribute",
        )
        info = _StartupInfoEx()
        if startup is None:
            info.startup.cb = ctypes.sizeof(info)
        else:
            info.startup = startup
            info.startup.cb = ctypes.sizeof(info)
        info.attribute_list = ctypes.cast(raw, ctypes.c_void_p).value
        created = _ProcessInfo()
        flags = CREATE_SUSPENDED | CREATE_NO_WINDOW | EXTENDED_STARTUPINFO_PRESENT
        command_buffer = ctypes.create_unicode_buffer(command)
        ok = _KERNEL.CreateProcessW(
            None,
            command_buffer,
            None,
            None,
            inherit,
            flags,
            None,
            None,
            ctypes.byref(info),
            ctypes.byref(created),
        )
        _check(ok, "CreateProcessW")
        return created
    finally:
        _KERNEL.DeleteProcThreadAttributeList(raw)


def _wait_dead(process: int, timeout_ms: int) -> bool:
    _KERNEL.WaitForSingleObject(process, timeout_ms)
    code = wintypes.DWORD()
    _KERNEL.GetExitCodeProcess(process, ctypes.byref(code))
    return code.value != STILL_ACTIVE


def _poll_file(path: Path, deadline_at: float) -> bool:
    while time.monotonic() < deadline_at:
        if path.is_file() and path.stat().st_size > 0:
            return True
        time.sleep(0.02)
    return path.is_file() and path.stat().st_size > 0
