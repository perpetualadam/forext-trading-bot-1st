"""Fixed Option A request descriptions and the session deadline clock.

This module does not open a socket, read a credential, or import a production module.
The clock is a wall-clock budget for later phases. It is not a socket inactivity timer.
"""

from __future__ import annotations

import time
from typing import Callable

HOST = "api-fxtrade.oanda.com"
PORT = 443
PER_REQUEST_TIMEOUT_SECONDS = 5.0
TOTAL_SESSION_DEADLINE_SECONDS = 15.0
MAX_BODY = 1_048_576
SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
INSTRUMENT_QUERY = ",".join(SIX)
ALLOWED_KINDS = ("instruments", "pricing")
BANNED_KINDS = frozenset(
    {
        "summary",
        "orders",
        "trades",
        "positions",
        "transactions",
        "candles",
        "openPositions",
        "pendingOrders",
    }
)
REJECTED = "R55G2_REJECTED"
TIMEOUT = "TIMEOUT"
SESSION_DEADLINE = "SESSION_DEADLINE"
LIVE_DISABLED = "R55G2_LIVE_DISABLED"
LIVE_TRANSPORT_NOT_ACTIVATED = "R55G2_LIVE_TRANSPORT_NOT_ACTIVATED"
REAL_CREDENTIAL_INPUT_NOT_AUTHORISED = "R55G2_REAL_CREDENTIAL_INPUT_NOT_AUTHORISED"


class GateRejected(RuntimeError):
    """Fail closed. The message is only the fixed classification."""

    def __init__(self, classification: str = REJECTED, detail: dict[str, str] | None = None) -> None:
        self.classification = classification
        self.detail = detail or {}
        super().__init__(classification)


class SessionClock:
    """Monotonic budget. Values above the approved caps are rejected."""

    def __init__(
        self,
        per_request: float = PER_REQUEST_TIMEOUT_SECONDS,
        session: float = TOTAL_SESSION_DEADLINE_SECONDS,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        if per_request <= 0 or session <= 0:
            raise GateRejected(REJECTED)
        if per_request > PER_REQUEST_TIMEOUT_SECONDS or session > TOTAL_SESSION_DEADLINE_SECONDS:
            raise GateRejected(REJECTED)
        self.per_request = float(per_request)
        self.session = float(session)
        self._time = time.monotonic if time_fn is None else time_fn
        self.session_started: float | None = None
        self.request_started: float | None = None

    def now(self) -> float:
        return float(self._time())

    def start_session(self) -> None:
        if self.session_started is not None:
            raise GateRejected(REJECTED)
        self.session_started = self.now()

    def start_request(self) -> None:
        self.ensure_session()
        self.request_started = self.now()

    def session_remaining(self) -> float:
        if self.session_started is None:
            raise GateRejected(REJECTED)
        return self.session - (self.now() - self.session_started)

    def ensure_session(self) -> None:
        if self.session_remaining() <= 0:
            raise GateRejected(SESSION_DEADLINE)

    def phase_budget(self) -> tuple[float, str]:
        """Return the binding positive budget and the code to raise when it is spent."""
        if self.request_started is None:
            raise GateRejected(REJECTED)
        left_session = self.session_remaining()
        left_request = self.per_request - (self.now() - self.request_started)
        if left_session <= 0:
            raise GateRejected(SESSION_DEADLINE)
        if left_request <= 0:
            raise GateRejected(TIMEOUT)
        if left_session <= left_request:
            return left_session, SESSION_DEADLINE
        return left_request, TIMEOUT


def _account_ok(account_id: str) -> None:
    if not isinstance(account_id, str) or account_id == "":
        raise GateRejected(REJECTED)
    if any(ch in account_id for ch in "/?#& \r\n\t"):
        raise GateRejected(REJECTED)


def _query(kind: str) -> dict[str, str]:
    query = {"instruments": INSTRUMENT_QUERY}
    if kind == "pricing":
        query["includeHomeConversions"] = "true"
    return query


def describe(kind: str, account_id: str) -> dict[str, object]:
    """Return one allowlisted description. The account identifier is not copied into it."""
    _account_ok(account_id)
    if kind not in ALLOWED_KINDS:
        raise GateRejected(REJECTED)
    return {
        "sequence": 1 if kind == "instruments" else 2,
        "method": "GET",
        "host": HOST,
        "port": PORT,
        "path_pattern": f"/v3/accounts/{{accountID}}/{kind}",
        "query": _query(kind),
        "timeout_seconds": PER_REQUEST_TIMEOUT_SECONDS,
        "retries": 0,
        "redirects": False,
        "body": None,
        "stream": False,
    }


def plan_two(account_id: str) -> list[dict[str, object]]:
    """Plan instruments, then pricing. There is no third description."""
    planned = [describe("instruments", account_id), describe("pricing", account_id)]
    if len(planned) != 2:
        raise GateRejected(REJECTED)
    return planned


def reject_kind(kind: str) -> None:
    """Reject a banned or unknown endpoint name before any connection exists."""
    if kind in BANNED_KINDS or kind not in ALLOWED_KINDS:
        raise GateRejected(REJECTED)


def reject_raw_target(value: object) -> None:
    """Reject a URL or an object that is not an allowlisted description."""
    if isinstance(value, str) or not isinstance(value, dict):
        raise GateRejected(REJECTED)
    if "url" in value or "://" in str(value.get("path_pattern", "")):
        raise GateRejected(REJECTED)


def validate_description(description: dict[str, object], account_id: str) -> None:
    """Reject overrides. This does not contact a host."""
    reject_raw_target(description)
    _account_ok(account_id)
    allowed = {
        "sequence",
        "method",
        "host",
        "port",
        "path_pattern",
        "query",
        "timeout_seconds",
        "retries",
        "redirects",
        "body",
        "stream",
    }
    if set(description) != allowed:
        raise GateRejected(REJECTED)
    if description["method"] != "GET":
        raise GateRejected(REJECTED)
    if description["host"] != HOST or description["port"] != PORT:
        raise GateRejected(REJECTED)
    if description["timeout_seconds"] != PER_REQUEST_TIMEOUT_SECONDS:
        raise GateRejected(REJECTED)
    if description["retries"] != 0 or description["redirects"] is not False:
        raise GateRejected(REJECTED)
    if description["body"] is not None or description["stream"] is not False:
        raise GateRejected(REJECTED)
    path = description["path_pattern"]
    if not isinstance(path, str) or not path.startswith("/v3/accounts/{accountID}/"):
        raise GateRejected(REJECTED)
    kind = path.rpartition("/")[2]
    if kind not in ALLOWED_KINDS or description["sequence"] != (1 if kind == "instruments" else 2):
        raise GateRejected(REJECTED)
    query = description["query"]
    if not isinstance(query, dict):
        raise GateRejected(REJECTED)
    expected = _query(kind)
    if set(query) != set(expected) or any(query.get(key) != value for key, value in expected.items()):
        raise GateRejected(REJECTED)
    if account_id in path or account_id in str(query):
        raise GateRejected(REJECTED)
