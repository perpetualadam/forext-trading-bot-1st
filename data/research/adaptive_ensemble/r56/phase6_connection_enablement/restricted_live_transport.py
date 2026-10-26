"""Two GET methods. The live opener cannot run while the source switch is off.

Offline mode substitutes the Phase 5 synthetic account id when the caller passes
SYNTHETIC_PIN. Authenticated mode accepts only an account id that matches the
OANDA form ``^[0-9]{3}-[0-9]{3}-[0-9]{1,20}-[0-9]{3}$`` (site, division, user,
account). Control characters, whitespace, slashes, and URL delimiters are
rejected. The synthetic pin is rejected in authenticated mode. The path is built
inside this module. A malformed id raises before any connection object is used.

The real HTTPS branch also requires the source switch and a second runtime
grant. Neither is available. Tests inject HarnessConnection, which is not a socket.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PHASE5 = HERE.parent / "phase5_connection"
SELECTOR = "SYNTHETIC_PIN"
MAX_BODY_BYTES = 1048576
ACCOUNT_ID_FORMAT = re.compile(r"^[0-9]{3}-[0-9]{3}-[0-9]{1,20}-[0-9]{3}$")
_REDIRECTS = frozenset({301, 302, 303, 307, 308})
_CHANGING = ("/orders", "/trades", "/positions", "/transactions", "/candles", "/financing", "/configuration")
_URL_DELIMITERS = set("/\\?#@:;&%=\r\n\t ")


class TransportRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PreparedGet:
    def __init__(
        self,
        *,
        kind: str,
        path: str,
        query: dict[str, str],
        bound_account: str | None = None,
        mode: str = "OFFLINE",
    ) -> None:
        pins = _pins()
        self.method = "GET"
        self.scheme = "https"
        self.host = pins.HOST
        self.port = pins.PORT
        self.kind = kind
        self.path = path
        self.query = dict(query)
        self.body = None
        self.redirects = False
        self.retries = 0
        self.stream = False
        self.cookies = None
        self.bound_account = bound_account
        self.mode = mode


def _load(directory: Path, prefix: str, stem: str) -> Any:
    name = f"{prefix}_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, directory / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _pins() -> Any:
    return _load(PHASE5, "r56p5", "restricted_https_transport")


def _gate() -> Any:
    return _load(HERE, "r56p6", "live_session_gate")


def validate_authenticated_account(account_id: object) -> str:
    """Return the id, or reject it before a connection is created."""
    if not isinstance(account_id, str) or not account_id or len(account_id) > 32:
        raise TransportRejected("ACCOUNT_ID_REJECTED")
    if any(ord(character) < 32 or ord(character) == 127 for character in account_id):
        raise TransportRejected("ACCOUNT_ID_REJECTED")
    if any(character in _URL_DELIMITERS for character in account_id):
        raise TransportRejected("ACCOUNT_ID_REJECTED")
    if account_id == SELECTOR or account_id == _pins().SYNTHETIC_ACCOUNT_ID:
        raise TransportRejected("SYNTHETIC_ACCOUNT_REJECTED")
    if ACCOUNT_ID_FORMAT.fullmatch(account_id) is None:
        raise TransportRejected("ACCOUNT_ID_REJECTED")
    return account_id


def resolve_account(selector: object, mode: str) -> str:
    if mode == "OFFLINE":
        if selector != SELECTOR:
            raise TransportRejected("REAL_ACCOUNT_ID_REJECTED")
        pinned = _pins().SYNTHETIC_ACCOUNT_ID
        if not isinstance(pinned, str) or any(character in pinned for character in "/\\") or ".." in pinned:
            raise TransportRejected("ACCOUNT_ID_REJECTED")
        return pinned
    if mode == "AUTHENTICATED":
        return validate_authenticated_account(selector)
    raise TransportRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")


def build_prepared(kind: str, selector: object, mode: str) -> PreparedGet:
    account = resolve_account(selector, mode)
    tail = "summary" if kind == "summary" else "pricing"
    path = "/v3/accounts/" + account + "/" + tail
    query = {} if kind == "summary" else {"instruments": _pins().INSTRUMENTS}
    return PreparedGet(kind=kind, path=path, query=query, bound_account=account, mode=mode)


def _expected_path(request: PreparedGet) -> str:
    if getattr(request, "mode", "OFFLINE") == "AUTHENTICATED":
        account = validate_authenticated_account(getattr(request, "bound_account", None))
    else:
        account = _pins().SYNTHETIC_ACCOUNT_ID
        if not isinstance(account, str):
            raise TransportRejected("ACCOUNT_ID_REJECTED")
    tail = "summary" if request.kind == "summary" else "pricing"
    return "/v3/accounts/" + account + "/" + tail


def build_tls_context() -> Any:
    import ssl

    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    if context.verify_mode != ssl.CERT_REQUIRED or context.check_hostname is not True:
        raise TransportRejected("TLS_VERIFICATION_REQUIRED")
    return context


def disable_tls_verification(*_args: Any, **_kwargs: Any) -> None:
    raise TransportRejected("TLS_VERIFICATION_CANNOT_BE_DISABLED")


def live_request_headers(authorization_header: str) -> dict[str, str]:
    if not isinstance(authorization_header, str) or not authorization_header.startswith("Bearer "):
        raise TransportRejected("AUTHORIZATION_REJECTED")
    return {"Accept": "application/json", "Authorization": authorization_header}


def validate_outbound(request: Any) -> None:
    pins = _pins()
    if not isinstance(request, PreparedGet):
        raise TransportRejected("REQUEST_REJECTED")
    if request.method != "GET":
        raise TransportRejected("METHOD_REJECTED")
    if request.scheme != "https":
        raise TransportRejected("SCHEME_REJECTED")
    if request.host != pins.HOST or request.port != pins.PORT:
        raise TransportRejected("HOST_REJECTED")
    path = str(request.path or "")
    lowered = path.lower()
    if "://" in path or path.startswith("//"):
        raise TransportRejected("URL_REJECTED")
    if any(piece in lowered for piece in _CHANGING) or "/instruments" in lowered or "stream" in lowered:
        raise TransportRejected("ACCOUNT_CHANGING_REJECTED")
    if request.kind == "summary":
        if path != _expected_path(request) or request.query != {}:
            raise TransportRejected("QUERY_REJECTED" if request.query else "ENDPOINT_REJECTED")
    elif request.kind == "pricing":
        if path != _expected_path(request):
            raise TransportRejected("ENDPOINT_REJECTED")
        if request.query != {"instruments": pins.INSTRUMENTS}:
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
    if request.cookies not in (None, {}):
        raise TransportRejected("COOKIES_REJECTED")


def request_target(prepared: PreparedGet) -> str:
    """The only URL the real branch would open. It is built from the prepared path."""
    validate_outbound(prepared)
    if prepared.kind == "pricing":
        return prepared.path + "?instruments=" + prepared.query["instruments"]
    return prepared.path


def _token_text(authorization_header: object) -> str | None:
    if not isinstance(authorization_header, str) or not authorization_header.startswith("Bearer "):
        return None
    token = authorization_header[7:]
    if not token or any(character in token for character in " \t\r\n") or any(ord(character) < 32 or ord(character) == 127 for character in token):
        return None
    return token


def header_accepted_harness(authorization_header: object) -> bool:
    """Harness sessions accept only the synthetic credential marker."""
    token = _token_text(authorization_header)
    return token is not None and token.startswith("SYNTHETIC-") and "NOT-REAL" in token and " " not in token


def header_accepted_real(authorization_header: object) -> bool:
    """Real-mode syntax check. A well-formed token is not a grant and does not open a socket."""
    token = _token_text(authorization_header)
    if token is None or not 16 <= len(token) <= 128:
        return False
    if any(character in token for character in "/\\?#@:;%"):
        return False
    return True


def _header_accepted(authorization_header: object) -> bool:
    return header_accepted_harness(authorization_header)


class FakeExchange:
    """Stands in for the TLS socket. It has the same exchange signature as the live opener."""

    offline_only = True
    marker = "R56P6_FAKE_HTTPS"

    def __init__(
        self,
        document: dict | None = None,
        *,
        status_code: int = 200,
        body: bytes | None = None,
        fill: int = 0,
        tls_policy: dict | None = None,
        proxy_from_environment: bool = False,
    ) -> None:
        self.document = {} if document is None else document
        self.status_code = int(status_code)
        self.body = body
        self.fill = int(fill)
        self.tls_policy = tls_policy or {"verify_mode": "CERT_REQUIRED", "check_hostname": True}
        self.proxy_from_environment = proxy_from_environment
        self.authorization_accepted = False
        self.calls: list[tuple[str, str]] = []

    def exchange(self, prepared: PreparedGet, authorization_header: str, grant: object = None) -> bytes:
        self.authorization_accepted = _header_accepted(authorization_header)
        if not self.authorization_accepted:
            raise TransportRejected("AUTHORIZATION_REJECTED")
        del grant
        self.calls.append((prepared.method, prepared.path))
        if self.fill:
            return b"x" * self.fill
        if self.body is not None:
            return self.body
        return json.dumps(self.document).encode("utf-8")


class HarnessConnection:
    """Scripted response injected at the transport boundary. This is not a socket."""

    marker = "R56P6_HARNESS_CONNECTION"

    def __init__(
        self,
        document: dict | None = None,
        *,
        status_code: int = 200,
        body: bytes | None = None,
        fill: int = 0,
    ) -> None:
        self.document = {} if document is None else document
        self.status_code = int(status_code)
        self.body = body
        self.fill = int(fill)
        self.opened = False
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def perform(self, prepared: PreparedGet) -> bytes:
        self.opened = True
        self.calls.append((prepared.method, prepared.path, dict(prepared.query)))
        if self.fill:
            return b"x" * self.fill
        if self.body is not None:
            return self.body
        return json.dumps(self.document).encode("utf-8")


class LiveExchange:
    """HTTPS GET through the standard library, or a harness connection injected by a test.

    A missing connection is the real branch. That branch raises before
    HTTPSConnection while the source switch is off and no runtime grant exists.
    """

    offline_only = False
    real_connections_opened = 0

    def __init__(self, connection: HarnessConnection | None = None) -> None:
        self.connection = connection
        self.authorization_accepted = False
        self.tls_policy = {"verify_mode": "CERT_REQUIRED", "check_hostname": True}
        self.proxy_from_environment = False

    @property
    def status_code(self) -> int:
        if self.connection is None:
            return 200
        return int(self.connection.status_code)

    def exchange(self, prepared: PreparedGet, authorization_header: str, grant: object = None) -> bytes:
        validate_outbound(prepared)
        gate = _gate()
        if self.connection is not None:
            self.authorization_accepted = header_accepted_harness(authorization_header)
            if not self.authorization_accepted:
                raise TransportRejected("AUTHORIZATION_REJECTED")
            if self.connection.__class__ is not HarnessConnection or self.connection.marker != "R56P6_HARNESS_CONNECTION":
                raise TransportRejected("LIVE_EXCHANGE_NOT_AUTHORISED")
            try:
                gate.assert_harness_authorisation(
                    grant,
                    session_id=getattr(prepared, "session_id", None),
                    step=prepared.kind,
                )
            except gate.GateRejected as exc:
                raise TransportRejected(exc.code) from None
            return self.connection.perform(prepared)
        self.authorization_accepted = header_accepted_real(authorization_header)
        if not self.authorization_accepted:
            raise TransportRejected("AUTHORIZATION_REJECTED")
        gate.assert_real_session()
        try:
            gate.assert_parent_capability(grant, session_id=getattr(prepared, "session_id", None), step=prepared.kind)
        except gate.GateRejected as exc:
            raise TransportRejected(exc.code) from None
        LiveExchange.real_connections_opened += 1
        context = build_tls_context()
        import http.client

        connection = http.client.HTTPSConnection(prepared.host, prepared.port, context=context, timeout=5)
        connection.request("GET", request_target(prepared), body=None, headers=live_request_headers(authorization_header))
        response = connection.getresponse()
        status = int(response.status)
        if status in _REDIRECTS:
            connection.close()
            raise TransportRejected("REDIRECT_REJECTED")
        payload = response.read(MAX_BODY_BYTES + 1)
        connection.close()
        if status != 200:
            raise TransportRejected(f"HTTP_{status}")
        if len(payload) > MAX_BODY_BYTES:
            raise TransportRejected("RESPONSE_TOO_LARGE")
        return payload


class RestrictedLiveTransport:
    def __init__(self, exchange: Any, grant: object = None, session_id: str = "") -> None:
        if isinstance(exchange, LiveExchange):
            if exchange.connection is None:
                _gate().assert_real_session()
            elif exchange.connection.__class__ is not HarnessConnection or exchange.connection.marker != "R56P6_HARNESS_CONNECTION":
                raise TransportRejected("LIVE_EXCHANGE_NOT_AUTHORISED")
        elif exchange.__class__ is not FakeExchange or exchange.offline_only is not True or exchange.marker != "R56P6_FAKE_HTTPS":
            raise TransportRejected("LIVE_EXCHANGE_NOT_AUTHORISED")
        self.exchange = exchange
        self.grant = grant
        self.session_id = session_id
        self.kinds: list[str] = []

    def get_account_summary(self, account_selector: str, *, authorization_header: str, mode: str = "OFFLINE") -> bytes:
        if self.kinds:
            raise TransportRejected("SUMMARY_DUPLICATE_REJECTED" if "summary" in self.kinds else "REQUEST_LIMIT")
        prepared = build_prepared("summary", account_selector, mode)
        prepared.session_id = self.session_id
        self.kinds.append("summary")
        return self._finish(prepared, authorization_header)

    def get_pricing(
        self,
        account_selector: str,
        *,
        authorization_header: str,
        prior: tuple[str, ...],
        mode: str = "OFFLINE",
    ) -> bytes:
        if prior != ("summary",) or self.kinds:
            raise TransportRejected("SEQUENCE_REJECTED" if prior != ("summary",) else "REQUEST_LIMIT")
        prepared = build_prepared("pricing", account_selector, mode)
        prepared.session_id = self.session_id
        self.kinds.append("pricing")
        return self._finish(prepared, authorization_header)

    def _finish(self, prepared: PreparedGet, authorization_header: str) -> bytes:
        validate_outbound(prepared)
        policy = getattr(self.exchange, "tls_policy", {"verify_mode": "CERT_REQUIRED", "check_hostname": True})
        if not isinstance(policy, dict) or policy.get("verify_mode") != "CERT_REQUIRED" or policy.get("check_hostname") is not True:
            raise TransportRejected("TLS_VERIFICATION_REQUIRED")
        if policy.get("allow_insecure") is True:
            raise TransportRejected("TLS_VERIFICATION_CANNOT_BE_DISABLED")
        if getattr(self.exchange, "proxy_from_environment", False) is not False:
            raise TransportRejected("PROXY_REJECTED")
        raw = self.exchange.exchange(prepared, authorization_header, self.grant)
        status = int(getattr(self.exchange, "status_code", 200))
        if status in _REDIRECTS:
            raise TransportRejected("REDIRECT_REJECTED")
        if status != 200:
            raise TransportRejected(f"HTTP_{status}")
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_BODY_BYTES:
            raise TransportRejected("RESPONSE_TOO_LARGE")
        return bytes(raw)
