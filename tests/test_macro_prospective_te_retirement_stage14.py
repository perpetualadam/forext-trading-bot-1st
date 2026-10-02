"""Stage 14 TE operational retirement tests. Temporary dirs only. Zero network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_IPATH = Path("reports/decision_quality/_macro_prospective_te_retirement_stage14.py")
_ISPEC = importlib.util.spec_from_file_location("macro_stage14", _IPATH)
S14 = importlib.util.module_from_spec(_ISPEC)
_ISPEC.loader.exec_module(S14)

_S13PATH = Path("reports/decision_quality/_macro_prospective_evidence_intake_stage13.py")
_S13SPEC = importlib.util.spec_from_file_location("macro_stage13_from14", _S13PATH)
S13 = importlib.util.module_from_spec(_S13SPEC)
_S13SPEC.loader.exec_module(S13)

R = S14.R
A = S14.A
_SSPEC = importlib.util.spec_from_file_location(
    "macro_sched_stage14", Path("reports/decision_quality/_macro_prospective_scheduler.py")
)
S = importlib.util.module_from_spec(_SSPEC)
_SSPEC.loader.exec_module(S)

UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
CPI = "usd_cpi_2026-10-14"
EMP = "usd_empsit_2026-10-02"
FOMC = "usd_fomc_statement_2026-10-28"
CLOCK_OPEN = datetime(2026, 10, 12, 12, 40, tzinfo=UTC)
CREATED_T48 = datetime(2026, 10, 12, 12, 31, tzinfo=UTC)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rec(tmp_path: Path, clock=CLOCK_OPEN):
    rec = R.bootstrap_store(tmp_path, clock=lambda: clock)
    R.register_official_upcoming(rec, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    S14.apply_operational_overlay(rec)
    return rec


def _times(created=CREATED_T48, modified=None):
    modified = modified or created
    def _fn(_path):
        return created, modified
    return _fn


def test_historical_te_observations_and_evidence_unchanged():
    obs = REAL_ROOT / "observations" / "observations.jsonl"
    rows = [json.loads(line) for line in obs.read_text(encoding="utf-8").splitlines() if line.strip()]
    emp = [r for r in rows if r.get("macro_event_id") == EMP]
    assert emp
    assert all(r.get("source_id") == "trading_economics" for r in emp)
    assert not any(r.get("macro_event_id") == CPI for r in rows)
    assert not any(r.get("macro_event_id") == FOMC for r in rows)
    meta = REAL_ROOT / "evidence" / "stage11_evidence.meta.json"
    assert meta.exists()
    blob = json.loads(meta.read_text(encoding="utf-8"))
    assert "trading_economics" in json.dumps(blob)
    assert _sha(obs) == hashlib.sha256(obs.read_bytes()).hexdigest()


def test_te_adapter_disabled_but_code_preserved():
    rec = R.ProspectiveRecorder(REAL_ROOT)
    src = rec.source_by_id("trading_economics")
    assert src is not None
    assert src.get("enabled") is False
    assert src.get("currently_live") is False
    assert src.get("approved_consensus_provider") is False
    assert src.get("operational_status") == "OPERATIONAL_RETIRED_SUBSCRIPTION_CANCELLED"
    assert src.get("automation_class") != "APPROVED_AUTOMATION_READY"
    ad = A.TradingEconomicsAdapter(env={})
    assert ad.currently_live() is False
    ok, reason = ad.is_enabled(rec)
    assert ok is False
    assert reason != "OK"
    assert Path("forex_bot/decision_quality/trading_economics/client.py").exists()
    assert Path("forex_bot/decision_quality/trading_economics/schema.py").exists()
    assert Path("tests/test_trading_economics_pretrial.py").exists()
    assert Path("reports/decision_quality/_macro_te_probe_stage6a.py").exists()
    te_audit = next(row for row in A.SOURCE_AUDIT if row["source_id"] == "trading_economics")
    assert te_audit["currently_live"] is False
    assert te_audit["classification"] == "API_AVAILABLE_CREDENTIALS_MISSING"


def test_cpi_is_provider_pending_no_te_assumption():
    rec = R.ProspectiveRecorder(REAL_ROOT)
    event = rec.event_by_id(CPI)
    assert event is not None
    status = S14.event_provider_status(event)
    assert status["registration"] == "ACTIVE"
    assert status["checkpoint_schedule"] == "ACTIVE"
    assert status["consensus_provider"] == "NONE_APPROVED"
    assert status["consensus_provider_id"] is None
    assert status["provider_status"] == "PROVIDER_PENDING"
    assert status["automated_collection"] == "DISABLED"
    assert status["manual_collection"] == "WAITING_FOR_APPROVED_PROVIDER"
    assert status["approved_consensus_provider_available"] is False
    assert event.get("consensus_provider_id") is None
    runbook = Path("reports/decision_quality/macro_prospective_cpi_evidence_runbook.md").read_text(encoding="utf-8")
    assert "Refresh/view Trading Economics" not in runbook
    assert "PROVIDER_PENDING" in runbook
    assert "--provider-id <approved-provider>" in runbook
    assert list(R.CPI_SERIES) == ["headline_mom", "headline_yoy", "core_mom", "core_yoy"]


def test_no_provider_cannot_create_fake_observation_and_records_no_enabled_source(tmp_path):
    rec = _rec(tmp_path)
    te = A.TradingEconomicsAdapter(env={}, transport=lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    summary = S.ProspectiveScheduler(rec, adapters=[te]).collect_due()
    assert summary["external_requests"] == 0
    assert rec.load_observations() == []
    results = [a.get("result") for a in summary.get("actions") or []]
    assert "NO_ENABLED_SOURCE" in results
    assert all(a.get("observation") != "FAKE" for a in summary.get("actions") or [])
    with pytest.raises(S14.ProviderClosed, match="NO_ENABLED_SOURCE"):
        S14.refuse_fake_observation()
    with pytest.raises(S13.IntakeClosed, match="PROVIDER_ID_REQUIRED"):
        png = tmp_path / "cap.png"
        png.write_bytes(b"PNG14")
        secured = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times())
        S13.ingest_values(
            rec=rec,
            event_id=CPI,
            checkpoint="T0-48h",
            evidence_ref=secured["evidence_id"],
            displayed={"headline_mom": {"consensus_raw": "0.2"}},
        )
    assert rec.load_observations() == []


def test_te_and_bls_refused_as_future_consensus_providers(tmp_path):
    rec = _rec(tmp_path)
    png = tmp_path / "cap.png"
    png.write_bytes(b"PNG14B")
    secured = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times())
    displayed = {
        "headline_mom": {"consensus_raw": "0.2", "forecast_raw": "0.3", "previous_raw": "0.1"},
        "headline_yoy": {"consensus_raw": "3.1", "forecast_raw": "3.0", "previous_raw": "2.9"},
        "core_mom": {"consensus_raw": "0.2", "forecast_raw": "0.2", "previous_raw": "0.2"},
        "core_yoy": {"consensus_raw": "3.0", "forecast_raw": "3.1", "previous_raw": "3.0"},
    }
    with pytest.raises(S13.IntakeClosed, match="TRADING_ECONOMICS_OPERATIONAL_RETIRED"):
        S13.ingest_values(
            rec=rec,
            event_id=CPI,
            checkpoint="T0-48h",
            evidence_ref=secured["evidence_id"],
            displayed=displayed,
            provider_id="trading_economics",
        )
    with pytest.raises(S13.IntakeClosed, match="not a consensus provider"):
        S13.ingest_values(
            rec=rec,
            event_id=CPI,
            checkpoint="T0-48h",
            evidence_ref=secured["evidence_id"],
            displayed=displayed,
            provider_id="bls_official",
        )
    with pytest.raises(S13.IntakeClosed, match="NO_APPROVED_CONSENSUS_PROVIDER"):
        S13.ingest_values(
            rec=rec,
            event_id=CPI,
            checkpoint="T0-48h",
            evidence_ref=secured["evidence_id"],
            displayed=displayed,
            provider_id="reuters",
        )
    assert rec.load_observations() == []


def test_evidence_intake_remains_provider_neutral_and_requires_explicit_id(tmp_path):
    rec = _rec(tmp_path)
    png = tmp_path / "cap.png"
    png.write_bytes(b"PNG14C")
    out = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times())
    assert out["observation_eligible"] is True
    assert out.get("provider_id") in (None, "")
    src = Path("reports/decision_quality/_macro_prospective_evidence_intake_stage13.py").read_text(encoding="utf-8")
    assert 'source_id="trading_economics"' not in src
    assert 'provider_name="Trading Economics"' not in src
    displayed = {
        "headline_mom": {"consensus_raw": "0.2", "forecast_raw": "0.3", "previous_raw": "0.1"},
        "headline_yoy": {"consensus_raw": "3.1", "forecast_raw": "3.0", "previous_raw": "2.9"},
        "core_mom": {"consensus_raw": "0.2", "forecast_raw": "0.2", "previous_raw": "0.2"},
        "core_yoy": {"consensus_raw": "3.0", "forecast_raw": "3.1", "previous_raw": "3.0"},
    }
    ingested = S13.ingest_values(
        rec=rec,
        event_id=CPI,
        checkpoint="T0-48h",
        evidence_ref=out["evidence_id"],
        displayed=displayed,
        provider_id="fixture_provider_a",
    )
    assert ingested["provider_id"] == "fixture_provider_a"
    assert ingested["components"]["headline_mom"]["forecast_semantics"] == "PROVIDER_FORECAST_NOT_CONSENSUS"
    obs = rec.load_observations()
    assert len(obs) == 1
    assert obs[0]["source_id"] == "fixture_provider_a"
    assert obs[0]["source_id"] != "trading_economics"


def test_bls_not_classified_as_consensus_and_known_provider_status():
    bls = S14.classify_provider("bls_official")
    assert bls["role"] == S14.ROLE_OFFICIAL_ACTUAL
    assert bls["approved_consensus_provider"] is False
    te = S14.classify_provider("trading_economics")
    assert te["role"] == S14.ROLE_CONSENSUS
    assert te["currently_live"] is False
    assert te["approved_consensus_provider"] is False
    ff = S14.classify_provider("forex_factory")
    assert ff["registered"] is False
    assert ff["approved_consensus_provider"] is False
    assert S14.approved_consensus_provider_available() is False
    assert S14.te_currently_live() is False
    assert any("survey" in row.lower() or "Consensus" in row for row in S14.CONSENSUS_VS_FORECAST_RULES)
    assert any("headline_mom" in row for row in S14.PROVIDER_ACCEPTANCE_REQUIREMENTS)


def test_missed_checkpoint_stays_truthful(tmp_path):
    late = datetime(2026, 10, 13, 1, 0, tzinfo=UTC)
    rec = _rec(tmp_path, clock=late)
    rows = rec.checkpoint_status_rows(rec.event_by_id(CPI), late)
    t48 = next(r for r in rows if r["checkpoint_id"] == "T0-48h")
    assert t48["status"] == "MISSED_NOT_OBSERVED"
    assert rec.load_observations() == []


def test_production_archives_and_gates_untouched_by_temp_store(tmp_path):
    before_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_bytes()
    before_emp = next(e for e in json.loads((REAL_ROOT / "events" / "events.json").read_text(encoding="utf-8")) if e["macro_event_id"] == EMP)
    before_fomc = next(e for e in json.loads((REAL_ROOT / "events" / "events.json").read_text(encoding="utf-8")) if e["macro_event_id"] == FOMC)
    before_task = (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_bytes()
    before_actuals = (REAL_ROOT / "release_actuals" / "actuals.jsonl").read_bytes() if (REAL_ROOT / "release_actuals" / "actuals.jsonl").exists() else b""
    rec = _rec(tmp_path)
    png = tmp_path / "cap.png"
    png.write_bytes(b"PNG14D")
    S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times())
    after_events = json.loads((REAL_ROOT / "events" / "events.json").read_text(encoding="utf-8"))
    after_emp = next(e for e in after_events if e["macro_event_id"] == EMP)
    after_fomc = next(e for e in after_events if e["macro_event_id"] == FOMC)
    assert after_emp == before_emp
    assert after_fomc == before_fomc
    assert (REAL_ROOT / "observations" / "observations.jsonl").read_bytes() == before_obs
    assert (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_bytes() == before_task
    actuals_now = (REAL_ROOT / "release_actuals" / "actuals.jsonl").read_bytes() if (REAL_ROOT / "release_actuals" / "actuals.jsonl").exists() else b""
    assert actuals_now == before_actuals
    cfg = json.loads((REAL_ROOT / "config.json").read_text(encoding="utf-8"))
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    assert cfg["TRADING_ECONOMICS_ADAPTER_CURRENTLY_LIVE"] is False
    text = rec.format_status()
    assert "NEXT_EVENT_T48H_SCHEDULED_UTC:" in text
    assert "NEXT_EVENT_T48H_IS_OPEN:" in text
    assert "PROVIDER_STATUS:" in text
    ready = S14.readiness_check(rec, CPI)
    assert ready["t0_utc"] == "2026-10-14T12:30:00Z"
    assert ready["t48h_scheduled_utc"] == "2026-10-12T12:30:00Z"
    assert ready["t48h_is_open"] is True
    assert ready["http_requests"] == 0
    assert ready["trading_economics_currently_live"] is False


def test_no_network_or_production_logic_changes():
    stage14 = Path("reports/decision_quality/_macro_prospective_te_retirement_stage14.py").read_text(encoding="utf-8")
    low = stage14.lower()
    for forbidden in (
        "import requests",
        "urllib.request",
        "urllib.error",
        "oanda",
        "telegram",
        "playwright",
        "selenium",
    ):
        assert forbidden not in low
    assert "https://api.tradingeconomics.com" not in stage14
    assert "forexfactory.com" not in low
    assert "bls.gov" not in low
    task = json.loads((REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8-sig"))
    assert task["task_name"] == "ForexMacroProspectiveCollectDue"
    sched = Path("reports/decision_quality/_macro_prospective_scheduler.py").read_text(encoding="utf-8")
    assert "_macro_prospective_te_retirement_stage14" not in sched
    for path in (
        Path("forex_bot/bot_loop.py"),
        Path("forex_bot/ai_ensemble.py"),
        Path("forex_bot/rl_agent.py") if Path("forex_bot/rl_agent.py").exists() else Path("forex_bot/bot_loop.py"),
        Path("forex_bot/v2_shadow/observe.py"),
    ):
        assert "_macro_prospective_te_retirement_stage14" not in path.read_text(encoding="utf-8")
    live = R.ProspectiveRecorder(REAL_ROOT)
    assert S14.trading_economics_adapter_live(live) is False
    cpi_obs = [o for o in live.load_observations() if o.get("macro_event_id") == CPI]
    assert cpi_obs == []
