"""Offline tests for the R.56 phase 2 diagnostic logger. Networking is blocked."""

from __future__ import annotations

import ast
import importlib.util
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CLOCK = lambda: datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
IMPLEMENTATION = (
    "response_adapter.py",
    "account_diagnostics.py",
    "pricing_diagnostics.py",
    "sizing_diagnostics.py",
    "diagnostic_writer.py",
    "synthetic_fixtures.py",
)
FORBIDDEN_MODULES = {
    "forex_bot",
    "oandapyV20",
    "requests",
    "urllib",
    "http",
    "socket",
    "ssl",
    "main",
}


def _block_network() -> None:
    def blocked(*_args, **_kwargs):
        raise AssertionError("network_blocked")

    socket.socket = blocked  # type: ignore[misc, assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    socket.getaddrinfo = blocked  # type: ignore[assignment]


_block_network()


def _load(stem: str):
    name = f"r56p2_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _writer():
    return _load("diagnostic_writer")


def _fixtures():
    return _load("synthetic_fixtures")


def _logs(tmp: Path | None = None) -> Path:
    path = HERE / "synthetic_logs" if tmp is None else tmp
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean(path: Path) -> None:
    if not path.exists():
        return
    for item in path.glob("r56-diag-*.json"):
        item.unlink()


def _read(paths: list[Path]) -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def _one(kind: str, document, log_dir: Path) -> dict:
    writer = _writer()
    paths = writer.write_documents(
        kind,
        document,
        session_id=writer.new_session_id(),
        log_dir=log_dir,
        clock=CLOCK,
    )
    assert len(paths) == 1
    return json.loads(paths[0].read_text(encoding="utf-8"))


def test_01_valid_gbp_account():
    log_dir = _logs()
    _clean(log_dir)
    record = _one("account", _fixtures().account_document(), log_dir)
    assert record["outcome"] == "DIAGNOSTIC_RECORDED"
    assert record["home_currency"] == "GBP"
    assert record["home_currency_source"] == "BROKER_REPORTED"
    assert record["home_currency_is_gbp"] is True
    assert record["account_type"] == "NOT_RETURNED"
    assert record["account_id_logged"] is False
    assert record["account_identity_verified"] is False
    assert record["executable_order"] == "NOT_PRODUCED"
    _clean(log_dir)


def test_02_non_gbp_account():
    log_dir = _logs()
    record = _one("account", _fixtures().account_document(currency="USD"), log_dir)
    assert record["home_currency"] == "USD"
    assert record["home_currency_is_gbp"] is False
    _clean(log_dir)


