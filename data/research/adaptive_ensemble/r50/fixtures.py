"""Synthetic OANDA instrument and pricing fixtures. Not account data."""

from __future__ import annotations

SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)

_PRICES = {
    "EUR_USD": ("1.10000", "1.10020", "-4"),
    "GBP_USD": ("1.20000", "1.20030", "-4"),
    "AUD_USD": ("0.65000", "0.65010", "-4"),
    "USD_CAD": ("1.30000", "1.30040", "-4"),
    "USD_CHF": ("0.90000", "0.90020", "-4"),
    "USD_JPY": ("150.000", "150.030", "-2"),
}


def instrument_row(name: str, index: int) -> dict:
    pip = _PRICES[name][2]
    return {
        "name": name,
        "type": "CURRENCY",
        "pipLocation": pip,
        "displayPrecision": 3 if name.endswith("JPY") else 5,
        "tradeUnitsPrecision": 0,
        "minimumTradeSize": "1",
        "maximumOrderUnits": "1000000",
        "maximumPositionSize": "0",
        "marginRate": f"0.05{index}",
        "minimumTrailingStopDistance": "0.050" if name.endswith("JPY") else "0.00050",
        "guaranteedStopLossOrderMode": "DISABLED",
        "financing": {
            "longRate": f"-0.01{index}",
            "shortRate": f"0.02{index}",
            "financingDaysOfWeek": [{"dayOfWeek": "WEDNESDAY", "daysCharged": 3}],
        },
    }


def instruments_payload() -> dict:
    return {"instruments": [instrument_row(name, index) for index, name in enumerate(SIX, start=1)]}


def price_row(name: str, index: int) -> dict:
    bid, ask, _pip = _PRICES[name]
    return {
        "instrument": name,
        "time": "2026-10-21T18:00:00Z",
        "tradeable": True,
        "bids": [{"price": bid, "liquidity": 1}],
        "asks": [{"price": ask, "liquidity": 1}],
        "quoteHomeConversionFactors": {
            "positiveUnits": f"0.80{index}",
            "negativeUnits": f"0.81{index}",
        },
        "homeConversions": [
            {"currency": "USD", "accountGain": f"0.70{index}", "accountLoss": f"0.71{index}"}
        ],
    }


def pricing_payload() -> dict:
    return {"prices": [price_row(name, index) for index, name in enumerate(SIX, start=1)]}
