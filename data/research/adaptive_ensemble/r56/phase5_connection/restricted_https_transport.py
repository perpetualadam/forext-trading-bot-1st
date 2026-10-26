"""Two GET operations for a future read-only diagnostic. No live connection is opened.

A caller cannot supply a method, a URL, or an endpoint. Account-changing paths
cannot be represented by the public methods.
"""

from __future__ import annotations

import ssl
from typing import Any

HOST = "api-fxtrade.oanda.com"
PORT = 443
SCHEME = "https"
SYNTHETIC_ACCOUNT_ID = "001-001-0000000-001"
INSTRUMENTS = "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF"
SUMMARY_PATTERN = "/v3/accounts/{accountID}/summary"
PRICING_PATTERN = "/v3/accounts/{accountID}/pricing"
MAX_BODY_BYTES = 1048576
REQUEST_DEADLINE_SEC = 5.0
SESSION_DEADLINE_SEC = 15.0
TARGET_ENVIRONMENT = "OANDA_LIVE"
LIVE_NETWORK_ACCESS = "NOT_AUTHORISED"

_CHANGING = ("/orders", "/trades", "/positions", "/transactions", "/candles", "/financing", "/configuration")


class TransportRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PreparedGet:
    """Outbound description produced only inside this module."""

    def __init__(self, *, kind: str, path: str, query: dict[str, str]) -> None:
        self.method = "GET"
        self.scheme = SCHEME
        self.host = HOST
        self.port = PORT
        self.kind = kind
        self.path = path
        self.query = dict(query)
        self.body = None
        self.redirects = False
        self.retries = 0
        self.stream = False


def require_synthetic_account(account_id: str) -> str:
    """Accept the pinned synthetic id. Any other value fails closed."""
    if not isinstance(account_id, str) or account_id != SYNTHETIC_ACCOUNT_ID:
        raise TransportRejected("REAL_ACCOUNT_ID_REJECTED")
    if "/" in account_id or "\\" in account_id or ".." in account_id:
        raise TransportRejected("ACCOUNT_ID_REJECTED")
    return SYNTHETIC_ACCOUNT_ID


def _path_for(kind: str, account_id: str) -> str:
    pinned = require_synthetic_account(account_id)
    tail = "summary" if kind == "summary" else "pricing"
    return "/v3/accounts/" + pinned + "/" + tail


def build_tls_context() -> ssl.SSLContext:
    """Standard CA verification. There is no switch that disables it."""
    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    if context.verify_mode != ssl.CERT_REQUIRED or context.check_hostname is not True:
        raise TransportRejected("TLS_VERIFICATION_REQUIRED")
    return context


def disable_tls_verification(*_args: Any, **_kwargs: Any) -> None:
    raise TransportRejected("TLS_VERIFICATION_CANNOT_BE_DISABLED")


def perform_live_exchange(*_args: Any, **_kwargs: Any) -> None:
    """Sealed before any socket. http.client is not asked to connect."""
    raise TransportRejected("LIVE_NETWORK_NOT_AUTHORISED")


def open_live_connection() -> None:
    """The stdlib connection below is unreachable while this phase is sealed."""
    perform_live_exchange()
    context = build_tls_context()
    import http.client

    http.client.HTTPSConnection(HOST, PORT, context=context, timeout=REQUEST_DEADLINE_SEC)


