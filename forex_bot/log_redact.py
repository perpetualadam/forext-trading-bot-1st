"""Strip credentials from text before it is written to logs."""

from __future__ import annotations

import re
from typing import Any

_BOT_PATH = re.compile(r"/bot[^/\s?#]+")
_BEARER = re.compile(r"(?i)(bearer\s+)\S+")
_DISCORD_WEBHOOK = re.compile(
    r"https?://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\S+",
    re.IGNORECASE,
)
_USERINFO = re.compile(r"(://[^:/?#\s]+):([^@/\s]+)@")


def mask_token(url: str, token: str = "") -> str:
    """Never persist or log a raw Telegram bot token."""
    text = str(url or "")
    if token:
        text = text.replace(token, "<redacted>")
    return _BOT_PATH.sub("/bot<redacted>", text)


def _known_secrets() -> list[str]:
    secrets: list[str] = []
    try:
        from forex_bot.config import Config

        candidates = [
            getattr(Config, "TELEGRAM_TOKEN", ""),
            getattr(Config, "OANDA_ACCESS_TOKEN", ""),
            getattr(Config, "DISCORD_WEBHOOK_URL", ""),
        ]
        pg = getattr(Config, "POSTGRES", None)
        if pg is not None:
            candidates.append(getattr(pg, "password", ""))
    except Exception:
        candidates = []
    for raw in candidates:
        val = str(raw or "").strip()
        if len(val) >= 10:
            secrets.append(val)
    return secrets


def redact_log_text(text: Any) -> str:
    """Return a log-safe string. Never raises."""
    try:
        cleaned = mask_token(str(text or ""))
        for secret in _known_secrets():
            if secret and secret in cleaned:
                cleaned = cleaned.replace(secret, "<redacted>")
        cleaned = _BEARER.sub(r"\1<redacted>", cleaned)
        cleaned = _DISCORD_WEBHOOK.sub("https://discord.com/api/webhooks/<redacted>", cleaned)
        cleaned = _USERINFO.sub(r"\1:<redacted>@", cleaned)
        return cleaned
    except Exception:
        return "<redacted>"
