"""Helpers aligned with OANDA REST v20 docs (no live network)."""

from __future__ import annotations

from oandapyV20.contrib.requests import MarketOrderRequest, PositionCloseRequest
from oandapyV20.definitions.orders import OrderPositionFill, TimeInForce

from forex_bot.oanda_client import (
    _apply_http_timeout,
    _is_transient_transport,
    _oanda_request,
    build_api,
    oanda_http_timeout,
    official_env_label,
    official_rest_host,
    oanda_instrument,
)
from forex_bot.oanda_exec import _abs_units_decimal, _order_units_for_open


def test_instrument_name_underscore():
    assert oanda_instrument("eur-usd") == "EUR_USD"
    assert oanda_instrument("GBP/USD") == "GBP_USD"


def test_hosts_match_development_guide(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "live")
    from forex_bot import config as cfg

    monkeypatch.setattr(cfg.Config, "TRADING_MODE", "live")
    assert official_rest_host() == "https://api-fxtrade.oanda.com"
    assert official_env_label() == "fxTrade"
    monkeypatch.setattr(cfg.Config, "TRADING_MODE", "practice")
    assert official_rest_host() == "https://api-fxpractice.oanda.com"
    assert official_env_label() == "fxTrade Practice"


def test_market_order_body_is_official_shape():
    mo = MarketOrderRequest(
        instrument="EUR_USD",
        units=100,
        timeInForce=TimeInForce.FOK,
        positionFill=OrderPositionFill.OPEN_ONLY,
    )
    body = mo.data
    assert "order" in body
    assert body["order"]["type"] == "MARKET"
    assert body["order"]["units"] == "100"
    assert body["order"]["timeInForce"] == "FOK"
    assert body["order"]["positionFill"] == "OPEN_ONLY"
    assert body["order"]["instrument"] == "EUR_USD"


def test_position_close_units_are_positive_strings():
    req = PositionCloseRequest(longUnits=_abs_units_decimal(12.4))
    assert req.data == {"longUnits": "12"}
    req_s = PositionCloseRequest(shortUnits=_abs_units_decimal(5))
    assert req_s.data == {"shortUnits": "5"}


def test_open_units_signed():
    assert _order_units_for_open(10, "BUY") == 10
    assert _order_units_for_open(10, "SELL") == -10


def test_ssl_eof_is_transient_transport():
    exc = ConnectionError(
        "HTTPSConnectionPool(host='api-fxtrade.oanda.com', port=443): "
        "Max retries exceeded with url: /v3/accounts/x/openPositions "
        "(Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] "
        "EOF occurred in violation of protocol (_ssl.c:1010)')))"
    )
    assert _is_transient_transport(exc) is True
    assert _is_transient_transport(ValueError("bad units")) is False


def test_oanda_request_retries_ssl_then_succeeds(monkeypatch):
    monkeypatch.setattr("forex_bot.oanda_client.time.sleep", lambda _s: None)

    class FakeAPI:
        def __init__(self):
            self.n = 0

        def request(self, _r):
            self.n += 1
            if self.n == 1:
                raise ConnectionError(
                    "Max retries exceeded (Caused by SSLError UNEXPECTED_EOF_WHILE_READING)"
                )
            return {"positions": []}

    api = FakeAPI()
    out = _oanda_request(api, object(), context="open positions")
    assert out == {"positions": []}
    assert api.n == 2


def test_http_timeout_defaults_and_env(monkeypatch):
    monkeypatch.delenv("OANDA_CONNECT_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("OANDA_HTTP_TIMEOUT_SEC", raising=False)
    assert oanda_http_timeout() == (15.0, 15.0)
    monkeypatch.setenv("OANDA_CONNECT_TIMEOUT_SEC", "3")
    monkeypatch.setenv("OANDA_HTTP_TIMEOUT_SEC", "12")
    assert oanda_http_timeout() == (3.0, 12.0)


def test_build_api_sets_requests_timeout(monkeypatch):
    from forex_bot import oanda_client as oc
    from forex_bot.config import Config

    monkeypatch.setattr(Config, "OANDA_ACCESS_TOKEN", "tok")
    monkeypatch.setattr(Config, "TRADING_MODE", "practice")
    monkeypatch.setenv("OANDA_CONNECT_TIMEOUT_SEC", "4")
    monkeypatch.setenv("OANDA_HTTP_TIMEOUT_SEC", "11")
    prev = oc._api
    try:
        api = build_api()
        assert api is not None
        assert api._request_params["timeout"] == (4.0, 11.0)
    finally:
        oc._api = prev


def test_apply_timeout_repairs_client_without_timeout():
    class Bare:
        _request_params = {}

    api = _apply_http_timeout(Bare())
    assert "timeout" in api._request_params
    assert api._request_params["timeout"][0] > 0
    assert api._request_params["timeout"][1] > 0


def test_read_timeout_is_transient_and_retried(monkeypatch):
    from requests.exceptions import ReadTimeout

    monkeypatch.setattr("forex_bot.oanda_client.time.sleep", lambda _s: None)
    assert _is_transient_transport(ReadTimeout("Read timed out")) is True

    class FakeAPI:
        def __init__(self):
            self.n = 0

        def request(self, _r):
            self.n += 1
            if self.n == 1:
                raise ReadTimeout("Read timed out")
            return {"candles": []}

    out = _oanda_request(FakeAPI(), object(), context="latest EUR_USD")
    assert out == {"candles": []}
