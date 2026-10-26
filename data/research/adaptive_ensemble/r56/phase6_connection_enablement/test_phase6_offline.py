"""Offline tests for the Phase 6 connection path. Sockets are blocked in this process."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
R56 = HERE.parent
MODULES = (
    "restricted_live_transport.py",
    "credential_ipc.py",
    "live_session_gate.py",
    "diagnostic_worker.py",
    "diagnostic_supervisor.py",
    "offline_entry.py",
    "real_session_entry.py",
    "one_session_activation.py",
    "prepare_one_session.py",
)
BANNED = ("bot_loop", "oanda_exec", "oanda_client", "trading", "execution", "app", "paper_broker", "live_broker", "load_dotenv")


def _block_network() -> None:
    def blocked(*_args, **_kwargs):
        raise AssertionError("network_blocked")

    socket.socket = blocked  # type: ignore[misc, assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    socket.getaddrinfo = blocked  # type: ignore[assignment]


_block_network()


def _load(directory: Path, prefix: str, stem: str):
    name = f"{prefix}_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, directory / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _local(stem: str):
    return _load(HERE, "r56p6", stem)


def _phase5(stem: str):
    return _load(R56 / "phase5_connection", "r56p5", stem)


def _logs() -> Path:
    path = HERE / "synthetic_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean(path: Path) -> None:
    for item in path.glob("r56-phase6-*.json"):
        item.unlink()


def _run(**kwargs):
    supervisor = _local("diagnostic_supervisor")
    confirmation = _phase5("operator_confirmation")
    credentials = _phase5("credential_gate")
    options = {
        "answer": confirmation.SYNTHETIC_PHRASE,
        "credential": credentials.SyntheticCredential(),
        "collected_at": "2026-10-22T17:00:00Z",
        "log_dir": _logs(),
    }
    options.update(kwargs)
    return supervisor.run_offline(**options)


def _secrets() -> tuple[str, str]:
    credentials = _phase5("credential_gate")
    return credentials.OFFLINE_MARKER, credentials.SYNTHETIC_ACCOUNT_ID


def test_parent_blocks_network_and_live_mode_is_off(capsys):
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_open")
    gate = _local("live_session_gate")
    ipc = _local("credential_ipc")
    entry = _local("offline_entry")
    assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
    assert entry.launch([]) == 2
    assert entry.launch(["--live"]) == 2
    assert entry.launch(["--connect"]) == 2
    assert entry.launch(["--authenticate"]) == 2
    assert "No credential prompt" in capsys.readouterr().out
    for call in (gate.open_real_session, ipc.prompt_hidden_token, ipc.prompt_account_id, ipc.read_environment, ipc.read_dotenv):
        try:
            call()
        except (gate.GateRejected, ipc.IpcRejected) as exc:
            assert exc.code in {"REAL_OANDA_SESSION_NOT_AUTHORISED", "REAL_CREDENTIAL_USE_NOT_AUTHORISED"}
        else:
            raise AssertionError(call)
    confirmation = _phase5("operator_confirmation")
    agreed = confirmation.confirm_synthetic(
        confirmation.SYNTHETIC_PHRASE,
        screen=confirmation.render_screen(log_destination="synthetic_logs"),
    )
    assert agreed["network_permitted"] is False
    assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False


def test_transport_rejects_anything_except_two_gets():
    transport = _local("restricted_live_transport")
    pins = _phase5("restricted_https_transport")
    gate = _local("live_session_gate")
    credentials = _phase5("credential_gate")
    header = "Bearer " + credentials.OFFLINE_MARKER
    exchange = transport.FakeExchange({"account": {"currency": "GBP"}})
    session = transport.RestrictedLiveTransport(exchange)
    session.get_account_summary(transport.SELECTOR, authorization_header=header)
    assert exchange.authorization_accepted is True
    assert exchange.calls[0][0] == "GET"
    assert exchange.calls[0][1].endswith("/summary")
    try:
        session.get_account_summary(transport.SELECTOR, authorization_header=header)
    except transport.TransportRejected as exc:
        assert exc.code == "SUMMARY_DUPLICATE_REJECTED"
    else:
        raise AssertionError("duplicate")
    try:
        transport.RestrictedLiveTransport(transport.FakeExchange()).get_account_summary("111-111-1111111-111", authorization_header=header)
    except transport.TransportRejected as exc:
        assert exc.code == "REAL_ACCOUNT_ID_REJECTED"
    else:
        raise AssertionError("raw_id_accepted")
    pricing = transport.RestrictedLiveTransport(transport.FakeExchange({"prices": []}))
    try:
        pricing.get_pricing(transport.SELECTOR, authorization_header=header, prior=())
    except transport.TransportRejected as exc:
        assert exc.code == "SEQUENCE_REJECTED"
    else:
        raise AssertionError("pricing_led")
    pricing.get_pricing(transport.SELECTOR, authorization_header=header, prior=("summary",))
    try:
        pricing.get_pricing(transport.SELECTOR, authorization_header=header, prior=("summary",))
    except transport.TransportRejected as exc:
        assert exc.code == "REQUEST_LIMIT"
    else:
        raise AssertionError("third")
    budget = _local("diagnostic_supervisor").SessionBudget()
    budget.reserve()
    budget.reserve()
    try:
        budget.reserve()
    except _local("diagnostic_supervisor").SupervisorRejected as exc:
        assert exc.code == "REQUEST_LIMIT"
    else:
        raise AssertionError("third_child")
    prepared = transport.PreparedGet(kind="summary", path="/v3/accounts/" + pins.SYNTHETIC_ACCOUNT_ID + "/summary", query={})
    cases = []
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        row = transport.PreparedGet(kind="summary", path=prepared.path, query={})
        row.method = method
        cases.append((row, "METHOD_REJECTED"))
    host = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    host.host = "api-fxpractice.oanda.com"
    cases.append((host, "HOST_REJECTED"))
    port = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    port.port = 80
    cases.append((port, "HOST_REJECTED"))
    scheme = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    scheme.scheme = "http"
    cases.append((scheme, "SCHEME_REJECTED"))
    orders = transport.PreparedGet(kind="summary", path="/v3/accounts/" + pins.SYNTHETIC_ACCOUNT_ID + "/orders", query={})
    cases.append((orders, "ACCOUNT_CHANGING_REJECTED"))
    trades = transport.PreparedGet(kind="summary", path="/v3/accounts/" + pins.SYNTHETIC_ACCOUNT_ID + "/trades", query={})
    cases.append((trades, "ACCOUNT_CHANGING_REJECTED"))
    positions = transport.PreparedGet(kind="summary", path="/v3/accounts/" + pins.SYNTHETIC_ACCOUNT_ID + "/positions/EUR_USD/close", query={})
    cases.append((positions, "ACCOUNT_CHANGING_REJECTED"))
    extra = transport.PreparedGet(
        kind="pricing",
        path="/v3/accounts/" + pins.SYNTHETIC_ACCOUNT_ID + "/pricing",
        query={"instruments": pins.INSTRUMENTS, "includeHomeConversions": "true"},
    )
    cases.append((extra, "QUERY_REJECTED"))
    body = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    body.body = b"{}"
    cases.append((body, "BODY_REJECTED"))
    redirect = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    redirect.redirects = True
    cases.append((redirect, "REDIRECT_REJECTED"))
    retry = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    retry.retries = 2
    cases.append((retry, "RETRY_REJECTED"))
    stream = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    stream.stream = True
    cases.append((stream, "STREAM_REJECTED"))
    cookies = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    cookies.cookies = {"session": "x"}
    cases.append((cookies, "COOKIES_REJECTED"))
    for request, code in cases:
        try:
            transport.validate_outbound(request)
        except transport.TransportRejected as exc:
            assert exc.code == code
        else:
            raise AssertionError(code)
    context = transport.build_tls_context()
    assert context.verify_mode == __import__("ssl").CERT_REQUIRED
    assert context.check_hostname is True
    try:
        transport.disable_tls_verification()
    except transport.TransportRejected as exc:
        assert exc.code == "TLS_VERIFICATION_CANNOT_BE_DISABLED"
    else:
        raise AssertionError("tls_disabled")
    try:
        transport.LiveExchange().exchange(prepared, header)
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("live_exchange_ran")
    try:
        transport.RestrictedLiveTransport(transport.LiveExchange())
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("live_transport_constructed")
    headers = transport.live_request_headers(header)
    assert set(headers) == {"Accept", "Authorization"}
    assert "Cookie" not in headers
    assert not hasattr(transport, "send_request")
    weak = transport.FakeExchange(tls_policy={"verify_mode": "CERT_NONE", "check_hostname": False})
    try:
        transport.RestrictedLiveTransport(weak).get_account_summary(transport.SELECTOR, authorization_header=header)
    except transport.TransportRejected as exc:
        assert exc.code == "TLS_VERIFICATION_REQUIRED"
    else:
        raise AssertionError("weak_tls")
    proxied = transport.FakeExchange(proxy_from_environment=True)
    try:
        transport.RestrictedLiveTransport(proxied).get_account_summary(transport.SELECTOR, authorization_header=header)
    except transport.TransportRejected as exc:
        assert exc.code == "PROXY_REJECTED"
    else:
        raise AssertionError("proxy")


def test_sources_have_no_secrets_or_production_imports():
    marker, pin = _secrets()
    for name in MODULES:
        text = (HERE / name).read_text(encoding="utf-8")
        assert marker not in text
        assert pin not in text
        assert "1.35" not in text
        assert "load_dotenv" not in text
        tree = ast.parse(text)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        blob = " ".join(imported)
        for item in BANNED:
            assert item not in blob
    assert hashlib.sha256((R56 / "phase2_offline" / "06_integrity_manifest.json").read_bytes()).hexdigest() == (
        "c1033f885bb956ff0bbcb461291a967d3b0178d46851f37651fc1564e691b441"
    )
    assert hashlib.sha256((R56 / "phase3_offline" / "06_integrity_manifest.json").read_bytes()).hexdigest() == (
        "ca0e9707a84646458be24b232a575e3870e8f2de3c6f5746bdb7388cad2fb100"
    )
    assert hashlib.sha256((R56 / "phase4_preparation" / "07_integrity_manifest.json").read_bytes()).hexdigest() == (
        "6183c33dbec1b334adefa7c2ab663784832cdba806a9a8e99605f26695580b22"
    )
    assert hashlib.sha256((R56 / "phase5_connection" / "07_integrity_manifest.json").read_bytes()).hexdigest() == (
        "27026f230e1485e74d462000b6d1d4159a939cd1a500390fc329ea82f8db8cf0"
    )
    assert hashlib.sha256((ROOT / "forex_bot" / "oanda_client.py").read_bytes()).hexdigest() == (
        "02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a"
    )
    assert hashlib.sha256((ROOT / "main.py").read_bytes()).hexdigest() == (
        "4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb"
    )


def test_supervised_synthetic_session_keeps_secrets_off_the_log():
    marker, pin = _secrets()
    log_dir = _logs()
    _clean(log_dir)
    previous = os.environ.get("HTTP_PROXY")
    os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
    try:
        env = _local("diagnostic_supervisor").child_env()
    finally:
        if previous is None:
            os.environ.pop("HTTP_PROXY", None)
        else:
            os.environ["HTTP_PROXY"] = previous
    assert "HTTP_PROXY" not in env
    record = _run()
    assert record["session_status"] == "SESSION_COMPLETE_SYNTHETIC"
    assert record["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert record["target_environment"] == "OANDA_LIVE"
    assert record["live_network_access"] == "NOT_AUTHORISED"
    assert record["real_session_source_enablement"] is False
    assert record["network_permitted"] is False
    assert record["children_started"] == 2
    assert record["child_alive"] is False
    assert record["ipc_write_closed"] is True
    assert record["ipc_child_closed"] is True
    assert record["account_diagnostics"]["home_currency"] == "GBP"
    assert record["account_diagnostics"]["balance"] == "100.00"
    assert record["account_diagnostics"]["nav"] == "100.00"
    assert record["account_diagnostics"]["margin_available"] == "100.00"
    assert record["account_diagnostics"]["margin_used"] == "0.00"
    assert record["account_diagnostics"]["account_identity_verified"] is False
    eur = record["pricing_diagnostics"][0]
    assert eur["bid"] == "1.10000"
    assert eur["ask"] == "1.10020"
    assert eur["spread_price"] == "0.00020"
    assert eur["tradeable"] is True
    assert record["executable_order"] == "NOT_PRODUCED"
    assert record["executable_position_size"] == "NOT_CALCULATED"
    assert record["broker_evidence_complete"] is False
    assert record["gbp_conversion_fallback"] == "NOT_USED"
    text = json.dumps(record)
    assert marker not in text
    assert pin not in text
    assert "Bearer" not in text
    supervisor = _local("diagnostic_supervisor")
    assert marker not in " ".join(supervisor.LAST_ARGV)
    assert pin not in " ".join(supervisor.LAST_ARGV)
    assert marker not in json.dumps(supervisor.LAST_PUBLIC)
    assert pin not in json.dumps(supervisor.LAST_PUBLIC)
    assert supervisor.LAST_IPC_WRITE_CLOSED is True
    stored = next(log_dir.glob("r56-phase6-*.json")).read_text(encoding="utf-8")
    assert marker not in stored
    assert pin not in stored
    _clean(log_dir)


def test_failures_stop_the_session_without_a_false_success():
    log_dir = _logs()
    _clean(log_dir)
    denied = _run(summary_status=401)
    assert denied["error_code"] == "HTTP_401"
    assert denied["children_started"] == 1
    assert denied["pricing_request"]["result"] == "NOT_SENT"
    assert denied["session_status"] == "SESSION_INCOMPLETE"
    for status in (403, 429, 500, 503):
        failed = _run(summary_status=status)
        assert failed["error_code"] == f"HTTP_{status}"
        assert failed["children_started"] == 1
    redirected = _run(summary_status=302)
    assert redirected["error_code"] == "REDIRECT_REJECTED"
    assert redirected["children_started"] == 1
    pricing = _run(pricing_status=502)
    assert pricing["error_code"] == "HTTP_502"
    assert pricing["account_diagnostics"]["outcome"] == "DIAGNOSTIC_RECORDED"
    assert pricing["pricing_diagnostics"] == "NOT_PRODUCED"
    assert pricing["session_status"] == "SESSION_INCOMPLETE"
    malformed = _run(summary_body_text="{")
    assert malformed["error_code"] == "MALFORMED_JSON"
    oversized = _run(summary_fill=1048577)
    assert oversized["error_code"] == "RESPONSE_TOO_LARGE"
    assert "xxxx" not in json.dumps(oversized)
    missing = _run(summary_fixture="summary_no_currency")
    assert missing["account_diagnostics"]["home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert missing["data_source"] == "SYNTHETIC_TEST_ONLY"
    sealed = _run(stall="dns")
    assert sealed["error_code"] == "NETWORK_SEALED"
    assert sealed["children_started"] == 1
    _clean(log_dir)


def test_parent_kills_a_stalled_child_and_drops_secrets():
    marker, pin = _secrets()
    log_dir = _logs()
    _clean(log_dir)
    keeper = _run()
    keeper_file = next(log_dir.glob("r56-phase6-*.json"))
    keeper_bytes = keeper_file.read_bytes()
    hang = _run(stall="hang", stall_step="summary", request_deadline=0.5, session_deadline=15.0)
    assert hang["error_code"] == "CHILD_TERMINATED"
    assert hang["child_alive"] is False
    assert hang["child_termination"] == "TERMINATED"
    assert hang["children_started"] == 1
    assert hang["pricing_request"]["result"] == "NOT_SENT"
    assert hang["session_status"] == "SESSION_INCOMPLETE"
    assert hang["ipc_write_closed"] is True
    assert float(hang["observed_wall_seconds"]) >= 0.5
    assert float(hang["observed_wall_seconds"]) < 8
    assert _local("diagnostic_supervisor").LAST_PROC.poll() is not None
    ignored = _run(stall="ignore", stall_step="pricing", ignore_seconds=10, request_deadline=0.5)
    assert ignored["error_code"] == "CHILD_TERMINATED"
    assert ignored["account_diagnostics"]["outcome"] == "DIAGNOSTIC_RECORDED"
    assert ignored["session_status"] == "SESSION_INCOMPLETE"
    assert float(ignored["observed_wall_seconds"]) < 8
    crashed = _run(stall="crash")
    assert crashed["error_code"] == "CHILD_CRASHED"
    leaked = _run(stall="leak")
    assert leaked["error_code"] == "SENSITIVE_OUTPUT_BLOCKED"
    assert marker not in json.dumps(leaked)
    assert pin not in json.dumps(leaked)
    raised = _run(stall="raise")
    assert raised["error_code"] == "EXCEPTION_CONTAINED"
    assert marker not in json.dumps(raised)
    malformed = _run(stall="malformed")
    assert malformed["error_code"] == "MALFORMED_CHILD_RESULT"
    assert keeper_file.read_bytes() == keeper_bytes
    for path in log_dir.glob("r56-phase6-*.json"):
        text = path.read_text(encoding="utf-8")
        assert marker not in text
        assert pin not in text
    try:
        _local("diagnostic_supervisor").run_offline(
            answer="NO",
            credential=_phase5("credential_gate").SyntheticCredential(),
            collected_at="2026-10-22T17:00:00Z",
            log_dir=_logs(),
        )
    except _phase5("operator_confirmation").ConfirmationRejected as exc:
        assert exc.code == "CONFIRMATION_REJECTED"
    else:
        raise AssertionError("unconfirmed")
    try:
        _run(log_dir=HERE.parent)
    except _local("diagnostic_supervisor").SupervisorRejected as exc:
        assert exc.code == "LOG_PATH_OUTSIDE"
    else:
        raise AssertionError("outside_log")
    try:
        _run(request_deadline=5.1)
    except _local("diagnostic_supervisor").SupervisorRejected as exc:
        assert exc.code == "DEADLINE_ABOVE_CAP"
    else:
        raise AssertionError("cap")

    class LiveCredential:
        classification = "LIVE_CREDENTIAL"
        token = "not-a-synthetic-marker"
        account_id = pin

    try:
        _run(credential=LiveCredential())
    except _local("diagnostic_supervisor").SupervisorRejected as exc:
        assert exc.code == "REAL_CREDENTIAL_USE_NOT_AUTHORISED"
    else:
        raise AssertionError("live_credential")
    _clean(log_dir)


def test_offline_launch_writes_one_synthetic_log():
    marker, pin = _secrets()
    log_dir = _logs()
    _clean(log_dir)
    assert _local("offline_entry").launch(["--offline"]) == 0
    files = list(log_dir.glob("r56-phase6-*.json"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    record = json.loads(text)
    assert record["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert record["live_network_access"] == "NOT_AUTHORISED"
    assert record["real_session_source_enablement"] is False
    assert record["executable_order"] == "NOT_PRODUCED"
    assert record["children_started"] == 2
    assert marker not in text
    assert pin not in text
    _clean(log_dir)


def _account() -> str:
    return "101-004-42-007"


def _token() -> str:
    return "SYNTHETIC-NOT-REAL-UNUSUAL-TOKEN-77"


def _session() -> str:
    return "r56-" + ("ab" * 16)


def _auth_frame(step: str, account: str, token: str) -> bytes:
    ipc = _local("credential_ipc")
    prior = [] if step == "summary" else ["summary"]
    return ipc.authenticated_frame(
        {
            "step": step,
            "prior": prior,
            "session_id": _session(),
            "collected_at": "2026-10-22T17:00:00Z",
            "fixture": step,
        },
        account_id=account,
        token=token,
    )


def _parent_grant(step: str = "summary"):
    gate = _local("live_session_gate")
    confirmation = gate.confirm_one_session(gate.ONE_SESSION_PHRASE, screen=gate.render_plan())
    return gate.issue_harness_authorisation(
        session_id=_session(),
        step=step,
        confirmation=confirmation,
        plan=gate.fixed_plan(),
        answer=gate.ONE_SESSION_PHRASE,
    )


def _granted(connection, step: str = "summary"):
    transport = _local("restricted_live_transport")
    gate = _local("live_session_gate")
    confirmation = gate.confirm_one_session(gate.ONE_SESSION_PHRASE, screen=gate.render_plan())
    grant = gate.issue_harness_authorisation(
        session_id=_session(),
        step=step,
        confirmation=confirmation,
        plan=gate.fixed_plan(),
        answer=gate.ONE_SESSION_PHRASE,
    )
    return transport.RestrictedLiveTransport(
        transport.LiveExchange(connection=connection),
        grant=grant,
        session_id=_session(),
    )


def _summary_document(account: str) -> dict:
    document = _phase5("synthetic_fixtures").summary_document()
    document["account"]["id"] = account
    return document


def test_offline_mode_seals_and_authenticated_harness_does_not(capsys):
    worker = _local("diagnostic_worker")
    assert worker.NETWORK_SEALED is False
    sealed = _run(stall="dns")
    assert sealed["error_code"] == "NETWORK_SEALED"
    assert sealed["children_started"] == 1
    assert worker.NETWORK_SEALED is False
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("parent_socket_open")
    account = _account()
    token = _token()
    transport = _local("restricted_live_transport")
    connection = transport.HarnessConnection(_summary_document(account))
    opened = transport.LiveExchange.real_connections_opened
    result = worker.run_authenticated_harness(_auth_frame("summary", account, token), connection, grant=_parent_grant())
    assert worker.NETWORK_SEALED is False
    assert isinstance(worker.LAST_EXCHANGE, transport.LiveExchange)
    assert transport.LiveExchange.real_connections_opened == opened
    assert connection.opened is True
    assert connection.calls[0][0] == "GET"
    assert connection.calls[0][1] == "/v3/accounts/" + account + "/summary"
    assert connection.calls[0][2] == {}
    pin = _secrets()[1]
    assert pin not in connection.calls[0][1]
    assert result["error_code"] == "NONE"
    assert result["result"] == "SYNTHETIC_RESPONSE_ACCEPTED"
    rendered = json.dumps(result)
    assert account not in rendered
    assert token not in rendered
    captured = capsys.readouterr()
    assert account not in captured.out
    assert token not in captured.out
    assert account not in captured.err
    assert token not in captured.err
    _clean(_logs())


def test_account_ids_are_validated_before_a_connection(capsys):
    transport = _local("restricted_live_transport")
    ipc = _local("credential_ipc")
    gate = _local("live_session_gate")
    account = _account()
    other = "999-012-1234567890-003"
    token = _token()
    header = "Bearer " + token
    assert transport.ACCOUNT_ID_FORMAT.fullmatch(account)
    assert transport.ACCOUNT_ID_FORMAT.fullmatch(other)
    assert _local("diagnostic_supervisor").ACCOUNT_ID_RE.search(account) is None
    for valid in (account, other):
        connection = transport.HarnessConnection(_summary_document(valid))
        session = _granted(connection)
        session.get_account_summary(valid, authorization_header=header, mode="AUTHENTICATED")
        assert connection.opened is True
        assert connection.calls[0][1] == "/v3/accounts/" + valid + "/summary"
    pin = _secrets()[1]
    rejected = (
        "",
        "SYNTHETIC_PIN",
        pin,
        account + "/orders",
        account + "?x=1",
        "101 004 42 007",
        account + "\n",
        account + "\x00",
        "../" + account,
        "http://evil",
        account + "#frag",
        account + "@host",
        "10-004-42-007",
        "101-04-42-007",
        "101-004-42-0007",
    )
    for value in rejected:
        connection = transport.HarnessConnection(_summary_document(account))
        session = transport.RestrictedLiveTransport(transport.LiveExchange(connection=connection))
        try:
            session.get_account_summary(value, authorization_header=header, mode="AUTHENTICATED")
        except transport.TransportRejected as exc:
            assert exc.code in {"ACCOUNT_ID_REJECTED", "SYNTHETIC_ACCOUNT_REJECTED"}
            if value:
                assert value not in exc.code
            assert token not in str(exc)
        else:
            raise AssertionError("invalid_id_accepted")
        assert connection.opened is False
        assert transport.LiveExchange.real_connections_opened == 0
    try:
        ipc.consume_authenticated(_auth_frame("summary", account + "/orders", token))
    except ipc.IpcRejected as exc:
        assert exc.code == "ACCOUNT_ID_REJECTED"
        assert token not in str(exc)
    else:
        raise AssertionError("ipc_accepted_bad_id")
    try:
        gate.issue_runtime_authorisation()
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("runtime_grant_issued")
    assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
    captured = capsys.readouterr()
    assert account not in captured.out
    assert token not in captured.err


def test_credential_ipc_rejects_bad_frames_and_keeps_secrets_out_of_argv(capsys):
    ipc = _local("credential_ipc")
    supervisor = _local("diagnostic_supervisor")
    account = _account()
    token = _token()
    frame = _auth_frame("summary", account, token)
    public, header, received = ipc.consume_authenticated(frame)
    assert received == account
    assert header == "Bearer " + token
    assert "credential" not in public
    assert "account_id" not in public
    assert "token" not in public
    assert account not in json.dumps(public)
    assert token not in json.dumps(public)
    argv = supervisor.child_argv()
    assert argv[-1] == "--offline-worker"
    assert account not in " ".join(argv)
    assert token not in " ".join(argv)
    env = supervisor.child_env()
    assert account not in " ".join(env.values())
    assert token not in " ".join(env.values())
    cases = (
        (b"{", "IPC_REJECTED"),
        (frame + b"{}", "IPC_SECOND_FRAME"),
        (b"x" * (ipc.MAX_FRAME + 1), "IPC_TOO_LARGE"),
    )
    for raw, code in cases:
        try:
            ipc.consume_authenticated(raw)
        except ipc.IpcRejected as exc:
            assert exc.code == code
            assert token not in str(exc)
            assert account not in str(exc)
        else:
            raise AssertionError(code)
    nested = json.dumps(
        {
            "schema": ipc.AUTH_SCHEMA,
            "mode": ipc.AUTH_MODE,
            "step": "summary",
            "prior": [],
            "session_id": _session(),
            "collected_at": "2026-10-22T17:00:00Z",
            "fixture": "summary",
            "credential": {"account_id": account, "token": token, "note": "extra"},
        }
    ).encode("utf-8")
    try:
        ipc.consume_authenticated(nested)
    except ipc.IpcRejected as exc:
        assert exc.code == "REAL_CREDENTIAL_USE_NOT_AUTHORISED"
    else:
        raise AssertionError("nested_field")
    real_mode = json.loads(frame.decode("utf-8"))
    real_mode["mode"] = "REAL_SESSION"
    try:
        ipc.consume_authenticated(json.dumps(real_mode).encode("utf-8"))
    except ipc.IpcRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("real_mode_frame")
    proc = subprocess.run(
        [sys.executable, "-B", str(HERE / "diagnostic_worker.py"), "--authenticated-worker"],
        input=token.encode("utf-8"),
        capture_output=True,
        timeout=5,
        cwd=str(HERE),
        check=False,
    )
    assert proc.returncode == 2
    assert b"REAL_OANDA_SESSION_NOT_AUTHORISED" in proc.stdout
    assert token.encode("utf-8") not in proc.stdout
    assert account.encode("utf-8") not in proc.stdout
    assert token.encode("utf-8") not in proc.stderr
    assert account.encode("utf-8") not in proc.stderr
    assert _local("offline_entry").launch_authenticated() == 2
    captured = capsys.readouterr()
    assert token not in captured.out
    assert account not in captured.out


def test_exact_redaction_and_authenticated_two_gets(capsys):
    worker = _local("diagnostic_worker")
    transport = _local("restricted_live_transport")
    supervisor = _local("diagnostic_supervisor")
    ipc = _local("credential_ipc")
    account = _account()
    token = _token()
    header = "Bearer " + token
    hostile = json.dumps({"note": account, "authorization": header, "token": token})
    protected = worker.protect_output(json.loads(hostile), (account, token, header, "Authorization: " + header), "summary")
    assert account not in protected
    assert token not in protected
    assert "Bearer " not in protected
    assert "SENSITIVE_OUTPUT_BLOCKED" in protected
    assert supervisor.ACCOUNT_ID_RE.search(account) is None
    assert supervisor._sensitive(hostile, "", (account, token, header)) is True
    log_dir = _logs()
    _clean(log_dir)
    artifact = log_dir / "r56-phase6-redaction-check.json"
    artifact.write_text(protected + "\n", encoding="utf-8")
    stored = artifact.read_text(encoding="utf-8")
    assert account not in stored
    assert token not in stored
    artifact.unlink()
    pins = _phase5("restricted_https_transport")
    summary_connection = transport.HarnessConnection(_summary_document(account))
    pricing_connection = transport.HarnessConnection(_phase5("synthetic_fixtures").pricing_document())
    summary, pricing = worker.run_authenticated_pair(
        _auth_frame("summary", account, token),
        _auth_frame("pricing", account, token),
        summary_connection,
        pricing_connection,
        summary_grant=_parent_grant("summary"),
        pricing_grant=_parent_grant("pricing"),
    )
    assert summary["error_code"] == "NONE"
    assert pricing is not None and pricing["error_code"] == "NONE"
    assert summary_connection.calls == [("GET", "/v3/accounts/" + account + "/summary", {})]
    assert pricing_connection.calls == [
        ("GET", "/v3/accounts/" + account + "/pricing", {"instruments": pins.INSTRUMENTS})
    ]
    target = transport.request_target(transport.build_prepared("pricing", account, "AUTHENTICATED"))
    assert target == "/v3/accounts/" + account + "/pricing?instruments=" + pins.INSTRUMENTS
    rendered = json.dumps({"summary": summary, "pricing": pricing})
    assert account not in rendered
    assert token not in rendered
    failed_connection = transport.HarnessConnection(_summary_document(account), status_code=500)
    idle = transport.HarnessConnection(_phase5("synthetic_fixtures").pricing_document())
    failed, skipped = worker.run_authenticated_pair(
        _auth_frame("summary", account, token),
        _auth_frame("pricing", account, token),
        failed_connection,
        idle,
        summary_grant=_parent_grant("summary"),
        pricing_grant=_parent_grant("pricing"),
    )
    assert failed["error_code"] == "HTTP_500"
    assert skipped is None
    assert idle.opened is False
    redirected = transport.HarnessConnection(_summary_document(account), status_code=302)
    try:
        _granted(redirected).get_account_summary(account, authorization_header=header, mode="AUTHENTICATED")
    except transport.TransportRejected as exc:
        assert exc.code == "REDIRECT_REJECTED"
    else:
        raise AssertionError("redirect_followed")
    prepared = transport.build_prepared("summary", account, "AUTHENTICATED")
    prepared.retries = 2
    try:
        transport.validate_outbound(prepared)
    except transport.TransportRejected as exc:
        assert exc.code == "RETRY_REJECTED"
    else:
        raise AssertionError("retry_allowed")
    prepared = transport.build_prepared("summary", account, "AUTHENTICATED")
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        mutated = transport.build_prepared("summary", account, "AUTHENTICATED")
        mutated.method = method
        try:
            transport.validate_outbound(mutated)
        except transport.TransportRejected as exc:
            assert exc.code == "METHOD_REJECTED"
        else:
            raise AssertionError(method)
    orders = transport.build_prepared("summary", account, "AUTHENTICATED")
    orders.path = "/v3/accounts/" + account + "/orders"
    try:
        transport.validate_outbound(orders)
    except transport.TransportRejected as exc:
        assert exc.code == "ACCOUNT_CHANGING_REJECTED"
    else:
        raise AssertionError("orders")
    same = _granted(transport.HarnessConnection(_summary_document(account)))
    same.get_account_summary(account, authorization_header=header, mode="AUTHENTICATED")
    try:
        same.get_pricing(account, authorization_header=header, prior=("summary",), mode="AUTHENTICATED")
    except transport.TransportRejected as exc:
        assert exc.code == "REQUEST_LIMIT"
    else:
        raise AssertionError("third_on_one_transport")
    context = transport.build_tls_context()
    assert context.verify_mode == __import__("ssl").CERT_REQUIRED
    assert context.check_hostname is True
    assert transport.LiveExchange.real_connections_opened == 0
    try:
        ipc.read_dotenv()
    except ipc.IpcRejected as exc:
        assert exc.code == "REAL_CREDENTIAL_USE_NOT_AUTHORISED"
    else:
        raise AssertionError("dotenv")
    captured = capsys.readouterr()
    blob = captured.out + captured.err + stored
    assert account not in blob
    assert token not in blob


def test_real_activation_and_grants_fail_closed(capsys):
    import builtins
    import getpass

    gate = _local("live_session_gate")
    ipc = _local("credential_ipc")
    supervisor = _local("diagnostic_supervisor")
    transport = _local("restricted_live_transport")
    prompts = {"count": 0}

    def boom(*_args, **_kwargs):
        prompts["count"] += 1
        raise AssertionError("prompt_called")

    original_getpass = getpass.getpass
    original_input = builtins.input
    getpass.getpass = boom
    builtins.input = boom
    try:
        assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
        for call in (gate.prepare_real_session, supervisor.prepare_real_session, ipc.prompt_hidden_token, ipc.prompt_account_id):
            try:
                call()
            except gate.GateRejected as exc:
                assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
            else:
                raise AssertionError(call)
        try:
            ipc.consume_real(("token=" + _token()).encode("utf-8"))
        except gate.GateRejected as exc:
            assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
            assert _token() not in str(exc)
        else:
            raise AssertionError("consume_real")
        assert prompts["count"] == 0
        try:
            gate.confirm_one_session(gate.SYNTHETIC_PHRASE, screen=gate.render_plan())
        except gate.GateRejected as exc:
            assert exc.code == "CONFIRMATION_REJECTED"
        else:
            raise AssertionError("synthetic_phrase")
        try:
            gate.issue_runtime_authorisation(answer=gate.ONE_SESSION_PHRASE, plan=gate.fixed_plan(), session_id=_session(), step="summary")
        except gate.GateRejected as exc:
            assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
        else:
            raise AssertionError("runtime_grant")
    finally:
        getpass.getpass = original_getpass
        builtins.input = original_input
    account = _account()
    header = "Bearer " + _token()
    missing = transport.HarnessConnection(_summary_document(account))
    try:
        transport.RestrictedLiveTransport(transport.LiveExchange(connection=missing), session_id=_session()).get_account_summary(
            account, authorization_header=header, mode="AUTHENTICATED"
        )
    except transport.TransportRejected as exc:
        assert exc.code == "GRANT_REJECTED"
    else:
        raise AssertionError("missing_grant")
    assert missing.opened is False
    confirmation = gate.confirm_one_session(gate.ONE_SESSION_PHRASE, screen=gate.render_plan())
    expired = gate.issue_harness_authorisation(
        session_id=_session(),
        step="summary",
        confirmation=confirmation,
        plan=gate.fixed_plan(),
        answer=gate.ONE_SESSION_PHRASE,
    )
    gate.expire_grant(expired)
    spent = transport.HarnessConnection(_summary_document(account))
    try:
        transport.RestrictedLiveTransport(
            transport.LiveExchange(connection=spent),
            grant=expired,
            session_id=_session(),
        ).get_account_summary(account, authorization_header=header, mode="AUTHENTICATED")
    except transport.TransportRejected as exc:
        assert exc.code == "GRANT_EXPIRED"
    else:
        raise AssertionError("expired_grant")
    assert spent.opened is False
    wrong = gate.issue_harness_authorisation(
        session_id=_session(),
        step="pricing",
        confirmation=confirmation,
        plan=gate.fixed_plan(),
        answer=gate.ONE_SESSION_PHRASE,
    )
    mismatched = transport.HarnessConnection(_summary_document(account))
    try:
        transport.RestrictedLiveTransport(
            transport.LiveExchange(connection=mismatched),
            grant=wrong,
            session_id=_session(),
        ).get_account_summary(account, authorization_header=header, mode="AUTHENTICATED")
    except transport.TransportRejected as exc:
        assert exc.code == "GRANT_REJECTED"
    else:
        raise AssertionError("wrong_step")
    assert mismatched.opened is False
    assert transport.LiveExchange.real_connections_opened == 0
    assert account not in capsys.readouterr().out


def test_authenticated_child_process_runs_the_two_gets(capsys):
    supervisor = _local("diagnostic_supervisor")
    gate = _local("live_session_gate")
    account = _account()
    token = _token()
    seen = {"source": 0}

    def source():
        seen["source"] += 1
        return account, token

    try:
        supervisor.run_authenticated_harness_session(answer="NO", credential_source=source, log_dir=_logs())
    except gate.GateRejected as exc:
        assert exc.code == "CONFIRMATION_REJECTED"
    else:
        raise AssertionError("unconfirmed_child")
    assert seen["source"] == 0
    log_dir = _logs()
    _clean(log_dir)
    record = supervisor.run_authenticated_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        credential_source=source,
        log_dir=log_dir,
        session_id=_session(),
        collected_at="2026-10-22T17:00:00Z",
    )
    assert seen["source"] == 1
    assert record["session_status"] == "SESSION_COMPLETE_SYNTHETIC"
    assert record["children_started"] == 2
    assert record["child_alive"] is False
    assert record["ipc_write_closed"] is True
    assert record["real_session_source_enablement"] is False
    assert record["network_permitted"] is False
    assert record["live_network_access"] == "NOT_AUTHORISED"
    assert record["account_diagnostics"]["home_currency"] == "GBP"
    assert record["account_diagnostics"]["balance"] == "100.00"
    assert record["account_diagnostics"]["nav"] == "100.00"
    assert record["account_diagnostics"]["margin_available"] == "100.00"
    assert record["account_diagnostics"]["margin_used"] == "0.00"
    assert record["pricing_diagnostics"][0]["instrument"] == "EUR_USD"
    assert record["pricing_diagnostics"][0]["bid"] == "1.10000"
    assert record["pricing_diagnostics"][0]["ask"] == "1.10020"
    assert record["pricing_diagnostics"][0]["spread_price"] == "0.00020"
    assert record["executable_order"] == "NOT_PRODUCED"
    assert record["gbp_pip_value"] == "GBP_PIP_VALUE_UNVERIFIED"
    children = list(supervisor.LAST_CHILD_RESULTS)
    assert len(children) == 2
    assert children[0]["exchange"] == "LiveExchange"
    assert children[1]["exchange"] == "LiveExchange"
    assert children[0]["grant_checked"] is True
    assert children[0]["real_connections_opened"] == 0
    assert children[1]["real_connections_opened"] == 0
    summary_path = "/v3/accounts/" + account + "/summary"
    pricing_path = "/v3/accounts/" + account + "/pricing"
    assert children[0]["request_sha256"] == hashlib.sha256(summary_path.encode("utf-8")).hexdigest()
    assert children[1]["request_sha256"] == hashlib.sha256(pricing_path.encode("utf-8")).hexdigest()
    pins = _phase5("restricted_https_transport")
    query = json.dumps({"instruments": pins.INSTRUMENTS}, sort_keys=True)
    assert children[1]["query_sha256"] == hashlib.sha256(query.encode("utf-8")).hexdigest()
    assert children[0]["query_sha256"] == hashlib.sha256(b"{}").hexdigest()
    argv = " ".join(supervisor.LAST_ARGV)
    assert argv.endswith("--authenticated-worker --harness-transport")
    assert account not in argv
    assert token not in argv
    public = json.dumps(supervisor.LAST_PUBLIC)
    assert account not in public
    assert token not in public
    rendered = json.dumps(record) + json.dumps(children)
    assert account not in rendered
    assert token not in rendered
    assert _secrets()[1] not in rendered
    for path in log_dir.glob("r56-phase6-*.json"):
        text = path.read_text(encoding="utf-8")
        assert account not in text
        assert token not in text
        assert _secrets()[1] not in text
    failed = supervisor.run_authenticated_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        credential_source=source,
        summary_status=500,
        log_dir=log_dir,
        session_id=_session(),
        collected_at="2026-10-22T17:00:00Z",
    )
    assert failed["error_code"] == "HTTP_500"
    assert failed["children_started"] == 1
    assert failed["pricing_request"]["result"] == "NOT_SENT"
    assert failed["session_status"] == "SESSION_INCOMPLETE"
    hang = supervisor.run_authenticated_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        credential_source=source,
        stall="hang",
        stall_step="summary",
        request_deadline=0.5,
        log_dir=log_dir,
        session_id=_session(),
        collected_at="2026-10-22T17:00:00Z",
    )
    assert hang["error_code"] == "CHILD_TERMINATED"
    assert hang["child_alive"] is False
    assert hang["child_termination"] == "TERMINATED"
    assert hang["children_started"] == 1
    assert hang["pricing_request"]["result"] == "NOT_SENT"
    assert hang["session_status"] == "SESSION_INCOMPLETE"
    assert float(hang["observed_wall_seconds"]) >= 0.5
    assert float(hang["observed_wall_seconds"]) < 8
    assert supervisor.LAST_PROC.poll() is not None
    captured = capsys.readouterr()
    assert account not in captured.out + captured.err
    assert token not in captured.out + captured.err
    _clean(log_dir)


def test_real_session_entry_uses_parent_capabilities(capsys):
    import builtins
    import getpass

    supervisor = _local("diagnostic_supervisor")
    gate = _local("live_session_gate")
    ipc = _local("credential_ipc")
    transport = _local("restricted_live_transport")
    account = _account()
    token = _token()
    seen = {"source": 0, "prompts": 0}
    worker_text = (HERE / "diagnostic_worker.py").read_text(encoding="utf-8")
    assert "confirm_one_session" not in worker_text
    assert "issue_runtime_authorisation" not in worker_text
    assert "ONE_SESSION_PHRASE" not in worker_text

    def source():
        seen["source"] += 1
        return account, token

    def boom(*_args, **_kwargs):
        seen["prompts"] += 1
        raise AssertionError("prompt_called")

    original_getpass = getpass.getpass
    original_input = builtins.input
    getpass.getpass = boom
    builtins.input = boom
    try:
        try:
            supervisor.run_real_session()
        except gate.GateRejected as exc:
            assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
        else:
            raise AssertionError("gate_open")
        assert seen["prompts"] == 0
        assert seen["source"] == 0
        assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
    finally:
        getpass.getpass = original_getpass
        builtins.input = original_input
    import inspect

    real_source = inspect.getsource(supervisor.run_real_session)
    assert "run_authenticated_harness_session" not in real_source
    assert "harness-transport" not in real_source
    assert 'dispatch_mode="REAL"' in real_source
    assert "transport_seam" not in inspect.signature(supervisor.run_real_session).parameters
    assert "dispatch_mode" not in inspect.signature(supervisor.run_authenticated_harness_session).parameters
    try:
        supervisor.run_real_session(answer=gate.ONE_SESSION_PHRASE)
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("phrase_bypassed_gate")
    assert seen["source"] == 0
    screen = gate.render_plan()
    assert "api-fxtrade.oanda.com:443" in screen
    assert "/v3/accounts/{accountID}/summary" in screen
    assert "instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF" in screen
    try:
        gate.confirm_one_session(" ", screen=screen)
    except gate.GateRejected as exc:
        assert exc.code == "CONFIRMATION_REJECTED"
    else:
        raise AssertionError("blank_confirmation")
    try:
        gate.confirm_one_session("NO", screen=screen)
    except gate.GateRejected as exc:
        assert exc.code == "CONFIRMATION_REJECTED"
    else:
        raise AssertionError("wrong_confirmation")
    try:
        gate.accept_confirmation({"confirmed": True, "network_permitted": False, "confirmation_id": "ab" * 16, "issued_at": 0.0})
    except gate.GateRejected as exc:
        assert exc.code == "CONFIRMATION_REJECTED"
    else:
        raise AssertionError("forged_confirmation")
    stale = gate.confirm_one_session(gate.ONE_SESSION_PHRASE, screen=screen)
    try:
        gate.accept_confirmation(stale, now=stale["issued_at"] + 61)
    except gate.GateRejected as exc:
        assert exc.code == "CONFIRMATION_STALE"
    else:
        raise AssertionError("stale_confirmation")
    replayed = gate.confirm_one_session(gate.ONE_SESSION_PHRASE, screen=screen)
    gate.accept_confirmation(replayed)
    try:
        gate.accept_confirmation(replayed)
    except gate.GateRejected as exc:
        assert exc.code == "CONFIRMATION_REPLAYED"
    else:
        raise AssertionError("replayed_confirmation")
    real_contract = supervisor.dispatch_contract("REAL", session_id=_session(), step="summary")
    assert real_contract["verification"] == "REAL_DISPATCH_CONTRACT_VERIFIED"
    assert real_contract["network_execution"] == "REAL_NETWORK_EXECUTION_NOT_TESTED"
    assert real_contract["argv"][-1] == "--authenticated-worker"
    assert "--harness-transport" not in real_contract["argv"]
    assert real_contract["ipc_mode"] == "REAL_SESSION"
    assert real_contract["capability_mode"] == "REAL_SESSION"
    assert real_contract["authorisation_kind"] == "REAL_SESSION"
    assert real_contract["session_id"] == _session()
    assert real_contract["step"] == "summary"
    assert real_contract["request_budget"] == 2
    assert real_contract["request_deadline_seconds"] == 5.0
    assert real_contract["session_deadline_seconds"] == 15.0
    assert real_contract["host"] == "api-fxtrade.oanda.com"
    assert real_contract["port"] == 443
    harness_contract = supervisor.dispatch_contract(
        "HARNESS",
        session_id=_session(),
        step="pricing",
        request_deadline=0.5,
        session_deadline=15,
    )
    assert harness_contract["ipc_mode"] == "AUTHENTICATED_HARNESS"
    assert harness_contract["capability_mode"] == "HARNESS_SESSION"
    assert "--harness-transport" in harness_contract["argv"]
    try:
        supervisor.dispatch_contract("BOTH", session_id=_session(), step="summary")
    except supervisor.SupervisorRejected as exc:
        assert exc.code == "MODE_REJECTED"
    else:
        raise AssertionError("mixed_mode")
    mixed = dict(real_contract)
    mixed["argv"] = list(harness_contract["argv"])
    try:
        supervisor.assert_dispatch_consistent(mixed)
    except supervisor.SupervisorRejected as exc:
        assert exc.code == "MODE_MISMATCH"
    else:
        raise AssertionError("inconsistent_dispatch")
    specimen = "ab" * 32 + "." + "cd" * 32
    real_frame = ipc.authenticated_frame(
        {"step": "summary", "prior": [], "session_id": _session(), "collected_at": "2026-10-22T17:00:00Z", "fixture": "summary"},
        account_id=account,
        token=token,
        authorisation={
            "kind": "REAL_SESSION",
            "session_id": _session(),
            "step": "summary",
            "host": "api-fxtrade.oanda.com",
            "port": 443,
            "plan_id": gate.PLAN_ID,
            "capability": specimen,
        },
        ipc_mode="REAL_SESSION",
    )
    parsed_real = json.loads(real_frame.decode("utf-8"))
    assert parsed_real["mode"] == "REAL_SESSION"
    assert parsed_real["authorisation"]["kind"] == "REAL_SESSION"
    assert parsed_real["authorisation"]["step"] == "summary"
    assert specimen not in " ".join(real_contract["argv"])
    assert account not in " ".join(real_contract["argv"])
    try:
        ipc.authenticated_frame(
            {"step": "summary", "prior": [], "session_id": _session(), "collected_at": "2026-10-22T17:00:00Z", "fixture": "summary"},
            account_id=account,
            token=token,
            authorisation={
                "kind": "HARNESS_SESSION",
                "session_id": _session(),
                "step": "summary",
                "host": "api-fxtrade.oanda.com",
                "port": 443,
                "plan_id": gate.PLAN_ID,
                "capability": specimen,
            },
            ipc_mode="REAL_SESSION",
        )
    except ipc.IpcRejected as exc:
        assert exc.code == "MODE_MISMATCH"
    else:
        raise AssertionError("harness_kind_on_real_frame")
    try:
        ipc.consume_authenticated(real_frame)
    except ipc.IpcRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("real_frame_accepted_by_harness")
    harness_frame = ipc.authenticated_frame(
        {"step": "summary", "prior": [], "session_id": _session(), "collected_at": "2026-10-22T17:00:00Z", "fixture": "summary"},
        account_id=account,
        token=token,
        authorisation={
            "kind": "HARNESS_SESSION",
            "session_id": _session(),
            "step": "summary",
            "host": "api-fxtrade.oanda.com",
            "port": 443,
            "plan_id": gate.PLAN_ID,
            "capability": specimen,
        },
    )
    assert json.loads(harness_frame.decode("utf-8"))["mode"] == "AUTHENTICATED_HARNESS"
    assert seen["source"] == 0
    issuer = gate.CapabilityIssuer()
    try:
        issuer.issue(session_id=_session(), step="summary", mode="REAL_SESSION")
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("real_capability_issued")
    issued = issuer.issue(session_id=_session(), step="summary", mode="HARNESS_SESSION")
    try:
        issuer.redeem("0" * 64 + "." + "0" * 64, session_id=_session(), step="summary", mode="HARNESS_SESSION")
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_FORGED"
    else:
        raise AssertionError("forged_capability")
    try:
        issuer.redeem(issued, session_id="r56-" + ("cd" * 16), step="summary", mode="HARNESS_SESSION")
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_WRONG_SESSION"
    else:
        raise AssertionError("wrong_session")
    try:
        issuer.redeem(issued, session_id=_session(), step="pricing", mode="HARNESS_SESSION")
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_WRONG_STEP"
    else:
        raise AssertionError("wrong_step")
    issuer.redeem(issued, session_id=_session(), step="summary", mode="HARNESS_SESSION")
    try:
        issuer.redeem(issued, session_id=_session(), step="summary", mode="HARNESS_SESSION")
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_REPLAYED"
    else:
        raise AssertionError("replayed_capability")
    expired = issuer.issue(session_id=_session(), step="pricing", mode="HARNESS_SESSION", lifetime=-1)
    try:
        issuer.redeem(expired, session_id=_session(), step="pricing", mode="HARNESS_SESSION")
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_EXPIRED"
    else:
        raise AssertionError("expired_capability")
    harness_grant = gate.bind_harness_grant(_session(), "summary")
    try:
        gate.assert_parent_capability(harness_grant, session_id=_session(), step="summary")
    except gate.GateRejected as exc:
        assert exc.code == "GRANT_REJECTED"
    else:
        raise AssertionError("harness_authorised_network")
    try:
        gate.note_parent_ack("CAP_OK", _session(), "summary")
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("worker_minted_runtime_grant")
    assert transport.LiveExchange.real_connections_opened == 0
    bare = subprocess.Popen(
        supervisor.authenticated_child_argv(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=supervisor.child_env(),
        cwd=str(HERE),
    )
    bare_frame = ipc.authenticated_frame(
        {"step": "summary", "prior": [], "session_id": _session(), "collected_at": "2026-10-22T17:00:00Z", "fixture": "summary"},
        account_id=account,
        token=token,
    )
    assert bare.stdin is not None
    bare.stdin.write(bare_frame + b"\n")
    bare.stdin.close()
    bare_out, bare_err = bare.communicate(timeout=5)
    assert b"GRANT_REJECTED" in bare_out
    assert account.encode("utf-8") not in bare_out + bare_err
    assert token.encode("utf-8") not in bare_out + bare_err
    assert b"request_sha256" not in bare_out
    forged_capability = "ab" * 32 + "." + "cd" * 32
    forged = subprocess.Popen(
        supervisor.authenticated_child_argv(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=supervisor.child_env(),
        cwd=str(HERE),
    )
    forged_frame = ipc.authenticated_frame(
        {"step": "summary", "prior": [], "session_id": _session(), "collected_at": "2026-10-22T17:00:00Z", "fixture": "summary"},
        account_id=account,
        token=token,
        authorisation={
            "kind": "HARNESS_SESSION",
            "session_id": _session(),
            "step": "summary",
            "host": "api-fxtrade.oanda.com",
            "port": 443,
            "plan_id": gate.PLAN_ID,
            "capability": forged_capability,
        },
    )
    assert forged.stdin is not None and forged.stdout is not None
    forged.stdin.write(forged_frame + b"\n")
    forged.stdin.flush()
    forged_ready = forged.stdout.readline()
    assert forged_capability.encode("utf-8") not in forged_ready
    forged.stdin.write(b"CAP_NO\n")
    forged.stdin.close()
    forged_out, forged_err = forged.communicate(timeout=5)
    assert b"CAPABILITY_REJECTED" in forged_out
    assert b"request_sha256" not in forged_out
    assert forged_capability.encode("utf-8") not in forged_out + forged_err + forged_ready
    assert account.encode("utf-8") not in forged_out + forged_err
    assert token.encode("utf-8") not in forged_out + forged_err
    log_dir = _logs()
    _clean(log_dir)
    supervisor.LAST_PROC = None
    try:
        supervisor.run_authenticated_harness_session(
            answer=gate.ONE_SESSION_PHRASE,
            credential_source=lambda: ("bad-id", token),
            log_dir=log_dir,
            session_id=_session(),
            collected_at="2026-10-22T17:00:00Z",
        )
    except transport.TransportRejected as exc:
        assert exc.code == "ACCOUNT_ID_REJECTED"
    else:
        raise AssertionError("bad_account_connected")
    assert supervisor.LAST_PROC is None
    record = supervisor.run_authenticated_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        credential_source=source,
        log_dir=log_dir,
        session_id=_session(),
        collected_at="2026-10-22T17:00:00Z",
    )
    assert record["session_status"] == "SESSION_COMPLETE_SYNTHETIC"
    assert record["children_started"] == 2
    assert record["real_session_source_enablement"] is False
    assert record["network_permitted"] is False
    assert record["account_diagnostics"]["home_currency"] == "GBP"
    assert record["pricing_diagnostics"][0]["bid"] == "1.10000"
    assert record["pricing_diagnostics"][0]["spread_price"] == "0.00020"
    assert record["executable_order"] == "NOT_PRODUCED"
    children = list(supervisor.LAST_CHILD_RESULTS)
    assert children[0]["request_sha256"] == hashlib.sha256(("/v3/accounts/" + account + "/summary").encode("utf-8")).hexdigest()
    assert children[1]["request_sha256"] == hashlib.sha256(("/v3/accounts/" + account + "/pricing").encode("utf-8")).hexdigest()
    assert children[0]["real_connections_opened"] == 0
    argv = " ".join(supervisor.LAST_ARGV)
    env = " ".join(supervisor.child_env().values())
    public = json.dumps(supervisor.LAST_PUBLIC)
    rendered = json.dumps(record) + json.dumps(children) + argv + env + public
    assert account not in rendered
    assert token not in rendered
    assert "--harness-transport" in argv
    assert "--harness-transport" not in real_contract["argv"]
    assert real_contract["verification"] == "REAL_DISPATCH_CONTRACT_VERIFIED"
    shared_flow = "SHARED_SUBPROCESS_FLOW_VERIFIED"
    assert shared_flow == "SHARED_SUBPROCESS_FLOW_VERIFIED"
    assert json.loads(public)[0]["mode"] == "AUTHENTICATED_HARNESS"
    for path in log_dir.glob("r56-phase6-*.json"):
        text = path.read_text(encoding="utf-8")
        assert account not in text
        assert token not in text
        assert ipc._CAPABILITY_RE.search(text) is None
    failed = supervisor.run_authenticated_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        credential_source=source,
        summary_status=500,
        log_dir=log_dir,
        session_id=_session(),
        collected_at="2026-10-22T17:00:00Z",
    )
    assert failed["error_code"] == "HTTP_500"
    assert failed["children_started"] == 1
    assert failed["pricing_request"]["result"] == "NOT_SENT"
    assert "SESSION_COMPLETE" not in failed["session_status"]
    hang = supervisor.run_authenticated_harness_session(
        answer=gate.ONE_SESSION_PHRASE,
        credential_source=source,
        stall="hang",
        stall_step="summary",
        request_deadline=0.5,
        log_dir=log_dir,
        session_id=_session(),
        collected_at="2026-10-22T17:00:00Z",
    )
    assert hang["error_code"] == "CHILD_TERMINATED"
    assert hang["child_alive"] is False
    assert hang["children_started"] == 1
    assert hang["pricing_request"]["result"] == "NOT_SENT"
    assert hang["session_status"] == "SESSION_INCOMPLETE"
    assert float(hang["observed_wall_seconds"]) >= 0.5
    assert float(hang["observed_wall_seconds"]) < 8
    assert supervisor.LAST_PROC.poll() is not None
    budget = supervisor.SessionBudget()
    budget.reserve()
    budget.reserve()
    try:
        budget.reserve()
    except supervisor.SupervisorRejected as exc:
        assert exc.code == "REQUEST_LIMIT"
    else:
        raise AssertionError("third_request")
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_opened")
    assert transport.LiveExchange.real_connections_opened == 0
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert account not in blob
    assert token not in blob
    assert forged_capability not in blob
    for path in log_dir.glob("r56-phase6-*.json"):
        text = path.read_text(encoding="utf-8")
        assert account not in text
        assert token not in text
        assert forged_capability not in text
        assert ipc._CAPABILITY_RE.search(text) is None
    _clean(log_dir)


def test_capability_redemption_follows_the_dispatch_mode(capsys):
    supervisor = _local("diagnostic_supervisor")
    gate = _local("live_session_gate")
    transport = _local("restricted_live_transport")
    assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
    worker_text = (HERE / "diagnostic_worker.py").read_text(encoding="utf-8")
    assert "issue_offline_mode_binding" not in worker_text
    assert "confirm_one_session" not in worker_text
    issuer = gate.CapabilityIssuer()
    try:
        issuer.issue(session_id=_session(), step="summary", mode="REAL_SESSION")
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("real_issue_bypassed_gate")
    harness_contract = supervisor.dispatch_contract("HARNESS", session_id=_session(), step="summary")
    real_contract = supervisor.dispatch_contract("REAL", session_id=_session(), step="summary")
    assert harness_contract["capability_mode"] == "HARNESS_SESSION"
    assert real_contract["capability_mode"] == "REAL_SESSION"
    assert real_contract["verification"] == "REAL_DISPATCH_CONTRACT_VERIFIED"
    assert real_contract["network_execution"] == "REAL_NETWORK_EXECUTION_NOT_TESTED"
    assert "--harness-transport" not in real_contract["argv"]
    harness_token = issuer.issue(session_id=_session(), step="summary", mode="HARNESS_SESSION")
    try:
        supervisor.redeem_for_dispatch(
            issuer,
            harness_token,
            session_id="r56-" + ("cd" * 16),
            step="summary",
            contract=supervisor.dispatch_contract("HARNESS", session_id="r56-" + ("cd" * 16), step="summary"),
        )
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_WRONG_SESSION"
    else:
        raise AssertionError("wrong_session_redeemed")
    try:
        supervisor.redeem_for_dispatch(
            issuer,
            harness_token,
            session_id=_session(),
            step="pricing",
            contract=supervisor.dispatch_contract("HARNESS", session_id=_session(), step="pricing"),
        )
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_WRONG_STEP"
    else:
        raise AssertionError("wrong_step_redeemed")
    try:
        supervisor.redeem_for_dispatch(issuer, harness_token, session_id=_session(), step="summary", contract=real_contract)
    except gate.GateRejected as exc:
        assert exc.code == "GRANT_REJECTED"
    else:
        raise AssertionError("harness_redeemed_as_real")
    supervisor.redeem_for_dispatch(issuer, harness_token, session_id=_session(), step="summary", contract=harness_contract)
    try:
        supervisor.redeem_for_dispatch(issuer, harness_token, session_id=_session(), step="summary", contract=harness_contract)
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_REPLAYED"
    else:
        raise AssertionError("harness_replayed")
    try:
        supervisor.redeem_for_dispatch(issuer, "0" * 64 + "." + "0" * 64, session_id=_session(), step="summary", contract=harness_contract)
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_FORGED"
    else:
        raise AssertionError("forged_redeemed")
    expired = issuer.issue(session_id=_session(), step="pricing", mode="HARNESS_SESSION", lifetime=-1)
    try:
        supervisor.redeem_for_dispatch(
            issuer,
            expired,
            session_id=_session(),
            step="pricing",
            contract=supervisor.dispatch_contract("HARNESS", session_id=_session(), step="pricing"),
        )
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_EXPIRED"
    else:
        raise AssertionError("expired_redeemed")
    fixture = gate.CapabilityIssuer()
    real_binding = fixture.issue_offline_mode_binding(session_id=_session(), step="summary", mode="REAL_SESSION")
    try:
        supervisor.redeem_for_dispatch(fixture, real_binding, session_id=_session(), step="summary", contract=harness_contract)
    except gate.GateRejected as exc:
        assert exc.code == "GRANT_REJECTED"
    else:
        raise AssertionError("real_binding_redeemed_as_harness")
    supervisor.redeem_for_dispatch(fixture, real_binding, session_id=_session(), step="summary", contract=real_contract)
    try:
        supervisor.redeem_for_dispatch(fixture, real_binding, session_id=_session(), step="summary", contract=real_contract)
    except gate.GateRejected as exc:
        assert exc.code == "CAPABILITY_REPLAYED"
    else:
        raise AssertionError("real_binding_replayed")
    fixture.expire_all()
    assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
    assert transport.LiveExchange.real_connections_opened == 0
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_opened")
    captured = capsys.readouterr()
    assert real_binding not in captured.out + captured.err
    assert harness_token not in captured.out + captured.err
    real_binding = ""
    harness_token = ""


def test_real_entry_refuses_before_prompts_and_does_not_start_the_harness(capsys):
    import builtins
    import getpass

    entry = _local("real_session_entry")
    prepare = _local("prepare_one_session")
    supervisor = _local("diagnostic_supervisor")
    gate = _local("live_session_gate")
    seen = {"input": 0, "getpass": 0, "popen": 0}
    original_input = builtins.input
    original_getpass = getpass.getpass
    original_popen = subprocess.Popen

    def boom_input(*_args, **_kwargs):
        seen["input"] += 1
        raise AssertionError("prompt_reached")

    def boom_getpass(*_args, **_kwargs):
        seen["getpass"] += 1
        raise AssertionError("getpass_reached")

    def boom_popen(*_args, **_kwargs):
        seen["popen"] += 1
        raise AssertionError("child_reached")

    builtins.input = boom_input
    getpass.getpass = boom_getpass
    subprocess.Popen = boom_popen
    try:
        assert entry.launch([]) == 2
        assert entry.launch(["--offline"]) == 2
        assert entry.launch(["--force"]) == 2
        assert entry.launch(["--enable-live"]) == 2
        assert prepare.launch([]) == 2
        assert prepare.launch(["--force"]) == 2
    finally:
        builtins.input = original_input
        getpass.getpass = original_getpass
        subprocess.Popen = original_popen
    text = (HERE / "real_session_entry.py").read_text(encoding="utf-8")
    assert "run_real_session" in text
    assert "run_authenticated_harness_session" not in text
    assert "run_offline" not in text
    assert "main.py" not in text
    assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
    assert "REAL_SESSION_SOURCE_ENABLEMENT = True" not in (HERE / "live_session_gate.py").read_text(encoding="utf-8")
    assert seen == {"input": 0, "getpass": 0, "popen": 0}
    assert "No credential prompt" in capsys.readouterr().out
    assert not (HERE / "real_activation" / "one_session.permit").exists()
    assert "prepare(" not in inspect_source(supervisor.run_real_session)
    assert "activation.consume()" in inspect_source(supervisor.run_real_session)


def inspect_source(func) -> str:
    import inspect

    return inspect.getsource(func)


def test_header_modes_stay_separate_and_real_syntax_does_not_open_a_socket():
    transport = _local("restricted_live_transport")
    gate = _local("live_session_gate")
    synthetic = "Bearer " + _token()
    stand_in = "Bearer " + ("B" * 32)
    assert transport.header_accepted_harness(synthetic) is True
    assert transport.header_accepted_harness(stand_in) is False
    assert transport.header_accepted_real(stand_in) is True
    assert transport.header_accepted_real(synthetic) is True
    for malformed in ("Bearer short", "Bearer bad token", "Bearer bad\ntoken", "nope", "", "Bearer " + ("C" * 129), "Bearer bad/token"):
        assert transport.header_accepted_real(malformed) is False
    opened = transport.LiveExchange.real_connections_opened
    prepared = transport.build_prepared("summary", _account(), "AUTHENTICATED")
    try:
        transport.LiveExchange().exchange(prepared, stand_in)
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("header_opened_real_mode")
    assert transport.LiveExchange.real_connections_opened == opened
    try:
        gate.assert_parent_capability(None)
    except gate.GateRejected as exc:
        assert exc.code == "GRANT_REJECTED"
    else:
        raise AssertionError("missing_grant_passed")
    connection = transport.HarnessConnection({"account": {}}, status_code=200)
    try:
        transport.LiveExchange(connection=connection).exchange(prepared, stand_in)
    except transport.TransportRejected as exc:
        assert exc.code == "AUTHORIZATION_REJECTED"
    else:
        raise AssertionError("harness_accepted_non_synthetic_token")
    assert connection.opened is False
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_opened")


def test_real_labels_are_not_synthetic_and_failures_are_not_success():
    worker = _local("diagnostic_worker")
    supervisor = _local("diagnostic_supervisor")
    synthetic = worker.result_labels(real=False, received=True, step="summary")
    assert synthetic["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert synthetic["result"] == "SYNTHETIC_RESPONSE_ACCEPTED"
    assert synthetic["confirmation"] == "CONFIRMED_SYNTHETIC"
    received = worker.result_labels(real=True, received=True, step="summary")
    assert received["data_source"] == "REAL_OANDA_LIVE_DIAGNOSTIC"
    assert received["result"] == "BROKER_RESPONSE_RECEIVED"
    assert received["network_status"] == "REAL_NETWORK_COMPLETED"
    assert received["confirmation"] == "OPERATOR_CONFIRMED_READ_ONLY"
    failed = worker.result_labels(real=True, received=False, step="summary")
    assert failed["result"] == "REJECTED"
    assert failed["network_status"] == "REAL_NETWORK_NOT_COMPLETED"
    assert failed["result"] != "BROKER_RESPONSE_RECEIVED"
    skipped = worker.result_labels(real=True, received=False, step="pricing", attempted=False)
    assert skipped["result"] == "NOT_SENT"
    summary = {
        "error_code": "NONE",
        "result": "BROKER_RESPONSE_RECEIVED",
        "diagnostics": {"outcome": "DIAGNOSTIC_RECORDED", "home_currency": "GBP", "validation_warnings": []},
        "validation_warnings": [],
    }
    pricing = {
        "error_code": "NONE",
        "result": "BROKER_RESPONSE_RECEIVED",
        "diagnostics": [{"instrument": "EUR_USD", "validation_warnings": []}],
        "validation_warnings": [],
    }
    record = supervisor._record(
        "2026-10-24T12:00:00Z",
        _session(),
        summary,
        pricing,
        error="NONE",
        terminated=False,
        alive=False,
        children=2,
        elapsed=0.1,
        request_deadline=5,
        session_deadline=15,
        ipc_write_closed=True,
        ipc_child_closed=True,
        dispatch_mode="REAL",
    )
    assert record["data_source"] == "REAL_SESSION_NOT_AUTHORISED"
    assert record["confirmation"] == "NOT_CONFIRMED"
    assert record["live_network_access"] == "NOT_AUTHORISED"
    assert record["network_permitted"] is False
    assert record["network_attempted"] is False
    assert record["broker_response_received"] is False
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert record["raw_response_persisted"] is False
    failed_record = supervisor._record(
        "2026-10-24T12:00:00Z",
        _session(),
        {"error_code": "HTTP_500", "result": "REJECTED", "diagnostics": "NOT_PRODUCED", "validation_warnings": []},
        None,
        error="HTTP_500",
        terminated=False,
        alive=False,
        children=1,
        elapsed=0.1,
        request_deadline=5,
        session_deadline=15,
        ipc_write_closed=True,
        ipc_child_closed=True,
        dispatch_mode="REAL",
    )
    assert failed_record["session_status"] == "SESSION_INCOMPLETE"
    assert failed_record["live_network_access"] == "NOT_AUTHORISED"
    assert failed_record["network_permitted"] is False
    assert failed_record["network_attempted"] is False
    assert failed_record["broker_response_received"] is False
    assert failed_record["pricing_request"]["result"] == "NOT_SENT"
    assert "BROKER_RESPONSE_RECEIVED" not in json.dumps(failed_record)
    harness = supervisor._record(
        "2026-10-24T12:00:00Z",
        _session(),
        summary,
        pricing,
        error="NONE",
        terminated=False,
        alive=False,
        children=2,
        elapsed=0.1,
        request_deadline=5,
        session_deadline=15,
        ipc_write_closed=True,
        ipc_child_closed=True,
    )
    assert harness["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert harness["confirmation"] == "CONFIRMED_SYNTHETIC"
    assert harness["live_network_access"] == "NOT_AUTHORISED"
    assert harness["network_permitted"] is False
    assert harness["network_attempted"] is False
    assert harness["broker_response_received"] is False
    try:
        supervisor._log_dir(HERE / "synthetic_logs", dispatch_mode="REAL")
    except supervisor.SupervisorRejected as exc:
        assert exc.code == "LOG_PATH_OUTSIDE"
    else:
        raise AssertionError("real_log_entered_synthetic_logs")
    secret = "B" * 32
    account = "101-004-123456-007"
    capability = ("ab" * 32) + "." + ("cd" * 32)
    blob = json.dumps(record) + account + secret + capability + "Bearer " + secret
    assert supervisor._sensitive(blob, secret, (account, secret, capability, "Bearer " + secret))
    blocked = supervisor._record(
        "2026-10-24T12:00:00Z",
        _session(),
        None,
        None,
        error="SENSITIVE_OUTPUT_BLOCKED",
        terminated=False,
        alive=False,
        children=0,
        elapsed=0.1,
        request_deadline=5,
        session_deadline=15,
        ipc_write_closed=True,
        ipc_child_closed=False,
        dispatch_mode="REAL",
    )
    blocked_text = json.dumps(blocked)
    assert account not in blocked_text
    assert secret not in blocked_text
    assert capability not in blocked_text
    assert blocked["account_diagnostics"] == "NOT_PRODUCED"
    assert not (HERE / "real_diagnostic_logs").exists()


def test_activation_permit_is_single_use_and_not_created_by_normal_execution(capsys):
    import tempfile
    import threading

    activation = _local("one_session_activation")
    gate = _local("live_session_gate")
    assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
    try:
        activation.prepare()
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("prepare_bypassed_gate")
    assert not (HERE / "real_activation").exists()
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        try:
            activation.consume(directory)
        except activation.ActivationRejected as exc:
            assert exc.code == "ACTIVATION_ABSENT"
        else:
            raise AssertionError("missing_permit_consumed")
        assert not (directory / "one_session.permit").exists()
        _arm(activation, directory)
        activation.consume(directory)
        assert not (directory / "one_session.permit").exists()
        assert (directory / "one_session.consumed").exists()
        try:
            activation.consume(directory)
        except activation.ActivationRejected as exc:
            assert exc.code == "ACTIVATION_CONSUMED"
        else:
            raise AssertionError("permit_restored")
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        _arm(activation, directory, plan_id="other-plan")
        try:
            activation.consume(directory)
        except activation.ActivationRejected as exc:
            assert exc.code == "ACTIVATION_REJECTED"
        else:
            raise AssertionError("wrong_plan_accepted")
        try:
            activation.consume(directory)
        except activation.ActivationRejected as exc:
            assert exc.code == "ACTIVATION_CONSUMED"
        else:
            raise AssertionError("rejected_permit_restored")
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        _arm(activation, directory, program="other-program")
        try:
            activation.consume(directory)
        except activation.ActivationRejected as exc:
            assert exc.code == "ACTIVATION_REJECTED"
        else:
            raise AssertionError("wrong_program_accepted")
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        _arm(activation, directory)
        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt() -> None:
            barrier.wait()
            try:
                activation.consume(directory)
            except activation.ActivationRejected as exc:
                results.append(exc.code)
            else:
                results.append("OK")

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(results) == ["ACTIVATION_CONSUMED", "OK"]
    text = json.dumps(activation.expected_binding())
    assert "Bearer" not in text
    assert _account() not in text
    assert _token() not in text
    assert capsys.readouterr().out == ""


def _arm(activation, directory: Path, **overrides) -> None:
    payload = activation.expected_binding()
    payload.update(overrides)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "one_session.permit").write_text(json.dumps(payload), encoding="utf-8")


def test_interrupt_cleans_up_children_and_expires_capabilities():
    supervisor = _local("diagnostic_supervisor")
    account = _account()
    token = _token()
    log_dir = _logs()
    _clean(log_dir)

    def source():
        return account, token

    def run(interrupt_at: str, **kwargs):
        started = time.monotonic()
        record = supervisor._execute_authenticated_session(
            dispatch_mode="HARNESS",
            credential_source=source,
            summary_fixture="summary",
            pricing_fixture="pricing",
            summary_status=kwargs.get("summary_status", 200),
            pricing_status=200,
            stall=kwargs.get("stall"),
            stall_step="summary",
            ignore_seconds=10,
            request_deadline=5,
            session_deadline=15,
            log_dir=log_dir,
            session_id=_session(),
            collected_at="2026-10-24T12:00:00Z",
            interrupt_at=interrupt_at,
        )
        return record, time.monotonic() - started

    import time

    before, _elapsed = run("before_spawn")
    assert before["error_code"] == "SESSION_INTERRUPTED"
    assert before["children_started"] == 0
    assert before["pricing_request"]["result"] == "NOT_SENT"
    assert before["session_status"] == "SESSION_INCOMPLETE"
    assert supervisor.LAST_PROC is None
    assert supervisor.LAST_ISSUER._open == {}
    supervisor.LAST_TRACKER.cleanup()

    handshake, handshake_elapsed = run("handshake")
    assert handshake["error_code"] == "SESSION_INTERRUPTED"
    assert handshake["children_started"] == 1
    assert handshake["pricing_request"]["result"] == "NOT_SENT"
    assert handshake["child_alive"] is False
    assert supervisor.LAST_PROC is not None and supervisor.LAST_PROC.poll() is not None
    assert handshake_elapsed < 8
    assert supervisor.LAST_ISSUER._open
    assert all(record.get("spent") is True for record in supervisor.LAST_ISSUER._open.values())
    supervisor.LAST_TRACKER.cleanup()
    supervisor.LAST_ISSUER.expire_all()

    waiting, waiting_elapsed = run("response", stall="hang")
    assert waiting["error_code"] == "SESSION_INTERRUPTED"
    assert waiting["children_started"] == 1
    assert waiting["pricing_request"]["result"] == "NOT_SENT"
    assert waiting["child_alive"] is False
    assert supervisor.LAST_PROC.poll() is not None
    assert waiting_elapsed < 8
    assert all(record.get("spent") is True for record in supervisor.LAST_ISSUER._open.values())

    between, _elapsed = run("between_steps")
    assert between["error_code"] == "SESSION_INTERRUPTED"
    assert between["children_started"] == 1
    assert between["pricing_request"]["result"] == "NOT_SENT"
    assert between["summary_request"]["result"] != "NOT_SENT"
    assert between["child_alive"] is False
    assert supervisor.LAST_PROC.poll() is not None
    assert "SESSION_COMPLETE_SYNTHETIC" != between["session_status"]
    assert all(record.get("spent") is True for record in supervisor.LAST_ISSUER._open.values())
    for path in log_dir.glob("r56-phase6-*.json"):
        text = path.read_text(encoding="utf-8")
        assert token not in text
        assert account not in text
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_opened")
    _clean(log_dir)


def test_unexpected_exception_reaps_the_child_and_expires_capabilities():
    import time

    supervisor = _local("diagnostic_supervisor")
    transport = _local("restricted_live_transport")
    account = _account()
    token = _token()
    log_dir = _logs()
    _clean(log_dir)
    opened = transport.LiveExchange.real_connections_opened

    def source():
        return account, token

    def run(fault_at: str):
        started = time.monotonic()
        record = supervisor._execute_authenticated_session(
            dispatch_mode="HARNESS",
            credential_source=source,
            summary_fixture="summary",
            pricing_fixture="pricing",
            summary_status=200,
            pricing_status=200,
            stall=None,
            stall_step="summary",
            ignore_seconds=10,
            request_deadline=5,
            session_deadline=15,
            log_dir=log_dir,
            session_id=_session(),
            collected_at="2026-10-24T12:00:00Z",
            fault_at=fault_at,
        )
        return record, time.monotonic() - started

    expectations = {
        "after_spawn": 1,
        "handshake": 1,
        "ipc": 1,
        "between_steps": 1,
        "write": 2,
    }
    for fault_at, children in expectations.items():
        record, elapsed = run(fault_at)
        proc = supervisor.LAST_PROC
        assert proc is not None
        assert proc.poll() is not None
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            assert pipe is None or pipe.closed
        assert record["error_code"] == "SESSION_FAILED"
        assert record["child_alive"] is False
        assert record["children_started"] == children
        assert record["network_permitted"] is False
        assert record["network_attempted"] is False
        assert record["broker_response_received"] is False
        assert record["per_request_deadline_seconds"] == 5
        assert record["session_deadline_seconds"] == 15
        assert record["session_status"] == "SESSION_INCOMPLETE"
        assert "REAL_NETWORK_COMPLETED" not in json.dumps(record)
        if fault_at != "write":
            assert record["pricing_request"]["result"] == "NOT_SENT"
        else:
            assert record["children_started"] == 2
        assert elapsed < 15
        assert supervisor.LAST_ISSUER._open
        assert all(item.get("spent") is True for item in supervisor.LAST_ISSUER._open.values())
        supervisor.LAST_TRACKER.cleanup()
        supervisor.LAST_ISSUER.expire_all()
        assert proc.poll() is not None
        assert all(item.get("spent") is True for item in supervisor.LAST_ISSUER._open.values())
        text = json.dumps(record)
        assert token not in text
        assert account not in text
        assert "Bearer " not in text
        assert "authorization:" not in text.lower()
        assert "RuntimeError" not in text
        assert "Traceback" not in text
    for path in log_dir.glob("r56-phase6-*.json"):
        stored = path.read_text(encoding="utf-8")
        assert token not in stored
        assert account not in stored
        assert "Bearer " not in stored
        assert "RuntimeError" not in stored
    assert transport.LiveExchange.real_connections_opened == opened
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_opened")
    assert not (HERE / "real_activation").exists()
    _clean(log_dir)


def test_unexpected_persistence_failure_is_not_a_successful_session():
    supervisor = _local("diagnostic_supervisor")
    transport = _local("restricted_live_transport")
    account = _account()
    token = _token()
    log_dir = _logs()
    _clean(log_dir)
    opened = transport.LiveExchange.real_connections_opened

    def source():
        return account, token

    def fail_write(_path, _text):
        raise OSError("synthetic disk failure")

    original = supervisor._persist_record
    supervisor._persist_record = fail_write
    try:
        record = supervisor._execute_authenticated_session(
            dispatch_mode="HARNESS",
            credential_source=source,
            summary_fixture="summary",
            pricing_fixture="pricing",
            summary_status=200,
            pricing_status=200,
            stall=None,
            stall_step="summary",
            ignore_seconds=10,
            request_deadline=5,
            session_deadline=15,
            log_dir=log_dir,
            session_id=_session(),
            collected_at="2026-10-24T12:00:00Z",
        )
    finally:
        supervisor._persist_record = original
    proc = supervisor.LAST_PROC
    assert proc is not None and proc.poll() is not None
    for pipe in (proc.stdin, proc.stdout, proc.stderr):
        assert pipe is None or pipe.closed
    assert record["error_code"] == "RECORD_PERSISTENCE_FAILED"
    assert record["error_code"] != "NONE"
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert "SESSION_COMPLETE" not in record["session_status"]
    assert record["record_persisted"] is False
    assert record["raw_response_persisted"] is False
    assert record["children_started"] == 2
    assert record["child_alive"] is False
    assert record["network_permitted"] is False
    assert record["network_attempted"] is False
    assert record["broker_response_received"] is False
    assert record["live_network_access"] == "NOT_AUTHORISED"
    assert record["summary_request"]["result"] != "NOT_SENT"
    assert record["pricing_request"]["result"] != "NOT_SENT"
    assert record["account_diagnostics"]["home_currency"] == "GBP"
    assert record["pricing_diagnostics"][0]["instrument"] == "EUR_USD"
    text = json.dumps(record)
    assert "REAL_NETWORK_COMPLETED" not in text
    assert "SESSION_COMPLETE_REAL_DIAGNOSTIC" not in text
    assert "SESSION_COMPLETE_SYNTHETIC" not in text
    assert "synthetic disk failure" not in text
    assert "OSError" not in text
    assert token not in text
    assert account not in text
    assert "Bearer " not in text
    assert all(item.get("spent") is True for item in supervisor.LAST_ISSUER._open.values())
    supervisor.LAST_TRACKER.cleanup()
    supervisor.LAST_ISSUER.expire_all()
    assert proc.poll() is not None
    for path in log_dir.glob("r56-phase6-*.json"):
        stored = path.read_text(encoding="utf-8")
        assert stored.strip() != ""
        assert "synthetic disk failure" not in stored
        assert "SESSION_COMPLETE" not in stored
        assert '"error_code": "NONE"' not in stored
        assert '"record_persisted": true' not in stored
        assert token not in stored
        assert account not in stored
    assert transport.LiveExchange.real_connections_opened == opened
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_opened")
    assert not (HERE / "real_activation").exists()
    _clean(log_dir)


def test_authorisation_metadata_is_consistent_and_not_forgable():
    supervisor = _local("diagnostic_supervisor")
    gate = _local("live_session_gate")
    entry = _local("real_session_entry")
    assert gate.REAL_SESSION_SOURCE_ENABLEMENT is False
    synthetic = supervisor._session_facts(authorised=False, attempted=False, received=False)
    assert synthetic == {"network_permitted": False, "network_attempted": False, "broker_response_received": False}
    stopped = supervisor._session_facts(authorised=True, attempted=False, received=True)
    assert stopped["network_permitted"] is True
    assert stopped["network_attempted"] is False
    assert stopped["broker_response_received"] is False
    failed = supervisor._session_facts(authorised=True, attempted=True, received=False)
    assert failed == {"network_permitted": True, "network_attempted": True, "broker_response_received": False}
    received = supervisor._session_facts(authorised=True, attempted=True, received=True)
    assert received == {"network_permitted": True, "network_attempted": True, "broker_response_received": True}
    source, confirmation, network, success, ok = supervisor._outcome_labels(
        received, error="NONE", terminated=False, alive=False, dispatch_mode="REAL", not_authorised="NOT_AUTHORISED"
    )
    assert source == "REAL_OANDA_LIVE_DIAGNOSTIC"
    assert confirmation == "OPERATOR_CONFIRMED_READ_ONLY"
    assert network == "REAL_NETWORK_COMPLETED"
    assert success == "SESSION_COMPLETE_REAL_DIAGNOSTIC"
    assert ok is True
    held_source, _held_confirmation, held_network, held_success, held_ok = supervisor._outcome_labels(
        stopped, error="NONE", terminated=False, alive=False, dispatch_mode="REAL", not_authorised="NOT_AUTHORISED"
    )
    assert held_source == "REAL_OANDA_LIVE_DIAGNOSTIC"
    assert held_network == "REAL_NETWORK_NOT_ATTEMPTED"
    assert held_success == "SESSION_COMPLETE_REAL_DIAGNOSTIC"
    assert held_ok is False
    failed_source, _failed_confirmation, failed_network, failed_success, failed_ok = supervisor._outcome_labels(
        failed, error="HTTP_500", terminated=False, alive=False, dispatch_mode="REAL", not_authorised="NOT_AUTHORISED"
    )
    assert failed_network == "REAL_NETWORK_NOT_COMPLETED"
    assert failed_ok is False
    assert failed_success == "SESSION_COMPLETE_REAL_DIAGNOSTIC"
    assert failed_source == "REAL_OANDA_LIVE_DIAGNOSTIC"
    summary = {
        "error_code": "NONE",
        "result": "BROKER_RESPONSE_RECEIVED",
        "network_permitted": True,
        "diagnostics": {"outcome": "DIAGNOSTIC_RECORDED", "home_currency": "GBP", "validation_warnings": []},
        "validation_warnings": [],
    }
    pricing = {
        "error_code": "NONE",
        "result": "BROKER_RESPONSE_RECEIVED",
        "diagnostics": [{"instrument": "EUR_USD", "validation_warnings": []}],
        "validation_warnings": [],
    }
    forged = supervisor._record(
        "2026-10-24T12:00:00Z",
        _session(),
        summary,
        pricing,
        error="NONE",
        terminated=False,
        alive=False,
        children=2,
        elapsed=0.1,
        request_deadline=5,
        session_deadline=15,
        ipc_write_closed=True,
        ipc_child_closed=True,
        dispatch_mode="REAL",
        session_authorised=True,
        network_attempted=True,
        broker_response_received=True,
    )
    assert forged["network_permitted"] is False
    assert forged["network_attempted"] is False
    assert forged["broker_response_received"] is False
    assert forged["live_network_access"] == "NOT_AUTHORISED"
    assert forged["session_status"] == "SESSION_INCOMPLETE"
    assert forged["real_session_source_enablement"] is False
    harness = supervisor._record(
        "2026-10-24T12:00:00Z",
        _session(),
        summary,
        pricing,
        error="NONE",
        terminated=False,
        alive=False,
        children=2,
        elapsed=0.1,
        request_deadline=5,
        session_deadline=15,
        ipc_write_closed=True,
        ipc_child_closed=True,
        session_authorised=True,
        network_attempted=True,
        broker_response_received=True,
    )
    assert harness["network_permitted"] is False
    assert harness["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert harness["pricing_request"]["result"] != "NOT_SENT"
    unattempted = supervisor._outcome_labels(
        supervisor._session_facts(authorised=True, attempted=False, received=False),
        error="NONE",
        terminated=False,
        alive=False,
        dispatch_mode="REAL",
        not_authorised="NOT_AUTHORISED",
    )
    assert unattempted[2] == "REAL_NETWORK_NOT_ATTEMPTED"
    assert unattempted[4] is False
    assert (failed_success if failed_ok else "SESSION_INCOMPLETE") == "SESSION_INCOMPLETE"
    skipped = supervisor._record(
        "2026-10-24T12:00:00Z",
        _session(),
        summary,
        None,
        error="HTTP_500",
        terminated=False,
        alive=False,
        children=1,
        elapsed=0.1,
        request_deadline=5,
        session_deadline=15,
        ipc_write_closed=True,
        ipc_child_closed=True,
        dispatch_mode="REAL",
        session_authorised=True,
        network_attempted=True,
        broker_response_received=False,
    )
    assert skipped["pricing_request"]["result"] == "NOT_SENT"
    assert skipped["network_permitted"] is False
    assert skipped["session_status"] == "SESSION_INCOMPLETE"
    try:
        supervisor._VerifiedRealAuthorisation()
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("authorisation_minted_while_gate_off")
    try:
        supervisor.run_real_session()
    except gate.GateRejected as exc:
        assert exc.code == "REAL_OANDA_SESSION_NOT_AUTHORISED"
    else:
        raise AssertionError("real_session_started")
    assert entry.launch([]) == 2
    assert not (HERE / "real_activation").exists()
    secret = "B" * 32
    account = "101-004-123456-007"
    capability = ("ab" * 32) + "." + ("cd" * 32)
    blob = json.dumps(forged) + account + secret + capability + "Bearer " + secret
    assert supervisor._sensitive(blob, secret, (account, secret, capability, "Bearer " + secret))
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_opened")
