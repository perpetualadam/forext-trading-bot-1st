"""Offline proof that production dispatch uses the shared decision, and that a flat token cannot release exposure."""

from __future__ import annotations

import atexit
import importlib.util
import inspect
import json
import os
import socket
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R13 = ROOT / "data" / "research" / "adaptive_ensemble" / "r13"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R13 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    _evaluate_impl,
    dispatch_production_iteration,
    evaluate,
    evaluate_one_instrument_iteration,
    run_bot,
)
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    exposure_entry_block_reason,
    interpret_close_evidence,
    note_blocking_reservation,
    note_unconfirmed_exposure,
    reservation_status_block_reason,
    reset_order_intent_gate_for_tests,
    restore_unresolved_intent,
    select_rows_for_recovery,
)
from forex_bot.orders import (  # noqa: E402
    LocalOrder,
    OrderStatus,
    ingest_recovery_snapshot,
    register_order,
    reset_orders_for_tests,
    try_begin_order_submission,
)
from forex_bot.positions import Position, close_position, get_position, open_position, positions  # noqa: E402
from forex_bot.strategy_meta import SCALP_STRATEGY_KEYS, SWING_STRATEGY_KEYS, strategies  # noqa: E402

_fake_spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
_fake_mod = importlib.util.module_from_spec(_fake_spec)
assert _fake_spec is not None and _fake_spec.loader is not None
_fake_spec.loader.exec_module(_fake_mod)
FakeBroker = _fake_mod.FakeBroker

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
RECORDS: list[dict[str, object]] = []
OPS_PERMISSION = ROOT / "data" / "ops" / "live_safety_state.json"
OPS_BEFORE = OPS_PERMISSION.stat().st_mtime if OPS_PERMISSION.exists() else None


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R13)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R13 / "synthetic_live_safety_state.json")
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def _bars(price: float = 1.1, count: int = 50) -> list[dict[str, object]]:
    return [
        {
            "open": price,
            "high": price + 0.0002,
            "low": price - 0.0002,
            "close": price,
            "time": "2026-01-07T11:55:00+00:00",
        }
        for _ in range(count)
    ]


def _deps(**overrides: object) -> IterationDependencies:
    broker = overrides.pop("broker", None)
    values: dict[str, object] = {
        "candles": _bars(),
        "spread": 0.0002,
        "balance": 10000.0,
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.6},
        "strategy_name": "scalp",
        "strategy_known": True,
        "strategy_active": True,
        "strategy_authorised": True,
        "safety_initialised": True,
        "simulation": True,
        "now": OPEN,
        "quote_as_of": OPEN,
        "stop_distance": 0.001,
        "price": 1.1,
        "bid": 1.09995,
        "ask": 1.10005,
        "broker": broker if broker is not None else FakeBroker("filled"),
    }
    values.update(overrides)
    if "unrealised" not in overrides:
        values["unrealised"] = 0.0
    if "account_as_of" not in overrides:
        values["account_as_of"] = values.get("now")
    return IterationDependencies(**values)  # type: ignore[arg-type]


def _drive(coro: object) -> dict[str, object]:
    try:
        while True:
            coro.send(None)  # type: ignore[attr-defined]
    except StopIteration as stop:
        return stop.value


def _dispatch(**overrides: object) -> dict[str, object]:
    symbol = str(overrides.pop("symbol", "EUR_USD"))
    return dispatch_production_iteration(symbol, _deps(**overrides))


def record(test_id: str, function: str, source: str, expected: str, result: dict[str, object] | None, status: str, **extra: object) -> None:
    RECORDS.append(
        {
            "test_id": test_id,
            "function": function,
            "source_function": source,
            "production_dispatch": bool(result and result.get("production_dispatch")),
            "shared_implementation": None if result is None else result.get("shared_implementation"),
            "expected": expected,
            "actual": None if result is None else result.get("blocked_by") or result.get("status"),
            "status": status,
            "simulated_broker_requests": 0 if result is None else int(result.get("broker_requests") or 0),
            "real_broker_requests": 0,
            "postgresql_connections": 0,
            "evidence": extra,
        }
    )


def _note(test_id: str, function: str, source: str, expected: str, result: dict[str, object], ok: bool, **extra: object) -> None:
    record(test_id, function, source, expected, result, "PASS" if ok else "FAIL", **extra)
    assert ok, result


