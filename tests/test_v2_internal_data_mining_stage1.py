"""Helpers for V2 stage-1 mining. No live scoring. No source JSONL writes."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from forex_bot.v2_shadow.score_offline import last_completed_m5_start

_PATH = Path("reports/decision_quality/_v2_internal_data_mining_stage1.py")
_SPEC = importlib.util.spec_from_file_location("v2_internal_mining_stage1", _PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)
assign_quartile = _MOD.assign_quartile
earlier_cuts = _MOD.earlier_cuts
opportunity_key = _MOD.opportunity_key
unique_opportunities = _MOD.unique_opportunities


def test_opportunity_key_matches_score_offline():
    ts = datetime(2026, 9, 24, 21, 39, 3, 264589, tzinfo=timezone.utc)
    key = opportunity_key("EUR_USD", ts)
    expected = last_completed_m5_start(ts).isoformat()
    assert key == f"EUR_USD|{expected}"
    assert expected.startswith("2026-09-24T21:30:00")


def test_unique_opportunities_keep_earliest():
    rows = [
        {"decision_id": "b", "symbol": "EUR_USD", "timestamp_utc": "2026-09-24T12:26:50+00:00"},
        {"decision_id": "a", "symbol": "EUR_USD", "timestamp_utc": "2026-09-24T12:26:10+00:00"},
        {"decision_id": "c", "symbol": "GBP_USD", "timestamp_utc": "2026-09-24T12:26:10+00:00"},
    ]
    opp, n = unique_opportunities(rows)
    assert n == 3
    assert len(opp) == 2
    eur = [v for k, v in opp.items() if k.startswith("EUR_USD|")][0]
    assert eur["decision_id"] == "a"


def test_quartile_cuts_from_provided_values_only():
    cuts = earlier_cuts(list(range(1, 101)))
    assert cuts is not None
    assert assign_quartile(1, cuts) == "Q1"
    assert assign_quartile(100, cuts) == "Q4"
    assert assign_quartile(None, cuts) == "missing"
