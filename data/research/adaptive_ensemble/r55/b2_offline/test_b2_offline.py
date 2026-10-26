"""Offline tests for the B2 candidate. No production imports and no live call.

The network-denial fixture blocks DNS, socket creation, and connection attempts.
It is a testing safeguard. It is not a general security sandbox.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def _load():
    name = "r55b2_synthetic_session_under_test"
    path = HERE / "synthetic_session.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


session = _load()
TOKEN = session.fixtures.FIXTURE_TOKEN
ACCOUNT = session.fixtures.FIXTURE_ACCOUNT_ID


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


def _dump(package: dict) -> str:
    return json.dumps(package)


def _ok_pair() -> list[tuple[int, bytes]]:
    return [(200, session.fixtures.instruments_bytes()), (200, session.fixtures.pricing_bytes())]


def _with_prices(mutator) -> list[tuple[int, bytes]]:
    payload = copy.deepcopy(session.fixtures.pricing_payload())
    mutator(payload)
    return [(200, session.fixtures.instruments_bytes()), (200, json.dumps(payload).encode("utf-8"))]


def test_default_launch_is_disabled() -> None:
    assert session.launch([]) == 0
    assert session.launch(["--no-such-mode"]) == 0
    completed = subprocess.run(
        [sys.executable, "-B", str(HERE / "synthetic_session.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "R55 B2 default entry is disabled. No credential prompt. No network connection."
    assert TOKEN not in completed.stdout and ACCOUNT not in completed.stdout


def test_live_activation_is_rejected() -> None:
    os.environ["R55_B2_LIVE"] = "APPROVE"
    try:
        assert session.launch(["--live"]) == 2
        assert session.launch(["--live", TOKEN]) == 0
        try:
            session.run_live()
        except session.Rejected as exc:
            assert str(exc) == session.LIVE_DISABLED
        else:
            raise AssertionError("live")

        class Boom:
            def __init__(self, *_args, **_kwargs) -> None:
                raise AssertionError("constructed")

        try:
            session.run_session(mode="live", connection_class=Boom)
        except session.Rejected as exc:
            assert str(exc) == session.LIVE_DISABLED
        else:
            raise AssertionError("mode")
    finally:
        os.environ.pop("R55_B2_LIVE", None)


def test_normal_execution_uses_builtin_fixtures() -> None:
    package = session.run_offline()
    result = package["result"]
    assert result["validated_sanitised_responses"] == 2
    assert result["evidence_class"] == "SYNTHETIC_TEST_ONLY"
    assert result["broker_pricing"] == "SYNTHETIC_FIXTURE"
    assert [item["path_pattern"] for item in package["planned"]] == [
        "/v3/accounts/{accountID}/instruments",
        "/v3/accounts/{accountID}/pricing",
    ]
    assert result["rows"][0]["spread_pips"] == "2"
    assert result["rows"][5]["spread_pips"] == "4"
    assert ACCOUNT not in _dump(package)


def test_arbitrary_transport_cannot_enter_normal_execution() -> None:
    assert "connection_class" not in session.run_offline.__code__.co_varnames
    assert "run_test_case" not in session.launch.__code__.co_names
    assert "run_live" not in session.launch.__code__.co_names

    class Marked:
        offline_fake = object()

        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("constructed")

    try:
        session.run_session(mode="offline", connection_class=Marked)
    except session.Rejected as exc:
        assert str(exc) == session.LIVE_DISABLED
    else:
        raise AssertionError("injected")
    try:
        session.run_test_case(Marked)
    except session.Rejected as exc:
        assert str(exc) == session.REJECTED
    else:
        raise AssertionError("marker")


def test_exactly_two_get_descriptions() -> None:
    planned = session.plan.plan_two(ACCOUNT)
    assert len(planned) == 2
    assert [item["method"] for item in planned] == ["GET", "GET"]
    assert planned[0]["query"] == {"instruments": session.plan.INSTRUMENT_QUERY}
    assert planned[1]["query"]["includeHomeConversions"] == "true"
    assert set(planned[1]["query"]) == {"instruments", "includeHomeConversions"}


def test_instruments_precede_pricing() -> None:
    planned = session.plan.plan_two(ACCOUNT)
    assert [item["sequence"] for item in planned] == [1, 2]
    assert planned[0]["path_pattern"].endswith("/instruments")
    assert planned[1]["path_pattern"].endswith("/pricing")


def test_third_request_is_not_used() -> None:
    package = session.run_test_case([*_ok_pair(), (401, TOKEN.encode("utf-8"))])
    assert package["result"]["requests_attempted"] == 2
    assert package["result"]["validated_sanitised_responses"] == 2
    assert TOKEN not in _dump(package)


def test_account_summary_is_rejected() -> None:
    try:
        session.plan.reject_kind("summary")
    except session.plan.PlanRejected as exc:
        assert str(exc) == session.plan.REJECTED
    else:
        raise AssertionError("summary")
    forged = dict(session.plan.plan_two(ACCOUNT)[0])
    forged["path_pattern"] = "/v3/accounts/{accountID}/summary"
    try:
        session.plan.validate_description(forged, ACCOUNT)
    except session.plan.PlanRejected:
        pass
    else:
        raise AssertionError("summary description")


def test_order_trade_and_position_endpoints_are_rejected() -> None:
    for kind in ("orders", "trades", "positions", "transactions", "candles"):
        try:
            session.plan.reject_kind(kind)
        except session.plan.PlanRejected as exc:
            assert str(exc) == session.plan.REJECTED and TOKEN not in str(exc)
        else:
            raise AssertionError(kind)


def test_post_put_patch_delete_are_rejected() -> None:
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        forged = dict(session.plan.plan_two(ACCOUNT)[0])
        forged["method"] = method
        try:
            session.plan.validate_description(forged, ACCOUNT)
        except session.plan.PlanRejected:
            pass
        else:
            raise AssertionError(method)


def test_host_and_port_overrides_are_rejected() -> None:
    base = session.plan.plan_two(ACCOUNT)[0]
    for changed in ({"host": "example.invalid"}, {"port": 80}):
        forged = dict(base)
        forged.update(changed)
        try:
            session.plan.validate_description(forged, ACCOUNT)
        except session.plan.PlanRejected:
            pass
        else:
            raise AssertionError(changed)


def test_unexpected_query_parameters_are_rejected() -> None:
    forged = dict(session.plan.plan_two(ACCOUNT)[1])
    forged["query"] = dict(forged["query"])
    forged["query"]["since"] = "1"
    try:
        session.plan.validate_description(forged, ACCOUNT)
    except session.plan.PlanRejected:
        pass
    else:
        raise AssertionError("query")


def test_streaming_redirects_and_retries_are_rejected() -> None:
    base = session.plan.plan_two(ACCOUNT)[0]
    for changed in ({"stream": True}, {"redirects": True}, {"retries": 1}, {"body": b"{}"}):
        forged = dict(base)
        forged.update(changed)
        try:
            session.plan.validate_description(forged, ACCOUNT)
        except session.plan.PlanRejected:
            pass
        else:
            raise AssertionError(changed)


def test_first_failure_prevents_pricing() -> None:
    package = session.run_test_case([(401, b"hidden"), (200, session.fixtures.pricing_bytes())])
    result = package["result"]
    assert result["requests_attempted"] == 1
    assert result["successful_http_responses"] == 0
    assert result["validated_sanitised_responses"] == 0
    assert [item["endpoint"] for item in result["endpoint_results"]] == ["instruments"]
    assert result["rows"] == []


def test_http_errors_fail_closed() -> None:
    samples = [(401, "HTTP_401"), (403, "HTTP_403"), (404, "HTTP_404"), (429, "HTTP_429"), (500, "HTTP_5XX"), (503, "HTTP_5XX")]
    for status, classification in samples:
        package = session.run_test_case([(status, TOKEN.encode("utf-8")), (200, session.fixtures.pricing_bytes())])
        result = package["result"]
        assert result["requests_attempted"] == 1
        assert result["endpoint_results"][0]["error_classification"] == classification
        assert result["endpoint_results"][0]["http_status"] == str(status)
        assert TOKEN not in _dump(package)
        assert "hidden" not in _dump(package)


def test_malformed_json_is_rejected() -> None:
    package = session.run_test_case([(200, b"{"), (200, session.fixtures.pricing_bytes())])
    result = package["result"]
    assert result["requests_attempted"] == 1
    assert result["successful_http_responses"] == 1
    assert result["validated_sanitised_responses"] == 0
    assert result["endpoint_results"][0]["error_classification"] == "MALFORMED_JSON"


def test_oversized_response_is_rejected() -> None:
    raw = b"{" + (b"x" * session.plan.MAX_BODY)
    package = session.run_test_case([(200, raw), (200, session.fixtures.pricing_bytes())])
    result = package["result"]
    assert result["requests_attempted"] == 1
    assert result["validated_sanitised_responses"] == 0
    assert result["endpoint_results"][0]["error_classification"] == "RESPONSE_TOO_LARGE"
    assert "x" * 100 not in _dump(package)


def test_invalid_prices_are_rejected() -> None:
    for bad in ("-1.00000", "0", "NaN", "Infinity"):
        def mutate(payload: dict, price: str = bad) -> None:
            payload["prices"][0]["bids"] = [{"price": price}]

        package = session.run_test_case(_with_prices(mutate))
        assert package["result"]["validated_sanitised_responses"] == 1
        assert package["result"]["endpoint_results"][1]["result"] == "FAILURE"
        assert package["result"]["endpoint_results"][1]["error_classification"] == "SCHEMA_REJECTED"
        assert package["result"]["rows"] == []


def test_bid_greater_than_ask_is_rejected() -> None:
    def mutate(payload: dict) -> None:
        payload["prices"][0]["bids"] = [{"price": "1.20000"}]
        payload["prices"][0]["asks"] = [{"price": "1.10000"}]

    package = session.run_test_case(_with_prices(mutate))
    assert package["result"]["endpoint_results"][1]["error_classification"] == "SCHEMA_REJECTED"
    assert package["result"]["endpoint_results"][1]["field"] == "bid_ask"


def test_missing_instruments_and_prices_are_explicit() -> None:
    instruments = session.fixtures.instruments_payload()
    instruments["instruments"] = [row for row in instruments["instruments"] if row["name"] != "USD_JPY"]
    package = session.run_test_case([(200, json.dumps(instruments).encode("utf-8")), (200, session.fixtures.pricing_bytes())])
    failure = package["result"]["endpoint_results"][0]
    assert failure["error_classification"] == "SCHEMA_REJECTED"
    assert failure["field"] == "missing_instrument"
    assert failure["instrument"] == "USD_JPY"
    assert package["result"]["requests_attempted"] == 1

    def drop_price(payload: dict) -> None:
        payload["prices"] = [row for row in payload["prices"] if row["instrument"] != "GBP_USD"]

    package = session.run_test_case(_with_prices(drop_price))
    failure = package["result"]["endpoint_results"][1]
    assert failure["field"] == "missing_price"
    assert failure["instrument"] == "GBP_USD"
    assert package["result"]["rows"] == []


def test_missing_or_ambiguous_conversions_stay_unresolved() -> None:
    def drop(payload: dict) -> None:
        for item in payload["prices"]:
            item.pop("quoteHomeConversionFactors")
            item.pop("homeConversions")

    missing = session.run_test_case(_with_prices(drop))
    row = missing["result"]["rows"][0]
    assert row["positive_units_factor"] == "NOT_RETURNED"
    assert row["quoted_conversion_currency"] == "NOT_RETURNED"
    assert row["gbp_conversion_suitability"] == "NOT_VERIFIED"
    assert missing["result"]["account_home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
    assert missing["result"]["gbp_conversion_suitability"] == "NOT_VERIFIED"

    def ambiguous(payload: dict) -> None:
        payload["prices"][0]["homeConversions"] = [
            {"currency": "XTS", "accountGain": "0.70", "accountLoss": "0.71"},
            {"currency": "GBP", "accountGain": "0.80", "accountLoss": "0.81"},
        ]

    mixed = session.run_test_case(_with_prices(ambiguous))
    assert mixed["result"]["rows"][0]["quoted_conversion_currency"] == "AMBIGUOUS"
    assert mixed["result"]["rows"][0]["quoted_conversion_currency_is_account_home"] == "NO"
    assert mixed["result"]["account_home_currency"] == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"


def test_timestamps_are_classified_without_an_age_rule() -> None:
    def missing(payload: dict) -> None:
        payload["prices"][0].pop("time")

    package = session.run_test_case(_with_prices(missing))
    assert package["result"]["endpoint_results"][1]["error_classification"] == "MISSING_TIMESTAMP"

    def malformed(payload: dict) -> None:
        payload["prices"][1]["time"] = "yesterday"

    package = session.run_test_case(_with_prices(malformed))
    assert package["result"]["endpoint_results"][1]["error_classification"] == "MALFORMED_TIMESTAMP"

    def old(payload: dict) -> None:
        payload["prices"][0]["time"] = "1999-01-01T00:00:00Z"

    package = session.run_test_case(_with_prices(old))
    assert package["result"]["validated_sanitised_responses"] == 2
    assert package["result"]["quote_staleness_rule"] == "NOT_DEFINED"
    assert package["result"]["rows"][0]["time"] == "1999-01-01T00:00:00Z"


def test_no_quote_staleness_threshold_is_defined() -> None:
    source = (HERE / "response_validation.py").read_text(encoding="utf-8")
    assert "MAX_QUOTE_AGE" not in source
    assert "stale_after" not in source
    package = session.run_offline()
    assert package["result"]["quote_staleness_rule"] == "NOT_DEFINED"
    assert package["result"]["rows"][0]["time"] == "2019-01-02T03:04:05Z"


def test_secrets_do_not_appear() -> None:
    try:
        session.plan.plan_two("")
    except session.plan.PlanRejected as exc:
        assert str(exc) == session.plan.REJECTED
        assert TOKEN not in str(exc) and ACCOUNT not in str(exc)
    else:
        raise AssertionError("blank account")
    package = session.run_test_case([(403, f"Bearer {TOKEN}".encode("utf-8"))])
    blob = _dump(package)
    assert TOKEN not in blob and ACCOUNT not in blob and "Bearer" not in blob and "Authorization" not in blob


def test_failed_run_removes_stale_success_file() -> None:
    target = HERE / "stale_success_should_not_remain.json"
    target.write_text('{"evidence_class": "ACCOUNT_VERIFIED"}\n', encoding="utf-8")
    package = session.run_test_case([(500, b"hidden"), (200, session.fixtures.pricing_bytes())], target)
    assert package["result"]["validated_sanitised_responses"] == 0
    assert not target.exists()
    assert not Path(str(target) + ".tmp").exists()


def test_output_stays_synthetic() -> None:
    target = HERE / "synthetic_case_output.json"
    try:
        package = session.run_test_case(_ok_pair(), target)
        result = package["result"]
        assert result["evidence_class"] == "SYNTHETIC_TEST_ONLY"
        assert result["account_specific_api_evidence"] == "NOT_PRODUCED"
        assert result["authentication"] == "NOT_PERFORMED"
        assert result["account_verified"] == "NO"
        assert result["financing"] == "NOT_VERIFIED"
        assert result["token_permissions"] == "UNKNOWN"
        assert result["executable_trade_sizing"] == "NOT_CALCULATED"
        assert result["strategy_profitability"] == "NOT_ESTABLISHED"
        assert result["spread_bet_stake_map"] == "NOT_VERIFIED"
        assert result["gbp_pip_value"] == "NOT_VERIFIED"
        saved = target.read_text(encoding="utf-8")
        assert "ACCOUNT_VERIFIED" not in saved
        assert "1.35" not in saved
        assert TOKEN not in saved and ACCOUNT not in saved

        def untradeable(payload: dict) -> None:
            payload["prices"][2]["tradeable"] = False

        refused = session.run_test_case(_with_prices(untradeable), target)
        assert refused["result"]["validated_sanitised_responses"] == 1
        assert refused["result"]["endpoint_results"][1]["error_classification"] == "SCHEMA_REJECTED"
        assert refused["result"]["endpoint_results"][1]["field"] == "tradeable"
        assert refused["result"]["rows"] == []
        assert not target.exists()
    finally:
        if target.exists():
            target.unlink()


def test_network_denial_fixture_blocks_dns_sockets_and_connections() -> None:
    probes = (
        lambda: socket.getaddrinfo("api-fxtrade.oanda.com", 443),
        lambda: socket.create_connection(("api-fxtrade.oanda.com", 443)),
        lambda: socket.socket(),
    )
    for probe in probes:
        try:
            probe()
        except AssertionError as exc:
            assert str(exc) == "network"
        else:
            raise AssertionError("network open")


def test_b1_and_dependency_hashes_remain() -> None:
    expected = {
        ROOT / "data/research/adaptive_ensemble/r55/b1/session_main.py": "af9a93edc6779298f819430062e34b48289fced922d65f24a1d62a0982be8a90",
        ROOT / "data/research/adaptive_ensemble/r55/b1/transport.py": "3727df8494d6076a5997d88bd5be2a8fb4dc9a0a5f3428c65dc3f0e4002de20a",
        ROOT / "data/research/adaptive_ensemble/r55/b1/test_session.py": "5f1998d22aee2510014fa831a6eb3f94f0af67ebbcfe7483ce0be523525b6b6d",
        ROOT / "data/research/adaptive_ensemble/r51/https_adapter.py": "e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef",
        ROOT / "data/research/adaptive_ensemble/r52/session_entry.py": "59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56",
        ROOT / "data/research/adaptive_ensemble/r53/connector.py": "7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4",
        ROOT / "data/research/adaptive_ensemble/r54/session_main.py": "50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280",
        ROOT / "data/research/adaptive_ensemble/r55/session_main.py": "5913a190812343a9039570893f6cc96fb30fb2a08a6305b84e0bb7bea3576cf8",
        ROOT / "data/research/adaptive_ensemble/r48/readonly_transport.py": "3ef1be4e565b7e2f783931e66e962ba3264f4be551bda2e4cd87f1705bf3b844",
        ROOT / "data/research/adaptive_ensemble/r50/connector.py": "4520a39688001f4947d06a8c18dc0e404df7271c3ca79b0f62d64812fefab5f8",
        ROOT / "data/research/adaptive_ensemble/r50/fixtures.py": "bf03349d425c27f36f989182a051460d4d7da2535937ccd70019fbb4647a42ee",
    }
    for path, digest in expected.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    for name in ("request_plan.py", "response_validation.py", "synthetic_session.py", "synthetic_fixtures.py"):
        text = (HERE / name).read_text(encoding="utf-8")
        assert "forex_bot" not in text
        assert "urlopen" not in text
        assert "getenv" not in text
        assert "http.client" not in text
        assert "import socket" not in text
        assert "HTTPSConnection(" not in text
