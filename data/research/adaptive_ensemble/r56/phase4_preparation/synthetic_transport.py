"""Offline double for the Phase 4 transport candidate. It has no socket."""

from __future__ import annotations

import json
import time
from typing import Any

MARKER = "R56P4_OFFLINE_DOUBLE"
INSTRUMENTS = (
    ("EUR_USD", "1.10000", "1.10020"),
    ("GBP_USD", "1.20000", "1.20030"),
    ("USD_JPY", "150.000", "150.030"),
    ("AUD_USD", "0.65000", "0.65010"),
    ("USD_CAD", "1.30000", "1.30040"),
    ("USD_CHF", "0.90000", "0.90020"),
)


def summary_document(
    *,
    currency: str | None = "GBP",
    include_currency: bool = True,
    extra: dict | None = None,
) -> dict:
    account: dict[str, Any] = {
        "id": "001-001-0000000-001",
        "NAV": "100.00",
        "balance": "100.00",
        "unrealizedPL": "0.00",
        "marginAvailable": "100.00",
        "alias": "synthetic-alias-not-logged",
        "lastTransactionID": "5",
    }
    if include_currency and currency is not None:
        account["currency"] = currency
    if extra:
        account.update(extra)
    return {"account": account, "lastTransactionID": "5"}


def pricing_document(
    *,
    bid: str = "1.10000",
    ask: str = "1.10020",
    include_bid: bool = True,
    include_ask: bool = True,
) -> dict:
    rows = []
    for name, default_bid, default_ask in INSTRUMENTS:
        row_bid = bid if name == "EUR_USD" else default_bid
        row_ask = ask if name == "EUR_USD" else default_ask
        row: dict[str, Any] = {
            "instrument": name,
            "time": "2026-10-21T16:00:00Z",
            "tradeable": True,
            "status": "tradeable",
            "closeoutBid": row_bid,
            "closeoutAsk": row_ask,
        }
        if include_bid:
            row["bids"] = [{"price": row_bid}]
        if include_ask:
            row["asks"] = [{"price": row_ask}]
        rows.append(row)
    return {"prices": rows}


class OfflineDouble:
    """Cooperative phases honour the budget. ignore_timeout sleeps and does not."""

    classification = "OFFLINE_DOUBLE"
    marker = MARKER
    offline_only = True

    def __init__(
        self,
        summary: dict | None = None,
        pricing: dict | None = None,
        *,
        status_code: int = 200,
        stalls: dict | None = None,
        ignore_timeout: bool = False,
        ignore_seconds: float = 0.0,
        ignore_phase: str = "connect",
        body_override: bytes | None = None,
        chunk_size: int = 65536,
        tls_policy: dict | None = None,
        error_body: bytes = b"",
    ) -> None:
        self.summary = summary_document() if summary is None else summary
        self.pricing = pricing_document() if pricing is None else pricing
        self.status_code = status_code
        self.stalls = dict(stalls or {})
        self.ignore_timeout = ignore_timeout
        self.ignore_seconds = ignore_seconds
        self.ignore_phase = ignore_phase
        self.body_override = body_override
        self.chunk_size = chunk_size
        self.tls_policy = tls_policy or {"verify_mode": "CERT_REQUIRED", "check_hostname": True}
        self.error_body = error_body
        self.advance_after_summary = 0.0
        self.pricing_status: int | None = None
        self.pricing_body: bytes | None = None
        self.phases_run: list[str] = []
        self._body = b""
        self._offset = 0
        self.chunks_served = 0
        self.raise_on: str | None = None
        self.raise_text = ""
        self._prepared = False
        self.closed = False

    def prepare(self, kind: str) -> None:
        if kind == "pricing" and self.pricing_status is not None:
            self.status_code = self.pricing_status
        if kind == "pricing" and self.pricing_body is not None and self.status_code == 200:
            self._body = self.pricing_body
        elif self.body_override is not None and self.status_code == 200:
            self._body = self.body_override
        elif self.status_code != 200:
            self._body = self.error_body
        else:
            document = self.summary if kind == "summary" else self.pricing
            self._body = json.dumps(document).encode("utf-8")
        self._offset = 0
        self._prepared = True

    def run_phase(self, phase: str, budget: float, clock: Any) -> None:
        self.phases_run.append(phase)
        if self.raise_on == phase:
            raise RuntimeError(self.raise_text)
        if self.ignore_timeout and phase == self.ignore_phase:
            time.sleep(self.ignore_seconds)
            return
        stall = self.stalls.get(phase)
        if stall is None:
            return
        if stall > budget:
            clock.advance(budget + 0.0001)
            return
        clock.advance(stall)

    def read_chunk(self, budget: float, clock: Any) -> bytes | None:
        self.chunks_served += 1
        delay = self.stalls.get("body_chunk")
        if delay:
            if delay > budget:
                clock.advance(budget + 0.0001)
                return b""
            clock.advance(delay)
        if self._offset >= len(self._body):
            return None
        chunk = self._body[self._offset : self._offset + self.chunk_size]
        self._offset += len(chunk)
        return chunk

    def note_summary_done(self, clock: Any) -> None:
        if self.advance_after_summary:
            clock.advance(self.advance_after_summary)

    def close(self) -> None:
        self.closed = True