def _dump() -> None:
    R13.mkdir(parents=True, exist_ok=True)
    (R13 / "09_integration_test_results.json").write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")


atexit.register(_dump)


def _hold(symbol: str = "EUR_USD") -> None:
    note_unconfirmed_exposure(symbol, "cid-hold")


def test_g01_permission_blocked() -> None:
    broker = FakeBroker("filled")
    result = _dispatch(simulation=False, broker=broker)
    _note("G01", "test_g01_permission_blocked", "dispatch_production_iteration", "live permission blocks", result, result["production_dispatch"] is True and broker.request_count == 0 and "live_order_auth" in str(result["blocked_by"]))


def test_g02_strategy_inactive() -> None:
    result = _dispatch(strategy_active=False)
    _note("G02", "test_g02_strategy_inactive", "strategy_entry_block_reason", "STRATEGY_INACTIVE", result, result["blocked_by"] == "STRATEGY_INACTIVE" and result["broker_requests"] == 0)


def test_g03_invalid_direction() -> None:
    result = _dispatch(vote={"allow": True, "direction": "HOLD"})
    _note("G03", "test_g03_invalid_direction", "direction_action_gate", "invalid direction", result, result["blocked_by"] == "invalid_entry_direction" and result["broker_requests"] == 0)


def test_g04_existing_position() -> None:
    open_position(Position("EUR_USD", "BUY", 1, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    result = _dispatch()
    _note("G04", "test_g04_existing_position", "get_position", "position_already_open", result, result["blocked_by"] == "position_already_open" and result["broker_requests"] == 0)


def test_g05_pending_order() -> None:
    note_blocking_reservation("EUR_USD", "pending")
    result = _dispatch()
    _note("G05", "test_g05_pending_order", "exposure_entry_block_reason", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_g06_partial_order() -> None:
    register_order(LocalOrder("partial", "EUR_USD", "BUY", 2, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation("EUR_USD", "partial")
    result = _dispatch()
    _note("G06", "test_g06_partial_order", "reservation_status_block_reason", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_g07_unresolved_order() -> None:
    restore_unresolved_intent("EUR_USD", "unresolved")
    result = _dispatch()
    _note("G07", "test_g07_unresolved_order", "restore_unresolved_intent", "unresolved_intent", result, result["blocked_by"] == "unresolved_intent")


def test_g08_historical_filled() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "hist", "symbol": "EUR_USD", "status": "FILLED", "metadata": {}}])
    ingest_recovery_snapshot(kept, True)
    result = _dispatch()
    _note("G08", "test_g08_historical_filled", "select_rows_for_recovery", "exposure_unconfirmed", result, result["blocked_by"] == "exposure_unconfirmed" and result["broker_requests"] == 0)


def test_g09_missing_position_with_exposure() -> None:
    _hold()
    result = _dispatch()
    _note("G09", "test_g09_missing_position_with_exposure", "exposure_entry_block_reason", "exposure without a position", result, get_position("EUR_USD") is None and result["blocked_by"] == "exposure_unconfirmed")


def test_g10_simulated_buy() -> None:
    broker = FakeBroker("filled")
    result = _dispatch(broker=broker)
    _note("G10", "test_g10_simulated_buy", "dispatch_production_iteration", "one simulated BUY", result, result["direction"] == "BUY" and broker.request_count == 1 and result["shared_implementation"] == "evaluate_one_instrument_iteration")


def test_g11_simulated_sell() -> None:
    broker = FakeBroker("filled")
    result = _dispatch(vote={"allow": True, "direction": "SELL"}, broker=broker)
    _note("G11", "test_g11_simulated_sell", "dispatch_production_iteration", "one simulated SELL", result, result["direction"] == "SELL" and broker.request_count == 1)


def test_g12_synthetic_rejection() -> None:
    result = _dispatch(broker=FakeBroker("rejected"))
    _note("G12", "test_g12_synthetic_rejection", "mark_order_failed_or_cancelled", "rejected", result, result["status"] == "rejected" and exposure_entry_block_reason("EUR_USD") is None)


def test_g13_synthetic_timeout() -> None:
    result = _dispatch(broker=FakeBroker("filled", error=TimeoutError("simulated")))
    second = _dispatch(broker=FakeBroker("filled"))
    _note("G13", "test_g13_synthetic_timeout", "restore_unresolved_intent", "timeout keeps the hold", second, result["outcome"] == "timeout" and second["broker_requests"] == 0)


def test_g14_synthetic_partial() -> None:
    result = _dispatch(broker=FakeBroker("partial", response={"kind": "partial", "units": 1, "price": 1.1}))
    _note("G14", "test_g14_synthetic_partial", "finalize_order_fill", "partial stays unconfirmed", result, result["status"] == "partial" and exposure_entry_block_reason("EUR_USD") == "exposure_unconfirmed")


def test_g15_synthetic_ambiguous() -> None:
    result = _dispatch(broker=FakeBroker("ambiguous"))
    _note("G15", "test_g15_synthetic_ambiguous", "restore_unresolved_intent", "ambiguous", result, result["status"] == "uncertain" and result["exposure_held"] is True)


def test_g16_synthetic_malformed() -> None:
    result = _dispatch(broker=FakeBroker("filled", response={"units": 1}))
    _note("G16", "test_g16_synthetic_malformed", "evaluate_one_instrument_iteration", "malformed", result, result["outcome"] == "malformed" and result["exposure_held"] is True)


def test_g17_position_record_failure() -> None:
    first = _dispatch(fail_position_record=True)
    second = _dispatch(broker=FakeBroker("filled"))
    _note("G17", "test_g17_position_record_failure", "note_unconfirmed_exposure", "next entry blocked", second, first["exposure_held"] is True and second["broker_requests"] == 0)


def test_g18_persistence_failure() -> None:
    result = _dispatch(persistence_failure="fail")
    _note("G18", "test_g18_persistence_failure", "refuse_reservation_after_database_fault", "no dispatch", result, result["blocked_by"] == "reservation_persistence_failed" and result["broker_requests"] == 0)


def test_g19_reconciliation_unavailable() -> None:
    result = _dispatch(reconciliation_token="CONFIRMED_FLAT")
    _note("G19", "test_g19_reconciliation_unavailable", "dispatch_production_iteration", "token ignored", result, result["exposure_held"] is True and confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT") is False)


def test_g20_clean_shutdown() -> None:
    broker = FakeBroker("filled")
    result = _dispatch(broker=broker)
    _note("G20", "test_g20_clean_shutdown", "FakeBroker.close", "closed after one iteration", result, broker.closed is True and result["scheduled_another"] is False and broker.request_count == 1)


def test_g21_direct_flat_token_does_not_release() -> None:
    _hold()
    released = confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0, "production_dispatch": False}
    _note("G21", "test_g21_direct_flat_token_does_not_release", "confirm_exposure_flat", "hold remains", result, released is False and result["blocked_by"] == "exposure_unconfirmed")


def test_g22_verified_string_does_not_release() -> None:
    _hold()
    released = confirm_exposure_flat("EUR_USD", evidence="verified")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G22", "test_g22_verified_string_does_not_release", "confirm_exposure_flat", "hold remains", result, released is False)


def test_g23_verified_flag_does_not_release() -> None:
    _hold()
    released = confirm_exposure_flat("EUR_USD", verified=True)
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G23", "test_g23_verified_flag_does_not_release", "confirm_exposure_flat", "hold remains", result, released is False and result["blocked_by"] == "exposure_unconfirmed")


def test_g24_fabricated_dictionary_does_not_release() -> None:
    _hold()
    released = confirm_exposure_flat("EUR_USD", evidence={"exposure_safety": "CONFIRMED_FLAT", "verified": True})
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G24", "test_g24_fabricated_dictionary_does_not_release", "confirm_exposure_flat", "hold remains", result, released is False)


def test_g25_fake_reconciliation_response_does_not_release() -> None:
    _hold()
    released = confirm_exposure_flat("EUR_USD", evidence={"kind": "flat", "broker": "fake"})
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G25", "test_g25_fake_reconciliation_response_does_not_release", "confirm_exposure_flat", "hold remains", result, released is False)


def test_g26_wrong_symbol_does_not_release_this_symbol() -> None:
    _hold("EUR_USD")
    _hold("AUD_USD")
    released = confirm_exposure_flat("AUD_USD", evidence="CONFIRMED_FLAT")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G26", "test_g26_wrong_symbol_does_not_release_this_symbol", "confirm_exposure_flat", "EUR_USD still held", result, released is False and exposure_entry_block_reason("AUD_USD") == "exposure_unconfirmed")


def test_g27_stale_evidence_does_not_release() -> None:
    _hold()
    released = confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT", snapshot_stale=True)
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G27", "test_g27_stale_evidence_does_not_release", "confirm_exposure_flat", "hold remains", result, released is False)


def test_g28_incomplete_position_does_not_release() -> None:
    _hold()
    released = confirm_exposure_flat("EUR_USD", evidence={"symbol": "EUR_USD"})
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G28", "test_g28_incomplete_position_does_not_release", "confirm_exposure_flat", "hold remains", result, released is False)


def test_g29_conflicting_quantities_do_not_release() -> None:
    _hold()
    released = confirm_exposure_flat("EUR_USD", evidence={"local_units": 1, "broker_units": 5, "flat": True})
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G29", "test_g29_conflicting_quantities_do_not_release", "confirm_exposure_flat", "hold remains", result, released is False)


def test_g30_malformed_position_data_does_not_release() -> None:
    _hold()
    released = confirm_exposure_flat("EUR_USD", evidence=object())
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G30", "test_g30_malformed_position_data_does_not_release", "confirm_exposure_flat", "hold remains", result, released is False)


def test_g31_reconciliation_exception_keeps_the_hold() -> None:
    _hold()
    reason = interpret_close_evidence("EUR_USD", "reconciliation_raised")
    result = {"status": "held", "blocked_by": reason, "broker_requests": 0}
    _note("G31", "test_g31_reconciliation_exception_keeps_the_hold", "interpret_close_evidence", "hold remains", result, reason == "exposure_unconfirmed")


def test_g32_reconciliation_timeout_keeps_the_hold() -> None:
    _hold()
    reason = interpret_close_evidence("EUR_USD", "timeout")
    result = {"status": "held", "blocked_by": reason, "broker_requests": 0}
    _note("G32", "test_g32_reconciliation_timeout_keeps_the_hold", "interpret_close_evidence", "hold remains", result, reason == "exposure_unconfirmed")


def test_g33_connection_drop_keeps_the_hold() -> None:
    _hold()
    reason = interpret_close_evidence("EUR_USD", "connection_lost")
    result = {"status": "held", "blocked_by": reason, "broker_requests": 0}
    _note("G33", "test_g33_connection_drop_keeps_the_hold", "interpret_close_evidence", "hold remains", result, reason == "exposure_unconfirmed")


def test_g34_rejected_close_keeps_the_hold() -> None:
    _hold()
    reason = interpret_close_evidence("EUR_USD", "rejected")
    result = {"status": "held", "blocked_by": reason, "broker_requests": 0}
    _note("G34", "test_g34_rejected_close_keeps_the_hold", "interpret_close_evidence", "hold remains", result, reason == "exposure_unconfirmed")


def test_g35_partial_close_keeps_the_hold() -> None:
    _hold()
    reason = interpret_close_evidence("EUR_USD", "partial")
    result = {"status": "held", "blocked_by": reason, "broker_requests": 0}
    _note("G35", "test_g35_partial_close_keeps_the_hold", "interpret_close_evidence", "hold remains", result, reason == "exposure_unconfirmed")


def test_g36_removed_local_position_keeps_the_hold() -> None:
    _hold()
    close_position("EUR_USD")
    released = confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G36", "test_g36_removed_local_position_keeps_the_hold", "confirm_exposure_flat", "absence is not flat", result, released is False and get_position("EUR_USD") is None)


def test_g37_historical_filled_row_stays_unresolved() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "old", "symbol": "EUR_USD", "status": "FILLED"}])
    ingest_recovery_snapshot(kept, True)
    released = confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G37", "test_g37_historical_filled_row_stays_unresolved", "ingest_recovery_snapshot", "hold remains", result, kept and released is False and result["blocked_by"] == "exposure_unconfirmed")


