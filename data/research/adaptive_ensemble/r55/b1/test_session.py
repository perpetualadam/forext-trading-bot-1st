"""Offline full-path tests for the R.55 B1 session. Synthetic values only. The live entry is not called.

The network-denial fixture blocks name lookup, socket creation, and connection attempts
during these tests. It is a testing safeguard. It is not a general security sandbox.
A type check does not prove that an arbitrary class is free of network access.
"""

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

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


entry = _load("r55b1_session_main", HERE / "session_main.py")
fixtures = _load("r50_fixtures_for_r55b1", HERE.parents[1] / "r50" / "fixtures.py")
TOKEN = "SYNTHETIC-TOKEN-R55B1-NOT-REAL"
ACCOUNT = "SYNTHETIC-ACCOUNT-R55B1-NOT-REAL"


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


def _readers(log: list[str] | None = None, answer: str = "CONFIRM PREVIEW"):
    def confirm_input(prompt: str) -> str:
        if log is not None:
            log.append("confirm")
        assert "api-fxtrade.oanda.com" in prompt
        assert "instruments, then pricing" in prompt
        assert "Certificate verification: enabled" in prompt
        assert "Redirects: disabled" in prompt
        assert "Retries: disabled" in prompt
        assert "Trading actions: prohibited" in prompt
        assert "Broker token permissions: UNKNOWN" in prompt
        assert "not API-verified" in prompt
        assert "unverified" in prompt
        assert TOKEN not in prompt and ACCOUNT not in prompt
        assert "https://" not in prompt and "Authorization" not in prompt
        for name in fixtures.SIX:
            assert name in prompt
        return answer

    def account_input(prompt: str) -> str:
        if log is not None:
            log.append("account")
        assert prompt == "Account identifier: "
        return ACCOUNT

    def token_input(prompt: str) -> str:
        if log is not None:
            log.append("token")
        assert prompt == "API token: "
        assert TOKEN not in prompt
        return TOKEN

    return confirm_input, account_input, token_input


def _run(*steps: Step, output_path: Path | None = None, log: list[str] | None = None, answer: str = "CONFIRM PREVIEW") -> dict:
    confirm_input, account_input, token_input = _readers(log, answer)
    return entry.run_test_session(confirm_input, account_input, token_input, _arm(*steps), output_path, "offline")


