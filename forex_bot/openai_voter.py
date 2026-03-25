"""Optional OpenAI-compatible chat voter (OpenAI API, Azure OpenAI-style base URL, Ollama /v1, etc.)."""

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
- "allow": boolean — true only if a small speculative trade seems reasonable given the hints; false if uncertain or conflicting.
- "confidence": number from 0.0 to 1.0 — your confidence in that decision.
- "direction": exactly "BUY" or "SELL" — your directional bias for the next simulated trade.

Prefer allow=false when data is ambiguous."""


def _float_env(name: str, default: str) -> float:
    raw = (os.getenv(name) or "").strip()
    return float(raw) if raw else float(default)


def _truthy(name: str, default: bool = True) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    return default


class OpenAIVoter:
    """Calls POST {base}/chat/completions with Bearer token."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        use_json_format: bool | None = None,
        timeout: float | None = None,
        temperature: float | None = None,
    ) -> None:
        self.api_key = (
            api_key.strip()
            if isinstance(api_key, str)
            else (os.getenv("OPENAI_API_KEY") or "").strip()
        )
        self.model = (
            model.strip()
            if isinstance(model, str) and model.strip()
            else (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        )
        self.base_url = (
            base_url.rstrip("/")
            if isinstance(base_url, str) and base_url.strip()
            else (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        )
        if use_json_format is None:
            self._use_json_format = _truthy("OPENAI_JSON_MODE", True)
        else:
            self._use_json_format = use_json_format
        self._timeout = float(timeout) if timeout is not None else _float_env("OPENAI_TIMEOUT", "60")
        self._temperature = (
            float(temperature) if temperature is not None else _float_env("OPENAI_TEMPERATURE", "0.2")
        )

    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key and "api.openai.com" in self.base_url:
            raise ValueError("OPENAI_API_KEY is required for api.openai.com")

        user_block = json.dumps(payload, indent=2, default=str)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": f"Context:\n{user_block}\n\nOutput JSON with allow, confidence, direction.",
                },
            ],
            "temperature": self._temperature,
        }
        if self._use_json_format:
            body["response_format"] = {"type": "json_object"}

        def _post() -> dict[str, Any]:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=body,
                timeout=self._timeout,
            )
            r.raise_for_status()
            return r.json()

        try:
            data = await asyncio.to_thread(_post)
        except Exception as exc:
            logger.warning("OpenAI-compatible LLM request failed: %s", exc)
            raise

        try:
            text = data["choices"][0]["message"]["content"]
            parsed = json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.warning("Bad LLM response shape: %s", exc)
            raise

        direction = str(parsed.get("direction", "BUY")).upper()
        if direction not in ("BUY", "SELL"):
            direction = "BUY"

        conf = float(parsed.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))

        return {
            "allow": bool(parsed.get("allow", False)),
            "confidence": conf,
            "direction": direction,
        }
