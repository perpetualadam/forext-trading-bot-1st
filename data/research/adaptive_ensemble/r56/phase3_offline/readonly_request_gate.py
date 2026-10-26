"""Reject a read candidate before any transport is constructed.

There is no approved-object bypass. Every candidate is checked again.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

_CANDIDATE_KEYS = frozenset(
    {"method", "scheme", "host", "port", "path", "query", "body", "redirects", "retries", "stream"}
)


class GateRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _plan() -> Any:
    name = "r56p3_readonly_request_plan"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / "readonly_request_plan.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def approve(candidate: Any, *, step: int, prior: list[str]) -> dict:
    """Return a transport description with the account id removed from the path."""
    plan = _plan()
    if step not in (1, 2):
        raise GateRejected("REQUEST_LIMIT")
    if not isinstance(candidate, dict) or set(candidate) != _CANDIDATE_KEYS:
        raise GateRejected("REQUEST_REJECTED")
    if candidate.get("approved") is True or "skip_validation" in candidate:
        raise GateRejected("REQUEST_REJECTED")
    if candidate.get("method") != "GET":
        raise GateRejected("METHOD_REJECTED")
    if candidate.get("scheme") != "https":
        raise GateRejected("SCHEME_REJECTED")
    if candidate.get("host") != plan.HOST:
        raise GateRejected("HOST_REJECTED")
    if candidate.get("port") != plan.PORT:
        raise GateRejected("PORT_REJECTED")
    if candidate.get("body") is not None:
        raise GateRejected("BODY_REJECTED")
    if candidate.get("redirects") is not False:
        raise GateRejected("REDIRECT_REJECTED")
    if candidate.get("retries") != 0:
        raise GateRejected("RETRY_REJECTED")
    if candidate.get("stream") is not False:
        raise GateRejected("STREAM_REJECTED")
    kind = _kind(str(candidate.get("path") or ""), plan.SYNTHETIC_ACCOUNT_ID)
    query = candidate.get("query")
    if not isinstance(query, dict):
        raise GateRejected("QUERY_REJECTED")
    if kind == "summary":
        if query:
            raise GateRejected("QUERY_REJECTED")
        if step != 1 or prior:
            raise GateRejected("SEQUENCE_REJECTED")
        pattern = plan.SUMMARY_PATTERN
        safe_query: dict = {}
    elif kind == "pricing":
        expected = {"instruments": ",".join(plan.INSTRUMENTS)}
        if query != expected:
            raise GateRejected("QUERY_REJECTED")
        if step != 2 or prior != ["summary"]:
            raise GateRejected("SEQUENCE_REJECTED")
        pattern = plan.PRICING_PATTERN
        safe_query = dict(expected)
    else:
        raise GateRejected(kind)
    return {
        "method": "GET",
        "scheme": "https",
        "host": plan.HOST,
        "port": plan.PORT,
        "path_kind": kind,
        "endpoint": pattern,
        "query": safe_query,
        "body": None,
        "redirects": False,
        "retries": 0,
        "stream": False,
    }


def _kind(path: str, account_id: str) -> str:
    if not path.startswith("/") or "://" in path or ".." in path or "\\" in path:
        return "ENDPOINT_REJECTED"
    lowered = path.lower()
    if "/orders" in lowered:
        return "ORDERS_REJECTED"
    if "/trades" in lowered:
        return "TRADES_REJECTED"
    if "/positions" in lowered or "openpositions" in lowered:
        return "POSITIONS_REJECTED"
    if "/candles" in lowered or lowered.startswith("/v3/instruments"):
        return "CANDLES_REJECTED"
    parts = path.split("/")
    if len(parts) != 5 or parts[1] != "v3" or parts[2] != "accounts":
        return "ENDPOINT_REJECTED"
    if parts[3] != account_id:
        return "ACCOUNT_ID_REJECTED"
    if parts[4] == "summary":
        return "summary"
    if parts[4] == "pricing":
        return "pricing"
    return "ENDPOINT_REJECTED"
