"""Offline tests for R.56 phase 4. Networking is blocked."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE2 = HERE.parent / "phase2_offline"
PHASE3 = HERE.parent / "phase3_offline"
ROOT = HERE.parents[4]
IMPLEMENTATION = (
    "https_transport_candidate.py",
    "credential_boundary.py",
    "diagnostic_session.py",
    "offline_entry.py",
    "synthetic_transport.py",
)
PHASE2_SHA = {
    "response_adapter.py": "d10e5663d1ca81c28f22ca7085e86c746421eab911f64aeb37588dbef9123079",
    "account_diagnostics.py": "807b4b5c9a7cd353fe96a6b4691579af07308de573822b69e9cdeba3fdd4ba26",
    "pricing_diagnostics.py": "5aac6a9f7d6853e4dd884707845083e8aee2bf35fe5fe771cb8114e880389cf9",
    "sizing_diagnostics.py": "4d861e689db1bdbaf616567617caf8103d8766d7193fe90a6b9748f1d0f32525",
    "diagnostic_writer.py": "c480487c86149ab23c54b0398cc2f4b1cf3efbf7ee91cddf6002b2bb05d34448",
    "synthetic_fixtures.py": "e0d9ddb4f7b67725c99938c7f00979eb91c7a271ada03588720bd7e9e1abaaa2",
    "test_phase2_offline.py": "a39df7060e1fbb8d5dfc85692a0bd2c12d2d4b30b10097b4eed24986f728e70c",
}
PHASE3_SHA = {
    "collector_main.py": "14c2626847c873c57fc54415516be3ce60b477cb7c3ad3b72cb159021ef37ed1",
    "collector_session.py": "056f76d0e68c8cdedc122c0f630c5219cdfb8df69cb9ab7ffa86ec240396187a",
    "offline_transport.py": "8f36ca0ce7707ad0db9a35f7839f7752c2dc049ecabc82bf8db9d381189928fb",
    "readonly_request_gate.py": "ffaf0020c9252bf1dc8a43b5abfffdee9e85c3fba85332ea7cd44f845bfe2d8b",
    "readonly_request_plan.py": "739bd645f7005004d66af875a94f0da2a6c7241691856ff10a3c972aee8c5fd4",
    "synthetic_fixtures.py": "d93364681e335439e23ef9cfec482cee32496135a636d6935f33da8c4294628a",
    "test_phase3_offline.py": "426c39159dc62aee52aa5972732747cba13dff4555dbe8c1409d22a3bd313202",
}
FORBIDDEN = {"forex_bot", "oandapyV20", "requests", "httpx", "urllib", "socket", "ssl", "http", "main"}


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
    return _load(HERE, "r56p4", stem)


def _logs() -> Path:
    path = HERE / "synthetic_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean(path: Path) -> None:
    for item in path.glob("r56-phase4-*.json"):
        item.unlink()


def _clock(request_budget: float = 5.0, session_budget: float = 15.0):
    transport = _local("https_transport_candidate")
    return transport.SessionClock(
        monotonic=transport.ManualClock(),
        request_budget=request_budget,
        session_budget=session_budget,
    )


def _run(double=None, **kwargs):
    session = _local("diagnostic_session")
    fixtures = _local("synthetic_transport")
    if double is None:
        double = fixtures.OfflineDouble()
    clock = kwargs.pop("clock", None) or _clock()
    record = session.run_offline(
        double,
        clock=clock,
        log_dir=_logs(),
        collected_at="2026-10-22T13:00:00Z",
        **kwargs,
    )
    return record


def _plan():
    return _load(PHASE3, "r56p3", "readonly_request_plan")


def _gate():
    return _load(PHASE3, "r56p3", "readonly_request_gate")


def _summary_approved():
    return _gate().approve(_plan().summary_candidate(), step=1, prior=[])


def _pricing_approved():
    return _gate().approve(_plan().pricing_candidate(), step=2, prior=["summary"])


def _transport_session(double, request_budget=5.0, session_budget=15.0):
    module = _local("https_transport_candidate")
    clock = module.SessionClock(
        monotonic=module.ManualClock(),
        request_budget=request_budget,
        session_budget=session_budget,
    )
    return module.TransportSession(double, clock), clock


def test_default_entry_cannot_connect(capsys):
    log_dir = _logs()
    _clean(log_dir)
    before = {path.name for path in log_dir.iterdir()}
    assert _local("offline_entry").launch([]) == 2
    assert {path.name for path in log_dir.iterdir()} == before
    assert "No credential prompt" in capsys.readouterr().out


def test_live_rejected():
    assert _local("offline_entry").launch(["--live"]) == 2
    assert _local("offline_entry").launch(["--offline", "--live"]) == 2


def test_connect_rejected():
    assert _local("offline_entry").launch(["--connect"]) == 2


def test_authenticate_rejected():
    assert _local("offline_entry").launch(["--authenticate"]) == 2
    assert _local("offline_entry").launch(["--token", "abc"]) == 2


def test_real_credential_provider_rejected():
    credentials = _local("credential_boundary")

    class LiveProvider:
        classification = "LIVE_CREDENTIAL"
        token = "not-a-synthetic-token"
        account_id = credentials.SYNTHETIC_ACCOUNT_ID

    log_dir = _logs()
    _clean(log_dir)
    before = set(log_dir.iterdir())
    try:
        credentials.authorization_present(LiveProvider())
    except credentials.CredentialRejected as exc:
        assert exc.code == "REAL_CREDENTIAL_PROVIDER_REJECTED"
    else:
        raise AssertionError("real_provider_accepted")
    try:
        credentials.read_real_credential()
    except credentials.CredentialRejected as exc:
        assert exc.code == "REAL_CREDENTIAL_INPUT_NOT_AUTHORISED"
    else:
        raise AssertionError("real_reader_returned")
    assert set(log_dir.iterdir()) == before
    assert credentials.HIDDEN_INPUT == "NOT_IMPLEMENTED"


def test_no_production_or_trading_imports():
    banned = ("bot_loop", "oanda_exec", "oanda_client", "trading", "execution", "app", "paper_broker", "live_broker")
    for name in IMPLEMENTATION:
        tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        roots = {item.split(".")[0] for item in imported}
        assert not roots & FORBIDDEN
        blob = " ".join(imported)
        for item in banned:
            assert item not in blob


def test_dns_and_sockets_blocked():
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
    for name in IMPLEMENTATION:
        text = (HERE / name).read_text(encoding="utf-8")
        assert "os.environ" not in text
        assert "getenv" not in text
        assert "HTTPS_PROXY" not in text
        assert "HTTP_PROXY" not in text
        assert "import socket" not in text


def test_fixed_host_port_and_https():
    transport = _local("https_transport_candidate")
    approved = _summary_approved()
    assert approved["host"] == "api-fxtrade.oanda.com"
    assert approved["port"] == 443
    assert approved["scheme"] == "https"
    assert approved["method"] == "GET"
    session, _clock_obj = _transport_session(_local("synthetic_transport").OfflineDouble())
    for field, value, code in (
        ("host", "api-fxpractice.oanda.com", "HOST_REJECTED"),
        ("port", 80, "HOST_REJECTED"),
        ("scheme", "http", "SCHEME_REJECTED"),
        ("method", "POST", "METHOD_REJECTED"),
    ):
        mutated = dict(approved)
        mutated[field] = value
        try:
            session.execute(mutated, authorization_present=True)
        except transport.TransportRejected as exc:
            assert exc.code == code
        else:
            raise AssertionError(field)


def test_summary_and_pricing_endpoints_accepted():
    summary = _summary_approved()
    pricing = _pricing_approved()
    assert summary["endpoint"] == "/v3/accounts/{accountID}/summary"
    assert pricing["endpoint"] == "/v3/accounts/{accountID}/pricing"
    assert pricing["query"]["instruments"] == "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF"
    assert "includeHomeConversions" not in pricing["query"]
    record = _run()
    assert record["summary_request"]["result"] == "SYNTHETIC_RESPONSE_ACCEPTED"
    assert record["pricing_request"]["result"] == "SYNTHETIC_RESPONSE_ACCEPTED"
    assert record["target_environment"] == "OANDA_LIVE"
    assert record["live_network_access"] == "NOT_AUTHORISED"
    _clean(_logs())


def test_unknown_orders_trades_positions_rejected():
    plan = _plan()
    gate = _gate()
    account = plan.SYNTHETIC_ACCOUNT_ID
    cases = (
        ("/v3/accounts/" + account + "/changes", "ENDPOINT_REJECTED"),
        ("/v3/accounts/" + account + "/orders", "ORDERS_REJECTED"),
        ("/v3/accounts/" + account + "/trades", "TRADES_REJECTED"),
        ("/v3/accounts/" + account + "/positions/EUR_USD/close", "POSITIONS_REJECTED"),
    )
    for path, code in cases:
        candidate = dict(plan.summary_candidate())
        candidate["path"] = path
        try:
            gate.approve(candidate, step=1, prior=[])
        except gate.GateRejected as exc:
            assert exc.code == code
        else:
            raise AssertionError(path)


def test_summary_cannot_be_duplicated_and_pricing_cannot_lead():
    transport = _local("https_transport_candidate")
    fixtures = _local("synthetic_transport")
    session, _clock_obj = _transport_session(fixtures.OfflineDouble())
    approved = _summary_approved()
    session.execute(approved, authorization_present=True)
    try:
        session.execute(approved, authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "SUMMARY_DUPLICATE_REJECTED"
    else:
        raise AssertionError("duplicate_summary_accepted")
    early, _early_clock = _transport_session(fixtures.OfflineDouble())
    try:
        early.execute(_pricing_approved(), authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "SEQUENCE_REJECTED"
    else:
        raise AssertionError("pricing_led")


def test_third_request_rejected():
    transport = _local("https_transport_candidate")
    session, _clock_obj = _transport_session(_local("synthetic_transport").OfflineDouble())
    session.execute(_summary_approved(), authorization_present=True)
    session.execute(_pricing_approved(), authorization_present=True)
    try:
        session.execute(_summary_approved(), authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "REQUEST_LIMIT"
    else:
        raise AssertionError("third_request_accepted")


def test_query_instrument_body_redirect_retry_stream_rejected():
    plan = _plan()
    gate = _gate()
    pricing = plan.pricing_candidate()
    pricing["query"]["includeHomeConversions"] = "true"
    try:
        gate.approve(pricing, step=2, prior=["summary"])
    except gate.GateRejected as exc:
        assert exc.code == "QUERY_REJECTED"
    else:
        raise AssertionError("extra_query_accepted")
    wrong = plan.pricing_candidate()
    wrong["query"] = {"instruments": "EUR_USD"}
    try:
        gate.approve(wrong, step=2, prior=["summary"])
    except gate.GateRejected as exc:
        assert exc.code == "QUERY_REJECTED"
    else:
        raise AssertionError("partial_instruments_accepted")
    transport = _local("https_transport_candidate")
    session, _clock_obj = _transport_session(_local("synthetic_transport").OfflineDouble())
    for field, value, code in (
        ("body", {"order": {}}, "BODY_REJECTED"),
        ("redirects", True, "REDIRECT_REJECTED"),
        ("retries", 1, "RETRY_REJECTED"),
        ("stream", True, "STREAM_REJECTED"),
    ):
        mutated = dict(_summary_approved())
        mutated[field] = value
        try:
            session.execute(mutated, authorization_present=True)
        except transport.TransportRejected as exc:
            assert exc.code == code
        else:
            raise AssertionError(field)


def test_valid_summary_and_pricing_are_synthetic():
    record = _run()
    assert record["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert record["session_status"] == "SESSION_COMPLETE_SYNTHETIC"
    assert record["account_diagnostics"]["home_currency"] == "GBP"
    assert record["account_diagnostics"]["balance"] == "100.00"
    assert record["account_diagnostics"]["nav"] == "100.00"
    assert record["account_diagnostics"]["margin_available"] == "100.00"
    assert record["account_diagnostics"]["schema_version"] == "r56.phase2.1"
    eur = record["pricing_diagnostics"][0]
    assert eur["instrument"] == "EUR_USD"
    assert eur["bid"] == "1.10000"
    assert eur["ask"] == "1.10020"
    assert eur["spread_price"] == "0.00020"
    assert eur["spread_pips"] == "NOT_CALCULATED"
    assert eur["quote_timestamp"] == "2026-10-21T16:00:00Z"
    assert eur["tradeable"] is True
    assert record["broker_evidence_complete"] is False
    assert len(record["pricing_diagnostics"]) == 6
    _clean(_logs())


def test_missing_currency_bid_and_invalid_price():
    fixtures = _local("synthetic_transport")
    missing_currency = _run(fixtures.OfflineDouble(summary=fixtures.summary_document(include_currency=False)))
    assert missing_currency["account_diagnostics"]["home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED" in missing_currency["missing_evidence"]
    missing_bid = _run(fixtures.OfflineDouble(pricing=fixtures.pricing_document(include_bid=False)))
    assert missing_bid["pricing_diagnostics"][0]["bid"] == "NOT_RETURNED"
    assert missing_bid["pricing_diagnostics"][0]["spread_price"] == "NOT_CALCULATED"
    invalid = _run(fixtures.OfflineDouble(pricing=fixtures.pricing_document(bid="0")))
    assert invalid["pricing_diagnostics"][0]["bid"] == "NOT_RETURNED"
    assert "non_positive_price" in invalid["pricing_diagnostics"][0]["validation_warnings"]
    _clean(_logs())


def test_malformed_json_and_http_errors():
    fixtures = _local("synthetic_transport")
    malformed = _run(fixtures.OfflineDouble(body_override=b"{"))
    assert malformed["error_code"] == "MALFORMED_JSON"
    assert malformed["pricing_request"]["result"] == "NOT_SENT"
    assert malformed["session_status"] == "SESSION_INCOMPLETE"
    for status in (401, 403, 429, 500):
        failed = _run(fixtures.OfflineDouble(status_code=status, error_body=b"Bearer SYNTHETIC-TOKEN-R56P4-NOT-REAL"))
        assert failed["error_code"] == f"HTTP_{status}"
        assert failed["session_status"] == "SESSION_INCOMPLETE"
        assert "SYNTHETIC-TOKEN" not in json.dumps(failed)
        assert failed["pricing_diagnostics"] == "NOT_PRODUCED"
    _clean(_logs())


def test_response_larger_than_one_mebibyte():
    fixtures = _local("synthetic_transport")
    double = fixtures.OfflineDouble(body_override=b"x" * (1048576 + 1))
    record = _run(double)
    assert record["error_code"] == "RESPONSE_TOO_LARGE"
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert "xxxx" not in json.dumps(record)
    _clean(_logs())


def test_stalled_phases_stop_on_the_injected_clock():
    transport = _local("https_transport_candidate")
    fixtures = _local("synthetic_transport")
    for phase in ("connect", "tls", "headers"):
        double = fixtures.OfflineDouble(stalls={phase: 30})
        session, clock = _transport_session(double, request_budget=5.0, session_budget=15.0)
        try:
            session.execute(_summary_approved(), authorization_present=True)
        except transport.TransportRejected as exc:
            assert exc.code == "REQUEST_DEADLINE"
        else:
            raise AssertionError(phase)
        assert clock.monotonic() == 5.0001
        assert phase in double.phases_run
    stalled_read = fixtures.OfflineDouble(stalls={"body_chunk": 30})
    session, clock = _transport_session(stalled_read, request_budget=5.0, session_budget=15.0)
    try:
        session.execute(_summary_approved(), authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "REQUEST_DEADLINE"
    else:
        raise AssertionError("stalled_read_continued")
    assert clock.monotonic() == 5.0001
    slow = fixtures.OfflineDouble(body_override=b"y" * 500, chunk_size=10, stalls={"body_chunk": 0.05})
    session, clock = _transport_session(slow, request_budget=0.30, session_budget=15.0)
    try:
        session.execute(_summary_approved(), authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "REQUEST_DEADLINE"
    else:
        raise AssertionError("slow_body_continued")
    assert 1 <= slow.chunks_served <= 10
    assert 0.25 < clock.monotonic() <= 0.3001


def test_session_deadline_and_blocking_sleep():
    fixtures = _local("synthetic_transport")
    jumped = fixtures.OfflineDouble()
    jumped.advance_after_summary = 15.0
    record = _run(jumped, clock=_clock(request_budget=5.0, session_budget=15.0))
    assert record["error_code"] == "SESSION_DEADLINE"
    assert record["observed_clock_seconds"] == "15.0000"
    assert record["pricing_request"]["result"] == "REJECTED"
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert "SESSION_COMPLETE_SYNTHETIC" not in json.dumps(record)
    assert jumped.phases_run.count("connect") == 1
    blocking = fixtures.OfflineDouble(ignore_timeout=True, ignore_seconds=0.20, ignore_phase="connect")
    transport = _local("https_transport_candidate")
    started = time.monotonic()
    blocked = _run(
        blocking,
        clock=transport.SessionClock(monotonic=time.monotonic, request_budget=0.05, session_budget=15.0),
    )
    elapsed = time.monotonic() - started
    assert blocked["error_code"] == "REQUEST_DEADLINE"
    assert elapsed >= 0.18
    assert float(blocked["observed_wall_seconds"]) >= 0.18
    assert "tls" not in blocking.phases_run
    assert blocked["pricing_request"]["result"] == "NOT_SENT"
    _clean(_logs())


def test_failure_after_summary_has_no_success_artifact():
    fixtures = _local("synthetic_transport")
    double = fixtures.OfflineDouble()
    double.pricing_status = 502
    record = _run(double)
    assert record["error_code"] == "HTTP_502"
    assert record["account_diagnostics"]["outcome"] == "DIAGNOSTIC_RECORDED"
    assert record["pricing_diagnostics"] == "NOT_PRODUCED"
    assert record["session_status"] == "SESSION_INCOMPLETE"
    text = json.dumps(record)
    assert "SESSION_COMPLETE_SYNTHETIC" not in text
    _clean(_logs())


def test_secrets_unknown_fields_and_no_order():
    fixtures = _local("synthetic_transport")
    credentials = _local("credential_boundary")
    summary = fixtures.summary_document(
        extra={"division": "spread-bet", "comment": "Bearer " + credentials.SYNTHETIC_TOKEN}
    )
    record = _run(fixtures.OfflineDouble(summary=summary))
    text = json.dumps(record)
    assert credentials.SYNTHETIC_TOKEN not in text
    assert credentials.SYNTHETIC_ACCOUNT_ID not in text
    assert "Bearer" not in text
    assert "spread-bet" not in text
    assert "division" not in text
    assert record["executable_order"] == "NOT_PRODUCED"
    assert record["order_payload"] == "NOT_PRODUCED"
    assert record["executable_position_size"] == "NOT_CALCULATED"
    assert record["strategy_profitability"] == "NOT_ESTABLISHED"
    assert record["gbp_pip_value"] == "GBP_PIP_VALUE_UNVERIFIED"
    assert record["stake_to_unit_mapping"] == "STAKE_TO_UNIT_MAPPING_NOT_VERIFIED"
    assert record["financing"] == "FINANCING_NOT_VERIFIED"
    assert record["pip_location"] == "NOT_ESTABLISHED"
    assert record["home_conversion_request"] == "NOT_REQUESTED"
    assert record["quote_freshness"] == "QUOTE_FRESHNESS_NOT_VERIFIED"
    assert "1.35" not in text
    assert "OrderCreate" not in text
    raised = fixtures.OfflineDouble()
    raised.raise_on = "connect"
    raised.raise_text = "Bearer " + credentials.SYNTHETIC_TOKEN + " " + credentials.SYNTHETIC_ACCOUNT_ID
    failed = _run(raised)
    failed_text = json.dumps(failed)
    assert failed["error_code"] == "EXCEPTION_CONTAINED"
    assert credentials.SYNTHETIC_TOKEN not in failed_text
    assert credentials.SYNTHETIC_ACCOUNT_ID not in failed_text
    _clean(_logs())


def test_logs_stay_in_directory_and_sources_unchanged():
    session = _local("diagnostic_session")
    log_dir = _logs()
    _clean(log_dir)
    record = _run()
    assert record["phase2_adapters"] == "REUSED"
    for path in log_dir.glob("r56-phase4-*.json"):
        assert HERE in path.resolve().parents
        assert "synthetic_logs" in path.resolve().parts
    try:
        session.run_offline(
            _local("synthetic_transport").OfflineDouble(),
            clock=_clock(),
            log_dir=HERE.parent,
            collected_at="2026-10-22T13:00:00Z",
        )
    except session.SessionRejected as exc:
        assert exc.code == "LOG_PATH_OUTSIDE"
    else:
        raise AssertionError("outside_log_accepted")
    for name, digest in PHASE2_SHA.items():
        assert hashlib.sha256((PHASE2 / name).read_bytes()).hexdigest() == digest
    for name, digest in PHASE3_SHA.items():
        assert hashlib.sha256((PHASE3 / name).read_bytes()).hexdigest() == digest
    assert hashlib.sha256((ROOT / "forex_bot" / "oanda_client.py").read_bytes()).hexdigest() == (
        "02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a"
    )
    _clean(log_dir)


def test_repeated_sessions_and_tls_policy():
    log_dir = _logs()
    _clean(log_dir)
    keeper = log_dir / "unrelated-keep.txt"
    keeper.write_text("keep\n", encoding="utf-8")
    first = _run()
    second = _run()
    assert first["session_id"] != second["session_id"]
    files = list(log_dir.glob("r56-phase4-*.json"))
    assert len(files) == 2
    assert keeper.read_text(encoding="utf-8") == "keep\n"
    keeper.unlink()
    transport = _local("https_transport_candidate")

    class Context:
        verify_mode = None
        check_hostname = None

    context = Context()
    transport.apply_tls_policy(context)
    assert context.verify_mode == "CERT_REQUIRED"
    assert context.check_hostname is True
    bad = _local("synthetic_transport").OfflineDouble(tls_policy={"verify_mode": "CERT_NONE", "check_hostname": False})
    try:
        _transport_session(bad)[0].execute(_summary_approved(), authorization_present=True)
    except transport.TransportRejected as exc:
        assert exc.code == "TLS_POLICY_REJECTED"
    else:
        raise AssertionError("weak_tls_accepted")
    try:
        transport.seal_live_socket()
    except transport.TransportRejected as exc:
        assert exc.code == "LIVE_NETWORK_NOT_AUTHORISED"
    else:
        raise AssertionError("live_socket_opened")
    try:
        transport.SessionClock(monotonic=transport.ManualClock(), request_budget=5.1, session_budget=15.0)
    except transport.TransportRejected as exc:
        assert exc.code == "BUDGET_ABOVE_CAP"
    else:
        raise AssertionError("budget_cap_bypassed")
    _clean(log_dir)


def test_offline_launch_writes_one_synthetic_session():
    log_dir = _logs()
    _clean(log_dir)
    assert _local("offline_entry").launch(["--offline"]) == 0
    files = list(log_dir.glob("r56-phase4-*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert record["live_network_access"] == "NOT_AUTHORISED"
    assert record["executable_order"] == "NOT_PRODUCED"
    _clean(log_dir)
