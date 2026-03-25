"""Anthropic Messages API voter (not OpenAI-compatible)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

_SYSTEM = """You are a conservative risk gate for a forex trading bot demo.
You receive JSON with symbol, strategy, price, and simple model hints (nn_pred, seq_pred).

Reply with ONE JSON object only, no markdown, keys:
- "allow": boolean
- "confidence": number from 0.0 to 1.0
- "direction": exactly "BUY" or "SELL"

Prefer allow=false when data is ambiguous."""


def _int_env(name: str, default: str) -> int:
    raw = (os.getenv(name) or "").strip()
    return int(raw) if raw else int(default)


def _http_timeout_seconds() -> float:
    for key in ("ANTHROPIC_TIMEOUT", "OPENAI_TIMEOUT"):
        raw = (os.getenv(key) or "").strip()
        if raw:
            return float(raw)
    return 60.0


class AnthropicVoter:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("ANTHROPIC_API_KEY") or "").strip()
        self.model = (model if model is not None else os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022").strip()
        self.base_url = (base_url or os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")

    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is empty")

        user_block = json.dumps(payload, indent=2, default=str)
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": _int_env("ANTHROPIC_MAX_TOKENS", "512"),
            "system": _SYSTEM,
            "messages": [
                {
                    "role": "user",
                    "content": f"Context:\n{user_block}\n\nOutput JSON with allow, confidence, direction.",
                }
            ],
        }

        def _post() -> dict[str, Any]:
            r = requests.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=_http_timeout_seconds(),
            )
            r.raise_for_status()
            return r.json()

        try:
            data = await asyncio.to_thread(_post)
        except Exception as exc:
            logger.warning("Anthropic LLM request failed: %s", exc)
            raise

        try:
            parts = data["content"]
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            parsed = json.loads(text.strip())
        except (KeyError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("Bad Anthropic response: %s", exc)
            raise

        direction = str(parsed.get("direction", "BUY")).upper()
        if direction not in ("BUY", "SELL"):
            direction = "BUY"
        conf = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))

        return {
            "allow": bool(parsed.get("allow", False)),
            "confidence": conf,
            "direction": direction,
        }
