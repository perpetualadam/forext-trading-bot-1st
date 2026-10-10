"""Stage G.4 data-quality and runner tests. No broker calls and no strategy scoring."""

from __future__ import annotations

import ast
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.research.adaptive_ensemble.conversion import FxQuote, RateTable
from forex_bot.research.adaptive_ensemble.g3_convert import convert_signed
from forex_bot.research.adaptive_ensemble.g4_convert_audit import (
    arithmetic_fixtures,
    audit_frames,
    strict_weekend,
)
from forex_bot.research.adaptive_ensemble.g4_gaps import (
    ACQUISITION_OR_PAGINATION_DEFECT,
    EXPECTED_MARKET_CLOSURE,
    NORMALISATION_DEFECT,
    SOURCE_NO_CANDLE_RETURNED,
    UNRESOLVED,
    classify_one,
)
from forex_bot.research.adaptive_ensemble.g4_integrity import (
    verify_g3_hashes,
    verify_protocol,
)
from forex_bot.research.adaptive_ensemble.g4_policy import (
    evaluation_package,
    quality_policy,
)
from forex_bot.research.adaptive_ensemble.g4_prepare import prepare
from forex_bot.research.adaptive_ensemble.g4_sessions import (
    REQUIRED_SESSIONS,
    build_session_report,
    ny_1700_utc,
    session_bounds,
    session_label,
)
from forex_bot.research.adaptive_ensemble.isolation import forbidden_hits
from forex_bot.research.adaptive_ensemble.protocol import PROTOCOL_ID, integrity_hash
from forex_bot.research.adaptive_ensemble.validation_runner import (
    TOKEN,
    EvaluationRefused,
    assert_output_allowed,
    dry_run,
    execute_market,
    exercise_synthetic,
)

ROOT = Path(__file__).resolve().parents[1]
WHEN = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
WINDOW = [(datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 8, tzinfo=timezone.utc))]


def _gap(prev: datetime, nxt: datetime, **kwargs: object) -> str:
    payload = {
        "raw_contains_interior": False,
        "norm_contains_interior": False,
        "windows": WINDOW,
        "adjacent_complete": True,
    }
    payload.update(kwargs)
    return classify_one(prev=prev, nxt=nxt, **payload)  # type: ignore[arg-type]


def _package() -> tuple[dict[str, object], dict[str, object]]:
    definition_hash = "a" * 64
    policy = quality_policy(definition_hash=definition_hash)
    package = evaluation_package(protocol_hash="b" * 64, policy_hash=str(policy["integrity_hash"]), definition_hash=definition_hash)
    return package, policy


def _gates(**overrides: object) -> dict[str, object]:
    package, policy = _package()
    payload: dict[str, object] = {
        "authorised": False,
        "package": package,
        "policy": policy,
        "complete_common_sessions": 40,
        "conversion_status": "ok",
        "bid_ask_ok": True,
        "unresolved_gaps": 0,
        "warmup_ok": True,
        "model_schema": "exp_weights_v2",
    }
    payload.update(overrides)
    return dry_run(**payload)  # type: ignore[arg-type]


def test_protocol_and_raw_hashes() -> None:
    proto = verify_protocol()
    assert proto["verified"] is True
    assert proto["protocol_id"] == PROTOCOL_ID
    hashes = verify_g3_hashes()
    assert hashes["raw_verified"] is True
    assert hashes["normalised_verified"] is True
    assert hashes["preserved_ok"] is True


def test_weekend_and_source_omission_classes() -> None:
    friday = datetime(2026, 9, 4, 20, 55, tzinfo=timezone.utc)
    sunday = datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc)
    assert _gap(friday, sunday) == EXPECTED_MARKET_CLOSURE
    short_prev = datetime(2026, 9, 7, 21, 0, tzinfo=timezone.utc)
    short_next = datetime(2026, 9, 7, 21, 15, tzinfo=timezone.utc)
    assert _gap(short_prev, short_next) == SOURCE_NO_CANDLE_RETURNED
    assert _gap(short_prev, short_next, raw_contains_interior=True) == NORMALISATION_DEFECT
    hole = [(datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 2, tzinfo=timezone.utc))]
    assert _gap(short_prev, short_next, windows=hole) == ACQUISITION_OR_PAGINATION_DEFECT
    long_next = short_prev + timedelta(hours=3)
    assert _gap(short_prev, long_next) == UNRESOLVED