def test_03_missing_currency():
    log_dir = _logs()
    record = _one("account", _fixtures().account_document(include_currency=False), log_dir)
    assert record["home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert record["home_currency_is_gbp"] == "UNVERIFIED"
    assert "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED" in record["missing_evidence"]
    _clean(log_dir)


def test_04_missing_nav_or_margin():
    log_dir = _logs()
    missing_nav = _one("account", _fixtures().account_document(include_nav=False), log_dir)
    missing_margin = _one("account", _fixtures().account_document(include_margin=False), log_dir)
    assert missing_nav["nav"] == "NOT_RETURNED"
    assert "nav" in missing_nav["missing_evidence"]
    assert missing_margin["margin_available"] == "NOT_RETURNED"
    assert missing_margin["margin_used"] == "NOT_RETURNED"
    _clean(log_dir)


def test_05_valid_bid_ask():
    log_dir = _logs()
    record = _one("pricing", _fixtures().pricing_document(), log_dir)
    assert record["bid"] == "1.10000"
    assert record["ask"] == "1.10020"
    assert record["spread_price"] == "0.00020"
    assert record["spread_price_source"] == "BOT_CALCULATED"
    assert record["spread_pips"] == "NOT_CALCULATED"
    assert record["quote_freshness"] == "QUOTE_FRESHNESS_NOT_VERIFIED"
    _clean(log_dir)


def test_06_bid_greater_than_ask():
    log_dir = _logs()
    record = _one("pricing", _fixtures().pricing_document(bid="1.10020", ask="1.10000"), log_dir)
    assert record["spread_price"] == "NOT_CALCULATED"
    assert "bid_above_ask" in record["validation_warnings"]
    _clean(log_dir)


def test_07_zero_or_negative_prices():
    log_dir = _logs()
    zero = _one("pricing", _fixtures().pricing_document(bid="0", ask="1.10000"), log_dir)
    negative = _one("pricing", _fixtures().pricing_document(bid="-1.00000", ask="1.10000"), log_dir)
    assert zero["bid"] == "NOT_RETURNED"
    assert "non_positive_price" in zero["validation_warnings"]
    assert negative["bid"] == "NOT_RETURNED"
    _clean(log_dir)


def test_08_missing_bid_or_ask():
    log_dir = _logs()
    missing_bid = _one("pricing", _fixtures().pricing_document(include_bid=False), log_dir)
    missing_ask = _one("pricing", _fixtures().pricing_document(include_ask=False), log_dir)
    assert missing_bid["bid"] == "NOT_RETURNED"
    assert missing_ask["ask"] == "NOT_RETURNED"
    assert missing_bid["spread_price"] == "NOT_CALCULATED"
    _clean(log_dir)


def test_09_multiple_levels():
    log_dir = _logs()
    record = _one(
        "pricing",
        _fixtures().pricing_document(extra_bid="1.09990", extra_ask="1.10030"),
        log_dir,
    )
    assert record["bid"] == "1.10000"
    assert record["bid_levels"] == 2
    assert record["ask_levels"] == 2
    assert "additional_levels_not_used" in record["validation_warnings"]
    _clean(log_dir)


def test_10_missing_timestamp():
    log_dir = _logs()
    record = _one("pricing", _fixtures().pricing_document(include_time=False), log_dir)
    assert record["quote_timestamp"] == "NOT_RETURNED"
    assert record["quote_freshness"] == "QUOTE_FRESHNESS_NOT_VERIFIED"
    assert "missing_timestamp" in record["validation_warnings"]
    _clean(log_dir)


def test_11_malformed_timestamp():
    log_dir = _logs()
    record = _one("pricing", _fixtures().pricing_document(time="yesterday"), log_dir)
    assert record["quote_timestamp"] == "NOT_RETURNED"
    assert "malformed_timestamp" in record["validation_warnings"]
    assert record["quote_freshness"] == "QUOTE_FRESHNESS_NOT_VERIFIED"
    _clean(log_dir)


def test_12_missing_tradeability():
    log_dir = _logs()
    record = _one("pricing", _fixtures().pricing_document(include_tradeable=False), log_dir)
    assert record["tradeable"] == "NOT_RETURNED"
    assert record["tradeable_source"] == "UNVERIFIED"
    _clean(log_dir)


def test_13_missing_home_conversions():
    log_dir = _logs()
    record = _one("pricing", _fixtures().pricing_document(conversions=False), log_dir)
    assert record["home_conversion"] == "HOME_CONVERSION_NOT_VERIFIED"
    assert record["home_conversion_operational_request"] == "NOT_REQUESTED"
    _clean(log_dir)


def test_14_unexpected_extra_fields_are_dropped():
    log_dir = _logs()
    document = _fixtures().account_document(extra={"division": "spread-bet", "note": "ignore-me"})
    record = _one("account", document, log_dir)
    text = json.dumps(record)
    assert "division" not in text
    assert "ignore-me" not in text
    assert "spread-bet" not in text
    assert "unexpected_fields_dropped" in record["validation_warnings"]
    assert record["account_type"] == "NOT_RETURNED"
    _clean(log_dir)


def test_15_token_in_unexpected_field_is_absent():
    log_dir = _logs()
    token = _fixtures().SYNTHETIC_TOKEN
    document = _fixtures().account_document(extra={"comment": f"Bearer {token}"})
    record = _one("account", document, log_dir)
    assert token not in json.dumps(record)
    assert "Bearer" not in json.dumps(record)
    _clean(log_dir)


def test_16_account_id_is_not_persisted():
    log_dir = _logs()
    account_id = _fixtures().SYNTHETIC_ACCOUNT_ID
    document = _fixtures().account_document(extra={"note": account_id})
    record = _one("account", document, log_dir)
    assert account_id not in json.dumps(record)
    assert record["account_id_logged"] is False
    assert record["session_id"] != account_id
    assert not record["session_id"].startswith("001-")
    _clean(log_dir)


def test_17_exception_text_is_not_logged():
    log_dir = _logs()
    writer = _writer()
    exc = _fixtures().exception_with_secret()
    path = writer.write_exception(exc, log_dir=log_dir, clock=CLOCK)
    text = path.read_text(encoding="utf-8")
    assert _fixtures().SYNTHETIC_TOKEN not in text
    assert _fixtures().SYNTHETIC_ACCOUNT_ID not in text
    record = json.loads(text)
    assert record["outcome"] == "REJECTED"
    assert record["error_code"] == "EXCEPTION_CONTAINED"
    assert "DIAGNOSTIC_RECORDED" not in text
    _clean(log_dir)


def test_18_malformed_json():
    log_dir = _logs()
    record = _one("json", "{", log_dir)
    assert record["outcome"] == "REJECTED"
    assert record["error_code"] == "MALFORMED_JSON"
    assert "DIAGNOSTIC_RECORDED" not in json.dumps(record)
    _clean(log_dir)


def test_19_empty_response():
    log_dir = _logs()
    record = _one("account", {}, log_dir)
    assert record["outcome"] == "REJECTED"
    assert record["error_code"] == "EMPTY_RESPONSE"
    assert record.get("home_currency") is None
    _clean(log_dir)


def test_20_incorrect_types():
    log_dir = _logs()
    document = _fixtures().account_document(nav={"bad": True}, balance=1, margin_available=True)
    record = _one("account", document, log_dir)
    assert record["nav"] == "NOT_RETURNED"
    assert record["balance"] == "NOT_RETURNED"
    assert record["margin_available"] == "NOT_RETURNED"
    assert "incorrect_type" in record["validation_warnings"]
    _clean(log_dir)


def test_21_missing_sizing_inputs():
    log_dir = _logs()
    record = _one("sizing", {}, log_dir)
    assert record["instrument"] == "NOT_SUPPLIED"
    assert record["proposed_api_units"] == "NOT_SUPPLIED"
    assert "missing_sizing_input" in record["validation_warnings"]
    assert record["order_payload"] == "NOT_PRODUCED"
    _clean(log_dir)


def test_22_unverified_gbp_pip_value():
    log_dir = _logs()
    record = _one("sizing", _fixtures().sizing_document(pip_value="0.00", source="BOT_CALCULATED"), log_dir)
    assert record["calculated_pip_value"] == "0.00"
    assert record["calculated_pip_value_source"] == "BOT_CALCULATED"
    assert record["gbp_pip_value_status"] == "UNVERIFIED"
    _clean(log_dir)


def test_23_unverified_stake_mapping():
    log_dir = _logs()
    record = _one("sizing", _fixtures().sizing_document(), log_dir)
    assert record["stake_to_unit_mapping"] == "NOT_VERIFIED"
    assert record["sizing_formula_status"] == "NOT_REUSED"
    _clean(log_dir)


def test_24_no_executable_order_payload():
    log_dir = _logs()
    document = _fixtures().sizing_document(extra={"order": {"units": "1"}, "type": "MARKET"})
    record = _one("sizing", document, log_dir)
    text = json.dumps(record)
    assert record["executable_order"] == "NOT_PRODUCED"
    assert record["order_payload"] == "NOT_PRODUCED"
    assert "MARKET" not in text
    assert "OrderCreate" not in text
    assert "PositionClose" not in text
    _clean(log_dir)


def test_25_no_production_imports():
    for name in IMPLEMENTATION:
        tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [(node.module or "").split(".")[0]]
            else:
                continue
            assert not set(modules) & FORBIDDEN_MODULES


def test_26_no_trading_engine_imports():
    banned = ("bot_loop", "oanda_exec", "oanda_client", "trading", "execution", "app")
    for name in IMPLEMENTATION:
        text = (HERE / name).read_text(encoding="utf-8")
        tree = ast.parse(text)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        blob = " ".join(imported)
        for item in banned:
            assert item not in blob


def test_27_no_dns_or_socket_access():
    try:
        socket.getaddrinfo("example.com", 443)
    except AssertionError as exc:
        assert str(exc) == "network_blocked"
    else:
        raise AssertionError("dns_was_not_blocked")
    before = {name for name in sys.modules if name.startswith("r56p2_")}
    _writer()
    loaded = {name for name in sys.modules if name.startswith("r56p2_")} - before
    for name in loaded:
        assert not name.startswith("forex_bot")
        assert "oandapy" not in name


def test_28_live_activation_flags_rejected(capsys):
    log_dir = _logs()
    before = {path.name for path in log_dir.iterdir()}
    writer = _writer()
    for args in (
        ["--live"],
        ["--connect"],
        ["--authenticate"],
        ["--account"],
        ["--account=001-001-0000000-001"],
        ["--unknown"],
        ["--synthetic", "--live"],
        ["practice"],
    ):
        assert writer.launch(args, log_dir=log_dir) == 2
    after = {path.name for path in log_dir.iterdir()}
    assert after == before
    captured = capsys.readouterr()
    assert "No credential prompt" in captured.out
    _clean(log_dir)


def test_29_logs_remain_inside_permitted_directory():
    log_dir = _logs()
    _clean(log_dir)
    writer = _writer()
    paths = writer.write_documents(
        "account",
        _fixtures().account_document(),
        session_id=writer.new_session_id(),
        log_dir=log_dir,
        clock=CLOCK,
    )
    for path in paths:
        assert HERE in path.resolve().parents
        assert "synthetic_logs" in path.resolve().parts
    try:
        writer.write_documents(
            "account",
            _fixtures().account_document(),
            session_id=writer.new_session_id(),
            log_dir=HERE.parent,
            clock=CLOCK,
        )
    except writer.DiagnosticPathRejected as exc:
        assert exc.code == "LOG_PATH_OUTSIDE"
    else:
        raise AssertionError("outside_path_was_accepted")
    assert not any(HERE.parent.glob("r56-diag-*.json"))
    _clean(log_dir)


def test_30_no_secret_values_in_output():
    log_dir = _logs()
    _clean(log_dir)
    writer = _writer()
    assert writer.launch(["--synthetic"], log_dir=log_dir) == 0
    token = _fixtures().SYNTHETIC_TOKEN
    account_id = _fixtures().SYNTHETIC_ACCOUNT_ID
    for path in log_dir.glob("r56-diag-*.json"):
        text = path.read_text(encoding="utf-8")
        assert token not in text
        assert account_id not in text
        assert "Bearer" not in text
        assert "synthetic-alias-not-logged" not in text
    _clean(log_dir)


def test_31_failure_leaves_no_success_record():
    log_dir = _logs()
    _clean(log_dir)
    writer = _writer()
    writer.write_documents("json", "{", session_id=writer.new_session_id(), log_dir=log_dir, clock=CLOCK)
    records = [json.loads(path.read_text(encoding="utf-8")) for path in log_dir.glob("r56-diag-*.json")]
    assert records
    assert all(record["outcome"] == "REJECTED" for record in records)
    assert not any(record["outcome"] == "DIAGNOSTIC_RECORDED" for record in records)
    _clean(log_dir)


def test_32_repeated_runs_do_not_overwrite_unrelated_files():
    log_dir = _logs()
    _clean(log_dir)
    keeper = log_dir / "unrelated-keep.txt"
    keeper.write_text("keep\n", encoding="utf-8")
    writer = _writer()
    first = writer.launch([], log_dir=log_dir)
    second = writer.launch(["--synthetic"], log_dir=log_dir)
    assert first == 0 and second == 0
    assert keeper.read_text(encoding="utf-8") == "keep\n"
    created = list(log_dir.glob("r56-diag-*.json"))
    assert len(created) >= 6
    assert len({path.name for path in created}) == len(created)
    keeper.unlink()
    _clean(log_dir)


def test_33_supplied_margin_used_is_not_an_operational_capture():
    log_dir = _logs()
    record = _one("account", _fixtures().account_document(margin_used="0.00"), log_dir)
    assert record["margin_used"] == "0.00"
    assert record["margin_used_source"] == "BROKER_REPORTED"
    assert record["margin_used_operational_capture"] == "NOT_PARSED_BY_OPERATIONAL_CLIENT"
    _clean(log_dir)


def test_34_supplied_home_conversion_is_not_an_operational_request():
    log_dir = _logs()
    record = _one("pricing", _fixtures().pricing_document(conversions=True), log_dir)
    assert record["home_conversion"]["positive_units_factor"] == "0.74000"
    assert record["home_conversion"]["negative_units_factor"] == "0.74100"
    assert record["home_conversion"]["positive_units_factor"] != record["home_conversion"]["negative_units_factor"]
    assert record["home_conversion_operational_request"] == "NOT_REQUESTED"
    assert record["home_conversion"]["operational_pricing_request"] == "NOT_REQUESTED"
    _clean(log_dir)


def test_operational_sources_remain_unimported():
    assert ROOT.joinpath("forex_bot", "oanda_client.py").is_file()
    assert "forex_bot.oanda_client" not in sys.modules
    assert "forex_bot.config" not in sys.modules
    assert "forex_bot.oanda_exec" not in sys.modules
