"""Offline full-path tests for the R.54 session. Synthetic values only. No live host traffic."""

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


entry = _load("r54_session_main", HERE / "session_main.py")
fixtures = _load("r50_fixtures_for_r54", HERE.parent / "r50" / "fixtures.py")
TOKEN = "SYNTHETIC-TOKEN-R54-NOT-REAL"
ACCOUNT = "SYNTHETIC-ACCOUNT-R54-NOT-REAL"


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
            self._body = b"x" * (entry._r53().MAX_BODY + 1)
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
        Scripted.opened.append(self)

    def request(self, method: str, target: str, body: bytes | None = None, headers: dict | None = None) -> None:
        self.seen = {"method": method, "target": target, "body": body, "headers": headers}
        if self.step.mode == "timeout":
            raise TimeoutError("timed out")
        if self.step.mode == "tls":
            raise ssl.SSLError("verify failed")

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


def _arm(*steps: Step) -> type[Scripted]:
    Scripted.steps = list(steps)
    Scripted.opened = []
    Scripted.calls = 0
    return Scripted


def _pair(instruments: dict | None = None, prices: dict | None = None) -> type[Scripted]:
    return _arm(
        Step("ok", instruments if instruments is not None else fixtures.instruments_payload()),
        Step("ok", prices if prices is not None else fixtures.pricing_payload()),
        Step("ok", fixtures.pricing_payload()),
    )


def _readers(log: list[str] | None = None):
    def account_input(prompt: str) -> str:
        if log is not None:
            log.append("account")
        assert prompt == "Account identifier: "
        assert ACCOUNT not in prompt
        return ACCOUNT

    def token_input(prompt: str) -> str:
        if log is not None:
            log.append("token")
        assert prompt == "API token: "
        assert TOKEN not in prompt
        return TOKEN

    return account_input, token_input


def _run(*steps: Step, output_path: Path | None = None, log: list[str] | None = None) -> dict:
    account_input, token_input = _readers(log)
    return entry.run_session(account_input, token_input, _arm(*steps), output_path)


