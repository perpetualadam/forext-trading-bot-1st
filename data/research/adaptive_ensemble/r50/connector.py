"""Offline read-only research connector. No production imports and no network."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

LIVE_DISABLED = "R50_LIVE_ACCESS_DISABLED"
REJECTED = "R50_REJECTED"
SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?$")
_NOT = "NOT_RETURNED"


class LiveAccessDisabled(RuntimeError):
    """Real network access is not implemented."""


class Rejected(RuntimeError):
    """Fail closed. The message is a fixed code."""


def _gate():
    path = Path(__file__).resolve().parents[1] / "r48" / "readonly_transport.py"
    spec = importlib.util.spec_from_file_location("r48_readonly_transport", path)
    if spec is None or spec.loader is None:
        raise LiveAccessDisabled(LIVE_DISABLED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def enable_live(**_ignored: Any) -> None:
    """Flags, phrases, and overrides cannot open a connection."""
    raise LiveAccessDisabled(LIVE_DISABLED)


def launch(argv: list[str] | None = None) -> int:
    """Normal entry. Arguments are ignored and are not printed."""
    _ = [] if argv is None else argv
    print("Live verification remains unauthorised. No credential prompt. No network connection.")
    return 0


def _require(value: str) -> None:
    if not isinstance(value, str) or value == "" or value != value.strip() or any(ch in value for ch in "/?#& \r\n\t"):
        raise Rejected(REJECTED)


def _query(kind: str) -> dict[str, str]:
    names = ",".join(SIX)
    if kind == "instruments":
        return {"instruments": names}
    if kind == "pricing":
        return {"instruments": names, "includeHomeConversions": "true"}
    raise Rejected(REJECTED)


def prepare(kind: str, account_id: str, token: str, **extra: Any) -> dict[str, Any]:
    if extra:
        raise Rejected(REJECTED)
    _require(account_id)
    _require(token)
    gate = _gate()
    try:
        path = gate.build_path(kind, account_id)
        gate.assert_request("GET", gate.ALLOWED_HOST, path, tuple(_query(kind)))
    except Rejected:
        raise
    except Exception:
        raise Rejected(REJECTED) from None
    return {
        "method": "GET",
        "host": gate.ALLOWED_HOST,
        "path": path,
        "query": _query(kind),
        "timeout_seconds": gate.timeout_seconds(),
        "retries": gate.retry_limit(),
        "redirects": False,
        "body": None,
        "stream": False,
        "authorization": "Bearer " + token,
    }


def _number(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        raise Rejected(REJECTED) from None
    if not value.is_finite():
        raise Rejected(REJECTED)
    return value


def _spread(bid: str, ask: str, pip_location: str) -> str:
    bid_n = _number(bid)
    ask_n = _number(ask)
    if bid_n <= 0 or ask_n <= 0 or ask_n < bid_n:
        raise Rejected(REJECTED)
    try:
        location = int(pip_location)
    except ValueError:
        raise Rejected(REJECTED) from None
    width = (ask_n - bid_n) / (Decimal(10) ** location)
    rendered = format(width, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _shown(value: Any) -> str:
    if value in (None, "", "MISSING"):
        return _NOT
    return str(value)


def _check_names(names: list[str]) -> None:
    if any(name not in SIX for name in names):
        raise Rejected(REJECTED)
    if len(names) != len(set(names)):
        raise Rejected(REJECTED)


def _instruments(gate: Any, payload: Any) -> list[dict[str, Any]]:
    try:
        rows = gate.parse_instruments(payload)
    except Exception:
        raise Rejected(REJECTED) from None
    _check_names([row["instrument"] for row in rows])
    return rows


def _prices(gate: Any, payload: Any, locations: dict[str, str]) -> list[dict[str, Any]]:
    try:
        rows = gate.parse_pricing(payload, locations)
    except Exception:
        raise Rejected(REJECTED) from None
    _check_names([row["instrument"] for row in rows])
    for row in rows:
        if row.get("time") not in (None, "MISSING") and not _TIME.fullmatch(str(row["time"])):
            raise Rejected(REJECTED)
        if row.get("bid") not in (None, "MISSING") and row.get("ask") not in (None, "MISSING"):
            location = locations.get(row["instrument"])
            if location and location != "MISSING":
                row["spread_pips"] = _spread(row["bid"], row["ask"], location)
    return rows


def _blank(name: str) -> dict[str, str]:
    return {
        "instrument": name,
        "eligibility_evidence": _NOT,
        "evidence_class": "SYNTHETIC_TEST_ONLY",
        "pip_location": _NOT,
        "trade_unit_precision": _NOT,
        "minimum_size": _NOT,
        "margin_rate": _NOT,
        "bid": _NOT,
        "ask": _NOT,
        "spread_pips": _NOT,
        "conversion_factors": _NOT,
        "stop_restrictions": _NOT,
        "financing_fields": _NOT,
        "remaining_gbp_sizing": "UNKNOWN",
    }


def _matrix(instruments: list[dict[str, Any]], prices: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_name = {row["instrument"]: row for row in instruments}
    by_price = {row["instrument"]: row for row in prices}
    rows = []
    for name in SIX:
        item = by_name.get(name)
        price = by_price.get(name)
        if item is None:
            rows.append(_blank(name))
            continue
        factors = price.get("quoteHomeConversionFactors") if price else None
        home = price.get("homeConversions") if price else None
        factor_values = []
        if isinstance(factors, dict):
            factor_values.extend(factors.get(key) for key in ("positiveUnits", "negativeUnits"))
        if isinstance(home, list) and home and isinstance(home[0], dict):
            factor_values.extend(home[0].get(key) for key in ("accountGain", "accountLoss"))
        conversion = "PRESENT" if any(value not in (None, "MISSING", _NOT) for value in factor_values) else _NOT
        stop = _shown(item.get("minimumTrailingStopDistance"))
        mode = _shown(item.get("guaranteedStopLossOrderMode"))
        financing = "PRESENT" if item.get("financingLongRate") not in (None, "MISSING") else _NOT
        rows.append(
            {
                "instrument": name,
                "eligibility_evidence": "SYNTHETIC_TEST_ONLY",
                "evidence_class": "SYNTHETIC_TEST_ONLY",
                "pip_location": _shown(item.get("pipLocation")),
                "trade_unit_precision": _shown(item.get("tradeUnitsPrecision")),
                "minimum_size": _shown(item.get("minimumTradeSize")),
                "margin_rate": _shown(item.get("marginRate")),
                "bid": _shown(price.get("bid")) if price else _NOT,
                "ask": _shown(price.get("ask")) if price else _NOT,
                "spread_pips": _shown(price.get("spread_pips")) if price else _NOT,
                "positive_units_factor": _shown(factors.get("positiveUnits")) if isinstance(factors, dict) else _NOT,
                "negative_units_factor": _shown(factors.get("negativeUnits")) if isinstance(factors, dict) else _NOT,
                "account_gain_factor": _shown(home[0].get("accountGain")) if isinstance(home, list) and home else _NOT,
                "account_loss_factor": _shown(home[0].get("accountLoss")) if isinstance(home, list) and home else _NOT,
                "conversion_factors": conversion,
                "stop_restrictions": "PRESENT" if stop != _NOT or mode != _NOT else _NOT,
                "guaranteed_stop_mode": mode,
                "financing_fields": financing,
                "financing_long_rate": _shown(item.get("financingLongRate")),
                "financing_short_rate": _shown(item.get("financingShortRate")),
                "remaining_gbp_sizing": "UNKNOWN",
            }
        )
    return rows


def _guard(document: dict[str, Any], secrets: tuple[str, ...]) -> dict[str, Any]:
    blob = json.dumps(document)
    for secret in secrets:
        if secret and secret in blob:
            raise Rejected(REJECTED)
    if "Bearer" in blob or "Authorization" in blob or "https://" in blob or "1.35" in blob:
        raise Rejected(REJECTED)
    return document


def run_synthetic(account_id: str, token: str, transport: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """Run the two allowlisted reads against an injected transport."""
    _require(account_id)
    _require(token)
    gate = _gate()
    payloads: dict[str, Any] = {}
    for kind in ("instruments", "pricing"):
        prepared = prepare(kind, account_id, token)
        try:
            response = transport(prepared)
        except Rejected:
            raise
        except Exception:
            raise Rejected(REJECTED) from None
        if not isinstance(response, dict) or response.get("status") != 200:
            raise Rejected(REJECTED)
        try:
            gate.accept_status(int(response["status"]))
        except Exception:
            raise Rejected(REJECTED) from None
        payloads[kind] = response.get("payload")
    try:
        instruments = _instruments(gate, payloads["instruments"])
    except Rejected:
        raise
    locations = {
        row["instrument"]: row["pipLocation"]
        for row in instruments
        if row.get("pipLocation") not in (None, "MISSING")
    }
    prices = _prices(gate, payloads["pricing"], locations)
    document = {
        "evidence_class": "SYNTHETIC_TEST_ONLY",
        "rows": _matrix(instruments, prices),
        "ticket_comparison": _ticket_comparison(),
        "user_reported_financing_panel": _financing_panel(),
        "synthetic_financing_is_not_the_panel": True,
    }
    return _guard(document, (account_id, token))


def _ticket_comparison() -> list[dict[str, str]]:
    return [
        {"item": "quantity 1", "class": "ROUNDED_INTERFACE_OBSERVATION", "account_confirmation": "NO"},
        {"item": "units available 3476", "class": "ROUNDED_INTERFACE_OBSERVATION", "account_confirmation": "NO"},
        {"item": "trade value 0.84 GBP", "class": "ROUNDED_INTERFACE_OBSERVATION", "account_confirmation": "NO"},
        {"item": "one pip 0.00 GBP", "class": "ROUNDED_INTERFACE_OBSERVATION", "zero_risk": "NO"},
        {"item": "margin required 0.03 GBP", "class": "ROUNDED_INTERFACE_OBSERVATION", "fixed_rate": "NO"},
        {"item": "synthetic instrument metadata", "class": "SYNTHETIC_TEST_ONLY", "account_confirmation": "NO"},
        {"item": "synthetic pricing snapshot", "class": "SYNTHETIC_TEST_ONLY", "real_spread": "NO"},
        {"item": "stake to units mapping", "class": "UNKNOWN", "account_confirmation": "NO"},
    ]


def _financing_panel() -> dict[str, str]:
    return {
        "class": "USER_REPORTED_HISTORICAL_DISPLAY",
        "buy_annualised": "-2.43%",
        "buy_estimate_per_100000_units": "16.75 GBP",
        "sell_annualised": "+0.42%",
        "sell_estimate_per_100000_units": "2.90 GBP",
        "displayed_time": "22:00 GMT+1",
        "confirmed_by_synthetic_fields": "NO",
    }


def write_clean(path: Path, document: dict[str, Any], secrets: tuple[str, ...]) -> None:
    safe = _guard(document, secrets)
    path.write_text(json.dumps(safe, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
