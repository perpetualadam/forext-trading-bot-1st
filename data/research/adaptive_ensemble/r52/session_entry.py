"""Standalone R.52 entry point. Normal execution cannot open a connection or ask for a credential."""

from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import ssl
import sys
from pathlib import Path
from typing import Any, Callable

R51_PIN = "e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef"
HOST = "api-fxtrade.oanda.com"
PORT = 443
TIMEOUT_SECONDS = 5.0
MAX_BODY = 1_048_576
LIVE_DISABLED = "R52_LIVE_TRANSPORT_DISABLED"
REJECTED = "R52_REJECTED"
HOME_CURRENCY = "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
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


def r51_adapter_path() -> Path:
    return Path(__file__).resolve().parents[1] / "r51" / "https_adapter.py"


def r51_adapter_hash() -> str:
    return hashlib.sha256(r51_adapter_path().read_bytes()).hexdigest()


def require_r51_hash() -> None:
    if r51_adapter_hash() != R51_PIN:
        raise SystemExit("R52_R51_HASH_MISMATCH")


def _r51() -> Any:
    require_r51_hash()
    path = r51_adapter_path()
    spec = importlib.util.spec_from_file_location("r51_https_adapter", path)
    if spec is None or spec.loader is None:
        raise LiveTransportDisabled(LIVE_DISABLED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    """Build one fixed-host connection object. The real client class is refused."""
    require_r51_hash()
    if connection_class is None or _live_class(connection_class) or not isinstance(connection_class, type):
        raise LiveTransportDisabled(LIVE_DISABLED)
    context = tls_context()
    try:
        return connection_class(HOST, PORT, timeout=TIMEOUT_SECONDS, context=context)
    except (LiveTransportDisabled, Rejected):
        raise
    except Exception:
        raise Rejected(REJECTED) from None


def read_bounded(conn: Any, limit: int = MAX_BODY) -> bytes:
    """Read one bounded body from an injected connection. Live client objects are refused."""
    if conn is None or isinstance(conn, (http.client.HTTPConnection, http.client.HTTPSConnection)):
        raise LiveTransportDisabled(LIVE_DISABLED)
    try:
        response = conn.getresponse()
        if getattr(response, "status", None) != 200:
            raise Rejected(REJECTED)
        raw = response.read(limit + 1)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > limit:
            raise Rejected(REJECTED)
        return bytes(raw)
    except (Rejected, LiveTransportDisabled):
        raise
    except Exception:
        raise Rejected(REJECTED) from None
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
        raise Rejected(REJECTED) from None
    if not isinstance(payload, dict):
        raise Rejected(REJECTED)
    return payload


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


def live_session(*_args: Any, **_kwargs: Any) -> None:
    """Future live assembly. It cannot be reached from normal execution."""
    raise LiveTransportDisabled(LIVE_DISABLED)


def enable_live(**_ignored: Any) -> None:
    raise LiveTransportDisabled(LIVE_DISABLED)


def launch(argv: list[str] | None = None) -> int:
    """Normal entry. Arguments are ignored and are not printed."""
    _ = [] if argv is None else argv
    require_r51_hash()
    print("R52 entry point is disabled. No credential prompt. No network connection.")
    return 0


def _banned(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _BANNED_KEYS:
                raise Rejected(REJECTED)
            _banned(item)
    elif isinstance(value, list):
        for item in value:
            _banned(item)


def _project(raw: dict[str, Any], secrets: tuple[str, ...]) -> dict[str, Any]:
    rows_in = raw.get("schema_rows")
    if not isinstance(rows_in, list) or len(rows_in) != len(SIX):
        raise Rejected(REJECTED)
    rows = []
    for expected, item in zip(SIX, rows_in):
        if not isinstance(item, dict) or item.get("instrument") != expected:
            raise Rejected(REJECTED)
        if item.get("evidence_class") != "SYNTHETIC_TEST_ONLY":
            raise Rejected(REJECTED)
        if item.get("account_home_currency") != HOME_CURRENCY:
            raise Rejected(REJECTED)
        rows.append({key: item.get(key, "NOT_RETURNED") for key in _ROW_KEYS})
    if raw.get("calls_completed") != 2 or raw.get("endpoint_order") != ["instruments", "pricing"]:
        raise Rejected(REJECTED)
    document = {
        "evidence_class": "SYNTHETIC_TEST_ONLY",
        "calls_completed": 2,
        "endpoint_order": ["instruments", "pricing"],
        "account_home_currency": HOME_CURRENCY,
        "rows": rows,
        "remaining_blockers": [
            "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED",
            "SPREAD_BET_STAKE_MAP_UNKNOWN",
            "BROKER_TOKEN_PERMISSION_UNKNOWN",
            "NO_EXECUTABLE_SIZE",
            "QUANTITY_ONE_IS_NOT_PROVEN_AS_ONE_POUND_PER_PIP",
            "ONE_PIP_DISPLAY_IS_NOT_ZERO_RISK",
        ],
        "historical_ticket": {
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
        },
        "historical_financing_panel": {
            "class": "USER_REPORTED_HISTORICAL_DISPLAY",
            "api_confirmation": "NO",
            "buy_annualised": "-2.43%",
            "buy_estimate_gbp_per_100000_units": "16.75",
            "sell_annualised": "+0.42%",
            "sell_estimate_gbp_per_100000_units": "2.90",
            "displayed_time": "22:00 GMT+1",
        },
    }
    return _guard(document, secrets)


def _guard(document: dict[str, Any], secrets: tuple[str, ...]) -> dict[str, Any]:
    _banned(document)
    if document.get("evidence_class") != "SYNTHETIC_TEST_ONLY":
        raise Rejected(REJECTED)
    blob = json.dumps(document)
    for secret in secrets:
        if secret and secret in blob:
            raise Rejected(REJECTED)
    if "Bearer" in blob or "Authorization" in blob or "https://" in blob or "1.35" in blob or "ACCOUNT_VERIFIED" in blob:
        raise Rejected(REJECTED)
    return document


def run_synthetic(account_id: str, token: str, connection_factory: Callable[..., Any] | None) -> dict[str, Any]:
    """Run the two prepared reads through the R.51 adapter and an injected factory."""
    if _live_class(connection_factory):
        raise LiveTransportDisabled(LIVE_DISABLED)
    credential = accept_credentials(account_id, token)
    adapter = _r51()
    try:
        raw = adapter.run_offline(credential.account_id, credential.token, connection_factory)
    except adapter.LiveTransportDisabled:
        raise LiveTransportDisabled(LIVE_DISABLED) from None
    except Exception:
        raise Rejected(REJECTED) from None
    return _project(raw, (account_id, token))


def write_clean(path: Path, document: dict[str, Any], secrets: tuple[str, ...]) -> None:
    safe = _guard(document, secrets)
    path.write_text(json.dumps(safe, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
