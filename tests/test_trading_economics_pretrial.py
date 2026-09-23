"""Trading Economics pretrial harness. Zero real API requests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from forex_bot.decision_quality.isolation import assert_package_cannot_write_broker, forbidden_hits_in_source
from forex_bot.decision_quality.trading_economics.client import (
    API_KEY_ENV,
    AuthError,
    HttpError,
    HttpResponse,
    MalformedResponseError,
    RateLimitError,
    fetch_planned,
    parse_calendar_payload,
    public_url,
    read_api_key,
    redact_secret,
    redact_url,
)
from forex_bot.decision_quality.trading_economics.compare import empty_econoday_slot, comparison_key_from_te
from forex_bot.decision_quality.trading_economics.download import main, run_download
from forex_bot.decision_quality.trading_economics.events import TARGETS, horizon_window, plan_requests
from forex_bot.decision_quality.trading_economics.schema import (
    FORECAST_FIELD,
    TE_FORECAST_FIELD,
    normalize_record,
)
from forex_bot.decision_quality.trading_economics.store import write_raw_response
from forex_bot.decision_quality.trading_economics.surprise import surprise_raw
from forex_bot.decision_quality.trading_economics.timestamps import parse_provider_datetime
from forex_bot.decision_quality.trading_economics.validate import validate_event_vintages

ROOT = Path(__file__).resolve().parents[1]
HARNESS_DIR = ROOT / "forex_bot" / "decision_quality" / "trading_economics"
REPORT = ROOT / "reports" / "decision_quality" / "trading_economics_pretrial_readiness.md"
ORDINARY = ROOT / "tests" / "fixtures" / "trading_economics" / "ordinary_calendar.json"

PRE_RELEASE = {
    "CalendarId": "CPI1",
    "Date": "2025-09-11T12:30:00Z",
    "Country": "United States",
    "Category": "Inflation Rate",
    "Event": "CPI YoY",
    "Forecast": "2.3%",
    "TEForecast": "2.5%",
    "Actual": "",
    "Previous": "2.2%",
    "Revised": "",
    "LastUpdate": "2025-09-10T18:00:00Z",
    "Reference": "Aug",
}
FIRST_PRINT = {
    **PRE_RELEASE,
    "Actual": "2.4%",
    "ActualValue": 2.4,
    "ForecastValue": 2.3,
    "LastUpdate": "2025-09-11T12:30:05Z",
}
REVISED_LATER = {
    **FIRST_PRINT,
    "Actual": "2.6%",
    "ActualValue": 2.6,
    "LastUpdate": "2025-10-01T12:30:00Z",
}


def test_isolation_includes_trading_economics_package():
    assert assert_package_cannot_write_broker() == []
    for path in HARNESS_DIR.glob("*.py"):
        assert forbidden_hits_in_source(path.read_text(encoding="utf-8")) == []


def test_api_key_never_written_or_logged(tmp_path, capsys, monkeypatch):
    secret = "te-secret-unit-test-key-xyz"
    monkeypatch.setenv(API_KEY_ENV, secret)
    code = main(["--dry-run", "--profile", "sample", "--data-dir", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert secret not in out
    assert "<redacted>" in redact_secret(f"c={secret}", secret)
    reqs = plan_requests(start="2024-01-01", end="2024-02-01")
    stored = write_raw_response(
        raw_dir=tmp_path / "raw",
        req=reqs[0],
        body=b"[]",
        status=200,
        record_count=0,
        retrieved_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        response_url=public_url(reqs[0]) + f"&c={secret}",
    )
    meta = json.loads(stored.meta_path.read_text(encoding="utf-8"))
    dumped = json.dumps(meta)
    assert secret not in dumped
    assert meta["api_key_stored"] is False
    assert "c=" not in dumped or "<redacted>" in dumped


def test_dry_run_performs_zero_requests(monkeypatch, tmp_path):
    def boom(*_a, **_k):
        raise AssertionError("requests.get must not run in dry-run")

    monkeypatch.setattr("requests.get", boom)
    payload = run_download(profile="sample", confirm=False, data_root=tmp_path)
    assert payload["dry_run"] is True
    assert payload["fetched"] == []
    assert "DRY RUN" in payload["message"]
    code = main(["--dry-run", "--data-dir", str(tmp_path)])
    assert code == 0


def test_forecast_and_teforecast_remain_separate():
    row = json.loads(ORDINARY.read_text(encoding="utf-8"))[0]
    event = normalize_record(row)
    assert FORECAST_FIELD == "Forecast"
    assert TE_FORECAST_FIELD == "TEForecast"
    assert event.forecast_consensus == "253K"
    assert event.te_forecast == "253.1K"
    assert event.forecast_consensus != event.te_forecast


def test_missing_forecast_does_not_fall_back_to_teforecast():
    row = {
        "CalendarId": "1",
        "Date": "2024-01-01T12:30:00Z",
        "Forecast": "",
        "TEForecast": "2.5%",
        "Actual": "2.4%",
    }
    event = normalize_record(row)
    assert event.forecast_consensus is None
    assert event.te_forecast == "2.5%"
    result = surprise_raw([row])
    assert result.accepted is False
    assert result.te_forecast_used is False or result.reason != "ok"
    assert result.surprise_raw is None


def test_timestamp_conversion():
    zulu = parse_provider_datetime("2016-12-01T13:30:00Z")
    assert zulu.utc == "2016-12-01T13:30:00Z"
    assert "naive_datetime_no_offset" not in zulu.issues
    naive = parse_provider_datetime("2016-12-01T13:30:00")
    assert naive.utc == "2016-12-01T13:30:00Z"
    assert "naive_datetime_no_offset" in naive.issues
    assert "timezone_assumed_from_documentation_utc_claim" in naive.issues
    missing = parse_provider_datetime(None)
    assert "missing_timestamp" in missing.issues
    bad = parse_provider_datetime("not-a-date")
    assert "unparseable_timestamp" in bad.issues


def test_duplicate_event_handling():
    rows = json.loads(ORDINARY.read_text(encoding="utf-8"))
    doubled = rows + [{**rows[0], "Actual": "270K"}]
    verdict = validate_event_vintages(doubled)
    assert "87213" in verdict.duplicate_event_ids


def test_raw_response_preservation(tmp_path):
    req = plan_requests(start="2016-12-01", end="2017-02-25")[0]
    body = ORDINARY.read_bytes()
    first = write_raw_response(
        raw_dir=tmp_path,
        req=req,
        body=body,
        status=200,
        record_count=1,
        retrieved_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    assert first.body_path.read_bytes() == body
    with pytest.raises(FileExistsError):
        write_raw_response(
            raw_dir=tmp_path,
            req=req,
            body=body,
            status=200,
            record_count=1,
            retrieved_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
    second = write_raw_response(
        raw_dir=tmp_path,
        req=req,
        body=body,
        status=200,
        record_count=1,
        retrieved_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )
    assert second.body_path != first.body_path
    assert first.body_path.exists()


def test_normalization_copies_documented_fields_only():
    event = normalize_record(json.loads(ORDINARY.read_text(encoding="utf-8"))[0], retrieved_at="t", raw_sha256="abc")
    assert event.provider == "trading_economics"
    assert event.event_id == "87213"
    assert event.scheduled_time_raw == "2016-12-01T13:30:00"
    assert event.retrieved_at == "t"
    assert event.raw_sha256 == "abc"


def test_surprise_rejected_when_vintage_validation_fails():
    ordinary = json.loads(ORDINARY.read_text(encoding="utf-8"))
    result = surprise_raw(ordinary)
    assert result.accepted is False
    assert result.reason == "vintage_validation_failed"
    assert result.surprise_raw is None


def test_surprise_accepted_only_when_required_pit_fields_pass():
    result = surprise_raw([PRE_RELEASE, FIRST_PRINT, REVISED_LATER])
    assert result.accepted is True
    assert result.te_forecast_used is False
    assert result.consensus_pre_release == pytest.approx(2.3)
    assert result.actual_first_print == pytest.approx(2.4)
    assert result.surprise_raw == pytest.approx(0.1)


def test_http_failure_auth_rate_limit_malformed():
    req = plan_requests(start="2024-01-01", end="2024-02-01")[0]

    def status(code: int, body: bytes = b"[]", headers=None):
        return HttpResponse(status=code, body=body, headers=headers or {}, url=public_url(req))

    with pytest.raises(AuthError):
        fetch_planned(req, api_key="x", transport=lambda u, h: status(401))
    with pytest.raises(RateLimitError) as ri:
        fetch_planned(req, api_key="x", transport=lambda u, h: status(429, headers={"Retry-After": "30"}))
    assert ri.value.retry_after == "30"
    with pytest.raises(HttpError) as hi:
        fetch_planned(req, api_key="x", transport=lambda u, h: status(500, b"oops"))
    assert hi.value.status == 500
    with pytest.raises(MalformedResponseError):
        parse_calendar_payload(b"<html>nope</html>")
    with pytest.raises(MalformedResponseError):
        parse_calendar_payload(b'{"error":"nope"}')


def test_ordinary_row_is_not_pit_safe():
    ordinary = json.loads(ORDINARY.read_text(encoding="utf-8"))
    verdict = validate_event_vintages(ordinary)
    assert verdict.vintage_ok is False
    assert verdict.consensus_pre_release_ok is False
    assert verdict.first_print_actual_ok is False
    assert verdict.pit_endpoint_differs is None


def test_redact_url_strips_query_key():
    raw = "https://api.tradingeconomics.com/calendar?c=abc123&f=json"
    assert "abc123" not in redact_url(raw)
    assert "<redacted>" in redact_url(raw)


def test_request_plan_is_three_range_calls_not_per_event():
    start, end = horizon_window("5y", now_utc=datetime(2026, 9, 23, tzinfo=timezone.utc))
    reqs = plan_requests(start=start, end=end)
    assert len(reqs) == 3
    assert {r.family_id for r in reqs} == {"cpi", "nfp", "fomc"}
    assert all("/calendar/country/" in r.path for r in reqs)
    assert all(r.start == start and r.end == end for r in reqs)


def test_read_api_key_empty_is_none(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    assert read_api_key() is None
    monkeypatch.setenv(API_KEY_ENV, "  ")
    assert read_api_key() is None


def test_econoday_comparison_slot_is_empty_placeholder():
    event = normalize_record(PRE_RELEASE)
    key = comparison_key_from_te(event, "2025-09-11T12:30:00Z", "cpi")
    from forex_bot.decision_quality.trading_economics.compare import ProviderPrint

    row = empty_econoday_slot(
        key,
        ProviderPrint("trading_economics", "CPI1", "2.3%", None, False),
    )
    assert row.econoday is None
    assert row.consensus_match == "MISSING_ECONODAY"


def test_confirm_without_key_sends_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)

    def boom(*_a, **_k):
        raise AssertionError("no request")

    with pytest.raises(SystemExit):
        run_download(profile="sample", confirm=True, data_root=tmp_path, transport=boom, env={})


REQUIRED_REPORT = (
    "OFFICIAL API SOURCES",
    "ENDPOINTS",
    "POINT-IN-TIME ENDPOINT",
    "AVAILABLE FIELDS",
    "AUTHENTICATION",
    "REQUEST LIMITS",
    "REQUEST-EFFICIENCY PLAN",
    "NORMALIZED SCHEMA",
    "PIT VALIDATION RULES",
    "SAMPLE DOWNLOAD PLAN",
    "CROSS-PROVIDER COMPARISON PLAN",
    "KNOWN UNCERTAINTIES",
    "TEST RESULTS",
    "CAN THE CODE BE RUN IN DRY-RUN WITHOUT CREDENTIALS?",
    "REAL API CALLS MADE?",
    "TRADING ECONOMICS CREDENTIAL PRESENT?",
    "LIVE BOT CODE CHANGED?",
    "OANDA ORDERS SENT?",
    "DOCKER RESTARTED?",
)


def test_readiness_report_has_required_sections():
    text = REPORT.read_text(encoding="utf-8")
    missing = [title for title in REQUIRED_REPORT if title not in text]
    assert missing == []
    assert "YES" in text
    assert "REAL API CALLS MADE?" in text
