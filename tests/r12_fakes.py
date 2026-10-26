"""Deterministic stand-ins for one offline trading iteration.

These objects record calls in memory. They do not construct an OANDA client,
open a socket, or connect to PostgreSQL.
"""

from __future__ import annotations

from typing import Any


class FakeBroker:
    """Record one simulated request and return a scripted response."""

    def __init__(self, kind: str = "filled", *, response: dict[str, Any] | None = None, error: BaseException | None = None) -> None:
        self.kind = kind
        self.response = response
        self.error = error
        self.requests: list[dict[str, Any]] = []
        self.closed = False
        self.request_count = 0

    def submit(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("fake broker is closed")
        self.request_count += 1
        self.requests.append(dict(request))
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return dict(self.response)
        return {"kind": self.kind, "units": request.get("units"), "price": 1.1, "broker_order_id": "SIMULATED"}

    def close(self) -> None:
        self.closed = True


class FakeResource:
    """A clock, candle book, or persistence handle the test can close."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.closed = False

    def close(self) -> None:
        self.closed = True
