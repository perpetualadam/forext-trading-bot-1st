"""Offline fault injection for the R.60 supervisor copy. No socket is opened.

The R.56 gate and consumed-permit checks read files outside this directory.
They fail closed when those files are absent. They do not create or replace them.
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
R56_GATE = ROOT / "data" / "research" / "adaptive_ensemble" / "r56" / "phase6_connection_enablement" / "live_session_gate.py"
R56_CONSUMED = ROOT / "data" / "research" / "adaptive_ensemble" / "r56" / "phase6_connection_enablement" / "real_activation" / "one_session.consumed"
R56_PERMIT = R56_CONSUMED.with_name("one_session.permit")
ACCOUNT = "001-002-0000001-003"
TOKEN = "SYNTHETIC-NOT-REAL-R59-TOKEN"
MARKER = "UNIQUE_RAW_BODY_MARKER"
INSTRUMENTS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")


def load(stem: str):
    name = f"r60_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network opened")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def _row(name: str) -> dict:
    return {
        "name": name,
        "type": "CURRENCY",
        "pipLocation": -2 if name == "USD_JPY" else -4,
        "displayPrecision": 3 if name == "USD_JPY" else 5,
        "tradeUnitsPrecision": 0,
        "minimumTradeSize": "1",
        "maximumOrderUnits": "100000000",
        "maximumPositionSize": "0",
        "marginRate": "0.03330000",
        "ignoredRaw": MARKER,
        "accountID": ACCOUNT,
    }


def _document() -> dict:
    return {"instruments": [_row(name) for name in INSTRUMENTS], "lastTransactionID": "999"}


def _quiet(record: dict, folder: Path) -> None:
    saved = folder / (str(record["session_id"]) + ".json")
    blobs = [json.dumps(record)]
    if saved.is_file():
        blobs.append(saved.read_text(encoding="utf-8"))
    for blob in blobs:
        assert ACCOUNT not in blob
        assert TOKEN not in blob
        assert "Bearer" not in blob
        assert MARKER not in blob
        assert "UNIQUE_BROKEN_MARKER" not in blob
        assert "UNIQUE_CLEANUP_BOOM" not in blob
        assert "XXXX" not in blob
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert record["executable_order"] == "NOT_PRODUCED"
    assert record["live_network_access"] == "REAL_NETWORK_NOT_COMPLETED"
    assert record["network_attempted"] is False
    assert record["broker_response_received"] is False


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        kernel.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _pid_stop(pid: int) -> None:
    if not _pid_alive(pid):
        return
    os.kill(pid, signal.SIGTERM)


class _Pipe:
    def __init__(self) -> None:
        self.closed = False
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True


class _HoldStdin(_Pipe):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def write(self, data: bytes) -> int:
        self.entered.set()
        try:
            if self.mode == "broken":
                raise BrokenPipeError("UNIQUE_BROKEN_MARKER")
            if self.mode == "ready":
                return len(data)
            if not self.release.wait(5):
                raise TimeoutError("writer")
            if self.closed:
                raise BrokenPipeError("UNIQUE_BROKEN_MARKER")
            return len(data)
        finally:
            self.finished.set()

    def flush(self) -> None:
        return None


class _BlockStdout(_Pipe):
    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()

    def readline(self) -> bytes:
        self.release.wait(10)
        return b""

    def read(self) -> bytes:
        return b""

    def close(self) -> None:
        super().close()
        self.release.set()


class _FakeProc:
    def __init__(self, mode: str, *, kill: str) -> None:
        self.mode = mode
        self.kill_mode = kill
        self.stdin = _HoldStdin(mode)
        self.stdout = _BlockStdout() if mode == "ready" else _Pipe()
        self.stderr = _Pipe()
        self.returncode: int | None = None
        self.kills = 0
        self.wait_timeouts: list[float | None] = []
        self.polls = 0
        self.poll_error_after = 99

    def poll(self) -> int | None:
        self.polls += 1
        if self.polls >= self.poll_error_after:
            raise RuntimeError("UNIQUE_CLEANUP_BOOM")
        return self.returncode

    def kill(self) -> None:
        self.kills += 1
        if self.kill_mode == "permission":
            raise PermissionError("denied")
        if self.kill_mode == "oserror":
            raise OSError("denied")
        if self.kill_mode == "already-exited":
            self.returncode = 0
            raise ProcessLookupError(3, "already exited")
        if self.kill_mode == "survive":
            return None
        self.returncode = 1
        return None

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeouts.append(timeout)
        if self.returncode is None:
            raise subprocess.TimeoutExpired("r60-worker", timeout or 0)
        return self.returncode

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
        raise AssertionError("communicate")


def _session(supervisor, gate, tmp_path: Path, name: str, **kwargs):
    started = time.monotonic()
    record = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        request_deadline=kwargs.pop("request_deadline", 5),
        session_deadline=kwargs.pop("session_deadline", 0.4),
        log_dir=tmp_path / name,
        **kwargs,
    )
    return record, time.monotonic() - started


def _install_fake(monkeypatch: pytest.MonkeyPatch, supervisor, mode: str, kill: str) -> list[_FakeProc]:
    procs: list[_FakeProc] = []

    def _popen(*_args: object, **_kwargs: object) -> _FakeProc:
        proc = _FakeProc(mode, kill=kill)
        procs.append(proc)
        return proc

    monkeypatch.setattr(supervisor.subprocess, "Popen", _popen)
    return procs


def _release(proc: _FakeProc) -> None:
    proc.stdin.release.set()
    proc.stdin.finished.wait(2)


def test_r56_evidence_dependency_fails_closed_when_absent() -> None:
    text = (HERE / "live_session_gate.py").read_text(encoding="utf-8")
    assert "REAL_SESSION_SOURCE_ENABLEMENT = False" in text
    assert load("live_session_gate").REAL_SESSION_SOURCE_ENABLEMENT is False
    r56 = R56_GATE.read_text(encoding="utf-8")
    assert "REAL_SESSION_SOURCE_ENABLEMENT = False" in r56
    assert R56_CONSUMED.is_file()
    assert not R56_PERMIT.exists()
    assert not (HERE / "real_activation").exists()


def test_real_session_refuses_before_a_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")

    def boom(_screen: str) -> str:
        raise AssertionError("prompted")

    with pytest.raises(gate.GateRejected) as rejected:
        supervisor.run_real_session(reader=boom)
    assert rejected.value.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"


def test_sources_keep_the_gates_and_bound_the_waits() -> None:
    banned = ("forex_bot", "load_dotenv", "import dotenv", "import requests", "import httpx", "main.py")
    for path in HERE.glob("*.py"):
        if path.name == "test_r60_offline.py":
            continue
        text = path.read_text(encoding="utf-8")
        for item in banned:
            assert item not in text
    supervisor_text = (HERE / "diagnostic_supervisor.py").read_text(encoding="utf-8")
    assert supervisor_text.count("wait(timeout=5)") == 4
    assert "reader.join(1)" in supervisor_text
    worker = (HERE / "diagnostic_worker.py").read_text(encoding="utf-8")
    assert "subprocess" not in worker
    assert "Popen" not in worker


def test_permission_error_does_not_report_a_survivor_reaped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    procs = _install_fake(monkeypatch, supervisor, "block", "permission")
    try:
        record, elapsed = _session(supervisor, gate, tmp_path, "permission")
    finally:
        if procs:
            _release(procs[0])
    assert elapsed < 2.0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["child_alive"] is True
    assert record["child_terminated"] is True
    assert record["children_started"] == 1
    proc = procs[0]
    assert proc.kills >= 1
    assert proc.stdin.close_calls == 0
    assert proc.stdout.closed is True
    assert proc.stderr.closed is True
    assert proc.wait_timeouts
    assert set(proc.wait_timeouts) == {5}
    _quiet(record, tmp_path / "permission")


def test_oserror_on_kill_leaves_the_child_alive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    procs = _install_fake(monkeypatch, supervisor, "block", "oserror")
    try:
        record, elapsed = _session(supervisor, gate, tmp_path, "oserror")
    finally:
        if procs:
            _release(procs[0])
    assert elapsed < 2.0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["child_alive"] is True
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert procs[0].stdin.close_calls == 0
    assert procs[0].stdout.closed is True
    _quiet(record, tmp_path / "oserror")


def test_child_exiting_before_kill_is_not_left_alive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    procs = _install_fake(monkeypatch, supervisor, "block", "already-exited")
    try:
        record, elapsed = _session(supervisor, gate, tmp_path, "exited")
    finally:
        if procs:
            _release(procs[0])
    assert elapsed < 2.0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["child_alive"] is False
    assert procs[0].returncode == 0
    assert procs[0].stdin.close_calls >= 1
    _quiet(record, tmp_path / "exited")


def test_wait_timeout_and_surviving_child_stay_alive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    procs = _install_fake(monkeypatch, supervisor, "block", "survive")
    try:
        record, elapsed = _session(supervisor, gate, tmp_path, "survive")
    finally:
        if procs:
            _release(procs[0])
    assert elapsed < 2.0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["child_alive"] is True
    assert record["child_terminated"] is True
    assert procs[0].stdin.close_calls == 0
    assert procs[0].kills >= 2
    assert set(procs[0].wait_timeouts) == {5}
    _quiet(record, tmp_path / "survive")


def test_blocked_writer_returns_inside_the_session_deadline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    procs = _install_fake(monkeypatch, supervisor, "block", "kill")
    before = threading.active_count()
    try:
        record, elapsed = _session(supervisor, gate, tmp_path, "writer")
        assert procs[0].stdin.entered.is_set()
    finally:
        if procs:
            _release(procs[0])
    assert elapsed < 2.0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["child_alive"] is False
    assert threading.active_count() <= before + 1
    _quiet(record, tmp_path / "writer")


def test_broken_pipe_is_child_crashed_without_the_exception_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    procs = _install_fake(monkeypatch, supervisor, "broken", "kill")
    record, elapsed = _session(supervisor, gate, tmp_path, "broken", session_deadline=5)
    assert elapsed < 2.0
    assert record["error_code"] == "CHILD_CRASHED"
    assert record["child_alive"] is False
    assert record["child_terminated"] is False
    assert procs[0].poll() is not None
    _quiet(record, tmp_path / "broken")


def test_missing_worker_is_child_crashed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    missing = tmp_path / "missing_worker.py"
    monkeypatch.setattr(supervisor, "WORKER", missing)
    record, elapsed = _session(supervisor, gate, tmp_path, "missing", session_deadline=5)
    assert elapsed < 3.0
    assert not missing.exists()
    assert record["error_code"] == "CHILD_CRASHED"
    assert record["child_alive"] is False
    assert record["children_started"] == 1
    _quiet(record, tmp_path / "missing")


def test_empty_stdout_is_child_crashed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    script = tmp_path / "empty_worker.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    monkeypatch.setattr(supervisor, "WORKER", script)
    record, elapsed = _session(supervisor, gate, tmp_path, "empty", session_deadline=5)
    assert elapsed < 3.0
    assert record["error_code"] == "CHILD_CRASHED"
    assert record["child_alive"] is False
    _quiet(record, tmp_path / "empty")


def test_malformed_protocol_stays_incomplete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    record, elapsed = _session(supervisor, gate, tmp_path, "malformed", stall="malformed", session_deadline=5)
    assert elapsed < 3.0
    assert record["error_code"] == "MALFORMED_CHILD_RESULT"
    assert record["child_alive"] is False
    assert record["instruments"] == []
    _quiet(record, tmp_path / "malformed")


def test_cleanup_exception_is_not_a_successful_reap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    cleaned, cleaned_elapsed = _session(supervisor, gate, tmp_path, "cleanup", fault_at="cleanup", session_deadline=5)
    assert cleaned_elapsed < 3.0
    assert cleaned["error_code"] == "CHILD_CLEANUP_FAILED"
    assert cleaned["child_alive"] is False
    assert cleaned["record_persisted"] is True
    _quiet(cleaned, tmp_path / "cleanup")

    procs = _install_fake(monkeypatch, supervisor, "block", "permission")
    procs_holder = procs

    def _popen(*_args: object, **_kwargs: object) -> _FakeProc:
        proc = _FakeProc("block", kill="permission")
        proc.poll_error_after = 3
        procs_holder.append(proc)
        return proc

    monkeypatch.setattr(supervisor.subprocess, "Popen", _popen)
    try:
        blown, blown_elapsed = _session(supervisor, gate, tmp_path, "boom")
    finally:
        for proc in procs_holder:
            _release(proc)
    assert blown_elapsed < 2.0
    assert blown["error_code"] == "SESSION_DEADLINE"
    assert blown["child_alive"] is True
    assert "UNIQUE_CLEANUP_BOOM" not in json.dumps(blown)
    _quiet(blown, tmp_path / "boom")


def test_session_deadline_during_startup_starts_no_false_child(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    with pytest.raises(supervisor.SupervisorRejected) as rejected:
        supervisor.run_harness_session(
            answer=gate.ONE_SESSION_PHRASE,
            account_id=ACCOUNT,
            token=TOKEN,
            document=_document(),
            session_deadline=0,
            log_dir=tmp_path / "cap",
        )
    assert rejected.value.code == "DEADLINE_ABOVE_CAP"

    def fail_popen(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("spawned")

    monkeypatch.setattr(supervisor.subprocess, "Popen", fail_popen)
    real_spawn = supervisor._spawn

    def expired(**kwargs: object):
        kwargs["deadline_at"] = 0
        return real_spawn(**kwargs)

    monkeypatch.setattr(supervisor, "_spawn", expired)
    early, _elapsed = _session(supervisor, gate, tmp_path, "early", session_deadline=1)
    assert early["error_code"] == "SESSION_DEADLINE"
    assert early["children_started"] == 0
    assert early["child_alive"] is False
    assert early["child_terminated"] is False
    _quiet(early, tmp_path / "early")

    monkeypatch.undo()
    _block_network(monkeypatch)
    hung, hung_elapsed = _session(
        supervisor,
        gate,
        tmp_path,
        "startup",
        stall="delay-then-hang",
        session_deadline=0.3,
    )
    assert hung_elapsed < 3.0
    assert hung["error_code"] == "SESSION_DEADLINE"
    assert hung["child_alive"] is False
    assert hung["children_started"] == 1
    _quiet(hung, tmp_path / "startup")


def test_reader_join_after_the_deadline_is_one_second(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    procs = _install_fake(monkeypatch, supervisor, "ready", "kill")
    record, elapsed = _session(supervisor, gate, tmp_path, "reader", session_deadline=0.35)
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["child_alive"] is False
    assert 0.9 <= elapsed < 3.0
    assert procs[0].stdout.closed is True
    _quiet(record, tmp_path / "reader")


def test_repeated_sessions_do_not_leave_children_or_threads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    before = threading.active_count()
    for index in range(3):
        record, elapsed = _session(supervisor, gate, tmp_path, f"repeat-{index}", session_deadline=5)
        assert elapsed < 3.0
        assert record["error_code"] == "NONE"
        assert record["child_alive"] is False
        assert record["children_started"] == 1
        assert record["session_status"] == "SESSION_INCOMPLETE"
        assert record["record_persisted"] is True
        assert [item["name"]["value"] for item in record["instruments"]] == list(INSTRUMENTS)
        assert {item["name"]["status"] for item in record["instruments"]} == {"RETURNED"}
        _quiet(record, tmp_path / f"repeat-{index}")
    procs = _install_fake(monkeypatch, supervisor, "block", "kill")
    try:
        for index in range(5):
            record, elapsed = _session(supervisor, gate, tmp_path, f"fake-{index}")
            assert elapsed < 2.0
            assert record["child_alive"] is False
            assert record["error_code"] == "SESSION_DEADLINE"
            _release(procs[-1])
    finally:
        for proc in procs:
            proc.stdin.release.set()
    assert threading.active_count() <= before + 1


def test_descendant_is_not_reported_reaped_with_its_parent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    script = tmp_path / "parent_sleeper.py"
    script.write_text(
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'])\n"
        "sys.stdout.write(str(child.pid) + '\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    parent = subprocess.Popen(
        [sys.executable, "-B", str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    grandchild = 0
    try:
        holder: dict[str, bytes] = {}

        def _read() -> None:
            assert parent.stdout is not None
            holder["line"] = parent.stdout.readline()

        reader = threading.Thread(target=_read, daemon=True)
        reader.start()
        reader.join(3)
        assert "line" in holder and holder["line"].strip().isdigit()
        grandchild = int(holder["line"].strip())
        assert _pid_alive(grandchild)
        tracker = supervisor.ChildTracker()
        tracker.add(parent)
        assert tracker.cleanup() is None
        assert parent.poll() is not None
        assert _pid_alive(grandchild)
        assert parent.stdin is not None and parent.stdin.closed is True
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        if grandchild:
            _pid_stop(grandchild)
            for _ in range(20):
                if not _pid_alive(grandchild):
                    break
                time.sleep(0.05)
            assert not _pid_alive(grandchild)


def test_closed_stdin_is_not_flushed_again_by_communicate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")

    class _Stdin(_Pipe):
        def write(self, data: bytes) -> int:
            return len(data)

        def flush(self) -> None:
            return None

    class _Stdout(_Pipe):
        def readline(self) -> bytes:
            return b"{}\n"

        def read(self) -> bytes:
            return b"{not-json\n"

    class _Proc:
        def __init__(self) -> None:
            self.stdin = _Stdin()
            self.stdout = _Stdout()
            self.stderr = _Pipe()
            self.returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            self.returncode = 1

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 0
            return 0

        def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
            if self.stdin is not None:
                raise ValueError("flush of closed file")
            self.returncode = 0
            return self.stdout.read(), b""

    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *_args, **_kwargs: _Proc())
    record, elapsed = _session(supervisor, gate, tmp_path, "closed-stdin", session_deadline=5)
    assert elapsed < 2.0
    assert record["error_code"] == "MALFORMED_CHILD_RESULT"
    assert record["child_alive"] is False
    _quiet(record, tmp_path / "closed-stdin")


_PIPE_DRIVER = r"""
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

