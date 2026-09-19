"""Inbound Telegram commands and persistent control buttons.

Polling runs on a daemon thread (same idea as :mod:`forex_bot.alerts`) so
``getUpdates`` cannot block the event loop or delay OrderCreate. Only the
configured ``TELEGRAM_CHAT_ID`` (plus optional ``TELEGRAM_ALLOWED_CHAT_IDS``)
is authorized.

Start / Stop map to the existing in-process halt/resume gates (same as
``POST /halt`` and ``POST /resume``). They do **not** stop the FastAPI process
or flatten positions.

Disable with ``TELEGRAM_COMMANDS=0``. Requires the same token + chat id as alerts.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests

from forex_bot.config import Config

logger = logging.getLogger(__name__)

_LABEL_PREFIX = re.compile(r"^[^\w/]+", re.UNICODE)

REPLY_BUTTON_ROWS: list[list[str]] = [
    ["📊 P/L", "📉 Drawdown", "📈 Status"],
    ["▶️ Start", "⏹ Stop", "💼 Positions"],
    ["🏦 Account", "⚙️ System", "🪟 Windows"],
    ["📋 Metrics", "📜 Trades", "🧯 Risk"],
    ["🧪 Experiment", "🔄 Reconcile", "❓ Help"],
]

BOT_COMMANDS: list[tuple[str, str]] = [
    ("help", "Show control buttons and command list"),
    ("pnl", "Current realized + unrealized P/L"),
    ("drawdown", "Peak-to-trough equity drawdown"),
    ("status", "Bot status, gates, and health"),
    ("start_trading", "Resume new entries (same as POST /resume)"),
    ("stop", "Halt new entries (same as POST /halt)"),
    ("positions", "Open positions and mark-to-market"),
    ("account", "Cached OANDA account / NAV"),
    ("system", "Operational snapshot"),
    ("windows", "Live trading windows"),
    ("metrics", "Equity, Sharpe, win rate, risk"),
    ("trades", "Recent closed trades"),
    ("risk", "Portfolio exposure and risk caps"),
    ("experiment", "Ensemble / execution experiment flags"),
    ("reconcile", "Last broker reconcile snapshot"),
    ("mode", "OANDA host + execution mode (read-only)"),
    ("ping", "Confirm the command listener is alive"),
]

_COMMAND_ALIASES: dict[str, str] = {
    "start": "menu",
    "help": "help",
    "menu": "menu",
    "commands": "help",
    "pnl": "pnl",
    "pl": "pnl",
    "p/l": "pnl",
    "profit": "pnl",
    "profits": "pnl",
    "drawdown": "drawdown",
    "dd": "drawdown",
    "status": "status",
    "health": "status",
    "start_trading": "start_trading",
    "resume": "start_trading",
    "unhalt": "start_trading",
    "stop": "stop",
    "halt": "stop",
    "pause": "stop",
    "positions": "positions",
    "pos": "positions",
    "position": "positions",
    "opens": "positions",
    "account": "account",
    "nav": "account",
    "balance": "account",
    "system": "system",
    "ops": "system",
    "windows": "windows",
    "window": "windows",
    "session": "windows",
    "sessions": "windows",
    "metrics": "metrics",
    "perf": "metrics",
    "performance": "metrics",
    "trades": "trades",
    "replay": "trades",
    "history": "trades",
    "risk": "risk",
    "exposure": "risk",
    "experiment": "experiment",
    "ensemble": "experiment",
    "reconcile": "reconcile",
    "reconciliation": "reconcile",
    "mode": "mode",
    "ping": "ping",
}

_poller_lock = threading.Lock()
_poller_started = False
_stop_event = threading.Event()
_offset = 0
_commands_registered = False


@dataclass(frozen=True)
class CommandReply:
    text: str
    show_inline_panel: bool = False


def _env_flag(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def _env_timeout(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1.0, float(raw))
    except ValueError:
        return default


def telegram_configured() -> bool:
    token = (Config.TELEGRAM_TOKEN or "").strip()
    chat_id = (Config.TELEGRAM_CHAT_ID or "").strip()
    return bool(token and chat_id)


def commands_enabled() -> bool:
    return telegram_configured() and _env_flag("TELEGRAM_COMMANDS", True)


def allowed_chat_ids() -> set[str]:
    ids = {(Config.TELEGRAM_CHAT_ID or "").strip()}
    extra = (os.getenv("TELEGRAM_ALLOWED_CHAT_IDS") or "").strip()
    if extra:
        ids.update(part.strip() for part in extra.split(",") if part.strip())
    ids.discard("")
    return ids


def is_authorized_chat(chat_id: Any) -> bool:
    if chat_id is None:
        return False
    return str(chat_id).strip() in allowed_chat_ids()


def reply_keyboard_markup() -> dict[str, Any]:
    return {
        "keyboard": [[{"text": cell} for cell in row] for row in REPLY_BUTTON_ROWS],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def inline_keyboard_markup() -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    callback_for = {
        "📊 P/L": "pnl",
        "📉 Drawdown": "drawdown",
        "📈 Status": "status",
        "▶️ Start": "start_trading",
        "⏹ Stop": "stop",
        "💼 Positions": "positions",
        "🏦 Account": "account",
        "⚙️ System": "system",
        "🪟 Windows": "windows",
        "📋 Metrics": "metrics",
        "📜 Trades": "trades",
        "🧯 Risk": "risk",
        "🧪 Experiment": "experiment",
        "🔄 Reconcile": "reconcile",
        "❓ Help": "help",
    }
    for row in REPLY_BUTTON_ROWS:
        rows.append(
            [{"text": label, "callback_data": callback_for[label]} for label in row]
        )
    return {"inline_keyboard": rows}


def normalize_command(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    is_slash = raw.startswith("/")
    if is_slash:
        raw = raw[1:]
        raw = raw.split("@", 1)[0]
        raw = raw.split(None, 1)[0]
    raw = raw.strip().lower()
    start_label = REPLY_BUTTON_ROWS[1][0].strip().lower()
    # Persistent keyboard "▶️ Start" must resume. Telegram /start still opens the menu.
    if not is_slash and raw == start_label:
        return "start_trading"
    stripped = _LABEL_PREFIX.sub("", raw).strip()
    if is_slash:
        return _COMMAND_ALIASES.get(stripped, stripped)
    if stripped == "start":
        return "start_trading"
    return _COMMAND_ALIASES.get(stripped, stripped)


def _signed(value: float, digits: int = 2) -> str:
    return f"{value:+.{digits}f}"


def _num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _pf_text(pf: float | None) -> str:
    if pf is None:
        return "n/a"
    if pf == float("inf"):
        return "inf"
    return f"{float(pf):.2f}"


def _open_mtm() -> tuple[float | None, list[str]]:
    from forex_bot import positions as posmod
    from forex_bot.state import last_mid
    from forex_bot.trading import calculate_pnl

    lines: list[str] = []
    total = 0.0
    have = False
    missing = 0
    for sym, pos in sorted(posmod.positions.items()):
        mid = last_mid(sym)
        age = max(0.0, time.time() - float(pos.open_time or 0.0))
        kind = (pos.execution_kind or "?").strip() or "?"
        if mid is None or mid <= 0:
            missing += 1
            lines.append(
                f"{sym} {pos.direction} {pos.units:.2f}u entry={pos.entry_price:.5f} "
                f"mtm=n/a kind={kind} age={age:.0f}s"
            )
            continue
        pnl = float(calculate_pnl(pos, mid))
        total += pnl
        have = True
        lines.append(
            f"{sym} {pos.direction} {pos.units:.2f}u entry={pos.entry_price:.5f} "
            f"mid={mid:.5f} mtm={_signed(pnl, 5)} kind={kind} age={age:.0f}s"
        )
    if not have:
        return (None if missing else 0.0), lines
    return total, lines


def cmd_help() -> CommandReply:
    buttons = " | ".join(cell for row in REPLY_BUTTON_ROWS for cell in row)
    slashes = " ".join(f"/{name}" for name, _desc in BOT_COMMANDS)
    text = (
        "Final Boss Telegram control\n"
        "Buttons stay at the bottom of the chat. Slash commands work too.\n"
        "\n"
        f"Buttons: {buttons}\n"
        f"Commands: {slashes}\n"
        "\n"
        "▶️ Start / /start_trading / /resume = allow new entries (POST /resume).\n"
        "⏹ Stop / /stop / /halt = block new entries (POST /halt). Closes still run.\n"
        "/start and ❓ Help only show this menu — they do not start trading.\n"
        "Start/Stop never shut down the process or flatten positions.\n"
        "Only the configured TELEGRAM_CHAT_ID can use these controls."
    )
    return CommandReply(text, show_inline_panel=True)


def cmd_menu() -> CommandReply:
    return cmd_help()


def cmd_ping() -> CommandReply:
    return CommandReply("pong — Telegram commands are live. Trading loop is unchanged.")


def cmd_pnl() -> CommandReply:
    from forex_bot import positions as posmod
    from forex_bot.analytics import analytics
    from forex_bot.config import Config as Cfg
    from forex_bot.state import current_equity

    realized = float(sum(analytics.trades))
    closed_n = len(analytics.trades)
    equity = float(current_equity())
    base = float(Cfg.BASE_BALANCE)
    session = equity - base
    unrealized, _lines = _open_mtm()
    u_txt = "n/a (no mid yet)" if unrealized is None else _signed(unrealized, 5)
    total = None if unrealized is None else realized + unrealized
    total_txt = "n/a" if total is None else _signed(total, 5)
    text = (
        "📊 Current P/L\n"
        f"Equity: {_num(equity)}\n"
        f"Base: {_num(base)}\n"
        f"Equity vs base: {_signed(session)}\n"
        f"Realized (closed): {_signed(realized, 5)} ({closed_n} trades)\n"
        f"Unrealized (open): {u_txt}\n"
        f"Realized + unrealized: {total_txt}\n"
        f"Open positions: {len(posmod.positions)}\n"
        f"Drawdown: {_num(float(analytics.drawdown()))}"
    )
    return CommandReply(text)


def cmd_drawdown() -> CommandReply:
    from forex_bot.analytics import analytics
    from forex_bot.state import current_equity

    dd = float(analytics.drawdown())
    text = (
        "📉 Drawdown\n"
        f"Max peak-to-trough: {_num(dd)}\n"
        f"Closed trades used: {len(analytics.trades)}\n"
        f"Current equity: {_num(float(current_equity()))}\n"
        "Drawdown is the largest drop of base + cumulative closed-trade PnL."
    )
    return CommandReply(text)


def cmd_status() -> CommandReply:
    from forex_bot import positions as posmod
    from forex_bot.analytics import analytics
    from forex_bot.execution import (
        broker_orders_enabled,
        effective_paper_trading,
        get_execution_mode,
        is_trading_halted_runtime,
        kill_switch_env_active,
        pre_trade_entry_allowed,
        pre_trade_entry_blocked_reason,
        trading_allowed,
    )
    from forex_bot.operational_state import operational_state_payload
    from forex_bot.state import current_equity, state

    ops = operational_state_payload()
    blocked = pre_trade_entry_blocked_reason() or "none"
    text = (
        "📈 Status\n"
        f"Bot: {state.get('bot_status', 'unknown')}  phase={state.get('lifespan_phase')}\n"
        f"Operational: {ops.get('operational_state')} — {ops.get('operational_state_detail')}\n"
        f"Host={Config.TRADING_MODE} exec={get_execution_mode().value} "
        f"broker_orders={broker_orders_enabled()} paper={effective_paper_trading()}\n"
        f"Trading allowed (new entries): {trading_allowed()}\n"
        f"Pre-trade gate: {pre_trade_entry_allowed()}  blocked={blocked}\n"
        f"Runtime halt: {is_trading_halted_runtime()}  KILL_SWITCH: {kill_switch_env_active()}\n"
        f"Equity={_num(float(current_equity()))}  "
        f"winrate={analytics.winrate():.2%}  "
        f"drawdown={_num(float(analytics.drawdown()))}\n"
        f"Open positions: {len(posmod.positions)}  "
        f"last cycle: {state.get('last_bot_cycle_utc') or 'n/a'}\n"
        f"Started: {state.get('bot_started_at') or 'n/a'}"
    )
    return CommandReply(text)


def cmd_start_trading() -> CommandReply:
    from forex_bot.execution import (
        is_trading_halted_runtime,
        kill_switch_env_active,
        resume_trading,
        trading_allowed,
    )

    if (os.getenv("RECONCILE_ON_RESUME") or "").strip().lower() in ("1", "true", "yes", "on"):
        from forex_bot.reconciliation import run_reconciliation_once

        try:
            run_reconciliation_once()
        except Exception as exc:
            logger.warning("telegram resume reconcile failed: %s", exc)
    resume_trading()
    extra = ""
    if kill_switch_env_active():
        extra = "\nKILL_SWITCH env is still on — new entries stay blocked until that is cleared."
    elif not trading_allowed():
        extra = "\nRuntime halt is clear, but another gate still blocks new entries. Use 📈 Status."
    return CommandReply(
        "▶️ Trading STARTED (resume)\n"
        "New entries use the same gate as POST /resume.\n"
        f"Runtime halt now: {is_trading_halted_runtime()}  "
        f"trading_allowed={trading_allowed()}."
        f"{extra}\n"
        "The process was already running; this does not restart it."
    )


def cmd_stop() -> CommandReply:
    from forex_bot.execution import halt_trading, is_trading_halted_runtime

    halt_trading()
    return CommandReply(
        "⏹ Trading STOPPED\n"
        "New entries are blocked (same as POST /halt).\n"
        "Open positions can still close. The process stays up.\n"
        f"Runtime halt now: {is_trading_halted_runtime()}.\n"
        "▶️ Start or /start_trading to allow new entries again."
    )


def cmd_positions() -> CommandReply:
    from forex_bot import positions as posmod

    unrealized, lines = _open_mtm()
    if not lines:
        return CommandReply("💼 Positions\nNo open local positions.")
    u_txt = "n/a" if unrealized is None else _signed(unrealized, 5)
    body = "\n".join(lines)
    return CommandReply(f"💼 Positions ({len(posmod.positions)})\nUnrealized: {u_txt}\n{body}")


def cmd_account() -> CommandReply:
    from forex_bot.oanda_client import last_account_summary
    from forex_bot.state import current_equity

    snap = last_account_summary() or {}
    if not snap:
        return CommandReply(
            "🏦 Account\n"
            "No cached AccountSummary yet. The bot loop fills this each cycle.\n"
            f"Fallback equity: {_num(float(current_equity()))}"
        )
    text = (
        "🏦 Account (cached OANDA summary)\n"
        f"id={snap.get('id') or 'n/a'}  alias={snap.get('alias') or 'n/a'}\n"
        f"NAV={snap.get('NAV')} {snap.get('currency') or ''}\n"
        f"balance={snap.get('balance')}  marginAvailable={snap.get('marginAvailable')}\n"
        f"host={snap.get('host') or 'n/a'}  env={snap.get('environment') or 'n/a'}\n"
        f"App equity(): {_num(float(current_equity()))}"
    )
    return CommandReply(text)


def cmd_system() -> CommandReply:
    from forex_bot import positions as posmod
    from forex_bot.execution import (
        broker_orders_enabled,
        effective_paper_trading,
        get_execution_mode,
        is_trading_halted_runtime,
        kill_switch_env_active,
        pre_trade_entry_allowed,
        pre_trade_entry_blocked_reason,
        trading_allowed,
    )
    from forex_bot.operational_state import operational_state_payload
    from forex_bot.orders import orders_summary
    from forex_bot.reconciliation import (
        get_reconciliation_snapshot,
        new_entries_allowed_by_reconcile,
        reconcile_gate_enforced,
    )
    from forex_bot.state import state

    ops = operational_state_payload()
    reco = get_reconciliation_snapshot()
    orders = orders_summary()
    text = (
        "⚙️ System\n"
        f"phase={state.get('lifespan_phase')}  bot={state.get('bot_status')}\n"
        f"{ops.get('operational_state')}: {ops.get('operational_state_detail')}\n"
        f"exec={get_execution_mode().value}  host={Config.TRADING_MODE}  "
        f"broker_orders={broker_orders_enabled()}  paper={effective_paper_trading()}\n"
        f"trading_allowed={trading_allowed()}  pre_trade={pre_trade_entry_allowed()}  "
        f"blocked={pre_trade_entry_blocked_reason() or 'none'}\n"
        f"halt={is_trading_halted_runtime()}  kill_switch={kill_switch_env_active()}\n"
        f"reconcile_gate={reconcile_gate_enforced()}  "
        f"new_entries_by_reconcile={new_entries_allowed_by_reconcile()}  "
        f"stale={reco.get('reconcile_stale')}  age_s={reco.get('age_seconds_since_reconcile')}\n"
        f"orders={orders.get('order_count')} {orders.get('by_status')}\n"
        f"open_positions={len(posmod.positions)}  last_cycle={state.get('last_bot_cycle_utc') or 'n/a'}"
    )
    return CommandReply(text)


def cmd_windows() -> CommandReply:
    from forex_bot.session_rules import format_live_window_log, live_windows_status

    snap = live_windows_status()
    lines = [
        "🪟 Live windows",
        f"tz={snap.get('timezone')} ({snap.get('timezone_source')}) "
        f"dst={snap.get('dst_label')} offset={snap.get('utc_offset')}",
        f"now_local={snap.get('now_local')}  now_utc={snap.get('now_utc')}",
        f"exec={snap.get('execution_mode')}  any_inside={snap.get('any_symbol_inside')}",
        f"fills={snap.get('fills')}",
    ]
    for row in snap.get("symbols") or []:
        flag = "IN" if row.get("inside") else "OUT"
        lines.append(
            f"{row.get('symbol')} {flag} local={row.get('local_window')} utc={row.get('utc_window')}"
        )
    lines.append(format_live_window_log(snap))
    return CommandReply("\n".join(lines))


def cmd_metrics() -> CommandReply:
    from forex_bot.analytics import analytics
    from forex_bot.state import current_equity
    from forex_bot.trading import configured_max_portfolio_risk_pct, portfolio_risk_fraction

    eq = float(current_equity())
    cap = configured_max_portfolio_risk_pct()
    wr = analytics.winrate()
    text = (
        "📋 Metrics\n"
        f"Equity: {_num(eq)}\n"
        f"Sharpe (trade PnL): {_num(float(analytics.sharpe()), 4)}\n"
        f"Win rate: {wr:.2%} ({analytics.win_rate_pct():.1f}%)\n"
        f"Drawdown: {_num(float(analytics.drawdown()))}\n"
        f"Avg win: {_signed(float(analytics.avg_win()), 4)}  "
        f"avg loss: {_signed(float(analytics.avg_loss()), 4)}\n"
        f"Profit factor: {_pf_text(analytics.profit_factor())}\n"
        f"Closed trades: {len(analytics.trades)}\n"
        f"Portfolio stop-risk: {portfolio_risk_fraction(eq) * 100.0:.2f}%  "
        f"cap: {(cap * 100.0) if cap > 0 else 0.0:.2f}%\n"
        f"Mode host={Config.TRADING_MODE} paper_flag={Config.PAPER_TRADING}"
    )
    return CommandReply(text)


def cmd_trades() -> CommandReply:
    from forex_bot.analytics import analytics
    from forex_bot.database import fetch_all_trades_ordered

    try:
        rows = fetch_all_trades_ordered()[:8]
    except Exception as exc:
        logger.warning("telegram trades fetch failed: %s", exc)
        rows = []
    if rows:
        lines = ["📜 Recent trades (newest first)"]
        for r in rows:
            t = r.get("time")
            if hasattr(t, "isoformat"):
                t = t.isoformat()
            pnl = r.get("pnl")
            try:
                pnl_s = _signed(float(pnl), 5)
            except (TypeError, ValueError):
                pnl_s = str(pnl)
            lines.append(
                f"{t} {r.get('symbol')} {r.get('direction')} {pnl_s} "
                f"{r.get('strategy') or ''} {r.get('execution_kind') or ''}".strip()
            )
        return CommandReply("\n".join(lines))
    if analytics.trades:
        last = analytics.trades[-8:]
        body = ", ".join(_signed(float(p), 5) for p in reversed(last))
        return CommandReply(
            f"📜 Recent trades\nNo DB rows. In-memory closed PnLs (newest first): {body}"
        )
    return CommandReply("📜 Recent trades\nNo closed trades yet.")


def cmd_risk() -> CommandReply:
    from forex_bot.portfolio_exposure import exposure_snapshot
    from forex_bot.state import current_equity
    from forex_bot.trading import configured_max_portfolio_risk_pct, portfolio_risk_fraction

    exp = exposure_snapshot()
    eq = float(current_equity())
    cap = configured_max_portfolio_risk_pct()
    text = (
        "🧯 Risk / exposure\n"
        f"Gross USD notional ≈ {exp.get('gross_usd_notional_approx')}\n"
        f"Net USD exposure ≈ {exp.get('net_usd_exposure_approx')}\n"
        f"Gross cap: {exp.get('max_gross_usd_notional_cap')}  "
        f"breached={exp.get('exposure_cap_breached')}\n"
        f"Per-trade notional pct of NAV: {float(exp.get('notional_pct_of_nav') or 0.0):.4f}\n"
        f"Book gross pct of NAV: {float(exp.get('portfolio_gross_notional_pct_of_nav') or 0.0):.4f}"
        f"{' (inherited)' if exp.get('portfolio_gross_pct_inherited') else ''}\n"
        f"Stop-risk of equity: {portfolio_risk_fraction(eq) * 100.0:.2f}%  "
        f"cap={(cap * 100.0) if cap > 0 else 0.0:.2f}%"
    )
    return CommandReply(text)


def cmd_experiment() -> CommandReply:
    from forex_bot.ai_ensemble import ai as ai_ensemble
    from forex_bot.experiment import experiment_snapshot_with_voters

    snap = experiment_snapshot_with_voters(ai_ensemble)
    lines = ["🧪 Experiment"]
    for key in (
        "ensemble_mode",
        "nn_pred_mode",
        "execution_mode",
        "execution_mode_explicit",
        "trading_allowed",
        "kill_switch_env",
        "halted_runtime",
        "local_voters",
        "external_voters",
        "forex_backtest",
        "ai_disable_stub",
    ):
        lines.append(f"{key}={snap.get(key)}")
    return CommandReply("\n".join(lines))


def cmd_reconcile() -> CommandReply:
    from forex_bot.reconciliation import get_reconciliation_snapshot

    snap = get_reconciliation_snapshot()
    mismatches = snap.get("mismatches") or []
    text = (
        "🔄 Reconcile\n"
        f"last_run_utc={snap.get('last_run_utc') or 'n/a'}\n"
        f"age_s={snap.get('age_seconds_since_reconcile')}  stale={snap.get('reconcile_stale')}\n"
        f"gate={snap.get('effective_reconcile_gate')}  action={snap.get('reconcile_action')}\n"
        f"broker_positions={snap.get('broker_positions_fetched')}  "
        f"pending_orders={snap.get('broker_pending_orders')}\n"
        f"runs={snap.get('reconcile_runs_total')}  "
        f"fixes={snap.get('reconcile_fixes_total')}  "
        f"last_cycle_fixes={snap.get('reconcile_fixes_applied')}\n"
        f"mismatches={len(mismatches)}"
    )
    if mismatches:
        preview = ", ".join(str(m) for m in mismatches[:6])
        text += f"\n{preview}"
    return CommandReply(text)


def cmd_mode() -> CommandReply:
    from forex_bot.execution import (
        broker_orders_enabled,
        effective_paper_trading,
        execution_mode_explicit,
        get_execution_mode,
    )

    return CommandReply(
        "Mode (read-only from Telegram)\n"
        f"TRADING_MODE host: {Config.TRADING_MODE}\n"
        f"EXECUTION_MODE: {get_execution_mode().value}  "
        f"explicit={execution_mode_explicit()}\n"
        f"broker_orders={broker_orders_enabled()}  "
        f"effective_paper={effective_paper_trading()}\n"
        "Change host via HTTP /set_mode. Telegram will not flip live/practice."
    )


_HANDLERS: dict[str, Any] = {
    "help": cmd_help,
    "menu": cmd_menu,
    "ping": cmd_ping,
    "pnl": cmd_pnl,
    "drawdown": cmd_drawdown,
    "status": cmd_status,
    "start_trading": cmd_start_trading,
    "stop": cmd_stop,
    "positions": cmd_positions,
    "account": cmd_account,
    "system": cmd_system,
    "windows": cmd_windows,
    "metrics": cmd_metrics,
    "trades": cmd_trades,
    "risk": cmd_risk,
    "experiment": cmd_experiment,
    "reconcile": cmd_reconcile,
    "mode": cmd_mode,
}


def handle_command(name: str) -> CommandReply:
    key = (name or "").strip().lower()
    fn = _HANDLERS.get(key)
    if fn is None:
        return CommandReply(
            f"Unknown command '{name}'. Send /help or tap ❓ Help.",
            show_inline_panel=True,
        )
    try:
        return fn()
    except Exception:
        logger.exception("telegram command %s failed", key)
        return CommandReply(
            f"Command '{key}' failed (see Docker logs). Trading is unchanged."
        )


def _clip(text: str) -> str:
    if len(text) > 4000:
        return text[:3997] + "..."
    return text


def send_control_message(
    text: str,
    *,
    reply_markup: dict[str, Any] | None = None,
    chat_id: str | None = None,
) -> bool:
    """Direct sendMessage for command replies. Does not use the alert queue/cooldown."""
    token = (Config.TELEGRAM_TOKEN or "").strip()
    dest = (chat_id or Config.TELEGRAM_CHAT_ID or "").strip()
    if not token or not dest:
        return False
    payload: dict[str, Any] = {"chat_id": dest, "text": _clip(text)}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=_env_timeout("TELEGRAM_TIMEOUT_SEC", 8.0),
        )
        if resp.status_code != 200:
            logger.warning(
                "Telegram control HTTP %s: %s",
                resp.status_code,
                (resp.text or "")[:400],
            )
            return False
        body = resp.json() if resp.content else {}
        if isinstance(body, dict) and body.get("ok") is False:
            logger.warning("Telegram control API error: %s", body)
            return False
        return True
    except Exception as exc:
        logger.warning("Telegram control send failed: %s", exc)
        return False


def _answer_callback(callback_id: str, text: str = "") -> None:
    token = (Config.TELEGRAM_TOKEN or "").strip()
    if not token or not callback_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text[:180]},
            timeout=_env_timeout("TELEGRAM_TIMEOUT_SEC", 8.0),
        )
    except Exception as exc:
        logger.debug("answerCallbackQuery: %s", exc)


def _register_bot_commands() -> None:
    global _commands_registered
    if _commands_registered:
        return
    token = (Config.TELEGRAM_TOKEN or "").strip()
    if not token:
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/setMyCommands",
            json={"commands": [{"command": n, "description": d} for n, d in BOT_COMMANDS]},
            timeout=_env_timeout("TELEGRAM_TIMEOUT_SEC", 8.0),
        )
        if resp.status_code == 200:
            _commands_registered = True
        else:
            logger.warning("setMyCommands HTTP %s: %s", resp.status_code, (resp.text or "")[:200])
    except Exception as exc:
        logger.warning("setMyCommands failed: %s", exc)


def dispatch_text(text: str) -> CommandReply | None:
    """Return a reply for a chat message, or None if it is not a command/button."""
    name = normalize_command(text)
    if not name:
        return None
    if name in _HANDLERS:
        return handle_command(name)
    if (text or "").strip().startswith("/"):
        return handle_command(name)
    return None


def _send_reply(reply: CommandReply, chat_id: Any) -> None:
    dest = str(chat_id)
    send_control_message(
        reply.text,
        reply_markup=reply_keyboard_markup(),
        chat_id=dest,
    )
    if reply.show_inline_panel:
        send_control_message(
            "Control panel (same actions as the keyboard):",
            reply_markup=inline_keyboard_markup(),
            chat_id=dest,
        )


def process_update(update: dict[str, Any]) -> bool:
    """Handle one Telegram update. Returns True if a reply was produced."""
    if not isinstance(update, dict):
        return False

    callback = update.get("callback_query")
    if isinstance(callback, dict):
        chat = ((callback.get("message") or {}).get("chat") or {})
        chat_id = chat.get("id")
        data = str(callback.get("data") or "")
        cid = str(callback.get("id") or "")
        if not is_authorized_chat(chat_id):
            _answer_callback(cid, "Unauthorized")
            return False
        name = normalize_command(data) or data.strip().lower()
        reply = handle_command(name)
        _answer_callback(cid)
        _send_reply(reply, chat_id)
        return True

    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return False
    chat_id = (message.get("chat") or {}).get("id")
    if not is_authorized_chat(chat_id):
        return False
    text = message.get("text")
    if not isinstance(text, str):
        return False
    reply = dispatch_text(text)
    if reply is None:
        return False
    _send_reply(reply, chat_id)
    return True


def process_updates(payload: dict[str, Any] | list[dict[str, Any]]) -> int:
    """Process getUpdates JSON (or a raw list). Returns the next offset."""
    global _offset
    if isinstance(payload, list):
        updates = payload
    elif isinstance(payload, dict):
        updates = payload.get("result") or []
    else:
        return _offset
    next_offset = _offset
    for upd in updates:
        if not isinstance(upd, dict):
            continue
        uid = upd.get("update_id")
        try:
            next_offset = max(next_offset, int(uid) + 1)
        except (TypeError, ValueError):
            pass
        try:
            process_update(upd)
        except Exception:
            logger.exception("telegram update failed")
    _offset = next_offset
    return _offset


def _poll_timeout_sec() -> float:
    return _env_timeout("TELEGRAM_POLL_TIMEOUT_SEC", 20.0)


def _drain_backlog(token: str) -> int:
    """Advance offset past queued updates so a restart does not replay old Start/Stop."""
    offset = 0
    timeout = _env_timeout("TELEGRAM_TIMEOUT_SEC", 8.0)
    for _ in range(20):
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"timeout": 0, "limit": 100, "offset": offset},
                timeout=timeout,
            )
            body = resp.json() if resp.content else {}
        except Exception as exc:
            logger.warning("telegram backlog drain failed: %s", exc)
            return offset
        updates = body.get("result") if isinstance(body, dict) else None
        if not updates:
            return offset
        for upd in updates:
            try:
                offset = max(offset, int(upd.get("update_id")) + 1)
            except (TypeError, ValueError, AttributeError):
                continue
        if len(updates) < 100:
            return offset
    return offset


def _poller_loop() -> None:
    token = (Config.TELEGRAM_TOKEN or "").strip()
    if not token:
        return
    _register_bot_commands()
    global _offset
    _offset = _drain_backlog(token)
    logger.info("Telegram command listener started (offset=%s)", _offset)
    http_timeout = _poll_timeout_sec() + 5.0
    while not _stop_event.is_set():
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={
                    "timeout": int(_poll_timeout_sec()),
                    "offset": _offset,
                    "allowed_updates": '["message","callback_query","edited_message"]',
                },
                timeout=http_timeout,
            )
            if resp.status_code == 409:
                logger.warning(
                    "Telegram getUpdates 409 (another poller?). Backing off; trading continues."
                )
                _stop_event.wait(15.0)
                continue
            if resp.status_code != 200:
                logger.warning(
                    "Telegram getUpdates HTTP %s: %s",
                    resp.status_code,
                    (resp.text or "")[:300],
                )
                _stop_event.wait(5.0)
                continue
            body = resp.json() if resp.content else {}
            if isinstance(body, dict) and body.get("ok") is False:
                logger.warning("Telegram getUpdates error: %s", body)
                _stop_event.wait(5.0)
                continue
            process_updates(body if isinstance(body, dict) else {})
        except Exception as exc:
            if _stop_event.is_set():
                break
            logger.warning("Telegram poller error: %s", exc)
            _stop_event.wait(5.0)
    logger.info("Telegram command listener stopped")


def start_telegram_control() -> None:
    """Start the getUpdates thread if configured. Never raises to the caller."""
    global _poller_started
    if not commands_enabled():
        if telegram_configured():
            logger.info("Telegram commands disabled (TELEGRAM_COMMANDS=0)")
        return
    with _poller_lock:
        if _poller_started:
            return
        _stop_event.clear()
        try:
            threading.Thread(
                target=_poller_loop,
                name="telegram-control",
                daemon=True,
            ).start()
            _poller_started = True
        except Exception:
            logger.exception("telegram control failed to start (trading continues)")


def stop_telegram_control() -> None:
    """Ask the poller to exit. The thread is daemon, so shutdown is best-effort."""
    global _poller_started
    _stop_event.set()
    with _poller_lock:
        _poller_started = False


def reset_telegram_control_for_tests() -> None:
    global _offset, _commands_registered, _poller_started
    stop_telegram_control()
    _offset = 0
    _commands_registered = False
    _poller_started = False
    _stop_event.clear()
