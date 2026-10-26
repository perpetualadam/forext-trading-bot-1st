"""Standalone GET-only request gate. No production imports. No credentials. No network."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

ALLOWED_HOST = "api-fxtrade.oanda.com"
SIX_INSTRUMENTS = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
ALLOWED_KINDS = ("instruments", "pricing")
TIMEOUT_SECONDS = 5.0
RETRY_LIMIT = 0
EXECUTION_PERMITTED = False
BLOCKED_MESSAGE = "R48_AUTHENTICATED_EXECUTION_BLOCKED"

_INSTRUMENT_FIELDS = (
    "name",
    "type",
    "pipLocation",
    "displayPrecision",
    "tradeUnitsPrecision",
    "minimumTradeSize",
    "maximumOrderUnits",
    "maximumPositionSize",
    "marginRate",
    "minimumTrailingStopDistance",
    "guaranteedStopLossOrderMode",
)
_DAY = {"dayOfWeek", "daysCharged"}
_HOME_FIELDS = ("currency", "accountGain", "accountLoss")


class GateClosed(RuntimeError):
    """The authenticated call is refused before any connection is opened."""


class SchemaRejected(ValueError):
    """The response shape cannot be reduced to the sanitised fields."""


def timeout_seconds() -> float:
    return TIMEOUT_SECONDS


def retry_limit() -> int:
    return RETRY_LIMIT


def redacted_request(kind: str) -> dict[str, Any]:
    """Evidence-safe description. It contains no account identifier and no URL."""
    if kind not in ALLOWED_KINDS:
        raise GateClosed(BLOCKED_MESSAGE)
    query = "instruments=" + ",".join(SIX_INSTRUMENTS)
    if kind == "pricing":
        query += "&includeHomeConversions=true"
    return {
        "method": "GET",
        "host": ALLOWED_HOST,
        "path_pattern": f"/v3/accounts/{{accountID}}/{kind}",
        "query_pattern": query,
        "timeout_seconds": TIMEOUT_SECONDS,
        "retries": RETRY_LIMIT,
        "redirects": False,
        "body": None,
        "stream": False,
    }


def assert_request(method: str, host: str, path: str, query_keys: tuple[str, ...]) -> None:
    """Reject anything outside the two GET patterns. Raises before a connection would open."""
    if method != "GET":
        raise GateClosed(BLOCKED_MESSAGE)
    if host != ALLOWED_HOST:
        raise GateClosed(BLOCKED_MESSAGE)
    parts = [part for part in path.split("/") if part]
    if len(parts) != 4 or parts[0] != "v3" or parts[1] != "accounts" or parts[3] not in ALLOWED_KINDS:
        raise GateClosed(BLOCKED_MESSAGE)
    if not parts[2] or parts[2] == "{accountID}":
        raise GateClosed(BLOCKED_MESSAGE)
    allowed_keys = {"instruments", "includeHomeConversions"} if parts[3] == "pricing" else {"instruments"}
    if set(query_keys) != allowed_keys:
        raise GateClosed(BLOCKED_MESSAGE)


def build_path(kind: str, account_id: str) -> str:
    """Return a path for an in-memory check. Callers must not write this string to evidence."""
    if kind not in ALLOWED_KINDS:
        raise GateClosed(BLOCKED_MESSAGE)
    if not isinstance(account_id, str) or not account_id or any(ch in account_id for ch in "/?#& \r\n\t"):
        raise GateClosed(BLOCKED_MESSAGE)
    return f"/v3/accounts/{quote(account_id, safe='')}/{kind}"


def accept_status(status: int) -> None:
    """Accept only HTTP 200. Redirects are not followed and are not retried."""
    if status != 200:
        raise GateClosed(BLOCKED_MESSAGE)


def perform_request(**_kwargs: Any) -> None:
    """Authenticated execution is closed. The exception text is constant."""
    raise GateClosed(BLOCKED_MESSAGE)


def _missing(row: dict[str, Any], key: str) -> None:
    row[key] = "MISSING"


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def select_instrument(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
        raise SchemaRejected("instrument")
    row: dict[str, Any] = {"instrument": raw["name"].strip()}
    for key in _INSTRUMENT_FIELDS:
        if key == "name":
            continue
        text = _text(raw.get(key))
        if text is None:
            _missing(row, key)
        else:
            row[key] = text
    financing = raw.get("financing")
    if financing is None:
        _missing(row, "financingLongRate")
        _missing(row, "financingShortRate")
        _missing(row, "financingDays")
    elif not isinstance(financing, dict):
        raise SchemaRejected("financing")
    else:
        long_rate = _text(financing.get("longRate"))
        short_rate = _text(financing.get("shortRate"))
        row["financingLongRate"] = long_rate if long_rate is not None else "MISSING"
        row["financingShortRate"] = short_rate if short_rate is not None else "MISSING"
        days = financing.get("financingDaysOfWeek")
        if days is None:
            _missing(row, "financingDays")
        elif not isinstance(days, list):
            raise SchemaRejected("financingDays")
        else:
            cleaned = []
            for item in days:
                if not isinstance(item, dict) or not _DAY.issubset(item):
                    raise SchemaRejected("financingDays")
                cleaned.append({name: item[name] for name in ("dayOfWeek", "daysCharged")})
            row["financingDays"] = cleaned
    return row


def parse_instruments(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("instruments"), list):
        raise SchemaRejected("instruments")
    return [select_instrument(item) for item in payload["instruments"]]


def _factor_pair(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise SchemaRejected("conversion")
    positive = _text(raw.get("positiveUnits"))
    negative = _text(raw.get("negativeUnits"))
    return {
        "positiveUnits": positive if positive is not None else "MISSING",
        "negativeUnits": negative if negative is not None else "MISSING",
    }


def _home_rows(raw: Any) -> list[dict[str, str]] | str:
    if raw is None:
        return "MISSING"
    if not isinstance(raw, list):
        raise SchemaRejected("homeConversions")
    rows = []
    for item in raw:
        if not isinstance(item, dict):
            raise SchemaRejected("homeConversions")
        row = {}
        for key in _HOME_FIELDS:
            text = _text(item.get(key))
            row[key] = text if text is not None else "MISSING"
        rows.append(row)
    return rows


def _spread_pips(bid: str, ask: str, pip_location: str) -> str:
    try:
        location = int(pip_location)
        width = (Decimal(ask) - Decimal(bid)) / (Decimal(10) ** location)
    except (InvalidOperation, ValueError):
        raise SchemaRejected("spread") from None
    rendered = format(width, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def select_price(raw: Any, pip_location: str | None) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("instrument"), str):
        raise SchemaRejected("price")
    bids = raw.get("bids")
    asks = raw.get("asks")
    bid = _text(bids[0].get("price")) if isinstance(bids, list) and bids and isinstance(bids[0], dict) else None
    ask = _text(asks[0].get("price")) if isinstance(asks, list) and asks and isinstance(asks[0], dict) else None
    tradeable = raw.get("tradeable")
    row: dict[str, Any] = {
        "instrument": raw["instrument"].strip(),
        "time": _text(raw.get("time")) or "MISSING",
        "bid": bid or "MISSING",
        "ask": ask or "MISSING",
        "tradeable": tradeable if isinstance(tradeable, bool) else "MISSING",
        "spread_class": "POINT_IN_TIME_API_SNAPSHOT",
        "quoteHomeConversionFactors": _factor_pair(raw["quoteHomeConversionFactors"])
        if "quoteHomeConversionFactors" in raw
        else {"positiveUnits": "MISSING", "negativeUnits": "MISSING"},
        "homeConversions": _home_rows(raw.get("homeConversions")),
    }
    if bid and ask and pip_location and pip_location != "MISSING":
        row["spread_pips"] = _spread_pips(bid, ask, pip_location)
    else:
        row["spread_pips"] = "MISSING"
    return row


def parse_pricing(payload: Any, pip_locations: dict[str, str]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("prices"), list):
        raise SchemaRejected("prices")
    rows = []
    for item in payload["prices"]:
        if not isinstance(item, dict) or not isinstance(item.get("instrument"), str):
            raise SchemaRejected("price")
        rows.append(select_price(item, pip_locations.get(item["instrument"])))
    return rows
