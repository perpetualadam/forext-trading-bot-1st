"""Offline tests for the R.52 entry point. Synthetic values only. No live host traffic."""

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


entry = _load("r52_session_entry", HERE / "session_entry.py")
fixtures = _load("r50_fixtures_for_r52", HERE.parent / "r50" / "fixtures.py")
connector = _load("r50_connector_for_r52", HERE.parent / "r50" / "connector.py")
TOKEN = "SYNTHETIC-TOKEN-R52-NOT-REAL"
ACCOUNT = "SYNTHETIC-ACCOUNT-R52-NOT-REAL"


class FakeResponse:
    def __init__(self, status: int, payload: dict | bytes) -> None:
        self.status = status
        self.reads = 0
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


class FakeConn:
    def __init__(self, status: int, payload: dict | bytes) -> None:
        self.response = FakeResponse(status, payload)
        self.seen: dict | None = None
        self.closed = False

    def request(self, method: str, target: str, body: bytes | None = None, headers: dict | None = None) -> None:
        self.seen = {"method": method, "target": target, "body": body, "headers": headers}

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


class Factory:
    def __init__(self, steps: list[tuple[int, dict | bytes]]) -> None:
        self.steps = steps
        self.opened: list[dict] = []

    def __call__(self, host: str, timeout: float, context: ssl.SSLContext) -> FakeConn:
        status, payload = self.steps[len(self.opened)]
        conn = FakeConn(status, payload)
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


def _factory(instruments: dict | None = None, prices: dict | None = None, first_status: int = 200) -> Factory:
    return Factory(
        [
            (first_status, instruments if instruments is not None else fixtures.instruments_payload()),
            (200, prices if prices is not None else fixtures.pricing_payload()),
        ]
    )


class Prepared:
    def __init__(self, host: str, port: int | None = None, timeout: float | None = None, context: ssl.SSLContext | None = None, **kwargs: object) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.kwargs = kwargs
        self.connect_called = False
        self.request_called = False

    def connect(self) -> None:
        self.connect_called = True
        raise AssertionError("connect")

    def request(self, *_args: object, **_kwargs: object) -> None:
        self.request_called = True
        raise AssertionError("request")

    def close(self) -> None:
        self.closed = True


def test_r51_hash_is_pinned() -> None:
    assert entry.r51_adapter_hash() == entry.R51_PIN
    assert entry.R51_PIN == "e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef"


