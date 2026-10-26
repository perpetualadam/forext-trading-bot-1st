"""Fixed two-step read plan. No URL override and no extra endpoints.

The instrument order is the production default list in forex_bot/symbols.py.
The pricing query has the same single key the operational PricingInfo call sends.
"""

from __future__ import annotations

HOST = "api-fxtrade.oanda.com"
PORT = 443
SCHEME = "https"
SYNTHETIC_ACCOUNT_ID = "001-001-0000000-001"
INSTRUMENTS = (
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
)
SUMMARY_PATTERN = "/v3/accounts/{accountID}/summary"
PRICING_PATTERN = "/v3/accounts/{accountID}/pricing"


class PlanRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def summary_candidate(account_id: str = SYNTHETIC_ACCOUNT_ID) -> dict:
    _pin_account(account_id)
    return _candidate(f"/v3/accounts/{account_id}/summary", {})


def pricing_candidate(account_id: str = SYNTHETIC_ACCOUNT_ID) -> dict:
    _pin_account(account_id)
    return _candidate(
        f"/v3/accounts/{account_id}/pricing",
        {"instruments": ",".join(INSTRUMENTS)},
    )


def session_plan(account_id: str = SYNTHETIC_ACCOUNT_ID) -> tuple[dict, dict]:
    return summary_candidate(account_id), pricing_candidate(account_id)


def _pin_account(account_id: str) -> None:
    if account_id != SYNTHETIC_ACCOUNT_ID:
        raise PlanRejected("ACCOUNT_ID_REJECTED")


def _candidate(path: str, query: dict) -> dict:
    return {
        "method": "GET",
        "scheme": SCHEME,
        "host": HOST,
        "port": PORT,
        "path": path,
        "query": dict(query),
        "body": None,
        "redirects": False,
        "retries": 0,
        "stream": False,
    }
