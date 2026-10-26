"""Offline tests for the R.59 one-GET diagnostic. No socket is opened."""

from __future__ import annotations

import importlib.util
import json
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
    name = f"r59_{stem}"
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
    def blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def _row(name: str, *, financing: bool = False) -> dict:
    row = {
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
    if financing:
        row["financing"] = {
            "longRate": "-0.0100",
            "shortRate": "0.0200",
            "financingDaysOfWeek": [{"dayOfWeek": "WEDNESDAY", "daysCharged": 3}],
        }
    return row


def _document(*, financing: bool = False) -> dict:
    return {"instruments": [_row(name, financing=financing) for name in INSTRUMENTS], "lastTransactionID": "999"}


def test_source_gate_file_is_off_and_r56_evidence_is_untouched() -> None:
    text = (HERE / "live_session_gate.py").read_text(encoding="utf-8")
    assert "REAL_SESSION_SOURCE_ENABLEMENT = False" in text
    assert load("live_session_gate").REAL_SESSION_SOURCE_ENABLEMENT is False
    r56 = R56_GATE.read_text(encoding="utf-8")
    assert "REAL_SESSION_SOURCE_ENABLEMENT = False" in r56
    assert R56_CONSUMED.is_file()
    assert not R56_PERMIT.exists()
    assert not (HERE / "real_activation" / "one_session.permit").exists()


def test_entry_refuses_before_credentials_when_the_gate_is_off(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _block_network(monkeypatch)

    def boom(*_args, **_kwargs):
        raise AssertionError("credential prompt")

    monkeypatch.setattr("builtins.input", boom)
    monkeypatch.setattr("getpass.getpass", boom)
    assert load("real_session_entry").launch([]) == 2
    captured = capsys.readouterr()
    assert "not authorised" in captured.out
    assert ACCOUNT not in captured.out
    assert TOKEN not in captured.out


def test_absent_or_bad_permit_is_spent_once_and_does_not_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    activation = load("one_session_activation")
    gate = load("live_session_gate")
    with pytest.raises(activation.ActivationRejected) as absent:
        activation.consume(tmp_path / "missing")
    assert absent.value.code == "ACTIVATION_ABSENT"
    forged = tmp_path / "forged"
    forged.mkdir()
    (forged / "one_session.permit").write_text('{"schema":"forged"}', encoding="utf-8")
    with pytest.raises(activation.ActivationRejected) as rejected:
        activation.consume(forged)
    assert rejected.value.code == "ACTIVATION_REJECTED"
    assert (forged / "one_session.consumed").is_file()
    assert not (forged / "one_session.permit").exists()
    with pytest.raises(activation.ActivationRejected) as again:
        activation.consume(forged)
    assert again.value.code == "ACTIVATION_CONSUMED"
    valid = tmp_path / "valid"
    valid.mkdir()
    (valid / "one_session.permit").write_text(json.dumps(activation.expected_binding()), encoding="utf-8")
    activation.consume(valid)
    with pytest.raises(activation.ActivationRejected) as spent:
        activation.consume(valid)
    assert spent.value.code == "ACTIVATION_CONSUMED"
    prompted = {"count": 0}

    def boom(*_args, **_kwargs):
        prompted["count"] += 1
        raise AssertionError("credential prompt")

    monkeypatch.setattr(activation, "production_directory", lambda: tmp_path / "empty")
    monkeypatch.setattr("builtins.input", boom)
    monkeypatch.setattr("getpass.getpass", boom)
    gate.REAL_SESSION_SOURCE_ENABLEMENT = True
    try:
        with pytest.raises(gate.GateRejected) as missing:
            load("diagnostic_supervisor").run_real_session(reader=lambda _screen: gate.ONE_SESSION_PHRASE)
        assert missing.value.code == "ACTIVATION_ABSENT"
    finally:
        gate.REAL_SESSION_SOURCE_ENABLEMENT = False
    assert prompted["count"] == 0
    assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
    with pytest.raises(gate.GateRejected):
        activation.prepare()
    assert not (HERE / "real_activation" / "one_session.permit").exists()


def test_transport_accepts_only_the_one_get(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_network(monkeypatch)
    transport = load("restricted_live_transport")
    gate = load("live_session_gate")
    prepared = transport.build_prepared(ACCOUNT)
    transport.validate_outbound(prepared)
    assert transport.request_target(prepared).endswith("/instruments?instruments=" + transport.INSTRUMENTS)
    prepared.method = "POST"
    with pytest.raises(transport.TransportRejected) as method:
        transport.validate_outbound(prepared)
    assert method.value.code == "METHOD_REJECTED"
    prepared.method = "GET"
    prepared.host = "example.com"
    with pytest.raises(transport.TransportRejected) as host:
        transport.validate_outbound(prepared)
    assert host.value.code == "HOST_REJECTED"
    prepared.host = transport.HOST
    prepared.path = "/v3/accounts/" + ACCOUNT + "/summary"
    with pytest.raises(transport.TransportRejected) as endpoint:
        transport.validate_outbound(prepared)
    assert endpoint.value.code == "ENDPOINT_REJECTED"
    prepared.path = "/v3/accounts/" + ACCOUNT + "/instruments"
    prepared.query = {"instruments": "GBP_USD,EUR_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF"}
    with pytest.raises(transport.TransportRejected) as query:
        transport.validate_outbound(prepared)
    assert query.value.code == "QUERY_REJECTED"
    prepared.query = {"instruments": transport.INSTRUMENTS, "accountIds": ACCOUNT}
    with pytest.raises(transport.TransportRejected):
        transport.validate_outbound(prepared)
    prepared.query = {"instruments": transport.INSTRUMENTS}
    prepared.retries = 1
    with pytest.raises(transport.TransportRejected) as retry:
        transport.validate_outbound(prepared)
    assert retry.value.code == "RETRY_REJECTED"
    prepared.retries = 0
    prepared.redirects = True
    with pytest.raises(transport.TransportRejected) as redirect_flag:
        transport.validate_outbound(prepared)
    assert redirect_flag.value.code == "REDIRECT_REJECTED"
    session = "r59-" + "ab" * 16
    connection = transport.HarnessConnection(_document(), status_code=302)
    exchange = transport.LiveExchange(connection)
    grant = gate.bind_harness_grant(session, "instruments")
    client = transport.RestrictedLiveTransport(exchange, grant, session)
    with pytest.raises(transport.TransportRejected) as redirected:
        client.get_instruments(ACCOUNT, authorization_header="Bearer " + TOKEN, deadline_at=10**12)
    assert redirected.value.code == "REDIRECT_REJECTED"
    assert connection.calls == []
    with pytest.raises(transport.TransportRejected) as second:
        client.get_instruments(ACCOUNT, authorization_header="Bearer " + TOKEN, deadline_at=10**12)
    assert second.value.code == "REQUEST_LIMIT"

    def opened(*_args, **_kwargs):
        raise AssertionError("live socket")

    monkeypatch.setattr("http.client.HTTPSConnection", opened)
    live = transport.LiveExchange(None)
    with pytest.raises(transport.TransportRejected) as unapproved:
        live.exchange(transport.build_prepared(ACCOUNT), "Bearer " + TOKEN, None, deadline_at=10**12)
    assert unapproved.value.code == "GRANT_REJECTED"
    late = transport.LiveExchange(None)
    with pytest.raises(transport.TransportRejected) as expired:
        late.exchange(transport.build_prepared(ACCOUNT), "Bearer " + TOKEN, None, deadline_at=0)
    assert expired.value.code == "DEADLINE_REJECTED"


def test_metadata_statuses_preserve_precision_and_reject_strangers() -> None:
    extract = load("metadata_extract")
    rows = extract.extract(_document())
    eur = rows[0]
    assert eur["marginRate"] == {"status": "RETURNED", "value": "0.03330000"}
    assert eur["financing"]["longRate"] == {"status": "MISSING"}
    assert eur["financing"]["shortRate"] == {"status": "MISSING"}
    assert eur["financing"]["financingDaysOfWeek"] == {"status": "MISSING"}
    assert "0" != eur["financing"]["longRate"].get("value", "absent")
    assert eur["commission"] == {"status": "MISSING"}
    financed = extract.extract(_document(financing=True))[1]
    assert financed["financing"]["longRate"]["value"] == "-0.0100"
    assert financed["financing"]["financingDaysOfWeek"]["value"] == [{"dayOfWeek": "WEDNESDAY", "daysCharged": 3}]
    stranger = _document()
    stranger["instruments"].append({"name": "GBP_JPY", "type": "CURRENCY"})
    with pytest.raises(extract.MetadataRejected) as unexpected:
        extract.extract(stranger)
    assert unexpected.value.code == "UNEXPECTED_INSTRUMENT"
    duplicate = _document()
    duplicate["instruments"].append(dict(duplicate["instruments"][0]))
    with pytest.raises(extract.MetadataRejected) as dup:
        extract.extract(duplicate)
    assert dup.value.code == "DUPLICATE_INSTRUMENT"


def test_harness_session_keeps_secrets_and_raw_bodies_out_of_the_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    record = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        log_dir=tmp_path,
        request_deadline=5,
        session_deadline=15,
    )
    text = (tmp_path / (record["session_id"] + ".json")).read_text(encoding="utf-8")
    assert ACCOUNT not in text
    assert TOKEN not in text
    assert MARKER not in text
    assert "Bearer" not in text
    assert record["raw_response_persisted"] is False
    assert record["account_id_logged"] is False
    assert record["metadata_proves_spread_betting_account"] is False
    assert record["spread_betting_classification"] == "NOT_VERIFIED"
    assert record["network_permitted"] is False
    assert record["instruments"][0]["marginRate"]["value"] == "0.03330000"
    assert record["instruments"][0]["financing"]["longRate"]["status"] == "MISSING"
    assert record["request"]["query"]["instruments"] == gate.INSTRUMENTS
    assert record["children_started"] == 1
    assert record["child_alive"] is False
    assert record["record_persisted"] is True
    assert record["error_code"] == "NONE"


def test_timeout_and_spawn_fault_reap_the_child(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    stalled = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        stall="hang",
        request_deadline=2,
        session_deadline=15,
        log_dir=tmp_path / "stall",
    )
    assert stalled["error_code"] == "CHILD_TERMINATED"
    assert stalled["child_alive"] is False
    faulted = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        fault_at="after_spawn",
        log_dir=tmp_path / "fault",
    )
    assert faulted["error_code"] == "SESSION_FAILED"
    assert faulted["child_alive"] is False


def _assert_no_secrets(text: str) -> None:
    assert ACCOUNT not in text
    assert TOKEN not in text
    assert MARKER not in text
    assert "UNIQUE_FS_FAIL" not in text
    assert "Bearer" not in text


def test_persistence_failures_are_not_successful_diagnostics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    supervisor = load("diagnostic_supervisor")
    session = "r59-" + "ab" * 16

    def fail_write(_fd: int, _data: bytes) -> int:
        raise OSError("UNIQUE_FS_FAIL")

    monkeypatch.setattr(supervisor.os, "write", fail_write)
    with pytest.raises(OSError):
        supervisor._persist_record(tmp_path / "write", session, b"{\"record_persisted\": true}")
    assert list((tmp_path / "write").glob("*")) == []
    monkeypatch.undo()

    def fail_replace(_source: str, _target: str) -> None:
        raise OSError("UNIQUE_FS_FAIL")

    monkeypatch.setattr(supervisor.os, "replace", fail_replace)
    with pytest.raises(OSError):
        supervisor._persist_record(tmp_path / "replace", session, b"{\"record_persisted\": true}")
    assert list((tmp_path / "replace").glob("*")) == []
    monkeypatch.undo()

    def fail_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("UNIQUE_FS_FAIL")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    with pytest.raises(PermissionError):
        supervisor._persist_record(tmp_path / "denied", session, b"{\"record_persisted\": true}")
    assert not (tmp_path / "denied").exists()
    monkeypatch.undo()

    _block_network(monkeypatch)

    def fail_publish(*_args: object, **_kwargs: object) -> None:
        raise OSError("UNIQUE_FS_FAIL")

    monkeypatch.setattr(supervisor, "_persist_record", fail_publish)
    gate = load("live_session_gate")
    record = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        log_dir=tmp_path / "session",
    )
    rendered = json.dumps(record)
    _assert_no_secrets(rendered)
    assert record["error_code"] == "RECORD_PERSISTENCE_FAILED"
    assert record["record_persisted"] is False
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert record["live_network_access"] == "REAL_NETWORK_NOT_COMPLETED"
    session_dir = tmp_path / "session"
    saved = list(session_dir.glob("*.json")) if session_dir.exists() else []
    assert saved == []