def test_default_launch_is_disabled() -> None:
    assert entry.launch([TOKEN, "--live", "APPROVE", ACCOUNT]) == 0
    completed = subprocess.run(
        [sys.executable, "-B", str(HERE / "session_entry.py"), "--live", TOKEN],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "R52 entry point is disabled. No credential prompt. No network connection."
    assert TOKEN not in completed.stdout and ACCOUNT not in completed.stdout


def test_arguments_and_environment_do_not_enable_live_mode() -> None:
    os.environ["R52_LIVE"] = "1"
    try:
        assert entry.launch(["--live"]) == 0
        try:
            entry.enable_live(flag=True, phrase="APPROVE", live=True)
        except entry.LiveTransportDisabled as exc:
            assert str(exc) == entry.LIVE_DISABLED
        else:
            raise AssertionError("switch")
        try:
            entry.live_session(live=True)
        except entry.LiveTransportDisabled:
            pass
        else:
            raise AssertionError("live session")
    finally:
        os.environ.pop("R52_LIVE", None)


def test_prompts_are_not_used_by_launch_or_default_entry() -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("prompt")

    original_getpass = getpass.getpass
    original_input = __builtins__["input"] if isinstance(__builtins__, dict) else __builtins__.input  # type: ignore[index, union-attr]
    getpass.getpass = boom  # type: ignore[assignment]
    if isinstance(__builtins__, dict):
        __builtins__["input"] = boom  # type: ignore[index]
    else:
        __builtins__.input = boom  # type: ignore[union-attr]
    try:
        assert entry.launch([]) == 0
        try:
            entry.prompt_for_credentials()
        except entry.LiveTransportDisabled as exc:
            assert TOKEN not in str(exc)
        else:
            raise AssertionError("prompt ran")
        entry.run_synthetic(ACCOUNT, TOKEN, _factory())
    finally:
        getpass.getpass = original_getpass
        if isinstance(__builtins__, dict):
            __builtins__["input"] = original_input  # type: ignore[index]
        else:
            __builtins__.input = original_input  # type: ignore[union-attr]


def test_synthetic_credential_entry_stays_in_memory() -> None:
    prompts: list[str] = []

    def account_input(prompt: str) -> str:
        prompts.append(prompt)
        return ACCOUNT

    def token_input(prompt: str) -> str:
        prompts.append(prompt)
        return TOKEN

    credential = entry.prompt_for_credentials(account_input, token_input)
    assert prompts == ["Account identifier: ", "API token: "]
    assert ACCOUNT not in prompts[0] and TOKEN not in prompts[1]
    assert str(credential) == "MemoryCredential()"
    assert ACCOUNT not in repr(credential) and TOKEN not in repr(credential)
    try:
        entry.prompt_for_credentials(lambda _prompt: "bad id", token_input)
    except entry.Rejected as exc:
        assert "bad id" not in str(exc) and TOKEN not in str(exc)
    else:
        raise AssertionError("bad credential")
    def explode(_prompt: str) -> str:
        raise RuntimeError(TOKEN)

    try:
        entry.prompt_for_credentials(explode, token_input)
    except entry.Rejected as exc:
        assert TOKEN not in str(exc) and ACCOUNT not in str(exc)
    else:
        raise AssertionError("reader failure leaked")


def test_prepared_factory_is_fixed_and_does_not_connect() -> None:
    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"
    os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
    try:
        conn = entry.open_prepared_connection(Prepared)
    finally:
        os.environ.pop("HTTPS_PROXY", None)
        os.environ.pop("HTTP_PROXY", None)
    assert conn.host == "api-fxtrade.oanda.com"
    assert conn.port == 443
    assert conn.timeout == 5.0
    assert conn.kwargs == {}
    assert conn.context.verify_mode == ssl.CERT_REQUIRED
    assert conn.context.check_hostname is True
    assert conn.connect_called is False and conn.request_called is False
    try:
        entry.open_prepared_connection(http.client.HTTPSConnection)
    except entry.LiveTransportDisabled as exc:
        assert ACCOUNT not in str(exc)
    else:
        raise AssertionError("live class")

    class Subclass(http.client.HTTPSConnection):
        def __init__(self, *args, **kwargs):
            raise AssertionError("network")

    try:
        entry.open_prepared_connection(Subclass)
    except entry.LiveTransportDisabled:
        pass
    else:
        raise AssertionError("subclass")


def test_two_get_calls_filters_and_sanitised_output() -> None:
    factory = _factory()
    document = entry.run_synthetic(ACCOUNT, TOKEN, factory)
    assert [item["host"] for item in factory.opened] == ["api-fxtrade.oanda.com", "api-fxtrade.oanda.com"]
    assert [item["timeout"] for item in factory.opened] == [5.0, 5.0]
    assert all(item["verify_mode"] == ssl.CERT_REQUIRED and item["check_hostname"] is True for item in factory.opened)
    targets = [item["conn"].seen["target"] for item in factory.opened]
    assert [item["conn"].seen["method"] for item in factory.opened] == ["GET", "GET"]
    assert [item["conn"].seen["body"] for item in factory.opened] == [None, None]
    assert "/instruments?" in targets[0] and "/pricing?" in targets[1]
    assert "includeHomeConversions=true" not in targets[0]
    assert "includeHomeConversions=true" in targets[1]
    assert all(name in target for target in targets for name in fixtures.SIX)
    assert document["calls_completed"] == 2
    assert document["endpoint_order"] == ["instruments", "pricing"]
    assert document["evidence_class"] == "SYNTHETIC_TEST_ONLY"
    assert document["account_home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert len(factory.opened) == 2
    blob = json.dumps(document)
    assert TOKEN not in blob and ACCOUNT not in blob
    assert "Bearer" not in blob and "Authorization" not in blob and "https://" not in blob
    assert "ACCOUNT_VERIFIED" not in blob and "executable_units" not in blob
    assert document["rows"][0]["type"] == "CURRENCY"
    assert document["rows"][0]["stake_settlement"] == "UNKNOWN"
    assert document["rows"][5]["pip_location"] == "-2"
    assert document["rows"][5]["spread_pips"] == "3"
    assert document["historical_ticket"]["api_confirmation"] == "NO"
    assert document["historical_ticket"]["used_as_position_cap"] == "NO"
    assert document["historical_financing_panel"]["api_confirmation"] == "NO"


def test_rejections_fail_closed_without_leaks() -> None:
    budget_body = (ACCOUNT + TOKEN).encode("utf-8")
    try:
        entry.read_bounded(FakeConn(400, budget_body))
    except entry.Rejected as exc:
        assert str(exc) == entry.REJECTED
        assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
    else:
        raise AssertionError("http error")
    failed = FakeConn(400, budget_body)
    try:
        entry.read_bounded(failed)
    except entry.Rejected:
        pass
    assert failed.response.reads == 0 and failed.closed is True

    try:
        entry.parse_body(b"{")
    except entry.Rejected as exc:
        assert str(exc) == entry.REJECTED
        assert "{" not in str(exc)
    else:
        raise AssertionError("malformed")

    oversized = FakeConn(200, b"x" * (entry.MAX_BODY + 1))
    try:
        entry.read_bounded(oversized)
    except entry.Rejected as exc:
        assert ACCOUNT not in str(exc)
    else:
        raise AssertionError("size")

    redirected = _factory(first_status=302)
    try:
        entry.run_synthetic(ACCOUNT, TOKEN, redirected)
    except entry.Rejected as exc:
        assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
    else:
        raise AssertionError("redirect")
    assert len(redirected.opened) == 1
    assert redirected.opened[0]["conn"].response.reads == 0

    class Once(Factory):
        def __call__(self, host: str, timeout: float, context: ssl.SSLContext) -> FakeConn:
            self.opened.append({"host": host})
            raise RuntimeError(ACCOUNT)

    exploding = Once([])
    try:
        entry.run_synthetic(ACCOUNT, TOKEN, exploding)
    except entry.Rejected as exc:
        assert ACCOUNT not in str(exc)
    else:
        raise AssertionError("retry")
    assert len(exploding.opened) == 1

    instruments = fixtures.instruments_payload()
    instruments["instruments"].append({"name": "NZD_USD", "type": "CURRENCY"})
    try:
        entry.run_synthetic(ACCOUNT, TOKEN, _factory(instruments=instruments))
    except entry.Rejected as exc:
        assert "NZD_USD" not in str(exc)
    else:
        raise AssertionError("unknown")

    prices = fixtures.pricing_payload()
    for item in prices["prices"]:
        item.pop("quoteHomeConversionFactors")
        item.pop("homeConversions")
    document = entry.run_synthetic(ACCOUNT, TOKEN, _factory(prices=prices))
    assert "1.35" not in json.dumps(document)
    assert document["rows"][0]["positive_units_factor"] == "NOT_RETURNED"
    assert document["rows"][0]["negative_units_factor"] == "NOT_RETURNED"
    assert document["rows"][0]["account_gain_factor"] == "NOT_RETURNED"
    assert document["rows"][0]["account_loss_factor"] == "NOT_RETURNED"

    broken = Factory([(200, b"not-json")])
    try:
        entry.run_synthetic(ACCOUNT, TOKEN, broken)
    except entry.Rejected as exc:
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("bad json")


def test_foreign_targets_and_bodies_never_reach_a_factory() -> None:
    try:
        entry.run_synthetic(ACCOUNT, TOKEN, http.client.HTTPSConnection)
    except entry.LiveTransportDisabled as exc:
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("live factory")
    prepared = connector.prepare("pricing", ACCOUNT, TOKEN)
    adapter = entry._r51()
    budget = adapter.Budget()
    factory = _factory()
    for bad in (
        {**prepared, "method": "POST"},
        {**prepared, "host": "evil.example"},
        {**prepared, "path": f"/v3/accounts/{ACCOUNT}/orders"},
        {**prepared, "body": "{}"},
        {**prepared, "stream": True},
        {**prepared, "url": "https://evil.example"},
    ):
        try:
            adapter.exchange(bad, factory, budget)
        except adapter.Rejected as exc:
            assert ACCOUNT not in str(exc) and TOKEN not in str(exc)
        else:
            raise AssertionError("accepted")
    assert factory.opened == [] and budget.used == 0


def test_no_secret_stores_or_production_imports() -> None:
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
    try:
        entry.launch([])
        entry.open_prepared_connection(Prepared)
        entry.run_synthetic(ACCOUNT, TOKEN, _factory())
    finally:
        os.getenv = real_getenv
        winreg.OpenKey = real_key
        builtins.open = real_open


def test_write_refuses_secrets_and_keeps_threads_still() -> None:
    target = HERE / "secret_should_not_exist.json"
    try:
        entry.write_clean(target, {"token": TOKEN, "evidence_class": "SYNTHETIC_TEST_ONLY"}, (TOKEN, ACCOUNT))
    except entry.Rejected as exc:
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("wrote secret")
    assert not target.exists()
    before = threading.active_count()
    document = entry.run_synthetic(ACCOUNT, TOKEN, _factory())
    entry.write_clean(HERE / "06_synthetic_output.json", document, (TOKEN, ACCOUNT))
    saved = (HERE / "06_synthetic_output.json").read_text(encoding="utf-8")
    assert TOKEN not in saved and ACCOUNT not in saved and "SYNTHETIC_TEST_ONLY" in saved
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
        test_r51_hash_is_pinned()
        test_default_launch_is_disabled()
        test_arguments_and_environment_do_not_enable_live_mode()
        test_prompts_are_not_used_by_launch_or_default_entry()
        test_synthetic_credential_entry_stays_in_memory()
        test_prepared_factory_is_fixed_and_does_not_connect()
        test_two_get_calls_filters_and_sanitised_output()
        test_rejections_fail_closed_without_leaks()
        test_foreign_targets_and_bodies_never_reach_a_factory()
        test_no_secret_stores_or_production_imports()
    finally:
        socket.getaddrinfo = original_dns
        socket.create_connection = original_open
        http.client.HTTPSConnection = original_https
