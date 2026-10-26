"""Validate synthetic response data. This module does not fetch a response."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REJECTED = "R55B2_REJECTED"
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


class Failure(RuntimeError):
    """Classified validation failure. The message stays a fixed code."""

    def __init__(self, classification: str, detail: dict[str, str] | None = None) -> None:
        self.classification = classification
        self.detail = detail or {}
        super().__init__(REJECTED)


def _load_plan() -> Any:
    name = "r55b2_request_plan"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent / "request_plan.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _finite_price(text: str) -> Decimal:
    try:
        value = Decimal(str(text))
    except (InvalidOperation, ValueError):
        raise Failure("SCHEMA_REJECTED", {"field": "price"}) from None
    if not value.is_finite() or value <= 0:
        raise Failure("SCHEMA_REJECTED", {"field": "price"})
    return value


def _spread(bid: str, ask: str, pip_location: str) -> str:
    left = _finite_price(bid)
    right = _finite_price(ask)
    if left > right:
        raise Failure("SCHEMA_REJECTED", {"field": "bid_ask"})
    try:
        location = int(pip_location)
    except ValueError:
        raise Failure("SCHEMA_REJECTED", {"field": "pipLocation"}) from None
    width = (right - left) / (Decimal(10) ** location)
    if not width.is_finite():
        raise Failure("SCHEMA_REJECTED", {"field": "spread"})
    rendered = format(width, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def classify_status(status: int) -> str | None:
    """Return a fixed classification for a non-200 status. 200 returns None."""
    if status == 200:
        return None
    if status == 401:
        return "HTTP_401"
    if status == 403:
        return "HTTP_403"
    if status == 404:
        return "HTTP_404"
    if status == 429:
        return "HTTP_429"
    if 500 <= status <= 599:
        return "HTTP_5XX"
    return "HTTP_ERROR"


def parse_body(raw: bytes) -> dict[str, Any]:
    plan = _load_plan()
    if not isinstance(raw, (bytes, bytearray)):
        raise Failure("MALFORMED_JSON")
    if len(raw) > plan.MAX_BODY:
        raise Failure("RESPONSE_TOO_LARGE")
    try:
        payload = json.loads(bytes(raw).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise Failure("MALFORMED_JSON") from None
    if not isinstance(payload, dict):
        raise Failure("MALFORMED_JSON")
    return payload


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _shown(value: Any) -> str:
    text = _text(value)
    return text if text is not None else "NOT_RETURNED"


def validate_instruments(payload: dict[str, Any]) -> list[dict[str, str]]:
    plan = _load_plan()
    rows = payload.get("instruments")
    if not isinstance(rows, list):
        raise Failure("SCHEMA_REJECTED", {"field": "instruments"})
    found: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            raise Failure("SCHEMA_REJECTED", {"field": "instrument"})
        name = _text(item.get("name"))
        if name is None:
            raise Failure("SCHEMA_REJECTED", {"field": "name"})
        if name not in plan.SIX:
            raise Failure("SCHEMA_REJECTED", {"field": "unexpected_instrument", "instrument": name})
        if name in found:
            raise Failure("SCHEMA_REJECTED", {"field": "duplicate_instrument", "instrument": name})
        found[name] = item
    missing = [name for name in plan.SIX if name not in found]
    if missing:
        raise Failure("SCHEMA_REJECTED", {"field": "missing_instrument", "instrument": missing[0]})
    built = []
    for name in plan.SIX:
        item = found[name]
        pip = _text(item.get("pipLocation"))
        if pip is None:
            raise Failure("SCHEMA_REJECTED", {"field": "pipLocation", "instrument": name})
        try:
            int(pip)
        except ValueError:
            raise Failure("SCHEMA_REJECTED", {"field": "pipLocation", "instrument": name}) from None
        financing = item.get("financing")
        long_rate = "NOT_RETURNED"
        short_rate = "NOT_RETURNED"
        if isinstance(financing, dict):
            long_rate = _shown(financing.get("longRate"))
            short_rate = _shown(financing.get("shortRate"))
        built.append(
            {
                "instrument": name,
                "type": _shown(item.get("type")),
                "pip_location": pip,
                "display_precision": _shown(item.get("displayPrecision")),
                "minimum_trade_size": _shown(item.get("minimumTradeSize")),
                "margin_rate": _shown(item.get("marginRate")),
                "financing_long_rate": long_rate,
                "financing_short_rate": short_rate,
            }
        )
    return built


def _conversion(price: dict[str, Any]) -> dict[str, str]:
    factors = price.get("quoteHomeConversionFactors")
    homes = price.get("homeConversions")
    positive = "NOT_RETURNED"
    negative = "NOT_RETURNED"
    gain = "NOT_RETURNED"
    loss = "NOT_RETURNED"
    quoted = "NOT_RETURNED"
    state = "NOT_RETURNED"
    if isinstance(factors, dict):
        positive = _shown(factors.get("positiveUnits"))
        negative = _shown(factors.get("negativeUnits"))
        if positive != "NOT_RETURNED":
            _factor(positive)
        if negative != "NOT_RETURNED":
            _factor(negative)
        if positive != "NOT_RETURNED" or negative != "NOT_RETURNED":
            state = "PRESENT"
    if homes is None:
        pass
    elif not isinstance(homes, list):
        raise Failure("SCHEMA_REJECTED", {"field": "homeConversions"})
    elif len(homes) == 0:
        state = "NOT_RETURNED" if state == "NOT_RETURNED" else "PARTIAL"
    elif len(homes) > 1:
        quoted = "AMBIGUOUS"
        state = "AMBIGUOUS"
    elif isinstance(homes[0], dict):
        quoted = _shown(homes[0].get("currency"))
        gain = _shown(homes[0].get("accountGain"))
        loss = _shown(homes[0].get("accountLoss"))
        if gain != "NOT_RETURNED":
            _factor(gain)
        if loss != "NOT_RETURNED":
            _factor(loss)
        state = "AMBIGUOUS" if state == "AMBIGUOUS" else "PRESENT"
    else:
        raise Failure("SCHEMA_REJECTED", {"field": "homeConversions"})
    return {
        "positive_units_factor": positive,
        "negative_units_factor": negative,
        "account_gain_factor": gain,
        "account_loss_factor": loss,
        "quoted_conversion_currency": quoted,
        "quoted_conversion_currency_is_account_home": "NO",
        "conversion_state": state,
        "gbp_conversion_suitability": "NOT_VERIFIED",
    }


def _factor(text: str) -> None:
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        raise Failure("SCHEMA_REJECTED", {"field": "conversion"}) from None
    if not value.is_finite():
        raise Failure("SCHEMA_REJECTED", {"field": "conversion"})


def validate_pricing(payload: dict[str, Any], instruments: list[dict[str, str]]) -> list[dict[str, str]]:
    plan = _load_plan()
    rows = payload.get("prices")
    if not isinstance(rows, list):
        raise Failure("SCHEMA_REJECTED", {"field": "prices"})
    locations = {row["instrument"]: row["pip_location"] for row in instruments}
    found: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            raise Failure("SCHEMA_REJECTED", {"field": "price"})
        name = _text(item.get("instrument"))
        if name is None or name not in plan.SIX:
            raise Failure("SCHEMA_REJECTED", {"field": "unexpected_instrument", "instrument": name or "MISSING"})
        if name in found:
            raise Failure("SCHEMA_REJECTED", {"field": "duplicate_instrument", "instrument": name})
        found[name] = item
    missing = [name for name in plan.SIX if name not in found]
    if missing:
        raise Failure("SCHEMA_REJECTED", {"field": "missing_price", "instrument": missing[0]})
    built = []
    for name in plan.SIX:
        item = found[name]
        if "time" not in item or item.get("time") in (None, ""):
            raise Failure("MISSING_TIMESTAMP", {"field": "time", "instrument": name})
        stamp = _text(item.get("time"))
        if stamp is None or _TIME.fullmatch(stamp) is None:
            raise Failure("MALFORMED_TIMESTAMP", {"field": "time", "instrument": name})
        tradeable = item.get("tradeable")
        if not isinstance(tradeable, bool):
            raise Failure("SCHEMA_REJECTED", {"field": "tradeable", "instrument": name})
        bids = item.get("bids")
        asks = item.get("asks")
        bid = _text(bids[0].get("price")) if isinstance(bids, list) and bids and isinstance(bids[0], dict) else None
        ask = _text(asks[0].get("price")) if isinstance(asks, list) and asks and isinstance(asks[0], dict) else None
        if bid is None or ask is None:
            raise Failure("SCHEMA_REJECTED", {"field": "missing_price", "instrument": name})
        spread = _spread(bid, ask, locations[name])
        conversion = _conversion(item)
        quote_usable = "YES" if tradeable else "NO"
        if quote_usable == "NO":
            raise Failure("SCHEMA_REJECTED", {"field": "tradeable", "instrument": name, "tradeable": "false"})
        built.append(
            {
                "instrument": name,
                "time": stamp,
                "bid": bid,
                "ask": ask,
                "spread_pips": spread,
                "tradeable": "true",
                "quote_usable": quote_usable,
                "quote_staleness_rule": "NOT_DEFINED",
                **conversion,
            }
        )
    return built
