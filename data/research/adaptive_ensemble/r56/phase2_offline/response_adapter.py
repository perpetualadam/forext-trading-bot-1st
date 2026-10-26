"""Pure adapter for already-supplied OANDA-shaped dictionaries.

This module does not open sockets, read credentials, or import the trading bot.
Field names it recognises are limited to keys read by the operational parsers
or, where noted, keys the operational parser does not copy.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA_VERSION = "r56.phase2.1"

BROKER_REPORTED = "BROKER_REPORTED"
BOT_CALCULATED = "BOT_CALCULATED"
SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"
UNVERIFIED = "UNVERIFIED"
NOT_RETURNED = "NOT_RETURNED"
NOT_CALCULATED = "NOT_CALCULATED"
NOT_PRODUCED = "NOT_PRODUCED"

DATA_SOURCES = frozenset({SYNTHETIC_TEST_ONLY, "SUPPLIED_DOCUMENT"})
FIELD_SOURCES = frozenset({BROKER_REPORTED, BOT_CALCULATED, SYNTHETIC_TEST_ONLY, UNVERIFIED})

_ACCOUNT_ID = re.compile(r"^\d{3}-\d{3}-\d{3,}-\d{3}$")
_BEARER = re.compile(r"(?i)bearer\s+\S+")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_INSTRUMENT = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")
_DECIMAL = re.compile(r"^[+-]?(?:\d+\.\d+|\d+)$")
_STATUS = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$"
)
_SENSITIVE_KEYS = frozenset(
    {
        "id",
        "accountid",
        "account_id",
        "alias",
        "token",
        "access_token",
        "password",
        "authorization",
        "secret",
    }
)


def loads_object(text: str) -> tuple[Any, str | None]:
    """Parse one JSON value. The error code never includes the input text."""
    if not isinstance(text, str) or not text.strip():
        return None, "EMPTY_RESPONSE"
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        return None, "MALFORMED_JSON"


def sensitive_literals(document: Any) -> set[str]:
    """Values that must never be written. The set itself is not logged."""
    found: set[str] = set()

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for item_key, item in value.items():
                walk(item, str(item_key))
            return
        if isinstance(value, list):
            for item in value:
                walk(item, key)
            return
        if not isinstance(value, str):
            return
        text = value.strip()
        if not text:
            return
        key_name = key.lower()
        if key_name in _SENSITIVE_KEYS or _ACCOUNT_ID.match(text) or _BEARER.search(text):
            found.add(text)
        if "SYNTHETIC-TOKEN" in text or "AUTHORIZATION" in text.upper():
            found.add(text)

    walk(document)
    return {item for item in found if len(item) >= 6}


def account_view(document: Any) -> tuple[dict[str, Any] | None, list[str], set[str]]:
    """Return the inner account object, warnings, and sensitive literals."""
    warnings: list[str] = []
    secrets = sensitive_literals(document)
    if not isinstance(document, dict) or not document:
        return None, ["empty_response"], secrets
    if "errorMessage" in document or "errorCode" in document:
        return None, ["broker_error_document"], secrets
    account = document.get("account", document)
    if not isinstance(account, dict):
        return None, ["incorrect_type"], secrets
    if not account:
        return None, ["empty_response"], secrets
    known = {
        "id",
        "currency",
        "NAV",
        "balance",
        "unrealizedPL",
        "marginAvailable",
        "marginUsed",
        "alias",
        "lastTransactionID",
    }
    extra = [key for key in account if key not in known]
    wrapper_extra = [key for key in document if key not in {"account", "lastTransactionID"}]
    if extra or wrapper_extra:
        warnings.append("unexpected_fields_dropped")
    if "alias" in account:
        warnings.append("alias_not_logged")
    if "id" in account:
        warnings.append("account_id_not_logged")
    return account, warnings, secrets


def pricing_rows(document: Any) -> tuple[list[dict[str, Any]] | None, list[str], set[str]]:
    warnings: list[str] = []
    secrets = sensitive_literals(document)
    if not isinstance(document, dict) or not document:
        return None, ["empty_response"], secrets
    if "prices" not in document:
        return None, ["empty_response"], secrets
    prices = document.get("prices")
    if not isinstance(prices, list):
        return None, ["incorrect_type"], secrets
    if not prices:
        return None, ["empty_response"], secrets
    if any(key != "prices" for key in document):
        warnings.append("unexpected_fields_dropped")
    rows: list[dict[str, Any]] = []
    for item in prices:
        if not isinstance(item, dict):
            warnings.append("incorrect_type")
            continue
        rows.append(item)
    if not rows:
        return None, warnings, secrets
    return rows, warnings, secrets


def decimal_text(value: Any) -> str | None:
    """Keep a broker decimal string. Floats are rejected so they are not relabelled."""
    if isinstance(value, bool) or not isinstance(value, str):
        return None
    text = value.strip().replace(",", "")
    if not _DECIMAL.fullmatch(text):
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    if not parsed.is_finite():
        return None
    return text


def positive_price(value: Any) -> str | None:
    text = decimal_text(value)
    if text is None:
        return None
    if Decimal(text) <= 0:
        return None
    return text


def currency_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().upper()
    if not _CURRENCY.fullmatch(text):
        return None
    return text


def instrument_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().upper()
    if not _INSTRUMENT.fullmatch(text):
        return None
    return text


def timestamp_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not _TIMESTAMP.fullmatch(text):
        return None
    return text


def status_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not _STATUS.fullmatch(text):
        return None
    return text


def price_difference(bid: str, ask: str) -> str | None:
    """Quote-unit difference. Pip conversion is not applied."""
    try:
        gap = Decimal(ask) - Decimal(bid)
    except InvalidOperation:
        return None
    if gap <= 0:
        return None
    return format(gap, "f")
