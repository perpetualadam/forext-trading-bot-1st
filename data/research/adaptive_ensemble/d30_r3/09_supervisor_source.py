"""Job Object supervisor for synthetic workers. No network APIs."""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

ALLOWED_HOSTS = frozenset({"registry-1.docker.io", "auth.docker.io"})
REPOSITORY = "library/python"
WORKER_MODES = frozenset({
    "complete",
    "nonzero",
    "exception",
    "block",
    "ignore_stop",
    "malformed",
    "stdout_flood",
    "late",
    "secrets",
    "secret_block",
    "spawn_complete",
    "spawn_block",
    "spawn_exit_first",
})
SPAWN_MODES = frozenset({"spawn_complete", "spawn_block", "spawn_exit_first"})
CONTAINMENT_SEQUENCE = ("create_suspended", "assign_job", "verify_membership", "resume")
OUTPUT_CAP = 8192
STILL_ACTIVE = 259
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
CREATE_SUSPENDED = 0x00000004
CREATE_NO_WINDOW = 0x08000000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
STARTF_USESTDHANDLES = 0x00000100
HANDLE_FLAG_INHERIT = 0x00000001
JOB_OBJECT_LIMIT_WORKINGSET = 0x00000001
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
INVALID_HANDLE = ctypes.c_void_p(-1).value
KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)


class Reject(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class StageBlocked(Exception):
    def __init__(self, classification: str, detail: str) -> None:
        self.classification = classification
        self.detail = detail
        super().__init__(classification)


class FILETIME(ctypes.Structure):
    _fields_ = (("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD))


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = (
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", wintypes.BOOL),
    )


class STARTUPINFOW(ctypes.Structure):
    _fields_ = (
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    )


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = (("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p))


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    )


class IO_COUNTERS(ctypes.Structure):
    _fields_ = (
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    )


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    )


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    )


class JOBOBJECT_BASIC_PROCESS_ID_LIST(ctypes.Structure):
    _fields_ = (
        ("NumberOfAssignedProcesses", wintypes.DWORD),
        ("NumberOfProcessIdsInList", wintypes.DWORD),
        ("ProcessIdList", ctypes.c_size_t * 8),
    )


def _bind() -> None:
    k = KERNEL
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k.SetInformationJobObject.restype = wintypes.BOOL
    k.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    k.QueryInformationJobObject.restype = wintypes.BOOL
    k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k.AssignProcessToJobObject.restype = wintypes.BOOL
    k.TerminateJobObject.argtypes = [wintypes.HANDLE, ctypes.c_uint]
    k.TerminateJobObject.restype = wintypes.BOOL
    k.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    k.IsProcessInJob.restype = wintypes.BOOL
    k.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL,
        wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(PROCESS_INFORMATION),
    ]
    k.CreateProcessW.restype = wintypes.BOOL
    k.ResumeThread.argtypes = [wintypes.HANDLE]
    k.ResumeThread.restype = wintypes.DWORD
    k.TerminateProcess.argtypes = [wintypes.HANDLE, ctypes.c_uint]
    k.TerminateProcess.restype = wintypes.BOOL
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.GetExitCodeProcess.restype = wintypes.BOOL
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
    k.GetProcessTimes.restype = wintypes.BOOL
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.GetCurrentProcess.argtypes = []
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k.QueryFullProcessImageNameW.restype = wintypes.BOOL
    k.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    k.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    k.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
    k.UpdateProcThreadAttribute.restype = wintypes.BOOL
    k.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    k.DeleteProcThreadAttributeList.restype = None
    k.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(SECURITY_ATTRIBUTES), wintypes.DWORD]
    k.CreatePipe.restype = wintypes.BOOL
    k.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    k.SetHandleInformation.restype = wintypes.BOOL
    k.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    k.ReadFile.restype = wintypes.BOOL
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.CreateFileW.restype = wintypes.HANDLE


_bind()


class Owned:
    def __init__(self, value: int, kind: str) -> None:
        self.value = int(value or 0)
        self.kind = kind
        self.closed = self.value == 0

    def close(self) -> None:
        if self.closed or self.value == 0:
            self.closed = True
            return
        KERNEL.CloseHandle(self.value)
        self.closed = True


def win_error(prefix: str) -> OSError:
    code = ctypes.get_last_error()
    return OSError(code, prefix)


def minimal_env() -> dict[str, str]:
    kept = {}
    for key in ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC", "TEMP", "TMP"):
        value = os.environ.get(key)
        if value:
            kept[key] = value
    kept["PYTHONUTF8"] = "1"
    kept["PYTHONDONTWRITEBYTECODE"] = "1"
    kept["PYTHONNOUSERSITE"] = "1"
    return kept


def env_block(env: dict[str, str]) -> ctypes.Array[ctypes.c_wchar]:
    parts = [f"{key}={env[key]}" for key in sorted(env)]
    return ctypes.create_unicode_buffer("\0".join(parts) + "\0\0")


def quote_arg(text: str) -> str:
    if any(character in text for character in " \t\""):
        return '"' + text.replace('"', "") + '"'
    return text


