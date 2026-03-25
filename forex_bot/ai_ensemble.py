"""Pluggable local / external LLM-style voters (stubs match original behavior)."""

from __future__ import annotations

import logging
import os
import random
from typing import Any, Protocol

import numpy as np

logger = logging.getLogger(__name__)


def _stub_disabled() -> bool:
    return os.getenv("AI_DISABLE_STUB", "").strip().lower() in ("1", "true", "yes", "on")


def _optional_json_flag(env_name: str) -> bool | None:
    raw = (os.getenv(env_name) or "").strip().lower()
    if not raw:
        return None
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    return float(raw) if raw else default


def _random_stub_vote() -> dict[str, Any]:
    """Tunable random voter (original: ~70% allow, confidence 0.5–1.0)."""
    threshold = max(0.0, min(1.0, _env_float("STUB_ALLOW_THRESHOLD", 0.3)))
    lo = _env_float("STUB_CONFIDENCE_MIN", 0.5)
    hi = _env_float("STUB_CONFIDENCE_MAX", 1.0)
    if hi < lo:
        lo, hi = hi, lo
    lo = max(0.0, min(1.0, lo))
    hi = max(0.0, min(1.0, hi))
    allow = random.random() > threshold
    confidence = random.uniform(lo, hi) if lo <= hi else lo
    return {"allow": allow, "confidence": confidence}


def _aggregate_direction(votes: list[dict[str, Any]]) -> str:
    buy_w = 0.0
    sell_w = 0.0
    for v in votes:
        d = str(v.get("direction", "")).upper()
        w = float(v.get("confidence", 0.5))
        if d == "BUY":
            buy_w += w
        elif d == "SELL":
            sell_w += w
    if buy_w > 0 or sell_w > 0:
        return "BUY" if buy_w >= sell_w else "SELL"
    return (
        "BUY"
        if np.mean([random.choice([1, -1]) * float(v["confidence"]) for v in votes]) > 0
        else "SELL"
    )


class LLMVoter(Protocol):
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class LocalLLM:
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = payload
        return _random_stub_vote()


class ExternalLLMAPI:
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = payload
        return _random_stub_vote()


class AIEnsemble:
    def __init__(
        self,
        local_llms: list[LLMVoter] | None = None,
        external_llms: list[LLMVoter] | None = None,
    ) -> None:
        self.local_llms = local_llms or []
        self.external_llms = external_llms or []

    async def vote(self, payload: dict[str, Any], symbol: str) -> dict[str, Any]:
        _ = symbol
        votes: list[dict[str, Any]] = []
        for llm in self.local_llms:
            try:
                votes.append(await llm.predict(payload))
            except Exception as exc:
                logger.debug("local llm vote failed: %s", exc)
        for api in self.external_llms:
            try:
                votes.append(await api.predict(payload))
            except Exception as exc:
                logger.debug("external llm vote failed: %s", exc)
        if not votes:
            return {"allow": True, "confidence": 1.0, "direction": "BUY"}
        total_conf = sum(float(v["confidence"]) for v in votes)
        allow_score = sum(float(v["confidence"]) if v.get("allow") else 0.0 for v in votes) / (total_conf + 1e-6)
        direction = _aggregate_direction(votes)
        return {"allow": allow_score > 0.5, "confidence": allow_score, "direction": direction}


def _env_model(var: str, default: str) -> str:
    """Treat unset or blank env as missing so defaults still apply."""
    v = (os.getenv(var) or "").strip()
    return v if v else default


def _openai_compat_enabled() -> bool:
    if (os.getenv("OPENAI_API_KEY") or "").strip():
        return True
    base = (os.getenv("OPENAI_BASE_URL") or "").strip()
    return bool(base) and "api.openai.com" not in base


def _build_default_ensemble() -> AIEnsemble:
    from forex_bot.openai_voter import OpenAIVoter

    local: list[LLMVoter] = [] if _stub_disabled() else [LocalLLM()]
    external: list[LLMVoter] = []

    if (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        from forex_bot.anthropic_voter import AnthropicVoter

        external.append(AnthropicVoter())

    if _openai_compat_enabled():
        external.append(OpenAIVoter())

    if (os.getenv("DEEPSEEK_API_KEY") or "").strip():
        external.append(
            OpenAIVoter(
                api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
                base_url="https://api.deepseek.com/v1",
                model=_env_model("DEEPSEEK_MODEL", "deepseek-chat"),
            )
        )

    if (os.getenv("MISTRAL_API_KEY") or "").strip():
        external.append(
            OpenAIVoter(
                api_key=os.getenv("MISTRAL_API_KEY", "").strip(),
                base_url="https://api.mistral.ai/v1",
                model=_env_model("MISTRAL_MODEL", "mistral-small-latest"),
            )
        )

    xai_key = (os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY") or "").strip()
    if xai_key:
        external.append(
            OpenAIVoter(
                api_key=xai_key,
                base_url=(os.getenv("XAI_BASE_URL") or "https://api.x.ai/v1").rstrip("/"),
                model=_env_model("GROK_MODEL", _env_model("XAI_MODEL", "grok-2-latest")),
            )
        )

    if (os.getenv("GROQ_API_KEY") or "").strip():
        external.append(
            OpenAIVoter(
                api_key=os.getenv("GROQ_API_KEY", "").strip(),
                base_url="https://api.groq.com/openai/v1",
                model=_env_model("GROQ_MODEL", "llama-3.3-70b-versatile"),
            )
        )

    if (os.getenv("VENICE_API_KEY") or "").strip():
        venice_base = (os.getenv("VENICE_BASE_URL") or "https://api.venice.ai/v1").rstrip("/")
        external.append(
            OpenAIVoter(
                api_key=os.getenv("VENICE_API_KEY", "").strip(),
                base_url=venice_base,
                model=_env_model("VENICE_MODEL", "venice-uncensored"),
                use_json_format=_optional_json_flag("VENICE_JSON_MODE"),
            )
        )

    qrok_key = (os.getenv("QROK_API_KEY") or "").strip()
    qrok_base = (os.getenv("QROK_BASE_URL") or "").strip()
    if qrok_key and qrok_base:
        external.append(
            OpenAIVoter(
                api_key=qrok_key,
                base_url=qrok_base.rstrip("/"),
                model=_env_model("QROK_MODEL", "default"),
                use_json_format=_optional_json_flag("QROK_JSON_MODE"),
            )
        )
    elif qrok_key and not qrok_base:
        logger.warning("QROK_API_KEY is set but QROK_BASE_URL is missing; skipping Qrok voter.")

    if not local and not external:
        logger.warning("No LLM voters configured; using stub LocalLLM only.")
        local = [LocalLLM()]
    return AIEnsemble(local_llms=local, external_llms=external)


ai = _build_default_ensemble()
