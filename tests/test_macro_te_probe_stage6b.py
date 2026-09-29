"""Stage 6B TE calendar probe tests. No live Trading Economics requests."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

_PPATH = Path("reports/decision_quality/_macro_te_probe_stage6b.py")
_PSPEC = importlib.util.spec_from_file_location("macro_te_probe_stage6b", _PPATH)
P = importlib.util.module_from_spec(_PSPEC)
_PSPEC.loader.exec_module(P)

_A6PATH = Path("reports/decision_quality/_macro_te_probe_stage6a.py")
_A6SPEC = importlib.util.spec_from_file_location("macro_te_probe_stage6a_for_6b", _A6PATH)
A6 = importlib.util.module_from_spec(_A6SPEC)
_A6SPEC.loader.exec_module(A6)

_APATH = Path("reports/decision_quality/_macro_prospective_adapters.py")
_ASPEC = importlib.util.spec_from_file_location("macro_prospective_adapters_6b", _APATH)
A = importlib.util.module_from_spec(_ASPEC)
_ASPEC.loader.exec_module(A)

_RPATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_RSPEC = importlib.util.spec_from_file_location("macro_prospective_recorder_6b", _RPATH)
R = importlib.util.module_from_spec(_RSPEC)
_RSPEC.loader.exec_module(R)

UTC = timezone.utc
FIXTURE = Path("tests/fixtures/te_calendar_2026-10-02_stage6b.sanitized.json")
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
SECRET = "SUPER_SECRET_TE_KEY_DO_NOT_LEAK_6B"
CLOCK = datetime(2026, 9, 29, 4, 15, tzinfo=UTC)


def _fixture_rows() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]


def _payload(rows: list[dict] | None = None) -> bytes:
    return json.dumps(rows if rows is not None else _fixture_rows()).encode("utf-8")


def test_credential_read_from_environment_and_never_logged(tmp_path, capsys):
    env_key = P.read_key(env={P.TE_KEY_ENV: "  %s  " % SECRET})
    assert env_key == SECRET
    assert P.credential_configured(env={P.TE_KEY_ENV: SECRET}) is True
    dotenv = tmp_path / ".env"
    dotenv.write_text("%s=%s\n" % (P.TE_KEY_ENV, SECRET), encoding="utf-8")
    assert P.read_key(env={}, dotenv_path=dotenv) == SECRET

    captured_urls = []

    def transport(url, headers):
        captured_urls.append(url)
        return 200, _payload(), {"Content-Type": "application/json"}

    out = P.run_probe(
        dest=tmp_path / "probe",
        env={P.TE_KEY_ENV: SECRET},
        transport=transport,
        live=True,
        clock=lambda tz=None: CLOCK,
    )
    printed = capsys.readouterr()
    blob = json.dumps(out)
    artifact = (tmp_path / "probe" / P.SANITIZED_NAME).read_text(encoding="utf-8")
    meta = (tmp_path / "probe" / P.META_NAME).read_text(encoding="utf-8")
    assert SECRET not in printed.out
    assert SECRET not in printed.err
    assert SECRET not in blob
    assert SECRET not in artifact
    assert SECRET not in meta
    assert out["credential_in_artifact"] is False
    assert P.credential_leak_scan([tmp_path / "probe" / P.SANITIZED_NAME, tmp_path / "probe" / P.META_NAME], SECRET) == []
    parsed = urlparse(captured_urls[0])
    assert parsed.scheme == "https"
    assert parsed.hostname == "api.tradingeconomics.com"
    assert parsed.path == "/calendar/country/All/2026-10-02/2026-10-02"
    qs = parse_qs(parsed.query)
    assert list(qs.keys()) == ["c", "f"]
    assert qs["c"] == [SECRET]
    assert qs["f"] == ["json"]


def test_documented_path_and_c_query_not_authorization_header(tmp_path):
    spec = P.public_request_spec()
    assert spec["host"] == "api.tradingeconomics.com"
    assert spec["path"] == "/calendar/country/All/2026-10-02/2026-10-02"
    assert spec["query_parameter_names"] == ["c", "f"]
    assert spec["authentication_placement"] == "c query parameter"
    assert spec["authorization_header"] is False
    assert spec["bearer"] is False
    assert spec["basic"] is False
    assert P.STAGE_6A_AUDIT["authentication_placement"] == "Authorization header"
    assert "c=" not in A6.DOCUMENTED_QUERY
    assert A6.DOCUMENTED_QUERY.startswith("f=json")
    assert "united%20states" in A6.DOCUMENTED_PATH
    seen = {"auth": None, "path": None}

    def transport(url, headers):
        seen["auth"] = headers
        seen["path"] = urlparse(url).path
        assert "Authorization" not in headers
        assert "Bearer" not in str(headers)
        return 200, b"[]", {}

    P.run_probe(dest=tmp_path, env={P.TE_KEY_ENV: SECRET}, transport=transport, live=True, clock=lambda tz=None: CLOCK)
    assert seen["path"] == "/calendar/country/All/2026-10-02/2026-10-02"
    assert seen["auth"] == {"Accept": "application/json"}


def test_forecast_teforecast_blank_and_clock_semantics(tmp_path):
    us_rows = P.filter_us_target_date(_fixture_rows())
    found = P.inspect_employment_rows(us_rows, "2026-09-29T04:15:00Z")
    nfp = found["nonfarm_payroll_change"]
    assert nfp["event_name"] == "Non Farm Payrolls"
    assert nfp["semantics"]["SURVEY_CONSENSUS"] == "51"
    assert nfp["semantics"]["PROVIDER_FORECAST"] == "48"
    assert nfp["semantics"]["SURVEY_CONSENSUS"] != nfp["semantics"]["PROVIDER_FORECAST"]
    assert nfp["semantics"]["SOURCE_UPDATED_UTC"] == "2026-09-20T11:00:00"
    assert nfp["semantics"]["OBSERVED_AT_UTC"] == "2026-09-29T04:15:00Z"
    assert nfp["semantics"]["last_update_is_not_observed_at"] is True
    assert nfp["semantics"]["teforecast_substituted_for_forecast"] is False
    ahey = found["average_hourly_earnings_yoy"]
    assert ahey["forecast"] == ""
    assert ahey["consensus_display"] == "BLANK"
    assert ahey["semantics"]["SURVEY_CONSENSUS"] == "SURVEY_CONSENSUS_CURRENTLY_BLANK"
    assert ahey["semantics"]["PROVIDER_FORECAST"] == "3.8"
    assert ahey["te_forecast"] != ahey["forecast"]
    assert found["unemployment_rate"]["event_name"] == "Unemployment Rate"
    assert found["average_hourly_earnings_mom"]["event_name"] == "Average Hourly Earnings MoM"
    assert "adp" not in found
    assert A.map_employment_series("ADP Employment Change") is None

    def transport(url, headers):
        return 200, _payload(), {}

    out = P.run_probe(
        dest=tmp_path,
        env={P.TE_KEY_ENV: SECRET},
        transport=transport,
        live=True,
        clock=lambda tz=None: CLOCK,
    )
    assert out["observed_at_utc"] == "2026-09-29T04:15:00Z"
    assert out["observed_at_clock_role"] == "LOCAL_COLLECTION_TIME_ONLY"
    assert out["forecast_field_semantics"] == "SURVEY_CONSENSUS"
    assert out["teforecast_field_semantics"] == "PROVIDER_FORECAST"
    assert out["lastupdate_semantics"] == "SOURCE_UPDATED_UTC"
    assert out["employment"]["nonfarm_payroll_change"]["semantics"]["SOURCE_UPDATED_UTC"] != out["observed_at_utc"]
    assert out["us_events_returned"] == 5


def test_missing_targets_fail_closed_and_no_guessing():
    rows = [
        {
            "CalendarId": "adp1",
            "Country": "United States",
            "Date": "2026-10-02T12:15:00",
            "Event": "ADP Employment Change",
            "Forecast": "40",
            "TEForecast": "42",
        },
        {
            "CalendarId": "uknfp",
            "Country": "United Kingdom",
            "Date": "2026-10-02T06:00:00",
            "Event": "Non Farm Payrolls",
            "Forecast": "1",
            "TEForecast": "2",
        },
    ]
    found = P.inspect_employment_rows(P.filter_us_target_date(rows), "2026-09-29T04:15:00Z")
    assert found == {}
    assert "nonfarm_payroll_change" not in found
    assert "unemployment_rate" not in found


def test_http_403_no_retry_and_request_guard(tmp_path):
    calls = {"n": 0}

    def transport(url, headers):
        calls["n"] += 1
        return 403, b'{"message":"Access denied"}', {}

    guard = P.RequestGuard(1)
    out = P.run_probe(
        dest=tmp_path / "a",
        env={P.TE_KEY_ENV: SECRET},
        transport=transport,
        live=True,
        guard=guard,
        clock=lambda tz=None: CLOCK,
    )
    assert out["http_status"] == 403
    assert out["result"] == "ACCESS_DENIED"
    assert out["authentication"] == "FAILED"
    assert out["request_count"] == 1
    with pytest.raises(RuntimeError, match="request #2 rejected"):
        P.run_probe(
            dest=tmp_path / "b",
            env={P.TE_KEY_ENV: SECRET},
            transport=transport,
            live=True,
            guard=guard,
            clock=lambda tz=None: CLOCK,
        )
    assert calls["n"] == 1
    with pytest.raises(P.ProbeClosed, match="malformed"):
        P.parse_calendar_body(b"not-json")


def test_prewindow_probe_cannot_become_checkpoint_and_production_disabled(tmp_path):
    before = ""
    obs = REAL_ROOT / "observations" / "observations.jsonl"
    if obs.exists():
        before = obs.read_text(encoding="utf-8")
    task_before = (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8")
    cfg_before = (REAL_ROOT / "config.json").read_text(encoding="utf-8")
    reg_before = (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8")

    def transport(url, headers):
        return 200, _payload(), {}

    out = P.run_probe(
        dest=tmp_path,
        env={P.TE_KEY_ENV: SECRET},
        transport=transport,
        live=True,
        clock=lambda tz=None: CLOCK,
    )
    assert out["real_checkpoint_created"] is False
    assert out["entered_observations"] is False
    after = obs.read_text(encoding="utf-8") if obs.exists() else ""
    assert before == after
    assert not (tmp_path / "observations" / "observations.jsonl").exists()
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
    P.assert_scheduler_still_disabled()
    cfg = json.loads((REAL_ROOT / "config.json").read_text(encoding="utf-8"))
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    te = next(s for s in json.loads((REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8"))["sources"] if s["source_id"] == "trading_economics")
    assert te["enabled"] is False
    assert te["automation_class"] != "APPROVED_AUTOMATION_READY"
    assert te.get("automated_collection_permitted") is not True
    assert (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8") == task_before
    assert (REAL_ROOT / "config.json").read_text(encoding="utf-8") == cfg_before
    assert (REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8") == reg_before
