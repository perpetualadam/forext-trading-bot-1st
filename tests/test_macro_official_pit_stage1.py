"""Official macro PIT helpers. No bot_loop. No source JSONL writes."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

_PATH = Path("reports/decision_quality/_macro_official_pit_stage1.py")
_SPEC = importlib.util.spec_from_file_location("macro_official_pit_stage1", _PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)

et_wall_to_utc = _MOD.et_wall_to_utc
never_overwrite_first_print = _MOD.never_overwrite_first_print
split_event_and_values = _MOD.split_event_and_values
validate_value_record = _MOD.validate_value_record


def test_dst_conversion_est_vs_edt():
    winter = et_wall_to_utc(2025, 1, 10, 8, 30)
    summer = et_wall_to_utc(2025, 7, 3, 8, 30)
    cpi_sep = et_wall_to_utc(2025, 9, 11, 8, 30)
    assert winter == datetime(2025, 1, 10, 13, 30, tzinfo=timezone.utc)
    assert summer == datetime(2025, 7, 3, 12, 30, tzinfo=timezone.utc)
    assert cpi_sep == datetime(2025, 9, 11, 12, 30, tzinfo=timezone.utc)
    assert winter.hour - summer.hour == 1


def test_fomc_1400_et_dst():
    edt = et_wall_to_utc(2025, 9, 17, 14, 0)
    est = et_wall_to_utc(2025, 12, 10, 14, 0)
    assert edt == datetime(2025, 9, 17, 18, 0, tzinfo=timezone.utc)
    assert est == datetime(2025, 12, 10, 19, 0, tzinfo=timezone.utc)


def test_release_and_reference_period_are_separate():
    event = {
        "macro_event_id": "usd_cpi_2025-09-11",
        "event_family": "CPI",
        "event_name": "headline_cpi_mom_sa",
        "reference_period": "2025-08",
        "scheduled_release_utc": "2025-09-11T12:30:00+00:00",
        "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE",
    }
    assert event["reference_period"] != event["scheduled_release_utc"][:7]
    assert event["reference_period"] == "2025-08"


def test_first_print_not_overwritten_by_revision():
    store: dict = {}
    never_overwrite_first_print(store, "usd_empsit_2025-09-05", "nfp_change_first_print", 22000)
    try:
        never_overwrite_first_print(store, "usd_empsit_2025-09-05", "nfp_change_first_print", -4000)
        raised = False
    except ValueError:
        raised = True
    assert raised
    assert store["usd_empsit_2025-09-05|nfp_change_first_print"]["value"] == 22000
    never_overwrite_first_print(store, "usd_empsit_2025-11-20", "previous_nfp_revised", -4000)
    assert store["usd_empsit_2025-11-20|previous_nfp_revised"]["value"] == -4000


def test_multi_value_single_event():
    event = {"macro_event_id": "usd_cpi_2025-09-11", "event_family": "CPI"}
    values = [
        {"macro_event_id": "usd_cpi_2025-09-11", "event_family": "CPI", "event_name": "headline_cpi_mom_sa", "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE"},
        {"macro_event_id": "usd_cpi_2025-09-11", "event_family": "CPI", "event_name": "core_cpi_mom_sa", "pit_status": "PIT_SAFE_IF_USING_ARCHIVED_RELEASE"},
    ]
    packed = split_event_and_values(event, values)
    assert len(packed["values"]) == 2
    assert validate_value_record(values[0]) == []


def test_source_artifact_hash_is_stable():
    src = Path("data/research/macro_first_print/raw/bls/cpi/cpi_09112025.official.txt")
    raw = src.read_bytes().replace(b"\r\n", b"\n")
    digest = __import__("hashlib").sha256(raw).hexdigest()
    assert digest == "661f535af15d617a3930e83ff2e549dcb0cc42feec5d8aefd93de974cb4076da"


def test_consensus_without_asof_rejected():
    row = {
        "macro_event_id": "x",
        "event_family": "CPI",
        "event_name": "headline_cpi_mom_sa",
        "pit_status": "PIT_SAFE",
        "consensus": 0.2,
        "consensus_asof_utc": None,
    }
    assert "consensus without consensus_asof_utc" in validate_value_record(row)