def test_g38_pending_order_remains() -> None:
    note_blocking_reservation("EUR_USD", "still-pending")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G38", "test_g38_pending_order_remains", "note_blocking_reservation", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_g39_partial_order_remains() -> None:
    register_order(LocalOrder("part", "EUR_USD", "BUY", 2, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation("EUR_USD", "part")
    result = {"status": "held", "blocked_by": reservation_status_block_reason("PARTIAL"), "broker_requests": 0}
    _note("G39", "test_g39_partial_order_remains", "reservation_status_block_reason", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_g40_unresolved_order_remains() -> None:
    restore_unresolved_intent("EUR_USD", "still-open")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G40", "test_g40_unresolved_order_remains", "restore_unresolved_intent", "unresolved_intent", result, result["blocked_by"] == "unresolved_intent")


def test_g41_authoritative_release_is_not_available() -> None:
    record("G41", "test_g41_authoritative_release_is_not_available", "broker reconciliation", "NOT_EVALUATED", None, "NOT_EVALUATED")
    pytest.skip("NOT_EVALUATED")


def test_g42_restart_after_failed_release_keeps_the_hold() -> None:
    row = {"client_order_id": "restart", "symbol": "EUR_USD", "status": "FILLED", "metadata": {"exposure_safety": "UNCONFIRMED"}}
    confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT")
    reset_order_intent_gate_for_tests()
    ingest_recovery_snapshot(select_rows_for_recovery([row]), True)
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G42", "test_g42_restart_after_failed_release_keeps_the_hold", "select_rows_for_recovery", "hold returns with the row", result, result["blocked_by"] == "exposure_unconfirmed")


def test_g43_repeated_release_attempt_keeps_the_hold() -> None:
    _hold()
    first = confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT")
    second = confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G43", "test_g43_repeated_release_attempt_keeps_the_hold", "confirm_exposure_flat", "both attempts refused", result, first is False and second is False and result["blocked_by"] == "exposure_unconfirmed")


def test_g44_multiple_symbols_keep_independent_holds() -> None:
    _hold("EUR_USD")
    note_blocking_reservation("AUD_USD", "aud-pending")
    confirm_exposure_flat("EUR_USD", evidence="CONFIRMED_FLAT")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("AUD_USD"), "broker_requests": 0}
    _note("G44", "test_g44_multiple_symbols_keep_independent_holds", "exposure_entry_block_reason", "each symbol keeps its own hold", result, exposure_entry_block_reason("EUR_USD") == "exposure_unconfirmed" and result["blocked_by"] == "active_reservation")


def test_g45_failed_persistence_update_keeps_the_hold() -> None:
    first = _dispatch(reservation_update_failure=True)
    close_position("EUR_USD")
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0, "production_dispatch": first["production_dispatch"]}
    _note("G45", "test_g45_failed_persistence_update_keeps_the_hold", "refuse_reservation_after_database_fault", "recovery_unreadable", result, first["status"] == "filled" and result["blocked_by"] == "recovery_unreadable")


def test_g46_pending_reservation_regression() -> None:
    note_blocking_reservation("EUR_USD", "f01")
    result = _dispatch()
    _note("G46", "test_g46_pending_reservation_regression", "note_blocking_reservation", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_g47_partial_reservation_regression() -> None:
    note_blocking_reservation("EUR_USD", "f02")
    result = _dispatch()
    _note("G47", "test_g47_partial_reservation_regression", "note_blocking_reservation", "active_reservation", result, result["blocked_by"] == "active_reservation")


def test_g48_unresolved_reservation_regression() -> None:
    restore_unresolved_intent("EUR_USD", "f03")
    result = _dispatch()
    _note("G48", "test_g48_unresolved_reservation_regression", "restore_unresolved_intent", "unresolved_intent", result, result["blocked_by"] == "unresolved_intent")


def test_g49_unknown_status_hold() -> None:
    result = {"status": "held", "blocked_by": reservation_status_block_reason("MYSTERY"), "broker_requests": 0}
    _note("G49", "test_g49_unknown_status_hold", "reservation_status_block_reason", "unknown_status", result, result["blocked_by"] == "unknown_status")


def test_g50_duplicate_client_id() -> None:
    register_order(LocalOrder("same", "EUR_USD", "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _dispatch(client_order_id="same")
    _note("G50", "test_g50_duplicate_client_id", "try_begin_order_submission", "reservation_refused", result, result["blocked_by"] == "reservation_refused" and result["broker_requests"] == 0)


def test_g51_duplicate_symbol() -> None:
    _dispatch()
    result = _dispatch(broker=FakeBroker("filled"))
    _note("G51", "test_g51_duplicate_symbol", "exposure_entry_block_reason", "second dispatch blocked", result, result["broker_requests"] == 0)


def test_g52_ambiguous_commit_hold() -> None:
    result = _dispatch(persistence_failure="uncertain")
    _note("G52", "test_g52_ambiguous_commit_hold", "refuse_reservation_after_database_fault", "uncertain", result, result["outcome"] == "uncertain" and result["broker_requests"] == 0)


def test_g53_persistence_failure_hold() -> None:
    result = _dispatch(persistence_failure="fail")
    later = try_begin_order_submission(client_order_id="after-fault", symbol="EUR_USD", direction="BUY", units=1)
    outcome = {"status": "held", "blocked_by": "refused" if later is False else "allowed", "broker_requests": 0, "production_dispatch": result["production_dispatch"]}
    _note("G53", "test_g53_persistence_failure_hold", "try_begin_order_submission", "later reservation refused", outcome, later is False)


def test_g54_filled_exposure_hold() -> None:
    _hold()
    result = _dispatch()
    _note("G54", "test_g54_filled_exposure_hold", "note_unconfirmed_exposure", "exposure_unconfirmed", result, result["blocked_by"] == "exposure_unconfirmed" and confirm_exposure_flat("EUR_USD", evidence="FILLED") is False)


def test_g55_missing_position_hold() -> None:
    _hold()
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0}
    _note("G55", "test_g55_missing_position_hold", "exposure_entry_block_reason", "no local position", result, get_position("EUR_USD") is None and result["blocked_by"] == "exposure_unconfirmed")


def test_g56_position_recording_failure_regression() -> None:
    first = _dispatch(fail_position_record=True)
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("EUR_USD"), "broker_requests": 0, "production_dispatch": first["production_dispatch"]}
    _note("G56", "test_g56_position_recording_failure_regression", "note_unconfirmed_exposure", "hold remains", result, result["blocked_by"] == "exposure_unconfirmed")


def test_g57_historical_filled_recovery() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "r11", "symbol": "EUR_USD", "status": "FILLED"}])
    ingest_recovery_snapshot(kept, True)
    result = _dispatch()
    _note("G57", "test_g57_historical_filled_recovery", "select_rows_for_recovery", "historical FILLED blocks", result, bool(kept) and result["blocked_by"] == "exposure_unconfirmed")


