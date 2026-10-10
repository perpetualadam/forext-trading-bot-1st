"""Stage G.3 read-only acquisition tests. No live broker calls."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path

import pytest

from forex_bot.research.adaptive_ensemble.conversion import FxQuote, RateTable
from forex_bot.research.adaptive_ensemble.g3_acquire import normalise_pages
from forex_bot.research.adaptive_ensemble.g3_convert import convert_signed
from forex_bot.research.adaptive_ensemble.isolation import forbidden_hits
from forex_bot.research.adaptive_ensemble.oanda_readonly import (
    AuthFailed,
    ReadOnlyViolation,
    RedirectBlocked,
    assert_request,
    candle_url,
    fetch_candles,
    latest_completed_m5,
    redact,
    request_plan,
    windows,
)
from forex_bot.research.adaptive_ensemble.protocol import integrity_hash, load_protocol

REPORTED = "539cdc083f83393a79d254d21385edc6c48e88eb0f085d4549df9fdd6d431bc0"


class _Resp:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _Resp:  # noqa: PYI034
        return self

    def __exit__(self, *_a: object) -> bool:
        return False


class _Opener:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[urllib.request.Request] = []

    def open(self, req: urllib.request.Request, timeout: float = 0) -> _Resp:
        self.calls.append(req)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, _Resp)
        return item


def _http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://example.invalid", code, "err", headers, io.BytesIO(b"secret-body"))


def _payload() -> bytes:
    body = {
        "candles": [
            {
                "complete": True,
                "time": "2026-09-01T00:00:00.000000000Z",
                "bid": {"o": "1.10", "h": "1.11", "l": "1.09", "c": "1.10"},
                "ask": {"o": "1.11", "h": "1.12", "l": "1.10", "c": "1.11"},
            },
            {
                "complete": False,
                "time": "2026-09-01T00:05:00.000000000Z",
                "bid": {"o": "1.10", "h": "1.11", "l": "1.09", "c": "1.10"},
                "ask": {"o": "1.11", "h": "1.12", "l": "1.10", "c": "1.11"},
            },
        ]
    }
    return json.dumps(body).encode("utf-8")


def test_protocol_still_frozen() -> None:
    proto = load_protocol()
    assert proto["integrity_hash"] == REPORTED
    assert integrity_hash(proto) == REPORTED


def test_allowlist_and_get_only() -> None:
    url = candle_url("live", "EUR_USD")
    assert url == "https://api-fxtrade.oanda.com/v3/instruments/EUR_USD/candles"
    with pytest.raises(ReadOnlyViolation):
        candle_url("live", "EUR_GBP")
    with pytest.raises(ReadOnlyViolation):
        candle_url("demo", "EUR_USD")
    params = {"granularity": "M5", "price": "MBA", "from": "2026-09-01T00:00:00.000000000Z", "to": "2026-09-02T00:00:00.000000000Z"}
    assert_request(url, params, environment="live")
    with pytest.raises(ReadOnlyViolation):
        assert_request(url, {**params, "granularity": "H1"}, environment="live")
    with pytest.raises(ReadOnlyViolation):
        assert_request(url + "?count=1", params, environment="live")
    with pytest.raises(ReadOnlyViolation):
        assert_request("https://api-fxtrade.oanda.com/v3/accounts/abc/summary", params, environment="live")


def test_fetch_is_get_m5_and_redacts(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = _Opener([_Resp(_payload())])
    page = fetch_candles(
        environment="practice",
        instrument="USD_JPY",
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 2, tzinfo=timezone.utc),
        token="super-secret-token",
        opener=opener,  # type: ignore[arg-type]
        sleep=lambda _s: None,
    )
    req = opener.calls[0]
    assert req.get_method() == "GET"
    assert req.full_url.startswith("https://api-fxpractice.oanda.com/v3/instruments/USD_JPY/candles?")
    assert "granularity=M5" in req.full_url
    assert "price=MBA" in req.full_url
    assert "super-secret-token" not in req.full_url
    assert page.body["candles"][0]["complete"] is True
    assert redact("super-secret-token leaked", "super-secret-token") == "[REDACTED] leaked"
    monkeypatch.delenv("OANDA_ACCESS_TOKEN", raising=False)


def test_auth_failure_does_not_retry() -> None:
    opener = _Opener([_http_error(401)])
    with pytest.raises(AuthFailed):
        fetch_candles(
            environment="live",
            instrument="EUR_USD",
            start=datetime(2026, 9, 1, tzinfo=timezone.utc),
            end=datetime(2026, 9, 2, tzinfo=timezone.utc),
            token="tok",
            opener=opener,  # type: ignore[arg-type]
            sleep=lambda _s: None,
        )
    assert len(opener.calls) == 1


def test_rate_limit_bounded_then_redirect() -> None:
    opener = _Opener([_http_error(429, "0"), _Resp(_payload())])
    page = fetch_candles(
        environment="live",
        instrument="EUR_USD",
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 2, tzinfo=timezone.utc),
        token="tok",
        opener=opener,  # type: ignore[arg-type]
        sleep=lambda _s: None,
    )
    assert page.status == 200
    opener2 = _Opener([_http_error(302)])
    with pytest.raises(RedirectBlocked):
        fetch_candles(
            environment="live",
            instrument="EUR_USD",
            start=datetime(2026, 9, 1, tzinfo=timezone.utc),
            end=datetime(2026, 9, 2, tzinfo=timezone.utc),
            token="tok",
            opener=opener2,  # type: ignore[arg-type]
            sleep=lambda _s: None,
        )


def test_windows_bounded() -> None:
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 20, tzinfo=timezone.utc)
    spans = windows(start, end, days=7)
    assert spans[0][0] == start
    assert spans[-1][1] == end
    assert all(b > a for a, b in spans)
    plan = request_plan(environment="live", end=latest_completed_m5(datetime(2026, 10, 9, 12, 7, tzinfo=timezone.utc)))
    assert plan["estimated_requests"] == 6 * len(plan["windows"])
    assert plan["account_endpoints"] is False


def test_normalise_drops_incomplete_not_disagreement() -> None:
    pages = [
        {
            "candles": [
                {
                    "complete": True,
                    "time": "2026-09-01T00:00:00Z",
                    "bid": {"o": "1", "h": "1", "l": "1", "c": "1"},
                    "ask": {"o": "1.1", "h": "1.1", "l": "1.1", "c": "1.1"},
                },
                {
                    "complete": True,
                    "time": "2026-09-01T00:00:00Z",
                    "bid": {"o": "9", "h": "9", "l": "9", "c": "9"},
                    "ask": {"o": "9.1", "h": "9.1", "l": "9.1", "c": "9.1"},
                },
                {"complete": False, "time": "2026-09-01T00:05:00Z", "bid": {"c": "1"}, "ask": {"c": "1.1"}},
            ]
        }
    ]
    frame, meta = normalise_pages(pages)
    assert meta["incomplete_excluded"] == 1
    assert meta["conflicts_quarantined"] == 2
    assert frame.empty


def test_signed_conversion_positive_and_negative() -> None:
    when = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    table = RateTable(
        [
            FxQuote(when, "GBP_USD", 1.30, 1.40, "fixture"),
            FxQuote(when, "USD_JPY", 100.0, 110.0, "fixture"),
            FxQuote(when, "USD_CAD", 1.20, 1.25, "fixture"),
            FxQuote(when, "USD_CHF", 0.80, 0.90, "fixture"),
        ]
    )
    eur_pos = convert_signed(pnl_quote=1.40, pair="EUR_USD", when=when, table=table)
    eur_neg = convert_signed(pnl_quote=-1.30, pair="EUR_USD", when=when, table=table)
    assert eur_pos.gbp == pytest.approx(1.0)
    assert eur_neg.gbp == pytest.approx(-1.0)
    assert "ask" in eur_pos.path[-1]
    assert "bid" in eur_neg.path[-1]
    jpy = convert_signed(pnl_quote=110.0, pair="USD_JPY", when=when, table=table)
    assert jpy.gbp == pytest.approx((110.0 / 110.0) / 1.40)
    cad = convert_signed(pnl_quote=-1.20, pair="USD_CAD", when=when, table=table)
    assert cad.gbp == pytest.approx((-1.20 / 1.20) / 1.30)
    chf = convert_signed(pnl_quote=0.90, pair="USD_CHF", when=when, table=table)
    assert chf.gbp == pytest.approx((0.90 / 0.90) / 1.40)
    future = RateTable([FxQuote(when + timedelta(hours=2), "GBP_USD", 1.3, 1.4, "late")])
    blocked = convert_signed(pnl_quote=1.0, pair="EUR_USD", when=when, table=future)
    assert blocked.gbp is None
    stale = RateTable([FxQuote(when - timedelta(hours=30), "GBP_USD", 1.3, 1.4, "old")])
    assert convert_signed(pnl_quote=1.0, pair="EUR_USD", when=when, table=stale).status == "CONVERSION_STALE"
    friday = datetime(2026, 9, 4, 20, tzinfo=timezone.utc)
    monday = datetime(2026, 9, 7, 8, tzinfo=timezone.utc)
    weekend = RateTable([FxQuote(friday, "GBP_USD", 1.3, 1.4, "fri")])
    held = convert_signed(pnl_quote=1.4, pair="GBP_USD", when=monday, table=weekend)
    assert held.status == "ok"
    assert held.reason == "weekend_last_quote"


def test_no_broker_imports_and_stage_artifacts() -> None:
    assert forbidden_hits() == {}
    text = Path("forex_bot/research/adaptive_ensemble/oanda_readonly.py").read_text(encoding="utf-8")
    assert "oanda_exec" not in text
    assert "AccountSummary" not in text
    assess = json.loads(Path("data/research/adaptive_ensemble/assessment.json").read_text(encoding="utf-8"))
    assert assess["assessment"] == "EXPLORATORY_NO_CREDIBLE_EDGE"
