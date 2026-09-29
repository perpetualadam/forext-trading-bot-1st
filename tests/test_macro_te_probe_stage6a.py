"""Stage 6A TE calendar probe tests. No live Trading Economics requests."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_PPATH = Path("reports/decision_quality/_macro_te_probe_stage6a.py")
_PSPEC = importlib.util.spec_from_file_location("macro_te_probe_stage6a", _PPATH)
P = importlib.util.module_from_spec(_PSPEC)
_PSPEC.loader.exec_module(P)

_APATH = Path("reports/decision_quality/_macro_prospective_adapters.py")
_ASPEC = importlib.util.spec_from_file_location("macro_prospective_adapters", _APATH)
A = importlib.util.module_from_spec(_ASPEC)
_ASPEC.loader.exec_module(A)

_RPATH = Path("reports/decision_quality/_macro_prospective_recorder.py")
_RSPEC = importlib.util.spec_from_file_location("macro_prospective_recorder", _RPATH)
R = importlib.util.module_from_spec(_RSPEC)
_RSPEC.loader.exec_module(R)

UTC = timezone.utc
FIXTURE = Path("tests/fixtures/te_calendar_2026-10-02.sanitized.json")
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
SECRET = "SUPER_SECRET_TE_KEY_DO_NOT_LEAK"


class _Resp:
    def __init__(self, status, body, headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {}


def test_credentials_never_logged_and_absent_from_sanitized_artifact(tmp_path, capsys):
    body = FIXTURE.read_bytes()
    rows = json.loads(body)["rows"]
    payload = json.dumps(rows).encode("utf-8")

    def transport(url, headers):
        assert SECRET in headers.get("Authorization", "")
        return 200, payload, {"Content-Type": "application/json"}

    out = P.run_probe(
        dest=tmp_path,
        env={P.TE_KEY_ENV: SECRET},
        transport=transport,
        live=True,
    )
    captured = capsys.readouterr()
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    assert SECRET not in json.dumps(out)
    artifact = (tmp_path / "te_calendar_2026-10-02.sanitized.json").read_text(encoding="utf-8")
    assert SECRET not in artifact
    assert out["credential_in_artifact"] is False
    assert out["request_count"] == 1


def test_probe_cannot_enter_real_observation_store(tmp_path):
    before = REAL_ROOT.joinpath("observations", "observations.jsonl").read_text(encoding="utf-8") if REAL_ROOT.joinpath("observations", "observations.jsonl").exists() else ""
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
    P.run_probe(
        dest=tmp_path,
        env={P.TE_KEY_ENV: "x"},
        transport=lambda url, headers: (200, json.dumps(rows).encode(), {}),
        live=True,
    )
    after = REAL_ROOT.joinpath("observations", "observations.jsonl").read_text(encoding="utf-8") if REAL_ROOT.joinpath("observations", "observations.jsonl").exists() else ""
    assert before == after
    assert not (tmp_path / "observations" / "observations.jsonl").exists()


def test_exact_series_and_consensus_te_kept_separate():
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
    found = P.inspect_employment_rows(rows)
    assert found["nonfarm_payroll_change"]["event_name"] == "Non Farm Payrolls"
    assert found["unemployment_rate"]["event_name"] == "Unemployment Rate"
    assert found["average_hourly_earnings_mom"]["event_name"] == "Average Hourly Earnings MoM"
    assert found["average_hourly_earnings_yoy"]["event_name"] == "Average Hourly Earnings YoY"
    assert found["nonfarm_payroll_change"]["forecast"] != found["nonfarm_payroll_change"]["te_forecast"]
    assert "adp" not in found
    assert A.map_employment_series("ADP Employment Change") is None
    assert P.consensus_and_te_distinct(rows[0]) is True


def test_malformed_fails_closed_and_request_guard_rejects_second(tmp_path):
    with pytest.raises(P.ProbeClosed, match="malformed"):
        P.parse_calendar_body(b"not-json")
    guard = P.RequestGuard(1)
    guard.authorize()
    with pytest.raises(RuntimeError, match="request #2 rejected"):
        guard.authorize()
    calls = {"n": 0}

    def transport(url, headers):
        calls["n"] += 1
        return 200, b"[]", {}

    g = P.RequestGuard(1)
    P.run_probe(dest=tmp_path / "a", env={P.TE_KEY_ENV: "x"}, transport=transport, live=True, guard=g)
    with pytest.raises(RuntimeError, match="request #2 rejected"):
        P.run_probe(dest=tmp_path / "b", env={P.TE_KEY_ENV: "x"}, transport=transport, live=True, guard=g)
    assert calls["n"] == 1


def test_observed_at_cannot_be_backdated_and_scheduler_remains_disabled(tmp_path):
    rec = R.bootstrap_store(tmp_path, clock=lambda: datetime(2026, 9, 29, 4, 0, tzinfo=UTC))
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
    cfg = json.loads((REAL_ROOT / "config.json").read_text(encoding="utf-8"))
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    P.assert_scheduler_still_disabled()
    src = json.loads((REAL_ROOT / "source_registry" / "sources.json").read_text(encoding="utf-8"))
    te = next(s for s in src["sources"] if s["source_id"] == "trading_economics")
    assert te["enabled"] is False
    assert te["automation_class"] != "APPROVED_AUTOMATION_READY"
    assert te.get("automated_collection_permitted") is not True
