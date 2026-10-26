"""Scripted responses for the offline connector. No socket is used."""

from __future__ import annotations

import json
from typing import Any

MARKER = "R56P5_SCRIPTED"
INSTRUMENTS = (
    ("EUR_USD", "1.10000", "1.10020"),
    ("GBP_USD", "1.20000", "1.20030"),
    ("USD_JPY", "150.000", "150.030"),
    ("AUD_USD", "0.65000", "0.65010"),
    ("USD_CAD", "1.30000", "1.30040"),
    ("USD_CHF", "0.90000", "0.90020"),
)


def summary_document(*, include_currency: bool = True) -> dict[str, Any]:
    account: dict[str, Any] = {
        "id": "001-001-0000000-001",
        "NAV": "100.00",
        "balance": "100.00",
        "unrealizedPL": "0.00",
        "marginAvailable": "100.00",
        "marginUsed": "0.00",
        "alias": "synthetic-alias-not-logged",
        "lastTransactionID": "5",
    }
    if include_currency:
        account["currency"] = "GBP"
    return {"account": account, "lastTransactionID": "5"}


def pricing_document(*, include_bid: bool = True, bid: str = "1.10000") -> dict[str, Any]:
    rows = []
    for name, default_bid, default_ask in INSTRUMENTS:
        row_bid = bid if name == "EUR_USD" else default_bid
        row: dict[str, Any] = {
            "instrument": name,
            "time": "2026-10-21T16:00:00Z",
            "tradeable": True,
            "status": "tradeable",
            "closeoutBid": row_bid,
            "closeoutAsk": default_ask,
        }
        if include_bid:
            row["bids"] = [{"price": row_bid}]
        row["asks"] = [{"price": default_ask}]
        rows.append(row)
    return {"prices": rows}


class ScriptedConnector:
    """Returns prepared bytes. exchange() does not open a socket."""

    offline_only = True
    marker = MARKER
    proxy_from_environment = False

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
        self.calls: list[str] = []

    def exchange(self, prepared: Any) -> bytes:
        self.calls.append(prepared.method + " " + prepared.path)
        if self.fill:
            return b"x" * self.fill
        if self.body is not None:
            return self.body
        return json.dumps(self.document).encode("utf-8")
