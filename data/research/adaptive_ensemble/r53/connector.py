"""Final offline OANDA read-only connector. Normal execution cannot open a connection."""

from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import ssl
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

R51_PIN = "e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef"
R52_PIN = "59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56"
HOST = "api-fxtrade.oanda.com"
PORT = 443
TIMEOUT_SECONDS = 5.0
MAX_BODY = 1_048_576
LIVE_DISABLED = "R53_LIVE_TRANSPORT_DISABLED"
REJECTED = "R53_REJECTED"
HOME_CURRENCY = "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
_NOT = "NOT_RETURNED"
_ROW_KEYS = (
    "instrument",
    "type",
    "pip_location",
    "display_precision",
    "trade_unit_precision",
    "minimum_trade_size",
    "maximum_order_units",
    "maximum_position_size",
    "margin_rate",
    "minimum_trailing_stop_distance",
    "guaranteed_stop_mode",
    "financing_long_rate",
    "financing_short_rate",
    "time",
    "bid",
    "ask",
    "spread_pips",
    "tradeable",
    "positive_units_factor",
    "negative_units_factor",
    "account_gain_factor",
    "account_loss_factor",
    "quoted_conversion_currency",
    "quoted_conversion_currency_is_account_home",
    "account_home_currency",
    "stake_settlement",
    "evidence_class",
)
_ENDPOINT_KEYS = (
    "endpoint",
    "result",
    "error_classification",
    "http_status",
    "evidence_class",
    "missing_field_status",
)
_TOP_KEYS = (
    "evidence_class",
    "account_specific_api_evidence",
    "requests_attempted",
    "successful_http_responses",
    "validated_sanitised_responses",
    "endpoint_order",
    "endpoint_results",
    "account_home_currency",
    "rows",
    "missing_field_status",
    "remaining_blockers",
    "historical_ticket",
    "historical_financing_panel",
)
_TICKET_KEYS = (
    "class",
    "api_confirmation",
    "quantity",
    "units_available",
    "used_as_position_cap",
    "trade_value_gbp",
    "one_pip_gbp",
    "one_pip_is_zero_risk",
    "margin_required_gbp",
    "margin_is_fixed_rate",
)
_PANEL_KEYS = (
    "class",
    "api_confirmation",
    "buy_annualised",
    "buy_estimate_gbp_per_100000_units",
    "sell_annualised",
    "sell_estimate_gbp_per_100000_units",
    "displayed_time",
)
_CLASSIFICATIONS = {
    "NONE",
    "HTTP_ERROR",
    "TIMEOUT",
    "TLS_FAILURE",
    "MALFORMED_JSON",
    "SCHEMA_REJECTED",
    "RESPONSE_TOO_LARGE",
    "UNEXPECTED",
}
_BANNED_KEYS = {
    "token",
    "authorization",
    "account_id",
    "accountid",
    "url",
    "raw",
    "balance",
    "nav",
    "positions",
    "orders",
    "transactions",
    "password",
    "secret",
    "executable_units",
}


class LiveTransportDisabled(RuntimeError):
    """No live connection is available in this stage."""


class Rejected(RuntimeError):
    """Fail closed. The message is a fixed code."""


class Failure(Rejected):
    """A classified transport or schema failure. The text is still the fixed code."""

    def __init__(self, classification: str, http_ok: bool = False) -> None:
        if classification not in _CLASSIFICATIONS or classification == "NONE":
            classification = "UNEXPECTED"
        self.classification = classification
        self.http_ok = http_ok
        super().__init__(REJECTED)


class MemoryCredential:
    """In-memory holder. Its text form has no identifier and no token."""

    __slots__ = ("account_id", "token")

    def __init__(self, account_id: str, token: str) -> None:
        self.account_id = account_id
        self.token = token

    def __repr__(self) -> str:
        return "MemoryCredential()"

    def __str__(self) -> str:
        return "MemoryCredential()"


def _prior_path(stage: str, name: str) -> Path:
    return Path(__file__).resolve().parents[1] / stage / name


