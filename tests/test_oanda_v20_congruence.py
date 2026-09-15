"""Helpers aligned with OANDA REST v20 docs (no live network)."""

from __future__ import annotations

from oandapyV20.contrib.requests import MarketOrderRequest, PositionCloseRequest
from oandapyV20.definitions.orders import OrderPositionFill, TimeInForce

from forex_bot.oanda_client import (
    _is_transient_transport,
    _oanda_request,
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
