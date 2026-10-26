"""Offline tests for R.56 phase 5. The parent blocks sockets before imports."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
R56 = HERE.parent
PIN = "001-001-0000000-001"
MODULES = (
    "restricted_https_transport.py",
    "credential_gate.py",
    "operator_confirmation.py",
    "isolated_worker.py",
    "session_supervisor.py",
    "offline_entry.py",
    "synthetic_fixtures.py",
)
FORBIDDEN = {"forex_bot", "oandapyV20", "requests", "httpx", "urllib", "main"}
BANNED_IMPORTS = ("bot_loop", "oanda_exec", "oanda_client", "trading", "execution", "app", "paper_broker", "live_broker")


def _block_network() -> None:
    def blocked(*_args, **_kwargs):
        raise AssertionError("network_blocked")

    socket.socket = blocked  # type: ignore[misc, assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    socket.getaddrinfo = blocked  # type: ignore[assignment]


_block_network()


def _load(stem: str):
    name = f"r56p5_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _logs() -> Path:
    path = HERE / "synthetic_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean(path: Path) -> None:
    for item in path.glob("r56-phase5-*.json"):
        item.unlink()


def _run(**kwargs):
    supervisor = _load("session_supervisor")
    credentials = _load("credential_gate")
    confirmation = _load("operator_confirmation")
    options = {
        "answer": confirmation.SYNTHETIC_PHRASE,
        "credential": credentials.SyntheticCredential(),
        "collected_at": "2026-10-22T15:00:00Z",
        "log_dir": _logs(),
    }
    options.update(kwargs)
    return supervisor.run_offline(**options)


def _job(step: str = "summary", **overrides):
    fixtures = _load("synthetic_fixtures")
    job = {
        "mode": "OFFLINE_TEST",
        "connector": "scripted",
        "confirmed": True,
        "network_permitted": False,
        "credential_classification": "SYNTHETIC_TEST_ONLY",
        "authorization_present": True,
        "step": step,
        "prior": [] if step == "summary" else ["summary"],
        "session_id": "r56-" + ("ab" * 16),
        "collected_at": "2026-10-22T15:00:00Z",
        "document": fixtures.summary_document() if step == "summary" else fixtures.pricing_document(),
        "status": 200,
    }
    job.update(overrides)
    return job


def test_parent_blocks_dns_and_sockets():
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_was_not_blocked")
    try:
        socket.socket()
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("socket_was_not_blocked")


def test_live_flags_and_real_credentials_fail(capsys):
    entry = _load("offline_entry")
    credentials = _load("credential_gate")
    confirmation = _load("operator_confirmation")
    assert entry.launch([]) == 2
    assert entry.launch(["--live"]) == 2
    assert entry.launch(["--connect"]) == 2
    assert entry.launch(["--authenticate"]) == 2
    assert entry.launch(["--offline", "--live"]) == 2
    assert "No credential prompt" in capsys.readouterr().out

    class LiveProvider:
        classification = "LIVE_CREDENTIAL"
        token = "not-synthetic"
        account_id = PIN

    for call in (
        lambda: credentials.accept_offline(LiveProvider()),
        lambda: credentials.accept_offline(credentials.SyntheticCredential(token="live-token")),
        lambda: credentials.accept_offline(credentials.SyntheticCredential(account_id="111-111-1111111-111")),
        credentials.prompt_hidden_token,
        credentials.read_environment,
        credentials.read_dotenv,
        credentials.activate_live,
        confirmation.confirm_live,
    ):
        try:
            call()
        except (credentials.CredentialRejected, confirmation.ConfirmationRejected) as exc:
            assert exc.code in {"REAL_CREDENTIAL_USE_NOT_AUTHORISED", "LIVE_CONFIRMATION_NOT_AUTHORISED"}
        else:
            raise AssertionError("closed_path_returned")
    assert credentials.accept_offline(credentials.SyntheticCredential()) is True


def test_confirmation_screen_does_not_permit_network():
    confirmation = _load("operator_confirmation")
    screen = confirmation.render_screen(log_destination="phase5_connection/synthetic_logs")
    for part in (
        "Environment: OANDA LIVE",
        "Destination: api-fxtrade.oanda.com",
        "exactly two GET requests",
        "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF",
        "No orders or position changes.",
        "trading permissions",
        "production bot must remain stopped",
        "Sanitised log destination:",
        "Per-request deadline: 5 seconds.",
        "Session wall-clock deadline: 15 seconds.",
        "1048576",
    ):
        assert part in screen
    agreed = confirmation.confirm_synthetic(confirmation.SYNTHETIC_PHRASE, screen=screen)
    assert agreed["network_permitted"] is False
    assert agreed["data_source"] == "SYNTHETIC_TEST_ONLY"
    try:
        confirmation.confirm_synthetic("YES", screen=screen)
    except confirmation.ConfirmationRejected as exc:
        assert exc.code == "CONFIRMATION_REJECTED"
    else:
        raise AssertionError("bare_yes_confirmed")


def test_transport_allows_only_two_gets():
    transport = _load("restricted_https_transport")
    fixtures = _load("synthetic_fixtures")
    connector = fixtures.ScriptedConnector(fixtures.summary_document())
    session = transport.RestrictedTransport(connector)
    raw = session.get_account_summary(PIN, authorization_present=True)
    assert json.loads(raw)["account"]["currency"] == "GBP"
    assert connector.calls == ["GET /v3/accounts/" + PIN + "/summary"]
    try:
        session.get_account_summary(PIN, authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "SUMMARY_DUPLICATE_REJECTED"
    else:
        raise AssertionError("duplicate_summary")
    pricing = transport.RestrictedTransport(fixtures.ScriptedConnector(fixtures.pricing_document()))
    try:
        pricing.get_pricing(PIN, authorization_present=True, prior=())
    except transport.TransportRejected as exc:
        assert exc.code == "SEQUENCE_REJECTED"
    else:
        raise AssertionError("pricing_without_summary")
    priced = pricing.get_pricing(PIN, authorization_present=True, prior=("summary",))
    assert len(json.loads(priced)["prices"]) == 6
    try:
        pricing.get_pricing(PIN, authorization_present=True, prior=("summary",))
    except transport.TransportRejected as exc:
        assert exc.code == "REQUEST_LIMIT"
    else:
        raise AssertionError("third_request")
    budget = _load("session_supervisor").SessionBudget()
    budget.reserve()
    budget.reserve()
    try:
        budget.reserve()
    except _load("session_supervisor").SupervisorRejected as exc:
        assert exc.code == "REQUEST_LIMIT"
    else:
        raise AssertionError("third_child")
    assert not hasattr(transport, "send_request")
    assert not hasattr(transport.RestrictedTransport, "send_request")


def test_outbound_rejections_cover_methods_hosts_and_changes():
    transport = _load("restricted_https_transport")
    prepared = transport.PreparedGet(kind="summary", path="/v3/accounts/" + PIN + "/summary", query={})
    cases = []
    mutated = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    mutated.method = "POST"
    cases.append((mutated, "METHOD_REJECTED"))
    for method in ("PUT", "PATCH", "DELETE"):
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
    orders = transport.PreparedGet(kind="summary", path="/v3/accounts/" + PIN + "/orders", query={})
    cases.append((orders, "ACCOUNT_CHANGING_REJECTED"))
    trades = transport.PreparedGet(kind="summary", path="/v3/accounts/" + PIN + "/trades", query={})
    cases.append((trades, "ACCOUNT_CHANGING_REJECTED"))
    positions = transport.PreparedGet(kind="summary", path="/v3/accounts/" + PIN + "/positions/EUR_USD/close", query={})
    cases.append((positions, "ACCOUNT_CHANGING_REJECTED"))
    candles = transport.PreparedGet(kind="summary", path="/v3/instruments/EUR_USD/candles", query={})
    cases.append((candles, "ACCOUNT_CHANGING_REJECTED"))
    url = transport.PreparedGet(kind="summary", path="https://api-fxtrade.oanda.com/v3/accounts/" + PIN + "/summary", query={})
    cases.append((url, "URL_REJECTED"))
    extra = transport.PreparedGet(kind="pricing", path="/v3/accounts/" + PIN + "/pricing", query={"instruments": transport.INSTRUMENTS, "includeHomeConversions": "true"})
    cases.append((extra, "QUERY_REJECTED"))
    short = transport.PreparedGet(kind="pricing", path="/v3/accounts/" + PIN + "/pricing", query={"instruments": "EUR_USD"})
    cases.append((short, "QUERY_REJECTED"))
    body = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    body.body = b"{}"
    cases.append((body, "BODY_REJECTED"))
    redirect = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    redirect.redirects = True
    cases.append((redirect, "REDIRECT_REJECTED"))
    retry = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    retry.retries = 1
    cases.append((retry, "RETRY_REJECTED"))
    stream = transport.PreparedGet(kind="summary", path=prepared.path, query={})
    stream.stream = True
    cases.append((stream, "STREAM_REJECTED"))
    for request, code in cases:
        try:
            transport.validate_outbound(request)
        except transport.TransportRejected as exc:
            assert exc.code == code
        else:
            raise AssertionError(code)
    try:
        transport.RestrictedTransport(_load("synthetic_fixtures").ScriptedConnector()).get_account_summary("111-111-1111111-111", authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "REAL_ACCOUNT_ID_REJECTED"
    else:
        raise AssertionError("real_account_accepted")


def test_tls_cannot_be_disabled_and_live_exchange_is_sealed():
    transport = _load("restricted_https_transport")
    fixtures = _load("synthetic_fixtures")
    context = transport.build_tls_context()
    assert context.verify_mode == __import__("ssl").CERT_REQUIRED
    assert context.check_hostname is True
    try:
        transport.disable_tls_verification(context)
    except transport.TransportRejected as exc:
        assert exc.code == "TLS_VERIFICATION_CANNOT_BE_DISABLED"
    else:
        raise AssertionError("tls_disable_returned")
    try:
        transport.open_live_connection()
    except transport.TransportRejected as exc:
        assert exc.code == "LIVE_NETWORK_NOT_AUTHORISED"
    else:
        raise AssertionError("live_connection_opened")
    weak = fixtures.ScriptedConnector(tls_policy={"verify_mode": "CERT_NONE", "check_hostname": False})
    try:
        transport.RestrictedTransport(weak).get_account_summary(PIN, authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "TLS_VERIFICATION_REQUIRED"
    else:
        raise AssertionError("weak_tls_accepted")
    insecure = fixtures.ScriptedConnector(tls_policy={"verify_mode": "CERT_REQUIRED", "check_hostname": True, "allow_insecure": True})
    try:
        transport.RestrictedTransport(insecure).get_account_summary(PIN, authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "TLS_VERIFICATION_CANNOT_BE_DISABLED"
    else:
        raise AssertionError("insecure_flag_accepted")

    class LiveConnector:
        offline_only = False
        marker = "LIVE"

        def exchange(self, _prepared):
            raise AssertionError("live_exchange_called")

    try:
        transport.RestrictedTransport(LiveConnector())
    except transport.TransportRejected as exc:
        assert exc.code == "LIVE_CONNECTOR_NOT_AUTHORISED"
    else:
        raise AssertionError("live_connector_accepted")


def test_proxy_is_not_inherited_and_worker_seals_dns():
    supervisor = _load("session_supervisor")
    previous = os.environ.get("HTTP_PROXY")
    os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
    try:
        env = supervisor.child_env()
    finally:
        if previous is None:
            os.environ.pop("HTTP_PROXY", None)
        else:
            os.environ["HTTP_PROXY"] = previous
    assert "HTTP_PROXY" not in env
    assert "HTTPS_PROXY" not in env
    argv = " ".join(supervisor.child_argv())
    assert "SYNTHETIC-NOT-REAL" not in argv
    assert PIN not in argv
    worker = _load("isolated_worker")
    sealed = worker.run_job(_job(stall="dns"))
    assert sealed["error_code"] == "NETWORK_SEALED"
    proxied = worker.run_job(_job(proxy_from_environment=True))
    assert proxied["error_code"] == "PROXY_REJECTED"
    secret_job = _job()
    secret_job["token"] = "SYNTHETIC-NOT-REAL"
    assert worker.run_job(secret_job)["error_code"] == "JOB_SECRET_REJECTED"
    contained = worker.run_job(_job(stall="raise"))
    assert contained["error_code"] == "EXCEPTION_CONTAINED"
    assert PIN not in json.dumps(contained)


def test_worker_rejects_bad_responses_without_pricing_followup():
    worker = _load("isolated_worker")
    fixtures = _load("synthetic_fixtures")
    for status in (401, 403, 429, 500, 503):
        failed = worker.run_job(_job(status=status, body_text="Bearer hidden"))
        assert failed["error_code"] == f"HTTP_{status}"
        assert failed["diagnostics"] == "NOT_PRODUCED"
        assert "Bearer" not in json.dumps(failed)
    malformed = worker.run_job(_job(body_text="{"))
    assert malformed["error_code"] == "MALFORMED_JSON"
    oversized = worker.run_job(_job(fill=1048577))
    assert oversized["error_code"] == "RESPONSE_TOO_LARGE"
    assert "xxxx" not in json.dumps(oversized)
    missing = worker.run_job(_job(document=fixtures.summary_document(include_currency=False)))
    assert missing["error_code"] == "NONE"
    assert missing["diagnostics"]["home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert missing["data_source"] == "SYNTHETIC_TEST_ONLY"
    invalid = worker.run_job(_job(step="pricing", document=fixtures.pricing_document(include_bid=False)))
    assert invalid["diagnostics"][0]["bid"] == "NOT_RETURNED"
    assert invalid["diagnostics"][0]["spread_price"] == "NOT_CALCULATED"


def test_no_production_imports_and_prior_hashes():
    for name in MODULES:
        tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        roots = {item.split(".")[0] for item in imported}
        assert not roots & FORBIDDEN
        blob = " ".join(imported)
        for item in BANNED_IMPORTS:
            assert item not in blob
        text = (HERE / name).read_text(encoding="utf-8")
        assert "load_dotenv" not in text
        assert "1.35" not in text
        assert "os.environ.items" not in text
    assert hashlib.sha256((R56 / "phase2_offline" / "06_integrity_manifest.json").read_bytes()).hexdigest() == (
        "c1033f885bb956ff0bbcb461291a967d3b0178d46851f37651fc1564e691b441"
    )
    assert hashlib.sha256((R56 / "phase3_offline" / "06_integrity_manifest.json").read_bytes()).hexdigest() == (
        "ca0e9707a84646458be24b232a575e3870e8f2de3c6f5746bdb7388cad2fb100"
    )
    assert hashlib.sha256((R56 / "phase4_preparation" / "07_integrity_manifest.json").read_bytes()).hexdigest() == (
        "6183c33dbec1b334adefa7c2ab663784832cdba806a9a8e99605f26695580b22"
    )
    assert hashlib.sha256((ROOT / "forex_bot" / "oanda_client.py").read_bytes()).hexdigest() == (
        "02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a"
    )
    assert hashlib.sha256((ROOT / "forex_bot" / "oanda_account_adapter.py").read_bytes()).hexdigest() == (
        "191466d11e1fac41ef1ccd5603046a3df5c4682f761fde651adcf9229bdf83b5"
    )
    assert hashlib.sha256((ROOT / "main.py").read_bytes()).hexdigest() == (
        "4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb"
    )


def test_supervised_session_is_synthetic_and_redacted():
    log_dir = _logs()
    _clean(log_dir)
    record = _run()
    assert record["session_status"] == "SESSION_COMPLETE_SYNTHETIC"
    assert record["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert record["target_environment"] == "OANDA_LIVE"
    assert record["live_network_access"] == "NOT_AUTHORISED"
    assert record["network_permitted"] is False
    assert record["children_started"] == 2
    assert record["child_alive"] is False
    assert record["child_termination"] == "NOT_REQUIRED"
    assert record["process_isolation"] == "CHILD_PROCESS"
    assert record["account_diagnostics"]["home_currency"] == "GBP"
    assert record["account_diagnostics"]["balance"] == "100.00"
    assert record["account_diagnostics"]["nav"] == "100.00"
    assert record["account_diagnostics"]["margin_available"] == "100.00"
    assert record["account_diagnostics"]["margin_used"] == "0.00"
    assert record["account_diagnostics"]["account_identity_verified"] is False
    eur = record["pricing_diagnostics"][0]
    assert eur["instrument"] == "EUR_USD"
    assert eur["bid"] == "1.10000"
    assert eur["ask"] == "1.10020"
    assert eur["spread_price"] == "0.00020"
    assert eur["tradeable"] is True
    assert eur["quote_timestamp"] == "2026-10-21T16:00:00Z"
    assert len(record["pricing_diagnostics"]) == 6
    assert record["broker_evidence_complete"] is False
    assert record["executable_order"] == "NOT_PRODUCED"
    assert record["executable_position_size"] == "NOT_CALCULATED"
    assert record["strategy_profitability"] == "NOT_ESTABLISHED"
    assert record["gbp_conversion_fallback"] == "NOT_USED"
    assert record["home_conversion_request"] == "NOT_REQUESTED"
    assert record["raw_response_persisted"] is False
    for marker in (
        "GBP_PIP_VALUE_UNVERIFIED",
        "STAKE_TO_UNIT_MAPPING_NOT_VERIFIED",
        "FINANCING_NOT_VERIFIED",
        "QUOTE_FRESHNESS_NOT_VERIFIED",
        "HOME_CONVERSION_NOT_VERIFIED",
    ):
        assert marker in record["missing_evidence"]
    text = json.dumps(record)
    assert PIN not in text
    assert "SYNTHETIC-NOT-REAL" not in text
    assert "Bearer" not in text
    assert "synthetic-alias-not-logged" not in text
    assert "lastTransactionID" not in text
    assert "1.35" not in text
    supervisor = _load("session_supervisor")
    dumped = json.dumps(supervisor.LAST_JOBS)
    assert "SYNTHETIC-NOT-REAL" not in dumped
    assert "token" not in supervisor.LAST_JOBS[0]
    assert PIN not in " ".join(supervisor.LAST_ARGV)
    files = list(log_dir.glob("r56-phase5-*.json"))
    assert len(files) == 1
    assert PIN not in files[0].read_text(encoding="utf-8")
    _clean(log_dir)


def test_summary_failure_stops_pricing_and_failures_are_not_success():
    log_dir = _logs()
    _clean(log_dir)
    failed = _run(summary_status=500)
    assert failed["error_code"] == "HTTP_500"
    assert failed["children_started"] == 1
    assert failed["pricing_request"]["result"] == "NOT_SENT"
    assert failed["session_status"] == "SESSION_INCOMPLETE"
    assert "SESSION_COMPLETE_SYNTHETIC" not in json.dumps(failed)
    pricing = _run(pricing_status=502)
    assert pricing["error_code"] == "HTTP_502"
    assert pricing["children_started"] == 2
    assert pricing["account_diagnostics"]["outcome"] == "DIAGNOSTIC_RECORDED"
    assert pricing["pricing_diagnostics"] == "NOT_PRODUCED"
    assert pricing["session_status"] == "SESSION_INCOMPLETE"
    malformed = _run(summary_body_text="{")
    assert malformed["error_code"] == "MALFORMED_JSON"
    assert malformed["children_started"] == 1
    oversized = _run(summary_fill=1048577)
    assert oversized["error_code"] == "RESPONSE_TOO_LARGE"
    assert "xxxx" not in json.dumps(oversized)
    _clean(log_dir)


def test_parent_terminates_hang_ignore_crash_and_leak():
    log_dir = _logs()
    _clean(log_dir)
    keeper = _run()
    keeper_file = next(log_dir.glob("r56-phase5-*.json"))
    keeper_bytes = keeper_file.read_bytes()
    hang = _run(stall="hang", stall_step="summary", request_deadline=0.5, session_deadline=15.0)
    assert hang["error_code"] == "CHILD_TERMINATED"
    assert hang["child_termination"] == "TERMINATED"
    assert hang["child_alive"] is False
    assert hang["children_started"] == 1
    assert hang["session_status"] == "SESSION_INCOMPLETE"
    assert hang["pricing_request"]["result"] == "NOT_SENT"
    assert float(hang["observed_wall_seconds"]) >= 0.5
    assert float(hang["observed_wall_seconds"]) < 8
    assert _load("session_supervisor").LAST_PROC.poll() is not None
    ignored = _run(stall="ignore", stall_step="pricing", ignore_seconds=10, request_deadline=0.5, session_deadline=15.0)
    assert ignored["error_code"] == "CHILD_TERMINATED"
    assert ignored["account_diagnostics"]["outcome"] == "DIAGNOSTIC_RECORDED"
    assert ignored["session_status"] == "SESSION_INCOMPLETE"
    assert float(ignored["observed_wall_seconds"]) < 8
    crashed = _run(stall="crash", stall_step="summary")
    assert crashed["error_code"] == "CHILD_CRASHED"
    assert crashed["session_status"] == "SESSION_INCOMPLETE"
    leaked = _run(stall="leak", stall_step="summary")
    assert leaked["error_code"] == "SENSITIVE_OUTPUT_BLOCKED"
    assert leaked["account_diagnostics"] == "NOT_PRODUCED"
    assert PIN not in json.dumps(leaked)
    malformed = _run(stall="malformed", stall_step="summary")
    assert malformed["error_code"] == "MALFORMED_CHILD_RESULT"
    assert malformed["session_status"] == "SESSION_INCOMPLETE"
    assert keeper_file.read_bytes() == keeper_bytes
    assert keeper["session_status"] == "SESSION_COMPLETE_SYNTHETIC"
    for path in log_dir.glob("r56-phase5-*.json"):
        assert PIN not in path.read_text(encoding="utf-8")
        assert "SYNTHETIC-NOT-REAL" not in path.read_text(encoding="utf-8")
    try:
        _load("session_supervisor").run_offline(
            answer="NO",
            credential=_load("credential_gate").SyntheticCredential(),
            log_dir=HERE.parent,
            collected_at="2026-10-22T15:00:00Z",
        )
    except _load("operator_confirmation").ConfirmationRejected as exc:
        assert exc.code == "CONFIRMATION_REJECTED"
    else:
        raise AssertionError("bad_confirmation_continued")
    try:
        _run(log_dir=HERE.parent)
    except _load("session_supervisor").SupervisorRejected as exc:
        assert exc.code == "LOG_PATH_OUTSIDE"
    else:
        raise AssertionError("outside_log_accepted")
    try:
        _run(request_deadline=5.1)
    except _load("session_supervisor").SupervisorRejected as exc:
        assert exc.code == "DEADLINE_ABOVE_CAP"
    else:
        raise AssertionError("deadline_cap_bypassed")
    _clean(log_dir)


def test_offline_launch_writes_one_synthetic_session():
    log_dir = _logs()
    _clean(log_dir)
    assert _load("offline_entry").launch(["--offline"]) == 0
    files = list(log_dir.glob("r56-phase5-*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert record["live_network_access"] == "NOT_AUTHORISED"
    assert record["executable_order"] == "NOT_PRODUCED"
    assert record["children_started"] == 2
    assert PIN not in files[0].read_text(encoding="utf-8")
    _clean(log_dir)
