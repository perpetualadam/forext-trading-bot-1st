"""Telegram, Discord, and console alerts."""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from forex_bot.config import Config

logger = logging.getLogger(__name__)

_telegram_missing_logged = False


def telegram_alert(msg: str) -> None:
    global _telegram_missing_logged
    token = (Config.TELEGRAM_TOKEN or "").strip()
    chat_id = (Config.TELEGRAM_CHAT_ID or "").strip()
    if not token or not chat_id:
        if not _telegram_missing_logged:
            logger.info(
                "Telegram not configured: set TELEGRAM_TOKEN (or TELEGRAM_BOT_TOKEN) and "
                "TELEGRAM_CHAT_ID in .env to receive alerts."
            )
            _telegram_missing_logged = True
        return
    # Telegram hard limit 4096; keep margin for safety.
    if len(msg) > 4000:
        msg = msg[:3997] + "..."
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": msg},
            timeout=15,
        )
        try:
            body = resp.json()
        except ValueError:
            body = None
        if resp.status_code != 200:
            logger.warning(
                "Telegram HTTP %s: %s",
                resp.status_code,
                (resp.text or "")[:400],
            )
            return
        if isinstance(body, dict) and body.get("ok") is False:
            logger.warning("Telegram API error: %s", body)
    except Exception as exc:
        logger.warning("Telegram request failed: %s", exc)


def discord_alert(msg: str) -> None:
    if not Config.DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(Config.DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=10)
    except Exception as exc:
        logger.debug("discord_alert: %s", exc)


def alert(msg: str, level: str = "INFO") -> None:
    ts = f"[{level}] {datetime.now()}: {msg}"
    print(ts)
    telegram_alert(ts)
    discord_alert(ts)
