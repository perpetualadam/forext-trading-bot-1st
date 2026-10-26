"""Synthetic OANDA-shaped close fixtures.

These dictionaries follow the public trade-close examples retrieved on
26 October 2026. They are not captured broker responses. Account and trade
identifiers here are synthetic.
"""

from __future__ import annotations

ACCOUNT = "001-002-0000001-003"


def order_fill(
    *,
    transaction_id: str,
    instrument: str,
    fill_units: str,
    trade_id: str,
    trades_closed: str | None = None,
    trade_reduced: str | None = None,
    order_id: str = "ORD-R84",
    trade_opened: dict | None = None,
    extra: dict | None = None,
) -> dict:
    body = {
        "id": transaction_id,
        "type": "ORDER_FILL",
        "accountID": ACCOUNT,
        "instrument": instrument,
        "orderID": order_id,
        "units": fill_units,
        "reason": "MARKET_ORDER_TRADE_CLOSE",
    }
    if trades_closed is not None:
        body["tradesClosed"] = [
            {"tradeID": trade_id, "units": trades_closed, "realizedPL": "0.00000"}
        ]
    if trade_reduced is not None:
        body["tradeReduced"] = {
            "tradeID": trade_id,
            "units": trade_reduced,
            "realizedPL": "0.00000",
        }
    if trade_opened is not None:
        body["tradeOpened"] = trade_opened
    if extra:
        body.update(extra)
    return body


def documented_buy_full_close() -> dict:
    """Shape of the official full-close example: fill and tradesClosed are '-100'."""
    return order_fill(
        transaction_id="6404",
        instrument="EUR_USD",
        fill_units="-100",
        trade_id="6395",
        trades_closed="-100",
        order_id="6403",
    )


def documented_sell_partial_close() -> dict:
    """Shape of the official partial-close example: fill and tradeReduced are '10'."""
    return order_fill(
        transaction_id="6402",
        instrument="USD_CAD",
        fill_units="10",
        trade_id="6397",
        trade_reduced="10",
        order_id="6401",
    )
