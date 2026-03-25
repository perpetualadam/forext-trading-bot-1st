"""Telegram, Discord, and console alerts."""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from forex_bot.config import Config

logger = logging.getLogger(__name__)


def telegram_alert(msg: str) -> None:
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": Config.TELEGRAM_CHAT_ID, "text": msg},
            timeout=10,
        )
    except Exception as exc:
        logger.debug("telegram_alert: %s", exc)


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
