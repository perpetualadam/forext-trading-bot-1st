"""Offline tests for the R.48 GET-only gate. No credentials and no network."""

from __future__ import annotations

import importlib.util
import json
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "data" / "research" / "adaptive_ensemble" / "r48" / "readonly_transport.py"
SOURCE = MODULE_PATH.read_text(encoding="utf-8")
spec = importlib.util.spec_from_file_location("r48_readonly_transport", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_source_has_no_credential_or_production_path() -> None:
    for banned in ("forex_bot", "dotenv", "getenv", "oandapy", "requests", "socket", "Authorization", "Bearer"):
        assert banned not in SOURCE


def test_execution_gate_is_closed_and_does_not_echo_a_secret() -> None:
    calls: list[str] = []

    class Boom(socket.socket):
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            calls.append("socket")
            raise AssertionError("socket opened")

    original = socket.socket
    socket.socket = Boom  # type: ignore[misc]
    try:
        try:
            mod.perform_request(token="secret-value", account_id="SHOULD-NOT-LEAK")
        except mod.GateClosed as exc:
            assert str(exc) == mod.BLOCKED_MESSAGE
            assert "secret-value" not in str(exc)
            assert "SHOULD-NOT-LEAK" not in str(exc)
        else:
            raise AssertionError("gate opened")
    finally:
        socket.socket = original
    assert calls == []
    assert mod.EXECUTION_PERMITTED is False
    assert mod.retry_limit() == 0
    assert 0 < mod.timeout_seconds() <= 10


def test_methods_hosts_and_paths_are_allowlisted() -> None:
    ok_instruments = "/v3/accounts/SYNTHETIC/instruments"
    ok_pricing = "/v3/accounts/SYNTHETIC/pricing"
    mod.assert_request("GET", mod.ALLOWED_HOST, ok_instruments, ("instruments",))
    mod.assert_request("GET", mod.ALLOWED_HOST, ok_pricing, ("instruments", "includeHomeConversions"))
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        try:
            mod.assert_request(method, mod.ALLOWED_HOST, ok_instruments, ("instruments",))
        except mod.GateClosed:
            pass
        else:
            raise AssertionError(method)
    for host in ("api-fxpractice.oanda.com", "api-fxtrade.oanda.com.evil.test", "localhost"):
        try:
            mod.assert_request("GET", host, ok_instruments, ("instruments",))
        except mod.GateClosed:
            pass
        else:
            raise AssertionError(host)
    for path in (
        "/v3/accounts/SYNTHETIC/orders",
        "/v3/accounts/SYNTHETIC/summary",
        "/v3/accounts/SYNTHETIC/candles",
        "/v3/accounts/SYNTHETIC/pricing/stream",
        "/v3/accounts/SYNTHETIC/transactions",
        "/v3/accounts/SYNTHETIC/positions",
        "/v3/accounts/SYNTHETIC/trades",
        "/v3/accounts",
        "/v3/instruments/EUR_USD/candles",
    ):
        try:
            mod.assert_request("GET", mod.ALLOWED_HOST, path, ("instruments",))
        except mod.GateClosed:
            pass
        else:
            raise AssertionError(path)


def test_query_redirect_and_redacted_record() -> None:
    pricing = "/v3/accounts/SYNTHETIC/pricing"
    try:
        mod.assert_request("GET", mod.ALLOWED_HOST, pricing, ("instruments",))
    except mod.GateClosed:
        pass
    else:
        raise AssertionError("pricing query")
    try:
        mod.assert_request("GET", mod.ALLOWED_HOST, pricing, ("instruments", "includeHomeConversions", "since"))
    except mod.GateClosed:
        pass
    else:
        raise AssertionError("extra query")
    for status in (301, 302, 303, 307, 308, 500):
        try:
            mod.accept_status(status)
        except mod.GateClosed:
            pass
        else:
            raise AssertionError(status)
    mod.accept_status(200)
    record = mod.redacted_request("pricing")
    assert record["method"] == "GET"
    assert record["retries"] == 0
    assert record["redirects"] is False
    assert record["body"] is None
    assert record["stream"] is False
    assert "SYNTHETIC" not in json.dumps(record)
    assert "{accountID}" in record["path_pattern"]


def test_instrument_parser_drops_unexpected_fields_and_rejects_a_bad_shape() -> None:
    payload = {
        "accountID": "SHOULD-NOT-APPEAR",
        "instruments": [
            {
                "name": "EUR_USD",
                "type": "CURRENCY",
                "pipLocation": "-4",
                "displayPrecision": 5,
                "tradeUnitsPrecision": 0,
                "minimumTradeSize": "1",
                "maximumOrderUnits": "100",
                "maximumPositionSize": "0",
                "marginRate": "0.03",
                "minimumTrailingStopDistance": "0.0005",
                "guaranteedStopLossOrderMode": "DISABLED",
                "financing": {
                    "longRate": "-0.02",
                    "shortRate": "0.01",
                    "financingDaysOfWeek": [{"dayOfWeek": "WEDNESDAY", "daysCharged": 3, "note": "drop"}],
                },
                "unexpected": "drop-me",
            }
        ],
    }
    rows = mod.parse_instruments(payload)
    blob = json.dumps(rows)
    assert "SHOULD-NOT-APPEAR" not in blob
    assert "drop-me" not in blob
    assert "note" not in blob
    assert rows[0]["pipLocation"] == "-4"
    assert rows[0]["financingDays"] == [{"dayOfWeek": "WEDNESDAY", "daysCharged": 3}]
    missing = mod.parse_instruments({"instruments": [{"name": "GBP_USD"}]})
    assert missing[0]["pipLocation"] == "MISSING"
    try:
        mod.parse_instruments({"prices": []})
    except mod.SchemaRejected:
        pass
    else:
        raise AssertionError("schema")


def test_pricing_keeps_conversion_sides_separate_and_labels_the_spread() -> None:
    payload = {
        "prices": [
            {
                "instrument": "EUR_USD",
                "time": "2026-10-21T18:00:00.000000000Z",
                "tradeable": True,
                "bids": [{"price": "1.10000", "liquidity": 100}],
                "asks": [{"price": "1.10020", "liquidity": 100}],
                "quoteHomeConversionFactors": {"positiveUnits": "0.80", "negativeUnits": "0.81"},
                "homeConversions": [
                    {"currency": "USD", "accountGain": "0.74", "accountLoss": "0.75", "extra": "drop"}
                ],
                "closeoutBid": "drop",
            }
        ]
    }
    rows = mod.parse_pricing(payload, {"EUR_USD": "-4"})
    blob = json.dumps(rows)
    assert "liquidity" not in blob
    assert "closeoutBid" not in blob
    assert "extra" not in blob
    assert rows[0]["spread_pips"] == "2"
    assert rows[0]["spread_class"] == "POINT_IN_TIME_API_SNAPSHOT"
    factors = rows[0]["quoteHomeConversionFactors"]
    assert factors["positiveUnits"] == "0.80"
    assert factors["negativeUnits"] == "0.81"
    assert rows[0]["homeConversions"][0]["accountGain"] != rows[0]["homeConversions"][0]["accountLoss"]
    incomplete = mod.parse_pricing({"prices": [{"instrument": "EUR_USD", "bids": [], "asks": []}]}, {})
    assert incomplete[0]["spread_pips"] == "MISSING"
    assert incomplete[0]["quoteHomeConversionFactors"]["positiveUnits"] == "MISSING"