def test_overall_deadline_bounds_every_wait(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    started = time.monotonic()
    record = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        stall="delay-then-hang",
        request_deadline=5,
        session_deadline=1.25,
        log_dir=tmp_path,
    )
    elapsed = time.monotonic() - started
    assert elapsed < 3.0
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert record["child_alive"] is False
    assert record["record_persisted"] is True


def test_malformed_exit_and_cleanup_failures_stay_incomplete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    malformed = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        stall="malformed",
        log_dir=tmp_path / "malformed",
    )
    assert malformed["error_code"] == "MALFORMED_CHILD_RESULT"
    assert malformed["session_status"] == "SESSION_INCOMPLETE"
    assert malformed["child_alive"] is False
    exited = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        stall="exit",
        log_dir=tmp_path / "exit",
    )
    assert exited["error_code"] == "CHILD_CRASHED"
    assert exited["session_status"] == "SESSION_INCOMPLETE"
    assert exited["child_alive"] is False
    cleaned = supervisor.run_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        account_id=ACCOUNT,
        token=TOKEN,
        document=_document(),
        fault_at="cleanup",
        log_dir=tmp_path / "cleanup",
    )
    assert cleaned["error_code"] == "CHILD_CLEANUP_FAILED"
    assert cleaned["session_status"] == "SESSION_INCOMPLETE"
    assert cleaned["child_alive"] is False
    assert cleaned["record_persisted"] is True


