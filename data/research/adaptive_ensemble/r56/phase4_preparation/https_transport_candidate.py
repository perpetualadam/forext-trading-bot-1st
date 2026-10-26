"""Offline HTTPS transport candidate. It never opens a socket.

Deadlines are enforced on this phase interface. A blocking call that ignores
its budget is detected afterwards and is not preempted.
"""

from __future__ import annotations

import time
from typing import Any, Callable

HOST = "api-fxtrade.oanda.com"
PORT = 443
REQUEST_DEADLINE_SEC = 5.0
SESSION_DEADLINE_SEC = 15.0
MAX_BODY_BYTES = 1048576
TARGET_ENVIRONMENT = "OANDA_LIVE"
LIVE_NETWORK_ACCESS = "NOT_AUTHORISED"
TIMEOUT_ENFORCEMENT = "PHASE_BUDGET_ENFORCED_ON_OFFLINE_INTERFACE"
LIVE_SOCKET_TIMEOUT = "NOT_EXERCISED"

_APPROVED_KEYS = frozenset(
    {
        "method",
        "scheme",
        "host",
        "port",
        "path_kind",
        "endpoint",
        "query",
        "body",
        "redirects",
        "retries",
        "stream",
    }
)


class TransportRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ManualClock:
    """Injected clock. advance() does not wait."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


class SessionClock:
    """Caps are 5.0s per request and 15.0s per session. A test may use less."""

    def __init__(
        self,
        *,
        monotonic: Callable[[], float] | None = None,
        request_budget: float = REQUEST_DEADLINE_SEC,
        session_budget: float = SESSION_DEADLINE_SEC,
    ) -> None:
        if request_budget > REQUEST_DEADLINE_SEC or session_budget > SESSION_DEADLINE_SEC:
            raise TransportRejected("BUDGET_ABOVE_CAP")
        if request_budget <= 0 or session_budget <= 0:
            raise TransportRejected("BUDGET_REJECTED")
        self.monotonic = monotonic or time.monotonic
        self.request_budget = float(request_budget)
        self.session_budget = float(session_budget)
        self.session_started = self.monotonic()
        self.request_started = self.session_started

    def advance(self, seconds: float) -> None:
        mover = getattr(self.monotonic, "advance", None)
        if mover is None:
            raise TransportRejected("CLOCK_NOT_ADVANCABLE")
        mover(seconds)

    def begin_request(self) -> None:
        self.request_started = self.monotonic()

    def request_remaining(self) -> float:
        return self.request_budget - (self.monotonic() - self.request_started)

    def session_remaining(self) -> float:
        return self.session_budget - (self.monotonic() - self.session_started)

    def phase_budget(self) -> float:
        return min(self.request_remaining(), self.session_remaining())

    def require_time(self) -> None:
        if self.session_remaining() <= 0:
            raise TransportRejected("SESSION_DEADLINE")
        if self.request_remaining() <= 0:
            raise TransportRejected("REQUEST_DEADLINE")


def tls_requirements() -> dict[str, Any]:
    return {"verify_mode": "CERT_REQUIRED", "check_hostname": True, "protocol": "TLS_CLIENT"}


def apply_tls_policy(context: Any) -> Any:
    """Record the required TLS flags on a caller-supplied object. No socket is wrapped."""
    context.verify_mode = "CERT_REQUIRED"
    context.check_hostname = True
    if context.verify_mode != "CERT_REQUIRED" or context.check_hostname is not True:
        raise TransportRejected("TLS_POLICY_REJECTED")
    return context


def seal_live_socket() -> None:
    """The live path is closed. This does not resolve a name or open a socket."""
    raise TransportRejected("LIVE_NETWORK_NOT_AUTHORISED")


class TransportSession:
    """At most one summary and then one pricing call. The double must be offline."""

    def __init__(self, double: Any, clock: SessionClock) -> None:
        self.double = double
        self.clock = clock
        self.kinds: list[str] = []
        self.closed = False

    def execute(self, approved: dict, *, authorization_present: bool) -> bytes:
        if self.closed:
            raise TransportRejected("TRANSPORT_CLOSED")
        _assert_offline(self.double)
        _assert_tls(getattr(self.double, "tls_policy", None))
        _assert_approved(approved)
        if authorization_present is not True:
            raise TransportRejected("AUTHORIZATION_ABSENT")
        if len(self.kinds) >= 2:
            raise TransportRejected("REQUEST_LIMIT")
        kind = approved["path_kind"]
        if kind == "summary" and "summary" in self.kinds:
            raise TransportRejected("SUMMARY_DUPLICATE_REJECTED")
        if kind == "pricing" and self.kinds != ["summary"]:
            raise TransportRejected("SEQUENCE_REJECTED")
        self.kinds.append(kind)
        self.clock.begin_request()
        self.clock.require_time()
        self.double.prepare(kind)
        for phase in ("connect", "tls", "write", "headers"):
            self.clock.require_time()
            self.double.run_phase(phase, self.clock.phase_budget(), self.clock)
            self.clock.require_time()
        status = int(self.double.status_code)
        if status != 200:
            raise TransportRejected(f"HTTP_{status}")
        body = bytearray()
        while True:
            self.clock.require_time()
            chunk = self.double.read_chunk(self.clock.phase_budget(), self.clock)
            self.clock.require_time()
            if chunk is None:
                break
            if not isinstance(chunk, (bytes, bytearray)) or not chunk:
                continue
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                raise TransportRejected("RESPONSE_TOO_LARGE")
            body.extend(chunk)
        return bytes(body)

    def close(self) -> None:
        self.closed = True
        closer = getattr(self.double, "close", None)
        if closer is not None:
            closer()


def _assert_offline(double: Any) -> None:
    if double.__class__.__name__ != "OfflineDouble" or getattr(double, "marker", "") != "R56P4_OFFLINE_DOUBLE":
        raise TransportRejected("LIVE_TRANSPORT_NOT_AVAILABLE")
    if getattr(double, "offline_only", False) is not True:
        raise TransportRejected("LIVE_TRANSPORT_NOT_AVAILABLE")


def _assert_tls(policy: Any) -> None:
    required = tls_requirements()
    if not isinstance(policy, dict):
        raise TransportRejected("TLS_POLICY_REJECTED")
    if policy.get("verify_mode") != required["verify_mode"] or policy.get("check_hostname") is not True:
        raise TransportRejected("TLS_POLICY_REJECTED")


def _assert_approved(approved: Any) -> None:
    if not isinstance(approved, dict) or set(approved) != _APPROVED_KEYS:
        raise TransportRejected("REQUEST_REJECTED")
    if approved.get("method") != "GET":
        raise TransportRejected("METHOD_REJECTED")
    if approved.get("scheme") != "https":
        raise TransportRejected("SCHEME_REJECTED")
    if approved.get("host") != HOST or approved.get("port") != PORT:
        raise TransportRejected("HOST_REJECTED")
    if approved.get("path_kind") not in {"summary", "pricing"}:
        raise TransportRejected("ENDPOINT_REJECTED")
    endpoint = str(approved.get("endpoint") or "")
    if approved["path_kind"] == "summary" and endpoint != "/v3/accounts/{accountID}/summary":
        raise TransportRejected("ENDPOINT_REJECTED")
    if approved["path_kind"] == "pricing" and endpoint != "/v3/accounts/{accountID}/pricing":
        raise TransportRejected("ENDPOINT_REJECTED")
    if "://" in endpoint or "api-fxtrade.oanda.com" in endpoint:
        raise TransportRejected("URL_REJECTED")
    if approved.get("body") is not None:
        raise TransportRejected("BODY_REJECTED")
    if approved.get("redirects") is not False:
        raise TransportRejected("REDIRECT_REJECTED")
    if approved.get("retries") != 0:
        raise TransportRejected("RETRY_REJECTED")
    if approved.get("stream") is not False:
        raise TransportRejected("STREAM_REJECTED")
    query = approved.get("query")
    if approved["path_kind"] == "summary" and query != {}:
        raise TransportRejected("QUERY_REJECTED")
    if approved["path_kind"] == "pricing":
        if not isinstance(query, dict) or query.get("instruments") != (
            "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF"
        ):
            raise TransportRejected("QUERY_REJECTED")
