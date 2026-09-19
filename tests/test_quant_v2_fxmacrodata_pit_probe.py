"""Provenance tests for the FXMacroData free PIT consensus probe."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reports" / "decision_quality"))

from _quant_v2_fxmacrodata_pit_helpers import (  # noqa: E402
    classify_prediction_class,
    clocks_match,
    epoch_seconds_to_utc,
    first_print_from_revisions,
    is_consensus_class,
    prediction_precedes_release,
    revisions_separated,
)

PROBE = ROOT / "data" / "research" / "external" / "fxmacrodata_probe"
RAW = PROBE / "raw"
STANDARD = ROOT / "reports" / "decision_quality" / "quant_v2_fxmacrodata_pit_standard.json"
IDS = ROOT / "reports" / "decision_quality" / "quant_v2_fxmacrodata_frozen_recent_usd_ids.json"
REPORT = ROOT / "reports" / "decision_quality" / "quant_v2_fxmacrodata_pit_probe.md"
PROGRESS = ROOT / "reports" / "decision_quality" / "quant_v2_fxmacrodata_pit_probe_progress.json"
PRIOR_SAMPLE = ROOT / "reports" / "decision_quality" / "quant_v2_pit_consensus_frozen_sample.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pit_standard_frozen_before_prediction_values():
    spec = _json(STANDARD)
    assert spec["frozen_before_prediction_values"] is True
    assert "prediction_asof < official_release_time" in spec["critical_rule"]
    ids = _json(IDS)
    assert ids["frozen_before_prediction_values"] is True
    assert ids["n_sample"] == 3
    for row in ids["events"]:
        assert "predicted_value" not in row
        assert "consensus" not in row
        assert row["selected_before_prediction_values"] is True


def test_prior_s01_s18_sample_untouched():
    prior = _json(PRIOR_SAMPLE)
    assert prior["frozen_at_utc"] == "2026-09-19T07:36:34Z"
    assert prior["n_sample"] == 18


def test_timestamp_parsing_and_official_clock_match():
    assert epoch_seconds_to_utc(1786537800) == datetime(2026, 8, 12, 12, 30)
    assert epoch_seconds_to_utc(1786105800) == datetime(2026, 8, 7, 12, 30)
    assert epoch_seconds_to_utc(1785348000) == datetime(2026, 7, 29, 18, 0)
    assert clocks_match("2026-08-12T12:30:00", 1786537800)
    assert clocks_match("2026-09-11T12:30:00", 1789129800)
    assert clocks_match("2026-09-16T18:00:00", 1789581600)


def test_prediction_type_classification():
    assert classify_prediction_class("compiled_consensus") == "COMPILED_CONSENSUS"
    assert classify_prediction_class("forecaster_survey") == "FORECASTER_SURVEY"
    assert classify_prediction_class("fxmacrodata") == "MODEL_GENERATED"
    assert classify_prediction_class("model_nowcast") == "MODEL_GENERATED"
    assert classify_prediction_class("central_bank_projection") == "CENTRAL_BANK_FORECAST"
    assert is_consensus_class("compiled_consensus")
    assert not is_consensus_class("fxmacrodata")


def test_prediction_asof_must_precede_release():
    release = datetime(2026, 9, 11, 12, 30)
    assert prediction_precedes_release(datetime(2026, 9, 11, 12, 29), release)
    assert not prediction_precedes_release(datetime(2026, 9, 11, 12, 30), release)
    assert not prediction_precedes_release(datetime(2026, 9, 11, 12, 31), release)


def test_nfp_revisions_separate_first_print_from_latest():
    nfp = _json(RAW / "v1_announcements_usd_non_farm_payrolls_limit-3.json")
    july = next(r for r in nfp["data"] if r["announcement_id"] == "usd_non_farm_payrolls_2026-07-31")
    assert nfp["filters"]["revisions"] == "latest"
    assert july["val"] == 158913000.0
    assert first_print_from_revisions(july["revisions"]) == 158858000.0
    assert revisions_separated(july)
    assert july["val"] != first_print_from_revisions(july["revisions"])


def test_compiled_consensus_absent_and_values_require_key():
    infl = _json(RAW / "v1_predictions_usd_inflation_prediction_class-compiled_consensus_limit-3.json")
    nfp = _json(RAW / "v1_predictions_usd_non_farm_payrolls_prediction_class-compiled_consensus_limit-3.json")
    pol = _json(RAW / "v1_predictions_usd_policy_rate_prediction_class-compiled_consensus_limit-3.json")
    for payload in (infl, nfp, pol):
        assert payload["code"] == "api_key_required"
        assert payload["availability"]["reason"]["compiled_consensus"] == "no_source_for_pair"
    survey = _json(RAW / "v1_predictions_usd_inflation_prediction_class-forecaster_survey_limit-3.json")
    assert survey["availability"]["reason"]["forecaster_survey"] == "values_require_key"


def test_coverage_catalogue_flags():
    cov = _json(RAW / "v1_predictions_coverage_usd.json")
    assert cov["access"]["coverage_requires_key"] is False
    assert cov["access"]["values_require_key"] is True
    by = {r["indicator"]: r for r in cov["indicators"]}
    assert by["non_farm_payrolls"]["has_consensus_source"] is False
    assert by["policy_rate"]["has_consensus_source"] is False
    assert "compiled_consensus" not in by["inflation"]["classes_with_sources"]


def test_raw_probe_files_immutable_under_helpers():
    probe = RAW / "v1_predictions_coverage_usd.json"
    before = hashlib.sha256(probe.read_bytes()).hexdigest()
    classify_prediction_class("compiled_consensus")
    epoch_seconds_to_utc(1789129800)
    after = hashlib.sha256(probe.read_bytes()).hexdigest()
    assert before == after


def test_report_verdict_and_no_purchase():
    report = REPORT.read_text(encoding="utf-8")
    progress = _json(PROGRESS)
    assert "FXMACRODATA_UNSUITABLE" in report
    assert "PAID_VENDOR_SAMPLE_REQUEST_JUSTIFIED" in report
    assert progress["verdict"] == "FXMACRODATA_UNSUITABLE"
    assert progress["next_action"] == "PAID_VENDOR_SAMPLE_REQUEST_JUSTIFIED"
    assert progress["purchase_made"] is False
    assert progress["fx_join_run"] is False
