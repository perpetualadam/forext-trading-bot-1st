"""Pluggable external voters. The retired quant stub cannot approve a direction."""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Protocol

logger = logging.getLogger(__name__)


def _unavailable(reason: str, *, confidence: float = 0.0) -> dict[str, Any]:
    """Abstain without attaching a BUY or SELL placeholder."""
    return {
        "allow": False,
        "confidence": confidence,
        "direction": None,
        "status": "unavailable",
        "reason": reason,
    }


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


def _quant_stub_vote(payload: dict[str, Any]) -> dict[str, Any]:
    """Retired moving-average rule. It cannot supply BUY or SELL."""
    _ = payload
    return _unavailable("quant_stub_removed")


def _aggregate_direction(votes: list[dict[str, Any]]) -> str | None:
    """Confidence-weighted side. A tie or an abstention has no direction."""
    buy_w = 0.0
    sell_w = 0.0
    for vote in votes:
        if not vote.get("allow"):
            continue
        side = str(vote.get("direction") or "").upper()
        weight = float(vote.get("confidence", 0.0))
        if side == "BUY":
            buy_w += weight
        elif side == "SELL":
            sell_w += weight
    if buy_w > sell_w:
        return "BUY"
    if sell_w > buy_w:
        return "SELL"
    return None


class LLMVoter(Protocol):
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class LocalLLM:
    """Retired local heuristic. Registered ensembles do not include this voter."""

    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _quant_stub_vote(payload)


class ExternalLLMAPI:
    """Placeholder that does not call a network service and does not invent a side."""

    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = payload
        return _unavailable("external_voter_unavailable")


class AIEnsemble:
    def __init__(
        self,
        local_llms: list[LLMVoter] | None = None,
        external_llms: list[LLMVoter] | None = None,
        mode: str | None = None,
    ) -> None:
        self.local_llms = local_llms or []
        self.external_llms = external_llms or []
        self.mode = mode

    async def vote(self, payload: dict[str, Any], symbol: str) -> dict[str, Any]:
        _ = symbol
        if self.mode == "quant":
            return _unavailable("unsupported_ensemble_mode")
        votes: list[Any] = []
        failures = 0
        for voter in [*self.local_llms, *self.external_llms]:
            try:
                votes.append(await voter.predict(payload))
            except Exception as exc:
                failures += 1
                logger.debug("voter failed: %s", exc)
        if not votes:
            return _unavailable("voter_exception" if failures else "no_voters")
        cleaned: list[dict[str, Any]] = []
        for item in votes:
            if not isinstance(item, dict) or "allow" not in item:
                raise TypeError("malformed vote")
            side = str(item.get("direction") or "").strip().upper()
            if side == "HOLD":
                return _unavailable("hold")
            raw_confidence = item.get("confidence", 0.0 if not item.get("allow") else None)
            if raw_confidence is None:
                raise TypeError("missing confidence")
            confidence = float(raw_confidence)
            if math.isnan(confidence) or math.isinf(confidence):
                return _unavailable("nonfinite_confidence", confidence=confidence)
            if item.get("allow") and side not in ("BUY", "SELL"):
                return _unavailable("invalid_direction")
            cleaned.append({**item, "confidence": confidence, "direction": side or None})
        direction = _aggregate_direction(cleaned)
        total_conf = sum(float(vote["confidence"]) for vote in cleaned)
        allow_score = sum(
            float(vote["confidence"]) if vote.get("allow") else 0.0 for vote in cleaned
        ) / (total_conf + 1e-6)
        if direction not in ("BUY", "SELL") or not (allow_score > 0.5):
            reason = (
                "conflicting_or_missing_direction"
                if direction not in ("BUY", "SELL")
                else "allow_threshold"
            )
            return {
                "allow": False,
                "confidence": allow_score if math.isfinite(allow_score) else 0.0,
                "direction": None,
                "status": "abstain",
                "reason": reason,
            }
        return {
            "allow": True,
            "confidence": allow_score,
            "direction": direction,
            "status": "approved",
            "reason": "",
        }


def _env_model(var: str, default: str) -> str:
    """Treat unset or blank env as missing so defaults still apply."""
    v = (os.getenv(var) or "").strip()
    return v if v else default


def _openai_compat_enabled() -> bool:
    if (os.getenv("OPENAI_API_KEY") or "").strip():
        return True
    base = (os.getenv("OPENAI_BASE_URL") or "").strip()
    return bool(base) and "api.openai.com" not in base


def _fill_external_voters(external: list[LLMVoter]) -> None:
    """Append all configured API voters (OpenAI-compatible, Anthropic, etc.)."""
    from forex_bot.openai_voter import OpenAIVoter

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


def _build_default_ensemble() -> AIEnsemble:
    from forex_bot.experiment import normalize_ensemble_mode

    mode = normalize_ensemble_mode()
    external: list[LLMVoter] = []
    if mode in ("api", "hybrid"):
        _fill_external_voters(external)
    logger.info(
        "AI ensemble: mode=%s local_voters=0 external_voters=%s",
        mode,
        len(external),
    )
    return AIEnsemble(local_llms=[], external_llms=external, mode=mode)


ai = _build_default_ensemble()
