"""OANDA v20 market execution (optional; broker-agnostic fallbacks in trading.py)."""

from __future__ import annotations

import asyncio
import logging
import math
import os
from typing import Any

import oandapyV20.endpoints.orders as oanda_orders
import oandapyV20.endpoints.positions as oanda_positions
import oandapyV20.endpoints.trades as oanda_trades
from oandapyV20.contrib.requests import MarketOrderRequest, PositionCloseRequest
from oandapyV20.definitions.orders import OrderPositionFill, TimeInForce

from forex_bot.config import Config
from forex_bot.oanda_client import get_api, oanda_instrument

logger = logging.getLogger(__name__)


def assert_broker_order_allowed(*, execution_kind: str | None = None, action: str = "order") -> None:
    """
    Fail closed: paper / window_paper / simulated context must never submit broker orders,
    even if EXECUTION_MODE is live_broker (off-window learning uses the same process).
    """
    from forex_bot.execution import ExecutionMode, get_execution_mode, is_paper_like_kind

    kind = (execution_kind or "").strip().lower()
    if is_paper_like_kind(kind):
        raise RuntimeError(
            f"refusing broker {action}: execution_kind={kind or 'unset'} is local-only "
            f"(paper/window_paper/simulated cannot submit OANDA orders)"
        )
    if get_execution_mode() == ExecutionMode.PAPER:
        raise RuntimeError(f"refusing broker {action}: EXECUTION_MODE=paper")
    if not use_oanda_live():
        raise RuntimeError(f"broker execution not enabled for {action}")


