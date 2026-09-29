"""Stage 7A Forex Factory export probe tests. No live Forex Factory requests."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_PPATH = Path("reports/decision_quality/_macro_forex_factory_probe_stage7a.py")
_PSPEC = importlib.util.spec_from_file_location("macro_ff_probe_stage7a", _PPATH)
P = importlib.util.module_from_spec(_PSPEC)
_PSPEC.loader.exec_module(P)

_RPATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_RSPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_7a", _RPATH)
R = importlib.util.module_from_spec(_RSPEC)
_RSPEC.loader.exec_module(R)

UTC = timezone.utc
FIXTURE = Path("tests/fixtures/forex_factory_stage7a.sanitized.json")
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
CLOCK = datetime(2026, 9, 29, 21, 0, tzinfo=UTC)
PROD_IMPORT_PATHS = (
    Path("reports/decision_quality/_macro_prospective_scheduler.py"),
    Path("reports/decision_quality/_macro_prospective_adapters.py"),
    Path("reports/decision_quality/macro_prospective_cli.py"),
    Path("forex_bot/bot_loop.py"),
)


def _rows() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]


def _payload(rows: list[dict] | None = None) -> bytes:
    return json.dumps(rows if rows is not None else _rows()).encode("utf-8")


def test_request_guard_and_http_failure_no_retry_no_html_fallback(tmp_path):
    spec = P.public_request_spec()
    assert spec["host"] == "nfs.faireconomy.media"
    assert spec["path"] == "/ff_calendar_thisweek.json"
    assert spec["html_scraping"] is False
    assert spec["fallback_html"] is False
    calls = {"n": 0}

    def transport(url, headers):
        calls["n"] += 1
        assert url == P.EXPORT_URL
        assert "text/html" not in headers.get("Accept", "")
        return 403, b'{"message":"denied"}', {}

    guard = P.RequestGuard(1)
    out = P.run_probe(dest=tmp_path / "a", transport=transport, live=True, guard=guard, clock=lambda tz=None: CLOCK)
    assert out["http_status"] == 403
    assert out["request_count"] == 1
    assert out["html_scraping_used"] is False
    with pytest.raises(RuntimeError, match="request #2 rejected"):
        P.run_probe(dest=tmp_path / "b", transport=transport, live=True, guard=guard, clock=lambda tz=None: CLOCK)
    assert calls["n"] == 1
    with pytest.raises(P.ProbeClosed, match="HTML"):
        P.parse_export_body(b"<!DOCTYPE html><html>calendar</html>")
    with pytest.raises(P.ProbeClosed, match="malformed"):
        P.parse_export_body(b"not-json")


def test_schema_inspected_not_assumed_and_blank_forecast_stays_blank():
    rows = _rows()
    fields = P.returned_field_names(rows)
    assert "title" in fields
    assert "forecast" in fields
    assert "previous" in fields
    renamed = [{**rows[0], "EventName": rows[0]["title"]}]
    renamed[0].pop("title")
    assert "title" not in P.returned_field_names(renamed)
    assert "EventName" in P.returned_field_names(renamed)
    found = P.inspect_employment_rows(rows)
    nfp = found["nonfarm_payroll_change"]
    assert nfp["returned_event_name"] == "Non-Farm Employment Change"
    assert nfp["forecast"] == "51K"
    assert nfp["previous"] == "22K"
    assert nfp["forecast"] != nfp["previous"]
    assert nfp["forecast_replaced_with_previous"] is False
    assert nfp["forecast_fabricated"] is False
    ahey = found["average_hourly_earnings_yoy"]
    assert ahey["forecast"] == ""
    assert ahey["forecast_display"] == "BLANK"
    assert ahey["previous"] == "3.7%"
    assert ahey["forecast"] != ahey["previous"]
    missing = dict(rows[0])
    missing.pop("forecast")
    blanked = P.inspect_employment_rows([missing])
    assert blanked["nonfarm_payroll_change"]["forecast"] is None
    assert blanked["nonfarm_payroll_change"]["previous"] == "22K"
    assert blanked["nonfarm_payroll_change"]["forecast_replaced_with_previous"] is False


def test_event_matching_fails_closed_and_timezone_not_converted():
    rows = _rows()
    found = P.inspect_employment_rows(rows)
    assert "adp" not in found
    assert found["nonfarm_payroll_change"]["country_currency"] == "USD"
    gbp_only = [row for row in rows if row.get("country") == "GBP"]
    assert P.inspect_employment_rows(gbp_only) == {}
    adp_only = [row for row in rows if "ADP" in row["title"]]
    assert P.inspect_employment_rows(adp_only) == {}
    assert P.map_employment_title("ADP Non-Farm Employment Change") is None
    assert P.map_employment_title("Unemployment Claims") is None
    semantics = P.classify_timezone(rows)
    assert semantics == "UNSPECIFIED_OR_USER_LOCALIZED"
    with pytest.raises(P.ProbeClosed, match="TIMEZONE_AMBIGUOUS"):
        P.refuse_silent_utc_conversion(semantics, rows[0]["time"])


def test_observed_at_local_and_probe_cannot_create_checkpoint(tmp_path):
    obs = REAL_ROOT / "observations" / "observations.jsonl"
    before = obs.read_text(encoding="utf-8") if obs.exists() else ""
    task_before = (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8")
    cfg_before = (REAL_ROOT / "config.json").read_text(encoding="utf-8")
    reg_before = (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8")

    def transport(url, headers):
        return 200, _payload(), {"Content-Type": "application/json"}

    out = P.run_probe(dest=tmp_path, transport=transport, live=True, clock=lambda tz=None: CLOCK)
    assert out["observed_at_utc"] == "2026-09-29T21:00:00Z"
    assert out["observed_at_clock_role"] == "LOCAL_COLLECTION_TIME_ONLY"
    assert out["real_checkpoint_created"] is False
    assert out["entered_observations"] is False
    assert out["employment"]["nonfarm_payroll_change"]["date"] != out["observed_at_utc"]
    after = obs.read_text(encoding="utf-8") if obs.exists() else ""
    assert before == after
    rec = R.bootstrap_store(tmp_path / "rec", clock=lambda: CLOCK)
    rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-02T12:30:00Z",
        official_source="BLS",
    )
    with pytest.raises(R.RecorderClosed, match="OPERATOR_BACKDATE_FORBIDDEN"):
        rec.operator_ingest(
            macro_event_id="usd_empsit_2026-10-02",
            source_id="manual_operator",
            series_name="nonfarm_payroll_change",
            expectation_type="SURVEY_CONSENSUS",
            artifact_bytes=b"x",
            observed_at_utc="2026-09-01T00:00:00Z",
            forecast_value=1,
            unit="persons",
        )
    P.assert_scheduler_and_sources_unchanged()
    cfg = json.loads((REAL_ROOT / "config.json").read_text(encoding="utf-8"))
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    sources = json.loads((REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8"))["sources"]
    te = next(s for s in sources if s["source_id"] == "trading_economics")
    assert te["enabled"] is False
    assert te["automation_class"] != "APPROVED_AUTOMATION_READY"
    assert "forex_factory" not in [s["source_id"] for s in sources]
    assert (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8") == task_before
    assert (REAL_ROOT / "config.json").read_text(encoding="utf-8") == cfg_before
    assert (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8") == reg_before
    for path in PROD_IMPORT_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "_macro_forex_factory_probe_stage7a" not in text
        assert "nfs.faireconomy.media" not in text
    probe_src = Path("reports/decision_quality/_macro_forex_factory_probe_stage7a.py").read_text(encoding="utf-8").lower()
    assert "oanda" not in probe_src
    assert "selenium" not in probe_src
    assert "playwright" not in probe_src
