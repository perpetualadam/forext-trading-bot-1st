"""Offline startup and termination tests for the R.61 supervisor copy.

No socket is opened. The R.56 gate check reads files outside this directory and
fails closed when they are absent. Hanging launches run inside a killed driver.
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
    name = f"r61_{stem}"
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
    blobs = [json.dumps(record)]
    saved = folder / (str(record["session_id"]) + ".json")
    if saved.is_file():
        blobs.append(saved.read_text(encoding="utf-8"))
    for blob in blobs:
        assert ACCOUNT not in blob
        assert TOKEN not in blob
        assert "Bearer" not in blob
        assert MARKER not in blob
        assert "UNIQUE_REGISTER" not in blob
        assert "UNIQUE_LAUNCH" not in blob
        assert "UNIQUE_BROKEN" not in blob
        assert "XXXX" not in blob
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert record["executable_order"] == "NOT_PRODUCED"
    assert record["live_network_access"] == "REAL_NETWORK_NOT_COMPLETED"
    assert record["network_attempted"] is False
    assert record["broker_response_received"] is False


def _session(supervisor, gate, folder: Path, **kwargs):
    started = time.monotonic()
    record = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        request_deadline=kwargs.pop("request_deadline", 5),
        session_deadline=kwargs.pop("session_deadline", 5),
        log_dir=folder,
        **kwargs,
    )
    return record, time.monotonic() - started


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
    if _pid_alive(pid):
        os.kill(pid, signal.SIGTERM)


class _Pipe:
    def __init__(self) -> None:
        self.closed = False
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True

    def write(self, data: bytes) -> int:
        return len(data)

    def flush(self) -> None:
        return None

    def readline(self) -> bytes:
        return b""

    def read(self) -> bytes:
        return b""


class _Hold(_Pipe):
    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()
        self.entered = threading.Event()

    def write(self, data: bytes) -> int:
        self.entered.set()
        self.release.wait(5)
        return len(data)


class _Fake:
    def __init__(self, *, kill: str = "die", exited: bool = False) -> None:
        self.stdin = _Hold() if kill == "block" else _Pipe()
        self.stdout = _Pipe()
        self.stderr = _Pipe()
        self.returncode: int | None = 0 if exited else None
        self.kills = 0
        self.waits: list[float | None] = []
        self.kill_mode = kill
        self.seen_alive_at_add = False

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.kills += 1
        if self.kill_mode in {"permission", "survive", "block"}:
            if self.kill_mode == "permission":
                raise PermissionError("denied")
            return None
        self.returncode = 1
        return None

    def wait(self, timeout: float | None = None) -> int:
        self.waits.append(timeout)
        if self.returncode is None:
            raise subprocess.TimeoutExpired("r61-worker", timeout or 0)
        return self.returncode

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
        raise AssertionError("communicate")


def test_gates_and_r56_evidence_fail_closed_when_absent() -> None:
    text = (HERE / "live_session_gate.py").read_text(encoding="utf-8")
    assert "REAL_SESSION_SOURCE_ENABLEMENT = False" in text
    assert load("live_session_gate").REAL_SESSION_SOURCE_ENABLEMENT is False
    assert "REAL_SESSION_SOURCE_ENABLEMENT = False" in R56_GATE.read_text(encoding="utf-8")
    assert R56_CONSUMED.is_file()
    assert not R56_PERMIT.exists()
    assert not (HERE / "real_activation").exists()
    banned = ("forex_bot", "load_dotenv", "import dotenv", "import requests", "import httpx", "main.py")
    for path in HERE.glob("*.py"):
        if path.name == "test_r61_offline.py":
            continue
        body = path.read_text(encoding="utf-8")
        for item in banned:
            assert item not in body
    worker = (HERE / "diagnostic_worker.py").read_text(encoding="utf-8")
    assert "Popen" not in worker


def test_real_session_refuses_before_a_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")

    def boom(_screen: str) -> str:
        raise AssertionError("prompted")

    with pytest.raises(gate.GateRejected) as rejected:
        supervisor.run_real_session(reader=boom)
    assert rejected.value.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"


def test_deadline_before_popen_does_not_create_a_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    ipc = supervisor._load("credential_ipc")
    real_frame = ipc.authenticated_frame
    calls = {"popen": 0}

    def slow_frame(*args: object, **kwargs: object) -> bytes:
        time.sleep(0.45)
        return real_frame(*args, **kwargs)

    def fail_popen(*_args: object, **_kwargs: object) -> None:
        calls["popen"] += 1
        raise AssertionError("spawned")

    ipc.authenticated_frame = slow_frame
    monkeypatch.setattr(supervisor.subprocess, "Popen", fail_popen)
    try:
        record, elapsed = _session(supervisor, gate, tmp_path / "before", session_deadline=0.2)
    finally:
        ipc.authenticated_frame = real_frame
    assert elapsed < 2.0
    assert calls["popen"] == 0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["children_started"] == 0
    assert record["child_alive"] is False
    assert record["child_terminated"] is False
    _quiet(record, tmp_path / "before")


_BLOCK_DRIVER = r"""
import importlib.util
import sys
import time
from pathlib import Path

