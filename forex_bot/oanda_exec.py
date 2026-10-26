"""OANDA v20 market execution (optional; broker-agnostic fallbacks in trading.py)."""

from __future__ import annotations

import asyncio
import logging
import math
import os
from dataclasses import dataclass, field
from typing import Any

import oandapyV20.endpoints.orders as oanda_orders
import oandapyV20.endpoints.positions as oanda_positions
import oandapyV20.endpoints.trades as oanda_trades
from oandapyV20.contrib.requests import MarketOrderRequest, PositionCloseRequest
from oandapyV20.definitions.orders import OrderPositionFill, TimeInForce
from oandapyV20.exceptions import V20Error

from forex_bot.config import Config
from forex_bot.oanda_client import get_api, oanda_instrument

logger = logging.getLogger(__name__)

OUTCOME_FILLED = "FILLED"
OUTCOME_CANCELLED = "CANCELLED"
OUTCOME_REJECTED = "REJECTED"
OUTCOME_AMBIGUOUS_TRANSPORT = "AMBIGUOUS_TRANSPORT_OUTCOME"
OUTCOME_MALFORMED = "MALFORMED_RESPONSE"


@dataclass(frozen=True)
class OrderCreateClassification:
    outcome: str
    cancel_reason: str | None = None
    create_tx_id: str | None = None
    cancel_tx_id: str | None = None
    fill_tx_id: str | None = None
    client_id: str | None = None
    related_transaction_ids: tuple[str, ...] = field(default_factory=tuple)
    last_transaction_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_id: str | None = None


class OrderCreateOutcomeError(RuntimeError):
    """Broker open did not produce a fill. Never a signal to send another OrderCreate."""

    def __init__(self, classification: OrderCreateClassification, message: str) -> None:
        super().__init__(message)
        self.classification = classification


class OrderCreateCancelled(OrderCreateOutcomeError):
    pass


class OrderCreateRejected(OrderCreateOutcomeError):
    pass


class OrderCreateAmbiguous(OrderCreateOutcomeError):
    pass


class OrderCreateMalformed(OrderCreateOutcomeError):
    pass