def test_default_stays_offline_and_live_entry_is_not_called() -> None:
    found = entry.prior_hashes()
    assert found["r52"] == "59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56"
    assert found["r55"] == entry.PINS["r55"][2]
    called = {"live": 0}

    def boom_live() -> int:
        called["live"] += 1
        raise AssertionError("live")

    def boom_prompt(*_args, **_kwargs):
        raise AssertionError("prompt")

    import builtins

    original_getpass = getpass.getpass
    original_input = builtins.input
    original_live = entry.run_live
    getpass.getpass = boom_prompt  # type: ignore[assignment]
    builtins.input = boom_prompt  # type: ignore[assignment]
    entry.run_live = boom_live  # type: ignore[method-assign]
    entry.LIVE = True
    os.environ["R55_LIVE"] = "APPROVE"
    try:
        assert entry.launch([TOKEN, "--live", "CONFIRM PREVIEW", ACCOUNT]) == 0
        assert entry.launch(["--live", TOKEN]) == 0
        assert entry.launch(["CONFIRM PREVIEW"]) == 0
        assert entry.launch(["--live"]) == 2
        assert called["live"] == 0
        try:
            entry.prompt_for_credentials()
        except entry.Rejected:
            pass
        else:
            raise AssertionError("prompt")
        assert entry.run_offline() == 0
        assert called["live"] == 0
    finally:
        getpass.getpass = original_getpass
        builtins.input = original_input
        entry.run_live = original_live
        os.environ.pop("R55_LIVE", None)
        del entry.LIVE
    try:
        entry.run_live()
    except entry.Rejected as exc:
        assert str(exc) == entry.LIVE_DISABLED
    else:
        raise AssertionError("live")

    def refused(_prompt: str) -> str:
        raise AssertionError("callback")

    try:
        entry.run_session(refused, refused, refused, http.client.HTTPSConnection, mode="live")
    except entry.Rejected as exc:
        assert str(exc) == entry.LIVE_DISABLED
    else:
        raise AssertionError("mode")
    try:
        entry.run_session(refused, refused, refused, http.client.HTTPConnection, mode="offline")
    except entry.Rejected as exc:
        assert str(exc) == entry.LIVE_DISABLED
    else:
        raise AssertionError("http")

    class Child(http.client.HTTPSConnection):
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("network")

    class Unmarked:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("network")

    try:
        entry.run_session(refused, refused, refused, Child, mode="offline")
    except entry.Rejected as exc:
        assert str(exc) == entry.LIVE_DISABLED
    else:
        raise AssertionError("subclass")
    try:
        entry.run_session(refused, refused, refused, Unmarked, mode="offline")
    except entry.Rejected as exc:
        assert str(exc) == entry.LIVE_DISABLED
    else:
        raise AssertionError("unmarked")
    labelled = {"evidence_class": entry.LIVE_EVIDENCE}
    try:
        entry._validate(labelled, (TOKEN, ACCOUNT), "offline")
    except entry.Rejected as exc:
        assert str(exc) == entry.LIVE_DISABLED and TOKEN not in str(exc)
    else:
        raise AssertionError("live label")
    completed = subprocess.run(
        [sys.executable, "-B", str(HERE / "session_main.py"), "--offline"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0
    assert "api-fxtrade.oanda.com" in completed.stdout
    assert "SYNTHETIC_TEST_ONLY" in completed.stdout
    assert TOKEN not in completed.stdout and ACCOUNT not in completed.stdout
    assert entry.launch(["--no-such-mode"]) == 0


def test_cancellation_stops_before_credentials() -> None:
    log: list[str] = []
    package = _run(Step("ok", fixtures.instruments_payload()), log=log, answer="no")
    assert log == ["confirm"]
    assert package["confirmed"] is False
    assert package["credentials_requested"] is False
    assert package["result"] is None
    assert package["terminated"] is True
    assert Scripted.calls == 0
    blank = _run(Step("ok", fixtures.instruments_payload()), answer="CONFIRM PREVIEW ")
    assert blank["credentials_requested"] is False and Scripted.calls == 0


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
    assert log == ["confirm", "account", "token", "connect", "connect"]
    preview = package["preview"]
    result = package["result"]
    assert package["confirmed"] is True and package["terminated"] is True
    assert preview["host"] == "api-fxtrade.oanda.com"
    assert preview["port"] == 443
    assert preview["method"] == "GET"
    assert preview["endpoint_order"] == ["instruments", "pricing"]
    assert preview["instruments"] == list(fixtures.SIX)
    assert preview["maximum_requests"] == 2
    assert preview["timeout_seconds"] == 5
    assert preview["certificate_verification"] == "ENABLED"
    assert preview["redirects"] == "DISABLED"
    assert preview["retries"] == "DISABLED"
    assert preview["trading_actions"] == "PROHIBITED"
    assert preview["credential_permission"] == "UNKNOWN"
    assert preview["executable_size"] == "NOT_CALCULATED"
    assert Scripted.calls == 2
    assert [item.host for item in Scripted.opened] == ["api-fxtrade.oanda.com", "api-fxtrade.oanda.com"]
    assert [item.port for item in Scripted.opened] == [443, 443]
    assert [item.timeout for item in Scripted.opened] == [5.0, 5.0]
    assert [item.kwargs for item in Scripted.opened] == [{}, {}]
    assert all(item.context.verify_mode == ssl.CERT_REQUIRED and item.context.check_hostname is True for item in Scripted.opened)
    assert [item.seen["method"] for item in Scripted.opened] == ["GET", "GET"]
    assert [item.seen["body"] for item in Scripted.opened] == [None, None]
    urls = [item.seen["target"] for item in Scripted.opened]
    assert "/instruments?" in urls[0] and "/pricing?" in urls[1]
    assert "includeHomeConversions=true" not in urls[0] and "includeHomeConversions=true" in urls[1]
    assert all(name in url for url in urls for name in fixtures.SIX)
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
    blocked.write_text('{"validated_sanitised_responses": 2, "evidence_class": "SYNTHETIC_TEST_ONLY"}', encoding="utf-8")
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

    labelled = dict(missing["result"])
    labelled["evidence_class"] = "ACCOUNT_VERIFIED"
    try:
        entry._validate(labelled, (TOKEN, ACCOUNT), "offline")
    except entry.Rejected as exc:
        assert str(exc) == entry.REJECTED and TOKEN not in str(exc)
    else:
        raise AssertionError("verified label")

    def explode(_prompt: str) -> str:
        raise RuntimeError(TOKEN)

    try:
        entry.run_test_session(_readers()[0], explode, _readers()[2], _arm(Step("ok", fixtures.instruments_payload())))
    except entry.Rejected as exc:
        assert str(exc) == entry.REJECTED and TOKEN not in str(exc)
    else:
        raise AssertionError("leaked reader failure")


def test_forbidden_requests_do_not_open_and_bad_output_is_not_written() -> None:
    class Boom:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("opened")

    gate = entry._r53()
    sender = entry._transmit()
    prepared = gate._r50().prepare("pricing", ACCOUNT, TOKEN)
    samples = [
        {**prepared, "method": "POST"},
        {**prepared, "method": "PUT"},
        {**prepared, "method": "DELETE"},
        {**prepared, "host": "evil.example"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/orders"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/summary"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/trades"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/positions"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/transactions"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/candles"},
        {**prepared, "body": "{}"},
        {**prepared, "stream": True},
        {**prepared, "query": {**prepared["query"], "extra": "1"}},
    ]
    for bad in samples:
        try:
            sender(bad, Boom, gate)
        except gate.Failure as exc:
            assert str(exc) == gate.REJECTED
            assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
        else:
            raise AssertionError("accepted")

    good = _run(Step("ok", fixtures.instruments_payload()), Step("ok", fixtures.pricing_payload()))
    leaked = dict(good["result"])
    leaked["token"] = TOKEN
    try:
        entry._validate(leaked, (TOKEN, ACCOUNT), "offline")
    except entry.Rejected as exc:
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("token field")
    target = HERE / "secret_should_not_exist.json"
    assert not target.exists()
    extra = dict(good["result"])
    extra["note"] = "unexpected"
    try:
        entry._validate(extra, (TOKEN, ACCOUNT), "offline")
    except entry.Rejected:
        pass
    else:
        raise AssertionError("extra field")
    assert not target.exists()


def test_boundaries_imports_and_preservation() -> None:
    assert "forex_bot.config" not in sys.modules
    assert "forex_bot.oanda_client" not in sys.modules
    for path in (HERE / "transport.py", HERE.parent.parent / "r53" / "connector.py", HERE.parent.parent / "r50" / "connector.py", HERE.parent.parent / "r48" / "readonly_transport.py"):
        text = path.read_text(encoding="utf-8")
        assert "subprocess" not in text
        assert "urlopen" not in text
        assert "forex_bot" not in text
        assert "getenv" not in text
        assert "HTTPSConnection(" not in text
    session_text = (HERE / "session_main.py").read_text(encoding="utf-8")
    assert "forex_bot" not in session_text
    assert "urlopen" not in session_text
    assert "subprocess" not in session_text
    assert "getenv" not in session_text
    assert "HTTPSConnection(" not in session_text
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
    gate = entry._r53()
    gate.MAX_CALLS = 99
    original_loader = entry._r53
    entry._r53 = lambda: gate  # type: ignore[method-assign]
    try:
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
    assert entry.prior_hashes()["r52"] == entry.PINS["r52"][2]
    assert entry.prior_hashes()["r55"] == entry.PINS["r55"][2]
    outside = HERE.parents[4] / "forex_bot" / "bot_loop.py"
    before_hash = entry.prior_hashes()["r53"]
    assert outside.is_file()
    assert before_hash == entry.PINS["r53"][2]


@pytest.fixture(autouse=True)
def deny_network():
    """Block DNS, socket creation, and connections for this test module.

    This is a testing safeguard. It is not a general security sandbox.
    """
    original_dns = socket.getaddrinfo
    original_open = socket.create_connection
    original_socket = socket.socket

    def boom_dns(*_args, **_kwargs):
        raise AssertionError("network")

    def boom_open(*_args, **_kwargs):
        raise AssertionError("network")

    class DeniedSocket(original_socket):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            raise AssertionError("network")

    socket.getaddrinfo = boom_dns  # type: ignore[assignment]
    socket.create_connection = boom_open  # type: ignore[assignment]
    socket.socket = DeniedSocket  # type: ignore[misc]
    try:
        yield
    finally:
        socket.getaddrinfo = original_dns
        socket.create_connection = original_open
        socket.socket = original_socket


def test_marker_cannot_bypass_the_executable() -> None:
    marker = object()

    class Marked:
        offline_fake = marker

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("network")

    class Copied:
        offline_fake = Marked.offline_fake

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("network")

    def refused(_prompt: str) -> str:
        raise AssertionError("callback")

    for client in (Marked, Copied, Scripted):
        try:
            entry.run_session(refused, refused, refused, client, mode="offline")
        except entry.Rejected as exc:
            assert str(exc) == entry.LIVE_DISABLED
        else:
            raise AssertionError("marker bypass")
    assert "run_test_session" not in entry.launch.__code__.co_names
    assert "run_test_session" not in entry.run_offline.__code__.co_names
    assert "run_session" in entry.run_offline.__code__.co_names
    assert "SyntheticTransport" in entry.run_offline.__code__.co_names


def test_test_double_socket_and_dns_are_blocked() -> None:
    seen: list[str] = []
    original_dns = socket.getaddrinfo
    original_open = socket.create_connection
    original_socket = socket.socket

    def boom_dns(*_args, **_kwargs):
        seen.append("dns")
        raise AssertionError("network")

    def boom_open(*_args, **_kwargs):
        seen.append("connect")
        raise AssertionError("network")

    class DeniedSocket(original_socket):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            seen.append("socket")
            raise AssertionError("network")

    socket.getaddrinfo = boom_dns  # type: ignore[assignment]
    socket.create_connection = boom_open  # type: ignore[assignment]
    socket.socket = DeniedSocket  # type: ignore[misc]
    stale = HERE / "socket_should_not_succeed.json"
    stale.write_text('{"ok": true}', encoding="utf-8")
    try:
        probes = (
            ("dns", lambda: socket.getaddrinfo("api-fxtrade.oanda.com", 443)),
            ("connect", lambda: socket.create_connection(("api-fxtrade.oanda.com", 443))),
            ("socket", lambda: socket.socket()),
        )
        for name, call in probes:
            class Probe:
                action = staticmethod(call)

                def __init__(self, *_args: object, **_kwargs: object) -> None:
                    self.action()

            package = entry.run_test_session(*_readers(), Probe, stale, "offline")
            assert name in seen
            assert package["result"]["requests_attempted"] == 1
            assert package["result"]["successful_http_responses"] == 0
            assert package["result"]["validated_sanitised_responses"] == 0
            assert package["result"]["evidence_class"] == "SYNTHETIC_TEST_ONLY"
            assert package["result"]["account_specific_api_evidence"] == "NOT_PRODUCED"
            assert package["result"]["endpoint_results"][0]["error_classification"] == "UNEXPECTED"
        assert not stale.exists()
        dumped = json.dumps(package)
        assert TOKEN not in dumped and ACCOUNT not in dumped
    finally:
        socket.getaddrinfo = original_dns
        socket.create_connection = original_open
        socket.socket = original_socket
        if stale.exists():
            stale.unlink()


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
        test_default_stays_offline_and_live_entry_is_not_called()
        test_cancellation_stops_before_credentials()
        test_full_path_preview_transport_and_write()
        test_accounting_failures_stop_without_retry_or_output()
        test_schema_rejections_and_missing_conversions()
        test_forbidden_requests_do_not_open_and_bad_output_is_not_written()
        test_boundaries_imports_and_preservation()
        test_marker_cannot_bypass_the_executable()
        test_test_double_socket_and_dns_are_blocked()
    finally:
        socket.getaddrinfo = original_dns
        socket.create_connection = original_open
        http.client.HTTPSConnection = original_https