class _IpcStream:
    def __init__(self, line: bytes) -> None:
        self.closed = False
        self._line = line
        self._read = False

    def readline(self) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._line

    def read(self) -> bytes:
        return b""

    def close(self) -> None:
        self.closed = True


class _IpcStdin:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.closed = False
        self.calls = 0
        self.release = threading.Event()

    def write(self, data: bytes) -> int:
        self.calls += 1
        if self.mode == "broken" or (self.mode == "broken-ack" and self.calls >= 2):
            raise BrokenPipeError("UNIQUE_IPC_FRAME")
        if self.mode == "cumulative" and self.calls == 1:
            self.release.wait(0.4)
            return len(data)
        blocked = self.mode == "block-frame" or (
            self.mode in {"block-ack", "cumulative"} and self.calls >= 2
        )
        if blocked:
            self.release.wait(8)
            if self.closed:
                raise BrokenPipeError("UNIQUE_IPC_FRAME")
        return len(data)

    def flush(self) -> None:
        if self.closed:
            raise BrokenPipeError("UNIQUE_IPC_FRAME")

    def close(self) -> None:
        self.closed = True
        self.release.set()


class _IpcProc:
    def __init__(self, mode: str, line: bytes, exited: bool) -> None:
        self.stdin = _IpcStdin(mode)
        self.stdout = _IpcStream(line)
        self.stderr = _IpcStream(b"")
        self.returncode = 0 if exited else None
        self.mode = mode

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.returncode = 1
        self.stdin.close()

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is not None:
            return self.returncode
        if self.mode == "early-hang":
            time.sleep(0 if timeout is None else timeout)
            if self.returncode is not None:
                return self.returncode
            raise subprocess.TimeoutExpired("r59-worker", timeout or 0)
        self.returncode = 1
        return self.returncode

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
        self.wait(timeout)
        return b"", b""


