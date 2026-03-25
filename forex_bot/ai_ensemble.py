"""Pluggable local / external LLM-style voters (stubs match original behavior)."""

from __future__ import annotations

import logging
import random
from typing import Any, Protocol

import numpy as np

logger = logging.getLogger(__name__)


class LLMVoter(Protocol):
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class LocalLLM:
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = payload
        return {"allow": random.random() > 0.3, "confidence": random.uniform(0.5, 1.0)}


class ExternalLLMAPI:
    async def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ = payload
        return {"allow": random.random() > 0.3, "confidence": random.uniform(0.5, 1.0)}


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
        direction = (
            "BUY"
            if np.mean([random.choice([1, -1]) * float(v["confidence"]) for v in votes]) > 0
            else "SELL"
        )
        return {"allow": allow_score > 0.5, "confidence": allow_score, "direction": direction}


ai = AIEnsemble(local_llms=[LocalLLM()], external_llms=[])