here = Path(sys.argv[1])
destination = Path(sys.argv[2])
account = sys.argv[3]
token = sys.argv[4]
phrase = sys.argv[5]


def load(stem):
    name = "r60_" + stem
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, here / (stem + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


supervisor = load("diagnostic_supervisor")
ipc = supervisor._load("credential_ipc")
real_frame = ipc.authenticated_frame
real_popen = supervisor.subprocess.Popen


def padded_frame(*args, **kwargs):
    return real_frame(*args, **kwargs) + (b"X" * (256 * 1024))


def sleeper(argv, **kwargs):
    return real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)


ipc.authenticated_frame = padded_frame
supervisor.subprocess.Popen = sleeper
started = time.monotonic()
record = supervisor.run_harness_session(
    answer=phrase,
    account_id=account,
    token=token,
    document={"instruments": [], "lastTransactionID": "1"},
    request_deadline=5,
    session_deadline=0.4,
    log_dir=destination.parent / "logs",
)
elapsed = time.monotonic() - started
text = json.dumps(record)
destination.write_text(
    json.dumps(
        {
            "error_code": record["error_code"],
            "session_status": record["session_status"],
            "child_alive": record["child_alive"],
            "elapsed": elapsed,
            "record": text,
        }
    ),
    encoding="utf-8",
)
"""


def test_real_pipe_deadline_kills_before_close(tmp_path: Path) -> None:
    driver = tmp_path / "pipe_driver.py"
    result = tmp_path / "result.json"
    driver.write_text(_PIPE_DRIVER, encoding="utf-8")
    gate = load("live_session_gate")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(driver),
                str(HERE),
                str(result),
                ACCOUNT,
                TOKEN,
                gate.ONE_SESSION_PHRASE,
            ],
            timeout=8,
            capture_output=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError("real-pipe deadline blocked past the independent 8 second bound")
    elapsed = time.monotonic() - started
    assert elapsed < 4.0
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")[-500:]
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["error_code"] == "SESSION_DEADLINE"
    assert payload["session_status"] == "SESSION_INCOMPLETE"
    assert payload["child_alive"] is False
    assert payload["elapsed"] < 3.0
    rendered = payload["record"]
    assert ACCOUNT not in rendered
    assert TOKEN not in rendered
    assert "Bearer" not in rendered
    assert "XXXX" not in rendered
