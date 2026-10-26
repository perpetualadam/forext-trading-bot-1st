"""Pure descriptions of the two Option A GET requests.

This module does not open a socket, read credentials, or import a production module.
"""

from __future__ import annotations

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
REJECTED = "R55B2_REJECTED"

FUTURE_LIMITS = {
    "live_transport": "ABSENT",
    "credential_entry": "NOT_IMPLEMENTED",
    "confirmation_before_credentials": "REQUIRED_BEFORE_ANY_FUTURE_LIVE_SESSION",
    "hidden_token_entry": "NOT_IMPLEMENTED",
    "tls_certificate_verification": "REQUIRED",
    "tls_hostname_verification": "REQUIRED",
    "per_request_timeout_seconds": PER_REQUEST_TIMEOUT_SECONDS,
    "total_session_deadline_seconds": TOTAL_SESSION_DEADLINE_SECONDS,
    "timeout_enforcement": "NOT_IMPLEMENTED_OFFLINE",
    "max_body_bytes": MAX_BODY,
    "retries": 0,
    "redirects": False,
    "stream": False,
    "request_body": None,
    "order_methods": "PROHIBITED",
    "account_summary": "NOT_AUTHORISED",
}


class PlanRejected(RuntimeError):
    """Fail closed. The message is a fixed code."""

    def __init__(self) -> None:
        super().__init__(REJECTED)


def _account_ok(account_id: str) -> None:
    if not isinstance(account_id, str) or account_id == "":
        raise PlanRejected()
    if any(ch in account_id for ch in "/?#& \r\n\t"):
        raise PlanRejected()


def _query(kind: str) -> dict[str, str]:
    query = {"instruments": INSTRUMENT_QUERY}
    if kind == "pricing":
        query["includeHomeConversions"] = "true"
    return query


def describe(kind: str, account_id: str) -> dict[str, object]:
    """Return one allowlisted description. The account identifier is not copied into it."""
    _account_ok(account_id)
    if kind not in ALLOWED_KINDS:
        raise PlanRejected()
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
        raise PlanRejected()
    return planned


def reject_kind(kind: str) -> None:
    """Reject a banned or unknown endpoint name before any description is built."""
    if kind in BANNED_KINDS or kind not in ALLOWED_KINDS:
        raise PlanRejected()


def validate_description(description: dict[str, object], account_id: str) -> None:
    """Reject overrides. This does not contact a host."""
    _account_ok(account_id)
    if not isinstance(description, dict):
        raise PlanRejected()
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
        raise PlanRejected()
    if description["method"] != "GET":
        raise PlanRejected()
    if description["host"] != HOST or description["port"] != PORT:
        raise PlanRejected()
    if description["timeout_seconds"] != PER_REQUEST_TIMEOUT_SECONDS:
        raise PlanRejected()
    if description["retries"] != 0 or description["redirects"] is not False:
        raise PlanRejected()
    if description["body"] is not None or description["stream"] is not False:
        raise PlanRejected()
    path = description["path_pattern"]
    if not isinstance(path, str) or not path.startswith("/v3/accounts/{accountID}/"):
        raise PlanRejected()
    kind = path.rpartition("/")[2]
    if kind not in ALLOWED_KINDS or description["sequence"] != (1 if kind == "instruments" else 2):
        raise PlanRejected()
    query = description["query"]
    if not isinstance(query, dict):
        raise PlanRejected()
    expected = _query(kind)
    if set(query) != set(expected) or any(query.get(key) != value for key, value in expected.items()):
        raise PlanRejected()
    if account_id in path or account_id in str(query):
        raise PlanRejected()