class Budget:
    def __init__(self) -> None:
        self.total = 0
        self.head = 0
        self.token = 0
        self.body = 0
        self.redirects_followed = 0
        self.retries = 0
        self.redirects_recorded = 0

    def reserve(self, host: str, method: str, repository: str, digest: str | None, category: str, allowlist: set[str]) -> int:
        if category in {"storage", "registry_get", "layer_body", "retry"}:
            raise Reject(category)
        if host not in ALLOWED_HOSTS:
            raise Reject("host")
        if repository != REPOSITORY:
            raise Reject("repository")
        if method not in {"HEAD", "GET"}:
            raise Reject("method")
        if host == "registry-1.docker.io" and method != "HEAD":
            raise Reject("registry_get")
        if category == "token" and (host != "auth.docker.io" or method != "GET"):
            raise Reject("token method")
        if digest is not None and digest not in allowlist:
            raise Reject("digest")
        if self.total >= 20:
            raise Reject("total")
        if category == "head" and self.head >= 16:
            raise Reject("head")
        if category == "token" and self.token >= 1:
            raise Reject("token")
        self.total += 1
        if category == "head":
            self.head += 1
        if category == "token":
            self.token += 1
        return self.total

    def add_body(self, count: int, limit: int = 1048576) -> None:
        if count < 0 or self.body + count > limit:
            raise Reject("body")
        self.body += count

    def record_redirect(self) -> None:
        self.redirects_recorded += 1

    def apply_worker_message(self, message: dict) -> None:
        return None

    def apply_descendant_message(self, message: dict) -> None:
        return None

    def snapshot(self) -> dict[str, int]:
        return {
            "total": self.total,
            "head": self.head,
            "token": self.token,
            "body": self.body,
            "redirects_followed": self.redirects_followed,
            "retries": self.retries,
            "redirects_recorded": self.redirects_recorded,
        }


def cleanup_status(duration: float, allowance: float, exits_confirmed: bool) -> str:
    if not exits_confirmed or duration > allowance:
        return "BLOCKED"
    return "complete"


def lock_result(row: dict, value: str) -> None:
    if "result" in row and row["result"] != value:
        raise Reject("reclassify")
    row["result"] = value


def layout_report() -> dict[str, int]:
    pointer = ctypes.sizeof(ctypes.c_void_p)
    basic = ctypes.sizeof(JOBOBJECT_BASIC_LIMIT_INFORMATION)
    extended = ctypes.sizeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION)
    expected_basic = 64 if pointer == 8 else 48
    expected_extended = 144 if pointer == 8 else 112
    return {
        "pointer_bytes": pointer,
        "basic_limit_bytes": basic,
        "extended_limit_bytes": extended,
        "expected_basic_bytes": expected_basic,
        "expected_extended_bytes": expected_extended,
        "layouts_match": basic == expected_basic and extended == expected_extended,
    }


def api_review() -> dict[str, object]:
    layouts = layout_report()
    return {
        "dll": "kernel32",
        "loader": "ctypes.WinDLL",
        "pointer_bytes": layouts["pointer_bytes"],
        "layouts": layouts,
        "constants": {
            "CREATE_SUSPENDED": CREATE_SUSPENDED,
            "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE": JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
            "JOB_OBJECT_LIMIT_ACTIVE_PROCESS": JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
            "JOB_OBJECT_LIMIT_BREAKAWAY_OK": JOB_OBJECT_LIMIT_BREAKAWAY_OK,
            "JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK": JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK,
            "PROC_THREAD_ATTRIBUTE_HANDLE_LIST": PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            "STILL_ACTIVE": STILL_ACTIVE,
        },
        "containment_sequence": list(CONTAINMENT_SEQUENCE),
        "inherited_worker_handles": ["NUL", "stdout-write", "stderr-write"],
        "inherited_descendant_handles": ["NUL"],
        "job_handle_inherited": False,
        "breakaway_flags_set": False,
    }


def current_process_in_job() -> bool:
    result = wintypes.BOOL()
    ok = KERNEL.IsProcessInJob(KERNEL.GetCurrentProcess(), None, ctypes.byref(result))
    if not ok:
        raise win_error("IsProcessInJob current")
    return bool(result.value)


def _set_limits(job: int, active_limit: int) -> None:
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
    info.BasicLimitInformation.ActiveProcessLimit = active_limit
    ok = KERNEL.SetInformationJobObject(job, 9, ctypes.cast(ctypes.byref(info), ctypes.c_void_p), ctypes.sizeof(info))
    if not ok:
        raise win_error("SetInformationJobObject")


def read_limits(job: int) -> tuple[int, int]:
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    ok = KERNEL.QueryInformationJobObject(job, 9, ctypes.cast(ctypes.byref(info), ctypes.c_void_p), ctypes.sizeof(info), None)
    if not ok:
        raise win_error("QueryInformationJobObject limits")
    return int(info.BasicLimitInformation.LimitFlags), int(info.BasicLimitInformation.ActiveProcessLimit)


def job_member_basename(job: int, pid: int) -> str:
    handle = KERNEL.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return "unopened"
    try:
        if not process_in_job(int(handle), job):
            return "not-in-job"
        buffer = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if not KERNEL.QueryFullProcessImageNameW(int(handle), 0, buffer, ctypes.byref(size)):
            return "unnamed"
        return Path(buffer.value).name
    finally:
        KERNEL.CloseHandle(handle)


