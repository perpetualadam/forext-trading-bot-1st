"""Mocked failure / parse behaviour of production voters. No real HTTP."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
import requests

from forex_bot.ai_ensemble import AIEnsemble
from forex_bot.openai_voter import OpenAIVoter
from forex_bot.anthropic_voter import AnthropicVoter


class _Stub:
    def __init__(self, out=None, exc=None):
        self.out = out or {"allow": True, "confidence": 0.7, "direction": "SELL"}
        self.exc = exc

    async def predict(self, payload):
        if self.exc:
            raise self.exc
        return dict(self.out)


def test_vote_omits_failed_voter_and_uses_remaining():
    ens = AIEnsemble(local_llms=[_Stub()], external_llms=[_Stub(exc=RuntimeError("timeout"))])
    out = asyncio.run(ens.vote({}, "EUR_USD"))
    assert out["allow"] is True
    assert out["direction"] == "SELL"


def test_vote_fail_closed_when_every_voter_raises():
    ens = AIEnsemble(
        local_llms=[_Stub(exc=TimeoutError("t"))],
        external_llms=[_Stub(exc=RuntimeError("down"))],
    )
    out = asyncio.run(ens.vote({}, "EUR_USD"))
    assert out["allow"] is False
    assert out["confidence"] == 0.0


def _openai_ok(content: str, status=200):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def test_openai_voter_hold_coerced_to_buy():
    voter = OpenAIVoter(api_key="x", timeout=1)
    with patch("forex_bot.openai_voter.requests.post", return_value=_openai_ok(
        '{"allow": true, "confidence": 0.9, "direction": "HOLD"}'
    )):
        out = asyncio.run(voter.predict({"symbol": "EUR_USD"}))
    assert out["direction"] == "BUY"
    assert out["allow"] is True


def test_openai_voter_missing_allow_defaults_false():
    voter = OpenAIVoter(api_key="x", timeout=1)
    with patch("forex_bot.openai_voter.requests.post", return_value=_openai_ok(
        '{"confidence": 0.9, "direction": "SELL"}'
    )):
        out = asyncio.run(voter.predict({}))
    assert out["allow"] is False
    assert out["direction"] == "SELL"


def test_openai_voter_malformed_json_raises():
    voter = OpenAIVoter(api_key="x", timeout=1)
    with patch("forex_bot.openai_voter.requests.post", return_value=_openai_ok("not-json")):
        with pytest.raises(Exception):
            asyncio.run(voter.predict({}))


def test_openai_voter_empty_content_raises():
    voter = OpenAIVoter(api_key="x", timeout=1)
    with patch("forex_bot.openai_voter.requests.post", return_value=_openai_ok("")):
        with pytest.raises(Exception):
            asyncio.run(voter.predict({}))


def test_openai_voter_timeout_raises():
    voter = OpenAIVoter(api_key="x", timeout=1)
    with patch("forex_bot.openai_voter.requests.post", side_effect=requests.Timeout("t")):
        with pytest.raises(Exception):
            asyncio.run(voter.predict({}))


def test_openai_voter_http_error_raises():
    voter = OpenAIVoter(api_key="x", timeout=1)
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.HTTPError("429")
    with patch("forex_bot.openai_voter.requests.post", return_value=resp):
        with pytest.raises(Exception):
            asyncio.run(voter.predict({}))


def test_anthropic_unknown_direction_coerced_to_buy():
    voter = AnthropicVoter(api_key="x")
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "content": [{"type": "text", "text": '{"allow": true, "confidence": 0.4, "direction": "WAIT"}'}]
    }
    with patch("forex_bot.anthropic_voter.requests.post", return_value=resp):
        out = asyncio.run(voter.predict({}))
    assert out["direction"] == "BUY"
    assert out["allow"] is True
