"""Stage-4 early-sync helpers. No bot_loop. No source JSONL/FX writes."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

_PATH = Path("reports/decision_quality/_macro_us_early_sync_stage4.py")
_SPEC = importlib.util.spec_from_file_location("macro_us_early_sync_stage4", _PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)

S3 = _MOD.S3
decision_time = _MOD.decision_time
feature_bar_start = _MOD.feature_bar_start
exit_bar_start = _MOD.exit_bar_start
exec_follow_pips = _MOD.exec_follow_pips
agreement_with_median = _MOD.agreement_with_median
continuation_vs_first = _MOD.continuation_vs_first


def test_decision_time_is_t0_plus_5():
    t0 = datetime(2025, 9, 11, 12, 30, tzinfo=timezone.utc)
    d = decision_time(t0)
    assert d == t0 + timedelta(minutes=5)
    assert feature_bar_start(t0) == t0
    assert feature_bar_start(t0) + timedelta(minutes=5) == d


def test_feature_bar_cannot_include_bar_starting_at_d():
    t0 = datetime(2025, 9, 11, 12, 30, tzinfo=timezone.utc)
    d = decision_time(t0)
    feat = feature_bar_start(t0)
    assert feat + timedelta(minutes=5) <= d
    assert feat != d
    # the next candle starts at D and is unknown at D
    next_bar = d
    assert next_bar > feat
    assert next_bar >= d


def test_remaining_5_to_15_is_not_t0_to_15_cumulative():
    t0 = datetime(2025, 9, 11, 12, 30, tzinfo=timezone.utc)
    d = decision_time(t0)
    exit15 = exit_bar_start(t0, 15)
    assert exit15 == t0 + timedelta(minutes=10)
    assert exit15 >= d
    # T0→+15 would use the T0 bar open; remaining starts at T0-bar close
    assert exit15 != t0
    assert exit_bar_start(t0, 30) == t0 + timedelta(minutes=25)
    assert exit_bar_start(t0, 60) == t0 + timedelta(minutes=55)


def test_exit_bar_for_primary_horizons_is_strictly_after_d():
    t0 = datetime(2025, 9, 5, 12, 30, tzinfo=timezone.utc)
    d = decision_time(t0)
    for end in (15, 30, 60, 120, 240):
        start = exit_bar_start(t0, end)
        assert start >= d
        completes = start + timedelta(minutes=5)
        assert completes == t0 + timedelta(minutes=end)
        assert completes > d


def test_usd_executable_mapping_at_d():
    entry = pd.Series({"ask_close": 1.10010, "bid_close": 1.10000})
    later = pd.Series({"ask_close": 1.09910, "bid_close": 1.09900})  # EUR down 10 native pips mid-ish
    # USD strength => SELL EUR_USD: entry bid_close, exit ask_close
    pips = exec_follow_pips("EUR_USD", 1, entry, later)
    assert abs(pips - (1.10000 - 1.09910) / 0.0001) < 1e-9
    # USD strength => BUY USD_JPY
    e2 = pd.Series({"ask_close": 150.010, "bid_close": 150.000})
    x2 = pd.Series({"ask_close": 150.130, "bid_close": 150.120})
    p2 = exec_follow_pips("USD_JPY", 1, e2, x2)
    assert abs(p2 - (150.120 - 150.010) / 0.01) < 1e-9
    # USD weakness reverses both
    p_eur_weak = exec_follow_pips("EUR_USD", -1, entry, later)
    assert p_eur_weak == (1.09900 - 1.10010) / 0.0001
    p_jpy_weak = exec_follow_pips("USD_JPY", -1, e2, x2)
    assert p_jpy_weak == (150.000 - 150.130) / 0.01


def test_eligibility_still_29_pit_approved():
    import json

    events = json.loads(S3.EVENTS_PATH.read_text(encoding="utf-8"))
    keep, drop = S3.eligible_events(events)
    assert len(keep) == 29
    fam = {}
    for e in keep:
        fam[e["event_family"]] = fam.get(e["event_family"], 0) + 1
    assert fam["CPI"] == 10
    assert fam["EMPLOYMENT_SITUATION"] == 11
    assert fam["FOMC"] == 8
    dropped_ids = {d["macro_event_id"] for d in drop}
    assert "usd_cpi_2025-10-24" in dropped_ids or any("unpublished" in str(d["reasons"]) for d in drop)


def test_continuation_classifier_uses_first5_sign_not_t0_cumulative():
    assert continuation_vs_first(1, 4.0) == "continuation"
    assert continuation_vs_first(1, -2.0) == "reversal"
    assert continuation_vs_first(-1, -0.5) == "continuation"
    assert continuation_vs_first(1, 0.0) == "flat"
    assert continuation_vs_first(0, 3.0) == "flat"


def test_agreement_zeros_do_not_count():
    pairs = {
        "EUR_USD": 2.0,
        "GBP_USD": 1.0,
        "AUD_USD": 0.5,
        "USD_JPY": 0.0,
        "USD_CAD": 3.0,
        "USD_CHF": 1.5,
    }
    agree, med_s, med = agreement_with_median(pairs)
    assert med_s == 1
    assert agree == 5


def test_results_keep_29_events_and_primary_counts():
    import json

    path = Path("reports/decision_quality/_macro_us_early_sync_stage4_results.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["eligible_n"] == 29
    assert payload["eligible_by_family"]["CPI"] == 10
    assert payload["eligible_by_family"]["EMPLOYMENT_SITUATION"] == 11
    assert payload["eligible_by_family"]["FOMC"] == 8
    assert payload["controls"]["n"] == 458
    assert payload["primary_6of6"]["n"] == 22
    assert payload["agreement_dist"].get("6") == 22 or payload["agreement_dist"].get(6) == 22
    # remaining +5->+15 is not the T0-cumulative first-5m print
    row = payload["events"][0]
    rem15 = row["remaining_mid"].get("15") or row["remaining_mid"].get(15)
    assert rem15 is not None
    assert rem15["median"] != row["first5_median_usd_pips"]
