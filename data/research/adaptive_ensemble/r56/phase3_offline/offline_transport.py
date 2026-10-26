"""Synthetic transport only. This module has no network client and no live factory."""

from __future__ import annotations

from typing import Any


class OfflineTransportRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SyntheticTransport:
    """Return supplied dictionaries for approved summary and pricing descriptions."""

    classification = "SYNTHETIC_TRANSPORT"

    def __init__(
        self,
        summary: dict,
        pricing: dict,
        *,
        raise_on: str | None = None,
        raise_error: BaseException | None = None,
    ) -> None:
        self.summary = summary
        self.pricing = pricing
        self.raise_on = raise_on
        self.raise_error = raise_error
        self.calls: list[str] = []

    def execute(self, approved: dict) -> Any:
        kind = approved.get("path_kind") if isinstance(approved, dict) else None
        if kind not in {"summary", "pricing"}:
            raise OfflineTransportRejected("TRANSPORT_UNAPPROVED")
        if approved.get("host") != "api-fxtrade.oanda.com" or approved.get("port") != 443:
            raise OfflineTransportRejected("TRANSPORT_UNAPPROVED")
        if approved.get("method") != "GET" or approved.get("body") is not None:
            raise OfflineTransportRejected("TRANSPORT_UNAPPROVED")
        if "accountID" not in str(approved.get("endpoint") or ""):
            raise OfflineTransportRejected("TRANSPORT_UNAPPROVED")
        if "/" in str(approved.get("endpoint") or "").split("{accountID}")[-1] and kind == "summary":
            tail = str(approved.get("endpoint")).endswith("/summary")
            if not tail:
                raise OfflineTransportRejected("TRANSPORT_UNAPPROVED")
        self.calls.append(kind)
        if self.raise_on == kind:
            if self.raise_error is not None:
                raise self.raise_error
            raise OfflineTransportRejected("SYNTHETIC_TRANSPORT_FAILED")
        if kind == "summary":
            return self.summary
        return self.pricing


def live_transport() -> None:
    """No live transport exists. This function does not build a client."""
    raise OfflineTransportRejected("LIVE_TRANSPORT_NOT_AVAILABLE")
