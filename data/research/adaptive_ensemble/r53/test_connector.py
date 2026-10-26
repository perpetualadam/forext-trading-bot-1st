"""Offline tests for the R.53 connector. Synthetic values only. No live host traffic."""

from __future__ import annotations

import getpass
import importlib.util
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import winreg
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


entry = _load("r53_connector", HERE / "connector.py")
fixtures = _load("r50_fixtures_for_r53", HERE.parent / "r50" / "fixtures.py")
connector = _load("r50_connector_for_r53", HERE.parent / "r50" / "connector.py")
TOKEN = "SYNTHETIC-TOKEN-R53-NOT-REAL"
ACCOUNT = "SYNTHETIC-ACCOUNT-R53-NOT-REAL"


class Step:
    def __init__(self, mode: str, payload: dict | bytes | None = None, status: int = 200) -> None:
        self.mode = mode
        self.payload = payload
        self.status = status


class FakeResponse:
    def __init__(self, step: Step) -> None:
        self.status = step.status
        self.reads = 0
        if step.mode == "huge":
            self._body = b"x" * (entry.MAX_BODY + 1)
        elif isinstance(step.payload, bytes):
            self._body = step.payload
        else:
            self._body = json.dumps(step.payload).encode("utf-8")

    def read(self, amount: int | None = None) -> bytes:
        self.reads += 1
        return self._body


class Scripted:
    steps: list[Step] = []
    opened: list["Scripted"] = []
    calls = 0

    def __init__(self, host: str, port: int | None = None, timeout: float | None = None, context: ssl.SSLContext | None = None, **kwargs: object) -> None:
        Scripted.calls += 1
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.kwargs = kwargs
        self.step = Scripted.steps[Scripted.calls - 1]
        self.closed = False
        self.seen: dict | None = None
        self.response = FakeResponse(self.step)
        if self.step.mode == "tls":
            raise ssl.SSLError("verify failed")
        Scripted.opened.append(self)

    def request(self, method: str, target: str, body: bytes | None = None, headers: dict | None = None) -> None:
        self.seen = {"method": method, "target": target, "body": body, "headers": headers}
        if self.step.mode == "timeout":
            raise TimeoutError("timed out")

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


def _arm(*steps: Step) -> type[Scripted]:
    Scripted.steps = list(steps)
    Scripted.opened = []
    Scripted.calls = 0
    return Scripted


def _ok_pair(instruments: dict | None = None, prices: dict | None = None) -> type[Scripted]:
    return _arm(
        Step("ok", instruments if instruments is not None else fixtures.instruments_payload()),
        Step("ok", prices if prices is not None else fixtures.pricing_payload()),
        Step("ok", fixtures.pricing_payload()),
    )


def test_prior_hashes_match() -> None:
    found = entry.prior_hashes()
    assert found["r51"] == "e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef"
    assert found["r52"] == "59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56"


