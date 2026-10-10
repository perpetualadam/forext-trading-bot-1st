"""Standalone GET-only OANDA candle client. No order, account, or trade endpoints."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

APPROVED_PATH = "/v3/instruments/{instrument}/candles"
APPROVED_INSTRUMENTS = frozenset(
    {"EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"}
)
HOSTS = {
    "practice": "api-fxpractice.oanda.com",
    "live": "api-fxtrade.oanda.com",
}
GRANULARITY = "M5"
PRICE = "MBA"
MAX_CANDLES = 5000
WINDOW_DAYS = 7
MIN_INTERVAL_SEC = 1.0
MAX_RETRIES = 2
TIMEOUT_SEC = 20.0
START = datetime(2026, 9, 1, tzinfo=timezone.utc)

FORBIDDEN_FRAGMENTS = (
    "/orders",
    "/trades",
    "/positions",
    "/accounts",
    "/transactions",
    "/configuration",
    "/summary",
)


class ReadOnlyViolation(RuntimeError):
    pass


class RedirectBlocked(RuntimeError):
    pass


class AuthFailed(RuntimeError):
    pass


@dataclass
class PageResult:
    status: int
    body: dict[str, Any]
    url_path: str
    instrument: str


def redact(text: str, token: str) -> str:
    if token and token in text:
        return text.replace(token, "[REDACTED]")
    return text


def candle_url(environment: str, instrument: str) -> str:
    if environment not in HOSTS:
        raise ReadOnlyViolation("unverified environment")
    if instrument not in APPROVED_INSTRUMENTS:
        raise ReadOnlyViolation("instrument not approved")
    path = APPROVED_PATH.format(instrument=instrument)
    if any(frag in path for frag in FORBIDDEN_FRAGMENTS):
        raise ReadOnlyViolation("forbidden path")
    return f"https://{HOSTS[environment]}{path}"


def assert_request(url: str, params: dict[str, str], *, environment: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ReadOnlyViolation("https required")
    if parsed.netloc != HOSTS.get(environment):
        raise ReadOnlyViolation("host not approved")
    if parsed.query:
        raise ReadOnlyViolation("query must be separate from url")
    parts = parsed.path.split("/")
    if parts[:3] != ["", "v3", "instruments"] or len(parts) != 5 or parts[4] != "candles":
        raise ReadOnlyViolation("path is not the candle endpoint")
    if parts[3] not in APPROVED_INSTRUMENTS:
        raise ReadOnlyViolation("instrument not approved")
    if any(frag in parsed.path for frag in FORBIDDEN_FRAGMENTS):
        raise ReadOnlyViolation("forbidden path")
    allowed = {"granularity", "price", "from", "to"}
    if set(params) - allowed:
        raise ReadOnlyViolation("unexpected parameter")
    if params.get("granularity") != GRANULARITY or params.get("price") != PRICE:
        raise ReadOnlyViolation("granularity or price not approved")


def latest_completed_m5(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    floored = now.replace(minute=(now.minute // 5) * 5, second=0)
    return floored - timedelta(minutes=5)


def windows(start: datetime, end: datetime, *, days: int = WINDOW_DAYS) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    cur = start
    step = timedelta(days=days)
    while cur < end:
        nxt = min(cur + step, end)
        out.append((cur, nxt))
        cur = nxt
    return out


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000000Z")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        raise RedirectBlocked(f"redirect {code} blocked")


def default_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect)


def fetch_candles(
    *,
    environment: str,
    instrument: str,
    start: datetime,
    end: datetime,
    token: str,
    opener: urllib.request.OpenerDirector | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> PageResult:
    url = candle_url(environment, instrument)
    params = {
        "granularity": GRANULARITY,
        "price": PRICE,
        "from": _rfc3339(start),
        "to": _rfc3339(end),
    }
    assert_request(url, params, environment=environment)
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        full,
        method="GET",
        headers={
            "Authorization": "Bearer" + " " + token,
            "Accept-Datetime-Format": "RFC3339",
            "User-Agent": "stage-g3-readonly-candles",
        },
    )
    client = opener or default_opener()
    attempt = 0
    while True:
        try:
            with client.open(req, timeout=TIMEOUT_SEC) as resp:
                status = int(getattr(resp, "status", 200))
                raw = resp.read()
            break
        except RedirectBlocked:
            raise
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            detail = redact(exc.read().decode("utf-8", errors="replace")[:300], token)
            if status in (301, 302, 303, 307, 308):
                raise RedirectBlocked("redirect status blocked") from None
            if status in (401, 403):
                raise AuthFailed(f"auth failed HTTP {status}") from None
            if status == 429 or status >= 500:
                if attempt >= MAX_RETRIES:
                    raise RuntimeError(f"HTTP {status} after retries") from None
                retry_after = 2.0 * (attempt + 1)
                header = exc.headers.get("Retry-After") if exc.headers else None
                if header:
                    try:
                        retry_after = min(30.0, float(header))
                    except ValueError:
                        retry_after = 2.0 * (attempt + 1)
                attempt += 1
                sleep(retry_after)
                continue
            raise RuntimeError(f"HTTP {status} {detail}") from None
        except urllib.error.URLError:
            if attempt >= MAX_RETRIES:
                raise RuntimeError("transport failed") from None
            attempt += 1
            sleep(1.0)
            continue
    try:
        body = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("malformed JSON") from exc
    if not isinstance(body, dict):
        raise TypeError("malformed payload")
    return PageResult(status=status, body=body, url_path=urllib.parse.urlparse(url).path, instrument=instrument)


def request_plan(*, environment: str, end: datetime) -> dict[str, Any]:
    spans = windows(START, end)
    return {
        "endpoint": "GET /v3/instruments/{instrument}/candles",
        "host": HOSTS[environment],
        "environment": environment,
        "instruments": sorted(APPROVED_INSTRUMENTS),
        "granularity": GRANULARITY,
        "price": PRICE,
        "start": START.isoformat(),
        "end": end.isoformat(),
        "window_days": WINDOW_DAYS,
        "windows": [[a.isoformat(), b.isoformat()] for a, b in spans],
        "max_candles_documented": MAX_CANDLES,
        "estimated_requests": len(APPROVED_INSTRUMENTS) * len(spans),
        "min_interval_sec": MIN_INTERVAL_SEC,
        "max_retries": MAX_RETRIES,
        "timeout_sec": TIMEOUT_SEC,
        "redirects": "blocked",
        "account_endpoints": False,
    }