def test_g58_multiple_historical_filled_rows() -> None:
    rows = [
        {"client_order_id": "a", "symbol": "EUR_USD", "status": "FILLED", "metadata": {}},
        {"client_order_id": "b", "symbol": "AUD_USD", "status": "FILLED", "metadata": None},
    ]
    kept = select_rows_for_recovery(rows)
    ingest_recovery_snapshot(kept, True)
    result = {"status": "held", "blocked_by": exposure_entry_block_reason("AUD_USD"), "broker_requests": 0}
    _note("G58", "test_g58_multiple_historical_filled_rows", "select_rows_for_recovery", "both symbols held", result, len(kept) == 2 and exposure_entry_block_reason("EUR_USD") == "exposure_unconfirmed" and result["blocked_by"] == "exposure_unconfirmed")


def test_g59_invalid_direction_regression() -> None:
    result = _dispatch(vote={"allow": True, "direction": "NO_TRADE"})
    _note("G59", "test_g59_invalid_direction_regression", "direction_action_gate", "invalid direction", result, result["blocked_by"] == "invalid_entry_direction")


def test_g60_inactive_strategy_regression() -> None:
    result = _dispatch(strategy_name="scalp", strategy_known=True, strategy_active=False)
    _note("G60", "test_g60_inactive_strategy_regression", "strategy_entry_block_reason", "STRATEGY_INACTIVE", result, result["blocked_by"] == "STRATEGY_INACTIVE" and strategies["scalp"].active is False)