def job_process_ids(job: int) -> tuple[list[int], int]:
    info = JOBOBJECT_BASIC_PROCESS_ID_LIST()
    info.NumberOfProcessIdsInList = 8
    ok = KERNEL.QueryInformationJobObject(job, 3, ctypes.cast(ctypes.byref(info), ctypes.c_void_p), ctypes.sizeof(info), None)
    if not ok:
        raise win_error("QueryInformationJobObject pids")
    count = int(info.NumberOfAssignedProcesses)
    listed = min(count, int(info.NumberOfProcessIdsInList), 8)
    return [int(info.ProcessIdList[index]) for index in range(listed)], count


def limits_are_contained(flags: int, active_limit: int) -> bool:
    kill_set = bool(flags & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
    active_set = bool(flags & JOB_OBJECT_LIMIT_ACTIVE_PROCESS)
    breakaway_clear = not (flags & (JOB_OBJECT_LIMIT_BREAKAWAY_OK | JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK))
    return kill_set and active_set and breakaway_clear and active_limit in {1, 2}


def probe_job() -> dict[str, object]:
    if os.name != "nt":
        raise StageBlocked("D30_R3_BLOCKED_CONTAINMENT_UNAVAILABLE", "not windows")
    layouts = layout_report()
    if not layouts["layouts_match"]:
        raise StageBlocked("D30_R3_BLOCKED_CONTAINMENT_UNAVAILABLE", "structure layout")
    supervisor_in_job = current_process_in_job()
    job = KERNEL.CreateJobObjectW(None, None)
    if not job:
        raise StageBlocked("D30_R3_BLOCKED_CONTAINMENT_UNAVAILABLE", f"CreateJobObjectW {ctypes.get_last_error()}")
    try:
        _set_limits(job, 1)
        flags, active = read_limits(job)
    finally:
        KERNEL.CloseHandle(job)
    return {
        "supervisor_in_job": supervisor_in_job,
        "limit_flags": flags,
        "active_process_limit": active,
        "limits_contained": limits_are_contained(flags, active),
        "layouts": layouts,
        "process_created": False,
    }


def process_times(handle: int) -> tuple[int, int]:
    created = FILETIME()
    exited = FILETIME()
    kernel = FILETIME()
    user = FILETIME()
    ok = KERNEL.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user))
    if not ok:
        raise win_error("GetProcessTimes")
    return int(created.dwLowDateTime), int(created.dwHighDateTime)


def creation_matches(handle: int, low: int, high: int) -> bool:
    return process_times(handle) == (int(low), int(high))


def process_in_job(process: int, job: int) -> bool:
    result = wintypes.BOOL()
    ok = KERNEL.IsProcessInJob(process, job, ctypes.byref(result))
    if not ok:
        raise win_error("IsProcessInJob")
    return bool(result.value)


def exit_code(handle: int) -> int | None:
    code = wintypes.DWORD()
    ok = KERNEL.GetExitCodeProcess(handle, ctypes.byref(code))
    if not ok:
        return None
    return int(code.value)


def still_alive(handle: int) -> bool:
    return exit_code(handle) == STILL_ACTIVE


def wait_handle(handle: int, seconds: float) -> bool:
    timeout_ms = max(0, int(seconds * 1000))
    result = KERNEL.WaitForSingleObject(handle, timeout_ms)
    return result == WAIT_OBJECT_0


def parse_identity(payload: object) -> tuple[int, int, int]:
    if not isinstance(payload, dict) or set(payload) != {"pid", "creation_low", "creation_high"}:
        raise Reject("identity fields")
    values = [payload["pid"], payload["creation_low"], payload["creation_high"]]
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in values):
        raise Reject("identity type")
    pid, low, high = values
    if pid <= 0 or low < 0 or high < 0:
        raise Reject("identity range")
    return pid, low, high


def accept_stdout(raw: bytes) -> str:
    if not raw.strip():
        return "empty"
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "rejected_malformed"
    if not isinstance(parsed, dict) or set(parsed) - {"kind", "status"}:
        return "rejected_unlisted_field"
    if parsed.get("kind") != "ok":
        return "rejected_kind"
    if parsed.get("status") not in {"complete", "sleep"}:
        return "rejected_status"
    return "accepted"


class Spawn:
    def __init__(self) -> None:
        self.process: Owned | None = None
        self.thread: Owned | None = None
        self.pid = 0
        self.tid = 0
        self.stdout_read: Owned | None = None
        self.stderr_read: Owned | None = None
        self.inherited: list[str] = []


def _nul() -> int:
    attributes = SECURITY_ATTRIBUTES()
    attributes.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
    attributes.bInheritHandle = 1
    handle = KERNEL.CreateFileW(
        "NUL",
        0x80000000 | 0x40000000,
        0x00000001 | 0x00000002,
        ctypes.cast(ctypes.byref(attributes), ctypes.c_void_p),
        3,
        0x80,
        None,
    )
    if not handle or int(handle) == INVALID_HANDLE:
        raise win_error("CreateFileW NUL")
    return int(handle)


