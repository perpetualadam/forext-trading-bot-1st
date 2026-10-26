"""Pricing diagnostics from an already-supplied pricing document.

Spread in quote units is calculated only for a positive bid and a higher ask.
Spread in pips is not calculated: the operational pricing parse has no pip location.
Quote age is not judged.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
HOME_CONVERSION_UNVERIFIED = "HOME_CONVERSION_NOT_VERIFIED"
FRESHNESS_UNVERIFIED = "QUOTE_FRESHNESS_NOT_VERIFIED"
NOT_RETURNED = "NOT_RETURNED"
NOT_CALCULATED = "NOT_CALCULATED"
UNVERIFIED = "UNVERIFIED"
BROKER_REPORTED = "BROKER_REPORTED"
BOT_CALCULATED = "BOT_CALCULATED"

_PRICE_KEYS = frozenset(
    {
        "instrument",
        "time",
        "status",
        "tradeable",
        "bids",
        "asks",
        "closeoutBid",
        "closeoutAsk",
        "quoteHomeConversionFactors",
        "homeConversions",
    }
)


def _adapter() -> Any:
    name = "r56p2_response_adapter"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / "response_adapter.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build(document: Any) -> tuple[list[dict[str, Any]], set[str]]:
    adapter = _adapter()
    rows, warnings, secrets = adapter.pricing_rows(document)
    if rows is None:
        code = "EMPTY_RESPONSE" if "empty_response" in warnings else "REJECTED_DOCUMENT"
        return [_rejected(code, warnings)], secrets
    records = [_one(adapter, row, list(warnings)) for row in rows]
    return records, secrets


def _one(adapter: Any, row: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    missing: list[str] = []
    if any(key not in _PRICE_KEYS for key in row):
        warnings.append("unexpected_fields_dropped")
    instrument = adapter.instrument_name(row.get("instrument"))
    if instrument is None:
        instrument = NOT_RETURNED
        warnings.append("missing_or_invalid_instrument")
        missing.append("instrument")
    bid, bid_levels, bid_warnings = _side(adapter, row.get("bids"), "bid")
    ask, ask_levels, ask_warnings = _side(adapter, row.get("asks"), "ask")
    warnings.extend(bid_warnings)
    warnings.extend(ask_warnings)
    spread, spread_source, spread_warnings = _spread(adapter, bid, ask)
    warnings.extend(spread_warnings)
    if bid == NOT_RETURNED:
        missing.append("bid")
    if ask == NOT_RETURNED:
        missing.append("ask")

    timestamp, time_warnings = _time(adapter, row)
    warnings.extend(time_warnings)
    if timestamp == NOT_RETURNED:
        missing.append("quote_timestamp")
    missing.append(FRESHNESS_UNVERIFIED)

    tradeable, trade_source, trade_warnings = _tradeable(row)
    warnings.extend(trade_warnings)
    if tradeable == NOT_RETURNED:
        missing.append("tradeable")

    status = adapter.status_text(row.get("status")) if "status" in row else None
    if "status" in row and status is None:
        warnings.append("incorrect_type")
        status_value = NOT_RETURNED
    elif status is None:
        status_value = NOT_RETURNED
    else:
        status_value = status

    conversion, conversion_warnings = _conversion(adapter, row)
    warnings.extend(conversion_warnings)
    if conversion == HOME_CONVERSION_UNVERIFIED:
        missing.append(HOME_CONVERSION_UNVERIFIED)

    closeout_bid = _optional_price(adapter, row, "closeoutBid")
    closeout_ask = _optional_price(adapter, row, "closeoutAsk")
    return {
        "record_kind": "pricing",
        "outcome": "DIAGNOSTIC_RECORDED",
        "instrument": instrument,
        "instrument_source": BROKER_REPORTED if instrument != NOT_RETURNED else UNVERIFIED,
        "bid": bid,
        "bid_source": BROKER_REPORTED if bid != NOT_RETURNED else UNVERIFIED,
        "ask": ask,
        "ask_source": BROKER_REPORTED if ask != NOT_RETURNED else UNVERIFIED,
        "bid_levels": bid_levels,
        "ask_levels": ask_levels,
        "spread_price": spread,
        "spread_price_source": spread_source,
        "spread_pips": NOT_CALCULATED,
        "spread_pips_reason": "PIP_LOCATION_NOT_IN_OPERATIONAL_PRICING_RESPONSE",
        "quote_timestamp": timestamp,
        "quote_timestamp_source": BROKER_REPORTED if timestamp != NOT_RETURNED else UNVERIFIED,
        "quote_freshness": FRESHNESS_UNVERIFIED,
        "tradeable": tradeable,
        "tradeable_source": trade_source,
        "status": status_value,
        "closeout_bid": closeout_bid,
        "closeout_ask": closeout_ask,
        "home_conversion": conversion,
        "home_conversion_operational_request": "NOT_REQUESTED",
        "missing_evidence": _unique(missing),
        "validation_warnings": _unique(warnings),
        "executable_order": adapter.NOT_PRODUCED,
    }


def _side(adapter: Any, levels: Any, name: str) -> tuple[str, int, list[str]]:
    if levels is None:
        return NOT_RETURNED, 0, [f"missing_{name}"]
    if not isinstance(levels, list):
        return NOT_RETURNED, 0, ["incorrect_type"]
    if not levels:
        return NOT_RETURNED, 0, [f"missing_{name}"]
    warnings: list[str] = []
    if len(levels) > 1:
        warnings.append("additional_levels_not_used")
    first = levels[0]
    if not isinstance(first, dict) or "price" not in first:
        return NOT_RETURNED, len(levels), warnings + ["incorrect_type"]
    if not adapter.positive_price(first.get("price")):
        if adapter.decimal_text(first.get("price")) is not None and Decimal(adapter.decimal_text(first.get("price"))) <= 0:
            warnings.append("non_positive_price")
        else:
            warnings.append("incorrect_type")
        return NOT_RETURNED, len(levels), warnings
    return adapter.positive_price(first.get("price")), len(levels), warnings


def _spread(adapter: Any, bid: str, ask: str) -> tuple[str, str, list[str]]:
    if bid == NOT_RETURNED or ask == NOT_RETURNED:
        return NOT_CALCULATED, UNVERIFIED, []
    if Decimal(bid) > Decimal(ask):
        return NOT_CALCULATED, UNVERIFIED, ["bid_above_ask"]
    gap = adapter.price_difference(bid, ask)
    if gap is None:
        return NOT_CALCULATED, UNVERIFIED, ["non_positive_price"]
    return gap, BOT_CALCULATED, []


def _time(adapter: Any, row: dict[str, Any]) -> tuple[str, list[str]]:
    if "time" not in row or row.get("time") in (None, ""):
        return NOT_RETURNED, ["missing_timestamp"]
    text = adapter.timestamp_text(row.get("time"))
    if text is None:
        return NOT_RETURNED, ["malformed_timestamp"]
    return text, []


def _tradeable(row: dict[str, Any]) -> tuple[Any, str, list[str]]:
    if "tradeable" not in row or row.get("tradeable") is None:
        return NOT_RETURNED, UNVERIFIED, ["missing_tradeable"]
    value = row.get("tradeable")
    if not isinstance(value, bool):
        return NOT_RETURNED, UNVERIFIED, ["incorrect_type"]
    return value, BROKER_REPORTED, []


def _optional_price(adapter: Any, row: dict[str, Any], key: str) -> str:
    if key not in row or row.get(key) in (None, ""):
        return NOT_RETURNED
    text = adapter.positive_price(row.get(key))
    return text if text is not None else NOT_RETURNED


def _conversion(adapter: Any, row: dict[str, Any]) -> tuple[Any, list[str]]:
    if "quoteHomeConversionFactors" not in row and "homeConversions" not in row:
        return HOME_CONVERSION_UNVERIFIED, ["home_conversion_absent"]
    factors = row.get("quoteHomeConversionFactors")
    homes = row.get("homeConversions")
    positive = NOT_RETURNED
    negative = NOT_RETURNED
    warnings: list[str] = []
    if factors is None and homes is None:
        return HOME_CONVERSION_UNVERIFIED, ["home_conversion_absent"]
    if "quoteHomeConversionFactors" in row and not isinstance(factors, dict):
        warnings.append("incorrect_type")
        factors = None
    if isinstance(factors, dict):
        positive = adapter.positive_price(factors.get("positiveUnits")) or NOT_RETURNED
        negative = adapter.positive_price(factors.get("negativeUnits")) or NOT_RETURNED
        if positive == NOT_RETURNED or negative == NOT_RETURNED:
            warnings.append("incomplete_home_conversion")
    currencies: list[dict[str, str]] = []
    if "homeConversions" in row and homes is not None and not isinstance(homes, list):
        warnings.append("incorrect_type")
    if isinstance(homes, list):
        for item in homes:
            if not isinstance(item, dict):
                warnings.append("incorrect_type")
                continue
            code = adapter.currency_code(item.get("currency"))
            gain = adapter.decimal_text(item.get("accountGain"))
            loss = adapter.decimal_text(item.get("accountLoss"))
            if code is None or gain is None or loss is None:
                warnings.append("incomplete_home_conversion")
                continue
            currencies.append(
                {
                    "currency": code,
                    "account_gain": gain,
                    "account_loss": loss,
                    "source": BROKER_REPORTED,
                }
            )
    if positive == NOT_RETURNED and negative == NOT_RETURNED and not currencies:
        return HOME_CONVERSION_UNVERIFIED, warnings or ["home_conversion_absent"]
    return {
        "status": "PRESENT_IN_SUPPLIED_DOCUMENT",
        "operational_pricing_request": "NOT_REQUESTED",
        "positive_units_factor": positive,
        "positive_units_source": BROKER_REPORTED if positive != NOT_RETURNED else UNVERIFIED,
        "negative_units_factor": negative,
        "negative_units_source": BROKER_REPORTED if negative != NOT_RETURNED else UNVERIFIED,
        "home_conversions": currencies,
    }, warnings


def _rejected(code: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "record_kind": "failure",
        "outcome": "REJECTED",
        "error_code": code,
        "missing_evidence": ["pricing"],
        "validation_warnings": _unique(warnings),
        "executable_order": "NOT_PRODUCED",
    }


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen
