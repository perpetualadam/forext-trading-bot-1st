"""Evaluation loop, evolution, and daily reporting."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from forex_bot.ai_ensemble import ai
from forex_bot.alerts import alert
from forex_bot.analytics import analytics
from forex_bot.config import Config
from forex_bot.execution import (
    close_fill_path,
    effective_paper_trading,
    is_broker_backed,
    is_paper_like_kind,
    open_fill_path,
    pre_trade_entry_blocked_reason,
)
from forex_bot.indicators import compute_indicators
from forex_bot.live_manage import ManageQuote
from forex_bot.nn_pred import compute_nn_pred
from forex_bot.execution_metrics import record_fill_failure, record_fill_quality
from forex_bot.orders import (
    OrderStatus,
    OrderStatus,
    finalize_order_fill,
    generate_client_order_id,
    mark_order_failed_or_cancelled,
    try_begin_order_submission,
    update_order,
)
from forex_bot.portfolio_exposure import (
    approx_gross_usd_notional_for,
    configured_max_gross_usd,
    format_notional_cap_report,
    format_notional_cap_skip_alert,
    format_usd_direction_skip,
    notional_cap_decision,
    notional_pct_of_nav,
    portfolio_gross_notional_pct_of_nav,
    same_usd_direction_open_positions,
    usd_direction,
    usd_direction_guard_decision,
)
from forex_bot.portfolio import PortfolioEngine
from forex_bot.positions import (
    Position,
    close_position,
    get_position,
    open_position,
    position_management_permitted,
    positions as position_map,
)
from forex_bot.profit_protection import (
    ProtectionDecision,
    apply_profit_protection,
    mark_protection_close_attempt,
    original_tp_distance_pips,
    pip_size as _pip_size,
    protection_close_allowed,
    raise_mfe_from_post_entry_ohlcv,
    seed_position_mfe,
    unrealized_profit_pips,
)
from forex_bot.rl_agent import RLAgent
from forex_bot.session_rules import (
    flatten_for_weekend,
    in_active_session,
    is_live_trading,
    live_window_log_enabled,
    log_live_windows,
    pre_close_adjustment,
    symbol_live_window_status,
    volatility_ok,
)
from forex_bot.operational_events import record_operational_transition_if_changed
from forex_bot.state import (
    current_equity,
    last_report_ts,
    pricing_snapshot,
    record_mid,
    set_last_report_ts,
    set_pricing_snapshot,
    state as state_dict,
)
from forex_bot.decision_skip_log import (
    CANDLE_ACQUISITION_FAILED,
    CANDLE_INTERNAL_ERROR,
    CANDLE_PARSING_FAILED,
    CYCLE_INTEGRITY_FAILED,
    DECISION_CANDLES_EMPTY,
    DECISION_CANDLES_FETCH_FAILED,
    DECISION_CANDLES_MISSING,
    DECISION_CANDLES_UNVERIFIED,
    ENTRY_SKIPPED_NO_VALID_CANDLES,
    INSTRUMENT_CYCLE_FAILED,
    LIVE_ORDER_AUTH_BLOCKED,
    MANAGEMENT_CONTINUED_WITHOUT_CANDLES,
    MANAGEMENT_QUOTE_STALE,
    MANAGEMENT_QUOTE_UNAVAILABLE,
    MANAGEMENT_UNAVAILABLE,
    MARKET_SESSION_CLOSED,
    NO_OHLCV,
    NO_STRATEGY_SELECTED,
    POSITION_ALREADY_OPEN,
    PROTECTIVE_CLOSE_FAILED,
    PROTECTIVE_CLOSE_UNCONFIRMED,
    QUANT_AI_REJECTED,
    RECONCILE_OR_PRETRADE_BLOCKED,
    RL_DIRECTION_MISMATCH,
    RL_SKIP,
    RL_STATE_UNAVAILABLE,
    SIZING_BELOW_MIN,
    STALE_OR_INVALID_DATA,
    STRATEGY_INACTIVE,
    STRATEGY_NOT_AUTHORISED,
    VOLATILITY_UNSAFE,
    WEEKEND_FLATTEN,
    log_decision_skip,
    log_strategy_pre_sizing_skip,
)
from forex_bot.strategy_meta import select_strategy, seq_model, strategies
from forex_bot.entry_geometry import (
    fetch_entry_pricing,
    format_entry_fill_geometry_line,
    format_entry_geometry_line,
    format_entry_geometry_skip,
    live_broker_geometry_required,
    resolve_live_entry_geometry,
)
from forex_bot.trading import (
    apply_execution_costs,
    apply_latency,
    apply_market_impact,
    calculate_pnl,
    cap_position_units,
    configured_max_portfolio_risk_pct,
    execute_trade,
    portfolio_risk_amount,
    portfolio_risk_cap_exceeded,
    position_sizing,
    sl_tp_distance_for_entry,
    stop_risk_account_ccy,
    strategy_execution_style,
)

logger = logging.getLogger(__name__)

rl_agent = RLAgent()


def canonical_entry_direction(value: object) -> str | None:
    """Return BUY or SELL. Any missing or unrecognised value is not a trade."""
    if not isinstance(value, str):
        return None
    text = value.strip().upper()
    if text in ("BUY", "SELL"):
        return text
    return None


def direction_action_gate(value: object, sizer, builder, sender, reserve=None) -> str | None:
    """Call sizing, construction, reservation, and dispatch only after a valid direction."""
    direction = canonical_entry_direction(value)
    if direction is None:
        return None
    if sizer is not None:
        sizer(direction)
    if builder is not None:
        builder(direction)
    if reserve is not None:
        reserve(direction)
    if sender is not None:
        sender(direction)
    return direction


def _authoritative_strategy(
    selected: object,
    *,
    active_map: dict[str, bool] | None,
) -> tuple[str | None, str | None, bool]:
    """Apply the selector result. A caller-supplied name is not an input.

    Returns the strategy name, a block reason, and whether that name is active
    for this decision. Production ``strategies[name].active`` is not changed.
    """
    if selected is None or (isinstance(selected, str) and not str(selected).strip()):
        return None, "NO_STRATEGY_SELECTED", False
    if not isinstance(selected, str):
        return None, "selector_result_malformed", False
    name = selected.strip()
    if name not in strategies:
        return None, "UNKNOWN_STRATEGY", False
    strat = strategies[name]
    if active_map is not None and name in active_map:
        active = bool(active_map[name])
    else:
        active = bool(strat.active)
    if not active:
        return name, "STRATEGY_INACTIVE", False
    return name, None, True


def strategy_entry_block_reason(
    strategy_name: str | None,
    *,
    active: bool,
    authorised_for_live: bool,
    safety_initialised: bool,
    known_strategy: bool,
) -> str | None:
    """Return a block reason before sizing. None means the entry may continue."""
    if strategy_name is None:
        return "NO_STRATEGY_SELECTED"
    if not known_strategy:
        return "UNKNOWN_STRATEGY"
    if not active:
        return "STRATEGY_INACTIVE"
    if safety_initialised and not authorised_for_live:
        return "STRATEGY_NOT_AUTHORISED"
    return None


def continue_entry_after_strategy_gate(
    strategy_name: str | None,
    *,
    active: bool,
    authorised_for_live: bool,
    safety_initialised: bool,
    known_strategy: bool,
    sizer,
    builder,
    sender,
    id_factory,
) -> str | None:
    """Run trading actions only after the strategy gate allows the entry."""
    if strategy_entry_block_reason(
        strategy_name,
        active=active,
        authorised_for_live=authorised_for_live,
        safety_initialised=safety_initialised,
        known_strategy=known_strategy,
    ):
        return None
    if sizer is not None:
        sizer()
    if builder is not None:
        builder()
    if id_factory is not None:
        id_factory()
    if sender is not None:
        sender()
    return strategy_name


def broker_entry_block_reason(symbol: str) -> str | None:
    """Block a new broker client id while an earlier intent is unresolved or unreadable."""
    from forex_bot.database import current_intent_book, new_intent_block_reason, read_durable_recovery

    rows, readable = read_durable_recovery()
    return new_intent_block_reason(current_intent_book(), symbol, rows, readable)


def _safe_audit(**fields: object) -> None:
    """Merge into the current evaluation session, or append a standalone record."""
    try:
        from forex_bot.decision_repair.audit import current_audit
        from forex_bot.live_safety import live_order_auth_state

        cur = current_audit()
        payload = {k: v for k, v in fields.items() if v is not None}
        if "live_order_auth_state" not in payload:
            payload["live_order_auth_state"] = live_order_auth_state()
        if cur is not None:
            cur.update(**payload)
            return
        from forex_bot.decision_repair.flags import audit_enabled
        from forex_bot.decision_repair.audit import append_record_safe, empty_record

        if not audit_enabled():
            return
        rec = empty_record(symbol=str(fields.get("symbol") or ""))
        rec.update(payload)
        append_record_safe(rec)
    except Exception:
        logger.exception("decision audit append failed (ignored)")


def _audit_reject(reason: str, *, stage: str) -> None:
    try:
        from forex_bot.decision_repair.audit import reject_current

        reject_current(reason, stage=stage)
    except Exception:
        logger.exception("decision audit reject stamp failed (ignored)")


def _audit_close(*, outcome: str, trigger: str, evidence: str = "NOT_EVALUATED") -> None:
    """Never blocks a protective close."""
    try:
        from forex_bot.decision_repair.audit import current_audit

        cur = current_audit()
        if cur is None:
            return
        cur.note_close(outcome=outcome, trigger=trigger, evidence=evidence)
    except Exception:
        logger.exception("decision audit close stamp failed (ignored; close not blocked)")


def _permit_new_exposure_or_block() -> bool:
    """Fail closed for new exposure when the audit flag is on and the write fails."""
    try:
        from forex_bot.decision_repair.audit import current_audit

        cur = current_audit()
        if cur is None:
            return True
        return bool(cur.permit_new_exposure())
    except Exception:
        logger.exception("decision audit new-exposure persist failed (blocked)")
        return False
portfolio = PortfolioEngine()

_last_performance_log_ts: float = 0.0


def _performance_log_enabled() -> bool:
    return (os.getenv("PERFORMANCE_LOG") or "1").strip().lower() not in ("0", "false", "no", "off")


def _performance_log_interval_sec() -> float:
    try:
        return max(0.0, float((os.getenv("PERFORMANCE_LOG_INTERVAL_SEC") or "0").strip() or "0"))
    except ValueError:
        return 0.0


def _maybe_log_performance_metrics() -> None:
    """One identifiable [PERFORMANCE] line per bot cycle, or throttled by PERFORMANCE_LOG_INTERVAL_SEC."""
    global _last_performance_log_ts
    if not _performance_log_enabled():
        return
    now = time.time()
    interval = _performance_log_interval_sec()
    if interval > 0 and (now - _last_performance_log_ts) < interval:
        return
    _last_performance_log_ts = now
    import forex_bot.positions as posmod

    eq = current_equity()
    pf = analytics.profit_factor()
    if pf is None:
        pf_s = "n/a"
    elif pf == float("inf"):
        pf_s = "inf"
    else:
        pf_s = f"{float(pf):.4f}"
    logger.info(
        "[PERFORMANCE] equity=%.2f sharpe=%.4f win_rate_pct=%.2f winrate=%.4f drawdown=%.2f "
        "closed_trades=%s profit_factor=%s open_positions=%s open_symbols=%s",
        eq,
        analytics.sharpe(),
        analytics.win_rate_pct(),
        analytics.winrate(),
        analytics.drawdown(),
        len(analytics.trades),
        pf_s,
        len(posmod.positions),
        sorted(posmod.positions.keys()),
    )


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    return int(v) if v else default


def _min_position_hold_sec() -> float:
    """Seconds to hold before SL/TP exits apply; 0 = disabled (immediate exit on touch)."""
    try:
        return max(0.0, float((os.getenv("MIN_POSITION_HOLD_SEC") or "0").strip() or "0"))
    except ValueError:
        return 0.0


def _position_log_enabled() -> bool:
    return (os.getenv("POSITION_LOG") or "1").strip().lower() not in ("0", "false", "no", "off")


def _log_open_position_line(symbol: str, pos: Position, price: float) -> None:
    """Lightweight snapshot: no extra API/DB; uses current bar mid from evaluate()."""
    mtm = calculate_pnl(pos, price)
    if mtm > 1e-12:
        side = "winning"
    elif mtm < -1e-12:
        side = "losing"
    else:
        side = "flat"
    age_sec = time.time() - float(pos.open_time)
    pip = _pip_size(symbol)
    if pos.direction == "BUY":
        d_sl = float(price) - float(pos.stop_loss)
        d_tp = float(pos.take_profit) - float(price)
    else:
        d_sl = float(pos.stop_loss) - float(price)
        d_tp = float(price) - float(pos.take_profit)
    p_sl = d_sl / pip if pip else 0.0
    p_tp = d_tp / pip if pip else 0.0
    mh = _min_position_hold_sec()
    if mh > 0:
        hold_part = f"min_hold_remain_sec={max(0.0, mh - age_sec):.0f}"
    else:
        hold_part = "min_hold_remain_sec=n/a"
    logger.info(
        "[POSITION] %s dir=%s age_sec=%.0f mtm_pnl=%.5f side=%s mid=%.5f entry=%.5f "
        "dist_to_sl_price=%.5f dist_to_tp_price=%.5f dist_to_sl_pips=%.1f dist_to_tp_pips=%.1f %s",
        symbol,
        pos.direction,
        age_sec,
        mtm,
        side,
        price,
        pos.entry_price,
        d_sl,
        d_tp,
        p_sl,
        p_tp,
        hold_part,
    )


def _refresh_pricing_snapshot() -> None:
    """One batched PricingInfo GET per bot cycle. Never writes."""
    from forex_bot.oanda_client import fetch_pricing_snapshot

    try:
        snap = fetch_pricing_snapshot(Config.SYMBOLS)
    except Exception:
        logger.exception("pricing snapshot failed")
        snap = {}
    set_pricing_snapshot(snap)


def _m5_bar_time(raw) -> str:
    try:
        return str(raw["time"].iloc[-1])
    except Exception:
        return ""


def _tp_progress(pos: Position) -> float | None:
    dist = original_tp_distance_pips(pos)
    mfe = float(getattr(pos, "max_profit_pips", 0.0) or 0.0)
    if dist is None or dist <= 0:
        return None
    return mfe / dist


def _df_last(df, column: str) -> float | None:
    if column not in df.columns:
        return None
    raw = df[column].iloc[-1]
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if val != val:
        return None
    return val


def _persist_v2_shadow_market_m5(symbol: str, raw) -> None:
    """Research-only. Uses already-fetched M5. Return discarded. Never authorizes."""
    from forex_bot.v2_shadow.market import maybe_record_completed_m5

    maybe_record_completed_m5(symbol, raw)


def _observe_v2_shadow_candidate(
    *,
    symbol: str,
    strategy_name: str,
    direction: str,
    price: float,
    df,
    atr_v: float,
    ma_fast: float,
    ma_slow: float,
    ret_1: float,
    rl_action: str,
    rl_state: str,
) -> None:
    """Shadow-only. Return is discarded. Must never change production direction."""
    from forex_bot.v2_shadow import maybe_observe_candidate

    quote = pricing_snapshot().get(symbol)
    bid = getattr(quote, "bid", None) if quote is not None else None
    ask = getattr(quote, "ask", None) if quote is not None else None
    if bid is None and quote is not None:
        bid = getattr(quote, "closeout_bid", None)
    if ask is None and quote is not None:
        ask = getattr(quote, "closeout_ask", None)
    now_utc = datetime.now(timezone.utc)
    rets: dict[str, float | None] = {}
    for label, steps in (("ret_5", 1), ("ret_15", 3), ("ret_30", 6)):
        if len(df) > steps:
            c0 = float(df["close"].iloc[-1])
            c1 = float(df["close"].iloc[-1 - steps])
            rets[label] = ((c0 - c1) / c1) if c1 else None
        else:
            rets[label] = None
    n_broker = sum(1 for p in position_map.values() if is_broker_backed(p))
    usd_dir = usd_direction(symbol, direction)
    usd_count = len(same_usd_direction_open_positions(usd_dir)) if usd_dir else None
    from forex_bot.oanda_client import last_account_summary

    acct = last_account_summary() or {}
    exposure = acct.get("positionValue")
    if exposure is None:
        exposure = acct.get("NAV")
    maybe_observe_candidate(
        symbol=symbol,
        strategy_label=strategy_name,
        production_side=direction,
        mid=price,
        bid=float(bid) if bid is not None else None,
        ask=float(ask) if ask is not None else None,
        pip_size=_pip_size(symbol),
        atr=None if atr_v != atr_v else atr_v,
        sma_fast=None if ma_fast != ma_fast else ma_fast,
        sma_slow=None if ma_slow != ma_slow else ma_slow,
        rsi=_df_last(df, "rsi"),
        macd=_df_last(df, "macd"),
        boll_up=_df_last(df, "boll_up"),
        boll_down=_df_last(df, "boll_down"),
        ret_1=None if ret_1 != ret_1 else ret_1,
        ret_5=rets["ret_5"],
        ret_15=rets["ret_15"],
        ret_30=rets["ret_30"],
        hour_utc=now_utc.hour,
        day_of_week=now_utc.weekday(),
        usd_direction=usd_dir,
        broker_backed_position_count=n_broker,
        gross_portfolio_exposure=float(exposure) if exposure is not None else None,
        same_usd_direction_count=usd_count,
        rl_action=rl_action,
        rl_state=rl_state,
        rl_q_values=dict(rl_agent.q.get(rl_state) or {}),
        rl_epsilon=float(rl_agent.epsilon),
    )


class CycleIntegrityError(RuntimeError):
    """Shared-state failure. Stop the rest of this symbol cycle."""


def _record_candle_failure(symbol: str, reason: str) -> None:
    """Record a decision-candle failure without logging broker payloads."""
    logger.warning("%s: %s", symbol, reason)
    log_decision_skip(symbol=symbol, reason=reason, stage="data")
    if reason == DECISION_CANDLES_UNVERIFIED:
        log_decision_skip(symbol=symbol, reason=STALE_OR_INVALID_DATA, stage="data")
        return
    if reason != NO_OHLCV:
        log_decision_skip(symbol=symbol, reason=NO_OHLCV, stage="data")


def _skip_new_entry_without_candles(symbol: str, audit_reason: str = NO_OHLCV) -> None:
    log_decision_skip(symbol=symbol, reason=ENTRY_SKIPPED_NO_VALID_CANDLES, stage="data")
    log_decision_skip(symbol=symbol, reason=audit_reason, stage="data")


def _candle_exception_kind(exc: BaseException) -> str:
    """Classify a candle-boundary failure. Integrity errors are not passed here."""
    from forex_bot.market_provenance import ProvenanceRejected

    if isinstance(exc, ProvenanceRejected):
        return CANDLE_INTERNAL_ERROR
    if isinstance(exc, (ValueError, KeyError, TypeError, ArithmeticError)):
        return CANDLE_PARSING_FAILED
    if isinstance(exc, RuntimeError):
        return CANDLE_INTERNAL_ERROR
    return CANDLE_ACQUISITION_FAILED


def _contain_candle_exception(symbol: str, exc: BaseException) -> tuple[None, str]:
    """Candles are unavailable. This does not decide whether a position can be managed."""
    kind = _candle_exception_kind(exc)
    logger.warning("%s: %s (%s)", symbol, kind, type(exc).__name__)
    log_decision_skip(symbol=symbol, reason=kind, stage="data")
    _record_candle_failure(symbol, DECISION_CANDLES_FETCH_FAILED)
    return None, NO_OHLCV


def fetch_ohlcv(symbol: str, granularity: str, count: int):
    """Decision-candle seam. Callers and tests replace this; the client remains the source."""
    from forex_bot.oanda_client import fetch_ohlcv as client_fetch_ohlcv

    return client_fetch_ohlcv(symbol, granularity, count)


async def _load_decision_candles(symbol: str, count: int):
    """Load the decision frame. Acquisition failure returns None and never fabricates bars.

    The second value is the audit reason that must stay last when no entry is made.
    ``CycleIntegrityError`` is the only acquisition-call failure that stops the cycle.
    """
    try:
        raw = await asyncio.to_thread(fetch_ohlcv, symbol, "M5", count)
    except CycleIntegrityError:
        raise
    except AssertionError:
        raise
    except Exception as exc:  # noqa: BLE001 — candle failures must not skip position management
        return _contain_candle_exception(symbol, exc)
    try:
        if raw is None:
            _record_candle_failure(symbol, DECISION_CANDLES_MISSING)
            return None, NO_OHLCV
        if bool(getattr(raw, "empty", True)):
            _record_candle_failure(symbol, DECISION_CANDLES_EMPTY)
            return None, NO_OHLCV
        if "close" not in raw.columns or bool(raw["close"].isna().iloc[-1]):
            logger.warning("Incomplete OHLCV for %s", symbol)
            _record_candle_failure(symbol, DECISION_CANDLES_UNVERIFIED)
            return None, STALE_OR_INVALID_DATA
    except CycleIntegrityError:
        raise
    except AssertionError:
        raise
    except Exception:  # noqa: BLE001 — a malformed frame is unverified, not a cycle abort
        logger.warning("%s: decision candle frame could not be validated", symbol)
        _record_candle_failure(symbol, DECISION_CANDLES_UNVERIFIED)
        return None, STALE_OR_INVALID_DATA
    return raw, None


def _normalise_instrument(value: object) -> str:
    return str(value or "").replace("/", "_").replace("-", "_").upper()


def _screen_manage_quote(
    symbol: str, quote: ManageQuote | None
) -> tuple[ManageQuote | None, str | None]:
    """Check instrument identity and bid/ask. Freshness stays in resolve_broker_manage_price."""
    if quote is None:
        return None, MANAGEMENT_QUOTE_UNAVAILABLE
    if _normalise_instrument(getattr(quote, "instrument", "")) != _normalise_instrument(symbol):
        return None, MANAGEMENT_QUOTE_UNAVAILABLE
    bid = getattr(quote, "bid", None)
    ask = getattr(quote, "ask", None)
    if bid is not None or ask is not None:
        try:
            bid_f = float(bid) if bid is not None else None
            ask_f = float(ask) if ask is not None else None
        except (TypeError, ValueError):
            return None, MANAGEMENT_QUOTE_UNAVAILABLE
        if (
            bid_f is None
            or ask_f is None
            or not math.isfinite(bid_f)
            or not math.isfinite(ask_f)
            or bid_f <= 0
            or ask_f <= 0
            or bid_f > ask_f
        ):
            return None, MANAGEMENT_QUOTE_UNAVAILABLE
    from forex_bot.live_manage import MANAGE_PRICE_STALE_SEC, quote_age_sec

    age = quote_age_sec(quote)
    if age is not None and age > float(MANAGE_PRICE_STALE_SEC):
        return quote, MANAGEMENT_QUOTE_STALE
    return quote, None


def _position_close_identity(pos: Position) -> tuple[str, float] | None:
    side = str(getattr(pos, "direction", "") or "").upper().strip()
    if side not in ("BUY", "SELL"):
        return None
    try:
        units = float(pos.units)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(units) or units <= 0:
        return None
    return side, units


def _close_exception_reason(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timed out" in text or "timeout" in text:
        return PROTECTIVE_CLOSE_UNCONFIRMED
    return PROTECTIVE_CLOSE_FAILED


async def _cycle_symbols(symbols) -> None:
    """Run one symbol at a time. An isolated failure does not skip the remaining names."""
    for symbol in symbols:
        try:
            await evaluate(symbol)
        except CycleIntegrityError:
            logger.exception("instrument cycle integrity failure on %s", symbol)
            log_decision_skip(symbol=symbol, reason=CYCLE_INTEGRITY_FAILED, stage="cycle")
            log_decision_skip(
                symbol=symbol,
                reason=INSTRUMENT_CYCLE_FAILED,
                stage="cycle",
                detail="integrity",
            )
            raise
        except Exception:
            logger.exception("instrument_cycle_failed %s", symbol)
            log_decision_skip(symbol=symbol, reason=INSTRUMENT_CYCLE_FAILED, stage="cycle")


async def evaluate(symbol: str, dependencies: IterationDependencies | None = None) -> dict[str, Any] | None:
    """Evaluate one symbol. Audit session is best-effort except fail-closed new exposure.

    A supplied dependency object uses the shared single-iteration boundary
    and does not enter ``_evaluate_impl`` or ``run_bot``.
    """
    if dependencies is not None:
        return dispatch_production_iteration(symbol, dependencies)
    from forex_bot.decision_repair.audit import EvaluationAudit

    session = EvaluationAudit.start(symbol)
    try:
        await _evaluate_impl(symbol)
    except Exception:
        session.note_error("UNEXPECTED_EVALUATION_ERROR")
        raise
    finally:
        session.finish()


async def _evaluate_impl(symbol: str) -> None:
    """Evaluate: manage open positions (TP/SL) or open new risk-based positions (hybrid + AI + RL)."""
    ohlcv_count = _env_int("HYBRID_OHLCV_COUNT", 200)
    raw, candle_audit = await _load_decision_candles(symbol, ohlcv_count)
    price = None
    if raw is not None:
        try:
            from forex_bot.decision_repair.audit import candle_fingerprint

            last = raw.iloc[-1]
            _safe_audit(
                candle_time=str(last["time"]) if "time" in raw.columns else "NOT_EVALUATED",
                candle_fingerprint=candle_fingerprint(
                    {k: last[k] for k in ("time", "open", "high", "low", "close") if k in raw.columns}
                ),
            )
        except Exception:
            logger.exception("decision audit candle stamp failed (ignored)")
        try:
            _persist_v2_shadow_market_m5(symbol, raw)
        except Exception:
            logger.exception("[V2 SHADOW] market persist failed (ignored)")
        price = float(raw["close"].iloc[-1])
        record_mid(symbol, price)

    try:
        pos = get_position(symbol)
        if pos is None:
            from forex_bot.position_recovery import symbol_has_quarantined_exposure

            if symbol_has_quarantined_exposure(symbol):
                log_decision_skip(symbol=symbol, reason="quarantined_exposure", stage="position")
                logger.info("%s: quarantined exposure — new entry withheld", symbol)
                return
    except CycleIntegrityError:
        raise
    except Exception:
        logger.exception("%s: position state unavailable", symbol)
        log_decision_skip(symbol=symbol, reason=MANAGEMENT_UNAVAILABLE, stage="position")
        log_decision_skip(
            symbol=symbol,
            reason=INSTRUMENT_CYCLE_FAILED,
            stage="position",
            detail="position_state_unavailable",
        )
        return
    if raw is None and pos is not None:
        log_decision_skip(symbol=symbol, reason=MANAGEMENT_CONTINUED_WITHOUT_CANDLES, stage="position")
    if raw is None and pos is None:
        _skip_new_entry_without_candles(symbol, candle_audit or NO_OHLCV)
        return
    weekend_flat = flatten_for_weekend()
    # Session / weekend-flatten gates block *new entries* only — always manage open risk first.
    if pos is None and (not in_active_session(symbol) or weekend_flat):
        if weekend_flat:
            logger.info("%s: skip new open — weekend flatten window (before Friday FX close)", symbol)
            log_decision_skip(symbol=symbol, reason=WEEKEND_FLATTEN, stage="session")
        else:
            alert(f"{symbol}: Market closed, skipping trade")
            log_decision_skip(symbol=symbol, reason=MARKET_SESSION_CLOSED, stage="session")
        return

    if pos:
        if (getattr(pos, "execution_kind", "") or "").strip().lower() == "live":
            from forex_bot.startup_recovery import live_management_permitted

            if not live_management_permitted():
                log_decision_skip(symbol=symbol, reason="recovery_incomplete", stage="position")
                logger.info("%s: live management withheld until startup recovery completes", symbol)
                return
        if not position_management_permitted(pos):
            log_decision_skip(symbol=symbol, reason="observation_only_position", stage="position")
            logger.info(
                "%s: observation-only position — management close and local delete withheld",
                symbol,
            )
            return
        if is_broker_backed(pos):
            try:
                from forex_bot.broker_protection import record_management_protection_evidence

                record_management_protection_evidence(pos)
            except Exception:
                logger.exception("%s: broker protection evidence withheld", symbol)
        log_decision_skip(symbol=symbol, reason=POSITION_ALREADY_OPEN, stage="position")
        from forex_bot.live_manage import (
            PRICE_SOURCE_PAPER_CANDLE,
            broker_sl_tp_hit,
            format_close_decision_line,
            format_manage_price_line,
            resolve_broker_manage_price,
        )

        m5_close = price
        m5_time = _m5_bar_time(raw) if raw is not None else ""
        quote = None
        quote_diag = None
        if is_broker_backed(pos):
            try:
                snap = pricing_snapshot()
            except CycleIntegrityError:
                raise
            except Exception:
                logger.exception("%s: management quote lookup failed", symbol)
                snap = {}
            quote = snap.get(pos.symbol) or snap.get(symbol) if isinstance(snap, dict) else None
            quote, quote_diag = _screen_manage_quote(symbol, quote)
            if quote_diag == MANAGEMENT_QUOTE_STALE:
                log_decision_skip(symbol=symbol, reason=MANAGEMENT_QUOTE_STALE, stage="position")
            elif quote_diag == MANAGEMENT_QUOTE_UNAVAILABLE:
                log_decision_skip(symbol=symbol, reason=MANAGEMENT_QUOTE_UNAVAILABLE, stage="position")
            manage_price, price_source = resolve_broker_manage_price(quote, pos.direction)
        else:
            manage_price = m5_close
            price_source = PRICE_SOURCE_PAPER_CANDLE
            if manage_price is None:
                log_decision_skip(symbol=symbol, reason=MANAGEMENT_QUOTE_UNAVAILABLE, stage="position")

        log_px = manage_price if manage_price is not None else m5_close
        if _position_log_enabled() and log_px is not None:
            _log_open_position_line(symbol, pos, float(log_px))

        current_pips = None
        if manage_price is not None:
            current_pips = unrealized_profit_pips(
                pos.symbol, pos.direction, pos.entry_price, manage_price
            )
            if is_broker_backed(pos):
                seed_position_mfe(
                    pos, manage_price, raw, include_partial_entry_bar=False
                )
                if raw is not None:
                    raise_mfe_from_post_entry_ohlcv(pos, raw)
            else:
                seed_position_mfe(pos, manage_price, raw)
            pp = apply_profit_protection(pos, manage_price, ohlcv=raw)
            if (getattr(pos, "execution_kind", "") or "").strip().lower() == "live":
                from forex_bot.close_journal import account_binding
                from forex_bot.position_recovery import persist_protection_progress

                binding = account_binding((Config.OANDA_ACCOUNT_ID or "").strip())
                try:
                    durable = persist_protection_progress(pos, binding)
                except Exception:
                    durable = False
                if not durable:
                    pos.recovery_quarantine = True
                    log_decision_skip(symbol=symbol, reason="protection_state_not_durable", stage="position")
                    return
        else:
            pp = ProtectionDecision(
                enabled=True,
                current_pips=0.0,
                max_profit_pips=float(getattr(pos, "max_profit_pips", 0.0) or 0.0),
                active=bool(getattr(pos, "profit_protection_active", False)),
                exit_threshold_pips=getattr(pos, "profit_protection_exit_pips", None),
                should_close=False,
                just_activated=False,
                just_ratcheted=False,
            )

        if is_broker_backed(pos):
            logger.info(
                format_manage_price_line(
                    symbol=symbol,
                    broker_id=str(getattr(pos, "broker_order_id", "") or ""),
                    side=pos.direction,
                    source=price_source,
                    current_price=manage_price,
                    closeout_bid=getattr(quote, "closeout_bid", None) if quote else None,
                    closeout_ask=getattr(quote, "closeout_ask", None) if quote else None,
                    m5_close=m5_close,
                    m5_time=m5_time,
                    fill=float(pos.entry_price),
                    fill_time=str(pos.open_time),
                    current_pips=current_pips,
                    mfe_pips=float(getattr(pos, "max_profit_pips", 0.0) or 0.0),
                    tp_progress=_tp_progress(pos),
                )
            )

        sl_tp_hit = False
        if is_broker_backed(pos):
            sl_tp_hit = broker_sl_tp_hit(pos)
        elif manage_price is not None:
            if pos.direction == "BUY":
                sl_tp_hit = manage_price <= pos.stop_loss or manage_price >= pos.take_profit
            else:
                sl_tp_hit = manage_price >= pos.stop_loss or manage_price <= pos.take_profit
        protect_hit = bool(pp.should_close)
        if is_broker_backed(pos) and manage_price is None:
            protect_hit = False
        if manage_price is not None:
            price = float(manage_price)
        if protect_hit and not protection_close_allowed(pos):
            logger.warning(
                "%s: profit-protection close deferred — previous close attempt still cooling down",
                symbol,
            )
            protect_hit = False
        close_hit = sl_tp_hit

        if weekend_flat and not close_hit and not protect_hit:
            alert(f"{symbol}: Weekend flatten — closing before Friday FX close (avoid weekend gap)")

        if close_hit or weekend_flat or protect_hit:
            if _position_close_identity(pos) is None:
                logger.error(
                    "%s: protective close withheld — position side or size is uncertain",
                    symbol,
                )
                log_decision_skip(
                    symbol=symbol,
                    reason=PROTECTIVE_CLOSE_FAILED,
                    stage="position",
                    detail="uncertain_position",
                )
                return
            mh = _min_position_hold_sec()
            if (
                close_hit
                and not weekend_flat
                and not protect_hit
                and mh > 0
                and (time.time() - float(pos.open_time)) < mh
            ):
                logger.debug(
                    "%s: SL/TP touched but min hold %.0fs not met (age=%.1fs)",
                    symbol,
                    mh,
                    time.time() - float(pos.open_time),
                )
                _audit_reject("POSITION_MIN_HOLD", stage="position")
                return
            fill_path = close_fill_path(symbol, pos.execution_kind)
            if fill_path == "abort_broker_disabled":
                if protect_hit:
                    mark_protection_close_attempt(pos)
                alert(
                    f"{symbol}: Skip close — live position requires a broker fill but "
                    f"EXECUTION_MODE/USE_OANDA_LIVE is not sending orders (fail closed)"
                )
                logger.error("%s: live close aborted — broker orders disabled", symbol)
                _audit_reject("CLOSE_BROKER_DISABLED", stage="position")
                return

            spr_c: float | None
            slp_c: float | None
            impact_amt: float
            exit_price_exec: float | None
            lat_ms: int

            if fill_path == "simulate":
                if raw is None or price is None:
                    logger.error(
                        "%s: paper close not priced — decision candles unavailable",
                        symbol,
                    )
                    log_decision_skip(
                        symbol=symbol,
                        reason=MANAGEMENT_QUOTE_UNAVAILABLE,
                        stage="position",
                    )
                    _audit_reject("CLOSE_UNPRICED", stage="position")
                    return
                # SIMULATION CONTROL START
                lat_ms = await apply_latency()
                route_lb = _env_int("HYBRID_ROUTE_LOOKBACK", 60)
                df_px = compute_indicators(raw, lookback=route_lb)
                atr_v = float(df_px["atr"].iloc[-1])
                if math.isnan(atr_v) or atr_v <= 0:
                    atr_v = 0.0001
                strat_style = strategy_execution_style(pos.strategy_name)
                exit_leg = "SELL" if pos.direction == "BUY" else "BUY"
                mid_impact, impact_amt = apply_market_impact(pos.units, price, exit_leg)
                exit_price_exec, spr_c, slp_c = apply_execution_costs(
                    symbol, exit_leg, mid_impact, atr_v, strat_style
                )
                pnl = calculate_pnl(pos, exit_price_exec)
                alert(
                    f"[EXECUTION] {symbol} close latency={lat_ms}ms impact={impact_amt:.6f} "
                    f"spread={spr_c:.5f} slippage={slp_c:.5f}"
                )
                # SIMULATION CONTROL END
            else:
                lat_ms = 0
                spr_c, slp_c = None, None
                impact_amt = 0.0
                if price is None:
                    if fill_path != "broker":
                        logger.error(
                            "%s: protective close not priced — management price unavailable",
                            symbol,
                        )
                        log_decision_skip(
                            symbol=symbol,
                            reason=MANAGEMENT_QUOTE_UNAVAILABLE,
                            stage="position",
                        )
                        _audit_reject("CLOSE_UNPRICED", stage="position")
                        return
                    exit_price_exec = None
                    pnl = 0.0
                    alert(
                        f"[EXECUTION] BROKER_CLOSE {symbol} source={price_source} (PositionClose)"
                    )
                else:
                    exit_price_exec = float(price)
                    pnl = calculate_pnl(pos, exit_price_exec)
                    if fill_path == "broker":
                        alert(
                            f"[EXECUTION] BROKER_CLOSE {symbol} current={float(price):.5f} "
                            f"source={price_source} (PositionClose)"
                        )
                    else:
                        alert(
                            f"[EXECUTION] MID {symbol} close mid={float(price):.5f} "
                            f"(paper/window_paper; no broker order)"
                        )

            if protect_hit:
                mark_protection_close_attempt(pos)
            close_reason = "sl_tp" if sl_tp_hit else (
                "weekend_flatten" if weekend_flat and not protect_hit else (
                    "profit_protection" if protect_hit else "close"
                )
            )
            trigger = (
                "sl_tp_hit" if sl_tp_hit else (
                    "weekend_flat" if weekend_flat and not protect_hit else (
                        "protect_hit" if protect_hit else "close"
                    )
                )
            )
            logger.info(
                format_close_decision_line(
                    symbol=symbol,
                    broker_id=str(getattr(pos, "broker_order_id", "") or ""),
                    reason=close_reason,
                    entry=float(pos.entry_price),
                    current_price=None if price is None else float(price),
                    price_source=price_source if pos else PRICE_SOURCE_PAPER_CANDLE,
                    sl=float(pos.stop_loss),
                    tp=float(pos.take_profit),
                    mfe_pips=float(getattr(pos, "max_profit_pips", 0.0) or 0.0),
                    tp_progress=_tp_progress(pos),
                    protected_exit_pips=getattr(pos, "profit_protection_exit_pips", None),
                    trigger=trigger,
                    sl_tp_hit=sl_tp_hit,
                    weekend_flat=weekend_flat,
                    protect_hit=protect_hit,
                    current_side=pos.direction,
                )
            )
            diagnostics = None
            try:
                from forex_bot.trade_diagnostics import snapshot_from_position

                diagnostics = snapshot_from_position(
                    pos, exit_reason=close_reason, exit_price=exit_price_exec
                )
            except Exception:
                logger.exception("%s: trade diagnostics snapshot failed (ignored)", symbol)
            _audit_close(outcome="CLOSE_INTENT", trigger=close_reason, evidence="NOT_EVALUATED")
            _audit_close(outcome="CLOSE_SUBMISSION_ATTEMPTED", trigger=close_reason, evidence="NOT_EVALUATED")
            if (getattr(pos, "execution_kind", "") or "").strip().lower() == "live":
                from forex_bot.broker_close_evidence import (
                    CLOSE_FULLY_CONFIRMED,
                    run_guarded_live_close,
                )

                operation = await run_guarded_live_close(pos, reason=close_reason)
                if operation.confirmation_state != CLOSE_FULLY_CONFIRMED:
                    _audit_close(
                        outcome="CLOSE_UNCONFIRMED",
                        trigger=close_reason,
                        evidence=operation.confirmation_state,
                    )
                    return
                if operation.realized_pnl is not None:
                    pnl = float(operation.realized_pnl)
                from forex_bot.positions import close_confirmed_live_position

                removed = close_confirmed_live_position(symbol, operation)
            else:
                try:
                    pnl = await execute_trade(
                        pos.symbol,
                        pos.strategy_name,
                        pos.direction,
                        pos.units,
                        pos.entry_price,
                        pos.stop_loss,
                        pos.take_profit,
                        realized_pnl=pnl,
                        execution_kind=pos.execution_kind,
                        exit_price=exit_price_exec,
                        spread_component=spr_c,
                        slippage_component=slp_c,
                        diagnostics=diagnostics,
                    )
                except Exception as exc:
                    close_diag = _close_exception_reason(exc)
                    logger.exception("%s: close execution/logging failed (%s)", symbol, close_diag)
                    log_decision_skip(symbol=symbol, reason=close_diag, stage="position")
                    _audit_reject("CLOSE_FAILED", stage="position")
                    _audit_close(
                        outcome="CLOSE_UNCONFIRMED" if close_diag == PROTECTIVE_CLOSE_UNCONFIRMED else "CLOSE_FAILED",
                        trigger=close_reason,
                        evidence="execute_trade_exception",
                    )
                    return
                removed = close_position(symbol)
            if removed is None:
                _audit_close(
                    outcome="CLOSE_UNCONFIRMED",
                    trigger=close_reason,
                    evidence="local_delete_refused",
                )
                return
            if fill_path == "broker":
                _audit_close(
                    outcome="CLOSE_ACKNOWLEDGED",
                    trigger=close_reason,
                    evidence="close_units_confirmed",
                )
            else:
                _audit_close(outcome="CLOSE_EXECUTED", trigger=close_reason, evidence="local_fill")
            rl_agent.update(pos.rl_state, pos.direction, pnl)
            try:
                from forex_bot.decision_repair.flags import rl_persist_enabled
                from forex_bot.decision_repair.rl_store import RLStore, research_path

                if rl_persist_enabled():
                    RLStore(research_path()).save(
                        rl_agent.q,
                        alpha=rl_agent.alpha,
                        epsilon=rl_agent.epsilon,
                        mode="training",
                    )
            except Exception:
                logger.exception("RL persist failed (ignored; live gate unchanged)")
            logger.info(
                "[CLOSE] %s | Dir=%s | Units=%.4f | PnL=%.5f | entry=%.5f exit=%.5f | "
                "state=%s | reason=%s",
                symbol,
                pos.direction,
                pos.units,
                pnl,
                pos.entry_price,
                exit_price_exec if exit_price_exec is not None else float("nan"),
                pos.rl_state,
                close_reason,
            )
        return

    decision = dispatch_production_iteration(
        symbol,
        _production_iteration_dependencies(symbol, raw, price),
    )
    if decision.get("status") != "continue_existing_production_broker":
        blocked_by = str(decision.get("blocked_by") or "shared_entry_blocked")
        logger.warning("%s: new entry blocked by shared decision — %s", symbol, blocked_by)
        log_decision_skip(
            symbol=symbol,
            reason=RECONCILE_OR_PRETRADE_BLOCKED,
            stage="shared_entry",
            detail=blocked_by,
        )
        return

    from forex_bot.database import exposure_entry_block_reason

    exposure_block = exposure_entry_block_reason(symbol)
    if exposure_block:
        logger.warning("%s: new entry blocked — %s", symbol, exposure_block)
        log_decision_skip(
            symbol=symbol,
            reason=RECONCILE_OR_PRETRADE_BLOCKED,
            stage="exposure",
            detail=exposure_block,
        )
        return

    if raw is None or price is None:
        _skip_new_entry_without_candles(symbol, candle_audit or NO_OHLCV)
        return

    from forex_bot.broker_exit import broker_exit_open_blocked_reason

    pending_exit = broker_exit_open_blocked_reason(symbol)
    if pending_exit:
        logger.warning("%s: new entry blocked — %s", symbol, pending_exit)
        log_decision_skip(
            symbol=symbol, reason=RECONCILE_OR_PRETRADE_BLOCKED, stage="pretrade", detail=pending_exit
        )
        return

    blocked = pre_trade_entry_blocked_reason()
    if blocked:
        logger.warning("%s: new entry blocked — %s", symbol, blocked)
        skip_code = (
            LIVE_ORDER_AUTH_BLOCKED
            if str(blocked).startswith("live_order_auth")
            else RECONCILE_OR_PRETRADE_BLOCKED
        )
        log_decision_skip(symbol=symbol, reason=skip_code, stage="pretrade", detail=blocked)
        return

    route_lookback = _env_int("HYBRID_ROUTE_LOOKBACK", 60)
    df_route = compute_indicators(raw, lookback=route_lookback)

    strategy_name, lookback, horizon = select_strategy(symbol, df_route)
    try:
        from forex_bot.decision_repair.flags import deterministic_select_enabled
        from forex_bot.decision_repair.selection import last_selection

        sel = last_selection() if deterministic_select_enabled() else None
    except Exception:
        sel = None
    _safe_audit(
        symbol=symbol,
        selected_strategy=strategy_name,
        selection_policy_version=(
            sel.policy_version
            if sel is not None
            else (
                "deterministic_v1_unvalidated"
                if (os.getenv("DECISION_REPAIR_DETERMINISTIC_SELECT") or "").strip()
                else "legacy_random"
            )
        ),
        candidates=[c.name for c in sel.candidates] if sel is not None else "NOT_EVALUATED",
        candidate_eligibility=(
            [
                {
                    "name": c.name,
                    "eligible": c.eligible,
                    "active": c.active,
                    "reason": c.reject_reason,
                }
                for c in sel.candidates
            ]
            if sel is not None
            else "NOT_EVALUATED"
        ),
        strategy_activation_state=(
            "active"
            if strategy_name
            and strategies.get(strategy_name) is not None
            and strategies[strategy_name].active
            else "inactive"
        ),
        final_decision="pending",
    )
    from forex_bot.live_safety import live_safety_initialised

    known_strategy = bool(strategy_name) and strategy_name in strategies
    strat = strategies[strategy_name] if known_strategy else None
    strategy_block = strategy_entry_block_reason(
        strategy_name,
        active=bool(strat.active) if strat is not None else False,
        authorised_for_live=bool(getattr(strat, "authorised_for_live", False)) if strat is not None else False,
        safety_initialised=live_safety_initialised(),
        known_strategy=known_strategy,
    )
    if continue_entry_after_strategy_gate(
        strategy_name,
        active=bool(strat.active) if strat is not None else False,
        authorised_for_live=bool(getattr(strat, "authorised_for_live", False)) if strat is not None else False,
        safety_initialised=live_safety_initialised(),
        known_strategy=known_strategy,
        sizer=None,
        builder=None,
        sender=None,
        id_factory=None,
    ) is None:
        if strategy_block == "NO_STRATEGY_SELECTED":
            log_strategy_pre_sizing_skip(
                symbol=symbol,
                reason=NO_STRATEGY_SELECTED,
                selected=None,
                lookback=lookback,
                horizon=horizon,
            )
        elif strategy_block == "UNKNOWN_STRATEGY":
            log_strategy_pre_sizing_skip(
                symbol=symbol,
                reason="UNKNOWN_STRATEGY",
                selected=strategy_name,
                lookback=lookback,
                horizon=horizon,
            )
        elif strategy_block == "STRATEGY_INACTIVE":
            log_strategy_pre_sizing_skip(
                symbol=symbol,
                reason=STRATEGY_INACTIVE,
                selected=strategy_name,
                lookback=lookback,
                horizon=horizon,
            )
        else:
            log_strategy_pre_sizing_skip(
                symbol=symbol,
                reason=STRATEGY_NOT_AUTHORISED,
                selected=strategy_name,
                lookback=lookback,
                horizon=horizon,
            )
        return

    try:
        df = compute_indicators(raw, lookback=lookback)
    except Exception:
        logger.exception("%s: indicator calculation failed", symbol)
        log_decision_skip(symbol=symbol, reason=STALE_OR_INVALID_DATA, stage="quant")
        _audit_reject("INDICATOR_CALCULATION_FAILURE", stage="quant")
        return
    if df is None or getattr(df, "empty", True):
        log_decision_skip(symbol=symbol, reason=STALE_OR_INVALID_DATA, stage="quant")
        _audit_reject("INDICATOR_CALCULATION_FAILURE", stage="quant")
        return
    if not volatility_ok(df):
        alert(f"{symbol}: Volatility outside safe range, skipping trade")
        log_decision_skip(symbol=symbol, reason=VOLATILITY_UNSAFE, stage="quant")
        return

    price = float(df["close"].iloc[-1])
    seq_model.update(symbol, price)
    seq_pred = seq_model.predict(symbol)
    nn_pred = compute_nn_pred(price, seq_pred)

    ma_fast = float(df["ma_fast"].iloc[-1])
    ma_slow = float(df["ma_slow"].iloc[-1])
    atr_v = float(df["atr"].iloc[-1])
    ret_1 = float(df["close"].pct_change().iloc[-1]) if len(df) > 1 else 0.0

    ai_decision = await ai.vote(
        {
            "symbol": symbol,
            "strategy": strategy_name,
            "price": price,
            "nn_pred": nn_pred,
            "seq_pred": seq_pred,
            "horizon": horizon,
            "lookback": lookback,
            "hybrid": horizon != "legacy",
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "sma_fast": ma_fast,
            "sma_slow": ma_slow,
            "returns": ret_1,
            "atr": atr_v,
            "timeframe": "M5",
            "m5_bar_time": _m5_bar_time(raw),
        },
        symbol,
    )
    if not isinstance(ai_decision, dict) or "allow" not in ai_decision:
        log_decision_skip(
            symbol=symbol,
            reason=QUANT_AI_REJECTED,
            stage="quant_ai",
            strategy=strategy_name,
        )
        _safe_audit(ai_vote="UNAVAILABLE", ai_model_id="UNAVAILABLE")
        return
    _safe_audit(
        ai_vote=ai_decision.get("direction") or "UNAVAILABLE",
        ai_confidence=ai_decision.get("confidence"),
        ai_model_id=str(ai_decision.get("model") or "ensemble"),
    )
    if not ai_decision["allow"]:
        log_decision_skip(
            symbol=symbol,
            reason=QUANT_AI_REJECTED,
            stage="quant_ai",
            strategy=strategy_name,
        )
        return

    direction = direction_action_gate(ai_decision.get("direction"), None, None, None)
    if direction is None:
        log_decision_skip(
            symbol=symbol,
            reason="INVALID_ENTRY_DIRECTION",
            stage="direction",
            strategy=strategy_name,
        )
        return

    trend_v = float(df["trend"].iloc[-1])
    vol_v = float(df["volatility"].iloc[-1])
    if math.isnan(trend_v):
        trend_v = 0.0
    if math.isnan(vol_v):
        vol_v = 0.0
    state = f"{round(trend_v, 4)}_{round(vol_v, 6)}"

    # RL is a gate: SKIP blocks; BUY/SELL must agree with AI (never override AI side).
    rl_action = rl_agent.decide(state)
    _safe_audit(
        rl_action=rl_action,
        rl_state_fingerprint=state,
        rl_model_id="tabular_q_v1",
    )
    if rl_action == "UNAVAILABLE":
        logger.info("%s: RL state unavailable — blocking decision", symbol)
        log_decision_skip(symbol=symbol, reason=RL_STATE_UNAVAILABLE, stage="rl", state=state)
        _safe_audit(
            symbol=symbol,
            selected_strategy=strategy_name,
            rl_action="UNAVAILABLE",
            final_decision="reject",
            rejection_reasons=[RL_STATE_UNAVAILABLE],
        )
        return
    try:
        _observe_v2_shadow_candidate(
            symbol=symbol,
            strategy_name=strategy_name,
            direction=direction,
            price=price,
            df=df,
            atr_v=atr_v,
            ma_fast=ma_fast,
            ma_slow=ma_slow,
            ret_1=ret_1,
            rl_action=rl_action,
            rl_state=state,
        )
    except Exception:
        logger.exception("[V2 SHADOW] observe failed (ignored)")
    if rl_action == "SKIP":
        logger.info("%s: RL decided to skip trade (state=%s)", symbol, state)
        log_decision_skip(symbol=symbol, reason=RL_SKIP, stage="rl", state=state)
        return
    if rl_action in ("BUY", "SELL") and rl_action != direction:
        logger.info(
            "%s: RL gate blocked (rl=%s ai=%s state=%s)",
            symbol,
            rl_action,
            direction,
            state,
        )
        log_decision_skip(
            symbol=symbol,
            reason=RL_DIRECTION_MISMATCH,
            stage="rl",
            rl=rl_action,
            ai=direction,
        )
        return
    confidence = float(ai_decision.get("confidence", 0.6))

    weight = portfolio.get_weight(symbol)
    atr_v = float(df["atr"].iloc[-1])
    if math.isnan(atr_v) or atr_v <= 0:
        atr_v = 0.0001
    strat_style = strategy_execution_style(strategy_name)
    sl_d, tp_d = sl_tp_distance_for_entry(symbol, atr_v)
    stop_mid = price - sl_d if direction == "BUY" else price + sl_d

    balance = current_equity()
    units = position_sizing(symbol, price, stop_mid, balance)
    if notional_pct_of_nav() <= 0:
        units *= weight * confidence
    units = cap_position_units(units)
    if notional_pct_of_nav() > 0:
        units = math.floor(float(units) + 1e-9)
        if units < 1:
            logger.info(
                "%s: skip — per-trade notional size rounds below 1 OANDA unit (NAV=%.2f)",
                symbol,
                balance,
            )
            log_decision_skip(symbol=symbol, reason=SIZING_BELOW_MIN, stage="sizing")
            return
        logger.info(
            "[SIZE] %s units=%.0f notional≈%.2f USD (per-trade %.2f%% of NAV %.2f; "
            "portfolio cap %.2f%% ≈ %.2f USD)",
            symbol,
            units,
            approx_gross_usd_notional_for(symbol, float(units), float(price)),
            notional_pct_of_nav() * 100.0,
            balance,
            portfolio_gross_notional_pct_of_nav() * 100.0,
            configured_max_gross_usd(),
        )

    # MICRO_STRATEGY / LOT_SIZE HOOK START (optional — uncomment and implement)
    # sym_u = symbol.upper().replace("-", "_")
    # _lot = (os.getenv(f"LOT_SIZE_OVERRIDE_{sym_u}") or "").strip()
    # if _lot:
    #     units = max(1.0, float(_lot))
    # _micro = (os.getenv(f"MICRO_STRATEGY_{sym_u}") or "").strip()
    # if _micro:
    #     pass  # e.g. scale units or gate entries by label (scalp_1h, etc.)
    # MICRO_STRATEGY / LOT_SIZE HOOK END

    if units < 1e-6:
        log_decision_skip(symbol=symbol, reason=SIZING_BELOW_MIN, stage="sizing")
        return

    if pre_close_adjustment(symbol):
        alert(f"{symbol}: Near session close, reducing position size by 50%")
        units *= 0.5
        if units < 1.0:
            _audit_reject(SIZING_BELOW_MIN, stage="sizing")
            return

    alert(
        f"[HYBRID] {symbol} | horizon={horizon} | lookback={lookback} | "
        f"strategy={strategy_name} | route_lb={route_lookback}"
    )

    # live_allowed = is_live_trading(symbol, use_scalp_window=True)
    # LIVE WINDOW CHECK START
    live_allowed = is_live_trading(symbol)
    paper = effective_paper_trading()
    fill_path = open_fill_path(symbol)
    if fill_path == "abort_broker_disabled":
        alert(
            f"{symbol}: Skip open — inside live window but broker orders are disabled "
            f"(set EXECUTION_MODE=live_broker or paper_broker; fail closed, no local live fill)"
        )
        logger.error("%s: live open aborted — broker orders disabled", symbol)
        _audit_reject("BROKER_ORDERS_DISABLED", stage="pretrade")
        return
    use_live_fill = fill_path == "broker"
    if use_live_fill:
        exec_kind = "live"
    else:
        exec_kind = "simulated" if paper else "window_paper"

    if is_paper_like_kind(exec_kind):
        from forex_bot.reconciliation import paper_open_blocked_reason

        skip_why = paper_open_blocked_reason(symbol)
        if skip_why:
            logger.warning("[PAPER SKIP] %s | %s", symbol, skip_why)
            _audit_reject("PAPER_OPEN_BLOCKED", stage="pretrade")
            return

    use_sim_layers = fill_path == "simulate"
    if live_window_log_enabled():
        win = symbol_live_window_status(symbol)
        logger.info(
            "[LIVE WINDOW] %s %s → exec=%s | local=%s %s | utc=%s | now_local=%s | now_utc=%s | "
            "tz=%s offset=%s | paper=%s",
            symbol,
            "IN" if live_allowed else "OUT",
            exec_kind,
            win["local_window"],
            win["dst_label"],
            win["utc_window"],
            win["now_local"],
            win["now_utc"],
            win["timezone"],
            win["utc_offset"],
            paper,
        )
    # QUOTA: future per-symbol daily caps should run only when use_sim_layers is True
    # LIVE WINDOW CHECK END

    if not use_live_fill and not paper:
        win = symbol_live_window_status(symbol)
        alert(
            f"{symbol}: Outside live window — local {win['local_window']} {win['dst_label']} "
            f"(UTC {win['utc_window']}); now {win['now_local']} {win['dst_label']} / "
            f"{win['now_utc']} UTC — paper-style fills until the window opens "
            f"(hybrid/AI/RL unchanged)"
        )

    approx_add = approx_gross_usd_notional_for(symbol, float(units), float(price))
    cap_decision = notional_cap_decision(approx_add)
    from forex_bot.oanda_client import last_account_summary

    acct = last_account_summary()
    ccy = str(acct.get("currency") or "")
    nav = acct.get("NAV")
    if cap_decision["exceeds"]:
        msg = format_notional_cap_skip_alert(
            symbol, cap_decision, nav=nav, currency=ccy, direction=direction
        )
        alert(msg)
        logger.warning("%s", msg)
        _audit_reject("NOTIONAL_CAP", stage="risk")
        return
    logger.info(
        "%s",
        format_notional_cap_report(
            symbol, cap_decision, nav=nav, currency=ccy, allowed=True, direction=direction
        ),
    )

    # Stop risk in account currency (handles USD_* quote conversion).
    new_risk_at_stop = stop_risk_account_ccy(symbol, float(price), float(sl_d), float(units))
    if portfolio_risk_cap_exceeded(current_equity(), new_risk_at_stop):
        eq = current_equity()
        open_risk = portfolio_risk_amount()
        projected = open_risk + float(new_risk_at_stop)
        cap_pct = configured_max_portfolio_risk_pct()
        cap_amt = max(0.0, float(eq)) * cap_pct
        alert(
            f"{symbol}: Skip open — portfolio stop risk cap\n"
            f"Candidate symbol: {symbol}\n"
            f"Candidate side: {direction}\n"
            f"Current stop-risk exposure: {open_risk:.2f}\n"
            f"Projected stop-risk exposure: {projected:.2f}\n"
            f"Configured cap: {cap_amt:.2f} ({cap_pct * 100:.2f}% of equity {eq:.2f})\n"
            f"Rejection reason: projected stop risk exceeds MAX_PORTFOLIO_RISK_PCT"
        )
        _audit_reject("PORTFOLIO_RISK_CAP", stage="risk")
        return

    usd_dir_decision = usd_direction_guard_decision(symbol, direction)
    if usd_dir_decision["exceeds"]:
        msg = format_usd_direction_skip(usd_dir_decision)
        alert(msg)
        logger.warning("%s", msg)
        _audit_reject("USD_DIRECTION_GUARD", stage="risk")
        return

    entry_price: float
    spread_amt: float
    slip_amt: float
    position_units: float = float(units)

    broker_oid = ""
    client_order_id = ""
    fill_ts: float | None = None
    if fill_path == "broker":
        from forex_bot.market_provenance import decision_frame_rejection

        frame_reason = decision_frame_rejection(raw, symbol)
        if frame_reason:
            logger.warning("%s: refuse broker open — market provenance %s", symbol, frame_reason)
            log_decision_skip(
                symbol=symbol,
                reason=STALE_OR_INVALID_DATA,
                stage="provenance",
                detail=frame_reason,
            )
            return
        if is_paper_like_kind(exec_kind):
            logger.error(
                "%s: refuse broker open — fill_path=broker but exec_kind=%s",
                symbol,
                exec_kind,
            )
            _audit_reject("BROKER_KIND_MISMATCH", stage="broker")
            return
        unresolved_block = broker_entry_block_reason(symbol)
        if unresolved_block:
            logger.warning("%s: new broker order blocked (%s)", symbol, unresolved_block)
            _audit_reject("UNRESOLVED_BROKER_INTENT", stage="broker")
            return
        client_order_id = generate_client_order_id()
        t_reserve = time.perf_counter()
        if not try_begin_order_submission(
            client_order_id=client_order_id,
            symbol=symbol,
            direction=direction,
            units=float(units),
            metadata={"mid": float(price), "strategy": strategy_name},
        ):
            logger.warning("%s: idempotent skip — duplicate client_order_id or DB conflict", symbol)
            _audit_reject("IDEMPOTENT_SKIP", stage="broker")
            return
        t_sent = time.perf_counter()
        # Live/paper_broker: attach SL/TP to a fresh executable bid/ask, not M5 mid.
        # Cycle snapshot is stale; dedicated PricingInfo GET immediately before OrderCreate.
        if not live_broker_geometry_required(fill_path):
            mark_order_failed_or_cancelled(client_order_id)
            logger.error("%s: refuse broker open — fill_path=%s is not broker", symbol, fill_path)
            _audit_reject("FILL_PATH_NOT_BROKER", stage="broker")
            return
        fetched = fetch_entry_pricing(symbol)
        if fetched.skip_reason is not None:
            mark_order_failed_or_cancelled(client_order_id)
            msg = format_entry_geometry_skip(symbol, direction, fetched.skip_reason)
            logger.warning("%s", msg)
            alert(msg)
            log_decision_skip(
                symbol=symbol,
                reason=STALE_OR_INVALID_DATA,
                stage="entry_geometry",
                detail=fetched.skip_reason,
            )
            return
        geom, skip_reason = resolve_live_entry_geometry(
            symbol,
            direction,
            float(sl_d),
            float(tp_d),
            float(price),
            quote=fetched.quote,
            atr=atr_v,
            request_duration_ms=fetched.request_duration_ms,
            fetch_age_ms=fetched.fetch_age_ms(),
        )
        if skip_reason is not None:
            mark_order_failed_or_cancelled(client_order_id)
            msg = format_entry_geometry_skip(
                symbol, direction, skip_reason or "unknown", geom=geom
            )
            logger.warning("%s", msg)
            alert(msg)
            log_decision_skip(
                symbol=symbol,
                reason=STALE_OR_INVALID_DATA,
                stage="entry_geometry",
                detail=skip_reason,
            )
            return
        if geom is None:
            mark_order_failed_or_cancelled(client_order_id)
            msg = format_entry_geometry_skip(symbol, direction, "unknown")
            logger.warning("%s", msg)
            alert(msg)
            log_decision_skip(symbol=symbol, reason=STALE_OR_INVALID_DATA, stage="entry_geometry")
            return
        logger.info("%s", format_entry_geometry_line(geom))
        broker_sl = float(geom.sl)
        broker_tp = float(geom.tp)
        if not _permit_new_exposure_or_block():
            mark_order_failed_or_cancelled(client_order_id)
            logger.error("%s: new exposure blocked — required audit write failed", symbol)
            _audit_reject("AUDIT_WRITE_FAILED", stage="audit")
            return
        _safe_audit(
            client_order_id=client_order_id,
            order_intent_id=client_order_id,
            submission_status="attempted",
            path="new_entry",
        )
        import forex_bot.oanda_exec as oanda_exec

        try:
            logger.error("%s: legacy broker tail is not a dispatch path", symbol)
            return
        except oanda_exec.OrderCreateCancelled as exc:
            record_fill_failure()
            from forex_bot.database import release_resolved_intent

            release_resolved_intent(symbol)
            mark_order_failed_or_cancelled(client_order_id)
            logger.warning("%s", exc)
            _audit_reject("BROKER_SUBMISSION_CANCELLED", stage="broker")
            _safe_audit(order_submitted=True, broker_ack=False, submission_status="cancelled")
            return
        except oanda_exec.OrderCreateRejected as exc:
            record_fill_failure()
            from forex_bot.database import release_resolved_intent

            release_resolved_intent(symbol)
            mark_order_failed_or_cancelled(client_order_id)
            logger.warning("[ORDER REJECTED] %s open: %s", symbol, exc)
            _audit_reject("BROKER_SUBMISSION_REJECTED", stage="broker")
            _safe_audit(order_submitted=True, broker_ack=False, submission_status="rejected")
            return
        except oanda_exec.OrderCreateOutcomeError as exc:
            record_fill_failure()
            from forex_bot.database import remember_ambiguous_outcome

            remember_ambiguous_outcome(symbol, client_order_id)
            update_order(
                client_order_id,
                status=OrderStatus.UNRESOLVED,
                detail="ambiguous_broker_outcome",
            )
            logger.warning("[ORDER UNRESOLVED] %s open: %s", symbol, exc)
            _audit_reject("BROKER_OUTCOME_UNRESOLVED", stage="broker")
            _safe_audit(order_submitted=True, broker_ack=False, submission_status="unresolved")
            return
        except Exception as exc:
            record_fill_failure()
            from forex_bot.database import remember_ambiguous_outcome

            remember_ambiguous_outcome(symbol, client_order_id)
            update_order(
                client_order_id,
                status=OrderStatus.UNRESOLVED,
                detail="ambiguous_broker_outcome",
            )
            logger.warning("[ORDER UNRESOLVED] %s open: %s", symbol, exc)
            _audit_reject("BROKER_OUTCOME_UNRESOLVED", stage="broker")
            _safe_audit(order_submitted=True, broker_ack=False, submission_status="unresolved")
            return
        _safe_audit(
            order_submitted=True,
            broker_ack=True,
            submission_status="acknowledged",
            broker_request_id=str(oid or ""),
            client_order_id=client_order_id,
            final_decision="order_ack",
        )
        t_fill = time.perf_counter()
        entry_price = float(fill_price)
        spread_amt = 0.0
        slip_amt = 0.0
        impact_amt = 0.0
        st = OrderStatus.FILLED
        if float(filled_u) + 1e-6 < float(units):
            st = OrderStatus.PARTIAL
            logger.info("[ORDER PARTIAL] %s filled=%.4f requested=%.4f", symbol, filled_u, units)
        position_units = float(filled_u)
        broker_oid = str(oid) if oid else ""
        finalize_order_fill(
            client_order_id,
            broker_order_id=str(oid) if oid else "",
            fill_price=entry_price,
            units_filled=float(filled_u),
            status=st,
            metadata={
                "expected_mid": float(price),
                "executable_reference": float(geom.executable_reference),
                "submitted_sl": broker_sl,
                "submitted_tp": broker_tp,
                "slippage_signed": (entry_price - float(price))
                if direction == "BUY"
                else (float(price) - entry_price),
            },
        )
        record_fill_quality(
            expected_price=float(geom.executable_reference),
            fill_price=entry_price,
            direction=direction,
            latency_signal_to_send_ms=(t_sent - t_reserve) * 1000.0,
            latency_send_to_fill_ms=(t_fill - t_sent) * 1000.0,
        )
        logger.info(
            "%s",
            format_entry_fill_geometry_line(
                symbol=symbol,
                side=direction,
                reference=float(geom.executable_reference),
                fill=entry_price,
                sl=broker_sl,
                tp=broker_tp,
                broker_id=broker_oid,
                transaction_id=str(oid or ""),
            ),
        )
        alert(
            f"[EXECUTION] BROKER_FILL {symbol} open fill={entry_price:.5f} units≈{filled_u:.4f} id={oid} cid={client_order_id}"
        )
    elif use_sim_layers:
        if not _permit_new_exposure_or_block():
            logger.error("%s: new exposure blocked — required audit write failed", symbol)
            _audit_reject("AUDIT_WRITE_FAILED", stage="audit")
            return
        _safe_audit(submission_status="internal_open", order_submitted=False, simulated=True)
        # SIMULATION CONTROL START
        lat_ms = await apply_latency()
        mid_impact, impact_amt = apply_market_impact(units, price, direction)
        entry_price, spread_amt, slip_amt = apply_execution_costs(
            symbol, direction, mid_impact, atr_v, strat_style
        )
        alert(
            f"[EXECUTION] {symbol} open latency={lat_ms}ms impact={impact_amt:.6f} "
            f"spread={spread_amt:.5f} slippage={slip_amt:.5f}"
        )
        # SIMULATION CONTROL END
    else:
        if not _permit_new_exposure_or_block():
            logger.error("%s: new exposure blocked — required audit write failed", symbol)
            _audit_reject("AUDIT_WRITE_FAILED", stage="audit")
            return
        _safe_audit(submission_status="internal_open", order_submitted=False, simulated=True)
        entry_price = float(price)
        spread_amt = 0.0
        slip_amt = 0.0
        impact_amt = 0.0
        alert(
            f"[EXECUTION] MID {symbol} open mid={price:.5f} "
            f"(paper/window_paper; no broker order; live_allowed={live_allowed} exec_kind={exec_kind})"
        )

    if direction == "BUY":
        stop_loss = entry_price - sl_d
        take_profit = entry_price + tp_d
    else:
        stop_loss = entry_price + sl_d
        take_profit = entry_price - tp_d

    atr_entry = None
    try:
        from forex_bot.indicators import latest_atr_price
        from forex_bot.profit_protection import atr_to_pips, profit_protection_atr_period

        atr_px = latest_atr_price(raw, profit_protection_atr_period())
        if atr_px is not None:
            atr_entry = atr_to_pips(symbol, atr_px)
    except Exception:
        logger.exception("%s: ATR-at-entry snapshot failed (ignored)", symbol)
    if fill_path == "broker" and fill_ts:
        opened_at = float(fill_ts)
    else:
        opened_at = datetime.utcnow().timestamp()
    if fill_path == "broker" and float(position_units) <= 0:
        from forex_bot.database import note_unconfirmed_exposure

        note_unconfirmed_exposure(symbol, client_order_id or symbol)
        logger.warning("%s: broker fill has no position quantity — entry remains blocked", symbol)
        return
    try:
        open_position(
            Position(
                symbol=symbol,
                direction=direction,
                units=float(position_units),
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                open_time=opened_at,
                strategy_name=strategy_name,
                rl_state=state,
                execution_kind=exec_kind,
                atr_at_entry_pips=atr_entry,
                client_order_id=client_order_id,
                broker_order_id=broker_oid,
                broker_order=fill_path == "broker",
                max_profit_pips=0.0,
                profit_protection_seeded=fill_path == "broker",
            )
        )
    except Exception:
        logger.exception("%s: position record failed — entry remains blocked", symbol)
        if fill_path == "broker":
            from forex_bot.database import note_unconfirmed_exposure

            note_unconfirmed_exposure(symbol, client_order_id or symbol)
        return
    if fill_path == "broker":
        alert(
            f"[OPEN] {symbol} {direction} units={position_units:.2f} entry={entry_price:.5f} "
            f"mid={price:.5f} SL={stop_loss:.5f} TP={take_profit:.5f} kind={exec_kind} "
            f"broker_order=true cid={client_order_id} broker_id={broker_oid} "
            f"strategy={strategy_name} horizon={horizon}"
        )
    else:
        alert(
            f"[OPEN] {symbol} {direction} units={position_units:.2f} entry={entry_price:.5f} "
            f"mid={price:.5f} SL={stop_loss:.5f} TP={take_profit:.5f} kind={exec_kind} "
            f"broker_order=false strategy={strategy_name} horizon={horizon}"
        )
    logger.info(
        "[AI+RL] %s | OPEN Dir=%s | Units=%.4f | Conf=%.2f | RL_Action=%s | State=%s | %s lb=%s",
        symbol,
        direction,
        position_units,
        confidence,
        rl_action,
        state,
        horizon,
        lookback,
    )


def evolve() -> None:
    from forex_bot.decision_repair.flags import health_enabled

    if health_enabled():
        from forex_bot.decision_repair.health import record_evaluation

        record_evaluation(
            pnl_by_name={name: list(strat.pnl) for name, strat in strategies.items()},
            operator_disabled={name: not bool(strat.active) for name, strat in strategies.items()},
        )
        return
    for name, strat in strategies.items():
        if len(strat.pnl) < 20:
            continue
        if strat.sharpe() < 0:
            strat.active = False
            logger.info("Strategy disabled (sharpe < 0): %s", name)
            try:
                from forex_bot.live_safety import persist_evolve_disable

                persist_evolve_disable(name, sample_count=len(strat.pnl), sharpe=float(strat.sharpe()))
            except Exception:
                logger.exception("persist evolve disable failed for %s (strategy remains inactive)", name)


def daily_report() -> None:
    """Emit DAILY REPORT alert at most once per ``DAILY_REPORT_INTERVAL_SEC`` (default 86400 = 24h). Set 0 to disable."""
    try:
        interval = float((os.getenv("DAILY_REPORT_INTERVAL_SEC") or "86400").strip() or "86400")
    except ValueError:
        interval = 86400.0
    if interval <= 0:
        return
    now = time.time()
    last = last_report_ts()
    if last is not None and (now - last) < interval:
        return
    set_last_report_ts(now)
    eq = current_equity()
    alert(
        f" DAILY REPORT: Equity={eq:.2f} Sharpe={analytics.sharpe():.2f} "
        f"Winrate={analytics.winrate():.2%} Drawdown={analytics.drawdown():.2f}"
    )


@dataclass
class IterationDependencies:
    """Injected inputs for one offline iteration. Production code does not construct this."""

    candles: list[dict[str, Any]] | None = None
    spread: object = None
    balance: float | None = None
    account_present: bool = True
    account_context: str | None = None
    account_payload: dict[str, Any] | None = None
    account_error: str | None = None
    account_timeout: bool = False
    account_cached: bool = False
    account_as_of: datetime | None = None
    expected_account_id: str | None = None
    vote: dict[str, Any] | None = None
    vote_error: str | None = None
    strategy_name: str | None = None
    strategy_known: bool | None = None
    strategy_active: bool | None = None
    strategy_authorised: bool | None = None
    safety_initialised: bool | None = None
    simulation: bool = False
    now: datetime | None = None
    stop_distance: float | None = None
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    quote_as_of: datetime | None = None
    unrealised: float | None = None
    client_order_id: str | None = None
    broker: Any = None
    persistence_failure: str | None = None
    fail_position_record: bool = False
    reservation_update_failure: bool = False
    reconciliation_token: str | None = None
    phases: list[str] = field(default_factory=list)
    invoke_selector: bool = False
    invoke_vote: bool = False
    invoke_rl: bool = False
    rl_agent: Any = None
    strategy_active_map: dict[str, bool] | None = None
    selector_error: str | None = None
    vote_timeout: bool = False
    missing_features: bool = False
    rl_timeout: bool = False
    rl_error: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    extra_votes: tuple = ()
    empty_voters: bool = False
    broker_snapshot: dict[str, Any] | None = None
    broker_events: Any = None
    expected_account_currency: str | None = None
    oanda_summary: dict[str, Any] | None = None
    oanda_transactions: Any = None


def _iteration_frame(candles: list[dict[str, Any]]) -> Any:
    import pandas as pd

    return pd.DataFrame(candles)


_SHARED_EVIDENCE: dict[str, Any] = {}


def _reset_shared_evidence() -> None:
    _SHARED_EVIDENCE.clear()
    _SHARED_EVIDENCE.update(
        {
            "selector_called": False,
            "vote_wrapper_called": False,
            "rl_veto_called": False,
            "production_adapter_invoked": False,
            "account_gate": False,
            "sizing_invoked": False,
            "reservation_attempted": False,
            "adapter_called": False,
            "accepted_equity": None,
            "sizing_equity": None,
            "portfolio_cap_equity": None,
            "notional_cap_equity": None,
            "entry_equity_source": "",
            "current_equity_used_for_entry": False,
            "gross_notional_enabled": False,
            "unit_cap_enabled": False,
            "daily_loss_enabled": False,
            "drawdown_enabled": False,
            "spread_limit": "not_approved",
            "lookback_required": None,
            "margin_evidence": "not_implemented",
            "margin_sufficiency": "NOT_EVALUATED",
            "equity_is_not_margin_proof": True,
            "risk_halt": "",
            "quote_freshness": "not_evaluated",
            "selected_strategy": None,
            "lookback": None,
            "horizon": None,
        }
    )


def rl_decision_state(frame: Any) -> str:
    """Same state string the production loop passes to ``RLAgent.decide``."""
    trend_v = float(frame["trend"].iloc[-1]) if "trend" in getattr(frame, "columns", []) else 0.0
    vol_v = float(frame["volatility"].iloc[-1]) if "volatility" in getattr(frame, "columns", []) else 0.0
    if math.isnan(trend_v):
        trend_v = 0.0
    if math.isnan(vol_v):
        vol_v = 0.0
    return f"{round(trend_v, 4)}_{round(vol_v, 6)}"


def _drive_completed(coro: Any) -> Any:
    """Run a coroutine that does not sleep or use the network. No event loop."""
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


class _SuppliedVoter:
    """Feeds one controlled response into the production ``AIEnsemble.vote`` wrapper."""

    def __init__(self, response: Any, error: BaseException | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = 0

    async def predict(self, payload: dict[str, Any]) -> Any:
        _ = payload
        self.calls += 1
        if self.error is not None:
            raise self.error
        response = self.response
        if isinstance(response, dict) and "confidence" not in response:
            response = {**response, "confidence": 1.0 if response.get("allow") else 0.0}
        return response


def broker_signed_units(position_units: float, direction: str) -> int:
    """Sign rule used by the existing broker open: BUY positive, SELL negative.

    This mirrors ``oanda_exec._order_units_for_open`` and does not call it.
    The sized magnitude is still the value passed as ``position_units``.
    """
    magnitude = max(1, int(round(abs(float(position_units)))))
    if str(direction).strip().upper() == "BUY":
        return magnitude
    return -magnitude


def broker_open_arguments(
    *,
    symbol: str,
    units: float,
    direction: str,
    client_order_id: str,
    stop_loss: float | None,
    take_profit: float | None,
    execution_kind: str,
    entry_quote: Any,
) -> dict[str, Any]:
    """Map one order intent onto the existing broker-open signature. Does not call it."""
    from forex_bot.symbols import normalize_oanda_symbol

    return {
        "symbol": normalize_oanda_symbol(symbol),
        "position_units": float(units),
        "direction": direction,
        "client_order_id": client_order_id,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "execution_kind": execution_kind,
        "entry_quote": entry_quote,
        "broker_signed_units": broker_signed_units(units, direction),
    }


def _configured_unit_cap() -> float:
    """Existing per-order unit cap. Zero means the cap is off."""
    raw = (os.getenv("MAX_POSITION_UNITS") or "").strip()
    if not raw:
        return 0.0
    return float(raw)


def _entry_lookback_requirement(strategy_name: str | None, selected_lookback: object) -> int:
    """Use the selector lookback when it exists. Do not lower it.

    Otherwise use the existing scalp, swing, or default lookback setting.
    """
    if isinstance(selected_lookback, bool):
        selected_lookback = None
    if isinstance(selected_lookback, (int, float)) and not isinstance(selected_lookback, bool):
        if math.isfinite(float(selected_lookback)) and int(selected_lookback) > 0:
            return int(selected_lookback)
    name = str(strategy_name or "")
    if name.startswith("swing"):
        raw = (os.getenv("SWING_LOOKBACK") or "").strip()
        return int(raw) if raw else 100
    if "scalp" in name:
        raw = (os.getenv("SCALP_LOOKBACK") or "").strip()
        return int(raw) if raw else 50
    raw = (os.getenv("DEFAULT_INDICATOR_LOOKBACK") or "").strip()
    return int(raw) if raw else 50


def _unified_market_snapshot(
    dependencies: IterationDependencies,
    symbol: str,
    direction: str,
    candles: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """One quote for spread, sizing, and the intended entry.

    BUY is priced at the ask and SELL at the bid. The candle close is not a
    substitute. A synthetic snapshot never becomes production provenance.
    """
    if dependencies.bid is None or dependencies.ask is None:
        return None
    try:
        bid = float(dependencies.bid)
        ask = float(dependencies.ask)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask <= 0 or ask < bid:
        return None
    basis = "ask" if str(direction).upper() == "BUY" else "bid"
    price = ask if basis == "ask" else bid
    quote_time = dependencies.quote_as_of.isoformat() if isinstance(dependencies.quote_as_of, datetime) else None
    acquired = dependencies.now.isoformat() if isinstance(dependencies.now, datetime) else None
    candle_time = candles[-1].get("time") if candles and isinstance(candles[-1], dict) else None
    snapshot_id = f"{symbol}|{basis}|{bid:.10f}|{ask:.10f}|{quote_time}|{candle_time}|{len(candles)}"
    return {
        "snapshot_id": snapshot_id,
        "instrument": symbol,
        "bid": bid,
        "ask": ask,
        "price": price,
        "price_basis": basis,
        "quote_timestamp": quote_time,
        "acquisition_timestamp": acquired,
        "candle_timestamp": None if candle_time is None else str(candle_time),
        "candle_count": len(candles),
        "candle_price_basis": "ohlc",
        "provenance": "synthetic_harness" if dependencies.simulation else "not_production_verified",
        "spread": ask - bid,
        "spread_units": "price",
        "spread_policy": "POLICY_UNAPPROVED",
    }


def _bound_entry_quote(snapshot: dict[str, Any]) -> dict[str, Any]:
    """The entry quote carried with the order. It is the sizing snapshot."""
    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "bid": snapshot.get("bid"),
        "ask": snapshot.get("ask"),
        "price": snapshot.get("price"),
        "price_basis": snapshot.get("price_basis"),
    }


def _market_entry_block(
    dependencies: IterationDependencies,
    candles: list[dict[str, Any]],
    *,
    strategy_name: str | None,
) -> str | None:
    """Structural quote and candle checks. No numeric spread limit is approved."""
    required = _entry_lookback_requirement(strategy_name, _SHARED_EVIDENCE.get("lookback"))
    _SHARED_EVIDENCE["lookback_required"] = required
    _SHARED_EVIDENCE["spread_limit"] = "not_approved"
    _SHARED_EVIDENCE["market_provenance"] = "synthetic_harness" if dependencies.simulation else "not_production_verified"
    if len(candles) < required:
        return "insufficient_lookback"
    times: list[datetime] = []
    duplicate = False
    for row in candles:
        if not isinstance(row, dict) or "close" not in row:
            return "candle_malformed"
        for key in ("open", "high", "low", "close"):
            if key not in row:
                continue
            try:
                value = float(row[key])
            except (TypeError, ValueError):
                return "candle_malformed"
            if not math.isfinite(value):
                return "candle_nonfinite"
        raw_time = row.get("time")
        if raw_time:
            try:
                parsed = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
            except ValueError:
                return "candle_malformed"
            if times and parsed < times[-1]:
                return "candle_time_out_of_order"
            if times and parsed == times[-1]:
                duplicate = True
            times.append(parsed)
    _SHARED_EVIDENCE["duplicate_candle_timestamps"] = duplicate
    if dependencies.spread is not None and (
        isinstance(dependencies.spread, bool) or not isinstance(dependencies.spread, (int, float))
    ):
        return "quote_malformed"
    if isinstance(dependencies.spread, (int, float)) and not isinstance(dependencies.spread, bool):
        if not math.isfinite(float(dependencies.spread)):
            return "quote_nonfinite"
        if float(dependencies.spread) < 0:
            return "quote_negative_spread"
    bid = dependencies.bid
    ask = dependencies.ask
    if bid is None:
        return "quote_bid_missing"
    if ask is None:
        return "quote_ask_missing"
    try:
        bid_f = float(bid)
        ask_f = float(ask)
    except (TypeError, ValueError):
        return "quote_malformed"
    if not math.isfinite(bid_f):
        return "quote_bid_nonfinite"
    if not math.isfinite(ask_f):
        return "quote_ask_nonfinite"
    if bid_f <= 0:
        return "quote_bid_not_positive"
    if ask_f <= 0:
        return "quote_ask_not_positive"
    if ask_f < bid_f:
        return "quote_crossed"
    _SHARED_EVIDENCE["spread_price_units"] = ask_f - bid_f
    _SHARED_EVIDENCE["spread_units"] = "price"
    if dependencies.quote_as_of is None:
        _SHARED_EVIDENCE["quote_freshness"] = "missing"
        return "quote_timestamp_missing"
    if not isinstance(dependencies.quote_as_of, datetime):
        _SHARED_EVIDENCE["quote_freshness"] = "invalid"
        return "quote_timestamp_invalid"
    if dependencies.now is None:
        _SHARED_EVIDENCE["quote_freshness"] = "missing"
        return "quote_timestamp_missing"
    from forex_bot.live_manage import MANAGE_PRICE_STALE_SEC

    try:
        age = (dependencies.now - dependencies.quote_as_of).total_seconds()
    except (TypeError, ValueError):
        _SHARED_EVIDENCE["quote_freshness"] = "invalid"
        return "quote_timestamp_invalid"
    if age < 0:
        _SHARED_EVIDENCE["quote_freshness"] = "future"
        return "quote_timestamp_future"
    if age > float(MANAGE_PRICE_STALE_SEC):
        _SHARED_EVIDENCE["quote_freshness"] = "stale"
        return "quote_stale"
    _SHARED_EVIDENCE["quote_freshness"] = "harness_manage_window"
    return None


def _pending_gross_usd() -> tuple[str | None, float]:
    """Notional of blocking reservations. Missing size or price is not zero."""
    from forex_bot.database import reservation_status_block_reason
    from forex_bot.orders import orders_by_client_id
    from forex_bot.portfolio_exposure import approx_gross_usd_notional_for
    import forex_bot.database as database

    extra = 0.0
    seen: set[str] = set()

    def _add(order: Any) -> str | None:
        nonlocal extra
        try:
            units = float(order.units_requested)
            price = float(order.avg_fill_price)
        except (TypeError, ValueError):
            return "notional_exposure_unreadable"
        if not math.isfinite(units) or not math.isfinite(price) or price <= 0 or units == 0:
            return "notional_exposure_unreadable"
        extra += approx_gross_usd_notional_for(str(order.symbol), abs(units), price)
        return None

    for order in list(orders_by_client_id.values()):
        status = getattr(getattr(order, "status", None), "value", None)
        if not reservation_status_block_reason(status):
            continue
        seen.add(str(order.client_order_id))
        blocked = _add(order)
        if blocked:
            return blocked, 0.0
    for book in (database._process_blocking, database._process_unresolved):
        for client_order_id in book.values():
            if str(client_order_id) in seen:
                continue
            order = orders_by_client_id.get(str(client_order_id))
            if order is None:
                return "notional_exposure_unreadable", 0.0
            seen.add(str(client_order_id))
            blocked = _add(order)
            if blocked:
                return blocked, 0.0
    return None, extra


_GATE_STATUSES = {
    "PASS",
    "BLOCK",
    "MISSING_EVIDENCE",
    "POLICY_UNAPPROVED",
    "NOT_IMPLEMENTED",
    "DISABLED",
    "NOT_APPLICABLE",
}
_MANDATORY_GATE_IDS = (
    "live_permission",
    "account_snapshot",
    "quote_structure",
    "quote_freshness",
    "lookback",
    "portfolio_stop_risk",
    "numeric_spread",
    "margin",
    "production_account_provenance",
    "production_market_provenance",
    "production_quote_provenance",
    "production_strategy_activation",
    "execution_adapter",
)
_EARLY_GATE = {
    "quote_bid_missing": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_ask_missing": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_bid_nonfinite": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_ask_nonfinite": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_bid_not_positive": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_ask_not_positive": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_crossed": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_malformed": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_nonfinite": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_negative_spread": ("quote_structure", "BLOCK", "mandatory", "entry"),
    "quote_timestamp_missing": ("quote_freshness", "MISSING_EVIDENCE", "mandatory", "entry"),
    "quote_timestamp_invalid": ("quote_freshness", "BLOCK", "mandatory", "entry"),
    "quote_stale": ("quote_freshness", "BLOCK", "mandatory", "entry"),
    "quote_timestamp_future": ("quote_freshness", "BLOCK", "mandatory", "entry"),
    "insufficient_lookback": ("lookback", "BLOCK", "mandatory", "entry"),
    "candle_malformed": ("lookback", "BLOCK", "mandatory", "entry"),
    "candle_nonfinite": ("lookback", "BLOCK", "mandatory", "entry"),
    "candle_time_out_of_order": ("lookback", "BLOCK", "mandatory", "entry"),
    "notional_cap": ("gross_notional", "BLOCK", "optional", "entry"),
    "notional_exposure_unreadable": ("gross_notional", "MISSING_EVIDENCE", "optional", "entry"),
    "notional_nonfinite": ("gross_notional", "BLOCK", "optional", "entry"),
    "unit_cap": ("unit_cap", "BLOCK", "optional", "entry"),
    "daily_realised_loss_limit": ("daily_loss", "BLOCK", "optional", "entry"),
    "daily_total_loss_limit": ("daily_loss", "BLOCK", "optional", "entry"),
    "max_drawdown_limit": ("drawdown", "BLOCK", "optional", "entry"),
    "account_unrealised_unavailable": ("daily_loss", "MISSING_EVIDENCE", "optional", "entry"),
    "corrupt_risk_state": ("daily_loss", "BLOCK", "optional", "entry"),
    "portfolio_risk_cap": ("portfolio_stop_risk", "BLOCK", "mandatory", "entry"),
    "account_missing": ("account_snapshot", "MISSING_EVIDENCE", "mandatory", "entry"),
    "account_unverified": ("account_snapshot", "MISSING_EVIDENCE", "mandatory", "entry"),
    "account_equity_missing": ("account_snapshot", "MISSING_EVIDENCE", "mandatory", "entry"),
    "position_already_open": ("exposure_hold", "BLOCK", "mandatory", "entry"),
    "exposure_unconfirmed": ("exposure_hold", "BLOCK", "mandatory", "entry"),
    "active_reservation": ("exposure_hold", "BLOCK", "mandatory", "entry"),
    "unresolved_intent": ("exposure_hold", "BLOCK", "mandatory", "entry"),
    "rl_veto": ("rl_veto", "BLOCK", "mandatory", "entry"),
    "invalid_entry_direction": ("ai_vote", "BLOCK", "mandatory", "entry"),
    "STRATEGY_INACTIVE": ("strategy_gate", "BLOCK", "mandatory", "entry"),
}


def _record_gate(
    gate_id: str,
    status: str,
    *,
    classification: str,
    scope: str,
    reason: str = "",
    applicability: str = "",
) -> None:
    """Record one gate. A later PASS cannot replace an earlier non-PASS."""
    if status not in _GATE_STATUSES:
        status = "BLOCK"
        reason = reason or "unknown_gate_status"
    if status == "NOT_APPLICABLE" and not str(applicability).strip():
        status = "BLOCK"
        reason = reason or "invalid_applicability"
    gates = _SHARED_EVIDENCE.setdefault("risk_gates", [])
    for existing in gates:
        if existing["id"] != gate_id:
            continue
        if existing["status"] != "PASS":
            return
        if status == "PASS":
            return
        existing["status"] = status
        existing["reason"] = reason
        existing["applicability"] = applicability
        return
    gates.append(
        {
            "id": gate_id,
            "status": status,
            "classification": classification,
            "scope": scope,
            "reason": reason,
            "applicability": applicability,
        }
    )


def _record_standing_production_gaps() -> None:
    """Gaps that are not passes. Caller text cannot change these statuses."""
    _record_gate(
        "live_permission",
        "BLOCK",
        classification="mandatory",
        scope="production_only",
        reason="live_orders_refused_by_offline_seam",
    )
    _record_gate(
        "numeric_spread",
        "POLICY_UNAPPROVED",
        classification="mandatory",
        scope="production_only",
        reason="no_approved_numeric_spread_threshold",
    )
    _record_gate(
        "margin",
        "NOT_IMPLEMENTED",
        classification="mandatory",
        scope="production_only",
        reason="margin_not_implemented",
    )
    _record_gate(
        "production_account_provenance",
        "MISSING_EVIDENCE",
        classification="mandatory",
        scope="production_only",
        reason="synthetic_account_is_not_production_proof",
    )
    _record_gate(
        "production_market_provenance",
        "MISSING_EVIDENCE",
        classification="mandatory",
        scope="production_only",
        reason="synthetic_market_data_is_not_broker_verified",
    )
    _record_gate(
        "production_quote_provenance",
        "MISSING_EVIDENCE",
        classification="mandatory",
        scope="production_only",
        reason="synthetic_timestamp_is_not_production_freshness",
    )
    _record_gate(
        "production_strategy_activation",
        "BLOCK",
        classification="mandatory",
        scope="production_only",
        reason="production_strategies_remain_inactive",
    )
    _record_gate(
        "execution_adapter",
        "BLOCK",
        classification="mandatory",
        scope="production_only",
        reason="production_adapter_withheld",
    )


def _seal_entry_gates(dependencies: IterationDependencies, *, strategy_name: str | None, direction: str | None) -> None:
    """Record gate outcomes after the existing checks and before reservation."""
    _record_standing_production_gaps()
    _record_gate(
        "account_snapshot",
        "PASS",
        classification="mandatory",
        scope="entry",
        reason="isolated_snapshot_accepted",
    )
    _record_gate(
        "quote_structure",
        "PASS",
        classification="mandatory",
        scope="entry",
        reason="bid_ask_structure_accepted",
    )
    freshness = str(_SHARED_EVIDENCE.get("quote_freshness") or "")
    if freshness == "harness_manage_window":
        _record_gate(
            "quote_freshness",
            "PASS",
            classification="mandatory",
            scope="entry",
            reason="existing_90_second_window",
        )
    else:
        _record_gate(
            "quote_freshness",
            "MISSING_EVIDENCE",
            classification="mandatory",
            scope="entry",
            reason="quote_timestamp_missing",
        )
    _record_gate(
        "lookback",
        "PASS",
        classification="mandatory",
        scope="entry",
        reason=f"lookback_met:{_SHARED_EVIDENCE.get('lookback_required')}",
    )
    _record_gate(
        "portfolio_stop_risk",
        "PASS",
        classification="mandatory",
        scope="entry",
        reason="within_existing_five_percent_cap",
    )
    _record_gate(
        "exposure_hold",
        "PASS",
        classification="mandatory",
        scope="entry",
        reason="no_open_exposure_hold",
    )
    _record_gate(
        "strategy_gate",
        "PASS",
        classification="mandatory",
        scope="entry",
        reason=str(strategy_name or ""),
    )
    if direction in {"BUY", "SELL"}:
        _record_gate("ai_vote", "PASS", classification="mandatory", scope="entry", reason=str(direction))
    else:
        _record_gate("ai_vote", "BLOCK", classification="mandatory", scope="entry", reason="invalid_entry_direction")
    if _SHARED_EVIDENCE.get("rl_veto_called"):
        _record_gate("rl_veto", "PASS", classification="mandatory", scope="entry", reason="rl_approved")
    else:
        _record_gate(
            "rl_veto",
            "NOT_APPLICABLE",
            classification="mandatory",
            scope="entry",
            reason="rl_not_invoked",
            applicability="invoke_rl_is_false",
        )
    if _SHARED_EVIDENCE.get("gross_notional_enabled"):
        _record_gate("gross_notional", "PASS", classification="optional", scope="entry", reason="within_enabled_cap")
    else:
        _record_gate(
            "gross_notional",
            "DISABLED",
            classification="optional",
            scope="entry",
            reason="gross_notional_percentage_is_zero",
        )
    if _SHARED_EVIDENCE.get("unit_cap_enabled"):
        _record_gate("unit_cap", "PASS", classification="optional", scope="entry", reason="within_enabled_unit_cap")
    else:
        _record_gate("unit_cap", "DISABLED", classification="optional", scope="entry", reason="unit_cap_is_zero")
    if _SHARED_EVIDENCE.get("daily_loss_enabled"):
        _record_gate("daily_loss", "PASS", classification="optional", scope="entry", reason="within_existing_daily_loss_limit")
        _record_gate("drawdown", "PASS", classification="optional", scope="entry", reason="within_existing_drawdown_limit")
    else:
        _record_gate(
            "daily_loss",
            "DISABLED",
            classification="optional",
            scope="entry",
            reason="decision_repair_account_risk_off",
        )
        _record_gate(
            "drawdown",
            "DISABLED",
            classification="optional",
            scope="entry",
            reason="decision_repair_account_risk_off",
        )
    _ = dependencies


def _synthetic_dispatch_block() -> str | None:
    """Block the inert adapter unless every entry-scoped gate actually passed or is optional-disabled."""
    for gate in list(_SHARED_EVIDENCE.get("risk_gates") or []):
        if gate.get("scope") == "production_only":
            continue
        status = gate.get("status")
        if status not in _GATE_STATUSES:
            return "unknown_gate_status"
        if status == "PASS":
            continue
        if status == "DISABLED" and gate.get("classification") == "optional":
            continue
        if status == "NOT_APPLICABLE" and str(gate.get("applicability") or "").strip():
            continue
        return str(gate.get("reason") or gate.get("id") or "risk_gate_blocked")
    return None


_PRODUCER_SEALS: dict[str, dict[str, Any]] = {}
_CONSUMED_SEALS: set[str] = set()


def _order_binding(
    dependencies: IterationDependencies,
    *,
    symbol: str,
    direction: str,
    units: float | None,
    client_order_id: str,
) -> dict[str, Any]:
    """Immutable order facts stored with a producer decision. No account payload is copied."""
    stored_quote = _SHARED_EVIDENCE.get("entry_quote")
    if isinstance(stored_quote, dict):
        quote = dict(stored_quote)
    elif dependencies.bid is not None and dependencies.ask is not None:
        quote = {"bid": dependencies.bid, "ask": dependencies.ask}
    else:
        quote = None
    return {
        "instrument": symbol,
        "direction": direction,
        "quantity": units,
        "stop_loss": dependencies.stop_loss,
        "take_profit": dependencies.take_profit,
        "execution_kind": "simulated" if dependencies.simulation else "production",
        "entry_quote": quote,
        "client_order_id": client_order_id,
        "reservation_id": client_order_id if _SHARED_EVIDENCE.get("reservation_attempted") else "",
        "account_id": "",
    }


def _producer_seal_id(decision: dict[str, Any]) -> str:
    import hashlib
    import json

    payload = {
        "decision_id": decision.get("decision_id"),
        "context": decision.get("context"),
        "production_eligible": decision.get("production_eligible"),
        "timestamp": decision.get("timestamp"),
        "order_binding": decision.get("order_binding"),
        "spread": decision.get("spread"),
        "margin_evidence": decision.get("margin_evidence"),
    }
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _register_producer_seal(decision: dict[str, Any]) -> None:
    """Store the producer copy. A later caller mutation does not replace it."""
    import json

    seal_id = str(decision.get("seal_id") or "")
    if not seal_id or seal_id in _PRODUCER_SEALS:
        return
    _PRODUCER_SEALS[seal_id] = json.loads(json.dumps(decision, default=str))


def _finite_or_none(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _decision_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _mandatory_gate_reason(gates: object) -> str | None:
    if not isinstance(gates, list) or not gates:
        return "mandatory_gates_missing"
    seen: dict[str, str] = {}
    for gate in gates:
        if not isinstance(gate, dict) or "id" not in gate or "status" not in gate:
            return "eligibility_malformed"
        gate_id = str(gate.get("id") or "")
        status = gate.get("status")
        if not isinstance(status, str) or status not in _GATE_STATUSES:
            return "unknown_gate_status"
        if gate_id in seen and seen[gate_id] != status:
            return "decision_conflict"
        seen[gate_id] = status
    for gate_id in _MANDATORY_GATE_IDS:
        status = seen.get(gate_id)
        if status is None:
            return "mandatory_gates_missing"
        if status == "BLOCK":
            return "mandatory_block"
        if status == "MISSING_EVIDENCE":
            return "mandatory_missing_evidence"
        if status == "POLICY_UNAPPROVED":
            return "mandatory_policy_unapproved"
        if status == "NOT_IMPLEMENTED":
            return "mandatory_not_implemented"
        if status == "DISABLED":
            return "mandatory_disabled"
        if status != "PASS":
            return "unknown_gate_status"
    return None


def _binding_reason(binding: object, *, symbol: str, units: float, direction: str, client_order_id: str, stop_loss: object, take_profit: object, execution_kind: str, entry_quote: object, reservation_id: str) -> str | None:
    if not isinstance(binding, dict):
        return "order_binding_missing"
    if str(binding.get("instrument") or "") != str(symbol):
        return "order_instrument_mismatch"
    if str(binding.get("direction") or "").upper() != str(direction).upper():
        return "order_direction_mismatch"
    quantity = _finite_or_none(binding.get("quantity"))
    called = _finite_or_none(units)
    if quantity is None or called is None:
        return "order_quantity_invalid"
    if not math.isclose(abs(quantity), abs(called), rel_tol=0.0, abs_tol=1e-9):
        return "order_quantity_mismatch"
    if not _prices_match(binding.get("stop_loss"), stop_loss):
        return "order_stop_mismatch"
    if not _prices_match(binding.get("take_profit"), take_profit):
        return "order_target_mismatch"
    if binding.get("entry_quote") != entry_quote:
        return "order_quote_mismatch"
    if str(binding.get("execution_kind") or "") != str(execution_kind):
        return "order_execution_kind_mismatch"
    if str(binding.get("client_order_id") or "") != str(client_order_id):
        return "order_client_id_mismatch"
    if str(binding.get("reservation_id") or "") != str(reservation_id):
        return "order_reservation_mismatch"
    return None


def _prices_match(left: object, right: object) -> bool:
    if left is None and right is None:
        return True
    left_number = _finite_or_none(left)
    right_number = _finite_or_none(right)
    if left_number is None or right_number is None:
        return False
    return math.isclose(left_number, right_number, rel_tol=0.0, abs_tol=1e-9)


def production_adapter_refusal(
    risk_decision: object,
    *,
    symbol: str,
    units: float,
    direction: str,
    client_order_id: str,
    stop_loss: object = None,
    take_profit: object = None,
    execution_kind: str = "",
    entry_quote: object = None,
    reservation_id: str = "",
) -> str:
    """Refuse production dispatch. A caller dictionary is not production authority."""
    if risk_decision is None:
        return "eligibility_missing"
    if not isinstance(risk_decision, dict):
        return "eligibility_malformed"
    seal_id = str(risk_decision.get("seal_id") or "")
    if seal_id and seal_id in _CONSUMED_SEALS:
        return "decision_already_used"
    if risk_decision.get("context") == "isolated_test" or risk_decision.get("synthetic") is True:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "synthetic_context_rejected"
    if risk_decision.get("production_eligible") is not True:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "production_ineligible"
    gate_reason = _mandatory_gate_reason(risk_decision.get("gates"))
    if gate_reason:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return gate_reason
    if risk_decision.get("prior_outcome") in {"timeout", "ambiguous", "partial", "unresolved"}:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "prior_attempt_not_fresh"
    if risk_decision.get("reservation_state") != "reserved":
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "reservation_not_permission"
    binding_reason = _binding_reason(
        risk_decision.get("order_binding"),
        symbol=symbol,
        units=units,
        direction=direction,
        client_order_id=client_order_id,
        stop_loss=stop_loss,
        take_profit=take_profit,
        execution_kind=execution_kind,
        entry_quote=entry_quote,
        reservation_id=reservation_id,
    )
    if binding_reason:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return binding_reason
    stamped = _decision_timestamp(risk_decision.get("timestamp"))
    if risk_decision.get("timestamp") in (None, ""):
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "decision_timestamp_missing"
    if stamped is None:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "decision_timestamp_invalid"
    age = (datetime.now(timezone.utc) - stamped).total_seconds()
    if age < 0:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "decision_timestamp_future"
    if age > 90:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "decision_expired"
    account_id = ""
    binding = risk_decision.get("order_binding")
    if isinstance(binding, dict):
        account_id = str(binding.get("account_id") or "")
    if not account_id:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "account_identity_missing"
    stored = _PRODUCER_SEALS.get(seal_id)
    if stored is None:
        if seal_id:
            _CONSUMED_SEALS.add(seal_id)
        return "untrusted_decision"
    if stored.get("production_eligible") is not True or stored.get("order_binding") != risk_decision.get("order_binding"):
        _CONSUMED_SEALS.add(seal_id)
        return "decision_conflict"
    _CONSUMED_SEALS.add(seal_id)
    return "production_authority_unavailable"


def _build_risk_decision(
    dependencies: IterationDependencies,
    *,
    blocked_by: str,
    direction: str | None,
    broker_requests: int,
    symbol: str = "",
    strategy_name: str = "",
    units: float | None = None,
    client_order_id: str = "",
) -> dict[str, Any]:
    if blocked_by in _EARLY_GATE:
        gate_id, status, classification, scope = _EARLY_GATE[blocked_by]
        _record_gate(gate_id, status, classification=classification, scope=scope, reason=blocked_by)
    _record_standing_production_gaps()
    if _SHARED_EVIDENCE.get("reservation_attempted"):
        _record_gate("reservation", "PASS", classification="mandatory", scope="entry", reason="reservation_recorded")
    elif blocked_by in {"reservation_refused", "reservation_persistence_failed"}:
        _record_gate("reservation", "BLOCK", classification="mandatory", scope="entry", reason=blocked_by)
    else:
        _record_gate(
            "reservation",
            "NOT_APPLICABLE",
            classification="mandatory",
            scope="entry",
            reason="not_reached",
            applicability="eligibility_or_an_earlier_gate_returned",
        )
    present = {gate["id"] for gate in _SHARED_EVIDENCE.get("risk_gates") or []}
    for gate_id in _MANDATORY_GATE_IDS:
        if gate_id not in present:
            _record_gate(
                gate_id,
                "MISSING_EVIDENCE",
                classification="mandatory",
                scope="entry",
                reason="not_evaluated_on_this_path",
            )
    blocking: list[str] = []
    disabled: list[str] = []
    missing: list[str] = []
    unapproved: list[str] = []
    absent: list[str] = []
    mandatory: list[str] = []
    by_id: dict[str, str] = {}
    production_eligible = True
    for gate in list(_SHARED_EVIDENCE.get("risk_gates") or []):
        gate_id = str(gate["id"])
        status = str(gate["status"])
        by_id[gate_id] = status
        if gate.get("classification") == "mandatory":
            mandatory.append(gate_id)
        if status == "DISABLED":
            disabled.append(gate_id)
        elif status == "MISSING_EVIDENCE":
            missing.append(gate_id)
        elif status == "POLICY_UNAPPROVED":
            unapproved.append(gate_id)
        elif status == "NOT_IMPLEMENTED":
            absent.append(gate_id)
        if status == "PASS":
            continue
        if status == "DISABLED" and gate.get("classification") == "optional":
            continue
        if status == "NOT_APPLICABLE" and str(gate.get("applicability") or "").strip():
            continue
        production_eligible = False
        blocking.append(f"{gate_id}:{status}:{gate.get('reason') or ''}")
    for gate_id in _MANDATORY_GATE_IDS:
        if by_id.get(gate_id) != "PASS":
            production_eligible = False
    harness = bool(dependencies.simulation) and dependencies.account_context in (None, "isolated_test")
    stamp = dependencies.now.isoformat() if isinstance(dependencies.now, datetime) else ""
    decision = {
        "decision_id": f"{symbol}|{direction or ''}|{stamp}|{strategy_name}",
        "context": "isolated_test" if harness else "production",
        "instrument": symbol,
        "direction": direction or "",
        "timestamp": stamp,
        "strategy": strategy_name,
        "account_evidence": by_id.get("account_snapshot", "MISSING_EVIDENCE"),
        "market_data_evidence": by_id.get("production_market_provenance", "MISSING_EVIDENCE"),
        "exposure_hold": by_id.get("exposure_hold", "MISSING_EVIDENCE"),
        "portfolio_risk": by_id.get("portfolio_stop_risk", "MISSING_EVIDENCE"),
        "gross_notional": by_id.get("gross_notional", "DISABLED"),
        "unit_limit": by_id.get("unit_cap", "DISABLED"),
        "daily_loss": by_id.get("daily_loss", "DISABLED"),
        "drawdown": by_id.get("drawdown", "DISABLED"),
        "spread": by_id.get("numeric_spread", "POLICY_UNAPPROVED"),
        "quote_freshness": by_id.get("quote_freshness", "MISSING_EVIDENCE"),
        "lookback": by_id.get("lookback", "MISSING_EVIDENCE"),
        "margin_evidence": by_id.get("margin", "NOT_IMPLEMENTED"),
        "mandatory_gates": mandatory,
        "disabled_gates": disabled,
        "missing_evidence": missing,
        "unapproved_policies": unapproved,
        "not_implemented": absent,
        "blocking_reasons": blocking,
        "production_eligible": production_eligible,
        "synthetic_contract": "completed" if broker_requests else "not_completed",
        "reservation_attempted": bool(_SHARED_EVIDENCE.get("reservation_attempted")),
        "inert_adapter_invoked": broker_requests > 0,
        "production_adapter_invoked": False,
        "order_binding": _order_binding(
            dependencies,
            symbol=symbol,
            direction=direction or "",
            units=units,
            client_order_id=client_order_id,
        ),
        "gates": [dict(gate) for gate in list(_SHARED_EVIDENCE.get("risk_gates") or [])],
    }
    decision["seal_id"] = _producer_seal_id(decision)
    _register_producer_seal(decision)
    return decision


def _account_entry_block(dependencies: IterationDependencies) -> tuple[str | None, float | None]:
    """Reject equity that is missing, unusable, or not an isolated test snapshot.

    ``verified`` flags and ``current_equity`` are not account proof. A production
    snapshot is not fetched here. Without the isolated-test context the entry
    fails closed.

    When both ``dependencies.balance`` and a payload equity field are present,
    ``balance`` is the authoritative equity for that decision. The returned
    value is a float copy. Later mutation of the payload does not replace it.
    """
    if dependencies.account_timeout:
        return "account_acquisition_timeout", None
    if dependencies.account_error:
        return "account_acquisition_error", None
    if not dependencies.account_present:
        return "account_missing", None
    payload = dependencies.account_payload
    if payload is not None and not isinstance(payload, dict):
        return "account_payload_malformed", None
    if dependencies.account_cached:
        return "unverified_cached_equity", None
    harness = bool(dependencies.simulation) and dependencies.account_context in (None, "isolated_test")
    if not harness:
        return "account_unverified", None
    if dependencies.expected_account_id:
        actual = payload.get("id") if isinstance(payload, dict) else None
        if not actual:
            return "account_identity_unknown", None
        if str(actual) != str(dependencies.expected_account_id):
            return "account_identity_mismatch", None
    if dependencies.account_as_of is not None and dependencies.now is not None:
        if dependencies.account_as_of > dependencies.now:
            return "account_timestamp_future", None
        if (dependencies.now - dependencies.account_as_of).total_seconds() > 300:
            return "account_snapshot_stale", None
    elif dependencies.account_as_of is None:
        _SHARED_EVIDENCE["account_freshness_not_evaluated"] = True
    equity = dependencies.balance
    if equity is None and isinstance(payload, dict) and "equity" in payload:
        equity = payload.get("equity")
    if equity is None:
        return "account_equity_missing", None
    if isinstance(equity, bool) or not isinstance(equity, (int, float, str)):
        return "account_equity_malformed", None
    if isinstance(equity, str):
        try:
            equity = float(equity.strip())
        except ValueError:
            return "account_equity_malformed", None
    equity_value = float(equity)
    if not math.isfinite(equity_value):
        return "account_equity_nonfinite", None
    if equity_value <= 0:
        return "account_equity_not_positive", None
    _SHARED_EVIDENCE["account_equity"] = equity_value
    _SHARED_EVIDENCE["account_context"] = "isolated_test"
    return None, equity_value


async def production_execution_adapter(
    symbol: str,
    units: float,
    direction: str,
    client_order_id: str,
    *,
    stop_loss: float | None,
    take_profit: float | None,
    execution_kind: str,
    entry_quote: Any,
    risk_decision: Any = None,
    reservation_id: str = "",
) -> Any:
    """The only production call to the broker open. It refuses without a producer seal.

    A caller dictionary, ``verified=True``, or a synthetic decision is not authority.
    No current producer can seal ``production_eligible`` true, so this returns before
    the broker call. There is no retry.
    """
    reason = production_adapter_refusal(
        risk_decision,
        symbol=symbol,
        units=units,
        direction=direction,
        client_order_id=client_order_id,
        stop_loss=stop_loss,
        take_profit=take_profit,
        execution_kind=execution_kind,
        entry_quote=entry_quote,
        reservation_id=reservation_id,
    )
    if reason:
        return {
            "status": "refused",
            "reason": reason,
            "broker_called": False,
            "production_authorised": False,
            "verified_ignored": isinstance(risk_decision, dict) and bool(risk_decision.get("verified")),
        }
    import forex_bot.oanda_exec as oanda_exec
    from decimal import Decimal

    from forex_bot.close_journal import JournalUnavailable, account_binding
    from forex_bot.entry_journal import begin_entry_submission

    try:
        permit = begin_entry_submission(
            account_binding_value=account_binding((Config.OANDA_ACCOUNT_ID or "").strip()),
            instrument=symbol,
            direction=direction,
            requested_units=Decimal(str(units)),
            position_instance_id=__import__("uuid").uuid4().hex,
            position_generation=1,
            client_order_id=client_order_id,
            strategy_name=str(risk_decision.get("strategy_name") or "") if isinstance(risk_decision, dict) else "",
            stop_loss=None if stop_loss is None else str(stop_loss),
            take_profit=None if take_profit is None else str(take_profit),
            entry_reference=None,
            atr_at_entry_pips=None,
        )
    except JournalUnavailable as exc:
        return {
            "status": "refused",
            "reason": exc.reason,
            "broker_called": False,
            "production_authorised": False,
        }

    arguments = broker_open_arguments(
        symbol=symbol,
        units=units,
        direction=direction,
        client_order_id=client_order_id,
        stop_loss=stop_loss,
        take_profit=take_profit,
        execution_kind=execution_kind,
        entry_quote=entry_quote,
    )
    return await oanda_exec.execute_oanda_market_open(
        arguments["symbol"],
        arguments["position_units"],
        arguments["direction"],
        arguments["client_order_id"],
        stop_loss=arguments["stop_loss"],
        take_profit=arguments["take_profit"],
        execution_kind=arguments["execution_kind"],
        entry_quote=arguments["entry_quote"],
        entry_permit=permit,
    )


def _iteration_result(
    *,
    status: str,
    blocked_by: str,
    dependencies: IterationDependencies,
    phases: list[str],
    direction: str | None = None,
    units: float | None = None,
    broker_requests: int = 0,
    provenance: str | None = None,
    client_order_id: str = "",
    exposure_held: bool = False,
    source_gap: str = "",
    outcome: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        decision = _build_risk_decision(
            dependencies,
            blocked_by=blocked_by,
            direction=direction,
            broker_requests=broker_requests,
            symbol=str(_SHARED_EVIDENCE.get("instrument") or ""),
            strategy_name=str(_SHARED_EVIDENCE.get("strategy_name") or _SHARED_EVIDENCE.get("selected_strategy") or ""),
            units=units,
            client_order_id=client_order_id,
        )
    except Exception:
        decision = {
            "decision_id": "",
            "context": "production",
            "production_eligible": False,
            "synthetic_contract": "not_completed",
            "blocking_reasons": ["risk_gate_evaluation_failed"],
            "reservation_attempted": False,
            "inert_adapter_invoked": False,
            "production_adapter_invoked": False,
        }
    _SHARED_EVIDENCE["risk_decision"] = decision
    _SHARED_EVIDENCE["production_eligible"] = False if not isinstance(decision, dict) else bool(decision.get("production_eligible"))
    return {
        "status": status,
        "blocked_by": blocked_by,
        "direction": direction,
        "units": units,
        "broker_requests": broker_requests,
        "simulation": bool(dependencies.simulation),
        "production_authorised": False,
        "production_eligible": bool(_SHARED_EVIDENCE["production_eligible"]),
        "trading_ready": False,
        "scheduled_another": False,
        "provenance": provenance,
        "phases": tuple(phases),
        "client_order_id": client_order_id,
        "exposure_held": exposure_held,
        "source_gap": source_gap,
        "outcome": outcome,
        "real_broker": False,
        "details": {**_SHARED_EVIDENCE, **dict(details or {})},
    }


def evaluate_one_instrument_iteration(
    symbol: str,
    dependencies: IterationDependencies,
) -> dict[str, Any]:
    """Run one new-entry decision with the existing gates.

    This function does not sleep, schedule, or call ``run_bot``. A fake broker
    is used only when ``dependencies.simulation`` is true and the real live-order
    gate is blocking. That dispatch is not a broker order.
    """
    _reset_shared_evidence()
    from forex_bot.broker_exit import broker_exit_open_blocked_reason
    from forex_bot.database import (
        exposure_entry_block_reason,
        note_unconfirmed_exposure,
        refuse_reservation_after_database_fault,
        reservation_status_block_reason,
        restore_unresolved_intent,
    )
    from forex_bot.market_provenance import decision_frame_rejection
    from forex_bot.orders import record_synthetic_fill_position
    from forex_bot.positions import get_position
    from forex_bot.session_rules import flatten_for_weekend_at, in_active_session_at
    from forex_bot.strategy_meta import strategies

    phases: list[str] = ["seam"]
    sym = str(symbol or "").upper().strip()
    _SHARED_EVIDENCE["instrument"] = sym
    candles = dependencies.candles
    if not candles:
        phases.append("candles")
        return _iteration_result(
            status="blocked",
            blocked_by="no_candles",
            dependencies=dependencies,
            phases=phases,
        )

    phases.append("session")
    if dependencies.now is None:
        return _iteration_result(
            status="blocked",
            blocked_by="clock_not_injected",
            dependencies=dependencies,
            phases=phases,
        )
    if dependencies.now is not None:
        if flatten_for_weekend_at(dependencies.now):
            return _iteration_result(
                status="blocked",
                blocked_by="weekend_flatten",
                dependencies=dependencies,
                phases=phases,
            )
        if not in_active_session_at(sym, dependencies.now):
            return _iteration_result(
                status="blocked",
                blocked_by="market_session_closed",
                dependencies=dependencies,
                phases=phases,
            )

    phases.append("position")
    _SHARED_EVIDENCE["exposure_read"] = exposure_entry_block_reason(sym) or ""
    _SHARED_EVIDENCE["position_open"] = get_position(sym) is not None
    if _SHARED_EVIDENCE["position_open"]:
        return _iteration_result(
            status="blocked",
            blocked_by="position_already_open",
            dependencies=dependencies,
            phases=phases,
        )

    phases.append("exposure")
    exposure_block = exposure_entry_block_reason(sym)
    if exposure_block:
        return _iteration_result(
            status="blocked",
            blocked_by=exposure_block,
            dependencies=dependencies,
            phases=phases,
            exposure_held=True,
        )

    phases.append("broker_exit")
    if broker_exit_open_blocked_reason(sym):
        return _iteration_result(
            status="blocked",
            blocked_by="broker_exit_pending",
            dependencies=dependencies,
            phases=phases,
        )

    phases.append("permission")
    permission = pre_trade_entry_blocked_reason()
    if not dependencies.simulation:
        return _iteration_result(
            status="blocked",
            blocked_by=permission or "production_path_has_no_simulation_context",
            dependencies=dependencies,
            phases=phases,
        )
    if permission is None:
        return _iteration_result(
            status="blocked",
            blocked_by="production_authorisation_refused_by_offline_seam",
            dependencies=dependencies,
            phases=phases,
        )

    if (
        dependencies.invoke_selector
        or dependencies.strategy_active_map is not None
        or dependencies.selector_error
    ):
        phases.append("strategy_selection")
        try:
            if dependencies.selector_error == "unavailable":
                raise ImportError(dependencies.selector_error)
            if dependencies.selector_error:
                raise RuntimeError(dependencies.selector_error)
            route = compute_indicators(_iteration_frame(candles))
            if dependencies.strategy_active_map is not None:
                from forex_bot.decision_repair.selection import select_deterministic

                chosen = select_deterministic(
                    sym,
                    route,
                    active_override=dependencies.strategy_active_map,
                    persist=False,
                )
                selected_name, lookback, horizon = chosen.selected, chosen.lookback, chosen.horizon
            else:
                selected_name, lookback, horizon = select_strategy(sym, route)
            _SHARED_EVIDENCE["selector_called"] = True
            _SHARED_EVIDENCE["selected_strategy"] = selected_name
            _SHARED_EVIDENCE["lookback"] = lookback
            _SHARED_EVIDENCE["horizon"] = horizon
        except ImportError:
            return _iteration_result(
                status="blocked",
                blocked_by="strategy_selection_unavailable",
                dependencies=dependencies,
                phases=phases,
            )
        except Exception:
            return _iteration_result(
                status="blocked",
                blocked_by="strategy_selection_error",
                dependencies=dependencies,
                phases=phases,
            )
        strategy_name, selector_block, active = _authoritative_strategy(
            selected_name,
            active_map=dependencies.strategy_active_map,
        )
        _SHARED_EVIDENCE["strategy_name"] = strategy_name
        if dependencies.strategy_name not in (None, "") and dependencies.strategy_name != strategy_name:
            _SHARED_EVIDENCE["supplied_strategy_ignored"] = dependencies.strategy_name
        if selector_block:
            return _iteration_result(
                status="blocked",
                blocked_by=selector_block,
                dependencies=dependencies,
                phases=phases,
            )
        known = True
        strat = strategies.get(strategy_name or "")
        authorised = bool(getattr(strat, "authorised_for_live", False)) if strat is not None else False
        safety_ready = False
    elif dependencies.strategy_name == "":
        strategy_name = None
        known = False
        active = False
        authorised = False
        safety_ready = False
    elif dependencies.strategy_name is None:
        strategy_name = "scalp"
        known = strategy_name in strategies
        strat = strategies.get(strategy_name)
        active = bool(strat.active) if strat is not None else False
        authorised = bool(getattr(strat, "authorised_for_live", False)) if strat is not None else False
        safety_ready = False
    else:
        strategy_name = dependencies.strategy_name
        known = (
            bool(dependencies.strategy_known)
            if dependencies.strategy_known is not None
            else strategy_name in strategies
        )
        active = bool(dependencies.strategy_active)
        authorised = bool(dependencies.strategy_authorised)
        safety_ready = (
            bool(dependencies.safety_initialised)
            if dependencies.safety_initialised is not None
            else False
        )
    phases.append("strategy")
    strategy_block = strategy_entry_block_reason(
        strategy_name,
        active=active,
        authorised_for_live=authorised,
        safety_initialised=safety_ready,
        known_strategy=known,
    )
    continued = continue_entry_after_strategy_gate(
        strategy_name,
        active=active,
        authorised_for_live=authorised,
        safety_initialised=safety_ready,
        known_strategy=known,
        sizer=None,
        builder=None,
        sender=None,
        id_factory=None,
    )
    if strategy_block or continued is None:
        return _iteration_result(
            status="blocked",
            blocked_by=strategy_block,
            dependencies=dependencies,
            phases=phases,
        )
    _SHARED_EVIDENCE["strategy_name"] = strategy_name

    phases.append("indicators")
    indicator_details: dict[str, Any] = {}
    try:
        frame_for_indicators = _iteration_frame(candles)
        computed = compute_indicators(frame_for_indicators)
        indicator_details["rows"] = int(len(computed))
        from forex_bot.session_rules import volatility_ok

        indicator_details["volatility_ok"] = bool(volatility_ok(computed))
    except Exception:
        return _iteration_result(
            status="blocked",
            blocked_by="indicator_failure",
            dependencies=dependencies,
            phases=phases,
        )
    if computed is None or getattr(computed, "empty", True):
        return _iteration_result(
            status="blocked",
            blocked_by="indicator_failure",
            dependencies=dependencies,
            phases=phases,
            details=indicator_details,
        )
    if not indicator_details["volatility_ok"]:
        return _iteration_result(
            status="blocked",
            blocked_by="volatility_unsafe",
            dependencies=dependencies,
            phases=phases,
            details=indicator_details,
        )
    phases.append("vote")
    if dependencies.vote_error and not dependencies.invoke_vote:
        return _iteration_result(
            status="blocked",
            blocked_by="ai_vote_provider_error",
            dependencies=dependencies,
            phases=phases,
        )
    vote_payload: dict[str, Any] = {"symbol": sym, "strategy": strategy_name}
    if not dependencies.missing_features:
        try:
            close = computed["close"]
            vote_payload.update(
                {
                    "price": float(close.iloc[-1]),
                    "ma_fast": float(computed["ma_fast"].iloc[-1]),
                    "ma_slow": float(computed["ma_slow"].iloc[-1]),
                    "sma_fast": float(computed["ma_fast"].iloc[-1]),
                    "sma_slow": float(computed["ma_slow"].iloc[-1]),
                    "returns": float(close.pct_change(fill_method=None).iloc[-1]) if len(computed) > 1 else 0.0,
                    "atr": float(computed["atr"].iloc[-1]),
                    "timeframe": "M5",
                }
            )
        except Exception:
            vote_payload = {"symbol": sym, "strategy": strategy_name}
    use_wrapper = (
        dependencies.invoke_vote
        or dependencies.vote is not None
        or dependencies.vote_timeout
        or bool(dependencies.vote_error)
        or bool(dependencies.extra_votes)
        or dependencies.empty_voters
    )
    vote: dict[str, Any] | None
    if use_wrapper:
        from forex_bot.ai_ensemble import AIEnsemble
        from forex_bot.ai_ensemble import ai as production_ai

        voter_error: BaseException | None = None
        if dependencies.vote_timeout:
            voter_error = TimeoutError("vote_timeout")
        elif dependencies.vote_error:
            voter_error = RuntimeError(dependencies.vote_error)
        try:
            if dependencies.empty_voters:
                vote = _drive_completed(AIEnsemble([]).vote(vote_payload, sym))
            elif dependencies.vote is None and voter_error is None and not dependencies.extra_votes:
                vote = _drive_completed(production_ai.vote(vote_payload, sym))
            else:
                voters = [_SuppliedVoter(dependencies.vote, voter_error)]
                voters.extend(_SuppliedVoter(item) for item in dependencies.extra_votes)
                vote = _drive_completed(AIEnsemble(voters).vote(vote_payload, sym))
                _SHARED_EVIDENCE["voter_calls"] = sum(item.calls for item in voters)
            _SHARED_EVIDENCE["vote_wrapper_called"] = True
        except Exception:
            _SHARED_EVIDENCE["vote_wrapper_called"] = True
            return _iteration_result(
                status="blocked",
                blocked_by="ai_vote_malformed",
                dependencies=dependencies,
                phases=phases,
            )
    else:
        vote = dependencies.vote
    if isinstance(dependencies.vote, dict) and dependencies.vote.get("allow"):
        if canonical_entry_direction(dependencies.vote.get("direction")) is None:
            return _iteration_result(
                status="blocked",
                blocked_by="invalid_entry_direction",
                dependencies=dependencies,
                phases=phases,
            )
    if not isinstance(vote, dict) or "allow" not in vote:
        return _iteration_result(
            status="blocked",
            blocked_by="ai_vote_unavailable",
            dependencies=dependencies,
            phases=phases,
        )
    confidence = vote.get("confidence")
    if isinstance(confidence, float) and (math.isnan(confidence) or math.isinf(confidence)):
        return _iteration_result(
            status="blocked",
            blocked_by="ai_vote_nonfinite",
            dependencies=dependencies,
            phases=phases,
        )
    if not vote.get("allow"):
        return _iteration_result(
            status="blocked",
            blocked_by="ai_vote_rejected",
            dependencies=dependencies,
            phases=phases,
        )

    phases.append("direction")
    _SHARED_EVIDENCE["ai_vote"] = {"allow": bool(vote.get("allow")), "direction": vote.get("direction")}
    direction = direction_action_gate(vote.get("direction"), None, None, None)
    if direction is None:
        return _iteration_result(
            status="blocked",
            blocked_by="invalid_entry_direction",
            dependencies=dependencies,
            phases=phases,
        )
    if dependencies.invoke_rl or dependencies.rl_agent is not None or dependencies.rl_error or dependencies.rl_timeout:
        phases.append("rl")
        try:
            if dependencies.rl_error:
                raise RuntimeError(dependencies.rl_error)
            state = rl_decision_state(computed)
            agent = dependencies.rl_agent if dependencies.rl_agent is not None else rl_agent
            rl_action = agent.decide(state)
            _SHARED_EVIDENCE["rl_veto_called"] = True
            _SHARED_EVIDENCE["rl_action"] = rl_action
            _SHARED_EVIDENCE["rl_state"] = state
            _SHARED_EVIDENCE["rl_confidence_absent"] = True
        except Exception:
            return _iteration_result(
                status="blocked",
                blocked_by="rl_error",
                dependencies=dependencies,
                phases=phases,
            )
        if dependencies.rl_timeout:
            return _iteration_result(
                status="blocked",
                blocked_by="rl_timeout",
                dependencies=dependencies,
                phases=phases,
            )
        if isinstance(rl_action, float) and (math.isnan(rl_action) or math.isinf(rl_action)):
            return _iteration_result(
                status="blocked",
                blocked_by="rl_output_nonfinite",
                dependencies=dependencies,
                phases=phases,
            )
        if rl_action in (None, ""):
            return _iteration_result(
                status="blocked",
                blocked_by="rl_output_missing",
                dependencies=dependencies,
                phases=phases,
            )
        if not isinstance(rl_action, str):
            return _iteration_result(
                status="blocked",
                blocked_by="rl_output_malformed",
                dependencies=dependencies,
                phases=phases,
            )
        if rl_action == "UNAVAILABLE":
            return _iteration_result(
                status="blocked",
                blocked_by="rl_state_unavailable",
                dependencies=dependencies,
                phases=phases,
            )
        if rl_action == "SKIP":
            return _iteration_result(
                status="blocked",
                blocked_by="rl_veto",
                dependencies=dependencies,
                phases=phases,
            )
        if rl_action not in ("BUY", "SELL"):
            return _iteration_result(
                status="blocked",
                blocked_by="rl_output_malformed",
                dependencies=dependencies,
                phases=phases,
            )
        if rl_action != direction:
            return _iteration_result(
                status="blocked",
                blocked_by="rl_direction_mismatch",
                dependencies=dependencies,
                phases=phases,
            )

    phases.append("provenance")
    frame = _iteration_frame(candles)
    provenance = decision_frame_rejection(frame, sym, now=dependencies.now)
    source_gap = ""
    phases.append("market_data")
    market_block = _market_entry_block(dependencies, candles, strategy_name=strategy_name)
    if market_block:
        return _iteration_result(
            status="blocked",
            blocked_by=market_block,
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            provenance=provenance,
            source_gap=source_gap,
        )

    phases.append("account")
    _SHARED_EVIDENCE["account_gate"] = True
    account_block, balance_value = _account_entry_block(dependencies)
    if account_block or balance_value is None:
        return _iteration_result(
            status="blocked",
            blocked_by=account_block or "account_missing",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            provenance=provenance,
            source_gap=source_gap,
        )
    accepted_equity = float(balance_value)
    _SHARED_EVIDENCE["accepted_equity"] = accepted_equity
    _SHARED_EVIDENCE["entry_equity_source"] = "accepted_snapshot"
    _SHARED_EVIDENCE["current_equity_used_for_entry"] = False
    _SHARED_EVIDENCE["equity_is_not_margin_proof"] = True
    _SHARED_EVIDENCE["margin_evidence"] = "not_implemented"
    _SHARED_EVIDENCE["margin_sufficiency"] = "NOT_EVALUATED"
    from forex_bot.decision_repair.flags import account_risk_enabled

    if account_risk_enabled():
        from forex_bot.decision_repair.account_risk import block_reason

        _SHARED_EVIDENCE["daily_loss_enabled"] = True
        _SHARED_EVIDENCE["drawdown_enabled"] = True
        _SHARED_EVIDENCE["risk_freshness"] = "not_evaluated"
        risk_block = block_reason(equity=accepted_equity, unrealised=dependencies.unrealised)
        _SHARED_EVIDENCE["risk_halt"] = risk_block or ""
        if risk_block:
            return _iteration_result(
                status="blocked",
                blocked_by=risk_block,
                dependencies=dependencies,
                phases=phases,
                direction=direction,
                provenance=provenance,
                source_gap=source_gap,
            )

    if dependencies.price is not None:
        try:
            injected = float(dependencies.price)
        except (TypeError, ValueError):
            injected = float("nan")
        if not math.isfinite(injected) or injected <= 0:
            return _iteration_result(
                status="blocked",
                blocked_by=provenance or "invalid_price",
                dependencies=dependencies,
                phases=phases,
                direction=direction,
                provenance=provenance,
                source_gap=source_gap,
            )
    snapshot = _unified_market_snapshot(dependencies, sym, direction or "", candles)
    if snapshot is None:
        return _iteration_result(
            status="blocked",
            blocked_by="quote_bid_missing" if dependencies.bid is None else "quote_ask_missing",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            provenance=provenance,
            source_gap=source_gap,
        )
    _SHARED_EVIDENCE["market_snapshot"] = snapshot
    _SHARED_EVIDENCE["entry_quote"] = _bound_entry_quote(snapshot)
    price = float(snapshot["price"])
    if dependencies.price is not None and not math.isclose(float(dependencies.price), price, rel_tol=0.0, abs_tol=1e-9):
        _SHARED_EVIDENCE["injected_price_not_used"] = True
    if not math.isfinite(float(price)) or float(price) <= 0:
        return _iteration_result(
            status="blocked",
            blocked_by=provenance or "invalid_price",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            provenance=provenance,
            source_gap=source_gap,
        )
    try:
        stop_distance = 0.001 if dependencies.stop_distance is None else float(dependencies.stop_distance)
    except (TypeError, ValueError):
        return _iteration_result(
            status="blocked",
            blocked_by="sizing_input_invalid",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            provenance=provenance,
            source_gap=source_gap,
        )
    if not math.isfinite(stop_distance):
        return _iteration_result(
            status="blocked",
            blocked_by="sizing_input_invalid",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            provenance=provenance,
            source_gap=source_gap,
        )
    if direction == "BUY":
        stop_price = float(price) - stop_distance
    else:
        stop_price = float(price) + stop_distance

    phases.append("sizing")
    _SHARED_EVIDENCE["sizing_invoked"] = True
    _SHARED_EVIDENCE["sizing_equity"] = accepted_equity
    from forex_bot.trading import (
        cap_position_units,
        portfolio_risk_cap_exceeded,
        position_sizing,
        stop_risk_account_ccy,
    )

    try:
        units = float(position_sizing(sym, float(price), float(stop_price), accepted_equity))
        unit_cap = _configured_unit_cap()
        _SHARED_EVIDENCE["unit_cap_enabled"] = unit_cap > 0
        if unit_cap > 0 and units > unit_cap:
            return _iteration_result(
                status="blocked",
                blocked_by="unit_cap",
                dependencies=dependencies,
                phases=phases,
                direction=direction,
                units=units,
                provenance=provenance,
                source_gap=source_gap,
            )
        units = float(cap_position_units(units))
    except (TypeError, ValueError):
        return _iteration_result(
            status="blocked",
            blocked_by="sizing_input_invalid",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            provenance=provenance,
            source_gap=source_gap,
        )
    if not math.isfinite(units):
        return _iteration_result(
            status="blocked",
            blocked_by="quantity_nonfinite",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=None,
            provenance=provenance,
            source_gap=source_gap,
        )
    if units <= 0:
        return _iteration_result(
            status="blocked",
            blocked_by="size_not_positive",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap or "non_positive_size_is_not_an_early_return_in_run_bot",
        )

    from forex_bot.portfolio_exposure import (
        account_ccy_to_usd,
        existing_gross_usd_by_symbol,
        notional_cap_decision,
        portfolio_gross_notional_pct_of_nav,
        usd_direction_guard_decision,
    )

    phases.append("risk")
    proposed = abs(float(units) * float(price))
    gross_pct = portfolio_gross_notional_pct_of_nav()
    _SHARED_EVIDENCE["gross_notional_enabled"] = gross_pct > 0
    if gross_pct > 0:
        pending_block, pending_gross = _pending_gross_usd()
        if pending_block:
            return _iteration_result(
                status="blocked",
                blocked_by=pending_block,
                dependencies=dependencies,
                phases=phases,
                direction=direction,
                units=units,
                provenance=provenance,
                source_gap=source_gap,
            )
        if not math.isfinite(float(proposed)):
            return _iteration_result(
                status="blocked",
                blocked_by="notional_nonfinite",
                dependencies=dependencies,
                phases=phases,
                direction=direction,
                units=units,
                provenance=provenance,
                source_gap=source_gap,
            )
        existing_gross = float(sum(existing_gross_usd_by_symbol().values())) + float(pending_gross)
        proposed_add = max(0.0, float(proposed))
        cap_usd = max(0.0, account_ccy_to_usd(accepted_equity * gross_pct))
        notional_exceeds = cap_usd > 0 and existing_gross + proposed_add > cap_usd + 1e-6
        _SHARED_EVIDENCE["notional_cap_equity"] = accepted_equity
        _SHARED_EVIDENCE["notional_cap_usd"] = cap_usd
        _SHARED_EVIDENCE["notional_resulting_usd"] = existing_gross + proposed_add
    else:
        notional_exceeds = bool(notional_cap_decision(proposed).get("exceeds"))
        _SHARED_EVIDENCE["notional_cap_equity"] = None
    _SHARED_EVIDENCE["portfolio_cap_equity"] = accepted_equity
    if notional_exceeds:
        return _iteration_result(
            status="blocked",
            blocked_by="notional_cap",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )
    new_risk = stop_risk_account_ccy(sym, float(price), abs(stop_distance), float(units))
    if portfolio_risk_cap_exceeded(accepted_equity, new_risk):
        return _iteration_result(
            status="blocked",
            blocked_by="portfolio_risk_cap",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )
    usd_decision = usd_direction_guard_decision(sym, direction)
    if usd_decision.get("exceeds"):
        return _iteration_result(
            status="blocked",
            blocked_by="usd_direction_guard",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )
    hard_provenance = {
        "nonfinite_price",
        "invalid_price",
        "missing_protected_column",
        "invalid_timestamp",
        "stale_bar",
        "future_timestamp",
    }
    if provenance in hard_provenance or (provenance and not dependencies.simulation):
        return _iteration_result(
            status="blocked",
            blocked_by=provenance,
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )

    from forex_bot.symbols import is_valid_oanda_forex_symbol, normalize_oanda_symbol

    instrument = normalize_oanda_symbol(sym)
    if not is_valid_oanda_forex_symbol(instrument):
        return _iteration_result(
            status="blocked",
            blocked_by="invalid_symbol",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )
    for label, stop_value in (("invalid_stop", dependencies.stop_loss), ("invalid_target", dependencies.take_profit)):
        if stop_value is None:
            continue
        try:
            parsed_stop = float(stop_value)
        except (TypeError, ValueError):
            return _iteration_result(
                status="blocked",
                blocked_by=label,
                dependencies=dependencies,
                phases=phases,
                direction=direction,
                units=units,
                provenance=provenance,
                source_gap=source_gap,
            )
        if not math.isfinite(parsed_stop):
            return _iteration_result(
                status="blocked",
                blocked_by=label,
                dependencies=dependencies,
                phases=phases,
                direction=direction,
                units=units,
                provenance=provenance,
                source_gap=source_gap,
            )
    if dependencies.client_order_id == "":
        return _iteration_result(
            status="blocked",
            blocked_by="missing_client_order_id",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )

    phases.append("eligibility")
    try:
        _seal_entry_gates(dependencies, strategy_name=strategy_name, direction=direction)
    except Exception:
        return _iteration_result(
            status="blocked",
            blocked_by="risk_gate_evaluation_failed",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )
    eligibility_block = _synthetic_dispatch_block()
    if eligibility_block:
        return _iteration_result(
            status="blocked",
            blocked_by=eligibility_block,
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )
    if not (dependencies.simulation and dependencies.account_context in (None, "isolated_test")):
        return _iteration_result(
            status="blocked",
            blocked_by="production_entry_ineligible",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )

    phases.append("account_reconciliation")
    from forex_bot.account_reconciliation import reconcile_for_entry

    risk_snapshot = dependencies.broker_snapshot
    risk_events = list(dependencies.broker_events or [])
    if dependencies.oanda_summary is not None:
        from forex_bot.oanda_account_adapter import normalize_oanda_risk_inputs

        adapter_reason, risk_snapshot, risk_events = normalize_oanda_risk_inputs(
            dependencies.oanda_summary,
            dependencies.oanda_transactions,
            expected_account_id=dependencies.expected_account_id,
            expected_currency=dependencies.expected_account_currency,
            now=dependencies.now,
        )
        _SHARED_EVIDENCE["oanda_adapter_checked"] = True
        _SHARED_EVIDENCE["oanda_adapter_block"] = adapter_reason or ""
        if adapter_reason:
            return _iteration_result(
                status="blocked",
                blocked_by=adapter_reason,
                dependencies=dependencies,
                phases=phases,
                direction=direction,
                units=units,
                provenance=provenance,
                source_gap=source_gap,
            )
    recon_reason, recon = reconcile_for_entry(
        now=dependencies.now,
        snapshot=risk_snapshot,
        events=risk_events,
        expected_account_id=dependencies.expected_account_id,
        expected_currency=dependencies.expected_account_currency,
    )
    _SHARED_EVIDENCE["account_reconciliation_checked"] = True
    _SHARED_EVIDENCE["account_reconciliation_block"] = recon_reason or ""
    _SHARED_EVIDENCE["reconciled_nav"] = recon.get("nav")
    _SHARED_EVIDENCE["risk_equity_source"] = "broker_nav" if recon.get("used_broker_nav") else "accepted_balance"
    if recon_reason:
        return _iteration_result(
            status="blocked",
            blocked_by=recon_reason,
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )
    risk_equity = float(recon["nav"]) if recon.get("used_broker_nav") else accepted_equity
    risk_unrealised = recon.get("unrealised") if recon.get("used_broker_nav") else dependencies.unrealised
    risk_as_of = recon.get("as_of") if recon.get("used_broker_nav") else dependencies.account_as_of

    phases.append("execution_risk")
    from forex_bot.execution_risk import entry_risk_block

    risk_reason, risk_details = entry_risk_block(
        now=dependencies.now,
        equity=risk_equity,
        unrealised=risk_unrealised,
        account_as_of=risk_as_of,
        symbol=sym,
        units=float(units),
        price=float(price),
    )
    _SHARED_EVIDENCE["execution_risk_checked"] = True
    _SHARED_EVIDENCE["execution_risk_block"] = risk_reason or ""
    _SHARED_EVIDENCE["existing_exposure"] = risk_details.get("existing_exposure")
    _SHARED_EVIDENCE["proposed_exposure"] = risk_details.get("proposed_exposure")
    _SHARED_EVIDENCE["exposure_cap"] = risk_details.get("exposure_cap")
    if risk_reason:
        return _iteration_result(
            status="blocked",
            blocked_by=risk_reason,
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
        )

    phases.append("reservation")
    if dependencies.persistence_failure:
        refuse_reservation_after_database_fault()
        return _iteration_result(
            status="blocked",
            blocked_by="reservation_persistence_failed",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            source_gap=source_gap,
            exposure_held=True,
            outcome=str(dependencies.persistence_failure or ""),
        )
    from forex_bot.orders import orders_by_client_id

    client_order_id = dependencies.client_order_id or generate_client_order_id()
    for existing in list(orders_by_client_id.values()):
        if existing.symbol == sym and reservation_status_block_reason(existing.status.value):
            return _iteration_result(
                status="blocked",
                blocked_by=reservation_status_block_reason(existing.status.value) or "active_reservation",
                dependencies=dependencies,
                phases=phases,
                direction=direction,
                units=units,
                provenance=provenance,
                source_gap=source_gap,
                exposure_held=True,
            )
    _SHARED_EVIDENCE["reservation_attempted"] = True
    reserved = try_begin_order_submission(
        client_order_id=client_order_id,
        symbol=sym,
        direction=direction,
        units=float(units),
        metadata={"simulation": True, "strategy": strategy_name},
    )
    if not reserved:
        return _iteration_result(
            status="blocked",
            blocked_by="reservation_refused",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            client_order_id=client_order_id,
            source_gap=source_gap,
            exposure_held=exposure_entry_block_reason(sym) is not None,
        )
    if dependencies.broker is None or not hasattr(dependencies.broker, "submit"):
        mark_order_failed_or_cancelled(client_order_id)
        return _iteration_result(
            status="blocked",
            blocked_by="no_isolated_simulation_broker",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            provenance=provenance,
            client_order_id=client_order_id,
            source_gap=source_gap,
        )

    phases.append("execution_adapter")
    production_adapter = production_execution_adapter
    if not dependencies.simulation:
        _ = production_adapter
        return _iteration_result(
            status="blocked",
            blocked_by="production_execution_adapter_withheld",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            client_order_id=client_order_id,
        )
    phases.append("fake_broker")
    request = broker_open_arguments(
        symbol=sym,
        units=float(units),
        direction=direction,
        client_order_id=client_order_id,
        stop_loss=None if dependencies.stop_loss is None else float(dependencies.stop_loss),
        take_profit=None if dependencies.take_profit is None else float(dependencies.take_profit),
        execution_kind="simulated",
        entry_quote=dict(_SHARED_EVIDENCE.get("entry_quote") or {}),
    )
    request["units"] = request["position_units"]
    request["reservation_id"] = client_order_id
    request["instrument"] = request["symbol"]
    request["simulation"] = True
    request["production_authorised"] = False
    request["adapter"] = "recording"
    try:
        _SHARED_EVIDENCE["adapter_called"] = True
        response = dependencies.broker.submit(request)
    except TimeoutError:
        response = {"kind": "timeout"}
    except ConnectionError:
        response = {"kind": "connection_failure"}
    except Exception:
        response = {"kind": "ambiguous"}
    finally:
        closer = getattr(dependencies.broker, "close", None)
        if closer is not None:
            closer()
    broker_requests = int(getattr(dependencies.broker, "request_count", 1) or 1)
    kind = response.get("kind") if isinstance(response, dict) else "malformed"
    phases.append(f"outcome:{kind}")

    def _held(outcome_name: str, *, blocked_by: str = "") -> dict[str, Any]:
        from forex_bot.orders import OrderStatus, orders_by_client_id, update_order

        note_unconfirmed_exposure(sym, client_order_id)
        restore_unresolved_intent(sym, client_order_id)
        current = orders_by_client_id.get(client_order_id)
        if current is not None and current.status == OrderStatus.PENDING:
            from forex_bot.database import update_exec_order_row

            update_exec_order_row(
                client_order_id=client_order_id,
                status="UNRESOLVED",
                metadata={"reason": "ambiguous_broker_outcome", "exposure_safety": "UNCONFIRMED"},
            )
            update_order(client_order_id, status=OrderStatus.UNRESOLVED, detail="ambiguous_broker_outcome")
        return _iteration_result(
            status="uncertain",
            blocked_by=blocked_by or kind,
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            broker_requests=broker_requests,
            provenance=provenance,
            client_order_id=client_order_id,
            exposure_held=True,
            source_gap=source_gap,
            outcome=outcome_name,
        )

    if not isinstance(response, dict) or not kind:
        return _held("malformed")
    if kind in {"timeout", "connection_failure", "ambiguous", "malformed"}:
        return _held(str(kind))
    if kind in {"rejected", "refused"}:
        mark_order_failed_or_cancelled(client_order_id)
        return _iteration_result(
            status="rejected",
            blocked_by="broker_rejected",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            broker_requests=broker_requests,
            provenance=provenance,
            client_order_id=client_order_id,
            source_gap=source_gap,
            outcome="rejected",
        )
    if kind == "accepted":
        return _iteration_result(
            status="accepted",
            blocked_by="",
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=units,
            broker_requests=broker_requests,
            provenance=provenance,
            client_order_id=client_order_id,
            exposure_held=exposure_entry_block_reason(sym) is not None,
            source_gap=source_gap,
            outcome="accepted",
        )
    if kind in {"filled", "partial", "duplicate_fill", "conflicting_quantity"}:
        filled_units = units
        if kind == "partial":
            filled_units = float(response.get("units") or 0.0)
        elif kind == "conflicting_quantity":
            return _held("conflicting_quantity", blocked_by="conflicting_fill_quantity")
        elif kind == "duplicate_fill":
            filled_units = float(response.get("units") or units)
        status = OrderStatus.PARTIAL if kind == "partial" or filled_units < units else OrderStatus.FILLED
        finalize_order_fill(
            client_order_id,
            broker_order_id=str(response.get("broker_order_id") or "SIMULATED"),
            fill_price=float(response.get("price") or price),
            units_filled=float(filled_units),
            status=status,
        )
        if dependencies.fail_position_record or filled_units <= 0:
            note_unconfirmed_exposure(sym, client_order_id)
            recorded = "blocked"
        else:
            recorded = record_synthetic_fill_position(
                symbol=sym,
                client_order_id=client_order_id,
                direction=direction,
                units=float(filled_units),
                price=float(response.get("price") or price),
            )
        if dependencies.reservation_update_failure:
            refuse_reservation_after_database_fault()
        if dependencies.reconciliation_token:
            source_gap = source_gap or "fake_reconciliation_token_ignored"
        return _iteration_result(
            status="filled" if status == OrderStatus.FILLED else "partial",
            blocked_by="" if recorded == "recorded" else recorded,
            dependencies=dependencies,
            phases=phases,
            direction=direction,
            units=filled_units,
            broker_requests=broker_requests,
            provenance=provenance,
            client_order_id=client_order_id,
            exposure_held=exposure_entry_block_reason(sym) is not None,
            source_gap=source_gap,
            outcome=recorded,
        )
    return _held("unclassified", blocked_by="ambiguous")


def _rows_from_loaded_frame(raw: Any) -> list[dict[str, Any]] | None:
    """Copy an already-loaded frame into plain rows. This does not fetch data."""
    if raw is None:
        return None
    try:
        columns = [name for name in ("open", "high", "low", "close", "time") if name in raw.columns]
        if not columns:
            return None
        rows: list[dict[str, Any]] = []
        for index in range(len(raw)):
            rows.append({name: raw.iloc[index][name] for name in columns})
        return rows or None
    except Exception:
        logger.exception("loaded frame could not be read for the shared decision")
        return None


def _production_iteration_dependencies(symbol: str, raw: Any, price: float | None) -> IterationDependencies:
    """Production inputs for one new-entry decision. No broker and no simulation."""
    _ = symbol
    parsed_price: float | None
    try:
        parsed_price = None if price is None else float(price)
    except (TypeError, ValueError):
        parsed_price = None
    return IterationDependencies(
        candles=_rows_from_loaded_frame(raw),
        price=parsed_price,
        simulation=False,
        now=datetime.now(timezone.utc),
        broker=None,
        invoke_selector=True,
        invoke_vote=True,
        invoke_rl=True,
        rl_agent=rl_agent,
    )


def dispatch_production_iteration(symbol: str, dependencies: IterationDependencies) -> dict[str, Any]:
    """One production iteration boundary. It delegates to the shared decision.

    This does not start ``run_bot``, sleep, or schedule another iteration.
    """
    result = evaluate_one_instrument_iteration(symbol, dependencies)
    result["production_dispatch"] = True
    result["shared_implementation"] = "evaluate_one_instrument_iteration"
    return result


async def _execute_bot_cycle(symbols) -> None:
    """One management cycle. Reconciliation stays in its own loop."""
    from forex_bot.oanda_client import fetch_account_summary

    await asyncio.to_thread(fetch_account_summary)
    await asyncio.to_thread(_refresh_pricing_snapshot)
    await _cycle_symbols(symbols)
    state_dict["last_bot_cycle_utc"] = datetime.now(timezone.utc).isoformat()
    record_operational_transition_if_changed()
    portfolio.update(
        {
            "equity": current_equity(),
            "sharpe": analytics.sharpe(),
            "drawdown": analytics.drawdown(),
            "winrate": analytics.winrate(),
            "win_rate_pct": analytics.win_rate_pct(),
        }
    )
    if live_window_log_enabled():
        log_live_windows(reason="cycle")
    _maybe_log_performance_metrics()
    evolve()
    daily_report()


async def run_startup_and_one_iteration(symbols, *, broker_view=None) -> dict:
    """Recover, then run one real management cycle. This does not loop."""
    from forex_bot.startup_recovery import execute_startup_sequence, load_startup_broker_view

    if broker_view is None:
        report = execute_startup_sequence(load_startup_broker_view())
    else:
        report = execute_startup_sequence(broker_view)
    await _execute_bot_cycle(symbols)
    return report


async def run_bot() -> None:
    try:
        await run_startup_and_one_iteration(Config.SYMBOLS)
    except Exception as exc:
        logger.exception("run_bot iteration error: %s", exc)
    while True:
        try:
            await _execute_bot_cycle(Config.SYMBOLS)
        except Exception as exc:
            logger.exception("run_bot iteration error: %s", exc)
        await asyncio.sleep(Config.TRADE_INTERVAL)