def validate_outbound(request: Any) -> None:
    """Independent of the Phase 3 gate. A bad caller still cannot widen the request."""
    if not isinstance(request, PreparedGet):
        raise TransportRejected("REQUEST_REJECTED")
    if request.method != "GET":
        raise TransportRejected("METHOD_REJECTED")
    if request.scheme != SCHEME:
        raise TransportRejected("SCHEME_REJECTED")
    if request.host != HOST or request.port != PORT:
        raise TransportRejected("HOST_REJECTED")
    path = str(request.path or "")
    lowered = path.lower()
    if "://" in path or path.startswith("//"):
        raise TransportRejected("URL_REJECTED")
    if any(piece in lowered for piece in _CHANGING) or "/instruments" in lowered:
        raise TransportRejected("ACCOUNT_CHANGING_REJECTED")
    if request.kind == "summary":
        if path != _path_for("summary", SYNTHETIC_ACCOUNT_ID) or request.query != {}:
            raise TransportRejected("ENDPOINT_REJECTED" if request.query == {} else "QUERY_REJECTED")
    elif request.kind == "pricing":
        if path != _path_for("pricing", SYNTHETIC_ACCOUNT_ID):
            raise TransportRejected("ENDPOINT_REJECTED")
        if request.query != {"instruments": INSTRUMENTS}:
            raise TransportRejected("QUERY_REJECTED")
        if "includeHomeConversions" in request.query:
            raise TransportRejected("QUERY_REJECTED")
    else:
        raise TransportRejected("ENDPOINT_REJECTED")
    if request.body is not None:
        raise TransportRejected("BODY_REJECTED")
    if request.redirects is not False:
        raise TransportRejected("REDIRECT_REJECTED")
    if request.retries != 0:
        raise TransportRejected("RETRY_REJECTED")
    if request.stream is not False:
        raise TransportRejected("STREAM_REJECTED")


class RestrictedTransport:
    """Public surface: get_account_summary and get_pricing. One call each, in that order."""

    def __init__(self, connector: Any, *, request_deadline: float = REQUEST_DEADLINE_SEC) -> None:
        if request_deadline <= 0 or request_deadline > REQUEST_DEADLINE_SEC:
            raise TransportRejected("DEADLINE_ABOVE_CAP")
        if connector.__class__.__name__ != "ScriptedConnector" or getattr(connector, "offline_only", False) is not True:
            raise TransportRejected("LIVE_CONNECTOR_NOT_AUTHORISED")
        if getattr(connector, "marker", "") != "R56P5_SCRIPTED":
            raise TransportRejected("LIVE_CONNECTOR_NOT_AUTHORISED")
        self.connector = connector
        self.request_deadline = float(request_deadline)
        self.kinds: list[str] = []

    def get_account_summary(self, account_id: str, *, authorization_present: bool) -> bytes:
        if self.kinds:
            raise TransportRejected("SUMMARY_DUPLICATE_REJECTED" if "summary" in self.kinds else "SEQUENCE_REJECTED")
        self.kinds.append("summary")
        prepared = PreparedGet(kind="summary", path=_path_for("summary", account_id), query={})
        return self._exchange(prepared, authorization_present=authorization_present)

    def get_pricing(self, account_id: str, *, authorization_present: bool, prior: tuple[str, ...]) -> bytes:
        if prior != ("summary",):
            raise TransportRejected("SEQUENCE_REJECTED")
        if self.kinds:
            raise TransportRejected("REQUEST_LIMIT")
        self.kinds.append("pricing")
        prepared = PreparedGet(kind="pricing", path=_path_for("pricing", account_id), query={"instruments": INSTRUMENTS})
        return self._exchange(prepared, authorization_present=authorization_present)

    def _exchange(self, prepared: PreparedGet, *, authorization_present: bool) -> bytes:
        validate_outbound(prepared)
        if authorization_present is not True:
            raise TransportRejected("AUTHORIZATION_ABSENT")
        if getattr(self.connector, "proxy_from_environment", False) is not False:
            raise TransportRejected("PROXY_REJECTED")
        policy = getattr(self.connector, "tls_policy", None)
        if not isinstance(policy, dict) or policy.get("verify_mode") != "CERT_REQUIRED" or policy.get("check_hostname") is not True:
            raise TransportRejected("TLS_VERIFICATION_REQUIRED")
        if policy.get("allow_insecure") is True:
            raise TransportRejected("TLS_VERIFICATION_CANNOT_BE_DISABLED")
        raw = self.connector.exchange(prepared)
        status = int(getattr(self.connector, "status_code", 0))
        if status != 200:
            raise TransportRejected(f"HTTP_{status}")
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_BODY_BYTES:
            raise TransportRejected("RESPONSE_TOO_LARGE")
        return bytes(raw)
