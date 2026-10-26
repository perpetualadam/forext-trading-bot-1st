"""Isolated HTTPS adapter. Launching it cannot open a connection or ask for a credential."""

from __future__ import annotations

import http.client
import importlib.util
import json
import ssl
import sys
from pathlib import Path
from typing import Any, Callable

LIVE_DISABLED = "R51_LIVE_TRANSPORT_DISABLED"
REJECTED = "R51_REJECTED"
HOME_CURRENCY = "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
HOST = "api-fxtrade.oanda.com"
TIMEOUT_SECONDS = 5.0
MAX_CALLS = 2
MAX_BODY = 1_048_576
SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
_NOT = "NOT_RETURNED"


class LiveTransportDisabled(RuntimeError):
    """No live connection is available in this stage."""


class Rejected(RuntimeError):
    """Fail closed. The message is a fixed code."""


class Budget:
    def __init__(self, limit: int = MAX_CALLS) -> None:
        self.limit = limit
        self.used = 0

    def consume(self) -> None:
        if self.used >= self.limit:
            raise Rejected(REJECTED)
        self.used += 1


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise LiveTransportDisabled(LIVE_DISABLED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _r50() -> Any:
    return _load("r50_connector", Path(__file__).resolve().parents[1] / "r50" / "connector.py")


def _r48() -> Any:
    return _load("r48_readonly_transport", Path(__file__).resolve().parents[1] / "r48" / "readonly_transport.py")


def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    if context.verify_mode != ssl.CERT_REQUIRED or context.check_hostname is not True:
        raise Rejected(REJECTED)
    return context


def blocked_factory(*_args: Any, **_kwargs: Any) -> None:
    """The real host class is not used. This stand-in opens nothing."""
    raise LiveTransportDisabled(LIVE_DISABLED)


def future_credential_entry(*_args: Any, **_kwargs: Any) -> None:
    """Credential entry is not implemented. This function does not prompt."""
    raise LiveTransportDisabled(LIVE_DISABLED)


def enable_live(**_ignored: Any) -> None:
    """A flag, phrase, or override cannot start a connection."""
    raise LiveTransportDisabled(LIVE_DISABLED)


def launch(argv: list[str] | None = None) -> int:
    """Normal entry. Arguments are ignored and are not printed."""
    _ = [] if argv is None else argv
    print("Live verification remains unauthorised. No credential prompt. No network connection.")
    return 0


def disabled_preview() -> dict[str, Any]:
    """Safe description of the future two reads. It has no account identifier and no URL."""
    return {
        "mode": "NETWORK_DISABLED",
        "live_entry_point": "NOT_IMPLEMENTED",
        "host": HOST,
        "method": "GET",
        "templates": [
            "/v3/accounts/{accountID}/instruments",
            "/v3/accounts/{accountID}/pricing",
        ],
        "instruments": list(SIX),
        "include_home_conversions": True,
        "timeout_seconds": TIMEOUT_SECONDS,
        "maximum_calls": MAX_CALLS,
        "redirects": False,
        "retries": 0,
        "body": None,
        "stream": False,
        "tls": "CERT_REQUIRED",
        "account_home_currency": HOME_CURRENCY,
    }


def _shown(value: Any) -> str:
    if value in (None, "", "MISSING"):
        return _NOT
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _kind(path: str) -> str:
    if not isinstance(path, str) or path.count("/") != 4:
        raise Rejected(REJECTED)
    head, _, kind = path.rpartition("/")
    if kind not in ("instruments", "pricing") or not head.startswith("/v3/accounts/"):
        raise Rejected(REJECTED)
    account = head[len("/v3/accounts/") :]
    if account == "" or account == "{accountID}" or any(ch in account for ch in "/?#& \r\n\t"):
        raise Rejected(REJECTED)
    return kind


def _specify(prepared: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(prepared, dict):
        raise Rejected(REJECTED)
    allowed = {
        "method",
        "host",
        "path",
        "query",
        "timeout_seconds",
        "retries",
        "redirects",
        "body",
        "stream",
        "authorization",
    }
    if set(prepared) != allowed:
        raise Rejected(REJECTED)
    if prepared.get("method") != "GET" or prepared.get("host") != HOST:
        raise Rejected(REJECTED)
    if prepared.get("timeout_seconds") != TIMEOUT_SECONDS or isinstance(prepared.get("timeout_seconds"), bool):
        raise Rejected(REJECTED)
    if prepared.get("retries") != 0 or prepared.get("redirects") is not False:
        raise Rejected(REJECTED)
    if prepared.get("body") is not None or prepared.get("stream") is not False:
        raise Rejected(REJECTED)
    kind = _kind(prepared.get("path"))
    query = prepared.get("query")
    names = ",".join(SIX)
    if not isinstance(query, dict) or query.get("instruments") != names:
        raise Rejected(REJECTED)
    if kind == "instruments" and set(query) != {"instruments"}:
        raise Rejected(REJECTED)
    if kind == "pricing":
        if set(query) != {"instruments", "includeHomeConversions"} or query.get("includeHomeConversions") != "true":
            raise Rejected(REJECTED)
    token_header = prepared.get("authorization")
    if not isinstance(token_header, str) or not token_header.startswith("Bearer ") or token_header == "Bearer ":
        raise Rejected(REJECTED)
    target = prepared["path"] + "?instruments=" + names
    if kind == "pricing":
        target += "&includeHomeConversions=true"
    return {
        "host": HOST,
        "timeout": TIMEOUT_SECONDS,
        "context": tls_context(),
        "method": "GET",
        "target": target,
        "headers": {"Accept": "application/json", "Authorization": token_header},
        "kind": kind,
    }


def _refuse(connection_factory: Callable[..., Any] | None) -> None:
    if connection_factory is None or connection_factory is http.client.HTTPSConnection or connection_factory is blocked_factory:
        raise LiveTransportDisabled(LIVE_DISABLED)


def exchange(prepared: dict[str, Any], connection_factory: Callable[..., Any] | None, budget: Budget) -> dict[str, Any]:
    """Perform one GET on an injected connection. The real host class is refused."""
    spec = _specify(prepared)
    _refuse(connection_factory)
    budget.consume()
    conn: Any = None
    try:
        conn = connection_factory(host=spec["host"], timeout=spec["timeout"], context=spec["context"])
        conn.request("GET", spec["target"], body=None, headers=spec["headers"])
        response = conn.getresponse()
        if getattr(response, "status", None) != 200:
            raise Rejected(REJECTED)
        raw = response.read(MAX_BODY + 1)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_BODY:
            raise Rejected(REJECTED)
        try:
            payload = json.loads(bytes(raw).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            raise Rejected(REJECTED) from None
        if not isinstance(payload, dict):
            raise Rejected(REJECTED)
        return {"status": 200, "payload": payload}
    except (Rejected, LiveTransportDisabled):
        raise
    except Exception:
        raise Rejected(REJECTED) from None
    finally:
        if conn is not None:
            closer = getattr(conn, "close", None)
            if closer is not None:
                try:
                    closer()
                except Exception:
                    pass


def _schema(instruments: list[dict[str, Any]], prices: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_name = {row["instrument"]: row for row in instruments}
    by_price = {row["instrument"]: row for row in prices}
    if any(name not in SIX for name in by_name) or any(name not in SIX for name in by_price):
        raise Rejected(REJECTED)
    rows: list[dict[str, str]] = []
    for name in SIX:
        item = by_name.get(name)
        price = by_price.get(name)
        if item is None or price is None:
            raise Rejected(REJECTED)
        factors = price.get("quoteHomeConversionFactors")
        home = price.get("homeConversions")
        home_row = home[0] if isinstance(home, list) and home and isinstance(home[0], dict) else {}
        factor_row = factors if isinstance(factors, dict) else {}
        rows.append(
            {
                "instrument": name,
                "type": _shown(item.get("type")),
                "pip_location": _shown(item.get("pipLocation")),
                "display_precision": _shown(item.get("displayPrecision")),
                "trade_unit_precision": _shown(item.get("tradeUnitsPrecision")),
                "minimum_trade_size": _shown(item.get("minimumTradeSize")),
                "maximum_order_units": _shown(item.get("maximumOrderUnits")),
                "maximum_position_size": _shown(item.get("maximumPositionSize")),
                "margin_rate": _shown(item.get("marginRate")),
                "minimum_trailing_stop_distance": _shown(item.get("minimumTrailingStopDistance")),
                "guaranteed_stop_mode": _shown(item.get("guaranteedStopLossOrderMode")),
                "financing_long_rate": _shown(item.get("financingLongRate")),
                "financing_short_rate": _shown(item.get("financingShortRate")),
                "time": _shown(price.get("time")),
                "bid": _shown(price.get("bid")),
                "ask": _shown(price.get("ask")),
                "spread_pips": _shown(price.get("spread_pips")),
                "tradeable": _shown(price.get("tradeable")),
                "positive_units_factor": _shown(factor_row.get("positiveUnits")),
                "negative_units_factor": _shown(factor_row.get("negativeUnits")),
                "account_gain_factor": _shown(home_row.get("accountGain")),
                "account_loss_factor": _shown(home_row.get("accountLoss")),
                "quoted_conversion_currency": _shown(home_row.get("currency")),
                "quoted_conversion_currency_is_account_home": "NO",
                "account_home_currency": HOME_CURRENCY,
                "stake_settlement": "UNKNOWN",
                "evidence_class": "SYNTHETIC_TEST_ONLY",
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


def run_offline(account_id: str, token: str, connection_factory: Callable[..., Any] | None) -> dict[str, Any]:
    """Run the two R.50 reads through this adapter and an injected factory."""
    _refuse(connection_factory)
    connector = _r50()
    gate = _r48()
    budget = Budget()
    kept: dict[str, Any] = {}
    order: list[str] = []

    def transport(prepared: dict[str, Any]) -> dict[str, Any]:
        kind = _kind(prepared.get("path"))
        response = exchange(prepared, connection_factory, budget)
        kept[kind] = response["payload"]
        order.append(kind)
        return response

    try:
        document = connector.run_synthetic(account_id, token, transport)
    except connector.Rejected:
        raise Rejected(REJECTED) from None
    if order != ["instruments", "pricing"] or budget.used != 2:
        raise Rejected(REJECTED)
    try:
        instruments = gate.parse_instruments(kept.pop("instruments"))
        locations = {
            row["instrument"]: row["pipLocation"]
            for row in instruments
            if row.get("pipLocation") not in (None, "MISSING")
        }
        prices = gate.parse_pricing(kept.pop("pricing"), locations)
    except Rejected:
        raise
    except Exception:
        raise Rejected(REJECTED) from None
    if kept:
        raise Rejected(REJECTED)
    document["schema_rows"] = _schema(instruments, prices)
    document["account_home_currency"] = HOME_CURRENCY
    document["endpoint_order"] = order
    document["calls_completed"] = budget.used
    document["r51_transport"] = "INJECTED_FACTORY"
    document["spread_bet_stake_map"] = "UNKNOWN"
    return _guard(document, (account_id, token))


def write_clean(path: Path, document: dict[str, Any], secrets: tuple[str, ...]) -> None:
    safe = _guard(document, secrets)
    path.write_text(json.dumps(safe, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