def _pipe() -> tuple[int, int]:
    read = wintypes.HANDLE()
    write = wintypes.HANDLE()
    attributes = SECURITY_ATTRIBUTES()
    attributes.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
    attributes.bInheritHandle = 1
    ok = KERNEL.CreatePipe(ctypes.byref(read), ctypes.byref(write), ctypes.byref(attributes), 0)
    if not ok:
        raise win_error("CreatePipe")
    if not KERNEL.SetHandleInformation(read.value, HANDLE_FLAG_INHERIT, 0):
        raise win_error("SetHandleInformation")
    return int(read.value), int(write.value)


def _attribute_list(handles: list[int]) -> tuple[ctypes.Array[ctypes.c_char], ctypes.Array[ctypes.c_void_p]]:
    size = ctypes.c_size_t(0)
    KERNEL.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    buffer = ctypes.create_string_buffer(size.value)
    if not KERNEL.InitializeProcThreadAttributeList(ctypes.cast(buffer, ctypes.c_void_p), 1, 0, ctypes.byref(size)):
        raise win_error("InitializeProcThreadAttributeList")
    array = (wintypes.HANDLE * len(handles))(*handles)
    updated = KERNEL.UpdateProcThreadAttribute(
        ctypes.cast(buffer, ctypes.c_void_p),
        0,
        PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
        ctypes.cast(array, ctypes.c_void_p),
        ctypes.sizeof(array),
        None,
        None,
    )
    if not updated:
        KERNEL.DeleteProcThreadAttributeList(ctypes.cast(buffer, ctypes.c_void_p))
        raise win_error("UpdateProcThreadAttribute")
    return buffer, array


def spawn_suspended(argv: list[str], workdir: Path, env: dict[str, str], stdio: str) -> Spawn:
    if stdio not in {"pipes", "nul"}:
        raise Reject("stdio")
    if any(item == "shell" for item in argv):
        raise Reject("argv")
    spawned = Spawn()
    nul_handle = 0
    stdout_write = 0
    stderr_write = 0
    buffer = None
    array = None
    try:
        nul_handle = _nul()
        inherited = [nul_handle]
        names = ["NUL"]
        if stdio == "pipes":
            stdout_read, stdout_write = _pipe()
            stderr_read, stderr_write = _pipe()
            spawned.stdout_read = Owned(stdout_read, "stdout-read")
            spawned.stderr_read = Owned(stderr_read, "stderr-read")
            inherited.extend([stdout_write, stderr_write])
            names.extend(["stdout-write", "stderr-write"])
        buffer, array = _attribute_list(inherited)
        startup = STARTUPINFOEXW()
        startup.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput = nul_handle
        startup.StartupInfo.hStdOutput = stdout_write or nul_handle
        startup.StartupInfo.hStdError = stderr_write or nul_handle
        startup.lpAttributeList = ctypes.cast(buffer, ctypes.c_void_p).value
        command = ctypes.create_unicode_buffer(" ".join(quote_arg(item) for item in argv))
        environment = env_block(env)
        info = PROCESS_INFORMATION()
        flags = CREATE_SUSPENDED | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT
        created = KERNEL.CreateProcessW(
            argv[0],
            command,
            None,
            None,
            True,
            flags,
            ctypes.cast(environment, ctypes.c_void_p),
            str(workdir),
            ctypes.cast(ctypes.byref(startup), ctypes.c_void_p),
            ctypes.byref(info),
        )
        if not created:
            raise win_error("CreateProcessW")
        spawned.process = Owned(int(info.hProcess), "process")
        spawned.thread = Owned(int(info.hThread), "thread")
        spawned.pid = int(info.dwProcessId)
        spawned.tid = int(info.dwThreadId)
        spawned.inherited = names
        return spawned
    except Exception:
        if spawned.process is not None:
            KERNEL.TerminateProcess(spawned.process.value, 1)
            wait_handle(spawned.process.value, 2.0)
            spawned.process.close()
        if spawned.thread is not None:
            spawned.thread.close()
        if spawned.stdout_read is not None:
            spawned.stdout_read.close()
        if spawned.stderr_read is not None:
            spawned.stderr_read.close()
        raise
    finally:
        if buffer is not None:
            KERNEL.DeleteProcThreadAttributeList(ctypes.cast(buffer, ctypes.c_void_p))
        for extra in (nul_handle, stdout_write, stderr_write):
            if extra:
                KERNEL.CloseHandle(extra)
        del array


def _read_pipe(handle: int, sink: list[bytes], lock: threading.Lock, overflow: list[bool]) -> None:
    buffer = ctypes.create_string_buffer(4096)
    total = 0
    while total < OUTPUT_CAP:
        got = wintypes.DWORD()
        room = min(4096, OUTPUT_CAP - total)
        ok = KERNEL.ReadFile(handle, buffer, room, ctypes.byref(got), None)
        if not ok or got.value == 0:
            break
        chunk = buffer.raw[: int(got.value)]
        with lock:
            sink.append(chunk)
        total += len(chunk)
        if total >= OUTPUT_CAP:
            overflow[0] = True
            break


