"""FastAPI dashboard and process lifespan (bot task)."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Query
from fastapi.openapi.utils import get_openapi

from forex_bot.alerts import alert
from forex_bot.log_redact import redact_log_text
from forex_bot.ai_ensemble import ai as ai_ensemble
from forex_bot.analytics import analytics
from forex_bot.config import Config
from forex_bot.experiment import experiment_snapshot_with_voters
from forex_bot.execution import (
    broker_orders_enabled,
    effective_paper_trading,
    execution_mode_explicit,
    get_execution_mode,
    halt_trading,
    is_trading_halted_runtime,
    kill_switch_env_active,
    pre_trade_entry_allowed,
    pre_trade_entry_blocked_reason,
    resume_trading,
    trading_allowed,
)
from forex_bot.database import (
    fetch_all_trades_ordered,
    fetch_strategy_analysis,
    get_connection,
    release_connection_after_failed_startup,
)
from forex_bot.operational_events import (
    load_operational_events_cache_from_db,
    operational_events_payload,
    record_operational_transition_if_changed,
)
from forex_bot.operational_state import operational_state_payload
from forex_bot.session_rules import format_live_window_log, live_windows_status, log_live_windows
from forex_bot.state import (
    current_equity,
    mark_bot_started,
    mark_bot_stopped,
    set_lifecycle_message,
    set_lifespan_phase,
    state as bot_state,
)

logger = logging.getLogger(__name__)

_PRODUCTION_RECOVERY = object()
_CALL_RECOVERY = object()


class ReconciliationUnavailable(RuntimeError):
    """Market reconciliation could not run. Exposure holds stay in place."""


def _portfolio_metrics(equity: float) -> tuple[float, float]:
    from forex_bot.trading import configured_max_portfolio_risk_pct, portfolio_risk_fraction

    return portfolio_risk_fraction(equity), configured_max_portfolio_risk_pct()


def _oanda_client():
    from forex_bot import oanda_client

    return oanda_client


class StartupSafetyAbort(RuntimeError):
    """Startup stopped before database, broker, or background work."""


_last_cleanup_errors: list[str] = []


def startup_cleanup_errors() -> tuple[str, ...]:
    """Exception type names recorded by the latest lifespan cleanup."""
    return tuple(_last_cleanup_errors)


def _record_cleanup(secondary: list[BaseException], exc: BaseException) -> None:
    secondary.append(exc)
    logger.error("lifespan cleanup failed: %s", type(exc).__name__)


def _note_telegram_stop(status: object, notes: list[str]) -> None:
    """Record an incomplete Telegram stop without changing shutdown control.

    None means the callee supplied no documented status. Historical stubs and
    the pre-status contract return None. That is not treated as success and
    it is not treated as an incomplete stop.
    """
    if status in (None, "STOP_COMPLETED", "STOP_NOT_RUNNING"):
        return
    if status == "STOP_INCOMPLETE_WORKER_ALIVE":
        logger.warning(
            "D12-STOP-01 Telegram shutdown incomplete: "
            "polling worker remains alive after bounded join."
        )
        notes.append("D12-STOP-01")
        return
    logger.warning("D12-STOP-01 Telegram shutdown returned an unrecognised status.")
    notes.append("D12-STOP-UNKNOWN")


def _note_telegram_start(status: object) -> None:
    """Report a refused Telegram start without failing application startup.

    None means the callee supplied no documented start result. Historical
    stubs return None. That is not treated as success and it is not treated
    as a refusal.
    """
    if status in (
        None,
        "START_STARTED",
        "START_ALREADY_RUNNING",
        "START_DISABLED",
    ):
        return
    if status == "START_REFUSED_PREVIOUS_WORKER":
        logger.warning(
            "D12-START-01 Telegram startup refused: "
            "previous polling worker remains alive after shutdown request."
        )
        return
    if status == "START_FAILED":
        logger.warning("Telegram startup failed internally; trading continues.")
        return
    logger.warning("Telegram startup returned an unrecognised status.")


async def _await_owned_tasks(
    owned_tasks: list[asyncio.Task[Any]],
) -> list[BaseException]:
    """Cancel and await every task. One failure does not skip the others."""
    secondary: list[BaseException] = []
    for item in owned_tasks:
        item.cancel()
    for item in owned_tasks:
        try:
            await item
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            _record_cleanup(secondary, exc)
    return secondary


async def reconciliation_loop() -> None:
    """Periodic broker vs in-memory position comparison (log-only)."""
    from forex_bot.reconciliation import run_reconciliation_once

    while True:
        try:
            await asyncio.to_thread(run_reconciliation_once)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("reconciliation loop: %s", exc)
        interval = int((os.getenv("RECONCILE_INTERVAL_SEC") or "60").strip() or "60")
        await asyncio.sleep(max(10, interval))


async def health_snapshot_loop() -> None:
    """
    Same metrics as BOT STARTED (equity, sharpe, winrate, drawdown, symbols).

    HEALTH_SNAPSHOT_INTERVAL_SEC: seconds between snapshots; default 21600 (6h). Set 0 to disable.
    """
    while True:
        try:
            raw = (os.getenv("HEALTH_SNAPSHOT_INTERVAL_SEC") or "21600").strip() or "21600"
            interval = int(raw)
        except ValueError:
            interval = 21600
        if interval <= 0:
            return
        await asyncio.sleep(interval)
        try:
            msg = _health_alert_text("BOT STATUS")
            set_lifecycle_message(msg)
            alert(msg)
            logger.info(msg)
            if (os.getenv("LIVE_WINDOW_LOG") or "1").strip().lower() not in ("0", "false", "no", "off"):
                logger.info(format_live_window_log())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("health snapshot loop: %s", exc)


async def telegram_inbound_loop() -> None:
    """Legacy read-only /help /status poller. Skipped when telegram_control owns getUpdates."""
    from forex_bot.telegram_commands import handle_pending_updates, inbound_enabled, sync_command_menu

    commands_raw = (os.getenv("TELEGRAM_COMMANDS") or "1").strip().lower()
    if commands_raw not in ("0", "false", "no", "off"):
        return
    if not inbound_enabled():
        return
    try:
        await asyncio.to_thread(sync_command_menu)
    except Exception as exc:
        logger.warning("telegram command menu sync: %s", redact_log_text(exc))
    while True:
        try:
            await asyncio.to_thread(handle_pending_updates, lambda: _health_alert_text("BOT STATUS"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("telegram inbound: %s", redact_log_text(exc))
        await asyncio.sleep(2)


def _profit_factor_json(pf: float | None) -> float | str | None:
    if pf is None:
        return None
    if pf == float("inf"):
        return "inf"
    return round(float(pf), 4)


def _trading_metrics_payload() -> dict[str, Any]:
    wr = analytics.winrate()
    pf = analytics.profit_factor()
    eq = current_equity()
    risk_fraction, cap = _portfolio_metrics(eq)
    return {
        "equity": eq,
        "sharpe": analytics.sharpe(),
        # winrate: fraction 0..1 (0.54 == 54% wins). Do not append "%" without ×100.
        "winrate": wr,
        "win_rate_pct": round(analytics.win_rate_pct(), 2),
        "drawdown": analytics.drawdown(),
        "avg_win": round(analytics.avg_win(), 4),
        "avg_loss": round(analytics.avg_loss(), 4),
        "profit_factor": _profit_factor_json(pf),
        "portfolio_risk_pct": round(risk_fraction * 100.0, 2),
        "max_portfolio_risk_pct_cap": round(cap * 100.0, 2) if cap > 0 else 0.0,
        "trading_mode": Config.TRADING_MODE,
        "paper_trading": Config.PAPER_TRADING,
        "execution_mode": get_execution_mode().value,
        "effective_paper_trading": effective_paper_trading(),
        "broker_orders_enabled": broker_orders_enabled(),
        "sizing_note": (
            "If POSITION_NOTIONAL_PCT_OF_NAV>0, each new open is that fraction of broker NAV "
            "(face value), floored to whole OANDA units; else POSITION_RISK_PCT vs stop. "
            "Book cap: MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV of NAV in USD "
            "(inherits POSITION_NOTIONAL_PCT_OF_NAV if unset). "
            "Stop-risk book cap is separate (MAX_PORTFOLIO_RISK_PCT). "
            "TRADING_MODE only selects the OANDA host; EXECUTION_MODE selects fills."
        ),
    }


def _health_snapshot() -> dict[str, Any]:
    return {
        **_trading_metrics_payload(),
        "symbols": list(Config.SYMBOLS),
        "live_windows": live_windows_status(),
    }


def _system_snapshot() -> dict[str, Any]:
    """Single operational visibility payload (execution, broker, reconcile, loop)."""
    from forex_bot import positions as posmod
    from forex_bot.execution_metrics import snapshot as execution_metrics_snapshot
    from forex_bot.orders import orders_summary
    from forex_bot.portfolio_exposure import exposure_snapshot
    from forex_bot.live_safety import live_safety_snapshot
    from forex_bot.reconciliation import (
        get_reconciliation_snapshot,
        new_entries_allowed_by_reconcile,
        reconcile_gate_enforced,
    )

    return {
        "execution_mode": get_execution_mode().value,
        "execution_mode_explicit": execution_mode_explicit(),
        "effective_paper_trading": effective_paper_trading(),
        "broker_orders_enabled": broker_orders_enabled(),
        "trading_mode_oanda": Config.TRADING_MODE,
        "paper_trading_legacy": Config.PAPER_TRADING,
        "lifespan_phase": bot_state.get("lifespan_phase"),
        "trading_allowed": trading_allowed(),
        "new_entries_allowed_by_reconcile": new_entries_allowed_by_reconcile(),
        "effective_reconcile_gate": reconcile_gate_enforced(),
        "pre_trade_entry_allowed": pre_trade_entry_allowed(),
        "pre_trade_entry_blocked_reason": pre_trade_entry_blocked_reason(),
        "kill_switch_env": kill_switch_env_active(),
        "halted_runtime": is_trading_halted_runtime(),
        "reconciliation": get_reconciliation_snapshot(),
        "order_state_summary": orders_summary(),
        "execution_metrics": execution_metrics_snapshot(),
        "portfolio_exposure": exposure_snapshot(),
        "open_positions_count": len(posmod.positions),
        "last_bot_cycle_utc": bot_state.get("last_bot_cycle_utc"),
        "symbols": list(Config.SYMBOLS),
        "live_windows": live_windows_status(),
        "oanda_account": _oanda_client().last_account_summary() or None,
        **live_safety_snapshot(),
        **operational_state_payload(),
        **operational_events_payload(),
    }


def _health_alert_text(prefix: str) -> str:
    h = _health_snapshot()
    lw = h.get("live_windows") or {}
    insides = []
    for p in lw.get("symbols") or []:
        insides.append(f"{p['symbol']}={'IN' if p['inside'] else 'OUT'}")
    live_bit = (
        f" | live_tz={lw.get('timezone')} {lw.get('dst_label')} "
        f"offset={lw.get('utc_offset')} now_local={lw.get('now_local')} "
        f"{' '.join(insides)}"
    )
    return (
        f"{prefix} | host={h['trading_mode']} exec={h['execution_mode']} "
        f"broker_orders={h['broker_orders_enabled']} paper={h['effective_paper_trading']} | "
        f"equity={h['equity']:.2f} sharpe={h['sharpe']:.2f} "
        f"winrate={h['winrate']:.2%} drawdown={h['drawdown']:.2f} | "
        f"symbols={h['symbols']}"
        f"{live_bit}"
    )


def _serialize_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        t = d.get("time")
        if hasattr(t, "isoformat"):
            d["time"] = t.isoformat()
        out.append(d)
    return out


class StartupPorts:
    """Explicit startup dependencies. Production and offline callers supply their own."""

    def __init__(
        self,
        *,
        mode: str,
        validate_config: Callable[[], None],
        verify_safety: Callable[[], None],
        init_persistence: Callable[[], None],
        recover_orders: Callable[[], Any],
        recovery_rows: Any,
        recovery_readable: bool,
        init_broker: Callable[[], None],
        init_market_data: Callable[[], None],
        init_messaging: Callable[[], None],
        init_health: Callable[[], None],
        schedule_trading: Callable[[], str],
        close_opened: Callable[[list[str]], list[str]],
        symbols: Callable[[], list[str]],
        lifecycle: dict[str, Any] | None = None,
    ) -> None:
        self.mode = mode
        self.validate_config = validate_config
        self.verify_safety = verify_safety
        self.init_persistence = init_persistence
        self.recover_orders = recover_orders
        self.recovery_rows = recovery_rows
        self.recovery_readable = recovery_readable
        self.init_broker = init_broker
        self.init_market_data = init_market_data
        self.init_messaging = init_messaging
        self.init_health = init_health
        self.schedule_trading = schedule_trading
        self.close_opened = close_opened
        self.symbols = symbols
        self.lifecycle = lifecycle


class StartupReport:
    """Observable startup result. offline_ready is not permission to trade."""

    def __init__(self) -> None:
        self.phases: list[str] = []
        self.ok = False
        self.offline_ready = False
        self.trading_ready = False
        self.trading_loop_started = False
        self.error = ""
        self.cleanup_errors: list[str] = []
        self.exposure: dict[str, str | None] = {}
        self.reconciliation = "not_requested"
        self.historical_filled_gap = False


def _mark(report: StartupReport, phase: str) -> None:
    report.phases.append(phase)


async def _invoke(fn: Callable[[], Any]) -> Any:
    result = fn()
    if hasattr(result, "__await__"):
        result = await result
    return result


def _evaluate_startup_exposure(symbols: list[str]) -> dict[str, str | None]:
    from forex_bot.database import exposure_entry_block_reason

    return {symbol: exposure_entry_block_reason(symbol) for symbol in symbols}


async def initialise_application(ports: StartupPorts) -> StartupReport:
    """Run startup orchestration with the caller's dependencies.

    The offline mode never starts the trading loop. trading_ready stays false.
    """
    report = StartupReport()
    opened: list[str] = []
    _mark(report, "created")
    if ports.lifecycle is not None:
        if ports.lifecycle.get("stopped") and not ports.lifecycle.get("allow_after_shutdown"):
            report.error = "StartupSafetyAbort"
            _mark(report, "shutdown_completed")
            exc = StartupSafetyAbort("initialization after shutdown")
            setattr(exc, "startup_report", report)
            raise exc
        if ports.lifecycle.get("started") and not ports.lifecycle.get("allow_repeat"):
            report.error = "StartupSafetyAbort"
            _mark(report, "shutdown_completed")
            exc = StartupSafetyAbort("duplicate initialization")
            setattr(exc, "startup_report", report)
            raise exc
    try:
        await _invoke(ports.validate_config)
        _mark(report, "configuration_validated")
        await _invoke(ports.verify_safety)
        _mark(report, "safety_defaults_verified")
        await _invoke(ports.init_persistence)
        opened.append("persistence")
        _mark(report, "persistence_initialized")
        from forex_bot.database import select_rows_for_recovery
        from forex_bot.orders import ingest_recovery_snapshot

        if ports.recovery_rows is _PRODUCTION_RECOVERY:
            await _invoke(ports.recover_orders)
        elif ports.recovery_rows is _CALL_RECOVERY:
            provided = await _invoke(ports.recover_orders)
            ingest_recovery_snapshot(
                select_rows_for_recovery(provided),
                ports.recovery_readable,
            )
        else:
            ingest_recovery_snapshot(
                select_rows_for_recovery(ports.recovery_rows),
                ports.recovery_readable,
            )
        _mark(report, "order_recovery_completed")
        report.exposure = _evaluate_startup_exposure(ports.symbols())
        _mark(report, "exposure_safety_evaluated")
        await _invoke(ports.init_broker)
        opened.append("broker")
        _mark(report, "broker_dependency_initialized")
        try:
            await _invoke(ports.init_market_data)
        except ReconciliationUnavailable as exc:
            report.reconciliation = type(exc).__name__
        else:
            report.reconciliation = "completed"
        opened.append("market_data")
        _mark(report, "market_data_dependency_initialized")
        await _invoke(ports.init_messaging)
        opened.append("messaging")
        _mark(report, "messaging_dependency_initialized")
        await _invoke(ports.init_health)
        opened.append("health")
        _mark(report, "health_dependencies_prepared")
        schedule_status = await _invoke(ports.schedule_trading)
        if ports.mode == "offline":
            if schedule_status != "recorded_not_started":
                raise StartupSafetyAbort("offline scheduler returned an unsafe status")
            report.trading_loop_started = False
            report.trading_ready = False
            report.offline_ready = True
            report.ok = True
            _mark(report, "offline_initialization_ready")
        else:
            if schedule_status != "started":
                raise StartupSafetyAbort("production scheduler did not start")
            report.trading_loop_started = True
            report.trading_ready = False
            report.offline_ready = False
            report.ok = True
            _mark(report, "running")
        if ports.lifecycle is not None:
            ports.lifecycle["started"] = True
        return report
    except Exception as exc:
        report.ok = False
        report.offline_ready = False
        report.trading_ready = False
        report.trading_loop_started = False
        report.error = type(exc).__name__
        setattr(exc, "startup_report", report)
        if ports.mode == "offline":
            try:
                report.cleanup_errors = list(ports.close_opened(list(reversed(opened))))
            except Exception as cleanup_exc:
                report.cleanup_errors.append(type(cleanup_exc).__name__)
            _mark(report, "shutdown_completed")
            if ports.lifecycle is not None:
                ports.lifecycle["stopped"] = True
        raise


def shutdown_application(ports: StartupPorts, report: StartupReport) -> StartupReport:
    """Close an offline initialization. Repeated calls stay safe."""
    try:
        report.cleanup_errors.extend(
            ports.close_opened(
                ["scheduler", "health", "messaging", "market_data", "broker", "persistence"]
            )
        )
    except Exception as exc:
        report.cleanup_errors.append(type(exc).__name__)
    report.offline_ready = False
    report.trading_ready = False
    _mark(report, "shutdown_completed")
    if ports.lifecycle is not None:
        ports.lifecycle["stopped"] = True
        ports.lifecycle["started"] = False
    return report


def _production_startup_ports(
    owned_tasks: list[asyncio.Task[Any]],
    telegram_flag: dict[str, bool],
) -> StartupPorts:
    def validate_config() -> None:
        symbols = list(Config.SYMBOLS)
        if not symbols:
            raise StartupSafetyAbort("startup configuration has no symbols")

    def verify_safety() -> None:
        from forex_bot.live_safety import (
            initialise_fail_closed,
            live_order_auth_reason,
            live_safety_initialised,
        )

        initialise_fail_closed()
        if not live_safety_initialised():
            reason = live_order_auth_reason()
            logger.error(
                "startup aborted: safety state is not startup-compatible reason=%s",
                reason,
            )
            raise StartupSafetyAbort(
                "startup aborted: safety state is not startup-compatible "
                f"reason={reason}"
            )

    def init_persistence() -> None:
        set_lifespan_phase("starting")
        get_connection()

    def recover_orders() -> Any:
        from forex_bot.orders import load_open_orders_from_db_into_memory
        from forex_bot.reconciliation import load_reconcile_state_from_db

        load_open_orders_from_db_into_memory()
        load_reconcile_state_from_db()
        return None

    def init_broker() -> None:
        _oanda_client().build_api()

    def init_market_data() -> Any:
        async def _run() -> None:
            from forex_bot.reconciliation import run_reconciliation_once

            try:
                await asyncio.to_thread(_oanda_client().fetch_account_summary)
            except Exception as exc:
                logger.warning("startup AccountSummary: %s", exc)
            try:
                await asyncio.to_thread(run_reconciliation_once)
            except Exception as exc:
                logger.warning("startup reconciliation: %s", exc)

        return _run()

    def init_messaging() -> None:
        return None

    def init_health() -> None:
        from forex_bot.execution import (
            ExecutionMode,
            get_execution_mode,
            pre_trade_entry_blocked_reason,
        )

        if get_execution_mode() != ExecutionMode.PAPER:
            reason = pre_trade_entry_blocked_reason()
            if reason:
                logger.warning(
                    "startup: new entries blocked by policy until conditions clear (%s) — see GET /system",
                    reason,
                )

    def schedule_trading() -> str:
        from forex_bot.bot_loop import run_bot
        from forex_bot.telegram_control import start_telegram_control

        mark_bot_started()
        set_lifespan_phase("running")
        load_operational_events_cache_from_db()
        started_msg = _health_alert_text("BOT STARTED")
        set_lifecycle_message(started_msg)
        alert(started_msg)
        logger.info("Bot started; trading_mode=%s", Config.TRADING_MODE)
        log_live_windows(reason="startup")
        owned_tasks.append(asyncio.create_task(reconciliation_loop()))
        owned_tasks.append(asyncio.create_task(health_snapshot_loop()))
        owned_tasks.append(asyncio.create_task(telegram_inbound_loop()))
        owned_tasks.append(asyncio.create_task(run_bot()))
        telegram_flag["attempted"] = True
        _note_telegram_start(start_telegram_control())
        return "started"

    def close_opened(_names: list[str]) -> list[str]:
        return []

    return StartupPorts(
        mode="production",
        validate_config=validate_config,
        verify_safety=verify_safety,
        init_persistence=init_persistence,
        recover_orders=recover_orders,
        recovery_rows=_PRODUCTION_RECOVERY,
        recovery_readable=True,
        init_broker=init_broker,
        init_market_data=init_market_data,
        init_messaging=init_messaging,
        init_health=init_health,
        schedule_trading=schedule_trading,
        close_opened=close_opened,
        symbols=lambda: [str(item) for item in Config.SYMBOLS],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    _last_cleanup_errors.clear()
    from forex_bot.log_config import configure_forex_bot_logging

    configure_forex_bot_logging()
    owned_tasks: list[asyncio.Task[Any]] = []
    telegram_flag = {"attempted": False}
    startup_failure: BaseException | None = None
    body_error = False
    secondary: list[BaseException] = []
    release_notes: list[str] = []
    telegram_stop_notes: list[str] = []
    try:
        await initialise_application(_production_startup_ports(owned_tasks, telegram_flag))
    except Exception as exc:  # noqa: BLE001
        startup_failure = exc
        raise
    else:
        try:
            yield
        except Exception:  # noqa: BLE001
            body_error = True
            raise
    finally:
        telegram_stop_failed = False
        if telegram_flag["attempted"]:
            try:
                from forex_bot.telegram_control import stop_telegram_control

                stop_status = stop_telegram_control()
            except Exception as exc:  # noqa: BLE001
                telegram_stop_failed = True
                _record_cleanup(secondary, exc)
            else:
                _note_telegram_stop(stop_status, telegram_stop_notes)
        if startup_failure is None:
            set_lifespan_phase("stopping")
        secondary.extend(await _await_owned_tasks(owned_tasks))
        if startup_failure is not None and not telegram_stop_failed:
            release_notes.extend(release_connection_after_failed_startup())
            for note in release_notes:
                logger.error("lifespan cleanup failed: %s", note)
        if startup_failure is None:
            try:
                mark_bot_stopped()
                set_lifespan_phase("offline")
                stopped_msg = _health_alert_text("BOT STOPPED")
                set_lifecycle_message(stopped_msg)
                alert(stopped_msg)
                logger.info("Bot stopped (lifespan shutdown)")
            except Exception as exc:  # noqa: BLE001
                _record_cleanup(secondary, exc)
        _last_cleanup_errors[:] = [type(item).__name__ for item in secondary]
        _last_cleanup_errors.extend(release_notes)
        _last_cleanup_errors.extend(telegram_stop_notes)
        current = asyncio.current_task()
        cancelling = current is not None and current.cancelling() > 0
        if (
            startup_failure is None
            and not body_error
            and not cancelling
            and secondary
        ):
            raise secondary[0]


app = FastAPI(
    title="Final Boss Forex Bot",
    description="Live/Paper OANDA workflow, indicators, AI ensemble stub, PostgreSQL logging.",
    lifespan=lifespan,
)


@app.get(
    "/health",
    tags=["Status"],
    operation_id="get_health",
    summary="Liveness and bot flags",
)
async def health() -> dict[str, Any]:
    """Liveness probe; includes bot run state for dashboards (OANDA/DB not verified)."""
    return {
        "status": "ok",
        "bot": bot_state.get("bot_status", "unknown"),
        "started_at": bot_state.get("bot_started_at"),
        "paper_trading": Config.PAPER_TRADING,
        "trading_mode": Config.TRADING_MODE,
        "execution_mode": get_execution_mode().value,
        "trading_allowed": trading_allowed(),
        "live_windows": live_windows_status(),
        "oanda_account": _oanda_client().last_account_summary() or None,
        "experiment": experiment_snapshot_with_voters(ai_ensemble),
    }


@app.get(
    "/status",
    tags=["Status"],
    operation_id="get_status",
    summary="Full status snapshot",
)
async def status() -> dict[str, Any]:
    """Full system status for dashboard / monitoring."""
    snap = _health_snapshot()
    return {
        "bot": bot_state.get("bot_status", "unknown"),
        "started_at": bot_state.get("bot_started_at"),
        "stopped_at": bot_state.get("bot_stopped_at"),
        "last_lifecycle_message": bot_state.get("last_lifecycle_message", ""),
        "health": snap,
        "experiment": experiment_snapshot_with_voters(ai_ensemble),
        "system": _system_snapshot(),
    }


@app.get(
    "/system",
    tags=["Status"],
    operation_id="get_system_snapshot",
    summary="Operational snapshot (execution, OANDA mode, reconcile, positions, last cycle)",
)
async def system_endpoint() -> dict[str, Any]:
    return _system_snapshot()


@app.get(
    "/experiment",
    tags=["Status"],
    operation_id="get_experiment",
    summary="A/B flags: ensemble mode (quant vs API vs hybrid) and nn_pred mode",
)
async def experiment_endpoint() -> dict[str, Any]:
    """Quant vs LLM vs hybrid configuration for comparing runs (same env as backtest when aligned)."""
    return experiment_snapshot_with_voters(ai_ensemble)


@app.get(
    "/metrics",
    tags=["Status"],
    operation_id="get_metrics",
    summary="Equity and risk metrics",
)
async def metrics() -> dict[str, Any]:
    return _trading_metrics_payload()


@app.get(
    "/replay",
    tags=["Trades & analytics"],
    operation_id="get_trade_replay",
    summary="All logged trades (newest first)",
)
async def replay() -> list[dict[str, Any]]:
    return _serialize_trades(fetch_all_trades_ordered())


@app.get(
    "/strategy-analysis",
    tags=["Trades & analytics"],
    operation_id="get_strategy_analysis",
    summary="Per-strategy stats from the database",
    response_description="List of strategy aggregate rows (Sharpe, PnL, etc.).",
)
async def strategy_analysis() -> list[dict[str, Any]]:
    """Returns analytics grouped by strategy name (not related to OANDA mode or `/set_mode`)."""
    return fetch_strategy_analysis()


class OandaEnvMode(str, Enum):
    """OANDA REST environment (market data / API host), not paper PnL."""

    live = "live"
    practice = "practice"


def _apply_trading_mode(mode: str) -> dict[str, str]:
    try:
        Config.set_trading_mode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _oanda_client().build_api()
    alert(f" Trading mode changed to {Config.TRADING_MODE.upper()}")
    return {"status": "success", "mode": Config.TRADING_MODE}


@app.get(
    "/set_mode",
    tags=["Configuration"],
    operation_id="get_set_trading_mode",
    summary="Switch OANDA mode (GET — recommended in ReDoc)",
    description=(
        "No request body. Set **mode** to `live` or `practice` in the query dropdown. "
        "Example: `/set_mode?mode=practice`"
    ),
)
async def set_mode_get(
    mode: OandaEnvMode = Query(..., description="OANDA API environment"),
) -> dict[str, str]:
    return _apply_trading_mode(mode.value)


@app.post(
    "/set_mode",
    tags=["Configuration"],
    operation_id="post_set_trading_mode",
    summary="Switch OANDA mode (POST — query only, no JSON body)",
    description=(
        "ReDoc often sends an empty JSON body on POST, which breaks optional-body handlers. "
        "This route uses **only** the query parameter `mode` — leave the body empty / do not send JSON."
    ),
)
async def set_mode_post(
    mode: OandaEnvMode = Query(..., description="OANDA API environment"),
) -> dict[str, str]:
    return _apply_trading_mode(mode.value)


@app.post(
    "/halt",
    tags=["Configuration"],
    operation_id="post_halt_trading",
    summary="Halt new entries (in-process; does not set KILL_SWITCH env)",
)
async def halt_endpoint() -> dict[str, str]:
    halt_trading()
    alert("TRADING HALTED via POST /halt (new opens blocked; closes still run)")
    return {"status": "halted"}


@app.post(
    "/resume",
    tags=["Configuration"],
    operation_id="post_resume_trading",
    summary="Clear in-process halt from POST /halt",
)
async def resume_endpoint() -> dict[str, str]:
    if (os.getenv("RECONCILE_ON_RESUME") or "").strip().lower() in ("1", "true", "yes", "on"):
        from forex_bot.reconciliation import run_reconciliation_once

        try:
            await asyncio.to_thread(run_reconciliation_once)
        except Exception as exc:
            logger.warning("reconcile on resume failed: %s", exc)
    resume_trading()
    alert("TRADING RESUMED via POST /resume")
    return {"status": "resumed"}


def custom_openapi() -> dict[str, Any]:
    """Drop 422 from the published schema so ReDoc/Swagger do not show the ValidationError block."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description=app.description,
        routes=app.routes,
    )
    for path_item in openapi_schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            op_item = path_item.get(method)
            if not isinstance(op_item, dict):
                continue
            responses = op_item.get("responses")
            if isinstance(responses, dict):
                responses.pop("422", None)
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]
