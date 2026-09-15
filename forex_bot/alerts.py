"""Telegram, Discord, and console alerts.

Console print is synchronous. Telegram/Discord send on a background thread so a
hung api.telegram.org call cannot delay OrderCreate or block the event loop.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from datetime import datetime

import requests

from forex_bot.config import Config

logger = logging.getLogger(__name__)

_telegram_missing_logged = False
_queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=200)
_worker_lock = threading.Lock()
_worker_started = False
_fail_streak = 0
_cooldown_until = 0.0
_cooldown_logged = False


def _env_timeout(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1.0, float(raw))
    except ValueError:
        return default


def _telegram_timeout_sec() -> float:
    return _env_timeout("TELEGRAM_TIMEOUT_SEC", 8.0)


def _telegram_cooldown_sec() -> float:
    return _env_timeout("TELEGRAM_COOLDOWN_SEC", 60.0)


def _deliver_telegram(msg: str) -> bool:
    """POST sendMessage. Returns True on HTTP 200 + ok. Never raises to the caller."""
    global _telegram_missing_logged, _fail_streak, _cooldown_until, _cooldown_logged
    token = (Config.TELEGRAM_TOKEN or "").strip()
    chat_id = (Config.TELEGRAM_CHAT_ID or "").strip()
    if not token or not chat_id:
        if not _telegram_missing_logged:
            logger.info(
                "Telegram not configured: set TELEGRAM_TOKEN (or TELEGRAM_BOT_TOKEN) and "
                "TELEGRAM_CHAT_ID in .env to receive alerts."
            )
            _telegram_missing_logged = True
        return False
    now = time.monotonic()
    if now < _cooldown_until:
        return False
    if len(msg) > 4000:
        msg = msg[:3997] + "..."
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": msg},
            timeout=_telegram_timeout_sec(),
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
            _note_telegram_failure()
            return False
        if isinstance(body, dict) and body.get("ok") is False:
            logger.warning("Telegram API error: %s", body)
            _note_telegram_failure()
            return False
        _fail_streak = 0
        _cooldown_until = 0.0
        _cooldown_logged = False
        return True
    except Exception as exc:
        logger.warning("Telegram request failed: %s", exc)
        _note_telegram_failure()
        return False


def _note_telegram_failure() -> None:
    global _fail_streak, _cooldown_until, _cooldown_logged
    _fail_streak += 1
    if _fail_streak < 3:
        return
    _cooldown_until = time.monotonic() + _telegram_cooldown_sec()
    if not _cooldown_logged:
        logger.warning(
            "Telegram paused for %.0fs after %s failures (trading/alerts continue in Docker logs)",
            _telegram_cooldown_sec(),
            _fail_streak,
        )
        _cooldown_logged = True


def _deliver_discord(msg: str) -> None:
    if not Config.DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(Config.DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=8)
    except Exception as exc:
        logger.debug("discord_alert: %s", exc)


def _alert_worker() -> None:
    while True:
        kind, msg = _queue.get()
        try:
            if kind == "tg":
                _deliver_telegram(msg)
            elif kind == "dc":
                _deliver_discord(msg)
        except Exception:
            logger.exception("alert worker failed")
        finally:
            _queue.task_done()


def _ensure_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        threading.Thread(target=_alert_worker, name="alert-sender", daemon=True).start()
        _worker_started = True


def _enqueue(kind: str, msg: str) -> None:
    _ensure_worker()
    try:
        _queue.put_nowait((kind, msg))
    except queue.Full:
        logger.warning("alert queue full; dropped %s notification", kind)


def telegram_alert(msg: str) -> None:
    """Queue a Telegram send. Does not wait for the HTTP response."""
    _enqueue("tg", msg)


def discord_alert(msg: str) -> None:
    """Queue a Discord send. Does not wait for the HTTP response."""
    if not Config.DISCORD_WEBHOOK_URL:
        return
    _enqueue("dc", msg)


def alert(msg: str, level: str = "INFO") -> None:
    ts = f"[{level}] {datetime.now()}: {msg}"
    print(ts)
    telegram_alert(ts)
    discord_alert(ts)
