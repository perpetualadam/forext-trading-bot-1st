"""HTTP client for documented Trading Economics calendar URLs.

Default transport makes no network calls. The API key is never placed in the
URL, never written to metadata, and never printed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from forex_bot.decision_quality.trading_economics.events import PlannedRequest, public_url

API_KEY_ENV = "TRADING_ECONOMICS_API_KEY"
SECRET_QUERY_KEYS = frozenset({"c", "client", "apikey", "api_key", "token", "key"})

_KEY_IN_TEXT = re.compile(r"(?i)([?&](?:c|client|apikey|api_key|token)=)[^&\s]+")


class TradingEconomicsClientError(RuntimeError):
    """Base client error. str(self) must never contain a credential."""


class AuthError(TradingEconomicsClientError):
    pass


class RateLimitError(TradingEconomicsClientError):
    def __init__(self, message: str, *, retry_after: str | None = None, status: int = 429):
        super().__init__(message)
        self.retry_after = retry_after
        self.status = status


class HttpError(TradingEconomicsClientError):
    def __init__(self, message: str, *, status: int):
        super().__init__(message)
        self.status = status


class MalformedResponseError(TradingEconomicsClientError):
    pass


def read_api_key(env: dict[str, str] | None = None) -> str | None:
    source = env if env is not None else os.environ
    raw = (source.get(API_KEY_ENV) or "").strip()
    return raw or None


def redact_secret(text: str, secret: str | None = None) -> str:
    out = str(text or "")
    if secret:
        out = out.replace(secret, "<redacted>")
    out = _KEY_IN_TEXT.sub(r"\1<redacted>", out)
    out = re.sub(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?)[^\s'\"]+", r"\1<redacted>", out)
    return out


def redact_url(url: str, secret: str | None = None) -> str:
    parts = urlsplit(url)
    kept = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in SECRET_QUERY_KEYS:
            kept.append((key, "<redacted>"))
        else:
            kept.append((key, value))
    query = urlencode(kept)
    cleaned = urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
    return redact_secret(cleaned, secret)


@dataclass
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)
    url: str = ""


Transport = Callable[[str, dict[str, str]], HttpResponse]


class DryRunTransport:
    """Records planned calls and never opens a socket."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, headers: dict[str, str]) -> HttpResponse:
        self.calls.append((url, dict(headers)))
        raise AssertionError("dry-run transport must not be invoked for a live GET")


def requests_transport(url: str, headers: dict[str, str]) -> HttpResponse:
    import requests

    resp = requests.get(url, headers=headers, timeout=60)
    return HttpResponse(
        status=int(resp.status_code),
        body=resp.content or b"",
        headers={str(k): str(v) for k, v in resp.headers.items()},
        url=redact_url(str(resp.url)),
    )


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": api_key, "Accept": "application/json"}


def parse_calendar_payload(body: bytes) -> list[dict[str, Any]]:
    text = body.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MalformedResponseError(f"response is not JSON: {exc}") from exc
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        payload = payload["data"]
    if not isinstance(payload, list):
        raise MalformedResponseError(f"calendar payload is {type(payload).__name__}, expected list")
    rows: list[dict[str, Any]] = []
    for i, item in enumerate(payload):
        if not isinstance(item, dict):
            raise MalformedResponseError(f"row {i} is {type(item).__name__}, expected object")
        rows.append(item)
    return rows


def fetch_planned(
    req: PlannedRequest,
    *,
    api_key: str,
    transport: Transport,
) -> tuple[HttpResponse, list[dict[str, Any]]]:
    url = public_url(req)
    headers = _auth_headers(api_key)
    resp = transport(url, headers)
    if resp.status in (401, 403):
        raise AuthError(f"authentication failed (HTTP {resp.status})")
    if resp.status == 429:
        retry = None
        for key, value in resp.headers.items():
            if key.lower() == "retry-after":
                retry = value
                break
        raise RateLimitError("rate limited (HTTP 429)", retry_after=retry, status=429)
    if resp.status >= 400:
        raise HttpError(f"HTTP {resp.status}", status=resp.status)
    rows = parse_calendar_payload(resp.body)
    return resp, rows
