"""Synthetic account-summary and pricing documents. Not broker evidence."""

from __future__ import annotations

SYNTHETIC_ACCOUNT_ID = "001-001-0000000-001"
SYNTHETIC_TOKEN = "SYNTHETIC-TOKEN-R56P3-NOT-REAL"
INSTRUMENTS = (
    ("EUR_USD", "1.10000", "1.10020"),
    ("GBP_USD", "1.20000", "1.20030"),
    ("USD_JPY", "150.000", "150.030"),
    ("AUD_USD", "0.65000", "0.65010"),
    ("USD_CAD", "1.30000", "1.30040"),
    ("USD_CHF", "0.90000", "0.90020"),
)


def summary_document(*, currency: str | None = "GBP", extra: dict | None = None) -> dict:
    account = {
        "id": SYNTHETIC_ACCOUNT_ID,
        "currency": currency if currency is not None else "",
        "NAV": "100.00",
        "balance": "100.00",
        "unrealizedPL": "0.00",
        "marginAvailable": "100.00",
        "alias": "synthetic-alias-not-logged",
        "lastTransactionID": "5",
    }
    if currency is None:
        account.pop("currency")
    if extra:
        account.update(extra)
    return {"account": account, "lastTransactionID": "5"}


def pricing_document(*, extra: dict | None = None) -> dict:
    rows = []
    for name, bid, ask in INSTRUMENTS:
        row = {
            "instrument": name,
            "time": "2026-10-21T16:00:00Z",
            "tradeable": True,
            "status": "tradeable",
            "bids": [{"price": bid}],
            "asks": [{"price": ask}],
            "closeoutBid": bid,
            "closeoutAsk": ask,
        }
        if extra and name == "EUR_USD":
            row.update(extra)
        rows.append(row)
    return {"prices": rows}


def secret_exception() -> RuntimeError:
    return RuntimeError(f"Bearer {SYNTHETIC_TOKEN} account {SYNTHETIC_ACCOUNT_ID}")
