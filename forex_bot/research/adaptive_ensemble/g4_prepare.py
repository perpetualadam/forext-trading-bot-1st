"""Build Stage G.4 local reports. Does not call a broker or score strategies."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble.g4_convert_audit import (
    arithmetic_fixtures,
    audit_frames,
)
from forex_bot.research.adaptive_ensemble.g4_gaps import PAIRS, build_gap_inventory
from forex_bot.research.adaptive_ensemble.g4_integrity import (
    G3,
    G4,
    assert_g3_intact,
    git_baseline,
    write_json,
)
from forex_bot.research.adaptive_ensemble.g4_policy import (
    evaluation_package,
    quality_policy,
)
from forex_bot.research.adaptive_ensemble.g4_sessions import build_session_report
from forex_bot.research.adaptive_ensemble.validation_runner import dry_run

CLASS_DATA = "VALIDATION_RUNNER_READY_DATA_PENDING"
CLASS_QUALITY = "VALIDATION_RUNNER_READY_QUALITY_PENDING"
CLASS_ENGINEERING = "MORE_VALIDATION_ENGINEERING_REQUIRED"
CLASS_BLOCKED = "DATA_OR_SAFETY_INTEGRITY_BLOCKED"


def _frames() -> dict[str, pd.DataFrame]:
    return {pair: pd.read_csv(G3 / "normalized" / f"{pair}_M5.csv") for pair in PAIRS}


def _times(frames: dict[str, pd.DataFrame]) -> dict[str, list[datetime]]:
    out: dict[str, list[datetime]] = {}
    for pair, frame in frames.items():
        parsed = pd.to_datetime(frame["time"], utc=True)
        out[pair] = [stamp.to_pydatetime().astimezone(timezone.utc).replace(microsecond=0) for stamp in parsed]
    return out


def _classify(sessions: dict[str, Any], audit: dict[str, Any], unresolved: int, bid_ask_ok: bool, dry: dict[str, Any]) -> str:
    if dry.get("strategy_evaluation_performed") or dry.get("evaluation_started"):
        return CLASS_ENGINEERING
    quality_bad = unresolved or audit.get("status") != "ok" or not bid_ask_ok or int(sessions.get("blocked_sessions") or 0) > 0
    if quality_bad:
        return CLASS_QUALITY
    if int(sessions.get("complete_common_sessions") or 0) < 40:
        return CLASS_DATA
    if dry.get("refused"):
        return CLASS_DATA
    return CLASS_ENGINEERING


def prepare() -> dict[str, Any]:
    intact = assert_g3_intact()
    baseline = {"git": git_baseline(), **intact, "broker_requests": 0}
    write_json(G4 / "baseline_integrity.json", baseline)
    inventory = build_gap_inventory()
    write_json(G4 / "gap_inventory.json", {key: value for key, value in inventory.items() if key != "usd_chf"})
    write_json(G4 / "usd_chf_gap_investigation.json", inventory["usd_chf"])
    frames = _frames()
    bid_ask_ok = True
    for frame in frames.values():
        bid = pd.to_numeric(frame["bid_c"], errors="coerce")
        ask = pd.to_numeric(frame["ask_c"], errors="coerce")
        if bool((bid.isna() | ask.isna() | (bid <= 0) | (ask <= 0) | (bid > ask)).any()):
            bid_ask_ok = False
    audit = audit_frames(frames)
    fixtures = arithmetic_fixtures()
    failures = {pair: set(keys) for pair, keys in audit["conversion_failures"].items()}
    grouped: dict[str, list[dict[str, Any]]] = {pair: [] for pair in PAIRS}
    for gap in inventory["gaps"]:
        grouped[str(gap["instrument"])].append(gap)
    plan_start = datetime.fromisoformat("2026-09-01T00:00:00+00:00")
    plan_end = datetime.fromisoformat("2026-10-09T07:05:00+00:00")
    sessions = build_session_report(
        request_start=plan_start,
        request_end=plan_end,
        times_by_pair=_times(frames),
        gaps_by_pair=grouped,
        conversion_failures=failures,
    )
    definition = sessions["definition"]
    policy = quality_policy(definition_hash=str(definition["integrity_hash"]))
    package = evaluation_package(
        protocol_hash=str(intact["protocol"]["actual"]),
        policy_hash=str(policy["integrity_hash"]),
        definition_hash=str(definition["integrity_hash"]),
    )
    warmup_ok = all(len(frame) >= 120 for frame in frames.values())
    dry = dry_run(
        authorised=False,
        package=package,
        policy=policy,
        complete_common_sessions=int(sessions["complete_common_sessions"]),
        conversion_status=str(audit["status"]),
        bid_ask_ok=bid_ask_ok,
        unresolved_gaps=len(inventory["unresolved"]),
        warmup_ok=warmup_ok,
        model_schema="exp_weights_v2",
    )
    classification = _classify(sessions, audit, len(inventory["unresolved"]), bid_ask_ok, dry)
    write_json(G4 / "trading_day_definition.json", definition)
    write_json(G4 / "session_coverage.json", sessions)
    write_json(G4 / "conversion_coverage_audit.json", audit)
    write_json(G4 / "conversion_fixtures.json", fixtures)
    write_json(G4 / "data_quality_policy.json", policy)
    write_json(G4 / "evaluation_package_manifest.json", package)
    write_json(G4 / "dry_run_readiness.json", dry)
    readiness = {
        "stage": "G.4",
        "classification": classification,
        "broker_requests": 0,
        "strategy_evaluation_performed": False,
        "models_retuned": False,
        "complete_common_sessions": sessions["complete_common_sessions"],
        "remaining_to_40": sessions["remaining_to_40"],
        "duration_status": sessions["duration_status"],
        "conversion_status": audit["status"],
        "unresolved_gaps": len(inventory["unresolved"]),
        "redownload_recommended": inventory["redownload_recommended"],
        "thirty_trade_gate": "NOT_YET_EVALUATED",
        "validation_started": False,
        "policy_hash": policy["integrity_hash"],
        "package_hash": package["integrity_hash"],
        "definition_hash": definition["integrity_hash"],
        "stage_g_assessment_unchanged": "EXPLORATORY_NO_CREDIBLE_EDGE",
    }
    write_json(G4 / "readiness_manifest.json", readiness)
    return readiness


if __name__ == "__main__":
    print(prepare()["classification"])