def test_trading_day_dst_and_partial_boundary() -> None:
    assert ny_1700_utc(date(2026, 7, 16)) == datetime(2026, 7, 16, 21, 0, tzinfo=timezone.utc)
    assert ny_1700_utc(date(2026, 1, 15)) == datetime(2026, 1, 15, 22, 0, tzinfo=timezone.utc)
    start, end = session_bounds(date(2026, 9, 7))
    assert start == datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 9, 7, 21, 0, tzinfo=timezone.utc)
    nov_start, nov_end = session_bounds(date(2026, 11, 2))
    assert nov_start == datetime(2026, 11, 1, 22, 0, tzinfo=timezone.utc)
    assert nov_end == datetime(2026, 11, 2, 22, 0, tzinfo=timezone.utc)
    march_start, _march_end = session_bounds(date(2026, 3, 9))
    assert march_start == datetime(2026, 3, 8, 21, 0, tzinfo=timezone.utc)
    assert session_label(datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc)) == date(2026, 9, 7)
    assert session_label(datetime(2026, 9, 4, 21, 0, tzinfo=timezone.utc)) is None
    request_start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    request_end = datetime(2026, 9, 3, 21, 0, tzinfo=timezone.utc)
    times = list(pd.date_range("2026-09-01", "2026-09-03 20:55", freq="5min", tz="UTC").to_pydatetime())
    report = build_session_report(
        request_start=request_start,
        request_end=request_end,
        times_by_pair={"EUR_USD": times},
        gaps_by_pair={"EUR_USD": []},
        conversion_failures={"EUR_USD": set()},
    )
    assert REQUIRED_SESSIONS == 40
    assert report["threshold_reduced"] is False
    assert report["complete_common_sessions"] < 40
    statuses = {row["session"]: row["status"] for row in report["common"]}
    assert statuses["2026-09-01"] == "PARTIAL_BOUNDARY"
    assert statuses["2026-09-03"] == "COMPLETE"


def test_unresolved_gap_blocks_session() -> None:
    request_start = datetime(2026, 9, 2, 21, 0, tzinfo=timezone.utc)
    request_end = datetime(2026, 9, 4, 21, 0, tzinfo=timezone.utc)
    times = list(pd.date_range("2026-09-02 21:00", "2026-09-04 20:55", freq="5min", tz="UTC").to_pydatetime())
    gap = {
        "classification": UNRESOLVED,
        "previous": "2026-09-03T12:00:00+00:00",
        "next": "2026-09-03T15:00:00+00:00",
    }
    blocked = build_session_report(
        request_start=request_start,
        request_end=request_end,
        times_by_pair={"EUR_USD": times},
        gaps_by_pair={"EUR_USD": [gap]},
        conversion_failures={"EUR_USD": set()},
    )
    assert any(row["status"] == "DATA_QUALITY_BLOCKED" for row in blocked["common"])
    clean = build_session_report(
        request_start=request_start,
        request_end=request_end,
        times_by_pair={"EUR_USD": times},
        gaps_by_pair={"EUR_USD": []},
        conversion_failures={"EUR_USD": {"2026-09-03"}},
    )
    assert any(row["reason"] == "conversion" for row in clean["per_pair"]["EUR_USD"])


