"""Built-in synthetic responses for the offline B2 candidate.

These values are fixtures. They are not OANDA prices, account facts, or a GBP model.
"""

from __future__ import annotations

import json

FIXTURE_ACCOUNT_ID = "SYNTHETIC-ACCOUNT-R55B2-NOT-REAL"
FIXTURE_TOKEN = "SYNTHETIC-TOKEN-R55B2-NOT-REAL"
SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
_PRICES = {
    "EUR_USD": ("1.11100", "1.11120", "-4"),
    "GBP_USD": ("1.22200", "1.22230", "-4"),
    "AUD_USD": ("0.66600", "0.66610", "-4"),
    "USD_CAD": ("1.33300", "1.33340", "-4"),
    "USD_CHF": ("0.88800", "0.88820", "-4"),
    "USD_JPY": ("140.000", "140.040", "-2"),
}


def instrument_row(name: str, index: int) -> dict:
    pip = _PRICES[name][2]
    return {
        "name": name,
        "type": "CURRENCY",
        "pipLocation": pip,
        "displayPrecision": 3 if name.endswith("JPY") else 5,
        "minimumTradeSize": "1",
        "marginRate": f"0.05{index}",
        "financing": {"longRate": f"-0.01{index}", "shortRate": f"0.02{index}"},
    }


def instruments_payload() -> dict:
    return {"instruments": [instrument_row(name, index) for index, name in enumerate(SIX, start=1)]}


def price_row(name: str, index: int) -> dict:
    bid, ask, _pip = _PRICES[name]
    return {
        "instrument": name,
        "time": "2019-01-02T03:04:05Z",
        "tradeable": True,
        "bids": [{"price": bid}],
        "asks": [{"price": ask}],
        "quoteHomeConversionFactors": {
            "positiveUnits": f"0.80{index}",
            "negativeUnits": f"0.81{index}",
        },
        "homeConversions": [
            {"currency": "XTS", "accountGain": f"0.70{index}", "accountLoss": f"0.71{index}"}
        ],
    }


def pricing_payload() -> dict:
    return {"prices": [price_row(name, index) for index, name in enumerate(SIX, start=1)]}


def instruments_bytes() -> bytes:
    return json.dumps(instruments_payload()).encode("utf-8")


def pricing_bytes() -> bytes:
    return json.dumps(pricing_payload()).encode("utf-8")