def test_default_launch_is_disabled_and_prompts_for_nothing() -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("prompt")

    original_getpass = getpass.getpass
    import builtins

    original_input = builtins.input
    getpass.getpass = boom  # type: ignore[assignment]
    builtins.input = boom  # type: ignore[assignment]
    os.environ["R53_LIVE"] = "1"
    try:
        assert entry.launch([TOKEN, "--live", "APPROVE", ACCOUNT]) == 0
        try:
            entry.prompt_for_credentials()
        except entry.LiveTransportDisabled:
            pass
        else:
            raise AssertionError("prompt")
        try:
            entry.enable_live(flag=True, phrase="APPROVE")
        except entry.LiveTransportDisabled as exc:
            assert str(exc) == entry.LIVE_DISABLED
        else:
            raise AssertionError("switch")
        try:
            entry.future_live_entry()
        except entry.LiveTransportDisabled:
            pass
        else:
            raise AssertionError("future entry")
    finally:
        getpass.getpass = original_getpass
        builtins.input = original_input
        os.environ.pop("R53_LIVE", None)
    completed = subprocess.run(
        [sys.executable, "-B", str(HERE / "connector.py"), "--live", TOKEN],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env={**os.environ, "R53_LIVE": "1"},
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "R53 connector is disabled. No credential prompt. No network connection."
    assert TOKEN not in completed.stdout and ACCOUNT not in completed.stdout


def test_synthetic_session_counts_and_redaction() -> None:
    prompts: list[str] = []

    def account_input(prompt: str) -> str:
        prompts.append(prompt)
        return ACCOUNT

    def token_input(prompt: str) -> str:
        prompts.append(prompt)
        return TOKEN

    credential = entry.prompt_for_credentials(account_input, token_input)
    assert prompts == ["Account identifier: ", "API token: "]
    assert ACCOUNT not in repr(credential) and TOKEN not in repr(credential)
    document = entry.run_synthetic(credential.account_id, credential.token, _ok_pair())
    assert Scripted.calls == 2
    assert [item.host for item in Scripted.opened] == ["api-fxtrade.oanda.com", "api-fxtrade.oanda.com"]
    assert [item.port for item in Scripted.opened] == [443, 443]
    assert [item.timeout for item in Scripted.opened] == [5.0, 5.0]
    assert [item.kwargs for item in Scripted.opened] == [{}, {}]
    assert all(item.context is not None and item.context.verify_mode == ssl.CERT_REQUIRED and item.context.check_hostname is True for item in Scripted.opened)
    assert [item.seen["method"] for item in Scripted.opened] == ["GET", "GET"]
    assert [item.seen["body"] for item in Scripted.opened] == [None, None]
    targets = [item.seen["target"] for item in Scripted.opened]
    assert "/instruments?" in targets[0] and "/pricing?" in targets[1]
    assert "includeHomeConversions=true" not in targets[0] and "includeHomeConversions=true" in targets[1]
    assert all(name in target for target in targets for name in fixtures.SIX)
    assert all(item.closed for item in Scripted.opened)
    assert document["requests_attempted"] == 2
    assert document["successful_http_responses"] == 2
    assert document["validated_sanitised_responses"] == 2
    assert document["endpoint_order"] == ["instruments", "pricing"]
    assert [item["result"] for item in document["endpoint_results"]] == ["SUCCESS", "SUCCESS"]
    assert document["evidence_class"] == "SYNTHETIC_TEST_ONLY"
    assert document["account_specific_api_evidence"] == "NOT_PRODUCED"
    assert document["account_home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert document["rows"][0]["type"] == "CURRENCY"
    assert document["rows"][0]["stake_settlement"] == "UNKNOWN"
    assert document["rows"][5]["pip_location"] == "-2"
    assert document["rows"][5]["spread_pips"] == "3"
    assert document["rows"][0]["positive_units_factor"] != document["rows"][0]["negative_units_factor"]
    assert document["rows"][0]["account_gain_factor"] != document["rows"][0]["account_loss_factor"]
    assert document["historical_ticket"]["api_confirmation"] == "NO"
    assert document["historical_ticket"]["used_as_position_cap"] == "NO"
    assert document["historical_ticket"]["one_pip_is_zero_risk"] == "NO"
    assert document["historical_financing_panel"]["api_confirmation"] == "NO"
    blob = json.dumps(document)
    assert TOKEN not in blob and ACCOUNT not in blob
    assert "Bearer" not in blob and "Authorization" not in blob and "https://" not in blob
    assert "ACCOUNT_VERIFIED" not in blob and "executable_units" not in blob
    assert "1.35" not in blob


def test_failures_keep_separate_counts_and_do_not_retry() -> None:
    http_error = _arm(Step("http", (ACCOUNT + TOKEN).encode("utf-8"), status=302), Step("ok", fixtures.pricing_payload()))
    document = entry.run_synthetic(ACCOUNT, TOKEN, http_error)
    assert document["requests_attempted"] == 1
    assert document["successful_http_responses"] == 0
    assert document["validated_sanitised_responses"] == 0
    assert document["endpoint_results"][0]["error_classification"] == "HTTP_ERROR"
    assert Scripted.calls == 1
    assert Scripted.opened[0].response.reads == 0
    assert ACCOUNT not in json.dumps(document) and TOKEN not in json.dumps(document)

    timed = _arm(Step("timeout", b""), Step("ok", fixtures.pricing_payload()))
    document = entry.run_synthetic(ACCOUNT, TOKEN, timed)
    assert document["requests_attempted"] == 1
    assert document["successful_http_responses"] == 0
    assert document["validated_sanitised_responses"] == 0
    assert document["endpoint_results"][0]["error_classification"] == "TIMEOUT"
    assert Scripted.calls == 1
    assert "timed out" not in json.dumps(document)

    tls = _arm(Step("tls"), Step("ok", fixtures.pricing_payload()))
    document = entry.run_synthetic(ACCOUNT, TOKEN, tls)
    assert document["requests_attempted"] == 1
    assert document["successful_http_responses"] == 0
    assert document["validated_sanitised_responses"] == 0
    assert document["endpoint_results"][0]["error_classification"] == "TLS_FAILURE"
    assert Scripted.calls == 1
    assert "verify failed" not in json.dumps(document)

    broken = _arm(Step("raw", b"{"), Step("ok", fixtures.pricing_payload()))
    document = entry.run_synthetic(ACCOUNT, TOKEN, broken)
    assert document["requests_attempted"] == 1
    assert document["successful_http_responses"] == 1
    assert document["validated_sanitised_responses"] == 0
    assert document["successful_http_responses"] != document["validated_sanitised_responses"]
    assert document["endpoint_results"][0]["error_classification"] == "MALFORMED_JSON"
    assert Scripted.calls == 1

    huge = _arm(Step("huge"), Step("ok", fixtures.pricing_payload()))
    document = entry.run_synthetic(ACCOUNT, TOKEN, huge)
    assert document["requests_attempted"] == 1
    assert document["successful_http_responses"] == 1
    assert document["validated_sanitised_responses"] == 0
    assert document["endpoint_results"][0]["error_classification"] == "RESPONSE_TOO_LARGE"
    assert Scripted.calls == 1


def test_schema_failures_stop_and_reject_bad_numbers() -> None:
    instruments = fixtures.instruments_payload()
    instruments["instruments"].append({"name": "NZD_USD", "type": "CURRENCY"})
    document = entry.run_synthetic(ACCOUNT, TOKEN, _arm(Step("ok", instruments), Step("ok", fixtures.pricing_payload())))
    assert document["requests_attempted"] == 1
    assert document["successful_http_responses"] == 1
    assert document["validated_sanitised_responses"] == 0
    assert document["endpoint_results"][0]["error_classification"] == "SCHEMA_REJECTED"
    assert Scripted.calls == 1
    assert "NZD_USD" not in json.dumps(document)

    prices = fixtures.pricing_payload()
    prices["prices"][0]["bids"] = [{"price": "NaN"}]
    document = entry.run_synthetic(ACCOUNT, TOKEN, _ok_pair(prices=prices))
    assert document["requests_attempted"] == 2
    assert document["successful_http_responses"] == 2
    assert document["validated_sanitised_responses"] == 1
    assert document["validated_sanitised_responses"] != document["successful_http_responses"]
    assert document["endpoint_results"][1]["error_classification"] == "SCHEMA_REJECTED"
    assert document["rows"] == []

    prices = fixtures.pricing_payload()
    prices["prices"][0]["asks"] = [{"price": "1.00000"}]
    prices["prices"][0]["bids"] = [{"price": "1.10000"}]
    document = entry.run_synthetic(ACCOUNT, TOKEN, _ok_pair(prices=prices))
    assert document["validated_sanitised_responses"] == 1
    assert document["endpoint_results"][1]["result"] == "FAILURE"

    prices = fixtures.pricing_payload()
    for item in prices["prices"]:
        item.pop("quoteHomeConversionFactors")
        item.pop("homeConversions")
    document = entry.run_synthetic(ACCOUNT, TOKEN, _ok_pair(prices=prices))
    assert document["validated_sanitised_responses"] == 2
    assert document["rows"][0]["positive_units_factor"] == "NOT_RETURNED"
    assert document["rows"][0]["negative_units_factor"] == "NOT_RETURNED"
    assert document["rows"][0]["account_gain_factor"] == "NOT_RETURNED"
    assert document["rows"][0]["account_loss_factor"] == "NOT_RETURNED"
    assert document["missing_field_status"] == "NOT_RETURNED"
    assert "1.35" not in json.dumps(document)


def test_forbidden_shapes_do_not_open_and_do_not_write() -> None:
    class Boom:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("opened")

    prepared = connector.prepare("pricing", ACCOUNT, TOKEN)
    for bad in (
        {**prepared, "method": "POST"},
        {**prepared, "host": "evil.example"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/orders"},
        {**prepared, "body": "{}"},
        {**prepared, "stream": True},
        {**prepared, "url": "https://evil.example"},
    ):
        try:
            entry.transmit(bad, Boom)
        except entry.Failure as exc:
            assert str(exc) == entry.REJECTED
            assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
        else:
            raise AssertionError("accepted")
    try:
        entry.run_synthetic(ACCOUNT, TOKEN, http.client.HTTPSConnection)
    except entry.LiveTransportDisabled:
        pass
    else:
        raise AssertionError("live class")
    try:
        entry.open_prepared_connection(http.client.HTTPSConnection)
    except entry.LiveTransportDisabled:
        pass
    else:
        raise AssertionError("constructor")

    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"
    try:
        document = entry.run_synthetic(ACCOUNT, TOKEN, _ok_pair())
    finally:
        os.environ.pop("HTTPS_PROXY", None)
    assert Scripted.opened[0].host == "api-fxtrade.oanda.com"
    assert Scripted.opened[0].port == 443
    target = HERE / "secret_should_not_exist.json"
    leaked = dict(document)
    leaked["token"] = TOKEN
    try:
        entry.write_clean(target, leaked, (TOKEN, ACCOUNT))
    except entry.Rejected as exc:
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("wrote secret")
    assert not target.exists()
    extra = dict(document)
    extra["note"] = "unexpected"
    try:
        entry.write_clean(target, extra, (TOKEN, ACCOUNT))
    except entry.Rejected:
        pass
    else:
        raise AssertionError("extra field")
    assert not target.exists()
    partial = entry.run_synthetic(ACCOUNT, TOKEN, _arm(Step("http", b"hidden", status=500)))
    try:
        entry.write_clean(target, partial, (TOKEN, ACCOUNT))
    except entry.Rejected:
        pass
    else:
        raise AssertionError("wrote failure")
    assert not target.exists()
    entry.write_clean(HERE / "06_synthetic_output.json", document, (TOKEN, ACCOUNT))
    saved = (HERE / "06_synthetic_output.json").read_text(encoding="utf-8")
    assert TOKEN not in saved and ACCOUNT not in saved and "SYNTHETIC_TEST_ONLY" in saved


def test_no_secret_stores_production_imports_or_threads() -> None:
    assert "forex_bot.config" not in sys.modules
    assert "forex_bot.oanda_client" not in sys.modules
    real_getenv = os.getenv
    real_open = open
    real_key = winreg.OpenKey

    def guard_getenv(key: str, default: str | None = None) -> str | None:
        upper = str(key).upper()
        if any(part in upper for part in ("OANDA", "TOKEN", "SECRET", "PASSWORD", "ACCOUNT")):
            raise AssertionError("credential env")
        return real_getenv(key, default)

    def guard_open(file: object, *args: object, **kwargs: object):
        if os.path.basename(str(file)) == ".env":
            raise AssertionError("dotenv")
        return real_open(file, *args, **kwargs)

    def guard_key(*_args, **_kwargs):
        raise AssertionError("credential store")

    os.getenv = guard_getenv  # type: ignore[assignment]
    winreg.OpenKey = guard_key  # type: ignore[assignment]
    import builtins

    builtins.open = guard_open  # type: ignore[assignment]
    before = threading.active_count()
    try:
        entry.launch([])
        entry.run_synthetic(ACCOUNT, TOKEN, _ok_pair())
    finally:
        os.getenv = real_getenv
        winreg.OpenKey = real_key
        builtins.open = real_open
    assert threading.active_count() == before


def test_suite_performs_no_network_io() -> None:
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
        test_prior_hashes_match()
        test_default_launch_is_disabled_and_prompts_for_nothing()
        test_synthetic_session_counts_and_redaction()
        test_failures_keep_separate_counts_and_do_not_retry()
        test_schema_failures_stop_and_reject_bad_numbers()
        test_forbidden_shapes_do_not_open_and_do_not_write()
        test_no_secret_stores_production_imports_or_threads()
    finally:
        socket.getaddrinfo = original_dns
        socket.create_connection = original_open
        http.client.HTTPSConnection = original_https
