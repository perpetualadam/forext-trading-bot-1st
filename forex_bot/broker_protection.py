"""Read-only broker protection evidence.

Local stop and take-profit prices are not broker evidence. This module never
creates, amends, cancels, or closes orders, and it never deletes a local row.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)

PROTECTION_UNKNOWN = "PROTECTION_UNKNOWN"
PROTECTION_CONFIRMED = "PROTECTION_CONFIRMED"
UNPROTECTED_CONFIRMED = "UNPROTECTED_CONFIRMED"
PROTECTION_CONFLICT = "PROTECTION_CONFLICT"

ORDER_PENDING_CONFIRMED = "ORDER_PENDING_CONFIRMED"
ORDER_FILLED_CONFIRMED = "ORDER_FILLED_CONFIRMED"
ORDER_CANCELLED_CONFIRMED = "ORDER_CANCELLED_CONFIRMED"
ORDER_REJECTED_CONFIRMED = "ORDER_REJECTED_CONFIRMED"
ORDER_UNKNOWN = "ORDER_UNKNOWN"

STOP_LOSS_FILL_CONFIRMED = "STOP_LOSS_FILL_CONFIRMED"
TAKE_PROFIT_FILL_CONFIRMED = "TAKE_PROFIT_FILL_CONFIRMED"
EXIT_ATTRIBUTION_UNKNOWN = "EXIT_ATTRIBUTION_UNKNOWN"

_STOP_TYPES = frozenset({"STOP_LOSS", "GUARANTEED_STOP_LOSS"})
_TP_TYPES = frozenset({"TAKE_PROFIT"})
_FILLED_STATES = frozenset({"FILLED"})
_PENDING_STATES = frozenset({"PENDING"})
_CANCELLED_STATES = frozenset({"CANCELLED"})
_REJECTED_STATES = frozenset({"REJECTED"})
_PARTIAL_STATES = frozenset({"PARTIALLY_FILLED", "PARTIAL"})

_lock = threading.Lock()
_generation = 0
_published: dict[str, "ProtectionEvidence"] = {}


class ProtectionReadError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class ProtectionConflict(ProtectionReadError):
    """Contradictory broker evidence. Must not be resolved toward protection."""


@dataclass(frozen=True)
class ProtectiveOrderEvidence:
    instrument: str
    trade_id: str
    order_id: str
    order_type: str
    order_state: str
    price: Decimal | None
    units: Decimal | None
    transaction_id: str
    transaction_type: str
    transaction_time: str
    source: str


@dataclass(frozen=True)
class ProtectionEvidence:
    instrument: str
    account_scope: str
    trade_ids: tuple[str, ...]
    protection_state: str
    stop_protection: str
    take_profit_protection: str
    stop_order_state: str
    take_profit_order_state: str
    exit_attribution: str
    orders: tuple[ProtectiveOrderEvidence, ...] = field(default_factory=tuple)
    evidence_source: str = "none"
    completeness: str = "INCOMPLETE"
    generation: int = 0
    uncertainty_reason: str = ""
    local_prices_are_broker_evidence: bool = False
    authorises_close: bool = False
    authorises_management: bool = False
    authorises_local_delete: bool = False


def reset_protection_evidence_state() -> None:
    """Test helper. Does not touch positions or broker clients."""
    global _generation
    with _lock:
        _generation = 0
        _published.clear()


def published_protection_evidence(symbol: str) -> ProtectionEvidence | None:
    from forex_bot.symbols import normalize_oanda_symbol

    key = normalize_oanda_symbol(symbol)
    with _lock:
        return _published.get(key)


def _conflict(
    *,
    instrument: str,
    trade_ids: tuple[str, ...],
    reason: str,
    generation: int = 0,
) -> ProtectionEvidence:
    return ProtectionEvidence(
        instrument=instrument,
        account_scope="scoped",
        trade_ids=trade_ids,
        protection_state=PROTECTION_CONFLICT,
        stop_protection=PROTECTION_CONFLICT,
        take_profit_protection=PROTECTION_CONFLICT,
        stop_order_state=ORDER_UNKNOWN,
        take_profit_order_state=ORDER_UNKNOWN,
        exit_attribution=EXIT_ATTRIBUTION_UNKNOWN,
        evidence_source="trade_details",
        completeness="CONFLICT",
        generation=generation,
        uncertainty_reason=reason,
    )


def _unknown(
    *,
    instrument: str = "",
    trade_ids: tuple[str, ...] = (),
    reason: str,
    generation: int = 0,
    account_scope: str = "missing",
    source: str = "none",
) -> ProtectionEvidence:
    return ProtectionEvidence(
        instrument=instrument,
        account_scope=account_scope,
        trade_ids=trade_ids,
        protection_state=PROTECTION_UNKNOWN,
        stop_protection=PROTECTION_UNKNOWN,
        take_profit_protection=PROTECTION_UNKNOWN,
        stop_order_state=ORDER_UNKNOWN,
        take_profit_order_state=ORDER_UNKNOWN,
        exit_attribution=EXIT_ATTRIBUTION_UNKNOWN,
        evidence_source=source,
        completeness="INCOMPLETE",
        generation=generation,
        uncertainty_reason=reason,
    )


def _decimal(raw: Any, *, label: str) -> Decimal:
    if raw is None:
        raise ProtectionReadError(f"malformed_{label}")
    text = str(raw).replace(",", "").strip()
    if text == "":
        raise ProtectionReadError(f"malformed_{label}")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ProtectionReadError(f"malformed_{label}") from exc
    if not value.is_finite():
        raise ProtectionReadError(f"nonfinite_{label}")
    return value


def _begin(symbol: str, trade_ids: tuple[str, ...]) -> int:
    global _generation
    with _lock:
        _generation += 1
        return _generation


def _identity_now(symbol: str, trade_ids: tuple[str, ...]) -> bool:
    from forex_bot.broker_exit import local_broker_trade_ids
    from forex_bot.positions import positions
    from forex_bot.symbols import normalize_oanda_symbol

    row = positions.get(symbol) or positions.get(normalize_oanda_symbol(symbol))
    if row is None:
        return False
    if normalize_oanda_symbol(getattr(row, "symbol", "") or "") != symbol:
        return False
    return tuple(local_broker_trade_ids(row)) == trade_ids


def _publish(generation: int, symbol: str, trade_ids: tuple[str, ...], evidence: ProtectionEvidence) -> None:
    with _lock:
        if generation != _generation:
            raise ProtectionReadError("stale_response")
        if not _identity_now(symbol, trade_ids):
            raise ProtectionReadError("identity_changed")
        _published[symbol] = evidence


def _request_trade(trade_id: str) -> tuple[str, dict[str, Any]]:
    """GET TradeDetails. Raises ProtectionReadError. Does not write."""
    from forex_bot.config import Config
    from forex_bot.oanda_client import get_api

    api = get_api()
    account = (Config.OANDA_ACCOUNT_ID or "").strip()
    if api is None:
        raise ProtectionReadError("missing_client")
    if not account:
        raise ProtectionReadError("missing_account")
    try:
        import oandapyV20.endpoints.trades as trades_ep

        from forex_bot.oanda_client import _oanda_request
    except ModuleNotFoundError as exc:
        raise ProtectionReadError("reader_unavailable") from exc
    request = trades_ep.TradeDetails(accountID=account, tradeID=trade_id)
    try:
        body = _oanda_request(api, request, context="protection trade details")
    except TimeoutError as exc:
        raise ProtectionReadError("timeout") from exc
    except ProtectionReadError:
        raise
    except Exception as exc:
        raise ProtectionReadError("request_exception") from exc
    if body is None:
        raise ProtectionReadError("null_body")
    if not isinstance(body, dict):
        raise ProtectionReadError("malformed_body")
    return "scoped", body


def _order_from_section(
    blob: Any,
    *,
    instrument: str,
    trade_id: str,
    role: str,
) -> tuple[str, str, str, ProtectiveOrderEvidence | None]:
    """Return protection, order state, exit attribution, and the order record."""
    if blob is None:
        return UNPROTECTED_CONFIRMED, ORDER_UNKNOWN, EXIT_ATTRIBUTION_UNKNOWN, None
    if not isinstance(blob, dict):
        raise ProtectionReadError("malformed_order")
    order_id = str(blob.get("id") or "").strip()
    if not order_id:
        raise ProtectionReadError("malformed_order_id")
    order_type = str(blob.get("type") or "").strip().upper()
    allowed = _STOP_TYPES if role == "stop" else _TP_TYPES
    if order_type not in allowed:
        raise ProtectionReadError("order_type_mismatch")
    linked = str(blob.get("tradeID") or "").strip()
    if linked != trade_id:
        raise ProtectionConflict("order_trade_mismatch")
    state = str(blob.get("state") or "").strip().upper()
    price = _decimal(blob.get("price"), label="price")
    if price <= 0:
        raise ProtectionReadError("nonpositive_price")
    units = None
    if "units" in blob and blob.get("units") not in (None, ""):
        units = _decimal(blob.get("units"), label="units")
    filling = str(blob.get("fillingTransactionID") or "").strip()
    if state in _PENDING_STATES and filling:
        raise ProtectionConflict("contradictory_order_state")
    record = ProtectiveOrderEvidence(
        instrument=instrument,
        trade_id=trade_id,
        order_id=order_id,
        order_type=order_type,
        order_state=state or ORDER_UNKNOWN,
        price=price,
        units=units,
        transaction_id=filling,
        transaction_type="ORDER_FILL" if filling else "",
        transaction_time=str(blob.get("fillingTime") or blob.get("createTime") or ""),
        source="trade_details",
    )
    if state in _PENDING_STATES:
        return PROTECTION_CONFIRMED, ORDER_PENDING_CONFIRMED, EXIT_ATTRIBUTION_UNKNOWN, record
    if state in _CANCELLED_STATES:
        return PROTECTION_UNKNOWN, ORDER_CANCELLED_CONFIRMED, EXIT_ATTRIBUTION_UNKNOWN, record
    if state in _REJECTED_STATES:
        return PROTECTION_UNKNOWN, ORDER_REJECTED_CONFIRMED, EXIT_ATTRIBUTION_UNKNOWN, record
    if state in _PARTIAL_STATES:
        return PROTECTION_UNKNOWN, ORDER_UNKNOWN, EXIT_ATTRIBUTION_UNKNOWN, record
    if state in _FILLED_STATES:
        # The trade document can name a filling transaction. This reader does
        # not retrieve that transaction, so the fill is not attributed.
        filled_units = units
        trade_units_raw = blob.get("tradeUnits")
        if filled_units is not None and trade_units_raw not in (None, ""):
            expected = abs(_decimal(trade_units_raw, label="units"))
            if abs(filled_units) != expected:
                return PROTECTION_UNKNOWN, ORDER_UNKNOWN, EXIT_ATTRIBUTION_UNKNOWN, record
        return PROTECTION_UNKNOWN, ORDER_FILLED_CONFIRMED, EXIT_ATTRIBUTION_UNKNOWN, record
    return PROTECTION_UNKNOWN, ORDER_UNKNOWN, EXIT_ATTRIBUTION_UNKNOWN, record


def interpret_trade_protection(
    body: dict[str, Any] | None,
    *,
    instrument: str,
    trade_id: str,
    direction: str,
    local_units: Decimal,
) -> ProtectionEvidence:
    """Classify one TradeDetails body. Does not read the network or mutate positions."""
    if not isinstance(body, dict) or not isinstance(body.get("trade"), dict):
        raise ProtectionReadError("malformed_body")
    trade = body["trade"]
    from forex_bot.symbols import normalize_oanda_symbol

    want = normalize_oanda_symbol(instrument)
    got_id = str(trade.get("id") or "").strip()
    got_inst = normalize_oanda_symbol(str(trade.get("instrument") or ""))
    if got_id != trade_id or got_inst != want:
        raise ProtectionReadError("trade_identity_mismatch")
    state = str(trade.get("state") or "").strip().upper()
    if state not in {"OPEN", "CLOSED"}:
        raise ProtectionReadError("incomplete_trade")
    if state == "OPEN":
        if "currentUnits" not in trade:
            raise ProtectionReadError("incomplete_trade")
        units = _decimal(trade.get("currentUnits"), label="units")
        side = (direction or "").strip().upper()
        if side == "BUY" and units <= 0:
            raise ProtectionConflict("direction_conflict")
        if side == "SELL" and units >= 0:
            raise ProtectionConflict("direction_conflict")
        if side not in {"BUY", "SELL"}:
            raise ProtectionConflict("direction_conflict")
        if abs(units) != abs(local_units):
            raise ProtectionConflict("units_conflict")
    if state == "CLOSED" and "stopLossOrder" not in trade and "takeProfitOrder" not in trade:
        return _unknown(
            instrument=want,
            trade_ids=(trade_id,),
            reason="broker_trade_closed_without_fill_attribution",
            account_scope="scoped",
            source="trade_details",
        )
    if "stopLossOrder" not in trade and "takeProfitOrder" not in trade:
        raise ProtectionReadError("protection_sections_absent")
    orders: list[ProtectiveOrderEvidence] = []
    stop_protection = PROTECTION_UNKNOWN
    stop_order = ORDER_UNKNOWN
    stop_exit = EXIT_ATTRIBUTION_UNKNOWN
    tp_protection = PROTECTION_UNKNOWN
    tp_order = ORDER_UNKNOWN
    tp_exit = EXIT_ATTRIBUTION_UNKNOWN
    if "stopLossOrder" in trade:
        stop_protection, stop_order, stop_exit, stop_rec = _order_from_section(
            trade.get("stopLossOrder"), instrument=want, trade_id=trade_id, role="stop"
        )
        if stop_rec is not None:
            orders.append(stop_rec)
    if "takeProfitOrder" in trade:
        tp_protection, tp_order, tp_exit, tp_rec = _order_from_section(
            trade.get("takeProfitOrder"), instrument=want, trade_id=trade_id, role="take_profit"
        )
        if tp_rec is not None:
            orders.append(tp_rec)
    if len(orders) == 2 and orders[0].order_id == orders[1].order_id:
        raise ProtectionConflict("duplicate_order_id")
    exit_attribution = EXIT_ATTRIBUTION_UNKNOWN
    if stop_exit != EXIT_ATTRIBUTION_UNKNOWN and tp_exit != EXIT_ATTRIBUTION_UNKNOWN:
        raise ProtectionConflict("contradictory_exit")
    if stop_exit != EXIT_ATTRIBUTION_UNKNOWN:
        exit_attribution = stop_exit
    elif tp_exit != EXIT_ATTRIBUTION_UNKNOWN:
        exit_attribution = tp_exit
    if stop_protection == PROTECTION_CONFLICT or tp_protection == PROTECTION_CONFLICT:
        overall = PROTECTION_CONFLICT
    elif stop_protection == PROTECTION_CONFIRMED or tp_protection == PROTECTION_CONFIRMED:
        overall = PROTECTION_CONFIRMED
    elif (
        stop_protection == UNPROTECTED_CONFIRMED
        and tp_protection == UNPROTECTED_CONFIRMED
    ):
        overall = UNPROTECTED_CONFIRMED
    elif stop_protection == UNPROTECTED_CONFIRMED and "takeProfitOrder" not in trade:
        overall = PROTECTION_UNKNOWN
    elif tp_protection == UNPROTECTED_CONFIRMED and "stopLossOrder" not in trade:
        overall = PROTECTION_UNKNOWN
    else:
        overall = PROTECTION_UNKNOWN
    reason = ""
    if stop_order == ORDER_FILLED_CONFIRMED or tp_order == ORDER_FILLED_CONFIRMED:
        reason = "fill_reported_without_transaction_body"
    if state == "CLOSED":
        if stop_order != ORDER_FILLED_CONFIRMED and tp_order != ORDER_FILLED_CONFIRMED:
            return _unknown(
                instrument=want,
                trade_ids=(trade_id,),
                reason="broker_trade_closed_without_fill_attribution",
                account_scope="scoped",
                source="trade_details",
            )
        overall = PROTECTION_UNKNOWN
        stop_protection = PROTECTION_UNKNOWN
        tp_protection = PROTECTION_UNKNOWN
        reason = "closed_trade_fill_not_attributed"
    completeness = "COMPLETE" if overall != PROTECTION_UNKNOWN else "INCOMPLETE"
    if exit_attribution != EXIT_ATTRIBUTION_UNKNOWN:
        completeness = "COMPLETE"
    return ProtectionEvidence(
        instrument=want,
        account_scope="scoped",
        trade_ids=(trade_id,),
        protection_state=overall,
        stop_protection=stop_protection,
        take_profit_protection=tp_protection,
        stop_order_state=stop_order,
        take_profit_order_state=tp_order,
        exit_attribution=exit_attribution,
        orders=tuple(orders),
        evidence_source="trade_details",
        completeness=completeness,
        uncertainty_reason=reason,
    )


def collect_broker_protection_evidence(pos: Any) -> ProtectionEvidence:
    """Read protection for one permitted broker-backed row. Never writes or deletes."""
    from forex_bot.broker_exit import local_broker_trade_ids
    from forex_bot.execution import is_broker_backed
    from forex_bot.positions import position_management_permitted
    from forex_bot.symbols import normalize_oanda_symbol

    if not position_management_permitted(pos):
        return _unknown(reason="management_not_permitted")
    symbol = normalize_oanda_symbol(getattr(pos, "symbol", "") or "")
    if not is_broker_backed(pos):
        return _unknown(
            instrument=symbol,
            reason="local_reference_not_broker_evidence",
        )
    trade_ids = tuple(local_broker_trade_ids(pos))
    if len(trade_ids) != 1:
        reason = "missing_trade_id" if not trade_ids else "multiple_trade_ids"
        return _unknown(instrument=symbol, trade_ids=trade_ids, reason=reason)
    try:
        local_units = _decimal(getattr(pos, "units", None), label="units")
    except ProtectionReadError:
        return _unknown(instrument=symbol, trade_ids=trade_ids, reason="malformed_units")
    generation = _begin(symbol, trade_ids)
    try:
        _scope, body = _request_trade(trade_ids[0])
        evidence = interpret_trade_protection(
            body,
            instrument=symbol,
            trade_id=trade_ids[0],
            direction=str(getattr(pos, "direction", "") or ""),
            local_units=local_units,
        )
    except ProtectionConflict as exc:
        evidence = _conflict(
            instrument=symbol,
            trade_ids=trade_ids,
            reason=exc.reason,
            generation=generation,
        )
    except ProtectionReadError as exc:
        logger.warning("broker protection evidence withheld: %s", exc.reason)
        return _unknown(
            instrument=symbol,
            trade_ids=trade_ids,
            reason=exc.reason,
            generation=generation,
            account_scope="scoped" if exc.reason not in {"missing_client", "missing_account"} else "missing",
            source="trade_details",
        )
    evidence = ProtectionEvidence(
        instrument=evidence.instrument,
        account_scope=evidence.account_scope,
        trade_ids=evidence.trade_ids,
        protection_state=evidence.protection_state,
        stop_protection=evidence.stop_protection,
        take_profit_protection=evidence.take_profit_protection,
        stop_order_state=evidence.stop_order_state,
        take_profit_order_state=evidence.take_profit_order_state,
        exit_attribution=evidence.exit_attribution,
        orders=evidence.orders,
        evidence_source=evidence.evidence_source,
        completeness=evidence.completeness,
        generation=generation,
        uncertainty_reason=evidence.uncertainty_reason,
    )
    try:
        _publish(generation, symbol, trade_ids, evidence)
    except ProtectionReadError as exc:
        logger.warning("broker protection evidence withheld: %s", exc.reason)
        return _unknown(
            instrument=symbol,
            trade_ids=trade_ids,
            reason=exc.reason,
            generation=generation,
            account_scope="scoped",
            source="trade_details",
        )
    return evidence


def record_management_protection_evidence(pos: Any) -> ProtectionEvidence:
    """Operational hook. Records evidence and does not change close authority."""
    evidence = collect_broker_protection_evidence(pos)
    logger.info(
        "[BROKER PROTECTION] instrument=%s state=%s stop=%s tp=%s exit=%s reason=%s",
        evidence.instrument,
        evidence.protection_state,
        evidence.stop_protection,
        evidence.take_profit_protection,
        evidence.exit_attribution,
        evidence.uncertainty_reason,
    )
    return evidence
