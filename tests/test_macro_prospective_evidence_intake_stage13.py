"""Stage 13 manual evidence intake tests. Temporary dirs only. Zero network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_IPATH = Path("reports/decision_quality/_macro_prospective_evidence_intake_stage13.py")
_ISPEC = importlib.util.spec_from_file_location("macro_stage13", _IPATH)
S13 = importlib.util.module_from_spec(_ISPEC)
_ISPEC.loader.exec_module(S13)

R = S13.R
UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
CLOCK = datetime(2026, 10, 12, 12, 40, tzinfo=UTC)
CREATED_T48 = datetime(2026, 10, 12, 12, 31, tzinfo=UTC)
MODIFIED_T48 = datetime(2026, 10, 12, 12, 32, tzinfo=UTC)
CPI = "usd_cpi_2026-10-14"


def _rec(tmp_path: Path, clock=CLOCK):
    rec = R.bootstrap_store(tmp_path, clock=lambda: clock)
    R.register_official_upcoming(rec, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    return rec


def _times(created=CREATED_T48, modified=MODIFIED_T48):
    def _fn(_path):
        return created, modified
    return _fn


def _write(path: Path, data: bytes):
    path.write_bytes(data)
    return path


def _png(tmp_path: Path, name="capture.png", data=b"PNGFIX"):
    return _write(tmp_path / name, data)


def _mp4(tmp_path: Path, name="capture.mp4", data=b"MP4FIX"):
    return _write(tmp_path / name, data)


def test_valid_png_and_mp4_hash_and_bytes(tmp_path):
    rec = _rec(tmp_path)
    png = _png(tmp_path)
    before = png.read_bytes()
    src_sha = hashlib.sha256(before).hexdigest()
    out = S13.intake(rec=rec, event_id=CPI, checkpoint="T48H", source_file=png, times_fn=_times())
    assert out["observation_eligible"] is True
    assert out["pre_release_eligible"] is True
    assert out["source_sha256"] == src_sha
    assert out["archived_sha256"] == src_sha
    assert out["byte_length"] == len(before)
    assert png.read_bytes() == before
    archived = Path(out["archived_path"])
    assert archived.exists()
    assert hashlib.sha256(archived.read_bytes()).hexdigest() == src_sha
    assert out["source_file_created_utc"] == "2026-10-12T12:31:00Z"
    assert out["source_file_modified_utc"] == "2026-10-12T12:32:00Z"
    assert out["intake_utc"] == "2026-10-12T12:40:00Z"
    assert out["observed_at_utc"] == "2026-10-12T12:31:00Z"
    assert out["observed_at_utc"] != out["intake_utc"]
    assert out["observed_at_utc"] != out["checkpoint_scheduled_utc"]
    mp4 = _mp4(tmp_path)
    video = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=mp4, times_fn=_times())
    assert video["archived_sha256"] == hashlib.sha256(b"MP4FIX").hexdigest()
    assert Path(video["archived_path"]).suffix == ".mp4"


def test_unsupported_and_missing_file_rejected(tmp_path):
    rec = _rec(tmp_path)
    txt = _write(tmp_path / "notes.txt", b"nope")
    with pytest.raises(S13.IntakeClosed, match="unsupported"):
        S13.intake(rec=rec, event_id=CPI, checkpoint="T48H", source_file=txt, times_fn=_times())
    with pytest.raises(S13.IntakeClosed, match="EVIDENCE_FILE_NOT_FOUND"):
        S13.intake(rec=rec, event_id=CPI, checkpoint="T48H", source_file=tmp_path / "missing.png", times_fn=_times())
    assert S13.load_index(rec) == []


def test_duplicate_idempotent_and_same_sha_other_checkpoint_review(tmp_path):
    rec = _rec(tmp_path)
    png = _png(tmp_path)
    first = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times())
    second = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times())
    assert second["already_existed"] is True
    assert second["evidence_id"] == first["evidence_id"]
    assert len(S13.load_index(rec)) == 1
    other = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-36h", source_file=png, times_fn=_times())
    assert other["review_required"] is True
    assert other["observation_eligible"] is False
    assert "different checkpoint" in " ".join(other["reasons"])
    assert len(S13.load_index(rec)) == 1


def test_different_evidence_cannot_overwrite_captured(tmp_path):
    rec = _rec(tmp_path)
    png = _png(tmp_path)
    first = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times())
    displayed = {
        "headline_mom": {"consensus_raw": "0.2", "forecast_raw": "0.3", "previous_raw": "0.1"},
        "headline_yoy": {"consensus_raw": "3.1", "forecast_raw": "3.0", "previous_raw": "2.9"},
        "core_mom": {"consensus_raw": "0.2", "forecast_raw": "0.2", "previous_raw": "0.2"},
        "core_yoy": {"consensus_raw": "3.0", "forecast_raw": "3.1", "previous_raw": "3.0"},
    }
    S13.ingest_values(rec=rec, event_id=CPI, checkpoint="T0-48h", evidence_ref=first["evidence_id"], displayed=displayed, provider_id="fixture_provider_a")
    other = _png(tmp_path, "other.png", b"OTHER")
    blocked = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=other, times_fn=_times())
    assert blocked["observation_eligible"] is False
    assert any("already CAPTURED" in r for r in blocked["reasons"])
    assert len([o for o in rec.load_observations() if o["macro_event_id"] == CPI]) == 1


def test_insufficient_future_post_t0_and_unmapped_evidence(tmp_path):
    rec = _rec(tmp_path)
    png = _png(tmp_path)
    insuff = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times(datetime(1969, 12, 31, tzinfo=UTC), MODIFIED_T48))
    assert insuff["observation_eligible"] is False
    assert insuff["timestamp_provenance"] == "INSUFFICIENT"
    assert Path(insuff["archived_path"]).exists()
    with pytest.raises(S13.IntakeClosed, match="future"):
        S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times(datetime(2026, 10, 12, 13, 40, tzinfo=UTC), MODIFIED_T48))
    post_rec = _rec(tmp_path / "post", clock=datetime(2026, 10, 14, 13, 0, tzinfo=UTC))
    post = S13.intake(rec=post_rec, event_id=CPI, checkpoint="T0-48h", source_file=_png(tmp_path, "post.png", b"POST"), times_fn=_times(datetime(2026, 10, 14, 12, 30, tzinfo=UTC), datetime(2026, 10, 14, 12, 31, tzinfo=UTC)))
    assert post["pre_release_eligible"] is False
    assert post["observation_eligible"] is False
    early = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=_png(tmp_path, "early.png", b"EARLY"), times_fn=_times(datetime(2026, 10, 12, 0, 0, tzinfo=UTC), datetime(2026, 10, 12, 0, 1, tzinfo=UTC)))
    assert early["observation_eligible"] is False
    assert any("not silently mapped" in r for r in early["reasons"])


def test_dry_run_makes_zero_writes(tmp_path):
    rec = _rec(tmp_path)
    png = _png(tmp_path)
    out = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, dry_run=True, times_fn=_times())
    assert out["dry_run"] is True
    assert out["status"] == "DRY_RUN"
    assert S13.load_index(rec) == []
    assert not Path(out["archived_path"]).exists()
    assert rec.load_observations() == []


def test_value_failure_keeps_evidence_and_blank_consensus(tmp_path):
    rec = _rec(tmp_path)
    png = _png(tmp_path)
    secured = S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=png, times_fn=_times())
    archived = Path(secured["archived_path"]).read_bytes()
    bad = {
        "headline_mom": {"consensus_raw": "", "forecast_raw": "0.3", "previous_raw": "0.1"},
        "headline_yoy": {"consensus_raw": "", "forecast_raw": "3.0", "previous_raw": "2.9"},
        "core_mom": {"consensus_raw": "", "forecast_raw": "0.2", "previous_raw": "0.2"},
        "core_yoy": {"consensus_raw": "", "forecast_raw": "3.1", "previous_raw": "3.0"},
    }
    comps = S13.build_components(rec.event_by_id(CPI), bad)
    assert comps["headline_mom"]["consensus_value"] is None
    assert comps["headline_mom"]["consensus_value_quality"] == "NOT_AVAILABLE"
    assert comps["headline_mom"]["te_forecast_value"] == pytest.approx(0.3)
    assert comps["headline_mom"]["consensus_substituted_from_te_forecast"] is False
    ok = {
        "headline_mom": {"consensus_raw": "", "forecast_raw": "0.3", "previous_raw": "0.1"},
        "headline_yoy": {"consensus_raw": "3.1", "forecast_raw": "3.0", "previous_raw": "2.9"},
        "core_mom": {"consensus_raw": "0.2", "forecast_raw": "0.2", "previous_raw": "0.2"},
        "core_yoy": {"consensus_raw": "3.0", "forecast_raw": "3.1", "previous_raw": "3.0"},
    }
    ingested = S13.ingest_values(rec=rec, event_id=CPI, checkpoint="T0-48h", evidence_ref=secured["evidence_id"], displayed=ok, provider_id="fixture_provider_a")
    assert ingested["components"]["headline_mom"]["consensus_value"] is None
    assert ingested["observation_id"]
    assert Path(secured["archived_path"]).read_bytes() == archived
    combined = S13.intake(
        rec=rec,
        event_id=CPI,
        checkpoint="T0-48h",
        source_file=_png(tmp_path, "second.png", b"SECOND"),
        times_fn=_times(),
        displayed={"headline_mom": {"consensus_raw": "not-a-number"}},
    )
    assert Path(combined["archived_path"]).exists()
    assert combined.get("value_ingest_error")


def test_no_ocr_network_or_trading_changes(tmp_path):
    rec = _rec(tmp_path)
    before_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_bytes()
    before_events = (REAL_ROOT / "events" / "events.json").read_bytes()
    before_task = (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_bytes()
    before_cfg = (REAL_ROOT / "config.json").read_text(encoding="utf-8")
    src = Path("reports/decision_quality/_macro_prospective_evidence_intake_stage13.py").read_text(encoding="utf-8")
    low = src.lower()
    for forbidden in ("import pytesseract", "easyocr", "import cv2", "selenium", "playwright", "urllib.request", "requests.get", "oanda", "tradingeconomics.com", "forexfactory.com", "bls.gov"):
        assert forbidden not in low
    S13.intake(rec=rec, event_id=CPI, checkpoint="T0-48h", source_file=_png(tmp_path), times_fn=_times())
    assert (REAL_ROOT / "observations" / "observations.jsonl").read_bytes() == before_obs
    assert (REAL_ROOT / "events" / "events.json").read_bytes() == before_events
    assert (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_bytes() == before_task
    assert (REAL_ROOT / "config.json").read_text(encoding="utf-8") == before_cfg
    cfg = json.loads(before_cfg)
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    text = rec.format_status()
    assert "NEXT_EVENT_T48H_SCHEDULED_UTC:" in text
    assert "NEXT_EVENT_T48H_IS_OPEN:" in text
    assert "NEXT_EVENT_T48H_STATUS:" in text
    ready = S13.readiness_check(rec, CPI)
    assert ready["event_registered"] is True
    assert ready["t0_utc"] == "2026-10-14T12:30:00Z"
    assert ready["t48h_scheduled_utc"] == "2026-10-12T12:30:00Z"
    assert ready["t48h_is_open"] is True
    assert ready["http_requests"] == 0
    for path in (Path("forex_bot/bot_loop.py"), Path("reports/decision_quality/_macro_prospective_scheduler.py")):
        assert "_macro_prospective_evidence_intake_stage13" not in path.read_text(encoding="utf-8")
