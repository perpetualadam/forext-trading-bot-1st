"""Stage F.2: order-independent risk, exposure, rotation, close audit.

Broker-disconnected. Temporary stores only. No live authorisation.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.decision_repair import (
    AUDIT_SCHEMA_VERSION,
    POLICY_VERSION,
    RISK_SCHEMA_VERSION,
)
from forex_bot.decision_repair.account_risk import (
    INTEGRITY_INCONSISTENT,
    REASON_CONFLICT,
    REASON_DAILY_REALISED,
    REASON_EVENT_TIME,
    block_reason,
    observe,
    operator_clear_latch,
    reconstruct_day_realised,
)
from forex_bot.decision_repair.audit import EvaluationAudit, empty_record
from forex_bot.decision_repair.exposure import (
    REASON_CAP,
    REASON_POSITION_STALE,
    REASON_RECONCILE,
    REASON_RESERVATION,
    REASON_SNAPSHOT_MISSING,
    REASON_UNKNOWN_ORDER,
    classify_order,
    clear_reservations_for_tests,
    release_local,
    reserve_local,
    snapshot_from_broker_view,
)
from forex_bot.decision_repair.harness import SCENARIOS, load_jsonl
from forex_bot.decision_repair.selection import (
    ALL_NAMES,
    next_eligible,
    select_deterministic,
)
from forex_bot.execution import pre_trade_entry_blocked_reason
from forex_bot.live_safety import (
    AUTH_BLOCKED,
    initialise_fail_closed,
    live_order_auth_state,
)
from forex_bot.positions import Position
from forex_bot.strategy_meta import strategies

_FLAG_KEYS = (
    "DECISION_REPAIR_DETERMINISTIC_SELECT",
    "DECISION_REPAIR_RL_PERSIST",
    "DECISION_REPAIR_RL_REQUIRE_STATE",
    "DECISION_REPAIR_AUDIT",
    "DECISION_REPAIR_HEALTH",
    "DECISION_REPAIR_ACCOUNT_RISK",
)


@pytest.fixture(autouse=True)
def _clear_repair_flags(monkeypatch):
    for key in _FLAG_KEYS:
        monkeypatch.delenv(key, raising=False)
    clear_reservations_for_tests()


def _atr_df(n: int = 20, last: float = 0.002, med: float = 0.001) -> pd.DataFrame:
    atr = [med] * (n - 1) + [last]
    return pd.DataFrame(
        {
            "time": [datetime(2026, 6, 1, tzinfo=timezone.utc)] * n,
            "open": [1.1] * n,
            "high": [1.11] * n,
            "low": [1.09] * n,
            "close": [1.1] * n,
            "atr": atr,
        }
    )


def spec_day_realised(rows: list[dict], day: str) -> float:
    """Independent spec: unique event ids, sum deltas on that UTC calendar day."""
    unique: dict[str, float] = {}
    for row in rows:
        unique[row["event_id"]] = float(row["delta"])
    return sum(
        unique[row["event_id"]]
        for row in rows
        if row["day"] == day and unique.get(row["event_id"]) == float(row["delta"])
    )


LEDGER = [
    {"event_id": "e1", "time": "2026-06-01T10:00:00+00:00", "seq": 1, "delta": -1.0, "day": "2026-06-01"},
    {"event_id": "e2", "time": "2026-06-01T11:00:00+00:00", "seq": 2, "delta": -1.5, "day": "2026-06-01"},
    {"event_id": "e3", "time": "2026-06-01T12:00:00+00:00", "seq": 3, "delta": 0.5, "day": "2026-06-01"},
    {"event_id": "e4", "time": "2026-06-02T00:01:00+00:00", "seq": 4, "delta": -0.4, "day": "2026-06-02"},
]


def _ingest(path: Path, rows: list[dict], equity: float = 100.0) -> None:
    for row in rows:
        observe(
            event_id=row["event_id"],
            realised_delta=row["delta"],
            equity=equity,
            broker_time_utc=row["time"],
            broker_seq=row["seq"],
            path=path,
        )


def test_schema_and_policy_versions():
    assert RISK_SCHEMA_VERSION == 2
    assert AUDIT_SCHEMA_VERSION == 3
    assert POLICY_VERSION == "deterministic_rotate_v2_unvalidated"
    rec = empty_record(symbol="EUR_USD")
    assert rec["close_outcome"] == "NOT_EVALUATED"


def test_risk_ledger_order_independent_matches_spec(tmp_path):
    expected = spec_day_realised(LEDGER, "2026-06-01")
    assert expected == pytest.approx(-2.0)
    expected_d2 = spec_day_realised(LEDGER, "2026-06-02")
    assert expected_d2 == pytest.approx(-0.4)
    orders = [list(LEDGER), list(reversed(LEDGER)), list(LEDGER)]
    rng = random.Random(7)
    shuffled = list(LEDGER)
    rng.shuffle(shuffled)
    orders.append(shuffled)
    for batch in orders:
        path = tmp_path / f"{id(batch)}.json"
        _ingest(path, batch)
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert reconstruct_day_realised(doc["events"], "2026-06-01") == pytest.approx(expected)
        assert reconstruct_day_realised(doc["events"], "2026-06-02") == pytest.approx(expected_d2)
        assert [row["event_id"] for row in doc["events"]] == ["e1", "e2", "e3", "e4"]


def test_risk_duplicate_and_conflict_and_missing_time(tmp_path):
    path = tmp_path / "dup.json"
    _ingest(path, LEDGER[:1])
    _ingest(path, LEDGER[:1])
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert len(doc["events"]) == 1
    observe(
        event_id="e1",
        realised_delta=-9.0,
        equity=100.0,
        broker_time_utc="2026-06-01T10:00:00+00:00",
        broker_seq=1,
        path=path,
    )
    conflicted = json.loads(path.read_text(encoding="utf-8"))
    assert conflicted["integrity"] == INTEGRITY_INCONSISTENT
    assert conflicted["latch_reason"] == REASON_CONFLICT
    path2 = tmp_path / "notime.json"
    observe(event_id="x", realised_delta=-1.0, equity=100.0, path=path2)
    missing = json.loads(path2.read_text(encoding="utf-8"))
    assert missing["latch_reason"] == REASON_EVENT_TIME
    assert block_reason(equity=100.0, path=path2) == REASON_EVENT_TIME


def test_late_loss_does_not_clear_latch(tmp_path):
    path = tmp_path / "late.json"
    _ingest(path, [LEDGER[0], LEDGER[1]])
    assert reconstruct_day_realised(json.loads(path.read_text(encoding="utf-8"))["events"], "2026-06-01") == pytest.approx(-2.5)
    assert block_reason(equity=97.0, path=path) == REASON_DAILY_REALISED
    observe(
        event_id="gain",
        realised_delta=10.0,
        equity=110.0,
        broker_time_utc="2026-06-01T09:00:00+00:00",
        broker_seq=0,
        path=path,
    )
    assert block_reason(equity=110.0, path=path) == REASON_DAILY_REALISED


def test_risk_restart_and_corrupt(tmp_path):
    path = tmp_path / "rst.json"
    _ingest(path, LEDGER[:2], equity=100.0)
    assert block_reason(equity=97.0, path=path) == REASON_DAILY_REALISED
    again = block_reason(equity=97.0, path=path)
    assert again == REASON_DAILY_REALISED
    path.write_text("{not-json", encoding="utf-8")
    assert block_reason(equity=100.0, path=path) == "corrupt_risk_state"
    operator_clear_latch(operator_confirmed=True, path=tmp_path / "fresh.json")
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED


def test_exposure_positions_pending_and_protective(tmp_path):
    empty = snapshot_from_broker_view(
        nav=10_000,
        positions=[],
        pending_orders=[],
        reconcile_status="ok",
    )
    assert empty.ready is True
    assert empty.open_position_count == 0
    one = snapshot_from_broker_view(
        nav=10_000,
        positions=[{"id": "t1", "symbol": "EUR_USD", "units": 2, "notional": 200, "direction": "BUY"}],
        pending_orders=[
            {"id": "sl", "type": "STOP_LOSS", "status": "PENDING"},
            {"id": "tp", "type": "TAKE_PROFIT", "status": "PENDING"},
        ],
        reconcile_status="ok",
    )
    assert one.open_position_count == 1
    assert one.protective_order_count == 2
    assert one.pending_entry_count == 0
    assert one.committed_exposure == pytest.approx(200)
    pending = snapshot_from_broker_view(
        nav=10_000,
        positions=[{"id": "t1", "symbol": "EUR_USD", "units": 2, "notional": 200, "usd_direction": "LONG_USD"}],
        pending_orders=[{"id": "p1", "type": "LIMIT", "status": "PENDING", "units": 3, "notional": 300}],
        reconcile_status="ok",
        proposed_notional=100,
        max_committed=550,
    )
    assert pending.pending_entry_count == 1
    assert pending.block_reason == REASON_CAP
    unknown = snapshot_from_broker_view(
        nav=10_000,
        positions=[],
        pending_orders=[{"id": "u1", "type": "WEIRD", "status": "PENDING", "units": 1}],
        reconcile_status="ok",
    )
    assert unknown.block_reason == REASON_UNKNOWN_ORDER
    stale = snapshot_from_broker_view(nav=10_000, positions=[], pending_orders=[], stale=True)
    assert stale.block_reason == REASON_POSITION_STALE
    reco = snapshot_from_broker_view(nav=10_000, positions=[], pending_orders=[], reconcile_status="mismatch")
    assert reco.block_reason == REASON_RECONCILE
    missing = snapshot_from_broker_view(nav=10_000, positions=None, pending_orders=None)
    assert missing.block_reason == REASON_SNAPSHOT_MISSING


def test_partial_cancel_and_local_reservation():
    assert classify_order({"type": "STOP_LOSS"}) == "protective"
    assert classify_order({"type": "LIMIT", "status": "CANCELLED"}) == "cancelled"
    partial = snapshot_from_broker_view(
        nav=5000,
        positions=[],
        pending_orders=[{"id": "p", "type": "MARKET", "status": "PARTIALLY_FILLED", "units": 5, "filledUnits": 2, "notional": 3}],
        reconcile_status="ok",
    )
    assert partial.pending_entry_count == 1
    assert partial.reserved_notional == pytest.approx(3)
    assert reserve_local("EUR_USD", 10.0) is True
    assert reserve_local("EUR_USD", 10.0) is False
    release_local("EUR_USD")
    assert reserve_local("EUR_USD", 10.0) is True
    _ = REASON_RESERVATION


def test_selector_rotation_fairness_and_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("HYBRID_EUR_USD", raising=False)
    path = tmp_path / "cursor.json"
    active = {n: False for n in ALL_NAMES}
    active["trend"] = True
    active["scalp"] = True
    a = select_deterministic("EUR_USD", _atr_df(), active_override=active, persist=True, store_path=path)
    b = select_deterministic("EUR_USD", _atr_df(), active_override=active, persist=True, store_path=path)
    c = select_deterministic("EUR_USD", _atr_df(), active_override=active, persist=True, store_path=path)
    assert {a.selected, b.selected} == {"scalp", "trend"}
    assert a.selected != b.selected
    assert c.selected == a.selected
    gbp = select_deterministic("GBP_USD", _atr_df(), active_override=active, persist=True, store_path=path)
    assert gbp.selected == "scalp"
    peek = select_deterministic("EUR_USD", _atr_df(), active_override=active, persist=False, store_path=path)
    peek2 = select_deterministic("EUR_USD", _atr_df(), active_override=active, persist=False, store_path=path)
    assert peek.selected == peek2.selected
    assert next_eligible(["scalp", "trend"], "scalp") == "trend"
    path.write_text("{bad", encoding="utf-8")
    bad = select_deterministic("EUR_USD", _atr_df(), active_override=active, persist=True, store_path=path)
    assert bad.selected is None
    assert bad.reason == "SELECTOR_STATE_INVALID"


def test_selector_does_not_grant_auth_or_activate(monkeypatch, tmp_path):
    monkeypatch.setenv("DECISION_REPAIR_DETERMINISTIC_SELECT", "1")
    initialise_fail_closed()
    for strat in strategies.values():
        strat.active = False
    from forex_bot.strategy_meta import select_strategy

    name, _lb, _h = select_strategy("EUR_USD", _atr_df())
    assert name is None
    assert live_order_auth_state() == AUTH_BLOCKED
    assert all(s.active is False for s in strategies.values())


def test_close_audit_requires_evidence_and_never_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("DECISION_REPAIR_AUDIT", "1")
    dest = tmp_path / "decisions.jsonl"
    monkeypatch.setenv("DECISION_REPAIR_AUDIT_PATH", str(dest))
    session = EvaluationAudit.start("EUR_USD")
    session.note_close(outcome="CLOSE_INTENT", trigger="sl_tp")
    session.note_close(outcome="CLOSE_SUBMISSION_ATTEMPTED", trigger="sl_tp")
    session.note_close(outcome="CLOSE_EXECUTED", trigger="sl_tp", evidence="NOT_EVALUATED")
    session.finish()
    rows = load_jsonl(dest)
    assert rows
    last = rows[-1]
    assert last["close_outcome"] == "CLOSE_STATUS_UNKNOWN"
    session2 = EvaluationAudit.start("EUR_USD")
    session2.note_close(outcome="CLOSE_EXECUTED", trigger="profit_protection", evidence="local_fill")
    session2.finish()
    executed = [row for row in load_jsonl(dest) if row.get("close_outcome") == "CLOSE_EXECUTED"]
    assert executed
    assert executed[-1]["close_evidence"] == "local_fill"
    monkeypatch.setattr(
        "forex_bot.decision_repair.audit.append_record",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
    )
    session3 = EvaluationAudit.start("EUR_USD")
    session3.note_close(outcome="CLOSE_FAILED", trigger="sl_tp", evidence="execute_trade_exception")
    session3.finish()
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED


def test_evaluate_close_records_executed_and_survives_audit_failure(monkeypatch, tmp_path):
    from forex_bot.bot_loop import evaluate

    dest = tmp_path / "decisions.jsonl"
    monkeypatch.setenv("DECISION_REPAIR_AUDIT", "1")
    monkeypatch.setenv("DECISION_REPAIR_AUDIT_PATH", str(dest))
    idx = pd.date_range("2026-10-01", periods=20, freq="5min", tz="UTC")
    close = pd.Series([1.10] * 20, index=idx)
    raw = pd.DataFrame(
        {"time": idx, "open": close, "high": close + 0.0002, "low": close - 0.0002, "close": close, "volume": 1.0}
    )
    pos = Position(
        symbol="EUR_USD",
        direction="BUY",
        units=1.0,
        entry_price=1.12,
        stop_loss=1.11,
        take_profit=1.20,
        open_time=time.time() - 10_000,
        strategy_name="trend",
        rl_state="s",
        execution_kind="simulated",
    )
    closed: list[str] = []
    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", lambda *_a, **_k: raw)
    monkeypatch.setattr("forex_bot.bot_loop.get_position", lambda *_a, **_k: pos)
    monkeypatch.setattr("forex_bot.bot_loop.flatten_for_weekend", lambda: False)
    monkeypatch.setattr("forex_bot.bot_loop.in_active_session", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.bot_loop.close_fill_path", lambda *_a, **_k: "simulate")
    monkeypatch.setattr("forex_bot.bot_loop._min_position_hold_sec", lambda: 0)
    monkeypatch.setattr("forex_bot.bot_loop.apply_latency", lambda: asyncio.sleep(0))
    monkeypatch.setattr("forex_bot.bot_loop.apply_market_impact", lambda *_a, **_k: (1.10, 0.0))
    monkeypatch.setattr("forex_bot.bot_loop.apply_execution_costs", lambda *_a, **_k: (1.10, 0.0, 0.0))
    monkeypatch.setattr("forex_bot.bot_loop.calculate_pnl", lambda *_a, **_k: -1.0)

    async def _exec(*_a, **_k):
        return -1.0

    monkeypatch.setattr("forex_bot.bot_loop.execute_trade", _exec)
    monkeypatch.setattr("forex_bot.bot_loop.close_position", lambda symbol: closed.append(symbol))
    monkeypatch.setattr("forex_bot.bot_loop.rl_agent.update", lambda *_a, **_k: None)
    asyncio.run(evaluate("EUR_USD"))
    assert closed == ["EUR_USD"]
    rows = load_jsonl(dest)
    assert any(row.get("close_outcome") == "CLOSE_EXECUTED" for row in rows)
    closed.clear()
    dest.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "forex_bot.decision_repair.audit.append_record",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
    )
    asyncio.run(evaluate("EUR_USD"))
    assert closed == ["EUR_USD"]


def test_account_risk_and_exposure_do_not_authorise(monkeypatch):
    initialise_fail_closed()
    monkeypatch.setenv("DECISION_REPAIR_ACCOUNT_RISK", "1")
    from forex_bot.state import state as app_state

    app_state["broker_nav"] = 10_000
    app_state["broker_unrealised_pl"] = 0.0
    app_state["broker_positions"] = []
    app_state["broker_pending_orders"] = []
    app_state["broker_reconcile_status"] = "ok"
    assert pre_trade_entry_blocked_reason() == "live_order_auth_blocked"
    assert live_order_auth_state() == AUTH_BLOCKED


def test_harness_includes_f2_scenarios():
    assert "shuffled_risk_events" in SCENARIOS
    assert "audit_fail_close_allowed" in SCENARIOS
    assert "selector_rotation_restart" in SCENARIOS
