"""Offline tests for the R.51 HTTPS adapter. Synthetic values only. No live host traffic."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
from pathlib import Path

import http.client

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


adapter = _load("r51_https_adapter", HERE / "https_adapter.py")
connector = _load("r50_connector_for_r51", HERE.parent / "r50" / "connector.py")
fixtures = _load("r50_fixtures_for_r51", HERE.parent / "r50" / "fixtures.py")
TOKEN = "SYNTHETIC-TOKEN-R51-NOT-REAL"
ACCOUNT = "SYNTHETIC-ACCOUNT-R51-NOT-REAL"


class FakeResponse:
    def __init__(self, status: int, payload: dict | bytes) -> None:
        self.status = status
        self.reads = 0
        self.closed = False
        self.location = ACCOUNT
        if isinstance(payload, bytes):
            self._body = payload
        else:
            self._body = json.dumps(payload).encode("utf-8")

    def read(self, amount: int | None = None) -> bytes:
        self.reads += 1
        if amount is not None and amount < len(self._body):
            return self._body[:amount]
        return self._body

    def close(self) -> None:
        self.closed = True


class FakeConn:
    def __init__(self, status: int, payload: dict | bytes, gate: dict) -> None:
        self.response = FakeResponse(status, payload)
        self.gate = gate
        self.seen: dict | None = None
        self.closed = False

    def request(self, method: str, target: str, body: bytes | None = None, headers: dict | None = None) -> None:
        if self.gate["busy"]:
            raise AssertionError("concurrent")
        self.gate["busy"] = True
        try:
            self.seen = {"method": method, "target": target, "body": body, "headers": headers}
        finally:
            self.gate["busy"] = False

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


class Factory:
    def __init__(self, steps: list[tuple[int, dict | bytes]]) -> None:
        self.steps = steps
        self.opened: list[dict] = []
        self.gate = {"busy": False}
        self.inside = False

    def __call__(self, host: str, timeout: float, context: ssl.SSLContext) -> FakeConn:
        if self.inside:
            raise AssertionError("reentered")
        self.inside = True
        try:
            status, payload = self.steps[len(self.opened)]
            conn = FakeConn(status, payload, self.gate)
            self.opened.append(
                {
                    "host": host,
                    "timeout": timeout,
                    "verify_mode": context.verify_mode,
                    "check_hostname": context.check_hostname,
                    "conn": conn,
                }
            )
            return conn
        finally:
            self.inside = False


def _factory(instruments: dict | None = None, prices: dict | None = None, status: int = 200) -> Factory:
    return Factory(
        [
            (status, instruments if instruments is not None else fixtures.instruments_payload()),
            (200, prices if prices is not None else fixtures.pricing_payload()),
        ]
    )


def _guard_network(test):
    def wrapped() -> None:
        def boom(*_args, **_kwargs):
            raise AssertionError("network")

        original_dns = socket.getaddrinfo
        original_open = socket.create_connection
        original_https = http.client.HTTPSConnection
        socket.getaddrinfo = boom  # type: ignore[assignment]
        socket.create_connection = boom  # type: ignore[assignment]

        class Trap(original_https):  # type: ignore[misc, valid-type]
            def __init__(self, *args, **kwargs):
                raise AssertionError("network")

        http.client.HTTPSConnection = Trap  # type: ignore[misc]
        try:
            test()
        finally:
            socket.getaddrinfo = original_dns
            socket.create_connection = original_open
            http.client.HTTPSConnection = original_https

    return wrapped


def test_tls_certificate_verification_stays_enabled() -> None:
    context = adapter.tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.verify_mode != ssl.CERT_NONE


def test_exchange_builds_two_get_calls_and_stops() -> None:
    factory = _factory()
    document = adapter.run_offline(ACCOUNT, TOKEN, factory)
    assert [item["host"] for item in factory.opened] == [adapter.HOST, adapter.HOST]
    assert [item["timeout"] for item in factory.opened] == [5.0, 5.0]
    assert [item["verify_mode"] for item in factory.opened] == [ssl.CERT_REQUIRED, ssl.CERT_REQUIRED]
    assert [item["check_hostname"] for item in factory.opened] is not None
    assert all(item["check_hostname"] is True for item in factory.opened)
    methods = [item["conn"].seen["method"] for item in factory.opened]
    bodies = [item["conn"].seen["body"] for item in factory.opened]
    targets = [item["conn"].seen["target"] for item in factory.opened]
    assert methods == ["GET", "GET"]
    assert bodies == [None, None]
    assert "/instruments?" in targets[0] and "/pricing?" in targets[1]
    assert "includeHomeConversions=true" not in targets[0]
    assert "includeHomeConversions=true" in targets[1]
    assert all(name in target for target in targets for name in fixtures.SIX)
    assert document["calls_completed"] == 2
    assert document["endpoint_order"] == ["instruments", "pricing"]
    assert all(item["conn"].closed for item in factory.opened)
    budget = adapter.Budget()
    budget.used = 2
    try:
        adapter.exchange(connector.prepare("instruments", ACCOUNT, TOKEN), factory, budget)
    except adapter.Rejected as exc:
        assert str(exc) == adapter.REJECTED
        assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
    else:
        raise AssertionError("third call")
    assert len(factory.opened) == 2


def test_redirect_retry_body_stream_and_foreign_targets_stop_first() -> None:
    redirected = _factory(status=302)
    try:
        adapter.run_offline(ACCOUNT, TOKEN, redirected)
    except adapter.Rejected as exc:
        assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
    else:
        raise AssertionError("redirect")
    assert len(redirected.opened) == 1
    assert redirected.opened[0]["conn"].response.reads == 0

    class Exploding(Factory):
        def __call__(self, host: str, timeout: float, context: ssl.SSLContext) -> FakeConn:
            self.opened.append({"host": host})
            raise RuntimeError("temporary")

    exploding = Exploding([])
    try:
        adapter.run_offline(ACCOUNT, TOKEN, exploding)
    except adapter.Rejected:
        pass
    else:
        raise AssertionError("retry")
    assert len(exploding.opened) == 1

    budget = adapter.Budget()
    prepared = connector.prepare("pricing", ACCOUNT, TOKEN)
    for bad in (
        {**prepared, "method": "POST"},
        {**prepared, "host": "evil.example"},
        {**prepared, "url": "https://evil.example/orders"},
        {**prepared, "body": "{}"},
        {**prepared, "stream": True},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/orders"},
        {**prepared, "redirects": True},
        {**prepared, "retries": 1},
        {**prepared, "timeout_seconds": 30},
    ):
        try:
            adapter.exchange(bad, _factory(), budget)
        except adapter.Rejected as exc:
            assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
        else:
            raise AssertionError("bad request accepted")
    assert budget.used == 0


def test_secrets_do_not_leave_the_process(tmp_path: Path) -> None:
    document = adapter.run_offline(ACCOUNT, TOKEN, _factory())
    blob = json.dumps(document)
    assert TOKEN not in blob and ACCOUNT not in blob
    assert "Bearer" not in blob and "Authorization" not in blob and "https://" not in blob
    assert "liquidity" not in blob
    target = HERE / "secret_should_not_exist.json"
    try:
        adapter.write_clean(target, {"token": TOKEN}, (TOKEN, ACCOUNT))
    except adapter.Rejected as exc:
        assert TOKEN not in str(exc) and ACCOUNT not in str(exc)
    else:
        raise AssertionError("raw write")
    assert not target.exists()
    try:
        adapter.exchange({"path": ACCOUNT}, _factory(), adapter.Budget())
    except adapter.Rejected as exc:
        assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
    else:
        raise AssertionError("short path")


def test_default_launch_and_live_switches_stay_closed() -> None:
    assert adapter.launch([TOKEN, "--live", "APPROVE"]) == 0
    try:
        adapter.enable_live(phrase="APPROVE PHASE B", flag="--live", override=True, constant=True)
    except adapter.LiveTransportDisabled as exc:
        assert str(exc) == adapter.LIVE_DISABLED
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("live switch")
    try:
        adapter.future_credential_entry()
    except adapter.LiveTransportDisabled as exc:
        assert "credential prompt" not in str(exc)
    else:
        raise AssertionError("prompt")
    try:
        adapter.run_offline(ACCOUNT, TOKEN, adapter.blocked_factory)
    except adapter.LiveTransportDisabled as exc:
        assert TOKEN not in str(exc) and ACCOUNT not in str(exc)
    else:
        raise AssertionError("blocked factory")
    try:
        adapter.run_offline(ACCOUNT, TOKEN, http.client.HTTPSConnection)
    except adapter.LiveTransportDisabled:
        pass
    else:
        raise AssertionError("real class")
    completed = subprocess.run(
        [sys.executable, "-B", str(HERE / "https_adapter.py"), "--live", TOKEN],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "Live verification remains unauthorised. No credential prompt. No network connection."
    assert TOKEN not in completed.stdout and ACCOUNT not in completed.stdout


def test_no_production_import_and_no_credential_environment() -> None:
    assert not any(name == "forex_bot.config" or name == "forex_bot.oanda_client" or name.startswith("forex_bot.strategies") for name in sys.modules)
    real_getenv = os.getenv

    def guard(key: str, default: str | None = None) -> str | None:
        upper = str(key).upper()
        if any(part in upper for part in ("OANDA", "TOKEN", "SECRET", "PASSWORD", "ACCOUNT")):
            raise AssertionError("credential env")
        return real_getenv(key, default)

    os.getenv = guard  # type: ignore[assignment]
    try:
        adapter.launch([])
        adapter.tls_context()
        adapter.run_offline(ACCOUNT, TOKEN, _factory())
    finally:
        os.getenv = real_getenv


def test_malformed_unknown_and_missing_conversion_fail_closed() -> None:
    broken = Factory([(200, b"not-json")])
    try:
        adapter.run_offline(ACCOUNT, TOKEN, broken)
    except adapter.Rejected as exc:
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("malformed")
    assert len(broken.opened) == 1

    instruments = fixtures.instruments_payload()
    instruments["instruments"].append({"name": "NZD_USD", "type": "CURRENCY"})
    try:
        adapter.run_offline(ACCOUNT, TOKEN, _factory(instruments=instruments))
    except adapter.Rejected as exc:
        assert "NZD_USD" not in str(exc)
    else:
        raise AssertionError("unknown instrument")

    prices = fixtures.pricing_payload()
    prices["prices"] = "bad"
    try:
        adapter.run_offline(ACCOUNT, TOKEN, _factory(prices=prices))
    except adapter.Rejected:
        pass
    else:
        raise AssertionError("bad structure")

    stripped = fixtures.pricing_payload()
    for item in stripped["prices"]:
        item.pop("quoteHomeConversionFactors")
        item.pop("homeConversions")
    document = adapter.run_offline(ACCOUNT, TOKEN, _factory(prices=stripped))
    blob = json.dumps(document)
    assert "1.35" not in blob
    assert document["rows"][0]["conversion_factors"] == "NOT_RETURNED"
    assert document["schema_rows"][0]["positive_units_factor"] == "NOT_RETURNED"
    assert document["schema_rows"][0]["negative_units_factor"] == "NOT_RETURNED"
    assert document["schema_rows"][0]["account_gain_factor"] == "NOT_RETURNED"
    assert document["schema_rows"][0]["account_loss_factor"] == "NOT_RETURNED"


def test_conversion_factors_and_home_currency_stay_separate() -> None:
    prices = fixtures.pricing_payload()
    prices["prices"][0]["homeConversions"][0]["currency"] = "GBP"
    document = adapter.run_offline(ACCOUNT, TOKEN, _factory(prices=prices))
    row = document["schema_rows"][0]
    assert row["positive_units_factor"] != row["negative_units_factor"]
    assert row["account_gain_factor"] != row["account_loss_factor"]
    assert row["quoted_conversion_currency"] == "GBP"
    assert row["quoted_conversion_currency_is_account_home"] == "NO"
    assert row["account_home_currency"] == adapter.HOME_CURRENCY
    assert document["account_home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert row["stake_settlement"] == "UNKNOWN"
    assert "ACCOUNT_VERIFIED" not in json.dumps(document)
    assert "executable_units" not in json.dumps(document)
    assert document["rows"][5]["spread_pips"] == "3"
    assert document["schema_rows"][5]["pip_location"] == "-2"


def test_preview_and_threads_stay_quiet() -> None:
    preview = adapter.disabled_preview()
    blob = json.dumps(preview)
    assert preview["mode"] == "NETWORK_DISABLED"
    assert preview["live_entry_point"] == "NOT_IMPLEMENTED"
    assert TOKEN not in blob and ACCOUNT not in blob and "https://" not in blob
    before = threading.active_count()
    adapter.run_offline(ACCOUNT, TOKEN, _factory())
    assert threading.active_count() == before


def test_sanitised_schema_file_is_written() -> None:
    document = adapter.run_offline(ACCOUNT, TOKEN, _factory())
    target = HERE / "06_synthetic_session.json"
    adapter.write_clean(target, document, (TOKEN, ACCOUNT))
    saved = target.read_text(encoding="utf-8")
    assert TOKEN not in saved and ACCOUNT not in saved
    assert "SYNTHETIC_TEST_ONLY" in saved
    assert "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED" in saved
    assert document["schema_rows"][0]["type"] == "CURRENCY"
    assert document["schema_rows"][0]["display_precision"] == "5"
    assert document["schema_rows"][0]["tradeable"] == "true"


def test_entire_suite_makes_no_network_call() -> None:
    @_guard_network
    def body() -> None:
        test_tls_certificate_verification_stays_enabled()
        test_exchange_builds_two_get_calls_and_stops()
        test_redirect_retry_body_stream_and_foreign_targets_stop_first()
        test_secrets_do_not_leave_the_process(HERE)
        test_default_launch_and_live_switches_stay_closed()
        test_no_production_import_and_no_credential_environment()
        test_malformed_unknown_and_missing_conversion_fail_closed()
        test_conversion_factors_and_home_currency_stay_separate()
        test_preview_and_threads_stay_quiet()

    body()
