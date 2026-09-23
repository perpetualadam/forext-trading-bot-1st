"""Official BLS archive fetch. Research-only. Reuses Experiment D headers/pacing."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
}
PACE_SECONDS = 1.2


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    content: bytes
    content_type: str | None
    final_url: str


def fetch_url(url: str, *, timeout: int = 45, session: requests.Session | None = None) -> FetchResult:
    client = session or requests
    resp = client.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    return FetchResult(
        url=url,
        status=int(resp.status_code),
        content=resp.content or b"",
        content_type=resp.headers.get("Content-Type"),
        final_url=str(resp.url),
    )


def paced_sleep(seconds: float = PACE_SECONDS) -> None:
    time.sleep(seconds)
