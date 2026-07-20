"""Pluggable local / external LLM-style voters (deterministic quant stub by default)."""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Protocol

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


def _quant_stub_vote(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic filter from trend (MA cross) + momentum + ATR presence.
    Expects ``ma_fast`` / ``ma_slow`` (or ``sma_*``) and ``returns`` / ``atr`` when possible.
    """
    price = float(payload.get("price") or 0.0)
    sma_fast = payload.get("sma_fast")
    if sma_fast is None:
        sma_fast = payload.get("ma_fast")
    sma_slow = payload.get("sma_slow")
    if sma_slow is None:
        sma_slow = payload.get("ma_slow")
    try:
        sma_fast = float(sma_fast if sma_fast is not None else price)
        sma_slow = float(sma_slow if sma_slow is not None else price)
    except (TypeError, ValueError):
        return {"allow": False, "confidence": 0.0, "direction": None}

    returns = float(payload.get("returns") or 0.0)
    try:
        atr = float(payload.get("atr") or 0.0)
    except (TypeError, ValueError):
        atr = 0.0

    if math.isnan(sma_fast) or math.isnan(sma_slow):
        return {"allow": False, "confidence": 0.0, "direction": None}

    eps = max(0.0, _env_float("STUB_SMA_EPSILON", 1e-6))
    mom_thr = max(0.0, _env_float("STUB_MOMENTUM_THRESHOLD", 0.0001))
    conf_scale = max(1e-12, _env_float("STUB_CONFIDENCE_SCALE", 1000.0))

    if sma_fast > sma_slow + eps:
        direction = "BUY"
    elif sma_fast < sma_slow - eps:
        direction = "SELL"
    else:
        return {"allow": False, "confidence": 0.0, "direction": None}

    momentum_strength = abs(returns)
    vol_ok = atr > 0 and not math.isnan(atr)
    allow = momentum_strength > mom_thr and vol_ok

    confidence = min(1.0, max(0.0, momentum_strength * conf_scale))

    return {"allow": allow, "confidence": confidence, "direction": direction}


def _aggregate_direction(votes: list[dict[str, Any]]) -> str:
    buy_w = 0.0
    sell_w = 0.0
    for v in votes:
        d = str(v.get("direction") or "").upper()
        w = float(v.get("confidence", 0.5))
        if d == "BUY":
            buy_w += w
        elif d == "SELL":
            sell_w += w
    if buy_w > sell_w:
        return "BUY"
    if sell_w > buy_w:
        return "SELL"
    # Tie-break: highest-confidence vote with a side (no randomness).
    best_d = "BUY"
    best_c = -1.0
    for v in votes:
        d = str(v.get("direction") or "").upper()
        if d not in ("BUY", "SELL"):
            continue
        c = float(v.get("confidence", 0.0))
        if c > best_c:
            best_c = c
            best_d = d
    if best_c >= 0:
        return best_d
    return "BUY"


class LLMVoter(Protocol):
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class LocalLLM:
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _quant_stub_vote(payload)


class ExternalLLMAPI:
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _quant_stub_vote(payload)


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
            logger.warning(
                "AI ensemble: no voter outputs; failing closed (allow=False). "
                "Configure LLM keys or ensure LocalLLM stub is enabled."
            )
            return {"allow": False, "confidence": 0.0, "direction": "BUY"}
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
    local: list[LLMVoter] = []
    external: list[LLMVoter] = []

    if mode == "quant":
        local = [LocalLLM()]
        if _stub_disabled():
            logger.info("ENSEMBLE_MODE=quant: LocalLLM enabled (AI_DISABLE_STUB ignored for quant baseline).")
    elif mode == "api":
        _fill_external_voters(external)
        if not external:
            logger.warning("ENSEMBLE_MODE=api but no API keys configured; falling back to quant LocalLLM.")
            local = [LocalLLM()]
    else:
        if not _stub_disabled():
            local = [LocalLLM()]
        _fill_external_voters(external)
        if not local and not external:
            in_bt = os.getenv("FOREX_BACKTEST", "").strip().lower() in ("1", "true", "yes", "on")
            logger.warning(
                "Hybrid ensemble: no API keys and stub disabled — using quant LocalLLM only.%s",
                " (FOREX_BACKTEST=1)" if in_bt else "",
            )
            local = [LocalLLM()]

    logger.info(
        "AI ensemble: mode=%s local_voters=%s external_voters=%s",
        mode,
        len(local),
        len(external),
    )
    return AIEnsemble(local_llms=local, external_llms=external)


ai = _build_default_ensemble()