here = Path(sys.argv[1])
status = Path(sys.argv[2])
account = sys.argv[3]
token = sys.argv[4]
phrase = sys.argv[5]


def load(stem):
    name = "r61_" + stem
    spec = importlib.util.spec_from_file_location(name, here / (stem + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


supervisor = load("diagnostic_supervisor")


def blocking_popen(*_args, **_kwargs):
    status.write_text("entered", encoding="utf-8")
    time.sleep(30)
    raise RuntimeError("launch was not interrupted")


supervisor.subprocess.Popen = blocking_popen
supervisor.run_harness_session(
    answer=phrase,
    account_id=account,
    token=token,
    document={"instruments": [], "lastTransactionID": "1"},
    request_deadline=5,
    session_deadline=0.25,
    log_dir=status.parent / "logs",
)
status.write_text("returned", encoding="utf-8")
"""


def test_blocked_popen_is_not_interrupted_by_the_session_deadline(tmp_path: Path) -> None:
    driver = tmp_path / "block_driver.py"
    status = tmp_path / "status.txt"
    driver.write_text(_BLOCK_DRIVER, encoding="utf-8")
    gate = load("live_session_gate")
    proc = subprocess.Popen(
        [sys.executable, "-B", str(driver), str(HERE), str(status), ACCOUNT, TOKEN, gate.ONE_SESSION_PHRASE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    started = time.monotonic()
    try:
        seen = False
        while time.monotonic() - started < 5:
            if status.is_file() and status.read_text(encoding="utf-8") == "entered":
                seen = True
                break
            if proc.poll() is not None:
                err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr is not None else ""
                raise AssertionError(err[-500:])
            time.sleep(0.05)
        assert seen
        time.sleep(0.5)
        assert proc.poll() is None
        assert status.read_text(encoding="utf-8") == "entered"
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        for pipe in (proc.stdout, proc.stderr):
            if pipe is not None:
                pipe.close()
    elapsed = time.monotonic() - started
    assert elapsed < 8.0
    assert proc.poll() is not None
    assert TOKEN not in status.read_text(encoding="utf-8")


def test_failed_launch_and_exit_during_registration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")

    def fail_popen(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("UNIQUE_LAUNCH")

    monkeypatch.setattr(supervisor.subprocess, "Popen", fail_popen)
    failed, failed_elapsed = _session(supervisor, gate, tmp_path / "launch", session_deadline=5)
    assert failed_elapsed < 2.0
    assert failed["error_code"] == "SESSION_FAILED"
    assert failed["children_started"] == 0
    assert failed["child_alive"] is False
    _quiet(failed, tmp_path / "launch")

    exited = _Fake(exited=True)

    def already_dead(_data: bytes) -> int:
        raise BrokenPipeError("UNIQUE_BROKEN")

    exited.stdin.write = already_dead  # type: ignore[method-assign]

    def exited_popen(*_args: object, **_kwargs: object) -> _Fake:
        exited.seen_alive_at_add = exited.poll() is not None
        return exited

    monkeypatch.setattr(supervisor.subprocess, "Popen", exited_popen)
    record, elapsed = _session(supervisor, gate, tmp_path / "registered-dead", session_deadline=5)
    assert elapsed < 2.0
    assert exited.seen_alive_at_add is True
    assert record["children_started"] == 1
    assert record["child_alive"] is False
    assert record["error_code"] == "CHILD_CRASHED"
    assert exited.stdout.closed is True
    assert exited.stderr.closed is True
    _quiet(record, tmp_path / "registered-dead")


def test_registration_failure_keeps_the_process_for_cleanup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    proc = _Fake()

    def popen(*_args: object, **_kwargs: object) -> _Fake:
        return proc

    def refuse_add(self: object, _added: object) -> None:
        raise RuntimeError("UNIQUE_REGISTER")

    monkeypatch.setattr(supervisor.subprocess, "Popen", popen)
    monkeypatch.setattr(supervisor.ChildTracker, "add", refuse_add)
    record, elapsed = _session(supervisor, gate, tmp_path / "register", session_deadline=5)
    assert elapsed < 2.0
    assert record["error_code"] == "SESSION_FAILED"
    assert record["children_started"] == 1
    assert record["child_alive"] is False
    assert proc.kills >= 1
    assert proc.poll() is not None
    assert proc.stdout.closed is True
    _quiet(record, tmp_path / "register")


def test_untracked_release_does_not_close_a_live_stdin() -> None:
    supervisor = load("diagnostic_supervisor")
    proc = _Fake(kill="survive")
    assert supervisor._release_untracked(proc) is None
    assert proc.kills >= 1
    assert proc.poll() is None
    assert proc.stdin.close_calls == 0
    assert proc.stdout.closed is True
    assert proc.stderr.closed is True
    assert set(proc.waits) == {5}


def test_surviving_child_and_permission_error_are_not_reaped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    procs: list[_Fake] = []

    def popen(*_args: object, **_kwargs: object) -> _Fake:
        proc = _Fake(kill="survive")
        proc.stdin = _Hold()
        procs.append(proc)
        return proc

    monkeypatch.setattr(supervisor.subprocess, "Popen", popen)
    try:
        record, elapsed = _session(supervisor, gate, tmp_path / "survive", session_deadline=0.35)
    finally:
        for proc in procs:
            proc.stdin.release.set()
    assert elapsed < 2.0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["child_alive"] is True
    assert record["child_terminated"] is True
    assert procs[0].stdin.close_calls == 0
    assert procs[0].stdout.closed is True
    _quiet(record, tmp_path / "survive")

    denied: list[_Fake] = []

    def deny_popen(*_args: object, **_kwargs: object) -> _Fake:
        proc = _Fake(kill="permission")
        proc.stdin = _Hold()
        denied.append(proc)
        return proc

    monkeypatch.setattr(supervisor.subprocess, "Popen", deny_popen)
    try:
        blocked, blocked_elapsed = _session(supervisor, gate, tmp_path / "denied", session_deadline=0.35)
    finally:
        for proc in denied:
            proc.stdin.release.set()
    assert blocked_elapsed < 2.0
    assert blocked["error_code"] == "SESSION_DEADLINE"
    assert blocked["child_alive"] is True
    assert denied[0].stdin.close_calls == 0
    _quiet(blocked, tmp_path / "denied")


def test_sigterm_ignoring_child_is_killed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    script = tmp_path / "ignore_term.py"
    script.write_text(
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, lambda *_args: None)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(supervisor, "WORKER", script)
    record, elapsed = _session(supervisor, gate, tmp_path / "term", session_deadline=0.4)
    assert elapsed < 3.0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["child_alive"] is False
    assert record["children_started"] == 1
    _quiet(record, tmp_path / "term")


def test_grandchild_survives_parent_termination(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        started = time.monotonic()
        assert tracker.cleanup() is None
        cleanup_elapsed = time.monotonic() - started
        assert cleanup_elapsed < 3.0
        assert parent.poll() is not None
        assert _pid_alive(grandchild)
        assert parent.stdin is not None and parent.stdin.closed is True
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        if grandchild:
            _pid_stop(grandchild)
            for _ in range(40):
                if not _pid_alive(grandchild):
                    break
                time.sleep(0.05)
            assert not _pid_alive(grandchild)


def test_cleanup_exception_keeps_a_survivor_alive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    proc = _Fake(kill="permission")
    proc.stdin = _Hold()
    polls = {"n": 0}
    real_poll = proc.poll

    def raising_poll() -> int | None:
        polls["n"] += 1
        if polls["n"] >= 3:
            raise RuntimeError("UNIQUE_CLEANUP")
        return real_poll()

    proc.poll = raising_poll  # type: ignore[method-assign]

    def popen(*_args: object, **_kwargs: object) -> _Fake:
        return proc

    monkeypatch.setattr(supervisor.subprocess, "Popen", popen)
    try:
        record, elapsed = _session(supervisor, gate, tmp_path / "cleanup", session_deadline=0.35)
    finally:
        proc.stdin.release.set()
    assert elapsed < 2.0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["child_alive"] is True
    assert "UNIQUE_CLEANUP" not in json.dumps(record)
    _quiet(record, tmp_path / "cleanup")


def test_normal_exit_closes_handles_and_repeated_sessions_stay_stable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    real_popen = supervisor.subprocess.Popen
    kept: list[subprocess.Popen[bytes]] = []

    def spy(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
        kept.append(proc)
        return proc

    monkeypatch.setattr(supervisor.subprocess, "Popen", spy)
    before = threading.active_count()
    for index in range(3):
        record, elapsed = _session(supervisor, gate, tmp_path / f"ok-{index}")
        assert elapsed < 3.0
        assert record["error_code"] == "NONE"
        assert record["child_alive"] is False
        assert record["children_started"] == 1
        assert record["record_persisted"] is True
        assert [item["name"]["value"] for item in record["instruments"]] == list(INSTRUMENTS)
        proc = kept[-1]
        assert proc.poll() is not None
        assert proc.stdin is None or proc.stdin.closed is True
        assert proc.stdout is not None and proc.stdout.closed is True
        assert proc.stderr is not None and proc.stderr.closed is True
        _quiet(record, tmp_path / f"ok-{index}")
    assert threading.active_count() <= before + 1


def test_broken_ipc_during_startup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    proc = _Fake()

    def broken_write(_data: bytes) -> int:
        raise BrokenPipeError("UNIQUE_BROKEN")

    proc.stdin.write = broken_write  # type: ignore[method-assign]

    def popen(*_args: object, **_kwargs: object) -> _Fake:
        return proc

    monkeypatch.setattr(supervisor.subprocess, "Popen", popen)
    record, elapsed = _session(supervisor, gate, tmp_path / "broken", session_deadline=5)
    assert elapsed < 2.0
    assert record["error_code"] == "CHILD_CRASHED"
    assert record["child_alive"] is False
    assert record["children_started"] == 1
    _quiet(record, tmp_path / "broken")


_PIPE_DRIVER = r"""
import importlib.util
import json
import sys
import time
from pathlib import Path

here = Path(sys.argv[1])
destination = Path(sys.argv[2])
account = sys.argv[3]
token = sys.argv[4]
phrase = sys.argv[5]


def load(stem):
    name = "r61_" + stem
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
destination.write_text(
    json.dumps(
        {
            "error_code": record["error_code"],
            "session_status": record["session_status"],
            "child_alive": record["child_alive"],
            "elapsed": time.monotonic() - started,
            "record": json.dumps(record),
        }
    ),
    encoding="utf-8",
)
"""


def test_real_pipe_deadline_still_kills_before_close(tmp_path: Path) -> None:
    driver = tmp_path / "pipe_driver.py"
    result = tmp_path / "result.json"
    driver.write_text(_PIPE_DRIVER, encoding="utf-8")
    gate = load("live_session_gate")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-B", str(driver), str(HERE), str(result), ACCOUNT, TOKEN, gate.ONE_SESSION_PHRASE],
            timeout=8,
            capture_output=True,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        if expired.stdout is None:
            pass
        raise AssertionError("real-pipe deadline blocked past the independent 8 second bound")
    assert time.monotonic() - started < 4.0
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
