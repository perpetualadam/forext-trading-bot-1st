"""Consensus PIT pilot helpers. No bot_loop. No us_pit writes."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_PATH = Path("reports/decision_quality/_macro_consensus_pit_pilot.py")
_SPEC = importlib.util.spec_from_file_location("macro_consensus_pit_pilot", _PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)

SELECTED_IDS = _MOD.SELECTED_IDS
parse_utc = _MOD.parse_utc
US_PIT_DIR = _MOD.US_PIT_DIR
SELECTION_PATH = _MOD.SELECTION_PATH


def test_selection_frozen_calendar_rule():
    sel = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    assert sel["fx_outcomes_used"] is False
    ids = [e["macro_event_id"] for e in sel["selected"]]
    assert ids == SELECTED_IDS
    assert ids[:3] == ["usd_cpi_2025-09-11", "usd_cpi_2026-02-13", "usd_cpi_2026-07-14"]
    assert "EMPLOYMENT_SITUATION" in {e["event_family"] for e in sel["selected"]}
    assert "FOMC" in {e["event_family"] for e in sel["selected"]}


def test_pit_safe_requires_publication_before_t0():
    records = json.loads(_MOD.EVIDENCE_PATH.read_text(encoding="utf-8"))
    for rec in records:
        if rec["pit_status"] != "PIT_SAFE":
            continue
        pub = parse_utc(rec["source_publication_utc"])
        t0 = parse_utc(rec["official_release_utc"])
        assert pub is not None
        assert t0 is not None
        assert pub < t0, rec["consensus_evidence_id"]


def test_individual_forecast_not_relabeled_consensus():
    records = json.loads(_MOD.EVIDENCE_PATH.read_text(encoding="utf-8"))
    individuals = [r for r in records if r["expectation_type"] == "INDIVIDUAL_FORECAST"]
    assert individuals
    assert all("CONSENSUS" not in r["expectation_type"] for r in individuals)


def test_sources_not_averaged():
    records = json.loads(_MOD.EVIDENCE_PATH.read_text(encoding="utf-8"))
    nfp = [
        r["forecast_value"]
        for r in records
        if r["macro_event_id"] == "usd_empsit_2026-08-07" and r["series_name"] == "nonfarm_payroll_change" and r["expectation_type"] != "INDIVIDUAL_FORECAST"
    ]
    assert 80000 in nfp
    assert 83000 in nfp
    assert 97500 in nfp
    assert sum(nfp) / len(nfp) not in nfp


def test_surprise_only_pit_safe():
    blob = json.loads(_MOD.SURPRISE_PATH.read_text(encoding="utf-8"))
    records = json.loads(_MOD.EVIDENCE_PATH.read_text(encoding="utf-8"))
    safe_ids = {r["consensus_evidence_id"] for r in records if r["pit_status"] == "PIT_SAFE"}
    for s in blob["surprise"]:
        assert s["consensus_evidence_id"] in safe_ids


def test_us_pit_not_the_write_target():
    assert US_PIT_DIR.exists()
    assert _MOD.PILOT_DIR.exists()
    assert _MOD.PILOT_DIR.resolve() != US_PIT_DIR.resolve()
    assert "consensus_pit" in str(_MOD.PILOT_DIR).replace("\\", "/")
    assert _MOD.PILOT_DIR.resolve() != (US_PIT_DIR / "events").resolve()


def test_fomc_probability_not_collapsed_to_minus_25():
    records = json.loads(_MOD.EVIDENCE_PATH.read_text(encoding="utf-8"))
    implied = [r for r in records if r["expectation_type"] == "MARKET_IMPLIED_EXPECTATION"]
    assert implied
    assert all(r["unit"] == "probability" for r in implied)
    assert all(r.get("forecast_value") not in (-25, 25) for r in implied)
