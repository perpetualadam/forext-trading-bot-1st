"""Read-only Telegram slash commands. No trading, halt, or flatten."""

from __future__ import annotations

import logging
import os
from typing import Callable

from forex_bot.alerts import telegram_alert
from forex_bot.config import Config
from forex_bot.telegram_cloud import (
    fetch_pending_updates,
    parse_inbound_text,
    set_local_command_menu,
)

logger = logging.getLogger(__name__)

READONLY_COMMANDS = ("help", "start", "status")
BLOCKED_COMMANDS = (
    "halt",
    "resume",
    "kill",
    "close",
    "buy",
    "sell",
    "flatten",
    "stop",
    "positions",
)

HELP_TEXT = (
    "Commands:\n"
    "/help — this list\n"
    "/status — bot health snapshot\n"
    "Trading is not controlled from Telegram."
)


def inbound_enabled() -> bool:
    raw = (os.getenv("TELEGRAM_INBOUND") or "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return bool((Config.TELEGRAM_TOKEN or "").strip() and (Config.TELEGRAM_CHAT_ID or "").strip())


def chat_allowed(chat_id: object) -> bool:
    expected = (Config.TELEGRAM_CHAT_ID or "").strip()
    if not expected:
        return False
    return str(chat_id).strip() == expected


def local_command_menu() -> list[dict[str, str]]:
    return [
        {"command": "help", "description": "List Telegram commands"},
        {"command": "status", "description": "Bot health snapshot"},
    ]


def decide_command(update: dict, status_text: Callable[[], str]) -> dict:
    """Return how to reply. Never triggers trading side effects."""
    command = str(update.get("command") or parse_inbound_text(str(update.get("text") or "")).get("command") or "")
    if not chat_allowed(update.get("chat_id")):
        return {"action": "ignore", "reason": "chat_not_allowed", "reply": ""}
    if command in BLOCKED_COMMANDS:
        logger.warning("ignored blocked Telegram command /%s", command)
        return {
            "action": "reject",
            "reason": "blocked_command",
            "reply": "That command is disabled. Telegram cannot change trades.",
        }
    if command in ("help", "start"):
        return {"action": "reply", "reason": "help", "reply": HELP_TEXT}
    if command == "status":
        return {"action": "reply", "reason": "status", "reply": status_text()}
    if update.get("is_command"):
        return {
            "action": "reject",
            "reason": "unknown_command",
            "reply": "Unknown command. Try /help or /status.",
        }
    return {"action": "ignore", "reason": "not_a_command", "reply": ""}


def handle_pending_updates(status_text: Callable[[], str], send=telegram_alert) -> dict:
    """Pull queued Telegram messages once and reply to safe commands only."""
    if not inbound_enabled():
        return {"ok": False, "reason": "inbound_disabled"}
    pulled = fetch_pending_updates(Config.TELEGRAM_TOKEN, acknowledge=True)
    if not pulled.get("ok"):
        return pulled
    sent = 0
    for update in pulled.get("updates") or []:
        decision = decide_command(update, status_text)
        reply = decision.get("reply") or ""
        if reply:
            send(reply)
            sent += 1
    return {"ok": True, "n_updates": pulled.get("n_updates", 0), "replies_sent": sent}


def sync_command_menu() -> dict:
    if not inbound_enabled():
        return {"ok": False, "reason": "inbound_disabled"}
    return set_local_command_menu(Config.TELEGRAM_TOKEN, local_command_menu())