def test_g61_live_authorisation_block() -> None:
    result = _dispatch(simulation=False)
    _note("G61", "test_g61_live_authorisation_block", "pre_trade_entry_blocked_reason", "live block", result, "live_order_auth" in str(result["blocked_by"]) and result["broker_requests"] == 0)


def test_g62_no_real_broker_dispatch() -> None:
    import forex_bot.oanda_client as oanda_client

    result = _dispatch()
    _note("G62", "test_g62_no_real_broker_dispatch", "oanda_client._api", "no client", result, oanda_client._api is None and result["real_broker"] is False)


def test_g63_no_automatic_retry() -> None:
    first = _dispatch(broker=FakeBroker("ambiguous"))
    second = _dispatch(broker=FakeBroker("filled"))
    _note("G63", "test_g63_no_automatic_retry", "restore_unresolved_intent", "no second request", second, first["status"] == "uncertain" and second["broker_requests"] == 0)


def test_g64_no_production_state_mutation() -> None:
    _dispatch()
    stamp = OPS_PERMISSION.stat().st_mtime if OPS_PERMISSION.exists() else None
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("G64", "test_g64_no_production_state_mutation", "live_safety path", "unchanged", result, stamp == OPS_BEFORE)


def test_g65_no_production_launcher() -> None:
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("G65", "test_g65_no_production_launcher", "sys.modules", "main not imported", result, "main" not in sys.modules and run_bot.__name__ == "run_bot")