def test_conversion_fixtures_and_full_rules() -> None:
    fixtures = arithmetic_fixtures()
    assert fixtures["passed"] is True
    assert fixtures["strategy_pnl"] is False
    table = RateTable([FxQuote(WHEN, "GBP_USD", 1.30, 1.31, "fixture"), FxQuote(WHEN, "USD_JPY", 150.0, 150.2, "fixture")])
    pos = convert_signed(pnl_quote=100.0, pair="USD_JPY", when=WHEN, table=table)
    neg = convert_signed(pnl_quote=-100.0, pair="USD_JPY", when=WHEN, table=table)
    assert pos.path[1].endswith("ask")
    assert neg.path[1].endswith("bid")
    assert pos.gbp is not None and neg.gbp is not None
    assert abs(neg.gbp) > abs(pos.gbp)
    future = RateTable([FxQuote(WHEN + timedelta(hours=1), "GBP_USD", 1.30, 1.31, "fixture")])
    missing = convert_signed(pnl_quote=1.0, pair="EUR_USD", when=WHEN, table=future)
    assert missing.status == "GBP_CONVERSION_UNVERIFIED"
    stale_when = datetime(2026, 9, 3, 18, 0, tzinfo=timezone.utc)
    stale_table = RateTable([FxQuote(stale_when - timedelta(hours=30), "GBP_USD", 1.30, 1.31, "fixture")])
    stale = convert_signed(pnl_quote=1.0, pair="EUR_USD", when=stale_when, table=stale_table)
    assert stale.status == "CONVERSION_STALE"
    friday = datetime(2026, 9, 4, 20, 0, tzinfo=timezone.utc)
    sunday = datetime(2026, 9, 6, 22, 0, tzinfo=timezone.utc)
    assert strict_weekend(friday, sunday) is True
    monday_afternoon = datetime(2026, 9, 7, 15, 0, tzinfo=timezone.utc)
    assert strict_weekend(friday, monday_afternoon) is False
    empty = RateTable()
    assert convert_signed(pnl_quote=1.0, pair="USD_CAD", when=WHEN, table=empty).status == "GBP_CONVERSION_UNVERIFIED"
    assert convert_signed(pnl_quote=-1.0, pair="USD_CHF", when=WHEN, table=empty).reason == "missing_USD_CHF"


