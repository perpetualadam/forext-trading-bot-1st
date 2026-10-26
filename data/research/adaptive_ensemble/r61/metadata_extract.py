"""Sanitised instrument metadata. Missing values stay missing. Raw documents are not returned."""

from __future__ import annotations

import re
from typing import Any

EXPECTED = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
_DECIMAL = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
_ENUM = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")
_DAYS = frozenset({"SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"})
_TYPES = frozenset({"CURRENCY", "CFD", "METAL"})


class MetadataRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _missing() -> dict[str, str]:
    return {"status": "MISSING"}


def _invalid() -> dict[str, str]:
    return {"status": "INVALID"}


def _decimal_field(container: dict[str, Any], key: str) -> dict[str, str]:
    if key not in container:
        return _missing()
    value = container[key]
    if isinstance(value, str) and _DECIMAL.fullmatch(value):
        return {"status": "RETURNED", "value": value}
    return _invalid()


def _int_field(container: dict[str, Any], key: str) -> dict[str, Any]:
    if key not in container:
        return _missing()
    value = container[key]
    if isinstance(value, bool) or not isinstance(value, int):
        return _invalid()
    return {"status": "RETURNED", "value": value}


def _enum_field(container: dict[str, Any], key: str, allowed: frozenset[str] | None) -> dict[str, str]:
    if key not in container:
        return _missing()
    value = container[key]
    if not isinstance(value, str) or _ENUM.fullmatch(value) is None:
        return _invalid()
    if allowed is not None and value not in allowed:
        return {"status": "RETURNED", "value": value, "documented_enum": "NO"}
    return {"status": "RETURNED", "value": value}


def _days(value: object) -> dict[str, Any]:
    if not isinstance(value, list):
        return _invalid()
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return _invalid()
        day = item.get("dayOfWeek")
        count = item.get("daysCharged")
        if not isinstance(day, str) or day not in _DAYS or isinstance(count, bool) or not isinstance(count, int):
            return _invalid()
        rows.append({"dayOfWeek": day, "daysCharged": count})
    return {"status": "RETURNED", "value": rows}


def _financing(container: dict[str, Any]) -> dict[str, Any]:
    if "financing" not in container:
        return {"longRate": _missing(), "shortRate": _missing(), "financingDaysOfWeek": _missing()}
    raw = container["financing"]
    if not isinstance(raw, dict):
        return {"longRate": _invalid(), "shortRate": _invalid(), "financingDaysOfWeek": _invalid()}
    days = _days(raw["financingDaysOfWeek"]) if "financingDaysOfWeek" in raw else _missing()
    return {
        "longRate": _decimal_field(raw, "longRate"),
        "shortRate": _decimal_field(raw, "shortRate"),
        "financingDaysOfWeek": days,
    }


def _restriction(container: dict[str, Any]) -> dict[str, Any]:
    key = "guaranteedStopLossOrderLevelRestriction"
    if key not in container:
        return _missing()
    raw = container[key]
    if not isinstance(raw, dict):
        return _invalid()
    volume = _decimal_field(raw, "volume")
    price = _decimal_field(raw, "priceRange")
    if volume["status"] != "RETURNED" or price["status"] != "RETURNED":
        return _invalid()
    return {"status": "RETURNED", "value": {"volume": volume["value"], "priceRange": price["value"]}}


def _commission(container: dict[str, Any]) -> dict[str, Any]:
    if "commission" not in container:
        return _missing()
    raw = container["commission"]
    if not isinstance(raw, dict):
        return _invalid()
    rows = {key: _decimal_field(raw, key) for key in ("commission", "unitsTraded", "minimumCommission")}
    if any(item["status"] == "INVALID" for item in rows.values()):
        return _invalid()
    return {"status": "RETURNED", "value": rows}


def _instrument(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
        raise MetadataRejected("MALFORMED_INSTRUMENT")
    name = raw["name"]
    if name not in EXPECTED:
        raise MetadataRejected("UNEXPECTED_INSTRUMENT")
    return {
        "name": {"status": "RETURNED", "value": name},
        "type": _enum_field(raw, "type", _TYPES),
        "pipLocation": _int_field(raw, "pipLocation"),
        "displayPrecision": _int_field(raw, "displayPrecision"),
        "tradeUnitsPrecision": _int_field(raw, "tradeUnitsPrecision"),
        "minimumTradeSize": _decimal_field(raw, "minimumTradeSize"),
        "maximumOrderUnits": _decimal_field(raw, "maximumOrderUnits"),
        "maximumPositionSize": _decimal_field(raw, "maximumPositionSize"),
        "marginRate": _decimal_field(raw, "marginRate"),
        "financing": _financing(raw),
        "guaranteedStopLossOrderMode": _enum_field(raw, "guaranteedStopLossOrderMode", frozenset({"DISABLED", "ALLOWED", "REQUIRED"})),
        "minimumGuaranteedStopLossDistance": _decimal_field(raw, "minimumGuaranteedStopLossDistance"),
        "guaranteedStopLossOrderExecutionPremium": _decimal_field(raw, "guaranteedStopLossOrderExecutionPremium"),
        "guaranteedStopLossOrderLevelRestriction": _restriction(raw),
        "commission": _commission(raw),
    }


def extract(document: object) -> list[dict[str, Any]]:
    """Return the six instruments in the approved order, or reject the document."""
    if not isinstance(document, dict) or set(document) - {"instruments", "lastTransactionID"}:
        raise MetadataRejected("MALFORMED_RESPONSE")
    rows = document.get("instruments")
    if not isinstance(rows, list):
        raise MetadataRejected("MALFORMED_RESPONSE")
    built: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = _instrument(row)
        name = item["name"]["value"]
        if name in built:
            raise MetadataRejected("DUPLICATE_INSTRUMENT")
        built[name] = item
    if set(built) != set(EXPECTED):
        raise MetadataRejected("INSTRUMENT_SET_REJECTED")
    return [built[name] for name in EXPECTED]