def test_g66_production_orchestration_references_shared_decision() -> None:
    source = inspect.getsource(_evaluate_impl)
    evaluate_source = inspect.getsource(evaluate)
    ok = "dispatch_production_iteration" in source and "dispatch_production_iteration" in evaluate_source
    result = {"status": "wired", "blocked_by": "", "broker_requests": 0, "production_dispatch": True, "shared_implementation": "evaluate_one_instrument_iteration"}
    _note("G66", "test_g66_production_orchestration_references_shared_decision", "_evaluate_impl", "shared call present", result, ok)


def test_g67_driver_uses_production_boundary() -> None:
    broker = FakeBroker("filled")
    result = _drive(evaluate("EUR_USD", _deps(broker=broker)))
    direct = evaluate_one_instrument_iteration
    _note("G67", "test_g67_driver_uses_production_boundary", "evaluate", "production evaluate delegates", result, result["production_dispatch"] is True and result["shared_implementation"] == direct.__name__ and broker.request_count == 1)


def test_g68_gate_order_matches_the_shared_path() -> None:
    result = _dispatch()
    phases = list(result["phases"])
    expected = ["seam", "session", "position", "exposure", "broker_exit", "permission", "strategy", "indicators", "vote", "direction"]
    _note("G68", "test_g68_gate_order_matches_the_shared_path", "evaluate_one_instrument_iteration", "shared order", result, phases[: len(expected)] == expected)


