"""Stage 4 prospective source adapters. Research-only. No OANDA / trading."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

import pytest

_RPATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_RSPEC = importlib.util.spec_from_file_location("macro_prospective_recorder", _RPATH)
R = importlib.util.module_from_spec(_RSPEC)
_RSPEC.loader.exec_module(R)

_SPATH = Path("reports/decision_quality/_macro_prospective_scheduler.py")
_SSPEC = importlib.util.spec_from_file_location("macro_prospective_scheduler", _SPATH)
S = importlib.util.module_from_spec(_SSPEC)
_SSPEC.loader.exec_module(S)

_APATH = Path("reports/decision_quality/_macro_prospective_adapters.py")
_ASPEC = importlib.util.spec_from_file_location("macro_prospective_adapters", _APATH)
A = importlib.util.module_from_spec(_ASPEC)
_ASPEC.loader.exec_module(A)

UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")


class _Clock:
    def __init__(self, dt):
        self.dt = dt

    def __call__(self):
        return self.dt


class _Resp:
    def __init__(self, status, body):
        self.status = status
        self.body = body


class _FakeProvider(S.CollectionAdapter):
    def __init__(self, source_id, value, artifact, series="nonfarm_payroll_change"):
        self.source_id = source_id
        self.value = value
        self.artifact = artifact
        self.series = series
        self.collect_calls = 0

    def is_enabled(self, rec):
        return True, "OK"

    def collect(self, event, checkpoint, now):
        self.collect_calls += 1
        return S.CollectionResult(
            status="SUCCESS",
            source_id=self.source_id,
            external_request=False,
            artifact_bytes=self.artifact,
            series_name=self.series,
            expectation_type="SURVEY_CONSENSUS",
            forecast_value=self.value,
            unit="persons",
        )


def _rec(tmp_path, now):
    return R.bootstrap_store(tmp_path, clock=_Clock(now))


def _empsit(rec, t0="2026-10-02T12:30:00Z"):
    return rec.register_event(
        macro_event_id="usd_empsit_2026-10-02",
        event_family="EMPLOYMENT_SITUATION",
        event_name="The Employment Situation",
        reference_period="2026-09",
        scheduled_release_utc=t0,
        official_source="BLS",
    )


def _approve_te(rec):
    rec.config_path.write_text(json.dumps({R.FORWARD_FLAG: True}, indent=2) + "\n", encoding="utf-8")
    blob = rec.load_registry()
    for src in blob["sources"]:
        if src.get("source_id") == "trading_economics":
            src["enabled"] = True
            src["automated_collection_permitted"] = True
            src["archival_permitted"] = True
            src["automation_class"] = "APPROVED_AUTOMATION_READY"
    rec.registry_path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")


def test_unknown_disabled_unclear_missing_creds_make_zero_requests(tmp_path):
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    _empsit(rec)
    unknown = A.NeverFetchAdapter("not_in_registry")
    te = A.TradingEconomicsAdapter(env={}, transport=lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    assert unknown.is_enabled(rec)[0] is False
    assert te.network_calls == 0
    _approve_te(rec)
    assert te.is_enabled(rec) == (False, "MISSING_CREDENTIALS")
    reuters = rec.source_by_id("reuters")
    assert reuters["enabled"] is False
    assert reuters["automated_collection_permitted"] != True
    summary = S.ProspectiveScheduler(rec, adapters=[te]).collect_due()
    assert summary["external_requests"] == 0
    assert rec.load_observations() == []


def test_credentials_never_appear_in_logs(tmp_path):
    secret = "SUPER_SECRET_TE_KEY_DO_NOT_LEAK"
    assert A.redact("Authorization: %s" % secret, secret) == "Authorization: <redacted>"
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    _empsit(rec)
    _approve_te(rec)
    te = A._ApprovedTeTestAdapter(
        env={A.TE_KEY_ENV: secret},
        transport=lambda url, headers: _Resp(200, json.dumps([{"Event": "Non Farm Payrolls", "Forecast": "80k", "CalendarId": "1"}]).encode()),
    )
    S.ProspectiveScheduler(rec, adapters=[te]).collect_due()
    audit = (tmp_path / "scheduler" / "audit.jsonl").read_text(encoding="utf-8")
    assert secret not in audit
    for o in rec.load_observations():
        assert secret not in json.dumps(o)


def test_successful_te_mock_preserves_provenance_and_observed_at(tmp_path):
    now = datetime(2026, 9, 30, 12, 34, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    _empsit(rec)
    _approve_te(rec)
    body = json.dumps(
        [
            {"Event": "Non Farm Payrolls", "Forecast": "175k", "CalendarId": "nfp1", "reference_period": "2026-09"},
            {"Event": "Unemployment Rate", "Forecast": "4.2", "CalendarId": "ur1", "reference_period": "2026-09"},
            {"Event": "Average Hourly Earnings MoM", "Forecast": "0.3", "CalendarId": "ahem", "reference_period": "2026-09"},
            {"Event": "Average Hourly Earnings YoY", "Forecast": "3.7", "CalendarId": "ahey", "reference_period": "2026-09"},
        ]
    ).encode()
    te = A._ApprovedTeTestAdapter(env={A.TE_KEY_ENV: "x"}, transport=lambda url, headers: _Resp(200, body))
    S.ProspectiveScheduler(rec, adapters=[te]).collect_due()
    rows = rec.load_observations()
    series = {o["series_name"]: o for o in rows}
    assert series["nonfarm_payroll_change"]["forecast_value"] == 175000
    assert series["unemployment_rate"]["forecast_value"] == 4.2
    assert series["average_hourly_earnings_mom"]["forecast_value"] == 0.3
    assert series["average_hourly_earnings_yoy"]["forecast_value"] == 3.7
    assert series["nonfarm_payroll_change"]["unit"] == "persons"
    assert all(o["observed_at_utc"] == "2026-09-30T12:34:00Z" for o in rows)
    assert all(o["observed_at_utc"] != o["checkpoint_utc"] for o in rows)
    assert all(o["raw_artifact_hash"] == R.sha256_bytes(body) for o in rows)
    assert all(o.get("raw_artifact_sha256") == o["raw_artifact_hash"] for o in rows)
    assert all(o.get("raw_artifact_path") for o in rows)
    assert all(o["observed_at_utc"] == o.get("retrieval_utc") for o in rows)
    assert rows[0]["calendar_fields"]["provider"] == "Trading Economics"


def test_post_t0_forecast_rejected_and_backdate_impossible(tmp_path):
    now = datetime(2026, 10, 2, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    ev = _empsit(rec)
    fake = _FakeProvider("fixture_provider_a", 160000, b"late")
    rec.config_path.write_text(json.dumps({R.FORWARD_FLAG: True}), encoding="utf-8")
    sched = S.ProspectiveScheduler(rec, adapters=[fake])
    summary = {"ok": True, "actions": [], "external_requests": 0}
    due_row = {
        "checkpoint_id": "T0-5m",
        "checkpoint_utc": "2026-10-02T12:25:00Z",
        "status": "DUE",
        "next_boundary_utc": "2026-10-02T12:30:00Z",
    }
    sched._handle_checkpoint(ev, due_row, now, {"processed": {}}, summary, persist=False, dry_run=False)
    assert rec.load_observations() == []
    assert any(
        r.get("status") == "POST_T0_REJECTED"
        for a in summary["actions"]
        for r in a.get("adapter_results") or []
    )
    after = sched.collect_due()
    assert rec.load_observations() == []
    assert after["external_requests"] == 0
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


def test_cpi_four_components_and_fomc_distribution(tmp_path):
    now = datetime(2026, 10, 12, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    rec.register_event(
        macro_event_id="usd_cpi_2026-10-14",
        event_family="CPI",
        event_name="Consumer Price Index",
        reference_period="2026-09",
        scheduled_release_utc="2026-10-14T12:30:00Z",
        official_source="BLS",
    )
    _approve_te(rec)
    body = json.dumps(
        [
            {"Event": "CPI headline MoM", "Forecast": "0.2"},
            {"Event": "CPI headline YoY", "Forecast": "2.9"},
            {"Event": "CPI core MoM", "Forecast": "0.2"},
            {"Event": "CPI core YoY", "Forecast": "2.7"},
        ]
    ).encode()
    te = A._ApprovedTeTestAdapter(env={A.TE_KEY_ENV: "x"}, transport=lambda url, headers: _Resp(200, body))
    S.ProspectiveScheduler(rec, adapters=[te]).collect_due()
    names = {o["series_name"] for o in rec.load_observations()}
    assert names == set(A.CPI_SERIES)
    rec2 = _rec(tmp_path / "fomc", datetime(2026, 10, 26, 18, 1, tzinfo=UTC))
    rec2.register_event(
        macro_event_id="usd_fomc_statement_2026-10-28",
        event_family="FOMC",
        event_name="FOMC statement/decision",
        reference_period="2026-10-27/28",
        scheduled_release_utc="2026-10-28T18:00:00Z",
        official_source="Federal Reserve Board",
    )
    _approve_te(rec2)
    dist = {"hold": 0.4, "cut_25bp": 0.5, "cut_50bp": 0.1, "hike": 0.0}
    te2 = A._ApprovedTeTestAdapter(
        env={A.TE_KEY_ENV: "x"},
        transport=lambda url, headers: _Resp(200, json.dumps([{"Event": "FOMC", "fomc_distribution": dist}]).encode()),
    )
    S.ProspectiveScheduler(rec2, adapters=[te2]).collect_due()
    fomc_obs = rec2.load_observations()
    assert fomc_obs[0]["fomc_distribution"] == dist
    with pytest.raises(RuntimeError, match="must not be collapsed"):
        A.refuse_fomc_collapse(0.5, "cut")


def test_multiple_providers_vintages_and_hash_reuse(tmp_path):
    t0 = "2026-10-02T12:30:00Z"
    rec = _rec(tmp_path, datetime(2026, 9, 30, 12, 31, tzinfo=UTC))
    _empsit(rec, t0)
    rec.config_path.write_text(json.dumps({R.FORWARD_FLAG: True}), encoding="utf-8")
    blob = rec.load_registry()
    for src in blob["sources"]:
        if src.get("source_id") in {"fixture_provider_a", "fixture_provider_b"}:
            src["enabled"] = True
            src["automated_collection_permitted"] = True
    rec.registry_path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
    a = _FakeProvider("fixture_provider_a", 175000, b"A175")
    b = _FakeProvider("fixture_provider_b", 165000, b"B165")
    S.ProspectiveScheduler(rec, adapters=[a, b]).collect_due()
    rec.clock = _Clock(datetime(2026, 10, 2, 6, 31, tzinfo=UTC))
    a2 = _FakeProvider("fixture_provider_a", 160000, b"A160")
    b_same = _FakeProvider("fixture_provider_b", 165000, b"B165")
    S.ProspectiveScheduler(rec, adapters=[a2, b_same]).collect_due()
    rows = rec.load_observations()
    a_vals = [o["forecast_value"] for o in rows if o["source_id"] == "fixture_provider_a"]
    b_hashes = [o["raw_artifact_hash"] for o in rows if o["source_id"] == "fixture_provider_b"]
    assert 175000 in a_vals and 160000 in a_vals
    assert b_hashes[0] == b_hashes[1]
    assert {o["source_id"] for o in rows} == {"fixture_provider_a", "fixture_provider_b"}


def test_ambiguous_unit_series_malformed_network_rate_limit_write_nothing(tmp_path):
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    _empsit(rec)
    _approve_te(rec)
    with pytest.raises(ValueError):
        A.normalize_jobs_value("about 80-90k")
    assert A.map_employment_series("ADP Employment") is None
    cases = [
        ("PARSE_FAILED", lambda url, headers: _Resp(200, b"not-json")),
        ("SOURCE_UNAVAILABLE", lambda url, headers: (_ for _ in ()).throw(URLError("dns"))),
        ("RATE_LIMITED", lambda url, headers: _Resp(429, b"")),
        ("INVALID_SERIES", lambda url, headers: _Resp(200, json.dumps([{"Event": "ADP Employment", "Forecast": "100k"}]).encode())),
    ]
    for status, transport in cases:
        rec2 = _rec(tmp_path / status, now)
        _empsit(rec2)
        _approve_te(rec2)
        te = A._ApprovedTeTestAdapter(env={A.TE_KEY_ENV: "x"}, transport=transport)
        S.ProspectiveScheduler(rec2, adapters=[te]).collect_due()
        assert rec2.load_observations() == []


def test_official_bls_disabled_and_never_before_t0(tmp_path):
    now = datetime(2026, 9, 30, 12, 31, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    ev = _empsit(rec)
    ad = A.OfficialBlsFirstPrintAdapter(transport=lambda url, headers: (_ for _ in ()).throw(AssertionError("network")))
    assert ad.is_enabled(rec)[1] == "SOURCE_DISABLED"
    out = ad.collect(ev, {"checkpoint_id": "T0-48h"}, now)
    assert out.status == "ACCESS_DENIED"
    assert out.reason == "NEVER_BEFORE_T0"
    assert ad.network_calls == 0
    later = datetime(2026, 10, 2, 12, 31, tzinfo=UTC)
    ad2 = A.OfficialBlsFirstPrintAdapter(transport=lambda url, headers: _Resp(200, b"FIRST_PRINT_NFP=110000"))
    blob = rec.load_registry()
    for src in blob["sources"]:
        if src["source_id"] == "bls_official":
            src["enabled"] = True
            src["automated_collection_permitted"] = True
    rec.registry_path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
    rec.config_path.write_text(json.dumps({R.FORWARD_FLAG: True}), encoding="utf-8")
    ok = ad2.collect(ev, {"checkpoint_id": "T0"}, later)
    assert ok.status == "SUCCESS"
    assert ok.forecast_value == 110000


def test_probe_and_prewindow_do_not_enter_real_or_tmp_observations(tmp_path):
    probe = A.run_capability_probes(dest=tmp_path / "probes", env={}, live=False)
    assert probe["total_external_requests"] == 0
    assert probe["entered_observations"] is False
    now = datetime(2026, 9, 28, 21, 30, tzinfo=UTC)
    rec = _rec(tmp_path, now)
    R.register_official_upcoming(rec, now)
    te = A.TradingEconomicsAdapter(env={A.TE_KEY_ENV: "x"}, transport=lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    S.ProspectiveScheduler(rec, adapters=[te]).collect_due()
    assert rec.load_observations() == []
    assert te.network_calls == 0


def test_real_registry_and_observations_unchanged_no_trading_imports():
    obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8") if (REAL_ROOT / "observations" / "observations.jsonl").exists() else ""
    rows = [json.loads(ln) for ln in obs.splitlines() if ln.strip()]
    assert {r["associated_checkpoint_id"] for r in rows} <= {"T0-48h", "T0-24h", "T0-12h", "T0-1h", "T0-30m", "T0-15m"}
    for row in rows:
        assert row["macro_event_id"] == "usd_empsit_2026-10-02"
        assert row["expectation_type"] == "SURVEY_CONSENSUS"
        assert row["retrieval_method"] == "manual"
        assert row["pre_release"] is True
        assert "DRY-RUN FIXTURE" not in (row.get("notes") or "")
    assert not any(r.get("associated_checkpoint_id") == "T0-36h" for r in rows)
    events = json.loads((REAL_ROOT / "events" / "events.json").read_text(encoding="utf-8"))
    assert [e["macro_event_id"] for e in events] == [
        "usd_empsit_2026-10-02",
        "usd_cpi_2026-10-14",
        "usd_fomc_statement_2026-10-28",
    ]
    cfg = json.loads((REAL_ROOT / "config.json").read_text(encoding="utf-8"))
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    src = Path("reports/decision_quality/_macro_prospective_adapters.py").read_text(encoding="utf-8")
    for name in S.FORBIDDEN_PRODUCTION_IMPORTS:
        assert ("import %s" % name) not in src
        assert ("from %s" % name) not in src
    assert "oanda_exec" not in src
    assert "OrderCreate" not in src
    loop = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert "_macro_prospective_adapters" not in loop
    for row in A.SOURCE_AUDIT:
        assert "credentials_present" in row
        if row["source_id"] == "trading_economics":
            assert row["classification"] == "API_AVAILABLE_CREDENTIALS_MISSING"
            assert row["credentials_present"] is False
