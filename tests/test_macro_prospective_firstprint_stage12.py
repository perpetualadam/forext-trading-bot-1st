"""Stage 12 official BLS first-print recovery tests. Fixtures only. Zero network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from forex_bot.decision_quality.macro_first_print.store import write_raw_release

_IPATH = Path("reports/decision_quality/_macro_prospective_firstprint_stage12.py")
_ISPEC = importlib.util.spec_from_file_location("macro_stage12", _IPATH)
S12 = importlib.util.module_from_spec(_ISPEC)
_ISPEC.loader.exec_module(S12)

S11 = S12.S11
S10 = S11.S10
S8 = S11.S8
S9_PATH = Path("reports/decision_quality/_macro_prospective_ingest_stage9.py")
S9_SPEC = importlib.util.spec_from_file_location("macro_stage9_for_s12", S9_PATH)
S9 = importlib.util.module_from_spec(S9_SPEC)
S9_SPEC.loader.exec_module(S9)

R = S12.R
UTC = timezone.utc
REAL_ROOT = Path("data/research/macro/consensus_pit/prospective")
FIXTURE = Path("tests/fixtures/macro_first_print/empsit_2026-10-02_first_print.txt").read_bytes()
U6 = Path("tests/fixtures/macro_first_print/empsit_u6_only.txt").read_bytes()
NONSUP = Path("tests/fixtures/macro_first_print/empsit_nonsupervisory_only.txt").read_bytes()
GENERIC = Path("tests/fixtures/macro_first_print/empsit_generic_current_page.txt").read_bytes()
OBS48 = "2026-09-30T12:31:17Z"
OBS24 = "2026-10-01T12:30:43Z"
OBS12 = "2026-10-02T00:30:36Z"
OBS15 = "2026-10-02T12:16:36Z"
TRADING_PATHS = (
    Path("forex_bot/bot_loop.py"),
    Path("forex_bot/execution.py") if Path("forex_bot/execution.py").exists() else Path("forex_bot/bot_loop.py"),
    Path("reports/decision_quality/_macro_prospective_scheduler.py"),
)


def _rec(tmp_path: Path):
    rec = R.bootstrap_store(tmp_path, clock=lambda: datetime(2026, 10, 2, 21, 0, tzinfo=UTC))
    R.register_official_upcoming(rec, datetime(2026, 9, 28, 21, 30, tzinfo=UTC))
    return rec


def _seed(rec):
    S8.ingest_stage8(rec=rec, evidence_bytes=b"s8", observed_at_utc=OBS48, evidence_filename="a.bin", evidence_sha256=hashlib.sha256(b"s8").hexdigest(), ingested_at_utc="2026-09-30T21:20:00Z", evidence_timestamp_basis="f", artifact_suffix="bin")
    S9.ingest_stage9(rec=rec, evidence_bytes=b"s9", observed_at_utc=OBS24, evidence_filename="b.bin", evidence_sha256=hashlib.sha256(b"s9").hexdigest(), ingested_at_utc="2026-10-01T21:20:00Z", evidence_timestamp_basis="f", artifact_suffix="bin")
    S10.ingest_stage10(rec=rec, evidence_bytes=b"s10", observed_at_utc=OBS12, evidence_filename="c.bin", evidence_sha256=hashlib.sha256(b"s10").hexdigest(), ingested_at_utc="2026-10-02T00:45:00Z", evidence_timestamp_basis="f", artifact_suffix="bin")
    priors = {cid: S11.fingerprint(S11.checkpoint_rows(rec, cid)[0]) for cid in S11.PRIOR_CHECKPOINTS}
    S11.ingest_stage11_checkpoint(rec=rec, checkpoint_id="T0-15m", evidence_bytes=b"s15", observed_at_utc=OBS15, evidence_filename="d.bin", evidence_sha256=hashlib.sha256(b"s15").hexdigest(), ingested_at_utc="2026-10-02T12:40:00Z", evidence_timestamp_basis="f", artifact_suffix="bin", priors=priors)


def _recover(rec, tmp_path, **kwargs):
    defaults = {
        "rec": rec,
        "official_root": tmp_path / "official",
        "artifact_bytes": FIXTURE,
        "source_url": S12.ARCHIVE_HTML,
    }
    defaults.update(kwargs)
    return S12.recover(**defaults)


def test_only_official_bls_can_become_canonical():
    with pytest.raises(S12.RecoveryClosed, match="non-official"):
        S12.assert_official_url("https://tradingeconomics.com/calendar")
    with pytest.raises(S12.RecoveryClosed, match="non-official"):
        S12.assert_official_url("https://www.forexfactory.com/")
    with pytest.raises(S12.RecoveryClosed, match="non-official"):
        S12.assert_official_url("https://fred.stlouisfed.org/")
    S12.assert_official_url(S12.ARCHIVE_HTML)
    S12.assert_official_url(S12.ARCHIVE_TXT)


def test_te_actual_cannot_become_canonical(tmp_path):
    rec = _rec(tmp_path)
    _seed(rec)
    with pytest.raises(S12.RecoveryClosed):
        _recover(rec, tmp_path, source_url="https://tradingeconomics.com/united-states/calendar", artifact_bytes=b"Actual 119K")
    assert rec.load_actuals() == []


def test_generic_mutable_bls_page_cannot_prove_first_print(tmp_path):
    generic = S12.prove_release_identity(S12.GENERIC_CURRENT_URL, GENERIC)
    assert generic["proven"] is False
    assert generic["status"] == "NOT_PROVEN"
    rec = _rec(tmp_path)
    _seed(rec)
    out = _recover(rec, tmp_path, artifact_bytes=GENERIC, source_url=S12.GENERIC_CURRENT_URL)
    assert out["status"] == "NOT_PROVEN"
    assert out["first_print_record_created"] is False
    assert rec.load_actuals() == []


def test_release_identity_must_match_2026_10_02():
    proven = S12.prove_release_identity(S12.ARCHIVE_HTML, FIXTURE)
    assert proven["proven"] is True
    assert proven["status"] == "PROVEN_FIRST_PRINT"
    wrong_date = FIXTURE.replace(b"October 2, 2026", b"October 3, 2026").replace(b"SEPTEMBER 2026", b"AUGUST 2026")
    not_proven = S12.prove_release_identity(S12.ARCHIVE_HTML, wrong_date)
    assert not_proven["proven"] is False


def test_raw_artifact_hash_deterministic_and_cannot_overwrite(tmp_path):
    dest = tmp_path / "official"
    first = write_raw_release(dest_dir=dest, filename="empsit_10022026.htm", body=FIXTURE, source_url=S12.ARCHIVE_HTML, http_status=200, content_type="text/plain", publication_date="2026-10-02", release_number="USDL-26-1602")
    assert first.sha256 == hashlib.sha256(FIXTURE).hexdigest()
    assert first.reused is False
    again = write_raw_release(dest_dir=dest, filename="empsit_10022026.htm", body=FIXTURE, source_url=S12.ARCHIVE_HTML, http_status=200, content_type="text/plain", publication_date="2026-10-02", release_number="USDL-26-1602")
    assert again.reused is True
    assert again.sha256 == first.sha256
    original = (dest / "empsit_10022026.htm").read_bytes()
    changed = write_raw_release(dest_dir=dest, filename="empsit_10022026.htm", body=b"DIFFERENT BYTES", source_url=S12.ARCHIVE_HTML, http_status=200, content_type="text/plain", publication_date="2026-10-02", release_number="USDL-26-1602")
    assert changed.hash_changed is True
    assert (dest / "empsit_10022026.htm").read_bytes() == original
    assert hashlib.sha256(original).hexdigest() == first.sha256


def test_nfp_unemployment_ahe_parsers_and_fail_closed():
    comps = S12.extract_official_components(FIXTURE.decode("utf-8"))
    assert comps["nfp"]["actual_first_print"] == 119000
    assert "Total nonfarm payroll employment change" in comps["nfp"]["semantics"]
    assert comps["unemployment"]["actual_first_print"] == pytest.approx(4.4)
    assert "U-3" in comps["unemployment"]["semantics"]
    assert comps["ahe_mom"]["actual_first_print"] == pytest.approx(0.3)
    assert "all employees" in comps["ahe_mom"]["semantics"].lower()
    assert comps["ahe_yoy"]["actual_first_print"] == pytest.approx(3.8)
    assert "all employees" in comps["ahe_yoy"]["semantics"].lower()
    with pytest.raises(S12.RecoveryClosed, match="U-6"):
        S12.extract_official_components(U6.decode("utf-8"))
    with pytest.raises(S12.RecoveryClosed, match="nonsupervisory"):
        S12.extract_official_components(NONSUP.decode("utf-8"))
    with pytest.raises(S12.RecoveryClosed, match="ambiguous"):
        S12.extract_official_components("THE EMPLOYMENT SITUATION -- SEPTEMBER 2026\nNo numbers here.\n")


def test_first_print_immutable_revision_separated_and_idempotent(tmp_path):
    rec = _rec(tmp_path)
    _seed(rec)
    before = rec.obs_path.read_bytes()
    first = _recover(rec, tmp_path)
    assert first["status"] == "RECORDED"
    assert first["first_print_record_created"] is True
    assert rec.obs_path.read_bytes() == before
    assert S11.checkpoint_rows(rec, "T0-5m") == []
    assert first["strict_final_surprise"]["available"] is False
    los = first["last_observed_surprise"]
    assert los["available"] is True
    assert los["label"] == "LAST_OBSERVED_SURPRISE"
    assert los["checkpoint_id"] == "T0-15m"
    assert los["observed_at_utc"] == OBS15
    assert los["nfp_consensus"] == 90000
    assert los["nfp_actual"] == 119000
    assert los["nfp_surprise"] == 29000
    assert los["nfp_unit"] == "persons"
    assert los["unemployment_consensus"] == pytest.approx(4.1)
    assert los["unemployment_actual"] == pytest.approx(4.4)
    assert los["unemployment_surprise_pp"] == pytest.approx(0.3)
    assert los["unemployment_unit"] == "percentage_points"
    assert los["ahe_mom_consensus"] == pytest.approx(0.3)
    assert los["ahe_mom_actual"] == pytest.approx(0.3)
    assert los["ahe_mom_surprise_pp"] == pytest.approx(0.0)
    assert los["ahe_yoy_consensus"] == pytest.approx(3.2)
    assert los["ahe_yoy_actual"] == pytest.approx(3.8)
    assert los["ahe_yoy_surprise_pp"] == pytest.approx(0.6)
    first_ids = first["first_print_record_ids"]
    first_ts = first["retrieved_at_utc"]
    second = _recover(rec, tmp_path)
    assert second["status"] == "ALREADY_EXISTS"
    assert second["first_print_record_created"] is False
    assert second["raw_sha256"] == first["raw_sha256"]
    assert second["retrieved_at_utc"] == first_ts
    assert second["first_print_record_ids"] == first_ids
    assert all(row["result"]["status"] == "ALREADY_EXISTS" for row in second["records"])
    first_prints = [a for a in rec.load_actuals() if a["record_kind"] == "FIRST_PRINT"]
    assert len(first_prints) == 4
    nfp = next(a for a in first_prints if a["series_name"] == "nonfarm_payroll_change")
    with pytest.raises(R.RecorderConflict, match="first print cannot be overwritten"):
        rec.capture_first_print(
            macro_event_id="usd_empsit_2026-10-02",
            series_name="nonfarm_payroll_change",
            actual_first_print=1,
            artifact_bytes=b"DIFFERENT",
            first_observed_at_utc="2026-10-03T00:00:00Z",
            unit="persons",
        )
    rec.capture_revision(
        macro_event_id="usd_empsit_2026-10-02",
        series_name="nonfarm_payroll_change",
        actual_first_print=100000,
        artifact_bytes=b"REVISION",
        first_observed_at_utc="2026-11-01T12:30:00Z",
        unit="persons",
    )
    still = [a for a in rec.load_actuals() if a["record_kind"] == "FIRST_PRINT" and a["series_name"] == "nonfarm_payroll_change"]
    assert still[0]["actual_first_print"] == 119000
    assert still[0]["first_observed_at_utc"] == nfp["first_observed_at_utc"]
    raw = tmp_path / "official" / "empsit_10022026.htm"
    assert raw.exists()
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == first["raw_sha256"]
    assert S11.checkpoint_rows(rec, "T0-5m") == []
    assert rec.obs_path.read_bytes() == before


def test_no_network_budget_and_production_unchanged(tmp_path):
    rec = _rec(tmp_path)
    _seed(rec)
    before_obs = (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8")
    before_cfg = (REAL_ROOT / "config.json").read_text(encoding="utf-8")
    before_task = (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8")
    refused = S12.recover(rec=rec, official_root=tmp_path / "official", live=False)
    assert refused["status"] == "NOT_PROVEN"
    assert refused["bls_http_requests"] == 0
    src = Path("reports/decision_quality/_macro_prospective_firstprint_stage12.py").read_text(encoding="utf-8")
    assert "selenium" not in src.lower()
    assert "playwright" not in src.lower()
    assert "oanda" not in src.lower()
    assert "tradingeconomics.com" not in src.lower()
    assert "forexfactory.com" not in src.lower()
    assert "FORWARD_CONSENSUS_COLLECTION_ENABLED" in src
    for path in TRADING_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "_macro_prospective_firstprint_stage12" not in text
    production_markers = (
        Path("forex_bot/bot_loop.py"),
        Path("reports/decision_quality/_macro_prospective_scheduler.py"),
    )
    for path in production_markers:
        body = path.read_text(encoding="utf-8")
        assert "official-first-print-recover" not in body
        assert "OFFICIAL_BLS_FIRST_PRINT_ENABLED = True" not in body
    S8.assert_activation_unchanged()
    cfg = json.loads(before_cfg)
    assert cfg["FORWARD_CONSENSUS_COLLECTION_ENABLED"] is False
    assert cfg.get("OFFICIAL_BLS_FIRST_PRINT_ENABLED") is False
    assert (REAL_ROOT / "observations" / "observations.jsonl").read_text(encoding="utf-8") == before_obs
    assert (REAL_ROOT / "config.json").read_text(encoding="utf-8") == before_cfg
    assert (REAL_ROOT / "scheduler" / "windows_task_installed.json").read_text(encoding="utf-8") == before_task
    guard = S12.RequestGuard(2)
    def boom(url):
        raise AssertionError("network should not be used in this test")
    with pytest.raises(AssertionError):
        S12.official_get(S12.ARCHIVE_HTML, guard, transport=boom)
    assert guard.count == 1
    with pytest.raises(S12.RecoveryClosed, match="403"):
        S12.official_get(S12.ARCHIVE_HTML, S12.RequestGuard(10), transport=lambda url: {"url": url, "status": 403, "body": b"", "content_type": None})
    tight = S12.RequestGuard(1)
    S12.official_get(S12.ARCHIVE_HTML, tight, transport=lambda url: {"url": url, "status": 200, "body": b"x", "content_type": "text/plain"})
    with pytest.raises(S12.RecoveryClosed, match="REQUEST_GUARD"):
        S12.official_get(S12.ARCHIVE_TXT, tight, transport=lambda url: {"url": url, "status": 200, "body": b"x", "content_type": "text/plain"})
    assert S12.MAX_BLS_REQUESTS == 10
