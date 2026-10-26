"""One GET. The destination is fixed here, not in the entry-point text."""

from __future__ import annotations

import json
import re
import time
from typing import Any

HOST = "api-fxtrade.oanda.com"
PORT = 443
INSTRUMENTS = "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF"
PATH_TAIL = "/instruments"
MAX_BODY_BYTES = 1048576
ACCOUNT_ID_FORMAT = re.compile(r"^[0-9]{3}-[0-9]{3}-[0-9]{1,20}-[0-9]{3}$")
_REDIRECTS = frozenset({301, 302, 303, 307, 308})
_DENIED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
_DENIED_PATHS = ("/orders", "/trades", "/positions", "/pricing", "/summary", "/transactions", "/configuration", "/candles")
_URL_DELIMITERS = set("/\\?#@:;&%=\r\n\t ")


class TransportRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PreparedGet:
    def __init__(self, account_id: str) -> None:
        self.method = "GET"
        self.scheme = "https"
        self.host = HOST
        self.port = PORT
        self.kind = "instruments"
        self.path = "/v3/accounts/" + account_id + PATH_TAIL
        self.query = {"instruments": INSTRUMENTS}
        self.body = None
        self.redirects = False
        self.retries = 0
        self.bound_account = account_id
        self.session_id = ""


def validate_authenticated_account(account_id: object) -> str:
    if not isinstance(account_id, str) or not account_id or len(account_id) > 32:
        raise TransportRejected("ACCOUNT_ID_REJECTED")
    if any(ord(character) < 32 or ord(character) == 127 for character in account_id):
        raise TransportRejected("ACCOUNT_ID_REJECTED")
    if any(character in _URL_DELIMITERS for character in account_id):
        raise TransportRejected("ACCOUNT_ID_REJECTED")
    if "SYNTHETIC" in account_id or ACCOUNT_ID_FORMAT.fullmatch(account_id) is None:
        raise TransportRejected("ACCOUNT_ID_REJECTED")
    return account_id


def build_prepared(account_id: str) -> PreparedGet:
    return PreparedGet(validate_authenticated_account(account_id))


def validate_outbound(request: Any) -> None:
    if not isinstance(request, PreparedGet):
        raise TransportRejected("REQUEST_REJECTED")
    if request.method != "GET":
        raise TransportRejected("METHOD_REJECTED")
    if request.method in _DENIED_METHODS:
        raise TransportRejected("METHOD_REJECTED")
    if request.scheme != "https" or request.host != HOST or request.port != PORT:
        raise TransportRejected("HOST_REJECTED")
    path = str(request.path or "")
    lowered = path.lower()
    if "://" in path or path.startswith("//") or any(piece in lowered for piece in _DENIED_PATHS):
        raise TransportRejected("ENDPOINT_REJECTED")
    account = validate_authenticated_account(getattr(request, "bound_account", None))
    if path != "/v3/accounts/" + account + PATH_TAIL:
        raise TransportRejected("ENDPOINT_REJECTED")
    if request.query != {"instruments": INSTRUMENTS}:
        raise TransportRejected("QUERY_REJECTED")
    if request.body is not None:
        raise TransportRejected("BODY_REJECTED")
    if request.redirects is not False:
        raise TransportRejected("REDIRECT_REJECTED")
    if request.retries != 0:
        raise TransportRejected("RETRY_REJECTED")
    if request.kind != "instruments":
        raise TransportRejected("ENDPOINT_REJECTED")


def request_target(prepared: PreparedGet) -> str:
    validate_outbound(prepared)
    return prepared.path + "?instruments=" + INSTRUMENTS


def _token_text(authorization_header: object) -> str | None:
    if not isinstance(authorization_header, str) or not authorization_header.startswith("Bearer "):
        return None
    token = authorization_header[7:]
    if not token or any(character in token for character in " \t\r\n/\\?#@:;%"):
        return None
    return token


def header_accepted(authorization_header: object, *, synthetic: bool) -> bool:
    token = _token_text(authorization_header)
    if token is None or not 16 <= len(token) <= 128:
        return False
    if synthetic:
        return token.startswith("SYNTHETIC-") and "NOT-REAL" in token
    return True


