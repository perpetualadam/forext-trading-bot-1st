"""Sanitised evidence and structural checks for synthetic responses.

Successful output is written only when both responses validate. Failure leaves no success file.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
SYNTHETIC = "SYNTHETIC_TEST_ONLY"
OUTPUT_NAME = "synthetic_output.json"


def _gate() -> Any:
    name = "r55g2_request_gate"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / "request_gate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secrets() -> tuple[str, ...]:
    creds = _creds()
    return (
        creds.ACCOUNT,
        creds.TOKEN,
        "Bearer",
        "Authorization",
        "https://",
        "http://",
        "ACCOUNT_VERIFIED",
        "1.35",
    )


def _creds() -> Any:
    name = "r55g2_credential_boundary"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / "credential_boundary.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _finite_price(text: str) -> Decimal:
    gate = _gate()
    try:
        value = Decimal(str(text))
    except (InvalidOperation, ValueError):
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "price"}) from None
    if not value.is_finite() or value <= 0:
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "price"})
    return value


def _spread(bid: str, ask: str, pip_location: str) -> str:
    gate = _gate()
    left = _finite_price(bid)
    right = _finite_price(ask)
    if left > right:
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "bid_ask"})
    try:
        location = int(pip_location)
    except ValueError:
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "pipLocation"}) from None
    width = (right - left) / (Decimal(10) ** location)
    if not width.is_finite():
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "spread"})
    rendered = format(width, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def parse_body(raw: bytes) -> dict[str, Any]:
    gate = _gate()
    if not isinstance(raw, (bytes, bytearray)):
        raise gate.GateRejected("MALFORMED_JSON")
    if len(raw) > gate.MAX_BODY:
        raise gate.GateRejected("RESPONSE_TOO_LARGE")
    try:
        payload = json.loads(bytes(raw).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise gate.GateRejected("MALFORMED_JSON") from None
    if not isinstance(payload, dict):
        raise gate.GateRejected("MALFORMED_JSON")
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


def _factor(text: str) -> None:
    gate = _gate()
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "conversion"}) from None
    if not value.is_finite():
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "conversion"})


def validate_instruments(payload: dict[str, Any]) -> list[dict[str, str]]:
    gate = _gate()
    rows = payload.get("instruments")
    if not isinstance(rows, list):
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "instruments"})
    found: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "instrument"})
        name = _text(item.get("name"))
        if name is None:
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "name"})
        if name not in gate.SIX:
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "unexpected_instrument", "instrument": name})
        if name in found:
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "duplicate_instrument", "instrument": name})
        found[name] = item
    missing = [name for name in gate.SIX if name not in found]
    if missing:
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "missing_instrument", "instrument": missing[0]})
    built = []
    for name in gate.SIX:
        item = found[name]
        pip = _text(item.get("pipLocation"))
        if pip is None:
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "pipLocation", "instrument": name})
        try:
            int(pip)
        except ValueError:
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "pipLocation", "instrument": name}) from None
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
    gate = _gate()
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
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "homeConversions"})
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
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "homeConversions"})
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


def validate_pricing(payload: dict[str, Any], instruments: list[dict[str, str]]) -> list[dict[str, str]]:
    gate = _gate()
    rows = payload.get("prices")
    if not isinstance(rows, list):
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "prices"})
    locations = {row["instrument"]: row["pip_location"] for row in instruments}
    found: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "price"})
        name = _text(item.get("instrument"))
        if name is None or name not in gate.SIX:
            raise gate.GateRejected(
                "SCHEMA_REJECTED",
                {"field": "unexpected_instrument", "instrument": name or "MISSING"},
            )
        if name in found:
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "duplicate_instrument", "instrument": name})
        found[name] = item
    missing = [name for name in gate.SIX if name not in found]
    if missing:
        raise gate.GateRejected("SCHEMA_REJECTED", {"field": "missing_price", "instrument": missing[0]})
    built = []
    for name in gate.SIX:
        item = found[name]
        if "time" not in item or item.get("time") in (None, ""):
            raise gate.GateRejected("MISSING_TIMESTAMP", {"field": "time", "instrument": name})
        stamp = _text(item.get("time"))
        if stamp is None or _TIME.fullmatch(stamp) is None:
            raise gate.GateRejected("MALFORMED_TIMESTAMP", {"field": "time", "instrument": name})
        tradeable = item.get("tradeable")
        if not isinstance(tradeable, bool):
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "tradeable", "instrument": name})
        bids = item.get("bids")
        asks = item.get("asks")
        bid = _text(bids[0].get("price")) if isinstance(bids, list) and bids and isinstance(bids[0], dict) else None
        ask = _text(asks[0].get("price")) if isinstance(asks, list) and asks and isinstance(asks[0], dict) else None
        if bid is None or ask is None:
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "missing_price", "instrument": name})
        spread = _spread(bid, ask, locations[name])
        conversion = _conversion(item)
        if tradeable is not True:
            raise gate.GateRejected("SCHEMA_REJECTED", {"field": "tradeable", "instrument": name})
        built.append(
            {
                "instrument": name,
                "time": stamp,
                "bid": bid,
                "ask": ask,
                "spread_pips": spread,
                "tradeable": "true",
                "quote_usable": "YES",
                "quote_staleness_rule": "NOT_DEFINED",
                "quote_freshness": "NOT_VERIFIED",
                **conversion,
            }
        )
    return built


def endpoint_result(
    kind: str,
    result: str,
    classification: str,
    http_status: str,
    detail: dict[str, str] | None = None,
) -> dict[str, str]:
    row = {
        "endpoint": kind,
        "result": result,
        "error_classification": classification,
        "http_status": http_status,
        "evidence_class": SYNTHETIC,
    }
    if detail:
        field = detail.get("field", "")
        instrument = detail.get("instrument", "")
        allowed_fields = {
            "instruments",
            "instrument",
            "name",
            "pipLocation",
            "price",
            "bid_ask",
            "prices",
            "missing_instrument",
            "missing_price",
            "unexpected_instrument",
            "duplicate_instrument",
            "time",
            "tradeable",
            "homeConversions",
            "conversion",
            "spread",
        }
        if field in allowed_fields:
            row["field"] = field
        if isinstance(instrument, str) and len(instrument) == 7 and instrument[3] == "_" and instrument.isupper():
            row["instrument"] = instrument
    return row


def document(
    attempted: int,
    http_ok: int,
    validated: int,
    results: list[dict[str, str]],
    rows: list[dict[str, str]],
    per_request: float,
    session_budget: float,
) -> dict[str, Any]:
    gate = _gate()
    missing = "NONE"
    if validated != 2:
        missing = "NOT_VALIDATED"
    elif any(
        "NOT_RETURNED" in row.values() or row.get("conversion_state") in {"NOT_RETURNED", "AMBIGUOUS", "PARTIAL"}
        for row in rows
    ):
        missing = "NOT_RETURNED"
    payload = {
        "evidence_class": SYNTHETIC,
        "account_specific_api_evidence": "NOT_PRODUCED",
        "authentication": "AUTHENTICATION_NOT_PERFORMED",
        "account_verified": "NO",
        "broker_pricing": "SYNTHETIC_FIXTURE",
        "live_connection": "DISABLED",
        "requests_planned": 2,
        "requests_attempted": attempted,
        "successful_http_responses": http_ok,
        "validated_sanitised_responses": validated,
        "endpoint_order": ["instruments", "pricing"],
        "endpoint_results": results,
        "rows": rows,
        "missing_field_status": missing,
        "account_home_currency": "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED",
        "gbp_conversion_suitability": "NOT_VERIFIED",
        "spread_bet_stake_map": "NOT_VERIFIED",
        "gbp_pip_value": "NOT_VERIFIED",
        "financing": "NOT_VERIFIED",
        "token_permissions": "UNKNOWN",
        "executable_trade_sizing": "NOT_CALCULATED",
        "strategy_profitability": "NOT_ESTABLISHED",
        "quote_staleness_rule": "NOT_DEFINED",
        "quote_freshness": "NOT_VERIFIED",
        "option_b_account_summary": "NOT_AUTHORISED",
        "per_request_timeout_seconds": per_request,
        "total_session_deadline_seconds": session_budget,
        "timeout_enforcement": "PHASE_BUDGET_ENFORCED_ON_OFFLINE_INTERFACE",
        "live_socket_timeout": "NOT_EXERCISED",
        "dns_getaddrinfo": "NOT_CALLED",
        "approved_per_request_cap_seconds": gate.PER_REQUEST_TIMEOUT_SECONDS,
        "approved_session_cap_seconds": gate.TOTAL_SESSION_DEADLINE_SECONDS,
    }
    guard(json.dumps(payload))
    return payload


def guard(blob: str) -> None:
    gate = _gate()
    if any(secret in blob for secret in _secrets()):
        raise gate.GateRejected(gate.REJECTED)


def output_target(path: Path | None) -> Path | None:
    gate = _gate()
    if path is None:
        return None
    resolved = path.resolve()
    if resolved.name != OUTPUT_NAME or resolved.is_symlink():
        raise gate.GateRejected(gate.REJECTED)
    return resolved


def retire(path: Path | None) -> None:
    target = output_target(path)
    if target is not None and target.is_file() and not target.is_symlink():
        target.unlink()


def write_success(path: Path | None, payload: dict[str, Any]) -> bool:
    """Write only a fully validated document. A rejected document leaves no file."""
    target = output_target(path)
    if target is None:
        return False
    if payload.get("validated_sanitised_responses") != 2:
        return False
    blob = json.dumps(payload, indent=2) + "\n"
    guard(blob)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(blob, encoding="utf-8")
    temporary.replace(target)
    return True