def test_audit_tiny_frame_is_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "time": ["2026-09-02T12:00:00Z", "2026-09-02T12:05:00Z"],
            "bid_c": [1.10, 1.11],
            "ask_c": [1.11, 1.12],
        }
    )
    frames = {pair: frame.copy() for pair in ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")}
    frames["USD_JPY"] = pd.DataFrame({"time": frame["time"], "bid_c": [150.0, 150.1], "ask_c": [150.2, 150.3]})
    frames["USD_CAD"] = pd.DataFrame({"time": frame["time"], "bid_c": [1.35, 1.36], "ask_c": [1.36, 1.37]})
    frames["USD_CHF"] = pd.DataFrame({"time": frame["time"], "bid_c": [0.80, 0.81], "ask_c": [0.81, 0.82]})
    first = audit_frames(frames)
    second = audit_frames(frames)
    assert first["digest_sha256"] == second["digest_sha256"]
    assert first["timestamps_audited"] == 12
    assert first["full_portfolio_pnl_reconciliation"] is False
    assert first["status"] == "ok"


def test_runner_refuses_each_gate(tmp_path: Path) -> None:
    refused = _gates()
    assert refused["reasons"] == ["AUTHORISATION_REQUIRED"]
    assert refused["strategy_evaluation_performed"] is False
    assert refused["net_pnl_gbp"] is None
    assert "INSUFFICIENT_INDEPENDENT_DURATION" in _gates(complete_common_sessions=29)["reasons"]
    package, policy = _package()
    broken = dict(package)
    broken["integrity_hash"] = "0" * 64
    assert "INVALID_MANIFEST" in _gates(package=broken)["reasons"]
    assert "MODEL_STATE_INVALID" in _gates(model_schema="exp_weights_v1")["reasons"]
    assert "MISSING_CONVERSION" in _gates(conversion_status="GBP_CONVERSION_UNVERIFIED")["reasons"]
    assert "MISSING_BID_ASK" in _gates(bid_ask_ok=False)["reasons"]
    assert "UNRESOLVED_GAPS" in _gates(unresolved_gaps=2)["reasons"]
    assert "INSUFFICIENT_WARMUP" in _gates(warmup_ok=False)["reasons"]
    with pytest.raises(EvaluationRefused):
        assert_output_allowed(ROOT / "data" / "research" / "adaptive_ensemble" / "g3" / "out.json")
    with pytest.raises(EvaluationRefused):
        dry_run(package=package, policy=policy, complete_common_sessions=40, conversion_status="ok", bid_ask_ok=True, unresolved_gaps=0, warmup_ok=True, model_schema="exp_weights_v2", market_frames={"EUR_USD": []})
    with pytest.raises(EvaluationRefused):
        execute_market()
    allowed = tmp_path / "scratch"
    dry_run(
        package=package,
        policy=policy,
        complete_common_sessions=10,
        conversion_status="ok",
        bid_ask_ok=True,
        unresolved_gaps=0,
        warmup_ok=True,
        model_schema="exp_weights_v2",
        output_dir=allowed,
    )
    assert integrity_hash(policy) == policy["integrity_hash"]


def test_synthetic_exercise_is_reproducible_and_not_pnl() -> None:
    with pytest.raises(EvaluationRefused):
        exercise_synthetic("nope")
    first = exercise_synthetic(TOKEN)
    second = exercise_synthetic(TOKEN)
    assert first == second
    assert first["strategy_performance_evidence"] is False
    assert first["net_pnl_gbp"] is None
    assert first["market_data_used"] is False
    assert first["missing_ask"] == "missing_ask"
    assert first["gap_exit_reason"] == "gap_stop_executable_open"


def test_new_modules_have_no_network_or_broker_imports() -> None:
    banned = {"urllib", "urllib.request", "socket", "requests", "sqlite3", "docker"}
    root = ROOT / "forex_bot" / "research" / "adaptive_ensemble"
    names = [
        "g4_integrity.py",
        "g4_gaps.py",
        "g4_sessions.py",
        "g4_convert_audit.py",
        "g4_policy.py",
        "g4_prepare.py",
        "validation_runner.py",
    ]
    for name in names:
        text = (root / name).read_text(encoding="utf-8")
        assert "OANDA-" not in text
        assert "Bearer " not in text
        tree = ast.parse(text)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert imported.isdisjoint(banned)
    assert forbidden_hits() == {}


def test_stage_g4_prepare_refuses_evaluation() -> None:
    readiness = prepare()
    assert readiness["strategy_evaluation_performed"] is False
    assert readiness["validation_started"] is False
    assert readiness["broker_requests"] == 0
    assert readiness["thirty_trade_gate"] == "NOT_YET_EVALUATED"
    assert readiness["models_retuned"] is False
    assert int(readiness["complete_common_sessions"]) < 40
    assert readiness["classification"] in {
        "VALIDATION_RUNNER_READY_DATA_PENDING",
        "VALIDATION_RUNNER_READY_QUALITY_PENDING",
    }
    assess = json.loads((ROOT / "data" / "research" / "adaptive_ensemble" / "assessment.json").read_text(encoding="utf-8"))
    assert assess["assessment"] == "EXPLORATORY_NO_CREDIBLE_EDGE"
    dry = json.loads((ROOT / "data" / "research" / "adaptive_ensemble" / "g4" / "dry_run_readiness.json").read_text(encoding="utf-8"))
    assert dry["evaluation_started"] is False
    assert dry["net_pnl_gbp"] is None
    assert "AUTHORISATION_REQUIRED" in dry["reasons"]
    inventory = json.loads((ROOT / "data" / "research" / "adaptive_ensemble" / "g4" / "gap_inventory.json").read_text(encoding="utf-8"))
    assert inventory["redownload_recommended"] is False
    assert inventory["unresolved"] == []
    chf = json.loads((ROOT / "data" / "research" / "adaptive_ensemble" / "g4" / "usd_chf_gap_investigation.json").read_text(encoding="utf-8"))
    assert chf["non_weekend_gaps"] == 17
    assert chf["classifications"] == ["SOURCE_NO_CANDLE_RETURNED"]
    audit = json.loads((ROOT / "data" / "research" / "adaptive_ensemble" / "g4" / "conversion_coverage_audit.json").read_text(encoding="utf-8"))
    assert audit["full_portfolio_pnl_reconciliation"] is False
    assert audit["timestamps_audited"] == 48853
