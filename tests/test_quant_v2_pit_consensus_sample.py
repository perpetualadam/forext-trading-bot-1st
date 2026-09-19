"""Provenance tests for the Quant V2 PIT consensus sample audit.

No vendor consensus is loaded. Tests lock the frozen official-event sample,
forbid surprise/actual fields, and keep raw official files immutable.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from forex_bot.decision_quality.schedule import analysis_fields_clean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reports" / "decision_quality"))

from _quant_v2_pit_freeze_sample import select_frozen_sample  # noqa: E402

FROZEN = ROOT / "reports" / "decision_quality" / "quant_v2_pit_consensus_frozen_sample.json"
CATALOG = ROOT / "data" / "research" / "external" / "normalized" / "official_schedule_events_d1.json"
REPORT = ROOT / "reports" / "decision_quality" / "quant_v2_pit_consensus_sample_audit.md"
PROGRESS = ROOT / "reports" / "decision_quality" / "quant_v2_pit_consensus_progress.json"
VENDOR_DIRS = (
    ROOT / "data" / "research" / "external" / "raw" / "Econoday",
    ROOT / "data" / "research" / "external" / "raw" / "TradingEconomics",
    ROOT / "data" / "research" / "external" / "raw" / "Bloomberg",
)

FORBIDDEN_VALUE_KEYS = (
    "consensus",
    "forecast",
    "teforecast",
    "actual",
    "surprise",
    "previous",
    "revised",
    "pnl",
)

ALLOWED_EVENT_KEYS = {
    "sample_id",
    "event_id",
    "currency",
    "category",
    "source_agency",
    "source_event_name",
    "scheduled_ts_utc",
    "scheduled_tz_source",
    "selection_rule",
}


def _load_frozen() -> dict:
    return json.loads(FROZEN.read_text(encoding="utf-8"))


def test_frozen_sample_exists_and_is_small():
    spec = _load_frozen()
    assert spec["frozen_before_vendor_values"] is True
    assert spec["n_sample"] == 18
    assert spec["frozen_at_utc"] == "2026-09-19T07:36:34Z"
    events = spec["events"]
    assert [e["sample_id"] for e in events] == [f"S{i:02d}" for i in range(1, 19)]
    assert events[0]["currency"] == "USD"
    cats = {(e["currency"], e["category"]) for e in events}
    assert ("USD", "INFLATION") in cats
    assert ("USD", "EMPLOYMENT") in cats
    assert ("USD", "CENTRAL_BANK_DECISION") in cats
    assert ("GBP", "INFLATION") in cats
    assert ("CAD", "CENTRAL_BANK_DECISION") in cats


def test_frozen_sample_has_no_consensus_or_actual_values():
    spec = _load_frozen()
    for row in spec["events"] + spec["timestamp_stress_not_for_consensus"]:
        lowered = {k.lower() for k in row}
        assert not (lowered & set(FORBIDDEN_VALUE_KEYS))
        assert analysis_fields_clean(row)
        for key in ALLOWED_EVENT_KEYS:
            if key in row:
                assert row[key] not in (None, "") or key == "uncertain_reason"


def test_selection_is_deterministic_from_official_catalog():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    sample, stress = select_frozen_sample(catalog)
    frozen = _load_frozen()
    assert [e["event_id"] for e in sample] == [e["event_id"] for e in frozen["events"]]
    assert [e["event_id"] for e in stress] == [
        e["event_id"] for e in frozen["timestamp_stress_not_for_consensus"]
    ]
    assert all(analysis_fields_clean(r) for r in catalog)


def test_official_clocks_and_boc_fomc_lessons():
    frozen = {e["sample_id"]: e for e in _load_frozen()["events"]}
    assert frozen["S01"]["scheduled_ts_utc"] == "2025-09-11T12:30:00"
    assert frozen["S07"]["scheduled_ts_utc"] == "2025-09-17T18:00:00"
    assert frozen["S17"]["scheduled_ts_utc"] == "2025-09-17T13:45:00"
    assert frozen["S17"]["scheduled_tz_source"] == "America/Toronto"
    assert frozen["S10"]["scheduled_ts_utc"] == "2025-09-17T06:00:00"
    stress = {e["sample_id"]: e for e in _load_frozen()["timestamp_stress_not_for_consensus"]}
    assert stress["T01"]["role"] == "timestamp_stress_only_not_consensus_sample"
    assert stress["T01"]["uncertain_reason"] == "official_2025_lapse_delay"
    assert stress["T02"]["uncertain_reason"] == "official_2025_lapse_delay"
    winter = datetime.fromisoformat(stress["T02"]["scheduled_ts_utc"])
    summer = datetime.fromisoformat(frozen["S01"]["scheduled_ts_utc"])
    assert winter.hour == 13 and winter.minute == 30
    assert summer.hour == 12 and summer.minute == 30


def test_consensus_asof_must_precede_release_when_present():
    """Guardrail: if a later authorized sample adds vintages, asof must be pre-release."""
    for row in _load_frozen()["events"]:
        asof = row.get("consensus_asof_utc") or row.get("consensus_timestamp")
        assert asof is None
        scheduled = datetime.fromisoformat(row["scheduled_ts_utc"])
        assert scheduled.year >= 2025


def test_no_vendor_consensus_sample_was_stored():
    for path in VENDOR_DIRS:
        assert not path.exists()
    raw = ROOT / "data" / "research" / "external" / "raw"
    names = {p.name.lower() for p in raw.iterdir()} if raw.exists() else set()
    assert not names.intersection({"econoday", "tradingeconomics", "bloomberg", "forexfactory"})


def test_official_raw_files_remain_immutable_during_audit_helpers():
    probe = ROOT / "data" / "research" / "external" / "raw" / "BLS" / "2026-09-19" / "year_2025_cpi_empsit.txt"
    before = hashlib.sha256(probe.read_bytes()).hexdigest()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    select_frozen_sample(catalog)
    after = hashlib.sha256(probe.read_bytes()).hexdigest()
    assert before == after


def test_audit_outputs_record_incomplete_verdict():
    report = REPORT.read_text(encoding="utf-8")
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    assert "PIT_SAMPLE_INCOMPLETE" in report
    assert progress["verdict"] == "PIT_SAMPLE_INCOMPLETE"
    assert progress["purchase_made"] is False
    assert progress["surprise_study_run"] is False
    assert progress["fx_join_run"] is False
