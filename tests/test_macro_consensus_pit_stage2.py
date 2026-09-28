"""Consensus PIT Stage 2: historical reconstruction + forward snapshot architecture."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_S2 = Path("reports/decision_quality/_macro_consensus_pit_stage2.py")
_FW = Path("reports/decision_quality/_macro_consensus_forward.py")
_SPEC = importlib.util.spec_from_file_location("macro_consensus_pit_stage2", _S2)
S2 = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(S2)
_SPEC2 = importlib.util.spec_from_file_location("macro_consensus_forward", _FW)
FW = importlib.util.module_from_spec(_SPEC2)
assert _SPEC2 is not None and _SPEC2.loader is not None
_SPEC2.loader.exec_module(FW)


def test_remaining_universe_frozen_before_search_and_not_fx_conditioned():
    blob = S2.frozen_remaining()
    assert blob["fx_outcomes_used"] is False
    assert blob["remaining_n"] == 20
    ids = [e["macro_event_id"] for e in blob["remaining"]]
    assert ids[0] == "usd_cpi_2025-10-24"
    assert "usd_cpi_2025-09-11" not in ids
    assert len([i for i in ids if i.startswith("usd_cpi_")]) == 7
    assert len([i for i in ids if "empsit" in i]) == 8
    assert len([i for i in ids if "fomc" in i]) == 5


def test_pre_t0_timestamp_required_for_pit_safe():
    assert S2.publication_before_t0("2025-10-21T14:20:00Z", "2025-10-24T12:30:00Z") is True
    recs = json.loads((S2.NORM_DIR / "all_records.json").read_text(encoding="utf-8"))
    for rec in recs:
        if rec["pit_status"] != "PIT_SAFE":
            continue
        assert S2.publication_before_t0(rec.get("source_publication_utc"), rec["official_release_utc"]), rec["consensus_evidence_id"]


def test_post_t0_rejection():
    recs = json.loads((S2.EVIDENCE_DIR / "remaining_evidence.json").read_text(encoding="utf-8"))
    post = [r for r in recs if r["pit_status"] == "REJECT_POST_RELEASE"]
    assert post
    for rec in post:
        pub = S2.parse_utc(rec.get("source_publication_utc"))
        t0 = S2.parse_utc(rec["official_release_utc"])
        assert pub is not None and t0 is not None and pub >= t0


def test_exact_series_unit_and_reference_period_matching():
    exp = {"series_name": "headline_yoy", "unit": "percent", "seasonal_adjustment": "NSA", "reference_period": "2025-09"}
    off = {"series_name": "headline_yoy", "unit": "percent", "seasonal_adjustment": "NSA"}
    event = {"reference_period": "2025-09"}
    assert S2.exact_series_match(exp, off)
    assert S2.units_match(exp, off)
    assert S2.seasonal_match(exp, off)
    assert S2.reference_period_match(exp, event)
    assert not S2.exact_series_match({**exp, "series_name": "headline_mom"}, off)
    assert not S2.units_match({**exp, "unit": "persons"}, off)
    assert not S2.reference_period_match(exp, {"reference_period": "2025-11"})
    assert not S2.seasonal_match({**exp, "seasonal_adjustment": "SA"}, off)
    wrong = {"series_name": "headline_mom", "unit": "percent", "seasonal_adjustment": "SA", "reference_period": "2025-11"}
    official_2m = {"series_name": "headline_2m_sa", "unit": "percent", "seasonal_adjustment": "SA"}
    assert not S2.exact_series_match(wrong, official_2m)


def test_pit_safe_not_mixed_with_limitation():
    gold = json.loads((S2.GOLD_DIR / "gold.json").read_text(encoding="utf-8"))
    silver = json.loads((S2.SILVER_DIR / "silver.json").read_text(encoding="utf-8"))
    assert gold and silver
    assert all(r["pit_status"] == "PIT_SAFE" for r in gold)
    assert all(r["pit_status"] == "PIT_SAFE_WITH_LIMITATION" for r in silver)
    gold_ids = {r["consensus_evidence_id"] for r in gold}
    silver_ids = {r["consensus_evidence_id"] for r in silver}
    assert gold_ids.isdisjoint(silver_ids)


def test_multiple_providers_preserved_not_averaged():
    recs = json.loads((S2.NORM_DIR / "all_records.json").read_text(encoding="utf-8"))
    rows = S2.never_average_providers(recs, "usd_cpi_2026-04-10", "headline_yoy")
    pubs = {p for p, _ in rows}
    vals = {v for _, v in rows}
    assert "Reuters" in pubs
    assert "FactSet Insight" in pubs
    assert 3.3 in vals and 3.4 in vals
    assert (3.3 + 3.4) / 2 not in vals
    with pytest.raises(RuntimeError, match="must not be averaged"):
        FW.average_forecasts(recs)


def test_individual_forecast_not_relabeled_consensus():
    recs = json.loads((S2.NORM_DIR / "all_records.json").read_text(encoding="utf-8"))
    individuals = [r for r in recs if r["expectation_type"] == "INDIVIDUAL_FORECAST"]
    assert individuals
    assert all("CONSENSUS" not in r["expectation_type"] for r in individuals)
    assert all(S2.is_individual_not_consensus(r) for r in individuals)


def test_fomc_probability_distribution_preserved():
    recs = json.loads((S2.NORM_DIR / "all_records.json").read_text(encoding="utf-8"))
    implied = [r for r in recs if r["expectation_type"] == "MARKET_IMPLIED_EXPECTATION"]
    assert implied
    assert all(S2.fomc_probs_not_collapsed(r) for r in implied)
    oct_poll = next(r for r in recs if r["consensus_evidence_id"] == "ce_fomc_20251029_reuters_poll_decision")
    assert oct_poll["distribution"]["cut_25bp"] == 115
    assert oct_poll["forecast_value"] == "cut_25bp"
    assert oct_poll["forecast_value"] != -25


def test_raw_surprise_only_from_strict_pit_safe_scalar_consensus():
    blob = json.loads((S2.NORM_DIR / "raw_surprise_gold.json").read_text(encoding="utf-8"))
    recs = json.loads((S2.NORM_DIR / "all_records.json").read_text(encoding="utf-8"))
    by_id = {r["consensus_evidence_id"]: r for r in recs}
    silver_ids = {r["consensus_evidence_id"] for r in recs if r["pit_status"] == "PIT_SAFE_WITH_LIMITATION"}
    for s in blob["surprise"]:
        src = by_id[s["consensus_evidence_id"]]
        assert src["pit_status"] == "PIT_SAFE"
        assert s["consensus_evidence_id"] not in silver_ids
        if s.get("raw_surprise_possible") and src["series_name"] in S2.SCALAR_SERIES:
            assert src["expectation_type"] != "INDIVIDUAL_FORECAST"
            assert s["surprise_raw"] == pytest.approx(float(s["official_actual"]) - float(src["forecast_value"]))
    oct_yoy = next(s for s in blob["surprise"] if s["consensus_evidence_id"] == "ce_cpi_20251024_reuters_poll_headline_yoy")
    assert oct_yoy["raw_surprise_possible"] is True
    assert oct_yoy["surprise_raw"] == pytest.approx(-0.1)


def test_us_pit_and_pilot_not_write_targets():
    assert S2.US_PIT_DIR.resolve() != S2.HIST_DIR.resolve()
    assert S2.PILOT_DIR.resolve() != S2.HIST_DIR.resolve()
    assert "us_pit" not in str(S2.HIST_DIR.resolve()).replace("\\", "/").split("consensus_pit")[-1]


def test_forward_collection_disabled_by_default():
    assert FW.collection_enabled() is False
    assert FW.all_sources_disabled() is True
    cfg = FW.load_config()
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False


def test_forward_immutable_append_hash_and_observed_at(tmp_path):
    store = tmp_path / "snapshots.jsonl"
    obs = tmp_path / "observations.jsonl"
    arts = tmp_path / "artifacts"
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"FORWARD_CONSENSUS_COLLECTION_ENABLED": False}), encoding="utf-8")
    payload = b"reuters median 0.4 mom"
    fields = {
        "macro_event_id": "usd_cpi_future",
        "event_family": "CPI",
        "series_name": "headline_mom",
        "reference_period": "2026-09",
        "expectation_type": "SURVEY_CONSENSUS",
        "forecast_value": 0.4,
        "unit": "percent",
        "source_publisher": "Reuters",
        "source_reference": "https://example.invalid/reuters",
        "source_publication_utc": "2026-09-20T04:00:00Z",
        "source_updated_utc": "2026-09-20T04:10:00Z",
        "observed_at_utc": "2026-09-20T10:00:00Z",
        "official_release_utc": "2026-09-22T12:30:00Z",
        "pit_status": None,
        "retrieval_method": "manual_research",
        "notes": "observed_at is our clock",
    }
    first = FW.append_snapshot(
        store_path=store, observations_path=obs, artifacts_dir=arts,
        artifact_bytes=payload, artifact_name="r1.txt", fields=fields, collection_flag_path=cfg,
    )
    assert first["deduped_identical_bytes"] is False
    assert first["snapshot_sequence"] == 1
    assert first["observed_at_utc"] == "2026-09-20T10:00:00Z"
    assert first["source_publication_utc"] == "2026-09-20T04:00:00Z"
    assert first["observed_at_utc"] != first["source_publication_utc"]
    assert first["raw_artifact_hash"] == hashlib.sha256(payload).hexdigest()
    assert first["pit_status"] == "PIT_SAFE"
    digest_file = Path(first["artifact_location"]).read_bytes()
    assert digest_file == payload

    second = FW.append_snapshot(
        store_path=store, observations_path=obs, artifacts_dir=arts,
        artifact_bytes=payload, artifact_name="r1.txt",
        fields={**fields, "observed_at_utc": "2026-09-21T10:00:00Z"},
        collection_flag_path=cfg,
    )
    assert second["deduped_identical_bytes"] is True
    assert second["snapshot_id"] == first["snapshot_id"]
    snaps = FW.load_snapshots(store)
    assert len(snaps) == 1
    observations = [json.loads(line) for line in obs.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(observations) == 2
    assert observations[1]["observed_at_utc"] == "2026-09-21T10:00:00Z"

    changed = FW.append_snapshot(
        store_path=store, observations_path=obs, artifacts_dir=arts,
        artifact_bytes=b"reuters median 0.5 mom", artifact_name="r2.txt",
        fields={**fields, "forecast_value": 0.5, "observed_at_utc": "2026-09-21T16:00:00Z"},
        collection_flag_path=cfg,
    )
    assert changed["deduped_identical_bytes"] is False
    assert changed["snapshot_id"] != first["snapshot_id"]
    assert changed["snapshot_sequence"] == 2
    assert changed["raw_artifact_hash"] != first["raw_artifact_hash"]
    snaps = FW.load_snapshots(store)
    assert len(snaps) == 2


def test_forward_post_t0_rejected_from_final_consensus(tmp_path):
    store = tmp_path / "snapshots.jsonl"
    obs = tmp_path / "observations.jsonl"
    arts = tmp_path / "artifacts"
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"FORWARD_CONSENSUS_COLLECTION_ENABLED": False}), encoding="utf-8")
    base = {
        "macro_event_id": "usd_cpi_future",
        "event_family": "CPI",
        "series_name": "headline_mom",
        "reference_period": "2026-09",
        "expectation_type": "SURVEY_CONSENSUS",
        "forecast_value": 0.4,
        "unit": "percent",
        "source_publisher": "Reuters",
        "source_reference": "https://example.invalid/reuters",
        "source_publication_utc": "2026-09-22T12:00:00Z",
        "source_updated_utc": None,
        "official_release_utc": "2026-09-22T12:30:00Z",
        "retrieval_method": "manual_research",
        "notes": "",
    }
    pre = FW.append_snapshot(
        store_path=store, observations_path=obs, artifacts_dir=arts,
        artifact_bytes=b"pre", artifact_name="pre.txt",
        fields={**base, "observed_at_utc": "2026-09-22T11:00:00Z"},
        collection_flag_path=cfg,
    )
    post = FW.append_snapshot(
        store_path=store, observations_path=obs, artifacts_dir=arts,
        artifact_bytes=b"post", artifact_name="post.txt",
        fields={**base, "forecast_value": 0.9, "observed_at_utc": "2026-09-22T13:00:00Z"},
        collection_flag_path=cfg,
    )
    assert pre["pit_status"] == "PIT_SAFE"
    assert post["pit_status"] == "REJECT_POST_RELEASE"
    snaps = FW.load_snapshots(store)
    final = FW.final_pre_release_snapshot(snaps, macro_event_id="usd_cpi_future", series_name="headline_mom")
    assert final is not None
    assert final["snapshot_id"] == pre["snapshot_id"]
    assert final["observed_at_utc"] == "2026-09-22T11:00:00Z"


def test_forward_multiple_providers_never_averaged(tmp_path):
    store = tmp_path / "snapshots.jsonl"
    obs = tmp_path / "observations.jsonl"
    arts = tmp_path / "artifacts"
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"FORWARD_CONSENSUS_COLLECTION_ENABLED": False}), encoding="utf-8")
    shared = {
        "macro_event_id": "usd_cpi_future",
        "event_family": "CPI",
        "series_name": "headline_yoy",
        "reference_period": "2026-09",
        "expectation_type": "SURVEY_CONSENSUS",
        "unit": "percent",
        "source_reference": "https://example.invalid/x",
        "source_publication_utc": "2026-09-20T04:00:00Z",
        "source_updated_utc": None,
        "observed_at_utc": "2026-09-20T10:00:00Z",
        "official_release_utc": "2026-09-22T12:30:00Z",
        "retrieval_method": "manual_research",
        "notes": "",
    }
    FW.append_snapshot(
        store_path=store, observations_path=obs, artifacts_dir=arts,
        artifact_bytes=b"reuters 3.3", artifact_name="reu.txt",
        fields={**shared, "forecast_value": 3.3, "source_publisher": "Reuters"},
        collection_flag_path=cfg,
    )
    FW.append_snapshot(
        store_path=store, observations_path=obs, artifacts_dir=arts,
        artifact_bytes=b"factset 3.4", artifact_name="fs.txt",
        fields={**shared, "forecast_value": 3.4, "source_publisher": "FactSet Insight", "expectation_type": "SURVEY_MEDIAN"},
        collection_flag_path=cfg,
    )
    snaps = FW.load_snapshots(store)
    pubs = FW.providers_preserved(snaps, "usd_cpi_future", "headline_yoy")
    assert pubs.count("Reuters") == 1
    assert pubs.count("FactSet Insight") == 1
    vals = [r["forecast_value"] for r in snaps]
    assert 3.3 in vals and 3.4 in vals
    assert 3.35 not in vals