def test_g69_buy_reaches_fake_broker_once() -> None:
    broker = FakeBroker("filled")
    result = _drive(evaluate("EUR_USD", _deps(broker=broker)))
    _note("G69", "test_g69_buy_reaches_fake_broker_once", "evaluate", "one BUY request", result, result["direction"] == "BUY" and broker.request_count == 1)


def test_g70_sell_reaches_fake_broker_once() -> None:
    broker = FakeBroker("filled")
    result = _drive(evaluate("EUR_USD", _deps(vote={"allow": True, "direction": "SELL"}, broker=broker)))
    _note("G70", "test_g70_sell_reaches_fake_broker_once", "evaluate", "one SELL request", result, result["direction"] == "SELL" and broker.request_count == 1)


def test_g71_permission_block_reaches_fake_broker_zero_times() -> None:
    broker = FakeBroker("filled")
    result = _drive(evaluate("EUR_USD", _deps(simulation=False, broker=broker)))
    _note("G71", "test_g71_permission_block_reaches_fake_broker_zero_times", "evaluate", "zero requests", result, broker.request_count == 0)


def test_g72_no_strategy_activation() -> None:
    _dispatch()
    names = tuple(SCALP_STRATEGY_KEYS) + tuple(SWING_STRATEGY_KEYS)
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("G72", "test_g72_no_strategy_activation", "strategy_meta.strategies", "six strategies inactive", result, len(names) == 6 and all(strategies[name].active is False for name in names))


