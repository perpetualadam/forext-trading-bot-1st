"""Offline Gate 2 security tests.

The network-denial fixture blocks DNS, socket creation, and connection attempts.
It is a testing safeguard. It is not a general security sandbox.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
import ssl
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]

B2 = {
    "data/research/adaptive_ensemble/r55/b2_offline/request_plan.py":
        "0ec38d19c4460724d9a71418c568b0178947c1b4faad31cff42156af0febe489",
    "data/research/adaptive_ensemble/r55/b2_offline/response_validation.py":
        "e9377a43df8b65b5fb71ad51a40fcaded5eca9084fbcef257311e6463bea6002",
    "data/research/adaptive_ensemble/r55/b2_offline/synthetic_fixtures.py":
        "014960cef817fde3b37134f0a69e559208dd50b53458fa75067325eb8527fcfc",
    "data/research/adaptive_ensemble/r55/b2_offline/synthetic_session.py":
        "44566d5ca01ece8561809215d283a285cf73fa19d40426386450a50bfc10dfb3",
    "data/research/adaptive_ensemble/r55/b2_offline/test_b2_offline.py":
        "c43c7537e54400bc557e9b7cf004ae44591a0d744d2f35fb8acb3bbb33830446",
}
B1 = {
    "data/research/adaptive_ensemble/r55/b1/session_main.py":
        "af9a93edc6779298f819430062e34b48289fced922d65f24a1d62a0982be8a90",
    "data/research/adaptive_ensemble/r55/b1/transport.py":
        "3727df8494d6076a5997d88bd5be2a8fb4dc9a0a5f3428c65dc3f0e4002de20a",
    "data/research/adaptive_ensemble/r55/b1/test_session.py":
        "5f1998d22aee2510014fa831a6eb3f94f0af67ebbcfe7483ce0be523525b6b6d",
}
PINS = {
    "data/research/adaptive_ensemble/r51/https_adapter.py":
        "e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef",
    "data/research/adaptive_ensemble/r52/session_entry.py":
        "59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56",
    "data/research/adaptive_ensemble/r53/connector.py":
        "7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4",
    "data/research/adaptive_ensemble/r54/session_main.py":
        "50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280",
    "data/research/adaptive_ensemble/r55/session_main.py":
        "5913a190812343a9039570893f6cc96fb30fb2a08a6305b84e0bb7bea3576cf8",
    "data/research/adaptive_ensemble/r48/readonly_transport.py":
        "3ef1be4e565b7e2f783931e66e962ba3264f4be551bda2e4cd87f1705bf3b844",
    "data/research/adaptive_ensemble/r50/connector.py":
        "4520a39688001f4947d06a8c18dc0e404df7271c3ca79b0f62d64812fefab5f8",
    "data/research/adaptive_ensemble/r50/fixtures.py":
        "bf03349d425c27f36f989182a051460d4d7da2535937ccd70019fbb4647a42ee",
}
B3 = {
    "01_architecture_and_request_flow.md": "45009d8ec3b3624fa0852e592be00b2acc2ab7d4c48aa10e8f25306e671e41b0",
    "02_transport_security_spec.md": "e216571e15403443e0bd8f8740f73e83140932f71072b3cfbd77999b66789ecd",
    "03_credential_threat_model.md": "28d3bd149320d484707522fa395bea4a2358b2c9ab5cb897532254890004519d",
    "04_broker_evidence_contract.md": "dca2e176c5296ab2b2266cabc4a9ed339bccdd47de831b78be953f0fac90b7bc",
    "05_offline_security_test_spec.md": "bf899d3fafc38bfe415c6199b998225908fb06066fbe30c83d5d581c0ef3a5a4",
    "06_approval_gates.md": "a3cac34d4cb85761e3dbef278e390eb382151dab06209797eb8f7b309dcd69a7",
    "07_baseline_integrity.md": "314be66c8989ceda50a71ea8fc736d74473e7b378cb964fdae2c980ae7b063ab",
    "08_b3_design_report.md": "5727aa79d9cb32da0c05b8c0b25fde0d5a7171a09310d4f9b52e608c1cefc8e8",
}
OPERATIONAL = {
    "forex_bot/bot_loop.py": "6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796",
    "forex_bot/strategy_meta.py": "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d",
    "forex_bot/ai_ensemble.py": "1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa",
    "forex_bot/rl_agent.py": "2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e",
    "forex_bot/session_rules.py": "1e9ec90f573f1fd8add2a2fa4bab82fe164788242f34e97bbcf428e6f5c4bef1",
    "forex_bot/oanda_client.py": "02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a",
}


def _load(stem: str):
    name = f"r55g2_{stem}"
    path = HERE / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


session = _load("session_controller")
gate = session._load("request_gate")
transport = session._load("https_transport")
creds = session._load("credential_boundary")
evidence = session._load("evidence_writer")
doubles = session._load("synthetic_test_doubles")


class AcceptedContext:
    verify_mode = ssl.CERT_REQUIRED
    check_hostname = True


class WeakContext:
    def __init__(self, mode: object, hostname: object) -> None:
        self.verify_mode = mode
        self.check_hostname = hostname


@pytest.fixture(autouse=True)
def deny_network():
    """Block DNS, socket creation, and connections for this test module."""
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


def _yes(preview: str) -> str:
    assert doubles.TOKEN not in preview
    assert doubles.ACCOUNT not in preview
    assert "api-fxtrade.oanda.com" in preview
    assert "includeHomeConversions=true" in preview
    assert "UNKNOWN" in preview
    return creds.CONFIRM


def _no(_preview: str) -> str:
    return "no"


def _pair(**instrument_kwargs):
    return {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes(), **instrument_kwargs),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }


def _run(tmp_path: Path, ready: dict, confirm=_yes, cancel=None, per=None, budget=None, time_fn=None, provider=None):
    path = tmp_path / "synthetic_output.json"
    path.write_text("OLD SUCCESS\n", encoding="utf-8")
    kinds: list[str] = []

    def factory(kind: str):
        kinds.append(kind)
        if kind not in ready:
            raise AssertionError("unexpected request")
        return ready[kind]

    package = session.run_test_session(
        factory,
        creds.SyntheticProvider() if provider is None else provider,
        confirm,
        AcceptedContext(),
        path,
        per_request=per,
        session_budget=budget,
        time_fn=time_fn,
        cancel=cancel,
    )
    package["made"] = kinds
    package["output"] = path
    return package


def _note(case: str, expected: float, observed: float | None, stopped: bool, second: bool, stale: bool) -> None:
    shown = "none" if observed is None else f"{observed:.4f}"
    print(
        f"GATE2_DEADLINE case={case} expected={expected:.4f} observed={shown} "
        f"stopped={str(stopped).lower()} second_prevented={str(second).lower()} stale_removed={str(stale).lower()}"
    )


def _blob(package: dict) -> str:
    safe = {key: value for key, value in package.items() if key != "output"}
    return json.dumps(safe)


def _pricing(mutator) -> bytes:
    payload = doubles.pricing_payload()
    mutator(payload)
    return json.dumps(payload).encode("utf-8")


def test_project_root_is_the_repository():
    assert (ROOT / "forex_bot" / "bot_loop.py").is_file()


def test_default_cli_is_disabled(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("session entered")

    monkeypatch.setattr(session, "run_test_session", boom)
    monkeypatch.setattr(session, "run_live", boom)
    assert session.launch([]) == 0
    assert session.launch(["plain"]) == 0


@pytest.mark.parametrize("flag", ["--live", "--connect", "--authenticate", "--offline", "--trade"])
def test_live_flags_are_rejected(flag: str, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("session entered")

    monkeypatch.setattr(session, "run_test_session", boom)
    monkeypatch.setattr(session, "run_live", boom)
    assert session.launch([flag]) == 2


def test_run_live_raises_without_a_connection():
    with pytest.raises(gate.GateRejected) as caught:
        session.run_live()
    assert caught.value.classification == gate.LIVE_DISABLED


def test_sealed_factory_does_not_resolve():
    with pytest.raises(gate.GateRejected) as caught:
        transport.sealed_live_factory()
    assert caught.value.classification == gate.LIVE_TRANSPORT_NOT_ACTIVATED


def test_confirmation_refusal_skips_credentials_and_connection(tmp_path: Path):
    provider = creds.SyntheticProvider()
    package = _run(tmp_path, _pair(), confirm=_no, provider=provider)
    assert provider.calls == 0
    assert package["connections_constructed"] == 0
    assert package["stop"] == "CONFIRMATION_REFUSED"
    assert package["file_written"] is False
    assert not package["output"].exists()
    assert doubles.TOKEN not in _blob(package)


def test_cancel_before_credentials(tmp_path: Path):
    provider = creds.SyntheticProvider()
    package = _run(tmp_path, _pair(), cancel=lambda stage: stage == "before_credentials", provider=provider)
    assert provider.calls == 0
    assert package["connections_constructed"] == 0
    assert package["stop"] == "CANCELLED"
    assert not package["output"].exists()


def test_cancel_before_first_request_erases_credentials(tmp_path: Path):
    provider = creds.SyntheticProvider()
    package = _run(tmp_path, _pair(), cancel=lambda stage: stage == "before_first_request", provider=provider)
    assert provider.calls == 1
    assert package["connections_constructed"] == 0
    assert provider.handle is not None
    with pytest.raises(gate.GateRejected):
        provider.handle.token()
    assert str(provider.handle) == "REDACTED"
    assert not package["output"].exists()


def test_real_credential_input_is_not_executable():
    assert creds.hidden_input_available() is False
    assert creds.HIDDEN_INPUT == "NOT_IMPLEMENTED_GATE2"
    with pytest.raises(gate.GateRejected) as caught:
        creds.read_real_credential()
    assert caught.value.classification == gate.REAL_CREDENTIAL_INPUT_NOT_AUTHORISED


def test_deadlines_cannot_be_lengthened(tmp_path: Path):
    provider = creds.SyntheticProvider()
    with pytest.raises(gate.GateRejected):
        session.run_test_session(lambda _kind: doubles.ScriptedDouble(), provider, _yes, AcceptedContext(), per_request=5.1)
    assert provider.calls == 0
    with pytest.raises(gate.GateRejected):
        gate.SessionClock(5.0, 15.1)


def test_synthetic_success_is_labelled_and_redacted(tmp_path: Path):
    package = _run(tmp_path, _pair())
    result = package["result"]
    text = package["output"].read_text(encoding="utf-8")
    assert package["kinds"] == ["instruments", "pricing"]
    assert result["validated_sanitised_responses"] == 2
    assert result["evidence_class"] == "SYNTHETIC_TEST_ONLY"
    assert result["account_specific_api_evidence"] == "NOT_PRODUCED"
    assert result["authentication"] == "AUTHENTICATION_NOT_PERFORMED"
    assert result["account_home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert result["gbp_conversion_suitability"] == "NOT_VERIFIED"
    assert result["spread_bet_stake_map"] == "NOT_VERIFIED"
    assert result["gbp_pip_value"] == "NOT_VERIFIED"
    assert result["financing"] == "NOT_VERIFIED"
    assert result["token_permissions"] == "UNKNOWN"
    assert result["executable_trade_sizing"] == "NOT_CALCULATED"
    assert result["strategy_profitability"] == "NOT_ESTABLISHED"
    assert result["quote_freshness"] == "NOT_VERIFIED"
    assert result["rows"][0]["spread_pips"] == "4"
    assert result["rows"][0]["bid"] == "1.20200"
    assert "9.999" not in text
    assert doubles.TOKEN not in text
    assert doubles.ACCOUNT not in text
    assert "1.35" not in text
    assert "ACCOUNT_VERIFIED" not in text
    first = package["made"]
    assert first == ["instruments", "pricing"]
    instruments = _pair()["instruments"]
    used = _run(tmp_path, _pair())
    recorded = used["result"]
    assert recorded["endpoint_order"] == ["instruments", "pricing"]
    assert instruments.offline_only is True


def test_request_path_stays_out_of_the_file(tmp_path: Path):
    ready = _pair()
    package = _run(tmp_path, ready)
    text = package["output"].read_text(encoding="utf-8")
    assert ready["instruments"].hosts == [gate.HOST]
    assert ready["instruments"].ports == [gate.PORT]
    assert ready["instruments"].paths[0] == f"/v3/accounts/{doubles.ACCOUNT}/instruments"
    assert set(ready["instruments"].queries[0]) == {"instruments"}
    assert ready["pricing"].queries[0]["includeHomeConversions"] == "true"
    assert ready["instruments"].auth_flags == [True]
    assert doubles.TOKEN not in str(ready["instruments"].paths)
    assert doubles.TOKEN not in text
    assert doubles.ACCOUNT not in text


def test_third_response_is_never_constructed(tmp_path: Path):
    queued = [
        doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes()),
        doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
        doubles.ScriptedDouble(status=200, body=b"third"),
    ]

    def factory(kind: str):
        if kind == "pricing" and len(queued) == 1:
            raise AssertionError("third")
        return queued.pop(0)

    path = tmp_path / "synthetic_output.json"
    session.run_test_session(factory, creds.SyntheticProvider(), _yes, AcceptedContext(), path)
    assert len(queued) == 1
    assert queued[0]._body == b"third"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_non_get_is_rejected_before_construction(method: str):
    description = gate.plan_two(creds.ACCOUNT)[0]
    description = dict(description)
    description["method"] = method
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        raise AssertionError("constructed")

    clock = gate.SessionClock()
    clock.start_session()
    with pytest.raises(gate.GateRejected):
        transport.execute_description(factory, description, creds.ACCOUNT, creds.TOKEN, clock, AcceptedContext())
    assert calls["n"] == 0


@pytest.mark.parametrize("kind", ["summary", "orders", "trades", "positions", "transactions", "candles"])
def test_banned_kinds_are_rejected_before_construction(kind: str):
    with pytest.raises(gate.GateRejected):
        gate.reject_kind(kind)
    description = dict(gate.plan_two(creds.ACCOUNT)[0])
    description["path_pattern"] = f"/v3/accounts/{{accountID}}/{kind}"
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return doubles.ScriptedDouble()

    clock = gate.SessionClock()
    clock.start_session()
    with pytest.raises(gate.GateRejected):
        transport.execute_description(factory, description, creds.ACCOUNT, creds.TOKEN, clock, AcceptedContext())
    assert calls["n"] == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("host", "example.invalid"),
        ("port", 80),
        ("retries", 1),
        ("redirects", True),
        ("stream", True),
        ("body", b"x"),
    ],
)
def test_description_overrides_are_rejected_before_construction(field: str, value: object):
    description = dict(gate.describe("instruments", creds.ACCOUNT))
    description[field] = value
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return doubles.ScriptedDouble()

    clock = gate.SessionClock()
    clock.start_session()
    with pytest.raises(gate.GateRejected):
        transport.execute_description(factory, description, creds.ACCOUNT, creds.TOKEN, clock, AcceptedContext())
    assert calls["n"] == 0


def test_raw_url_is_rejected():
    with pytest.raises(gate.GateRejected):
        gate.reject_raw_target("https://api-fxtrade.oanda.com/v3/accounts/abc/instruments")
    description = dict(gate.describe("pricing", creds.ACCOUNT))
    description["url"] = "https://example.invalid"
    with pytest.raises(gate.GateRejected):
        gate.validate_description(description, creds.ACCOUNT)


@pytest.mark.parametrize(
    ("mode", "hostname"),
    [
        (ssl.CERT_NONE, True),
        (ssl.CERT_REQUIRED, False),
        (ssl.CERT_OPTIONAL, True),
    ],
)
def test_weak_tls_is_rejected_before_construction(mode: object, hostname: object):
    description = gate.describe("instruments", creds.ACCOUNT)
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return doubles.ScriptedDouble()

    clock = gate.SessionClock()
    clock.start_session()
    with pytest.raises(gate.GateRejected):
        transport.execute_description(factory, description, creds.ACCOUNT, creds.TOKEN, clock, WeakContext(mode, hostname))
    assert calls["n"] == 0


def test_default_tls_context_meets_the_requirement():
    transport.require_tls(ssl.create_default_context())


def test_non_offline_object_is_rejected_before_resolve():
    description = gate.describe("instruments", creds.ACCOUNT)

    class NotOffline:
        def __init__(self):
            self.events = []

        def resolve(self, *_args):
            self.events.append("resolve")

        def close(self):
            self.events.append("close")

    made = NotOffline()
    clock = gate.SessionClock()
    clock.start_session()
    with pytest.raises(gate.GateRejected):
        transport.execute_description(lambda: made, description, creds.ACCOUNT, creds.TOKEN, clock, AcceptedContext())
    assert made.events == ["close"]


def test_first_http_failure_stops_pricing(tmp_path: Path):
    ready = {
        "instruments": doubles.ScriptedDouble(status=500, body=b"nope"),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready)
    assert package["kinds"] == ["instruments"]
    assert package["result"]["validated_sanitised_responses"] == 0
    assert package["result"]["endpoint_results"][0]["error_classification"] == "HTTP_5XX"
    assert package["result"]["endpoint_results"][0]["http_status"] == "500"
    assert "chunk" not in ready["instruments"].events
    assert package["result"]["rows"] == []
    assert not package["output"].exists()


@pytest.mark.parametrize(
    ("status", "classification"),
    [(401, "HTTP_401"), (403, "HTTP_403"), (404, "HTTP_404"), (429, "HTTP_429"), (500, "HTTP_5XX"), (503, "HTTP_5XX")],
)
def test_http_errors_do_not_decode_a_body(tmp_path: Path, status: int, classification: str):
    ready = {
        "instruments": doubles.ScriptedDouble(status=status, body=doubles.TOKEN.encode("utf-8")),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready)
    assert package["kinds"] == ["instruments"]
    assert package["result"]["endpoint_results"][0]["error_classification"] == classification
    assert package["result"]["endpoint_results"][0]["http_status"] == str(status)
    assert "chunk" not in ready["instruments"].events
    assert doubles.TOKEN not in _blob(package)
    assert not package["output"].exists()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_is_not_followed(status: int):
    ready = doubles.ScriptedDouble(status=status, body=b"elsewhere")
    description = gate.describe("instruments", creds.ACCOUNT)
    clock = gate.SessionClock()
    clock.start_session()
    with pytest.raises(gate.GateRejected) as caught:
        transport.execute_description(lambda: ready, description, creds.ACCOUNT, creds.TOKEN, clock, AcceptedContext())
    assert caught.value.classification == "REDIRECT_NOT_FOLLOWED"
    assert "chunk" not in ready.events
    assert ready.hosts == [gate.HOST]
    assert ready.closed is True


def test_retry_value_and_429_make_only_one_attempt(tmp_path: Path):
    description = dict(gate.describe("pricing", creds.ACCOUNT))
    description["retries"] = 1
    with pytest.raises(gate.GateRejected):
        gate.validate_description(description, creds.ACCOUNT)
    ready = {
        "instruments": doubles.ScriptedDouble(status=429, body=b"slow"),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready)
    assert ready["instruments"].events.count("resolve") == 1
    assert package["kinds"] == ["instruments"]


def test_malformed_json_writes_no_success_file(tmp_path: Path):
    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=b"{"),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready)
    assert package["result"]["endpoint_results"][0]["error_classification"] == "MALFORMED_JSON"
    assert package["kinds"] == ["instruments"]
    assert not package["output"].exists()


def test_oversized_body_is_not_retained(tmp_path: Path):
    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=b"x" * (gate.MAX_BODY + 1), chunk_size=65536),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready)
    assert package["result"]["endpoint_results"][0]["error_classification"] == "RESPONSE_TOO_LARGE"
    assert package["result"]["rows"] == []
    assert not package["output"].exists()
    assert "x" * 100 not in _blob(package)


@pytest.mark.parametrize(
    ("bid", "ask", "field"),
    [("-1", "1.20240", "price"), ("0", "1.20240", "price"), ("NaN", "1.20240", "price"), ("Infinity", "1.20240", "price"), ("1.30", "1.20", "bid_ask")],
)
def test_invalid_prices_are_rejected(tmp_path: Path, bid: str, ask: str, field: str):
    def mutate(payload: dict):
        payload["prices"][0]["bids"][0]["price"] = bid
        payload["prices"][0]["asks"][0]["price"] = ask

    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes()),
        "pricing": doubles.ScriptedDouble(status=200, body=_pricing(mutate)),
    }
    package = _run(tmp_path, ready)
    assert package["result"]["validated_sanitised_responses"] == 1
    assert package["result"]["endpoint_results"][1]["error_classification"] == "SCHEMA_REJECTED"
    assert package["result"]["endpoint_results"][1]["field"] == field
    assert package["result"]["rows"] == []
    assert not package["output"].exists()


def test_missing_conversions_stay_unverified(tmp_path: Path):
    def mutate(payload: dict):
        for item in payload["prices"]:
            item.pop("quoteHomeConversionFactors")
            item.pop("homeConversions")

    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes()),
        "pricing": doubles.ScriptedDouble(status=200, body=_pricing(mutate)),
    }
    package = _run(tmp_path, ready)
    text = package["output"].read_text(encoding="utf-8")
    assert package["result"]["rows"][0]["conversion_state"] == "NOT_RETURNED"
    assert package["result"]["account_home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert "1.35" not in text


def test_missing_and_invalid_timestamps(tmp_path: Path):
    def remove(payload: dict):
        payload["prices"][0].pop("time")

    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes()),
        "pricing": doubles.ScriptedDouble(status=200, body=_pricing(remove)),
    }
    package = _run(tmp_path, ready)
    assert package["result"]["endpoint_results"][1]["error_classification"] == "MISSING_TIMESTAMP"
    assert not package["output"].exists()

    def bad(payload: dict):
        payload["prices"][0]["time"] = "yesterday"

    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes()),
        "pricing": doubles.ScriptedDouble(status=200, body=_pricing(bad)),
    }
    package = _run(tmp_path, ready)
    assert package["result"]["endpoint_results"][1]["error_classification"] == "MALFORMED_TIMESTAMP"


def test_old_timestamp_is_not_treated_as_fresh(tmp_path: Path):
    def old(payload: dict):
        for item in payload["prices"]:
            item["time"] = "1999-12-31T23:59:59Z"

    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes()),
        "pricing": doubles.ScriptedDouble(status=200, body=_pricing(old)),
    }
    package = _run(tmp_path, ready)
    assert package["result"]["validated_sanitised_responses"] == 2
    assert package["result"]["rows"][0]["quote_freshness"] == "NOT_VERIFIED"
    assert package["result"]["quote_staleness_rule"] == "NOT_DEFINED"


def test_second_request_failure_removes_stale_success(tmp_path: Path):
    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes()),
        "pricing": doubles.ScriptedDouble(status=500, body=b"{"),
    }
    package = _run(tmp_path, ready)
    assert package["result"]["requests_attempted"] == 2
    assert package["result"]["validated_sanitised_responses"] == 1
    assert package["result"]["rows"] == []
    assert not package["output"].exists()


def test_reader_exception_does_not_leak_the_synthetic_secret():
    class Exploding(doubles.OfflineDouble):
        def resolve(self, host: str, port: int, timeout: float) -> None:
            raise RuntimeError(doubles.TOKEN + doubles.ACCOUNT)

    description = gate.describe("instruments", creds.ACCOUNT)
    clock = gate.SessionClock()
    clock.start_session()
    with pytest.raises(gate.GateRejected) as caught:
        transport.execute_description(lambda: Exploding(), description, creds.ACCOUNT, creds.TOKEN, clock, AcceptedContext())
    assert doubles.TOKEN not in str(caught.value)
    assert doubles.ACCOUNT not in str(caught.value)
    assert doubles.TOKEN not in repr(caught.value)


def test_secret_in_a_response_field_is_not_written(tmp_path: Path):
    payload = doubles.instruments_payload()
    payload["note"] = doubles.TOKEN
    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=json.dumps(payload).encode("utf-8")),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready)
    text = package["output"].read_text(encoding="utf-8")
    assert doubles.TOKEN not in text
    assert doubles.ACCOUNT not in text


def test_cancel_after_first_request_skips_pricing(tmp_path: Path):
    package = _run(tmp_path, _pair(), cancel=lambda stage: stage == "between_requests")
    assert package["kinds"] == ["instruments"]
    assert package["stop"] == "CANCELLED"
    assert package["result"]["validated_sanitised_responses"] == 1
    assert not package["output"].exists()


def _stall_case(tmp_path: Path, phase: str, later: str):
    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes(), stall_phase=phase, stall_seconds=2.0),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready, per=0.25, budget=15.0)
    stale = not package["output"].exists()
    stopped = package["stop"] == "TIMEOUT" and later not in ready["instruments"].events
    second = "pricing" not in package["kinds"]
    _note(phase, 0.25, package["last_elapsed"], stopped, second, stale)
    assert stopped
    assert second
    assert stale
    assert ready["instruments"].timeouts_seen[phase] <= 0.25
    assert package["last_elapsed"] < 1.0
    assert package["last_elapsed"] > 0.15


def test_stalled_resolve_stops(tmp_path: Path):
    _stall_case(tmp_path, "resolve", "connect")


def test_stalled_connect_stops(tmp_path: Path):
    _stall_case(tmp_path, "connect", "handshake")


def test_stalled_handshake_stops(tmp_path: Path):
    _stall_case(tmp_path, "handshake", "send")


def test_stalled_headers_stop(tmp_path: Path):
    _stall_case(tmp_path, "headers", "chunk")


def test_slow_body_stops_on_the_wall_clock(tmp_path: Path):
    body = b"y" * 1600
    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=body, chunk_pause=0.08, chunk_size=32),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready, per=0.30, budget=15.0)
    stopped = package["stop"] == "TIMEOUT"
    second = "pricing" not in package["kinds"]
    stale = not package["output"].exists()
    _note("slow_body", 0.30, package["last_elapsed"], stopped, second, stale)
    assert stopped
    assert second
    assert stale
    assert 1 <= ready["instruments"].chunks_read <= 10
    assert package["last_elapsed"] < 1.0


def test_combined_pauses_hit_the_session_budget(tmp_path: Path):
    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes(), pause_each=0.12),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready, per=5.0, budget=0.30)
    stopped = package["stop"] == "SESSION_DEADLINE"
    second = "pricing" not in package["kinds"]
    stale = not package["output"].exists()
    _note("session_budget", 0.30, package["last_elapsed"], stopped, second, stale)
    assert stopped
    assert second
    assert stale
    assert package["last_elapsed"] < 1.0
    assert package["last_elapsed"] > 0.2


def test_timeout_after_the_first_success(tmp_path: Path):
    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes()),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes(), stall_phase="connect", stall_seconds=2.0),
    }
    package = _run(tmp_path, ready, per=0.25, budget=15.0)
    stopped = package["stop"] == "TIMEOUT"
    second_prevented = "handshake" not in ready["pricing"].events
    stale = not package["output"].exists()
    _note("after_first_success", 0.25, package["last_elapsed"], stopped, second_prevented, stale)
    assert package["result"]["validated_sanitised_responses"] == 1
    assert stopped
    assert second_prevented
    assert stale
    assert package["last_elapsed"] < 1.0


def test_configured_five_second_cap_stops_a_stall(tmp_path: Path):
    assert gate.PER_REQUEST_TIMEOUT_SECONDS == 5.0
    assert gate.TOTAL_SESSION_DEADLINE_SECONDS == 15.0
    ready = {
        "instruments": doubles.ScriptedDouble(status=200, body=doubles.instruments_bytes(), stall_phase="connect", stall_seconds=30.0),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready, per=5.0, budget=15.0)
    stopped = package["stop"] == "TIMEOUT" and "handshake" not in ready["instruments"].events
    second = "pricing" not in package["kinds"]
    stale = not package["output"].exists()
    _note("configured_per_request", 5.0, package["last_elapsed"], stopped, second, stale)
    assert stopped
    assert second
    assert stale
    assert 4.5 <= package["last_elapsed"] <= 6.0
    assert ready["instruments"].timeouts_seen["connect"] <= 5.0


def test_injected_clock_enforces_the_fifteen_second_constant(tmp_path: Path):
    state = {"arm": False}

    def time_fn() -> float:
        return 15.0 if state["arm"] else 0.0

    class Arm(doubles.ScriptedDouble):
        def close(self) -> None:
            state["arm"] = True
            super().close()

    ready = {
        "instruments": Arm(status=200, body=doubles.instruments_bytes()),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready, per=5.0, budget=15.0, time_fn=time_fn)
    second = "pricing" not in package["kinds"]
    stale = not package["output"].exists()
    _note("injected_session_constant", 15.0, 15.0, package["stop"] == "SESSION_DEADLINE", second, stale)
    assert package["stop"] == "SESSION_DEADLINE"
    assert package["result"]["validated_sanitised_responses"] == 1
    assert second
    assert stale


def test_non_cooperative_block_is_not_preempted(tmp_path: Path):
    ready = {
        "instruments": doubles.ScriptedDouble(
            status=200,
            body=doubles.instruments_bytes(),
            stall_phase="connect",
            stall_seconds=0.25,
            ignore_timeout=True,
        ),
        "pricing": doubles.ScriptedDouble(status=200, body=doubles.pricing_bytes()),
    }
    package = _run(tmp_path, ready, per=0.05, budget=15.0)
    stopped = package["stop"] == "TIMEOUT" and "handshake" not in ready["instruments"].events
    second = "pricing" not in package["kinds"]
    stale = not package["output"].exists()
    _note("non_cooperative_connect", 0.05, package["last_elapsed"], stopped, second, stale)
    print("GATE2_DEADLINE case=non_cooperative_connect preempted=no")
    assert stopped
    assert second
    assert stale
    assert package["last_elapsed"] > 0.05


def test_network_denial_fixture_blocks_dns_and_sockets():
    with pytest.raises(AssertionError, match="network"):
        socket.getaddrinfo("api-fxtrade.oanda.com", 443)
    with pytest.raises(AssertionError, match="network"):
        socket.create_connection(("api-fxtrade.oanda.com", 443))
    with pytest.raises(AssertionError, match="network"):
        socket.socket()


def test_sources_do_not_import_production_or_open_a_live_client():
    banned = (
        "forex_bot",
        "import requests",
        "load_dotenv",
        "getenv",
        "os.environ",
        "urlopen",
        "getpass",
        "input(",
        "oandapy",
        "socket.getaddrinfo(",
        "socket.create_connection(",
        "HTTPSConnection(",
    )
    for path in HERE.glob("*.py"):
        if path.name == "test_gate2_offline.py":
            continue
        text = path.read_text(encoding="utf-8")
        for item in banned:
            assert item not in text, path.name
    assert "forex_bot.config" not in sys.modules
    assert "forex_bot.oanda_client" not in sys.modules


def test_prior_sources_are_unchanged():
    expected = {}
    expected.update(B1)
    expected.update(B2)
    expected.update(PINS)
    expected.update(OPERATIONAL)
    for name, digest in expected.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    design = HERE.parent / "b3_design"
    for name, digest in B3.items():
        assert hashlib.sha256((design / name).read_bytes()).hexdigest() == digest
    b1 = (ROOT / "data/research/adaptive_ensemble/r55/b1/session_main.py").read_text(encoding="utf-8")
    b1_launch = b1.split("def launch", 1)[1].split("def main", 1)[0]
    assert "run_live(" not in b1_launch
    assert "return 2" in b1_launch
    b2 = (ROOT / "data/research/adaptive_ensemble/r55/b2_offline/synthetic_session.py").read_text(encoding="utf-8")
    b2_launch = b2.split("def launch", 1)[1].split("def main", 1)[0]
    assert "run_live(" not in b2_launch
    assert 'raise Rejected(LIVE_DISABLED)' in b2