class HarnessConnection:
    """Injected response. This object is not a socket."""

    marker = "R59_HARNESS_CONNECTION"

    def __init__(self, document: dict | None = None, *, status_code: int = 200, body: bytes | None = None) -> None:
        self.document = {} if document is None else document
        self.status_code = int(status_code)
        self.body = body
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def perform(self, prepared: PreparedGet) -> bytes:
        self.calls.append((prepared.method, prepared.path, dict(prepared.query)))
        if self.body is not None:
            return self.body
        return json.dumps(self.document).encode("utf-8")


class LiveExchange:
    """One HTTPS GET, or one injected harness response."""

    def __init__(self, connection: HarnessConnection | None = None) -> None:
        self.connection = connection
        self.calls = 0

    def exchange(self, prepared: PreparedGet, authorization_header: str, grant: object = None, *, deadline_at: float) -> tuple[int, bytes]:
        if self.calls:
            raise TransportRejected("REQUEST_LIMIT")
        self.calls += 1
        validate_outbound(prepared)
        if time.monotonic() > deadline_at:
            raise TransportRejected("DEADLINE_REJECTED")
        gate = _gate()
        if self.connection is not None:
            if self.connection.__class__ is not HarnessConnection or self.connection.marker != "R59_HARNESS_CONNECTION":
                raise TransportRejected("WORKER_REJECTED")
            if not header_accepted(authorization_header, synthetic=True):
                raise TransportRejected("AUTHORIZATION_REJECTED")
            try:
                gate.assert_harness_authorisation(grant, session_id=prepared.session_id, step="instruments")
            except gate.GateRejected as exc:
                raise TransportRejected(exc.code) from None
            status = int(self.connection.status_code)
            if status in _REDIRECTS:
                raise TransportRejected("REDIRECT_REJECTED")
            if status != 200:
                raise TransportRejected("HTTP_" + str(status))
            payload = self.connection.perform(prepared)
            if len(payload) > MAX_BODY_BYTES:
                raise TransportRejected("RESPONSE_TOO_LARGE")
            return status, payload
        if not header_accepted(authorization_header, synthetic=False):
            raise TransportRejected("AUTHORIZATION_REJECTED")
        try:
            gate.assert_parent_capability(grant, session_id=prepared.session_id, step="instruments")
        except gate.GateRejected as exc:
            raise TransportRejected(exc.code) from None
        import http.client
        import ssl

        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        if context.verify_mode != ssl.CERT_REQUIRED or context.check_hostname is not True:
            raise TransportRejected("TLS_VERIFICATION_REQUIRED")
        connection = http.client.HTTPSConnection(prepared.host, prepared.port, context=context, timeout=5)
        try:
            connection.request("GET", request_target(prepared), body=None, headers={"Accept": "application/json", "Authorization": authorization_header})
            response = connection.getresponse()
            status = int(response.status)
            if status in _REDIRECTS:
                raise TransportRejected("REDIRECT_REJECTED")
            payload = response.read(MAX_BODY_BYTES + 1)
        finally:
            connection.close()
        if status != 200:
            raise TransportRejected("HTTP_" + str(status))
        if len(payload) > MAX_BODY_BYTES:
            raise TransportRejected("RESPONSE_TOO_LARGE")
        return status, bytes(payload)


class RestrictedLiveTransport:
    def __init__(self, exchange: LiveExchange, grant: object, session_id: str) -> None:
        if not isinstance(exchange, LiveExchange):
            raise TransportRejected("WORKER_REJECTED")
        self.exchange = exchange
        self.grant = grant
        self.session_id = session_id
        self.sent = 0

    def get_instruments(self, account_id: str, *, authorization_header: str, deadline_at: float) -> bytes:
        if self.sent:
            raise TransportRejected("REQUEST_LIMIT")
        self.sent += 1
        prepared = build_prepared(account_id)
        prepared.session_id = self.session_id
        _status, payload = self.exchange.exchange(prepared, authorization_header, self.grant, deadline_at=deadline_at)
        return payload


def _gate() -> Any:
    import importlib.util
    import sys
    from pathlib import Path

    name = "r60_live_session_gate"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent / "live_session_gate.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