def test_blocked_ipc_cannot_pass_the_session_deadline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _block_network(monkeypatch)
    supervisor = load("diagnostic_supervisor")
    gate = load("live_session_gate")
    state = {"mode": "block-frame", "line": b"{}\n", "exited": False}
    procs: list[_IpcProc] = []

    def _popen(*_args: object, **_kwargs: object) -> _IpcProc:
        proc = _IpcProc(state["mode"], state["line"], state["exited"])
        procs.append(proc)
        return proc

    monkeypatch.setattr(supervisor.subprocess, "Popen", _popen)
    early = b'{"ready": false, "executable_order": "NOT_PRODUCED", "error_code": "IPC_REJECTED", "step": "instruments"}\n'

    def _run(mode: str, deadline: float, name: str, line: bytes = b"{}\n", exited: bool = False) -> tuple[dict[str, object], float, _IpcProc]:
        state["mode"] = mode
        state["line"] = line
        state["exited"] = exited
        started = time.monotonic()
        record = supervisor.run_harness_session(
            answer=gate.ONE_SESSION_PHRASE,
            account_id=ACCOUNT,
            token=TOKEN,
            document=_document(),
            request_deadline=5,
            session_deadline=deadline,
            log_dir=tmp_path / name,
        )
        proc = procs[-1]
        return record, time.monotonic() - started, proc

    def _quiet(record: dict[str, object], folder: Path, proc: _IpcProc) -> None:
        saved = (folder / (str(record["session_id"]) + ".json")).read_text(encoding="utf-8")
        rendered = json.dumps(record)
        for blob in (rendered, saved):
            assert ACCOUNT not in blob
            assert TOKEN not in blob
            assert "UNIQUE_IPC_FRAME" not in blob
        assert record["session_status"] == "SESSION_INCOMPLETE"
        assert record["child_alive"] is False
        assert record["record_persisted"] is True
        assert proc.poll() is not None

    framed, framed_elapsed, framed_proc = _run("block-frame", 0.55, "frame")
    assert framed_elapsed < 2.0
    assert framed["error_code"] == "SESSION_DEADLINE"
    _quiet(framed, tmp_path / "frame", framed_proc)

    cumulative, cumulative_elapsed, cumulative_proc = _run("cumulative", 1.05, "cumulative")
    assert cumulative_elapsed < 2.0
    assert cumulative["error_code"] == "SESSION_DEADLINE"
    _quiet(cumulative, tmp_path / "cumulative", cumulative_proc)

    acknowledged, acknowledged_elapsed, acknowledged_proc = _run("block-ack", 0.55, "ack")
    assert acknowledged_elapsed < 2.0
    assert acknowledged["error_code"] == "SESSION_DEADLINE"
    _quiet(acknowledged, tmp_path / "ack", acknowledged_proc)

    hung, hung_elapsed, hung_proc = _run("early-hang", 0.7, "early", early)
    assert hung_elapsed < 2.0
    assert hung["error_code"] == "SESSION_DEADLINE"
    _quiet(hung, tmp_path / "early", hung_proc)

    broken, broken_elapsed, broken_proc = _run("broken", 5, "broken")
    assert broken_elapsed < 2.0
    assert broken["error_code"] == "CHILD_CRASHED"
    _quiet(broken, tmp_path / "broken", broken_proc)

    exited, exited_elapsed, exited_proc = _run("broken-ack", 5, "broken-ack")
    assert exited_elapsed < 2.0
    assert exited["error_code"] == "CHILD_CRASHED"
    _quiet(exited, tmp_path / "broken-ack", exited_proc)

    finished, finished_elapsed, finished_proc = _run("early-ok", 5, "early-ok", early, True)
    assert finished_elapsed < 1.0
    assert finished["error_code"] == "IPC_REJECTED"
    _quiet(finished, tmp_path / "early-ok", finished_proc)


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
    name = "r59_" + stem
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


def test_sources_have_no_order_path_or_production_imports() -> None:
    banned = ("forex_bot", "load_dotenv", "import dotenv", "import requests", "import httpx", "main.py")
    for path in HERE.glob("*.py"):
        if path.name == "test_r59_offline.py":
            continue
        text = path.read_text(encoding="utf-8")
        for item in banned:
            assert item not in text
    transport = load("restricted_live_transport")
    assert not hasattr(transport.RestrictedLiveTransport, "create_order")
    assert not hasattr(transport.RestrictedLiveTransport, "get_pricing")
    assert not hasattr(transport.RestrictedLiveTransport, "get_account_summary")
    prepared = transport.build_prepared(ACCOUNT)
    prepared.path = "/v3/accounts/" + ACCOUNT + "/orders"
    with pytest.raises(transport.TransportRejected) as orders:
        transport.validate_outbound(prepared)
    assert orders.value.code == "ENDPOINT_REJECTED"
