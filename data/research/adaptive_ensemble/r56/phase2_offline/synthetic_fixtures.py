"""Synthetic documents shaped like the operational parsers. Not broker evidence."""

from __future__ import annotations

SYNTHETIC_ACCOUNT_ID = "001-001-0000000-001"
SYNTHETIC_TOKEN = "SYNTHETIC-TOKEN-R56P2-NOT-REAL"


def account_document(
    *,
    currency: str | None = "GBP",
    nav: object = "100.00",
    balance: object = "100.00",
    margin_available: object = "100.00",
    margin_used: object | None = None,
    unrealised: object = "0.00",
    account_id: str = SYNTHETIC_ACCOUNT_ID,
    include_currency: bool = True,
    include_nav: bool = True,
    include_margin: bool = True,
    extra: dict | None = None,
) -> dict:
    """Fields read by forex_bot.oanda_account_adapter.account_core, plus optional marginUsed.

    marginUsed is not copied by that function. It is present only when this fixture sets it.
    """
    account: dict = {
        "id": account_id,
        "balance": balance,
        "unrealizedPL": unrealised,
        "alias": "synthetic-alias-not-logged",
        "lastTransactionID": "5",
    }
    if include_currency and currency is not None:
        account["currency"] = currency
    if include_nav:
        account["NAV"] = nav
    if include_margin:
        account["marginAvailable"] = margin_available
    if margin_used is not None:
        account["marginUsed"] = margin_used
    if extra:
        account.update(extra)
    return {"account": account, "lastTransactionID": "5"}


def pricing_document(
    *,
    instrument: str = "EUR_USD",
    bid: object = "1.10000",
    ask: object = "1.10020",
    time: object | None = "2026-10-21T16:00:00Z",
    tradeable: object | None = True,
    status: str | None = "tradeable",
    extra_bid: str | None = None,
    extra_ask: str | None = None,
    conversions: bool = False,
    extra: dict | None = None,
    include_bid: bool = True,
    include_ask: bool = True,
    include_time: bool = True,
    include_tradeable: bool = True,
) -> dict:
    """Keys read by forex_bot.oanda_client.fetch_pricing_snapshot.

    Home-conversion keys are omitted unless conversions=True. The operational
    PricingInfo call does not send includeHomeConversions.
    """
    row: dict = {"instrument": instrument}
    if include_bid:
        bids = [{"price": bid}]
        if extra_bid is not None:
            bids.append({"price": extra_bid})
        row["bids"] = bids
    if include_ask:
        asks = [{"price": ask}]
        if extra_ask is not None:
            asks.append({"price": extra_ask})
        row["asks"] = asks
    if include_time and time is not None:
        row["time"] = time
    if include_tradeable and tradeable is not None:
        row["tradeable"] = tradeable
    if status is not None:
        row["status"] = status
    row["closeoutBid"] = "1.09980"
    row["closeoutAsk"] = "1.10040"
    if conversions:
        row["quoteHomeConversionFactors"] = {
            "positiveUnits": "0.74000",
            "negativeUnits": "0.74100",
        }
        row["homeConversions"] = [
            {"currency": "GBP", "accountGain": "0.74000", "accountLoss": "0.74100"}
        ]
    if extra:
        row.update(extra)
    return {"prices": [row]}


def sizing_document(
    *,
    instrument: str | None = "EUR_USD",
    units: str | None = "1",
    stop_distance: str | None = "0.00100",
    risk_budget: str | None = "1.00",
    currency: str | None = "GBP",
    pip_value: str | None = "0.00",
    margin_estimate: str | None = None,
    conversion: dict | None = None,
    source: str = "SYNTHETIC_TEST_ONLY",
    extra: dict | None = None,
) -> dict:
    """Caller-supplied sizing notes. These values are not an OANDA size quote."""
    body: dict = {"sources": {}}
    fields = {
        "instrument": instrument,
        "proposed_api_units": units,
        "stop_distance": stop_distance,
        "risk_budget": risk_budget,
        "account_currency": currency,
        "calculated_pip_value": pip_value,
        "margin_estimate": margin_estimate,
    }
    for key, value in fields.items():
        if value is not None:
            body[key] = value
            body["sources"][key] = source
    if conversion is not None:
        body["conversion_inputs"] = conversion
        body["sources"]["conversion_inputs"] = source
    if extra:
        body.update(extra)
    return body


def exception_with_secret() -> Exception:
    return RuntimeError(
        f"Bearer {SYNTHETIC_TOKEN} account {SYNTHETIC_ACCOUNT_ID} must not be logged"
    )