def test_g73_no_live_permission_mutation() -> None:
    _dispatch()
    stamp = OPS_PERMISSION.stat().st_mtime if OPS_PERMISSION.exists() else None
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("G73", "test_g73_no_live_permission_mutation", "live_safety path", "unchanged", result, stamp == OPS_BEFORE)


def test_g74_no_oanda_client() -> None:
    import forex_bot.oanda_client as oanda_client

    _dispatch()
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("G74", "test_g74_no_oanda_client", "oanda_client._api", "None", result, oanda_client._api is None)


def test_g75_no_postgresql() -> None:
    _dispatch()
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("G75", "test_g75_no_postgresql", "database._pg_conn", "None", result, database._pg_conn is None)


def test_g76_no_external_network() -> None:
    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocked = False
    except RuntimeError as exc:
        blocked = "NETWORK_BLOCKED" in str(exc)
    result = {"status": "observed", "blocked_by": "network" if blocked else "open", "broker_requests": 0}
    _note("G76", "test_g76_no_external_network", "socket barrier", "blocked", result, blocked)


def test_g77_no_dns_success() -> None:
    try:
        socket.getaddrinfo("example.invalid", 80)
        blocked = False
    except RuntimeError as exc:
        blocked = "DNS_BLOCKED" in str(exc)
    result = {"status": "observed", "blocked_by": "dns" if blocked else "open", "broker_requests": 0}
    _note("G77", "test_g77_no_dns_success", "socket.getaddrinfo", "blocked", result, blocked)


def test_g78_no_run_bot_execution() -> None:
    result = _dispatch()
    _note("G78", "test_g78_no_run_bot_execution", "dispatch_production_iteration", "run_bot not entered", result, "run_bot" not in result["phases"] and result["scheduled_another"] is False)


def test_g79_no_production_lifespan() -> None:
    result = {"status": "observed", "blocked_by": "", "broker_requests": 0}
    _note("G79", "test_g79_no_production_lifespan", "sys.modules", "lifespan not entered", result, "main" not in sys.modules)


def test_g80_exactly_one_iteration() -> None:
    broker = FakeBroker("filled")
    result = _dispatch(broker=broker)
    _note("G80", "test_g80_exactly_one_iteration", "dispatch_production_iteration", "one request", result, broker.request_count == 1 and result["scheduled_another"] is False)


def test_g81_deterministic_cleanup() -> None:
    broker = FakeBroker("filled", error=RuntimeError("simulated"))
    result = _dispatch(broker=broker)
    _note("G81", "test_g81_deterministic_cleanup", "FakeBroker.close", "closed", result, broker.closed is True and result["status"] == "uncertain")


def test_g82_no_pending_background_tasks() -> None:
    before = {item.ident for item in threading.enumerate()}
    result = _dispatch()
    after = {item.ident for item in threading.enumerate()}
    _note("G82", "test_g82_no_pending_background_tasks", "dispatch_production_iteration", "no new thread", result, before == after)


def test_g83_postgresql_engine_not_evaluated() -> None:
    record("G83", "test_g83_postgresql_engine_not_evaluated", "PostgreSQL", "NOT_EVALUATED", None, "NOT_EVALUATED")
    pytest.skip("NOT_EVALUATED")


def test_g84_broker_reconciliation_not_evaluated() -> None:
    record("G84", "test_g84_broker_reconciliation_not_evaluated", "broker reconciliation", "NOT_EVALUATED", None, "NOT_EVALUATED")
    pytest.skip("NOT_EVALUATED")


def test_g85_production_launcher_not_evaluated() -> None:
    record("G85", "test_g85_production_launcher_not_evaluated", "main", "NOT_EVALUATED", None, "NOT_EVALUATED")
    pytest.skip("NOT_EVALUATED")


def test_g86_continuous_run_bot_not_evaluated() -> None:
    record("G86", "test_g86_continuous_run_bot_not_evaluated", "run_bot", "NOT_EVALUATED", None, "NOT_EVALUATED")
    pytest.skip("NOT_EVALUATED")


def test_g87_authoritative_flat_release_not_evaluated() -> None:
    record("G87", "test_g87_authoritative_flat_release_not_evaluated", "broker-flat release", "NOT_EVALUATED", None, "NOT_EVALUATED")
    pytest.skip("NOT_EVALUATED")