def use_oanda_live() -> bool:
    """
    True when broker orders are allowed.

    - If ``EXECUTION_MODE`` is set to ``paper_broker`` or ``live_broker``, orders are enabled.
    - If unset, legacy ``USE_OANDA_LIVE`` gates order placement (``paper`` mode never sends orders).
    """
    from forex_bot.execution import ExecutionMode, get_execution_mode

    if (os.getenv("EXECUTION_MODE") or "").strip():
        return get_execution_mode() != ExecutionMode.PAPER
    raw = (os.getenv("USE_OANDA_LIVE") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _access_token() -> str:
    return (os.getenv("OANDA_ACCESS_TOKEN") or os.getenv("OANDA_API_KEY") or "").strip()


def _account_id() -> str:
    return (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()


def _abs_units_decimal(position_units: float) -> str:
    """OANDA DecimalNumber: always a string; position-close units must be positive."""
    u = max(1, int(round(abs(float(position_units)))))
    return str(u)


def _order_units_for_open(position_units: float, direction: str) -> int:
    """Opening: BUY → positive units, SELL → negative (v20 MarketOrder.units)."""
    u = max(1, int(round(abs(float(position_units)))))
    if (direction or "").upper().strip() == "BUY":
        return u
    return -u


def _format_oanda_price(symbol: str, price: float) -> str:
    """OANDA price precision: JPY pairs use 3 decimals, most majors use 5."""
    s = (symbol or "").upper().replace("-", "_")
    if "JPY" in s:
        return f"{float(price):.3f}"
    return f"{float(price):.5f}"


def _parse_fill(response: dict[str, Any]) -> tuple[float, float]:
    """Return (realized_pl_account_ccy, fill_price) from OrderCreate response."""
    oft = response.get("orderFillTransaction")
    if not oft:
        raise ValueError("OANDA response missing orderFillTransaction")

    fill_price = float(str(oft.get("price", "0")).replace(",", ""))
    pl_raw = oft.get("pl")
    if pl_raw is None or str(pl_raw).strip() == "":
        pl = float("nan")
    else:
        pl = float(str(pl_raw).replace(",", ""))
    return pl, fill_price


def _parse_open_fill(response: dict[str, Any]) -> tuple[float, float, str, float]:
    """
    Market open: (fill_price, abs_units_filled, order_fill_transaction_id, realized_pl or nan).
    """
    oft = response.get("orderFillTransaction")
    if not oft:
        raise ValueError("OANDA response missing orderFillTransaction")
    fill_price = float(str(oft.get("price", "0")).replace(",", ""))
    u_raw = oft.get("units")
    try:
        uf = abs(float(str(u_raw).replace(",", ""))) if u_raw is not None else 0.0
    except (TypeError, ValueError):
        uf = 0.0
    oid = str(oft.get("id") or response.get("lastTransactionID") or "")
    pl_raw = oft.get("pl")
    if pl_raw is None or str(pl_raw).strip() == "":
        pl = float("nan")
    else:
        pl = float(str(pl_raw).replace(",", ""))
    return fill_price, uf, oid, pl


def _place_market_order_sync(symbol: str, position_units: float, position_direction: str) -> tuple[float, float]:
    """PUT /v3/accounts/{id}/positions/{instrument}/close (official closeout)."""
    api = get_api()
    if api is None:
        raise RuntimeError("OANDA API client unavailable (token / build_api)")

    account_id = _account_id()
    if not account_id:
        raise RuntimeError("OANDA_ACCOUNT_ID missing")

    instrument = oanda_instrument(symbol)
    units_s = _abs_units_decimal(position_units)
    d = (position_direction or "").upper().strip()
    if d == "BUY":
        close_req = PositionCloseRequest(longUnits=units_s)
    else:
        close_req = PositionCloseRequest(shortUnits=units_s)

    r = oanda_positions.PositionClose(
        accountID=account_id, instrument=instrument, data=close_req.data
    )
    try:
        response = api.request(r)
    except Exception as exc:
        logger.error("OANDA PositionClose failed: %s", exc)
        raise RuntimeError(str(exc)) from exc

    if not isinstance(response, dict):
        raise ValueError("invalid OANDA PositionClose response")
    if d == "BUY":
        oft = response.get("longOrderFillTransaction") or {}
    else:
        oft = response.get("shortOrderFillTransaction") or {}
    if not oft:
        oft = response.get("orderFillTransaction") or {}
    cancel = response.get("longOrderCancelTransaction") or response.get("shortOrderCancelTransaction")
    if cancel and not oft:
        raise RuntimeError(f"OANDA PositionClose cancelled: {cancel.get('reason') or cancel}")
    pl, fill_price = _parse_fill({"orderFillTransaction": oft} if oft else {})
    if math.isnan(pl):
        logger.warning("OANDA close fill missing pl; fill_price=%s", fill_price)
    logger.info("[ORDER CLOSE] PositionClose %s %s units=%s fill=%.5f", instrument, d, units_s, fill_price)
    return pl, fill_price


def _place_market_order_open_sync(
    symbol: str,
    position_units: float,
    direction: str,
    client_order_id: str,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> tuple[float, float, str, float]:
    """Place MARKET order to open; returns (fill_price, abs_units, fill_tx_id, pl)."""
    api = get_api()
    if api is None:
        raise RuntimeError("OANDA API client unavailable (token / build_api)")
    account_id = _account_id()
    if not account_id:
        raise RuntimeError("OANDA_ACCOUNT_ID missing")
    instrument = oanda_instrument(symbol)
    units_int = _order_units_for_open(position_units, direction)
    cid = (client_order_id or "").strip()[:128] or f"cid-{instrument}"
    sl_on_fill = None
    tp_on_fill = None
    if stop_loss is not None and math.isfinite(float(stop_loss)):
        sl_on_fill = {
            "price": _format_oanda_price(instrument, float(stop_loss)),
            "timeInForce": "GTC",
        }
    if take_profit is not None and math.isfinite(float(take_profit)):
        tp_on_fill = {
            "price": _format_oanda_price(instrument, float(take_profit)),
            "timeInForce": "GTC",
        }
    # Official MarketOrder: units DecimalNumber, timeInForce FOK|IOC, OPEN_ONLY for entries.
    mo = MarketOrderRequest(
        instrument=instrument,
        units=units_int,
        timeInForce=TimeInForce.FOK,
        positionFill=OrderPositionFill.OPEN_ONLY,
        clientExtensions={
            "id": cid,
            "tag": "forex_bot",
            "comment": "idempotent client order",
        },
        stopLossOnFill=sl_on_fill,
        takeProfitOnFill=tp_on_fill,
    )
    r = oanda_orders.OrderCreate(accountID=account_id, data=mo.data)
    logger.info("[ORDER SENT] MARKET open %s units=%s", instrument, units_int)
    try:
        response = api.request(r)
    except Exception as exc:
        logger.error("[ORDER FAILED] OANDA OrderCreate (open) failed: %s", exc)
        raise RuntimeError(str(exc)) from exc
    if not isinstance(response, dict):
        raise ValueError("invalid OANDA response")
    fp, uf, oid, pl = _parse_open_fill(response)
    logger.info("[ORDER FILLED] %s %s units≈%.4f fill=%.5f id=%s", instrument, direction, uf, fp, oid)
    return fp, uf, oid, pl


async def execute_oanda_market_open(
    symbol: str,
    position_units: float,
    direction: str,
    client_order_id: str,
    *,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    execution_kind: str = "live",
) -> tuple[float, float, str, float]:
    """Broker-confirmed open: (fill_price, abs_filled_units, fill_transaction_id, pl_account_ccy)."""
    assert_broker_order_allowed(execution_kind=execution_kind, action="open")
    if not _access_token():
        raise RuntimeError("OANDA_ACCESS_TOKEN or OANDA_API_KEY missing")
    return await asyncio.to_thread(
        _place_market_order_open_sync,
        symbol,
        position_units,
        direction,
        client_order_id,
        stop_loss,
        take_profit,
    )


def fetch_pending_orders_sync() -> list[dict[str, Any]]:
    """Raw pending orders from OANDA (empty if unavailable)."""
    api = get_api()
    aid = _account_id()
    if api is None or not aid:
        return []
    try:
        r = oanda_orders.OrdersPending(accountID=aid)
        resp: dict[str, Any] = api.request(r)
    except Exception as exc:
        logger.warning("OANDA OrdersPending failed: %s", exc)
        return []
    orders = resp.get("orders")
    return list(orders) if isinstance(orders, list) else []


def fetch_trade_details_sync(trade_id: str) -> dict[str, Any] | None:
    """
    GET a single trade. Never creates, cancels, or replaces orders.

    OpenPositions does not include SL/TP or openTime; TradeDetails can.
    """
    tid = str(trade_id or "").strip()
    if not tid:
        return None
    api = get_api()
    aid = _account_id()
    if api is None or not aid:
        return None
    try:
        from forex_bot.oanda_client import _oanda_request

        r = oanda_trades.TradeDetails(accountID=aid, tradeID=tid)
        resp: dict[str, Any] = _oanda_request(api, r, context="trade details")
    except Exception as exc:
        logger.warning("OANDA TradeDetails %s failed: %s", tid, exc)
        return None
    trade = resp.get("trade") if isinstance(resp, dict) else None
    return trade if isinstance(trade, dict) else None


async def execute_oanda_market_close(
    symbol: str,
    position_units: float,
    position_direction: str,
    entry_price: float,
    *,
    execution_kind: str = "live",
) -> tuple[float, float]:
    """
    Place a market order to flatten ``position_units`` / ``position_direction``.

    Returns ``(realized_pnl_account_currency, exit_fill_price)``.
    Runs the synchronous REST call in a thread pool.
    """
    assert_broker_order_allowed(execution_kind=execution_kind, action="close")
    if not _access_token():
        raise RuntimeError("OANDA_ACCESS_TOKEN or OANDA_API_KEY missing")

    pl, fill_price = await asyncio.to_thread(
        _place_market_order_sync, symbol, position_units, position_direction
    )
    if math.isnan(pl):
        from forex_bot.trading import pnl_account_ccy

        u = abs(float(position_units))
        d = (position_direction or "").upper().strip()
        pl = pnl_account_ccy(symbol, d, float(entry_price), float(fill_price), u)
    return float(pl), float(fill_price)