def test_hashes_and_default_launch_stay_disabled() -> None:
    found = entry.prior_hashes()
    assert found["r51"] == entry.PINS["r51"][1]
    assert found["r52"] == entry.PINS["r52"][1]
    assert found["r53"] == entry.PINS["r53"][1]

    def boom(*_args, **_kwargs):
        raise AssertionError("prompt")

    import builtins

    original_getpass = getpass.getpass
    original_input = builtins.input
    original_run = subprocess.run
    getpass.getpass = boom  # type: ignore[assignment]
    builtins.input = boom  # type: ignore[assignment]
    entry.LIVE = True
    entry.ENABLED = True
    os.environ["R54_LIVE"] = "APPROVE"
    try:
        assert entry.launch([TOKEN, "--live", "APPROVE", ACCOUNT]) == 0
        try:
            entry.prompt_for_credentials()
        except entry.LiveTransportDisabled:
            pass
        else:
            raise AssertionError("prompt")
        try:
            entry.enable_live(phrase="APPROVE", flag=True, enabled=True)
        except entry.LiveTransportDisabled as exc:
            assert str(exc) == entry.LIVE_DISABLED and TOKEN not in str(exc)
        else:
            raise AssertionError("phrase")
        try:
            entry.future_live_entry(phrase="APPROVE")
        except entry.LiveTransportDisabled:
            pass
        else:
            raise AssertionError("future")
        try:
            entry.run_session(*_readers(), http.client.HTTPSConnection, phrase="APPROVE")  # type: ignore[call-arg]
        except TypeError:
            pass
        else:
            raise AssertionError("phrase argument")
        try:
            entry.run_session(*_readers(), http.client.HTTPSConnection)
        except entry.LiveTransportDisabled as exc:
            assert TOKEN not in str(exc) and ACCOUNT not in str(exc)
        else:
            raise AssertionError("live class")
    finally:
        getpass.getpass = original_getpass
        builtins.input = original_input
        subprocess.run = original_run
        os.environ.pop("R54_LIVE", None)
        del entry.LIVE
        del entry.ENABLED
    completed = subprocess.run(
        [sys.executable, "-B", str(HERE / "session_main.py"), "--live", TOKEN],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env={**os.environ, "R54_LIVE": "APPROVE"},
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "R54 session is disabled. No credential prompt. No network connection."
    assert TOKEN not in completed.stdout and ACCOUNT not in completed.stdout


def test_full_path_preview_transport_and_write() -> None:
    log: list[str] = []
    original_init = Scripted.__init__

    def marking(self, *args, **kwargs):
        log.append("connect")
        original_init(self, *args, **kwargs)

    Scripted.__init__ = marking  # type: ignore[method-assign]
    target = HERE / "06_synthetic_output.json"
    if target.exists():
        target.unlink()
    try:
        package = _run(
            Step("ok", fixtures.instruments_payload()),
            Step("ok", fixtures.pricing_payload()),
            Step("ok", fixtures.pricing_payload()),
            output_path=target,
            log=log,
        )
    finally:
        Scripted.__init__ = original_init  # type: ignore[method-assign]
    assert log == ["account", "token", "connect", "connect"]
    preview = package["preview"]
    result = package["result"]
    assert package["terminated"] is True
    assert preview["live_session_approved"] == "NO"
    assert preview["preview_status"] == "NOT_A_CONNECTION"
    assert preview["host"] == "api-fxtrade.oanda.com"
    assert preview["port"] == 443
    assert preview["method"] == "GET"
    assert preview["endpoints"] == ["instruments", "pricing"]
    assert preview["instruments"] == list(fixtures.SIX)
    assert preview["maximum_requests"] == 2
    assert preview["timeout_seconds"] == 5
    assert preview["certificate_verification"] == "ENABLED"
    assert preview["hostname_verification"] == "ENABLED"
    assert preview["trading_actions"] == "NONE"
    assert preview["credential_permission"] == "UNKNOWN"
    assert preview["account_home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert preview["executable_size"] == "NOT_CALCULATED"
    assert Scripted.calls == 2
    assert [item.host for item in Scripted.opened] == ["api-fxtrade.oanda.com", "api-fxtrade.oanda.com"]
    assert [item.port for item in Scripted.opened] == [443, 443]
    assert [item.timeout for item in Scripted.opened] == [5.0, 5.0]
    assert [item.kwargs for item in Scripted.opened] == [{}, {}]
    assert all(item.context.verify_mode == ssl.CERT_REQUIRED and item.context.check_hostname is True for item in Scripted.opened)
    assert [item.seen["method"] for item in Scripted.opened] == ["GET", "GET"]
    assert [item.seen["body"] for item in Scripted.opened] == [None, None]
    targets = [item.seen["target"] for item in Scripted.opened]
    assert "/instruments?" in targets[0] and "/pricing?" in targets[1]
    assert "includeHomeConversions=true" not in targets[0] and "includeHomeConversions=true" in targets[1]
    assert all(name in target for target in targets for name in fixtures.SIX)
    assert all(item.closed for item in Scripted.opened)
    assert result["requests_attempted"] == 2
    assert result["successful_http_responses"] == 2
    assert result["validated_sanitised_responses"] == 2
    assert result["endpoint_order"] == ["instruments", "pricing"]
    assert result["evidence_class"] == "SYNTHETIC_TEST_ONLY"
    assert result["account_specific_api_evidence"] == "NOT_PRODUCED"
    assert result["rows"][0]["stake_settlement"] == "UNKNOWN"
    assert result["rows"][5]["spread_pips"] == "3"
    assert result["rows"][0]["positive_units_factor"] != result["rows"][0]["negative_units_factor"]
    blob = json.dumps(package)
    assert TOKEN not in blob and ACCOUNT not in blob
    assert "Bearer" not in blob and "Authorization" not in blob and "https://" not in blob
    assert "ACCOUNT_VERIFIED" not in blob and "executable_units" not in blob and "1.35" not in blob
    saved = target.read_text(encoding="utf-8")
    assert TOKEN not in saved and ACCOUNT not in saved and "SYNTHETIC_TEST_ONLY" in saved


def test_accounting_failures_stop_without_retry_or_output() -> None:
    blocked = HERE / "must_not_appear.json"
    if blocked.exists():
        blocked.unlink()
    http_error = _run(Step("http", (ACCOUNT + TOKEN).encode(), status=302), Step("ok", fixtures.pricing_payload()), output_path=blocked)
    result = http_error["result"]
    assert result["requests_attempted"] == 1
    assert result["successful_http_responses"] == 0
    assert result["validated_sanitised_responses"] == 0
    assert result["endpoint_results"][0]["error_classification"] == "HTTP_ERROR"
    assert Scripted.calls == 1 and Scripted.opened[0].response.reads == 0 and Scripted.opened[0].closed is True
    assert not blocked.exists()
    assert ACCOUNT not in json.dumps(http_error) and TOKEN not in json.dumps(http_error)

    timed = _run(Step("timeout", b""), Step("ok", fixtures.pricing_payload()))
    assert timed["result"]["requests_attempted"] == 1
    assert timed["result"]["successful_http_responses"] == 0
    assert timed["result"]["endpoint_results"][0]["error_classification"] == "TIMEOUT"
    assert Scripted.calls == 1 and Scripted.opened[0].closed is True
    assert "timed out" not in json.dumps(timed)

    tls = _run(Step("tls"), Step("ok", fixtures.pricing_payload()))
    assert tls["result"]["requests_attempted"] == 1
    assert tls["result"]["endpoint_results"][0]["error_classification"] == "TLS_FAILURE"
    assert Scripted.calls == 1 and Scripted.opened[0].closed is True
    assert "verify failed" not in json.dumps(tls)

    broken = _run(Step("raw", b"{"), Step("ok", fixtures.pricing_payload()))
    assert broken["result"]["requests_attempted"] == 1
    assert broken["result"]["successful_http_responses"] == 1
    assert broken["result"]["validated_sanitised_responses"] == 0
    assert broken["result"]["endpoint_results"][0]["error_classification"] == "MALFORMED_JSON"
    assert Scripted.calls == 1

    huge = _run(Step("huge"), Step("ok", fixtures.pricing_payload()))
    assert huge["result"]["endpoint_results"][0]["error_classification"] == "RESPONSE_TOO_LARGE"
    assert huge["result"]["validated_sanitised_responses"] == 0
    assert Scripted.calls == 1


def test_schema_rejections_and_missing_conversions() -> None:
    instruments = fixtures.instruments_payload()
    instruments["instruments"].append({"name": "NZD_USD", "type": "CURRENCY"})
    unknown = _run(Step("ok", instruments), Step("ok", fixtures.pricing_payload()))
    assert unknown["result"]["requests_attempted"] == 1
    assert unknown["result"]["validated_sanitised_responses"] == 0
    assert unknown["result"]["endpoint_results"][0]["error_classification"] == "SCHEMA_REJECTED"
    assert Scripted.calls == 1
    assert "NZD_USD" not in json.dumps(unknown)

    prices = fixtures.pricing_payload()
    prices["prices"][0]["bids"] = [{"price": "NaN"}]
    numeric = _run(Step("ok", fixtures.instruments_payload()), Step("ok", prices))
    assert numeric["result"]["requests_attempted"] == 2
    assert numeric["result"]["successful_http_responses"] == 2
    assert numeric["result"]["validated_sanitised_responses"] == 1
    assert numeric["result"]["rows"] == []

    prices = fixtures.pricing_payload()
    prices["prices"][0]["asks"] = [{"price": "1.00000"}]
    prices["prices"][0]["bids"] = [{"price": "1.10000"}]
    crossed = _run(Step("ok", fixtures.instruments_payload()), Step("ok", prices))
    assert crossed["result"]["endpoint_results"][1]["result"] == "FAILURE"

    prices = fixtures.pricing_payload()
    for item in prices["prices"]:
        item.pop("quoteHomeConversionFactors")
        item.pop("homeConversions")
    missing = _run(Step("ok", fixtures.instruments_payload()), Step("ok", prices))
    assert missing["result"]["validated_sanitised_responses"] == 2
    assert missing["result"]["missing_field_status"] == "NOT_RETURNED"
    assert missing["result"]["rows"][0]["positive_units_factor"] == "NOT_RETURNED"
    assert missing["result"]["rows"][0]["account_gain_factor"] == "NOT_RETURNED"
    assert "1.35" not in json.dumps(missing)

    def explode(_prompt: str) -> str:
        raise RuntimeError(TOKEN)

    try:
        entry.run_session(explode, _readers()[1], _pair())
    except entry.Rejected as exc:
        assert str(exc) == entry.REJECTED and TOKEN not in str(exc)
    else:
        raise AssertionError("leaked reader failure")


def test_forbidden_requests_do_not_open_and_bad_output_is_not_written() -> None:
    class Boom:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("opened")

    connector = entry._r53()
    prepared = connector._r50().prepare("pricing", ACCOUNT, TOKEN)
    samples = [
        {**prepared, "method": "POST"},
        {**prepared, "method": "PUT"},
        {**prepared, "method": "DELETE"},
        {**prepared, "host": "evil.example"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/orders"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/summary"},
        {**prepared, "body": "{}"},
        {**prepared, "stream": True},
        {**prepared, "query": {**prepared["query"], "extra": "1"}},
    ]
    for bad in samples:
        try:
            connector.transmit(bad, Boom)
        except connector.Failure as exc:
            assert str(exc) == connector.REJECTED
            assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
        else:
            raise AssertionError("accepted")

    good = _run(Step("ok", fixtures.instruments_payload()), Step("ok", fixtures.pricing_payload()))
    leaked = dict(good["result"])
    leaked["token"] = TOKEN
    target = HERE / "secret_should_not_exist.json"
    try:
        connector.write_clean(target, leaked, (TOKEN, ACCOUNT))
    except connector.Rejected as exc:
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("wrote secret")
    assert not target.exists()
    extra = dict(good["result"])
    extra["note"] = "unexpected"
    try:
        connector.write_clean(target, extra, (TOKEN, ACCOUNT))
    except connector.Rejected:
        pass
    else:
        raise AssertionError("extra field")
    assert not target.exists()


def test_boundaries_imports_and_preservation() -> None:
    assert "forex_bot.config" not in sys.modules
    assert "forex_bot.oanda_client" not in sys.modules
    runtime = [
        HERE / "session_main.py",
        HERE.parent / "r53" / "connector.py",
        HERE.parent / "r50" / "connector.py",
        HERE.parent / "r48" / "readonly_transport.py",
    ]
    for path in runtime:
        text = path.read_text(encoding="utf-8")
        assert "subprocess" not in text
        assert "urlopen" not in text
        assert "forex_bot" not in text
        assert "getenv" not in text
        assert "getpass" not in text
        assert "HTTPSConnection(" not in text
    real_getenv = os.getenv
    real_open = open
    real_key = winreg.OpenKey
    real_popen = subprocess.Popen
    writes: list[str] = []

    def guard_getenv(key: str, default: str | None = None) -> str | None:
        upper = str(key).upper()
        if any(part in upper for part in ("OANDA", "TOKEN", "SECRET", "PASSWORD", "ACCOUNT")):
            raise AssertionError("credential env")
        return real_getenv(key, default)

    def guard_open(file: object, mode: str = "r", *args: object, **kwargs: object):
        if os.path.basename(str(file)) == ".env":
            raise AssertionError("dotenv")
        if any(flag in str(mode) for flag in ("w", "a", "x")):
            writes.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    def guard_key(*_args, **_kwargs):
        raise AssertionError("credential store")

    def guard_popen(*_args, **_kwargs):
        raise AssertionError("subprocess")

    os.getenv = guard_getenv  # type: ignore[assignment]
    winreg.OpenKey = guard_key  # type: ignore[assignment]
    subprocess.Popen = guard_popen  # type: ignore[assignment]
    import builtins

    builtins.open = guard_open  # type: ignore[assignment]
    before = threading.active_count()
    connector = entry._r53()
    connector.MAX_CALLS = 99
    original_loader = entry._r53
    entry._r53 = lambda: connector  # type: ignore[method-assign]
    try:
        entry.launch([])
        failure_path = HERE / "boundary_should_not_write.json"
        _run(Step("http", b"hidden", status=500), output_path=failure_path)
        assert writes == []
        assert not failure_path.exists()
        _run(Step("ok", fixtures.instruments_payload()), Step("ok", fixtures.pricing_payload()))
        assert Scripted.calls == 2
    finally:
        entry._r53 = original_loader  # type: ignore[method-assign]
        os.getenv = real_getenv
        winreg.OpenKey = real_key
        subprocess.Popen = real_popen
        builtins.open = real_open
    assert threading.active_count() == before
    assert entry.prior_hashes()["r53"] == entry.PINS["r53"][1]


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
        test_hashes_and_default_launch_stay_disabled()
        test_full_path_preview_transport_and_write()
        test_accounting_failures_stop_without_retry_or_output()
        test_schema_rejections_and_missing_conversions()
        test_forbidden_requests_do_not_open_and_bad_output_is_not_written()
        test_boundaries_imports_and_preservation()
    finally:
        socket.getaddrinfo = original_dns
        socket.create_connection = original_open
        http.client.HTTPSConnection = original_https
