"""Offline tests for the R.50 connector. Synthetic values only. No network."""

from __future__ import annotations

import copy
import importlib.util
import json
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


connector = _load("r50_connector", HERE / "connector.py")
fixtures = _load("r50_fixtures", HERE / "fixtures.py")
TOKEN = "SYNTHETIC-TOKEN-R50-NOT-REAL"
ACCOUNT = "SYNTHETIC-ACCOUNT-R50-NOT-REAL"


class Fake:
    def __init__(self, instruments: dict, prices: dict, status: int = 200, fail: bool = False) -> None:
        self.instruments = instruments
        self.prices = prices
        self.status = status
        self.fail = fail
        self.seen: list[dict] = []

    def __call__(self, prepared: dict) -> dict:
        self.seen.append(prepared)
        if self.fail:
            raise RuntimeError("temporary")
        kind = "pricing" if str(prepared.get("path", "")).endswith("/pricing") else "instruments"
        payload = self.prices if kind == "pricing" else self.instruments
        return {"status": self.status, "payload": payload}


def _run(fake: Fake | None = None) -> dict:
    transport = fake or Fake(fixtures.instruments_payload(), fixtures.pricing_payload())
    return connector.run_synthetic(ACCOUNT, TOKEN, transport)


def test_01_default_launch_makes_no_network_call() -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("network")

    original_dns = socket.getaddrinfo
    original_open = socket.create_connection
    socket.getaddrinfo = boom  # type: ignore[assignment]
    socket.create_connection = boom  # type: ignore[assignment]
    try:
        assert connector.launch([]) == 0
        completed = subprocess.run(
            [sys.executable, "-B", str(HERE / "connector.py"), "--live", TOKEN],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        socket.getaddrinfo = original_dns
        socket.create_connection = original_open
    assert completed.returncode == 0
    assert TOKEN not in completed.stdout
    assert ACCOUNT not in completed.stdout
    assert "unauthorised" in completed.stdout


def test_02_default_launch_does_not_request_credentials() -> None:
    assert "credential prompt" in "No credential prompt"
    text = "Live verification remains unauthorised. No credential prompt. No network connection."
    assert connector.launch([TOKEN, ACCOUNT]).__class__ is int
    completed = subprocess.run(
        [sys.executable, "-B", str(HERE / "connector.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.stdout.strip() == text


def test_03_no_production_imports() -> None:
    assert not any(name.startswith("forex_bot") for name in sys.modules)


def test_04_only_get_is_prepared() -> None:
    fake = Fake(fixtures.instruments_payload(), fixtures.pricing_payload())
    _run(fake)
    assert {item["method"] for item in fake.seen} == {"GET"}


def test_05_only_two_templates() -> None:
    fake = Fake(fixtures.instruments_payload(), fixtures.pricing_payload())
    _run(fake)
    endings = [item["path"].rsplit("/", 1)[-1] for item in fake.seen]
    assert endings == ["instruments", "pricing"]


def test_06_fixed_host() -> None:
    fake = Fake(fixtures.instruments_payload(), fixtures.pricing_payload())
    _run(fake)
    assert {item["host"] for item in fake.seen} == {"api-fxtrade.oanda.com"}


def test_07_arbitrary_url_is_rejected_before_transport() -> None:
    fake = Fake(fixtures.instruments_payload(), fixtures.pricing_payload())
    try:
        connector.prepare("instruments", ACCOUNT, TOKEN, url="https://evil.example/orders")
    except connector.Rejected:
        pass
    else:
        raise AssertionError("url accepted")
    assert fake.seen == []


def test_08_redirect_is_not_followed() -> None:
    fake = Fake(fixtures.instruments_payload(), fixtures.pricing_payload(), status=302)
    try:
        _run(fake)
    except connector.Rejected:
        pass
    else:
        raise AssertionError("redirect")
    assert len(fake.seen) == 1
    assert fake.seen[0]["redirects"] is False


def test_09_failure_is_not_retried() -> None:
    fake = Fake(fixtures.instruments_payload(), fixtures.pricing_payload(), fail=True)
    try:
        _run(fake)
    except connector.Rejected:
        pass
    else:
        raise AssertionError("retry")
    assert len(fake.seen) == 1
    assert fake.seen[0]["retries"] == 0


def test_10_streaming_is_rejected() -> None:
    try:
        connector.prepare("pricing", ACCOUNT, TOKEN, stream=True)
    except connector.Rejected:
        pass
    else:
        raise AssertionError("stream")


def test_11_request_body_is_rejected() -> None:
    try:
        connector.prepare("pricing", ACCOUNT, TOKEN, body={"order": 1})
    except connector.Rejected:
        pass
    else:
        raise AssertionError("body")


def test_12_timeout_is_short() -> None:
    prepared = connector.prepare("instruments", ACCOUNT, TOKEN)
    assert 0 < prepared["timeout_seconds"] <= 10
    assert prepared["body"] is None
    assert prepared["stream"] is False


def test_13_to_17_secrets_do_not_leak_and_raw_payload_is_not_written() -> None:
    document = _run()
    blob = json.dumps(document)
    assert TOKEN not in blob
    assert ACCOUNT not in blob
    assert "Bearer" not in blob
    assert "liquidity" not in blob
    try:
        connector.run_synthetic("", TOKEN, Fake(fixtures.instruments_payload(), fixtures.pricing_payload()))
    except connector.Rejected as exc:
        assert TOKEN not in str(exc)
        assert ACCOUNT not in str(exc)
    else:
        raise AssertionError("empty account")
    target = HERE / "secret_should_not_exist.json"
    try:
        connector.write_clean(target, {"token": TOKEN}, (TOKEN,))
    except connector.Rejected:
        pass
    else:
        raise AssertionError("raw write")
    assert not target.exists()


def test_18_instrument_filter_is_the_six_names() -> None:
    fake = Fake(fixtures.instruments_payload(), fixtures.pricing_payload())
    _run(fake)
    expected = ",".join(fixtures.SIX)
    assert {item["query"]["instruments"] for item in fake.seen} == {expected}


def test_19_unknown_instrument_is_rejected() -> None:
    payload = fixtures.instruments_payload()
    payload["instruments"].append({"name": "NZD_USD", "type": "CURRENCY"})
    fake = Fake(payload, fixtures.pricing_payload())
    try:
        _run(fake)
    except connector.Rejected as exc:
        assert "NZD_USD" not in str(exc)
    else:
        raise AssertionError("unknown instrument")


def test_20_missing_field_is_not_invented() -> None:
    payload = fixtures.instruments_payload()
    del payload["instruments"][0]["marginRate"]
    document = _run(Fake(payload, fixtures.pricing_payload()))
    eur = document["rows"][0]
    assert eur["instrument"] == "EUR_USD"
    assert eur["margin_rate"] == "NOT_RETURNED"


def test_21_invalid_numbers_fail_closed() -> None:
    payload = fixtures.pricing_payload()
    payload["prices"][0]["bids"] = [{"price": "not-a-number"}]
    try:
        _run(Fake(fixtures.instruments_payload(), payload))
    except connector.Rejected as exc:
        assert "not-a-number" not in str(exc)
    else:
        raise AssertionError("bad number")


def test_22_invalid_bid_ask_fails_closed() -> None:
    payload = fixtures.pricing_payload()
    payload["prices"][0]["asks"] = [{"price": "1.00000"}]
    payload["prices"][0]["bids"] = [{"price": "1.10000"}]
    try:
        _run(Fake(fixtures.instruments_payload(), payload))
    except connector.Rejected:
        pass
    else:
        raise AssertionError("crossed quote")


def test_23_conversion_factors_stay_separate() -> None:
    document = _run()
    row = document["rows"][0]
    assert row["positive_units_factor"] != row["negative_units_factor"]
    assert row["account_gain_factor"] != row["account_loss_factor"]
    prices = fixtures.pricing_payload()
    del prices["prices"][0]["quoteHomeConversionFactors"]["positiveUnits"]
    partial = _run(Fake(fixtures.instruments_payload(), prices))
    partial_row = partial["rows"][0]
    assert partial_row["positive_units_factor"] == "NOT_RETURNED"
    assert partial_row["negative_units_factor"] != "NOT_RETURNED"
    assert partial_row["positive_units_factor"] != partial_row["negative_units_factor"]


def test_24_gbp_fallback_is_not_applied() -> None:
    prices = fixtures.pricing_payload()
    for item in prices["prices"]:
        item.pop("quoteHomeConversionFactors")
        item.pop("homeConversions")
    document = _run(Fake(fixtures.instruments_payload(), prices))
    blob = json.dumps(document)
    assert "1.35" not in blob
    assert document["rows"][0]["conversion_factors"] == "NOT_RETURNED"


def test_25_output_is_labelled_synthetic(tmp_path: Path) -> None:
    document = _run()
    assert document["evidence_class"] == "SYNTHETIC_TEST_ONLY"
    assert all(row["evidence_class"] == "SYNTHETIC_TEST_ONLY" for row in document["rows"])
    assert document["rows"][0]["spread_pips"] == "2"
    assert document["rows"][5]["instrument"] == "USD_JPY"
    assert document["rows"][5]["spread_pips"] == "3"
    target = HERE / "06_synthetic_matrix.json"
    connector.write_clean(target, document, (TOKEN, ACCOUNT))
    saved = target.read_text(encoding="utf-8")
    assert TOKEN not in saved and ACCOUNT not in saved
    assert "SYNTHETIC_TEST_ONLY" in saved


def test_26_order_endpoint_never_reaches_the_transport() -> None:
    fake = Fake(fixtures.instruments_payload(), fixtures.pricing_payload())
    try:
        connector.prepare("orders", ACCOUNT, TOKEN)
    except connector.Rejected as exc:
        assert ACCOUNT not in str(exc)
    else:
        raise AssertionError("orders")
    assert fake.seen == []


def test_27_malformed_response_fails_closed() -> None:
    try:
        _run(Fake({"nope": True}, {"prices": []}))
    except connector.Rejected as exc:
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("malformed")


def test_28_synthetic_run_does_not_use_dns() -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("dns")

    original_dns = socket.getaddrinfo
    original_open = socket.create_connection
    socket.getaddrinfo = boom  # type: ignore[assignment]
    socket.create_connection = boom  # type: ignore[assignment]
    try:
        document = _run()
        connector.enable_live(phrase="APPROVE PHASE B", flag="--live", override=True)
    except connector.LiveAccessDisabled as exc:
        assert str(exc) == connector.LIVE_DISABLED
        assert TOKEN not in str(exc)
    else:
        raise AssertionError("live gate")
    finally:
        socket.getaddrinfo = original_dns
        socket.create_connection = original_open
    assert document["evidence_class"] == "SYNTHETIC_TEST_ONLY"


def test_home_conversion_query_is_present_only_on_pricing() -> None:
    fake = Fake(fixtures.instruments_payload(), fixtures.pricing_payload())
    _run(fake)
    assert "includeHomeConversions" not in fake.seen[0]["query"]
    assert fake.seen[1]["query"]["includeHomeConversions"] == "true"


def test_ticket_and_financing_panel_are_not_treated_as_api_proof() -> None:
    document = _run()
    ticket = {item["item"]: item for item in document["ticket_comparison"]}
    assert ticket["one pip 0.00 GBP"]["zero_risk"] == "NO"
    assert ticket["units available 3476"]["account_confirmation"] == "NO"
    assert ticket["margin required 0.03 GBP"]["fixed_rate"] == "NO"
    assert ticket["synthetic pricing snapshot"]["real_spread"] == "NO"
    panel = document["user_reported_financing_panel"]
    assert panel["confirmed_by_synthetic_fields"] == "NO"
    assert panel["buy_annualised"] == "-2.43%"
    assert document["rows"][0]["financing_long_rate"] != "-0.0243"