def prior_hashes() -> dict[str, str]:
    return {
        "r51": hashlib.sha256(_prior_path("r51", "https_adapter.py").read_bytes()).hexdigest(),
        "r52": hashlib.sha256(_prior_path("r52", "session_entry.py").read_bytes()).hexdigest(),
    }


def require_prior_hashes() -> None:
    found = prior_hashes()
    if found["r51"] != R51_PIN or found["r52"] != R52_PIN:
        raise SystemExit("R53_PRIOR_HASH_MISMATCH")


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise LiveTransportDisabled(LIVE_DISABLED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _r50() -> Any:
    require_prior_hashes()
    return _load("r50_connector_r53", _prior_path("r50", "connector.py"))


def _r48() -> Any:
    require_prior_hashes()
    return _load("r48_gate_r53", _prior_path("r48", "readonly_transport.py"))


def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    if context.verify_mode != ssl.CERT_REQUIRED or context.check_hostname is not True:
        raise Rejected(REJECTED)
    return context


def _live_class(connection_class: Any) -> bool:
    if connection_class is http.client.HTTPSConnection or connection_class is http.client.HTTPConnection:
        return True
    if isinstance(connection_class, type) and issubclass(connection_class, (http.client.HTTPConnection, http.client.HTTPSConnection)):
        return True
    return False


def open_prepared_connection(connection_class: Any) -> Any:
    """Prepare one fixed-host client object. The real client class is refused."""
    require_prior_hashes()
    if connection_class is None or _live_class(connection_class) or not isinstance(connection_class, type):
        raise LiveTransportDisabled(LIVE_DISABLED)
    context = tls_context()
    try:
        return connection_class(HOST, PORT, timeout=TIMEOUT_SECONDS, context=context)
    except (LiveTransportDisabled, Rejected):
        raise
    except Exception:
        raise Rejected(REJECTED) from None


def _kind(path: str) -> str:
    if not isinstance(path, str) or path.count("/") != 4:
        raise Failure("SCHEMA_REJECTED")
    head, _, kind = path.rpartition("/")
    if kind not in ("instruments", "pricing") or not head.startswith("/v3/accounts/"):
        raise Failure("SCHEMA_REJECTED")
    account = head[len("/v3/accounts/") :]
    if account == "" or account == "{accountID}" or any(ch in account for ch in "/?#& \r\n\t"):
        raise Failure("SCHEMA_REJECTED")
    return kind


def _target(prepared: dict[str, Any]) -> tuple[str, str]:
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
        raise Failure("SCHEMA_REJECTED")
    if prepared.get("method") != "GET" or prepared.get("host") != HOST:
        raise Failure("SCHEMA_REJECTED")
    if prepared.get("timeout_seconds") != TIMEOUT_SECONDS or isinstance(prepared.get("timeout_seconds"), bool):
        raise Failure("SCHEMA_REJECTED")
    if prepared.get("retries") != 0 or prepared.get("redirects") is not False:
        raise Failure("SCHEMA_REJECTED")
    if prepared.get("body") is not None or prepared.get("stream") is not False:
        raise Failure("SCHEMA_REJECTED")
    kind = _kind(str(prepared.get("path")))
    query = prepared.get("query")
    names = ",".join(SIX)
    if not isinstance(query, dict) or query.get("instruments") != names:
        raise Failure("SCHEMA_REJECTED")
    if kind == "instruments" and set(query) != {"instruments"}:
        raise Failure("SCHEMA_REJECTED")
    if kind == "pricing" and (set(query) != {"instruments", "includeHomeConversions"} or query.get("includeHomeConversions") != "true"):
        raise Failure("SCHEMA_REJECTED")
    header = prepared.get("authorization")
    if not isinstance(header, str) or not header.startswith("Bearer ") or header == "Bearer ":
        raise Failure("SCHEMA_REJECTED")
    target = str(prepared["path"]) + "?instruments=" + names
    if kind == "pricing":
        target += "&includeHomeConversions=true"
    return kind, target


def transmit(prepared: dict[str, Any], connection_class: Any) -> tuple[int, bytes]:
    """Send one GET through an injected client class. The live class is refused."""
    if _live_class(connection_class) or not isinstance(connection_class, type):
        raise LiveTransportDisabled(LIVE_DISABLED)
    _kind_name, target = _target(prepared)
    context = tls_context()
    conn: Any = None
    try:
        conn = connection_class(HOST, PORT, timeout=TIMEOUT_SECONDS, context=context)
        conn.request("GET", target, body=None, headers={"Accept": "application/json", "Authorization": prepared["authorization"]})
        response = conn.getresponse()
        if getattr(response, "status", None) != 200:
            raise Failure("HTTP_ERROR")
        raw = response.read(MAX_BODY + 1)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_BODY:
            raise Failure("RESPONSE_TOO_LARGE", http_ok=True)
        return 200, bytes(raw)
    except Failure:
        raise
    except TimeoutError:
        raise Failure("TIMEOUT") from None
    except ssl.SSLError:
        raise Failure("TLS_FAILURE") from None
    except (LiveTransportDisabled, Rejected):
        raise
    except Exception:
        raise Failure("UNEXPECTED") from None
    finally:
        closer = getattr(conn, "close", None)
        if closer is not None:
            try:
                closer()
            except Exception:
                pass


def parse_body(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise Failure("MALFORMED_JSON", http_ok=True) from None
    if not isinstance(payload, dict):
        raise Failure("MALFORMED_JSON", http_ok=True)
    return payload


def _shown(value: Any) -> str:
    if value in (None, "", "MISSING"):
        return _NOT
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _finite(text: str, positive: bool) -> Decimal:
    try:
        value = Decimal(str(text))
    except (InvalidOperation, ValueError):
        raise Failure("SCHEMA_REJECTED", http_ok=True) from None
    if not value.is_finite() or (positive and value <= 0):
        raise Failure("SCHEMA_REJECTED", http_ok=True)
    return value


def _factor(value: Any) -> str:
    if value in (None, "", "MISSING"):
        return _NOT
    _finite(str(value), positive=False)
    return str(value)


def _spread(bid: str, ask: str, pip_location: str) -> str:
    left = _finite(bid, positive=True)
    right = _finite(ask, positive=True)
    if right < left:
        raise Failure("SCHEMA_REJECTED", http_ok=True)
    try:
        location = int(pip_location)
    except ValueError:
        raise Failure("SCHEMA_REJECTED", http_ok=True) from None
    width = (right - left) / (Decimal(10) ** location)
    if not width.is_finite():
        raise Failure("SCHEMA_REJECTED", http_ok=True)
    rendered = format(width, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _names_ok(names: list[str]) -> None:
    if any(name not in SIX for name in names) or len(names) != len(set(names)):
        raise Failure("SCHEMA_REJECTED", http_ok=True)


def _blank(name: str) -> dict[str, str]:
    row = {key: _NOT for key in _ROW_KEYS}
    row["instrument"] = name
    row["account_home_currency"] = HOME_CURRENCY
    row["quoted_conversion_currency_is_account_home"] = "NO"
    row["stake_settlement"] = "UNKNOWN"
    row["evidence_class"] = "SYNTHETIC_TEST_ONLY"
    return row


def _rows(instruments: list[dict[str, Any]], prices: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_name = {row["instrument"]: row for row in instruments}
    by_price = {row["instrument"]: row for row in prices}
    built = []
    for name in SIX:
        item = by_name.get(name)
        price = by_price.get(name)
        if item is None or price is None:
            built.append(_blank(name))
            continue
        factors = price.get("quoteHomeConversionFactors")
        home = price.get("homeConversions")
        factor_row = factors if isinstance(factors, dict) else {}
        home_row = home[0] if isinstance(home, list) and home and isinstance(home[0], dict) else {}
        pip = _shown(item.get("pipLocation"))
        bid = _shown(price.get("bid"))
        ask = _shown(price.get("ask"))
        spread = _NOT
        if pip != _NOT and bid != _NOT and ask != _NOT:
            spread = _spread(bid, ask, pip)
        built.append(
            {
                "instrument": name,
                "type": _shown(item.get("type")),
                "pip_location": pip,
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
                "bid": bid,
                "ask": ask,
                "spread_pips": spread,
                "tradeable": _shown(price.get("tradeable")),
                "positive_units_factor": _factor(factor_row.get("positiveUnits")),
                "negative_units_factor": _factor(factor_row.get("negativeUnits")),
                "account_gain_factor": _factor(home_row.get("accountGain")),
                "account_loss_factor": _factor(home_row.get("accountLoss")),
                "quoted_conversion_currency": _shown(home_row.get("currency")),
                "quoted_conversion_currency_is_account_home": "NO",
                "account_home_currency": HOME_CURRENCY,
                "stake_settlement": "UNKNOWN",
                "evidence_class": "SYNTHETIC_TEST_ONLY",
            }
        )
    return built


def _missing_status(rows: list[dict[str, str]]) -> str:
    for row in rows:
        if any(value == _NOT for value in row.values()):
            return _NOT
    return "NONE"


def _endpoint(kind: str, result: str, classification: str, http_status: str, missing: str) -> dict[str, str]:
    return {
        "endpoint": kind,
        "result": result,
        "error_classification": classification,
        "http_status": http_status,
        "evidence_class": "SYNTHETIC_TEST_ONLY",
        "missing_field_status": missing,
    }


def _historical() -> tuple[dict[str, str], dict[str, str]]:
    ticket = {
        "class": "USER_REPORTED_TICKET_DISPLAY",
        "api_confirmation": "NO",
        "quantity": "1",
        "units_available": "3476",
        "used_as_position_cap": "NO",
        "trade_value_gbp": "0.84",
        "one_pip_gbp": "0.00",
        "one_pip_is_zero_risk": "NO",
        "margin_required_gbp": "0.03",
        "margin_is_fixed_rate": "NO",
    }
    panel = {
        "class": "USER_REPORTED_HISTORICAL_DISPLAY",
        "api_confirmation": "NO",
        "buy_annualised": "-2.43%",
        "buy_estimate_gbp_per_100000_units": "16.75",
        "sell_annualised": "+0.42%",
        "sell_estimate_gbp_per_100000_units": "2.90",
        "displayed_time": "22:00 GMT+1",
    }
    return ticket, panel


def _document(attempted: int, http_ok: int, validated: int, order: list[str], results: list[dict[str, str]], rows: list[dict[str, str]]) -> dict[str, Any]:
    ticket, panel = _historical()
    missing = _missing_status(rows) if rows else "NOT_VALIDATED"
    return {
        "evidence_class": "SYNTHETIC_TEST_ONLY",
        "account_specific_api_evidence": "NOT_PRODUCED",
        "requests_attempted": attempted,
        "successful_http_responses": http_ok,
        "validated_sanitised_responses": validated,
        "endpoint_order": order,
        "endpoint_results": results,
        "account_home_currency": HOME_CURRENCY,
        "rows": rows,
        "missing_field_status": missing,
        "remaining_blockers": [
            "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED",
            "SPREAD_BET_STAKE_MAP_UNKNOWN",
            "BROKER_TOKEN_PERMISSION_UNKNOWN",
            "NO_EXECUTABLE_SIZE",
            "QUANTITY_ONE_IS_NOT_PROVEN_AS_ONE_POUND_PER_PIP",
            "ONE_PIP_DISPLAY_IS_NOT_ZERO_RISK",
        ],
        "historical_ticket": ticket,
        "historical_financing_panel": panel,
    }


def _banned(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _BANNED_KEYS:
                raise Rejected(REJECTED)
            _banned(item)
    elif isinstance(value, list):
        for item in value:
            _banned(item)


def validate_output(document: dict[str, Any], secrets: tuple[str, ...]) -> dict[str, Any]:
    if set(document) != set(_TOP_KEYS):
        raise Rejected(REJECTED)
    _banned(document)
    if document.get("evidence_class") != "SYNTHETIC_TEST_ONLY":
        raise Rejected(REJECTED)
    if document.get("account_specific_api_evidence") != "NOT_PRODUCED":
        raise Rejected(REJECTED)
    if document.get("account_home_currency") != HOME_CURRENCY:
        raise Rejected(REJECTED)
    attempted = document.get("requests_attempted")
    http_ok = document.get("successful_http_responses")
    validated = document.get("validated_sanitised_responses")
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in (attempted, http_ok, validated)):
        raise Rejected(REJECTED)
    if not 0 <= validated <= http_ok <= attempted <= 2:
        raise Rejected(REJECTED)
    order = document.get("endpoint_order")
    results = document.get("endpoint_results")
    if order not in (["instruments"], ["instruments", "pricing"]) or not isinstance(results, list):
        raise Rejected(REJECTED)
    if len(order) != attempted or len(results) != attempted:
        raise Rejected(REJECTED)
    if [item.get("endpoint") for item in results] != order:
        raise Rejected(REJECTED)
    for item in results:
        if set(item) != set(_ENDPOINT_KEYS):
            raise Rejected(REJECTED)
        if item.get("result") not in ("SUCCESS", "FAILURE"):
            raise Rejected(REJECTED)
        if item.get("error_classification") not in _CLASSIFICATIONS:
            raise Rejected(REJECTED)
        if item.get("evidence_class") != "SYNTHETIC_TEST_ONLY":
            raise Rejected(REJECTED)
        if item.get("missing_field_status") not in ("NONE", "NOT_RETURNED", "NOT_VALIDATED"):
            raise Rejected(REJECTED)
    if document.get("missing_field_status") not in ("NONE", "NOT_RETURNED", "NOT_VALIDATED"):
        raise Rejected(REJECTED)
    rows = document.get("rows")
    if not isinstance(rows, list):
        raise Rejected(REJECTED)
    if validated == 2 and [row.get("instrument") for row in rows] != list(SIX):
        raise Rejected(REJECTED)
    if validated != 2 and rows:
        raise Rejected(REJECTED)
    for row in rows:
        if set(row) != set(_ROW_KEYS) or row.get("evidence_class") != "SYNTHETIC_TEST_ONLY":
            raise Rejected(REJECTED)
        if row.get("account_home_currency") != HOME_CURRENCY or row.get("stake_settlement") != "UNKNOWN":
            raise Rejected(REJECTED)
    if set(document["historical_ticket"]) != set(_TICKET_KEYS) or set(document["historical_financing_panel"]) != set(_PANEL_KEYS):
        raise Rejected(REJECTED)
    blob = json.dumps(document)
    for secret in secrets:
        if secret and secret in blob:
            raise Rejected(REJECTED)
    if "Bearer" in blob or "Authorization" in blob or "https://" in blob or "1.35" in blob or "ACCOUNT_VERIFIED" in blob:
        raise Rejected(REJECTED)
    return document


def _accept_instruments(gate: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        rows = gate.parse_instruments(payload)
    except Failure:
        raise
    except Exception:
        raise Failure("SCHEMA_REJECTED", http_ok=True) from None
    _names_ok([row["instrument"] for row in rows])
    return rows


def _accept_prices(gate: Any, payload: dict[str, Any], locations: dict[str, str]) -> list[dict[str, Any]]:
    try:
        rows = gate.parse_pricing(payload, locations)
    except Failure:
        raise
    except Exception:
        raise Failure("SCHEMA_REJECTED", http_ok=True) from None
    _names_ok([row["instrument"] for row in rows])
    return rows


def run_synthetic(account_id: str, token: str, connection_class: Any) -> dict[str, Any]:
    """Run at most two injected reads. A failure stops the session."""
    if _live_class(connection_class):
        raise LiveTransportDisabled(LIVE_DISABLED)
    credential = accept_credentials(account_id, token)
    connector = _r50()
    gate = _r48()
    attempted = 0
    http_ok = 0
    validated = 0
    order: list[str] = []
    results: list[dict[str, str]] = []
    instruments: list[dict[str, Any]] | None = None
    prices: list[dict[str, Any]] | None = None
    for kind in ("instruments", "pricing"):
        prepared = connector.prepare(kind, credential.account_id, credential.token)
        order.append(kind)
        try:
            _status, raw = transmit(prepared, connection_class)
        except Failure as exc:
            attempted += 1
            if exc.http_ok:
                http_ok += 1
            results.append(_endpoint(kind, "FAILURE", exc.classification, "200" if exc.http_ok else "NONE", "NOT_VALIDATED"))
            break
        attempted += 1
        http_ok += 1
        try:
            payload = parse_body(raw)
            if kind == "instruments":
                instruments = _accept_instruments(gate, payload)
            else:
                locations = {
                    row["instrument"]: row["pipLocation"]
                    for row in instruments or []
                    if row.get("pipLocation") not in (None, "MISSING")
                }
                prices = _accept_prices(gate, payload, locations)
                _rows(instruments or [], prices)
        except Failure as exc:
            results.append(_endpoint(kind, "FAILURE", exc.classification, "200", "NOT_VALIDATED"))
            break
        validated += 1
        results.append(_endpoint(kind, "SUCCESS", "NONE", "200", "NONE"))
    rows = _rows(instruments, prices) if instruments is not None and prices is not None and validated == 2 else []
    if validated == 2:
        status = _missing_status(rows)
        for item in results:
            item["missing_field_status"] = status
    else:
        for item in results:
            if item["result"] != "FAILURE":
                item["missing_field_status"] = "NOT_VALIDATED"
    document = _document(attempted, http_ok, validated, order, results, rows)
    return validate_output(document, (account_id, token))


def write_clean(path: Path, document: dict[str, Any], secrets: tuple[str, ...]) -> None:
    safe = validate_output(document, secrets)
    if safe["validated_sanitised_responses"] != 2 or safe["requests_attempted"] != 2 or safe["successful_http_responses"] != 2:
        raise Rejected(REJECTED)
    if any(item["result"] != "SUCCESS" for item in safe["endpoint_results"]):
        raise Rejected(REJECTED)
    path.write_text(json.dumps(safe, indent=2), encoding="utf-8")


def _require_secret(value: str) -> None:
    if not isinstance(value, str) or value == "" or value != value.strip() or any(ch in value for ch in "/?#& \r\n\t"):
        raise Rejected(REJECTED)


def accept_credentials(account_id: str, token: str) -> MemoryCredential:
    _require_secret(account_id)
    _require_secret(token)
    return MemoryCredential(account_id, token)


def prompt_for_credentials(account_input: Callable[[str], str] | None = None, token_input: Callable[[str], str] | None = None) -> MemoryCredential:
    """Accept injected readers. Calling this without readers does not prompt."""
    if account_input is None or token_input is None:
        raise LiveTransportDisabled(LIVE_DISABLED)
    try:
        account_id = account_input("Account identifier: ")
        token = token_input("API token: ")
    except (LiveTransportDisabled, Rejected):
        raise
    except Exception:
        raise Rejected(REJECTED) from None
    return accept_credentials(account_id, token)


def future_live_entry(*_args: Any, **_kwargs: Any) -> None:
    """Identified for a later approval. It cannot run a session in this stage."""
    raise LiveTransportDisabled(LIVE_DISABLED)


def enable_live(**_ignored: Any) -> None:
    raise LiveTransportDisabled(LIVE_DISABLED)


def launch(argv: list[str] | None = None) -> int:
    """Normal entry. Arguments are ignored and are not printed."""
    _ = [] if argv is None else argv
    require_prior_hashes()
    print("R53 connector is disabled. No credential prompt. No network connection.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