class Session:
    created_processes = 0

    def __init__(self, worker: Path, out_dir: Path, mode: str, operation_deadline: float, stage_deadline: float, stage_started: float, cleanup_allowance: float = 2.0, graceful: bool = False, close_without_terminate: bool = False) -> None:
        if mode not in WORKER_MODES:
            raise Reject("mode")
        if Session.created_processes >= 40:
            raise StageBlocked("D30_R3_BLOCKED_HARNESS_SAFETY", "process cap")
        self.worker = worker
        self.out_dir = out_dir
        self.mode = mode
        self.operation_deadline = operation_deadline
        self.stage_deadline = stage_deadline
        self.stage_started = stage_started
        self.cleanup_allowance = cleanup_allowance
        self.graceful = graceful
        self.close_without_terminate = close_without_terminate
        self.spawn = mode in SPAWN_MODES
        self.active_limit = 2 if self.spawn else 1
        self.job: Owned | None = None
        self.worker_process: Owned | None = None
        self.worker_thread: Owned | None = None
        self.descendant_process: Owned | None = None
        self.stdout_read: Owned | None = None
        self.stderr_read: Owned | None = None
        self.token = str(time.monotonic_ns())
        self.started = time.monotonic()
        self.operation_started = self.started
        self.deadline_at = self.started
        self.termination_at = self.started
        self.cleanup_started = self.started
        self.cleanup_finished = self.started
        self.worker_pid = 0
        self.worker_creation = (0, 0)
        self.descendant_pid = 0
        self.descendant_creation = (0, 0)
        self.worker_in_job = False
        self.descendant_in_job = False
        self.resume_previous_count: int | None = None
        self.descendant_resume_observed = False
        self.descendant_alive_after_worker = None
        self.descendant_in_job_after_worker = None
        self.limit_flags = 0
        self.job_pids: list[int] = []
        self.job_assigned_count = 0
        self.job_member_names: list[str] = []
        self.termination_method = "none"
        self.stop_reason = "completed"
        self.worker_exit: int | None = None
        self.descendant_exit: int | None = None
        self.worker_exit_confirmed = False
        self.descendant_exit_confirmed = False
        self.alive_after_graceful = False
        self.identity_guard_ok = False
        self.kill_on_close_sufficient: bool | None = None
        self.discarded_after_deadline = 0
        self.stdout_bytes = 0
        self.stderr_bytes = 0
        self.disposition = "empty"
        self.accepted = False
        self.saw_unlisted_marker = False
        self.handles_closed = False
        self.inherited: list[str] = []
        self.cleanup_blocked = False
        self.unresolved: list[dict[str, object]] = []
        self.attempts = 0
        self._chunks: list[bytes] = []
        self._err_chunks: list[bytes] = []
        self._lock = threading.Lock()
        self._overflow = [False]
        self._accepting = True
        self._frozen = 0
        self._readers: list[threading.Thread] = []
        self._shutdown_done = False

    def stage_elapsed(self) -> float:
        return time.monotonic() - self.stage_started

    def _paths(self) -> dict[str, Path]:
        return {
            "identity": self.out_dir / f"identity_{self.token}.json",
            "control": self.out_dir / f"control_{self.token}.txt",
            "ack": self.out_dir / f"ack_{self.token}.txt",
            "stop": self.out_dir / f"stop_{self.token}.txt",
        }

    def create_suspended(self) -> None:
        job = KERNEL.CreateJobObjectW(None, None)
        if not job:
            raise StageBlocked("D30_R3_BLOCKED_CONTAINMENT_UNAVAILABLE", f"CreateJobObjectW {ctypes.get_last_error()}")
        self.job = Owned(int(job), "job")
        _set_limits(self.job.value, self.active_limit)
        self.limit_flags, active = read_limits(self.job.value)
        if not limits_are_contained(self.limit_flags, active) or active != self.active_limit:
            raise StageBlocked("D30_R3_BLOCKED_CONTAINMENT_UNAVAILABLE", "limit readback")
        argv = [sys.executable, "-B", str(self.worker), self.mode, str(self.out_dir), self.token]
        spawned = spawn_suspended(argv, self.out_dir, minimal_env(), "pipes")
        Session.created_processes += 1
        self.worker_process = spawned.process
        self.worker_thread = spawned.thread
        self.stdout_read = spawned.stdout_read
        self.stderr_read = spawned.stderr_read
        self.worker_pid = spawned.pid
        self.inherited = list(spawned.inherited)
        self.worker_creation = process_times(self.worker_process.value)
        self._start_readers()

    def _start_readers(self) -> None:
        if self.stdout_read is None or self.stderr_read is None:
            return
        out = threading.Thread(target=_read_pipe, args=(self.stdout_read.value, self._chunks, self._lock, self._overflow))
        err = threading.Thread(target=_read_pipe, args=(self.stderr_read.value, self._err_chunks, self._lock, self._overflow))
        out.start()
        err.start()
        self._readers = [out, err]

    def assign_job(self) -> None:
        if self.job is None or self.worker_process is None:
            raise StageBlocked("D30_R3_BLOCKED_CREATION_RACE", "missing handles")
        if still_alive(self.worker_process.value) is False:
            raise StageBlocked("D30_R3_BLOCKED_CREATION_RACE", "worker ran before assign")
        ok = KERNEL.AssignProcessToJobObject(self.job.value, self.worker_process.value)
        if not ok:
            code = ctypes.get_last_error()
            self._terminate_owned_process(self.worker_process)
            raise StageBlocked("D30_R3_BLOCKED_CONTAINMENT_UNAVAILABLE", f"AssignProcessToJobObject {code}")

    def verify_membership(self) -> None:
        if self.job is None or self.worker_process is None:
            raise StageBlocked("D30_R3_BLOCKED_CREATION_RACE", "missing handles")
        self.worker_in_job = process_in_job(self.worker_process.value, self.job.value)
        if not self.worker_in_job:
            self._terminate_owned_process(self.worker_process)
            raise StageBlocked("D30_R3_BLOCKED_CREATION_RACE", "worker not in job before resume")
        self.identity_guard_ok = (not creation_matches(self.worker_process.value, self.worker_creation[0] ^ 1, self.worker_creation[1])) and creation_matches(self.worker_process.value, *self.worker_creation)

    def resume(self) -> None:
        if self.worker_thread is None or not self.worker_in_job:
            raise StageBlocked("D30_R3_BLOCKED_CREATION_RACE", "resume without membership")
        previous = KERNEL.ResumeThread(self.worker_thread.value)
        self.resume_previous_count = int(previous)
        self.worker_thread.close()
        if previous == 0xFFFFFFFF or previous != 1:
            raise StageBlocked("D30_R3_BLOCKED_CREATION_RACE", f"ResumeThread {previous}")

    def _terminate_owned_process(self, owned: Owned | None) -> None:
        if owned is None or owned.closed:
            return
        KERNEL.TerminateProcess(owned.value, 1)
        wait_handle(owned.value, self.cleanup_allowance)

    def _open_verified_descendant(self, pid: int, low: int, high: int) -> int:
        access = PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE
        handle = KERNEL.OpenProcess(access, False, pid)
        if not handle:
            raise StageBlocked("D30_R3_BLOCKED_DESCENDANT_VERIFICATION", f"OpenProcess {ctypes.get_last_error()}")
        if not creation_matches(int(handle), low, high):
            KERNEL.CloseHandle(handle)
            raise StageBlocked("D30_R3_BLOCKED_DESCENDANT_VERIFICATION", "creation mismatch")
        return int(handle)

    def _request_abort(self) -> None:
        paths = self._paths()
        paths["control"].write_text("abort\n", encoding="utf-8")
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if paths["ack"].exists() and paths["ack"].read_text(encoding="utf-8").strip() == "aborted":
                return
            time.sleep(0.02)

    def _await_descendant(self) -> None:
        paths = self._paths()
        deadline = time.monotonic() + 5.0
        payload = None
        while time.monotonic() < deadline:
            if self.stage_elapsed() >= self.stage_deadline:
                self._request_abort()
                raise StageBlocked("D30_R3_BLOCKED_DEADLINE_CLEANUP", "stage expired during setup")
            if paths["identity"].exists():
                try:
                    payload = json.loads(paths["identity"].read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    self._request_abort()
                    raise StageBlocked("D30_R3_BLOCKED_DESCENDANT_VERIFICATION", "identity malformed")
                break
            time.sleep(0.02)
        if payload is None:
            self._request_abort()
            raise StageBlocked("D30_R3_BLOCKED_DESCENDANT_VERIFICATION", "identity missing")
        try:
            pid, low, high = parse_identity(payload)
        except Reject:
            self._request_abort()
            raise StageBlocked("D30_R3_BLOCKED_DESCENDANT_VERIFICATION", "identity rejected")
        try:
            handle = self._open_verified_descendant(pid, low, high)
        except StageBlocked:
            self._request_abort()
            raise
        self.descendant_process = Owned(handle, "descendant")
        self.descendant_pid = pid
        self.descendant_creation = (low, high)
        if self.job is None or not process_in_job(handle, self.job.value):
            paths["control"].write_text("abort\n", encoding="utf-8")
            self._terminate_owned_process(self.descendant_process)
            raise StageBlocked("D30_R3_BLOCKED_DESCENDANT_CONTAINMENT", "descendant outside job")
        self.descendant_in_job = True
        paths["control"].write_text("resume\n", encoding="utf-8")
        ack_deadline = time.monotonic() + 2.0
        while time.monotonic() < ack_deadline:
            if paths["ack"].exists() and paths["ack"].read_text(encoding="utf-8").strip() == "resumed":
                self.descendant_resume_observed = True
                break
            time.sleep(0.02)
        if not self.descendant_resume_observed:
            raise StageBlocked("D30_R3_BLOCKED_DESCENDANT_VERIFICATION", "resume ack missing")
        if still_alive(self.descendant_process.value):
            self.descendant_in_job = process_in_job(self.descendant_process.value, self.job.value)
            if not self.descendant_in_job:
                raise StageBlocked("D30_R3_BLOCKED_DESCENDANT_CONTAINMENT", "membership lost after resume")
            self.job_pids, self.job_assigned_count = job_process_ids(self.job.value)
            self.job_member_names = [job_member_basename(self.job.value, pid) for pid in self.job_pids]
        else:
            self.descendant_exit_confirmed = exit_code(self.descendant_process.value) not in {None, STILL_ACTIVE}

    def _snapshot_output(self) -> bytes:
        with self._lock:
            return b"".join(self._chunks)

    def _finish_output(self) -> None:
        raw = self._snapshot_output()
        if self._accepting:
            self.disposition = accept_stdout(raw)
            self.accepted = self.disposition == "accepted"
        else:
            self.discarded_after_deadline = max(0, len(raw) - self._frozen)
            self.accepted = False
            if self.disposition == "empty":
                self.disposition = "rejected_after_deadline"
        self.stdout_bytes = len(raw)
        self.saw_unlisted_marker = b"redact-me" in raw
        with self._lock:
            self.stderr_bytes = sum(len(part) for part in self._err_chunks)

    def execute(self) -> dict[str, object]:
        self.attempts += 1
        paths = self._paths()
        try:
            if self.stage_elapsed() >= self.stage_deadline:
                self.stop_reason = "stage"
                return self.public_record()
            self.create_suspended()
            self.assign_job()
            self.verify_membership()
            self.resume()
            if self.spawn:
                self._await_descendant()
            elif self.job is not None and self.worker_process is not None and still_alive(self.worker_process.value):
                self.job_pids, self.job_assigned_count = job_process_ids(self.job.value)
                self.job_member_names = [job_member_basename(self.job.value, pid) for pid in self.job_pids]
            self.operation_started = time.monotonic()
            while True:
                if self._overflow[0]:
                    self.stop_reason = "output"
                    break
                if self.stage_elapsed() >= self.stage_deadline:
                    self.stop_reason = "stage"
                    break
                elapsed = time.monotonic() - self.operation_started
                if elapsed >= self.operation_deadline:
                    self.stop_reason = "operation"
                    break
                if self.worker_process is not None and not still_alive(self.worker_process.value):
                    self.stop_reason = "completed"
                    break
                time.sleep(0.02)
            self.deadline_at = time.monotonic()
            self._accepting = self.stop_reason == "completed"
            self._frozen = len(self._snapshot_output())
            if self.stop_reason != "completed":
                if self.graceful:
                    paths["stop"].write_text("stop\n", encoding="utf-8")
                    graceful_end = time.monotonic() + 0.15
                    while time.monotonic() < graceful_end and self.worker_process is not None and still_alive(self.worker_process.value):
                        time.sleep(0.02)
                    self.alive_after_graceful = self.worker_process is not None and still_alive(self.worker_process.value)
                if self.mode == "late":
                    observe_end = time.monotonic() + 0.45
                    while time.monotonic() < observe_end and self.worker_process is not None and still_alive(self.worker_process.value):
                        time.sleep(0.02)
                self.termination_at = time.monotonic()
                self._terminate()
            else:
                self.termination_at = self.deadline_at
                if self.descendant_process is not None and still_alive(self.descendant_process.value):
                    self.descendant_alive_after_worker = True
                    self.descendant_in_job_after_worker = self.job is not None and process_in_job(self.descendant_process.value, self.job.value)
                    self._terminate()
            self._reap()
        finally:
            try:
                self._reap()
            finally:
                self._cleanup_files()
        self._finish_output()
        return self.public_record()

    def _terminate(self) -> None:
        if self.job is None or self.job.closed:
            return
        if self.close_without_terminate:
            alive_before = bool(self.worker_process and still_alive(self.worker_process.value))
            self.job.close()
            self.termination_method = "CloseHandle"
            worker_done = self.worker_process is not None and wait_handle(self.worker_process.value, self.cleanup_allowance)
            descendant_done = True if self.descendant_process is None else wait_handle(self.descendant_process.value, self.cleanup_allowance)
            self.kill_on_close_sufficient = alive_before and worker_done and descendant_done and not self._any_alive()
            if self._any_alive():
                self.termination_method = "TerminateProcess-owned-handle"
                if self.worker_process is not None and still_alive(self.worker_process.value):
                    self._terminate_owned_process(self.worker_process)
                if self.descendant_process is not None and still_alive(self.descendant_process.value):
                    self._terminate_owned_process(self.descendant_process)
            return
        if KERNEL.TerminateJobObject(self.job.value, 1):
            self.termination_method = "TerminateJobObject"
        else:
            self.termination_method = "TerminateProcess-owned-handle"
            self._terminate_owned_process(self.worker_process)
            self._terminate_owned_process(self.descendant_process)

    def _any_alive(self) -> bool:
        worker_alive = self.worker_process is not None and not self.worker_process.closed and still_alive(self.worker_process.value)
        descendant_alive = self.descendant_process is not None and not self.descendant_process.closed and still_alive(self.descendant_process.value)
        return worker_alive or descendant_alive

    def _reap(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self.cleanup_started = time.monotonic()
        if self.worker_process is not None and still_alive(self.worker_process.value) and self.termination_method == "none":
            self._terminate()
        if self.worker_process is not None:
            wait_handle(self.worker_process.value, self.cleanup_allowance)
        if self.descendant_process is not None:
            wait_handle(self.descendant_process.value, self.cleanup_allowance)
        if self._any_alive() and self.job is not None and not self.job.closed:
            KERNEL.TerminateJobObject(self.job.value, 1)
            if self.termination_method == "none":
                self.termination_method = "TerminateJobObject"
            if self.worker_process is not None:
                wait_handle(self.worker_process.value, self.cleanup_allowance)
            if self.descendant_process is not None:
                wait_handle(self.descendant_process.value, self.cleanup_allowance)
        if self._any_alive() and self.job is not None and not self.job.closed:
            self.job.close()
            if self.worker_process is not None:
                wait_handle(self.worker_process.value, self.cleanup_allowance)
            if self.descendant_process is not None:
                wait_handle(self.descendant_process.value, self.cleanup_allowance)
        self.worker_exit = None if self.worker_process is None else exit_code(self.worker_process.value)
        self.descendant_exit = None if self.descendant_process is None else exit_code(self.descendant_process.value)
        self.worker_exit_confirmed = self.worker_exit is not None and self.worker_exit != STILL_ACTIVE
        if self.descendant_process is None:
            self.descendant_exit_confirmed = False
        else:
            self.descendant_exit_confirmed = self.descendant_exit is not None and self.descendant_exit != STILL_ACTIVE
        if self._any_alive():
            self.cleanup_blocked = True
            self.unresolved.append({"worker_pid": self.worker_pid, "descendant_pid": self.descendant_pid, "state": "alive"})
        for owned in (self.worker_process, self.descendant_process, self.job, self.stdout_read, self.stderr_read, self.worker_thread):
            if owned is not None:
                owned.close()
        for reader in self._readers:
            reader.join(timeout=1.0)
        self.handles_closed = all(owned is None or owned.closed for owned in (self.worker_process, self.descendant_process, self.job, self.stdout_read, self.stderr_read, self.worker_thread))
        self.cleanup_finished = time.monotonic()
        if self.cleanup_blocked:
            raise StageBlocked("D30_R3_BLOCKED_PROCESS_CLEANUP", "exit not confirmed")

    def _cleanup_files(self) -> None:
        for path in self._paths().values():
            if path.exists():
                path.unlink()

    def public_record(self) -> dict[str, object]:
        operation_elapsed = max(0.0, self.deadline_at - self.operation_started)
        cleanup_duration = max(0.0, self.cleanup_finished - self.cleanup_started)
        total = max(0.0, self.cleanup_finished - self.started)
        return {
            "mode": self.mode,
            "stop_reason": self.stop_reason,
            "job_handle_closed": self.job.closed if self.job is not None else True,
            "worker_pid": self.worker_pid,
            "worker_creation_low": self.worker_creation[0],
            "worker_creation_high": self.worker_creation[1],
            "descendant_pid": self.descendant_pid or None,
            "descendant_creation_low": self.descendant_creation[0] or None,
            "descendant_creation_high": self.descendant_creation[1] or None,
            "worker_in_job": self.worker_in_job,
            "descendant_in_job": self.descendant_in_job if self.spawn else None,
            "resume_previous_count": self.resume_previous_count,
            "descendant_resumed_after_membership": self.descendant_resume_observed if self.spawn else None,
            "descendant_alive_after_worker": self.descendant_alive_after_worker,
            "descendant_in_job_after_worker": self.descendant_in_job_after_worker,
            "limit_flags": self.limit_flags,
            "breakaway_clear": not bool(self.limit_flags & (JOB_OBJECT_LIMIT_BREAKAWAY_OK | JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK)),
            "job_pids": self.job_pids,
            "job_assigned_count": self.job_assigned_count,
            "job_member_names": self.job_member_names,
            "monotonic_start": round(self.started, 6),
            "operation_deadline": self.operation_deadline,
            "operation_elapsed": round(operation_elapsed, 4),
            "termination_method": self.termination_method,
            "termination_elapsed": round(max(0.0, self.termination_at - self.started), 4),
            "cleanup_duration": round(cleanup_duration, 4),
            "total_elapsed": round(total, 4),
            "worker_exit_code": self.worker_exit,
            "descendant_exit_code": self.descendant_exit if self.spawn else None,
            "worker_exit_confirmed": self.worker_exit_confirmed,
            "descendant_exit_confirmed": self.descendant_exit_confirmed if self.spawn else None,
            "alive_after_graceful": self.alive_after_graceful,
            "identity_guard_ok": self.identity_guard_ok,
            "kill_on_close_sufficient": self.kill_on_close_sufficient,
            "discarded_after_deadline": self.discarded_after_deadline,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "disposition": self.disposition,
            "accepted": self.accepted,
            "saw_unlisted_marker": self.saw_unlisted_marker,
            "handles_closed": self.handles_closed,
            "stage_origin": round(self.stage_started, 6),
            "inherited_handles": self.inherited,
            "attempts": self.attempts,
            "cleanup_blocked": self.cleanup_blocked,
            "unresolved": self.unresolved,
            "clock": "monotonic",
        }
