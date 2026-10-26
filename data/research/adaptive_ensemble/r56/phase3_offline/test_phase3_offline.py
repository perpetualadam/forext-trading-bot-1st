"""Offline tests for the R.56 phase 3 collector. Networking is blocked."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE2 = HERE.parent / "phase2_offline"
ROOT = HERE.parents[4]
CLOCK = lambda: datetime(2026, 10, 22, 13, 0, tzinfo=timezone.utc)
IMPLEMENTATION = (
    "collector_main.py",
    "readonly_request_plan.py",
    "readonly_request_gate.py",
    "offline_transport.py",
    "collector_session.py",
    "synthetic_fixtures.py",
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
OPERATIONAL_SHA = {
    "forex_bot/oanda_client.py": "02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a",
    "forex_bot/oanda_account_adapter.py": "191466d11e1fac41ef1ccd5603046a3df5c4682f761fde651adcf9229bdf83b5",
    "main.py": "4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb",
}
FORBIDDEN = {"forex_bot", "oandapyV20", "requests", "httpx", "urllib", "socket", "ssl", "http", "main"}


def _block_network() -> None:
    def blocked(*_args, **_kwargs):
        raise AssertionError("network_blocked")

    socket.socket = blocked  # type: ignore[misc, assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    socket.getaddrinfo = blocked  # type: ignore[assignment]


_block_network()


def _load(stem: str):
    name = f"r56p3_{stem}"
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
    for item in path.glob("r56-phase3-*.json"):
        item.unlink()


def _session():
    return _load("collector_session")


def _plan():
    return _load("readonly_request_plan")


def _gate():
    return _load("readonly_request_gate")


def _transport(summary=None, pricing=None, **kwargs):
    fixtures = _load("synthetic_fixtures")
    module = _load("offline_transport")
    return module.SyntheticTransport(
        fixtures.summary_document() if summary is None else summary,
        fixtures.pricing_document() if pricing is None else pricing,
        **kwargs,
    )


def _run(**kwargs):
    session = _session()
    record = session.run_synthetic(
        kwargs.pop("transport", _transport()),
        session_id=session.new_session_id(),
        log_dir=_logs(),
        clock=CLOCK,
    )
    return record


def _mutate(base: dict, **overrides) -> dict:
    copied = dict(base)
    copied.update(overrides)
    return copied


def _reject_path(path: str, code: str) -> None:
    plan = _plan()
    gate = _gate()
    candidate = _mutate(plan.summary_candidate(), path=path, query={})
    try:
        gate.approve(candidate, step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == code
    else:
        raise AssertionError(path)


def test_01_offline_entry_is_synthetic():
    log_dir = _logs()
    _clean(log_dir)
    assert _load("collector_main").launch(["--offline"]) == 0
    files = list(log_dir.glob("r56-phase3-*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["data_source"] == "SYNTHETIC_TEST_ONLY"
    assert record["session_status"] == "SESSION_COMPLETE_SYNTHETIC"
    assert record["schema_version"] == "r56.phase3.1"
    _clean(log_dir)


def test_02_missing_offline_argument_rejected(capsys):
    log_dir = _logs()
    _clean(log_dir)
    before = {path.name for path in log_dir.iterdir()}
    assert _load("collector_main").launch([]) == 2
    assert {path.name for path in log_dir.iterdir()} == before
    assert "No credential prompt" in capsys.readouterr().out


def test_03_live_rejected():
    assert _load("collector_main").launch(["--live"]) == 2
    assert _load("collector_main").launch(["--offline", "--live"]) == 2


def test_04_connect_rejected():
    assert _load("collector_main").launch(["--connect"]) == 2


def test_05_authenticate_rejected():
    assert _load("collector_main").launch(["--authenticate"]) == 2
    assert _load("collector_main").launch(["--account"]) == 2


def test_06_unknown_arguments_rejected():
    main = _load("collector_main")
    assert main.launch(["--offline", "--extra"]) == 2
    assert main.launch(["practice"]) == 2
    assert main.launch(["--unknown"]) == 2


def test_07_no_production_imports():
    for name in IMPLEMENTATION:
        tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [(node.module or "").split(".")[0]]
            else:
                continue
            assert not set(modules) & FORBIDDEN


def test_08_no_trading_engine_imports():
    banned = ("bot_loop", "oanda_exec", "oanda_client", "trading", "execution", "app", "paper_broker", "live_broker")
    for name in IMPLEMENTATION:
        tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        blob = " ".join(imported)
        for item in banned:
            assert item not in blob


def test_09_no_oanda_sdk_imports():
    for name in IMPLEMENTATION:
        text = (HERE / name).read_text(encoding="utf-8")
        assert "oandapyV20" not in text
        assert "import requests" not in text
        assert "httpx" not in text


def test_10_dns_blocked():
    try:
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_was_not_blocked")


def test_11_sockets_blocked():
    try:
        socket.socket()
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("socket_was_not_blocked")


def test_12_http_libraries_not_used():
    before = set(sys.modules)
    _session()
    added = set(sys.modules) - before
    for name in added:
        assert name not in {"requests", "httpx", "urllib.request", "oandapyV20"}
        assert not name.startswith("forex_bot")
        assert not name.startswith("oandapy")


def test_13_fixed_host_enforced():
    gate = _gate()
    candidate = _mutate(_plan().summary_candidate(), host="api-fxpractice.oanda.com")
    try:
        gate.approve(candidate, step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "HOST_REJECTED"
    else:
        raise AssertionError("host_was_accepted")


def test_14_fixed_port_enforced():
    gate = _gate()
    try:
        gate.approve(_mutate(_plan().summary_candidate(), port=80), step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "PORT_REJECTED"
    else:
        raise AssertionError("port_was_accepted")


def test_15_https_enforced():
    gate = _gate()
    try:
        gate.approve(_mutate(_plan().summary_candidate(), scheme="http"), step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "SCHEME_REJECTED"
    else:
        raise AssertionError("http_was_accepted")


def test_16_get_only():
    gate = _gate()
    try:
        gate.approve(_mutate(_plan().summary_candidate(), method="POST"), step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "METHOD_REJECTED"
    else:
        raise AssertionError("post_was_accepted")


def test_17_summary_endpoint_accepted():
    plan = _plan()
    approved = _gate().approve(plan.summary_candidate(), step=1, prior=[])
    assert approved["endpoint"] == "/v3/accounts/{accountID}/summary"
    assert approved["method"] == "GET"
    assert plan.SYNTHETIC_ACCOUNT_ID not in json.dumps(approved)


def test_18_pricing_endpoint_accepted():
    plan = _plan()
    approved = _gate().approve(plan.pricing_candidate(), step=2, prior=["summary"])
    assert approved["endpoint"] == "/v3/accounts/{accountID}/pricing"
    assert approved["query"]["instruments"] == "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF"
    assert "includeHomeConversions" not in approved["query"]


def test_19_summary_path_outside_pattern_rejected():
    _reject_path("/v3/accounts/summary", "ENDPOINT_REJECTED")


def test_20_orders_endpoint_rejected():
    _reject_path("/v3/accounts/" + _plan().SYNTHETIC_ACCOUNT_ID + "/orders", "ORDERS_REJECTED")


def test_21_trades_endpoint_rejected():
    _reject_path("/v3/accounts/" + _plan().SYNTHETIC_ACCOUNT_ID + "/trades", "TRADES_REJECTED")


def test_22_positions_endpoint_rejected():
    _reject_path("/v3/accounts/" + _plan().SYNTHETIC_ACCOUNT_ID + "/positions/EUR_USD/close", "POSITIONS_REJECTED")


def test_23_candles_endpoint_rejected():
    _reject_path("/v3/instruments/EUR_USD/candles", "CANDLES_REJECTED")


def test_24_unknown_endpoint_rejected():
    _reject_path("/v3/accounts/" + _plan().SYNTHETIC_ACCOUNT_ID + "/changes", "ENDPOINT_REJECTED")


def test_25_arbitrary_host_rejected():
    gate = _gate()
    try:
        gate.approve(_mutate(_plan().summary_candidate(), host="example.com"), step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "HOST_REJECTED"
    else:
        raise AssertionError("arbitrary_host_accepted")


def test_26_arbitrary_query_rejected():
    gate = _gate()
    candidate = _plan().pricing_candidate()
    candidate["query"]["includeHomeConversions"] = "true"
    try:
        gate.approve(candidate, step=2, prior=["summary"])
    except gate.GateRejected as exc:
        assert exc.code == "QUERY_REJECTED"
    else:
        raise AssertionError("extra_query_accepted")


def test_27_request_bodies_rejected():
    gate = _gate()
    try:
        gate.approve(_mutate(_plan().summary_candidate(), body={"order": {}}), step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "BODY_REJECTED"
    else:
        raise AssertionError("body_accepted")


def test_28_redirects_rejected():
    gate = _gate()
    try:
        gate.approve(_mutate(_plan().summary_candidate(), redirects=True), step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "REDIRECT_REJECTED"
    else:
        raise AssertionError("redirect_accepted")


def test_29_retries_rejected():
    gate = _gate()
    try:
        gate.approve(_mutate(_plan().summary_candidate(), retries=1), step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "RETRY_REJECTED"
    else:
        raise AssertionError("retry_accepted")


def test_30_streaming_rejected():
    gate = _gate()
    try:
        gate.approve(_mutate(_plan().summary_candidate(), stream=True), step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "STREAM_REJECTED"
    else:
        raise AssertionError("stream_accepted")


def test_31_two_request_maximum_and_order():
    plan = _plan()
    gate = _gate()
    gate.approve(plan.summary_candidate(), step=1, prior=[])
    gate.approve(plan.pricing_candidate(), step=2, prior=["summary"])
    try:
        gate.approve(plan.summary_candidate(), step=3, prior=["summary", "pricing"])
    except gate.GateRejected as exc:
        assert exc.code == "REQUEST_LIMIT"
    else:
        raise AssertionError("third_request_accepted")
    try:
        gate.approve(plan.pricing_candidate(), step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "SEQUENCE_REJECTED"
    else:
        raise AssertionError("pricing_before_summary_accepted")


def test_32_summary_before_pricing_in_session():
    transport = _transport()
    record = _run(transport=transport)
    assert transport.calls == ["summary", "pricing"]
    assert record["summary_request"]["sequence"] == 1
    assert record["pricing_request"]["sequence"] == 2
    _clean(_logs())


def test_33_summary_failure_stops_pricing():
    transport = _transport(summary={})
    record = _run(transport=transport)
    assert transport.calls == ["summary"]
    assert record["error_code"] == "SUMMARY_REJECTED"
    assert record["pricing_request"]["result"] == "NOT_SENT"
    assert record["session_status"] == "SESSION_INCOMPLETE"
    _clean(_logs())


def test_34_pricing_failure_is_not_a_completed_session():
    record = _run(transport=_transport(pricing={"prices": []}))
    assert record["error_code"] == "PRICING_REJECTED"
    assert record["session_status"] == "SESSION_INCOMPLETE"
    assert "SESSION_COMPLETE_SYNTHETIC" not in json.dumps(record)
    _clean(_logs())


def test_35_malformed_summary_rejected():
    record = _run(transport=_transport(summary=[]))
    assert record["error_code"] == "SUMMARY_REJECTED"
    assert record["pricing_diagnostics"] == "NOT_PRODUCED"
    _clean(_logs())


def test_36_malformed_pricing_rejected():
    record = _run(transport=_transport(pricing={"prices": "bad"}))
    assert record["error_code"] == "PRICING_REJECTED"
    assert record["account_diagnostics"]["outcome"] == "DIAGNOSTIC_RECORDED"
    _clean(_logs())


def test_37_account_identifier_omitted():
    record = _run()
    text = json.dumps(record)
    assert _load("synthetic_fixtures").SYNTHETIC_ACCOUNT_ID not in text
    assert "synthetic-alias-not-logged" not in text
    assert record["account_diagnostics"]["account_id_logged"] is False
    _clean(_logs())


def test_38_bearer_token_omitted():
    fixtures = _load("synthetic_fixtures")
    summary = fixtures.summary_document(extra={"comment": "Bearer " + fixtures.SYNTHETIC_TOKEN})
    record = _run(transport=_transport(summary=summary))
    text = json.dumps(record)
    assert fixtures.SYNTHETIC_TOKEN not in text
    assert "Bearer" not in text
    _clean(_logs())


def test_39_exceptions_sanitised():
    fixtures = _load("synthetic_fixtures")
    transport = _transport(raise_on="summary", raise_error=fixtures.secret_exception())
    record = _run(transport=transport)
    text = json.dumps(record)
    assert record["error_code"] == "EXCEPTION_CONTAINED"
    assert fixtures.SYNTHETIC_TOKEN not in text
    assert fixtures.SYNTHETIC_ACCOUNT_ID not in text
    assert "RuntimeError" not in text
    _clean(_logs())


def test_40_unknown_response_fields_not_logged():
    summary = _load("synthetic_fixtures").summary_document(extra={"division": "spread-bet", "note": "ignore-me"})
    record = _run(transport=_transport(summary=summary))
    text = json.dumps(record)
    assert "division" not in text
    assert "spread-bet" not in text
    assert "ignore-me" not in text
    _clean(_logs())


def test_41_phase2_adapters_reused():
    session = _session()
    account = session._phase2("account_diagnostics")
    pricing = session._phase2("pricing_diagnostics")
    assert Path(account.__file__).resolve() == (PHASE2 / "account_diagnostics.py").resolve()
    assert Path(pricing.__file__).resolve() == (PHASE2 / "pricing_diagnostics.py").resolve()
    record = _run()
    assert record["phase2_adapters"] == "REUSED"
    assert record["account_diagnostics"]["schema_version"] == "r56.phase2.1"
    assert record["pricing_diagnostics"][0]["schema_version"] == "r56.phase2.1"
    assert record["quote_freshness"] == "QUOTE_FRESHNESS_NOT_VERIFIED"
    assert record["gbp_pip_value"] == "GBP_PIP_VALUE_UNVERIFIED"
    assert record["stake_to_unit_mapping"] == "STAKE_TO_UNIT_MAPPING_NOT_VERIFIED"
    assert record["financing"] == "FINANCING_NOT_VERIFIED"
    assert record["gbp_conversion_fallback"] == "NOT_USED"
    assert record["executable_order"] == "NOT_PRODUCED"
    _clean(_logs())


def test_42_no_executable_order_payload():
    record = _run()
    text = json.dumps(record)
    assert record["order_payload"] == "NOT_PRODUCED"
    assert record["executable_position_size"] == "NOT_CALCULATED"
    assert "OrderCreate" not in text
    assert "PositionClose" not in text
    assert "1.35" not in text
    _clean(_logs())


def test_43_logs_restricted_to_authorised_directory():
    log_dir = _logs()
    _clean(log_dir)
    session = _session()
    session.run_synthetic(_transport(), session_id=session.new_session_id(), log_dir=log_dir, clock=CLOCK)
    for path in log_dir.glob("r56-phase3-*.json"):
        assert HERE in path.resolve().parents
        assert "synthetic_logs" in path.resolve().parts
    try:
        session.run_synthetic(_transport(), session_id=session.new_session_id(), log_dir=HERE.parent, clock=CLOCK)
    except session.GatePathRejected as exc:
        assert exc.code == "LOG_PATH_OUTSIDE"
    else:
        raise AssertionError("outside_log_accepted")
    assert not list((PHASE2 / "synthetic_logs").glob("r56-phase3-*.json"))
    _clean(log_dir)


def test_44_no_stale_success_artifact():
    log_dir = _logs()
    _clean(log_dir)
    keeper = log_dir / "unrelated-keep.txt"
    keeper.write_text("keep\n", encoding="utf-8")
    failed = _run(transport=_transport(pricing={"prices": []}))
    assert failed["session_status"] == "SESSION_INCOMPLETE"
    written = list(log_dir.glob("r56-phase3-*.json"))
    assert len(written) == 1
    assert "SESSION_COMPLETE_SYNTHETIC" not in written[0].read_text(encoding="utf-8")
    assert keeper.read_text(encoding="utf-8") == "keep\n"
    keeper.unlink()
    _clean(log_dir)


def test_45_existing_files_unchanged():
    for name, digest in PHASE2_SHA.items():
        assert hashlib.sha256((PHASE2 / name).read_bytes()).hexdigest() == digest
    for name, digest in OPERATIONAL_SHA.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest


def test_46_repeated_sessions_do_not_overwrite():
    log_dir = _logs()
    _clean(log_dir)
    keeper = log_dir / "unrelated-keep.txt"
    keeper.write_text("keep\n", encoding="utf-8")
    first = _run()
    second = _run()
    assert first["session_id"] != second["session_id"]
    files = list(log_dir.glob("r56-phase3-*.json"))
    assert len(files) == 2
    assert len({path.name for path in files}) == 2
    assert keeper.read_text(encoding="utf-8") == "keep\n"
    keeper.unlink()
    _clean(log_dir)


def test_live_transport_is_unavailable():
    module = _load("offline_transport")
    try:
        module.live_transport()
    except module.OfflineTransportRejected as exc:
        assert exc.code == "LIVE_TRANSPORT_NOT_AVAILABLE"
    else:
        raise AssertionError("live_transport_returned")


def test_bypass_flag_rejected():
    gate = _gate()
    candidate = _plan().summary_candidate()
    candidate["approved"] = True
    try:
        gate.approve(candidate, step=1, prior=[])
    except gate.GateRejected as exc:
        assert exc.code == "REQUEST_REJECTED"
    else:
        raise AssertionError("bypass_accepted")