def assert_broker_order_allowed(*, execution_kind: str | None = None, action: str = "order") -> None:
    """
    Fail closed: paper / window_paper / simulated context must never submit broker orders,
    even if EXECUTION_MODE is live_broker (off-window learning uses the same process).
    New live exposure also requires the durable default-deny authorisation gate.
    Protective closes are not blocked by that gate.
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
    from forex_bot.live_safety import assert_new_live_exposure_allowed

    assert_new_live_exposure_allowed(action=action)


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


def _as_tx_dict(raw: Any) -> dict[str, Any] | None:
    return raw if isinstance(raw, dict) and raw else None


def _tx_id(raw: dict[str, Any] | None) -> str | None:
    if not raw:
        return None
    val = raw.get("id")
    if val is None:
        return None
    text = str(val).strip()
    return text or None


def _client_id_from_tx(raw: dict[str, Any] | None) -> str | None:
    if not raw:
        return None
    ext = raw.get("clientExtensions")
    if isinstance(ext, dict):
        cid = ext.get("id")
        if cid is not None and str(cid).strip():
            return str(cid).strip()
    return None


def _related_ids(*sources: Any) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for src in sources:
        if isinstance(src, dict):
            raw = src.get("relatedTransactionIDs")
        else:
            raw = src
        if not isinstance(raw, list):
            continue
        for item in raw:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                out.append(text)
    return tuple(out)


def _fill_usable(fill: dict[str, Any] | None) -> bool:
    if not fill:
        return False
    price = fill.get("price")
    if price is None or str(price).strip() == "":
        return False
    try:
        px = float(str(price).replace(",", ""))
    except (TypeError, ValueError):
        return False
    return math.isfinite(px)


def classify_order_create_response(response: Any) -> OrderCreateClassification:
    """Classify an HTTP-successful OrderCreate body. Fill wins over cancel."""
    if not isinstance(response, dict):
        return OrderCreateClassification(
            outcome=OUTCOME_MALFORMED,
            error_message="invalid OANDA response",
        )
    fill = _as_tx_dict(response.get("orderFillTransaction"))
    create_tx = _as_tx_dict(response.get("orderCreateTransaction"))
    cancel_tx = _as_tx_dict(response.get("orderCancelTransaction"))
    reject_tx = _as_tx_dict(response.get("orderRejectTransaction"))
    last_id = str(response.get("lastTransactionID") or "").strip() or None
    related = _related_ids(response, create_tx, cancel_tx, fill, reject_tx)
    cid = (
        _client_id_from_tx(fill)
        or _client_id_from_tx(cancel_tx)
        or _client_id_from_tx(create_tx)
        or _client_id_from_tx(reject_tx)
    )
    if _fill_usable(fill):
        return OrderCreateClassification(
            outcome=OUTCOME_FILLED,
            fill_tx_id=_tx_id(fill) or last_id,
            create_tx_id=_tx_id(create_tx),
            cancel_tx_id=_tx_id(cancel_tx),
            client_id=cid,
            related_transaction_ids=related,
            last_transaction_id=last_id,
        )
    if cancel_tx is not None:
        reason = str(cancel_tx.get("reason") or "").strip() or None
        return OrderCreateClassification(
            outcome=OUTCOME_CANCELLED,
            cancel_reason=reason,
            create_tx_id=_tx_id(create_tx) or str(cancel_tx.get("orderID") or "").strip() or None,
            cancel_tx_id=_tx_id(cancel_tx),
            client_id=cid,
            related_transaction_ids=related,
            last_transaction_id=last_id,
        )
    if reject_tx is not None:
        return OrderCreateClassification(
            outcome=OUTCOME_REJECTED,
            create_tx_id=_tx_id(create_tx),
            client_id=cid,
            related_transaction_ids=related,
            last_transaction_id=last_id,
            error_code=str(reject_tx.get("rejectReason") or reject_tx.get("errorCode") or "").strip()
            or None,
            error_message=str(reject_tx.get("errorMessage") or reject_tx.get("rejectReason") or "").strip()
            or None,
        )
    return OrderCreateClassification(
        outcome=OUTCOME_MALFORMED,
        create_tx_id=_tx_id(create_tx),
        client_id=cid,
        related_transaction_ids=related,
        last_transaction_id=last_id,
        error_message="unclassifiable OANDA OrderCreate response",
    )


def _is_timeout_like(exc: BaseException) -> bool:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        name = type(cur).__name__.lower()
        if isinstance(cur, (TimeoutError, ConnectionError)):
            return True
        if "timeout" in name or "connection" in name:
            return True
        text = str(cur).lower()
        if "timed out" in text or "timeout" in text or "connection" in text:
            return True
        cur = cur.__cause__ or getattr(cur, "__context__", None)
    return False


def classify_order_create_transport_error(exc: BaseException) -> OrderCreateClassification:
    if isinstance(exc, V20Error):
        try:
            code_i = int(exc.code)
        except (TypeError, ValueError):
            code_i = None
        msg = str(exc.msg or exc).strip() or None
        code_s = None if code_i is None else str(code_i)
        if code_i is not None and 400 <= code_i < 500 and code_i != 408:
            return OrderCreateClassification(
                outcome=OUTCOME_REJECTED,
                error_code=code_s,
                error_message=msg,
            )
        return OrderCreateClassification(
            outcome=OUTCOME_AMBIGUOUS_TRANSPORT,
            error_code=code_s,
            error_message=msg,
        )
    if _is_timeout_like(exc):
        return OrderCreateClassification(
            outcome=OUTCOME_AMBIGUOUS_TRANSPORT,
            error_message=str(exc).strip() or type(exc).__name__,
        )
    return OrderCreateClassification(
        outcome=OUTCOME_AMBIGUOUS_TRANSPORT,
        error_message=str(exc).strip() or type(exc).__name__,
    )


def format_order_cancel_line(
    *,
    symbol: str,
    side: str,
    cid: str,
    classification: OrderCreateClassification,
) -> str:
    related = ",".join(classification.related_transaction_ids) or "n/a"
    return (
        f"[ORDER CANCEL] symbol={symbol} side={side} cid={cid or classification.client_id or 'n/a'} "
        f"create_tx={classification.create_tx_id or 'n/a'} "
        f"cancel_tx={classification.cancel_tx_id or 'n/a'} "
        f"reason={classification.cancel_reason or 'n/a'} "
        f"related_transaction_ids={related}"
    )


def _raise_for_classification(
    classification: OrderCreateClassification, *, symbol: str = "", side: str = "", cid: str = ""
) -> None:
    if classification.outcome == OUTCOME_CANCELLED:
        raise OrderCreateCancelled(
            classification,
            format_order_cancel_line(symbol=symbol, side=side, cid=cid, classification=classification),
        )
    if classification.outcome == OUTCOME_REJECTED:
        raise OrderCreateRejected(
            classification,
            f"[ORDER REJECTED] symbol={symbol} side={side} cid={cid} "
            f"errorCode={classification.error_code or 'n/a'} "
            f"errorMessage={classification.error_message or 'n/a'}",
        )
    if classification.outcome == OUTCOME_AMBIGUOUS_TRANSPORT:
        raise OrderCreateAmbiguous(
            classification,
            f"[ORDER AMBIGUOUS] symbol={symbol} side={side} cid={cid} "
            f"{classification.error_message or 'uncertain broker write'}",
        )
    raise OrderCreateMalformed(
        classification,
        f"[ORDER MALFORMED] symbol={symbol} side={side} cid={cid} "
        f"{classification.error_message or 'unclassifiable OANDA response'}",
    )


def _parse_open_fill(response: dict[str, Any]) -> tuple[float, float, str, float, float | None]:
    """
    Market open: (fill_price, abs_units_filled, order_fill_transaction_id, realized_pl or nan).
    """
    classified = classify_order_create_response(response)
    if classified.outcome != OUTCOME_FILLED:
        _raise_for_classification(classified)
    oft = response.get("orderFillTransaction")
    if not isinstance(oft, dict):
        _raise_for_classification(
            OrderCreateClassification(
                outcome=OUTCOME_MALFORMED,
                error_message="unclassifiable OANDA OrderCreate response",
            )
        )
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
    from forex_bot.profit_protection import _to_epoch

    fill_ts = _to_epoch(oft.get("time"))
    return fill_price, uf, oid, pl, fill_ts


class CloseGuardRefusal(RuntimeError):
    """The journal did not grant this close. No broker request was made."""


def _submit_position_close_body(
    symbol: str,
    position_units: float,
    position_direction: str,
    permit,
) -> dict[str, Any]:
    """PUT position close. Refuses unless the journal consumes this permit."""
    from forex_bot.close_journal import CloseSubmissionPermit, JournalUnavailable, active_journal

    if not isinstance(permit, CloseSubmissionPermit):
        raise CloseGuardRefusal("live close refused: journal submission authority is required")
    from forex_bot.startup_recovery import live_management_permitted

    if not live_management_permitted():
        raise CloseGuardRefusal("live close refused: recovery authority is absent")
    try:
        active_journal().claim_network_permit(permit)
    except JournalUnavailable as exc:
        raise CloseGuardRefusal(f"live close refused: {exc.reason}") from exc
    api = get_api()
    if api is None:
        raise RuntimeError("OANDA API client unavailable (token / build_api)")

    account_id = _account_id()
    if not account_id:
        raise RuntimeError("OANDA_ACCOUNT_ID missing")

    instrument = oanda_instrument(symbol)
    d = (position_direction or "").upper().strip()
    if d not in ("BUY", "SELL"):
        raise RuntimeError("protective close withheld: uncertain position direction")
    try:
        units_f = float(position_units)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("protective close withheld: uncertain position size") from exc
    if not math.isfinite(units_f) or units_f == 0:
        raise RuntimeError("protective close withheld: uncertain position size")
    units_s = _abs_units_decimal(units_f)
    if d == "BUY":
        close_req = PositionCloseRequest(longUnits=units_s)
    else:
        close_req = PositionCloseRequest(shortUnits=units_s)

    # longClientExtensions / shortClientExtensions exist on the SDK request.
    # They are labels, not a broker idempotency key. This call does not send them.
    r = oanda_positions.PositionClose(
        accountID=account_id, instrument=instrument, data=close_req.data
    )
    if not live_management_permitted():
        raise CloseGuardRefusal("live close refused: recovery authority lost before request")
    try:
        from forex_bot.oanda_rate_limit import acquire_oanda_rest_slot

        acquire_oanda_rest_slot()
        if not live_management_permitted():
            raise CloseGuardRefusal("live close refused: recovery authority lost during rate limit")
        response = api.request(r)
    except CloseGuardRefusal:
        raise
    except TimeoutError:
        logger.error("OANDA PositionClose timed out")
        raise
    except Exception as exc:
        logger.error("OANDA PositionClose failed: %s", exc)
        raise RuntimeError(str(exc)) from exc

    if not isinstance(response, dict):
        raise ValueError("invalid OANDA PositionClose response")
    return response


def _place_market_order_sync(
    symbol: str, position_units: float, position_direction: str, permit
) -> tuple[float, float]:
    """PUT position close. A returned tuple is not proof the local row may be deleted."""
    response = _submit_position_close_body(symbol, position_units, position_direction, permit)
    d = (position_direction or "").upper().strip()
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
    logger.info("[ORDER CLOSE] PositionClose %s %s fill=%.5f", symbol, d, fill_price)
    return pl, fill_price


def _submit_order_create(
    symbol: str,
    position_units: float,
    direction: str,
    client_order_id: str,
    stop_loss: float | None,
    take_profit: float | None,
    entry_quote: Any | None,
    entry_permit,
) -> dict[str, Any]:
    """POST OrderCreate. Refuses unless the entry journal consumes this permit."""
    from forex_bot.close_journal import JournalUnavailable
    from forex_bot.entry_journal import EntryGuardRefusal, EntrySubmissionPermit, claim_entry_permit
    from forex_bot.live_safety import assert_new_live_exposure_allowed
    from forex_bot.market_provenance import require_order_quote

    if not isinstance(entry_permit, EntrySubmissionPermit):
        raise EntryGuardRefusal("live entry refused: journal submission intent is required")
    from forex_bot.startup_recovery import live_management_permitted

    if not live_management_permitted():
        raise EntryGuardRefusal("live entry refused: recovery authority is absent")
    assert_new_live_exposure_allowed(action="open")
    require_order_quote(entry_quote, symbol)
    try:
        claim_entry_permit(entry_permit)
    except JournalUnavailable as exc:
        raise EntryGuardRefusal(f"live entry refused: {exc.reason}") from exc
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
        sl_on_fill = {"price": _format_oanda_price(instrument, float(stop_loss)), "timeInForce": "GTC"}
    if take_profit is not None and math.isfinite(float(take_profit)):
        tp_on_fill = {"price": _format_oanda_price(instrument, float(take_profit)), "timeInForce": "GTC"}
    mo = MarketOrderRequest(
        instrument=instrument,
        units=units_int,
        timeInForce=TimeInForce.FOK,
        positionFill=OrderPositionFill.OPEN_ONLY,
        clientExtensions={"id": cid, "tag": "forex_bot", "comment": "idempotent client order"},
        stopLossOnFill=sl_on_fill,
        takeProfitOnFill=tp_on_fill,
    )
    assert_new_live_exposure_allowed(action="open")
    request = oanda_orders.OrderCreate(accountID=account_id, data=mo.data)
    if not live_management_permitted():
        raise EntryGuardRefusal("live entry refused: recovery authority lost before request")
    logger.info("[ORDER SENT] MARKET open %s units=%s", instrument, units_int)
    try:
        from forex_bot.oanda_rate_limit import acquire_oanda_rest_slot

        acquire_oanda_rest_slot()
        if not live_management_permitted():
            raise EntryGuardRefusal("live entry refused: recovery authority lost during rate limit")
        response = api.request(request)
    except EntryGuardRefusal:
        raise
    except OrderCreateOutcomeError:
        raise
    except TimeoutError:
        logger.error("[ORDER FAILED] OANDA OrderCreate (open) timeout")
        raise
    except Exception as exc:
        classified = classify_order_create_transport_error(exc)
        logger.error("[ORDER FAILED] OANDA OrderCreate (open) %s: %s", classified.outcome, exc)
        _raise_for_classification(classified, symbol=instrument, side=direction, cid=cid)
    if not isinstance(response, dict):
        raise RuntimeError("invalid OANDA OrderCreate response")
    return response


def _place_market_order_open_sync(
    symbol: str,
    position_units: float,
    direction: str,
    client_order_id: str,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    entry_quote: Any | None = None,
    *,
    entry_permit,
) -> tuple[float, float, str, float, float | None]:
    """Place MARKET order to open; returns (fill_price, abs_units, fill_tx_id, pl, fill_time)."""
    from forex_bot.entry_journal import mark_entry

    try:
        response = _submit_order_create(
            symbol,
            position_units,
            direction,
            client_order_id,
            stop_loss,
            take_profit,
            entry_quote,
            entry_permit,
        )
    except TimeoutError:
        mark_entry(entry_permit.operation_id, outcome="ENTRY_OUTCOME_AMBIGUOUS", error="timeout")
        raise
    from forex_bot.entry_capture import record_entry_response

    try:
        record_entry_response(entry_permit, response, account_id=_account_id())
    except Exception:
        mark_entry(entry_permit.operation_id, outcome="ENTRY_OUTCOME_AMBIGUOUS", error="capture_failed")
        raise
    classified = classify_order_create_response(response)
    if classified.outcome == OUTCOME_CANCELLED:
        _raise_for_classification(classified, symbol=symbol, side=direction, cid=client_order_id)
    if classified.outcome != OUTCOME_FILLED:
        _raise_for_classification(classified, symbol=symbol, side=direction, cid=client_order_id)
    fp, uf, oid, pl, fill_ts = _parse_open_fill(response)
    logger.info("[ORDER FILLED] %s %s units≈%.4f fill=%.5f id=%s", symbol, direction, uf, fp, oid)
    return fp, uf, oid, pl, fill_ts


async def execute_oanda_market_open(
    symbol: str,
    position_units: float,
    direction: str,
    client_order_id: str,
    *,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    execution_kind: str = "live",
    entry_quote: Any | None = None,
    entry_permit,
) -> tuple[float, float, str, float, float | None]:
    """Broker-confirmed open. The permit is required and is not entry eligibility."""
    from forex_bot.market_provenance import require_order_quote

    assert_broker_order_allowed(execution_kind=execution_kind, action="open")
    require_order_quote(entry_quote, symbol)
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
        entry_quote,
        entry_permit=entry_permit,
    )


def fetch_pending_orders_sync() -> list[dict[str, Any]]:
    """Raw pending orders from OANDA (empty if unavailable)."""
    api = get_api()
    aid = _account_id()
    if api is None or not aid:
        return []
    try:
        from forex_bot.oanda_client import _oanda_request

        r = oanda_orders.OrdersPending(accountID=aid)
        resp: dict[str, Any] = _oanda_request(api, r, context="pending orders")
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


def fetch_transaction_details_sync(transaction_id: str) -> dict[str, Any] | None:
    """
    GET a single account transaction. Never creates, cancels, or replaces orders.
    """
    xid = str(transaction_id or "").strip()
    if not xid:
        return None
    api = get_api()
    aid = _account_id()
    if api is None or not aid:
        return None
    try:
        import oandapyV20.endpoints.transactions as tx_ep

        from forex_bot.oanda_client import _oanda_request

        r = tx_ep.TransactionDetails(accountID=aid, transactionID=xid)
        resp: dict[str, Any] = _oanda_request(api, r, context="transaction details")
    except Exception as exc:
        logger.warning("OANDA TransactionDetails %s failed: %s", xid, exc)
        return None
    tx = resp.get("transaction") if isinstance(resp, dict) else None
    return tx if isinstance(tx, dict) else None


async def execute_oanda_market_close(
    symbol: str,
    position_units: float,
    position_direction: str,
    entry_price: float,
    permit,
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
        _place_market_order_sync, symbol, position_units, position_direction, permit
    )
    if math.isnan(pl):
        from forex_bot.trading import pnl_account_ccy

        u = abs(float(position_units))
        d = (position_direction or "").upper().strip()
        pl = pnl_account_ccy(symbol, d, float(entry_price), float(fill_price), u)
    return float(pl), float(fill_price)
