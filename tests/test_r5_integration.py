"""Offline integration tests for the R.5 safety wiring.

These tests do not start the application, start the trading loop, or open
a database connection.
"""

from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path

import pytest

from forex_bot.bot_loop import (
    _evaluate_impl,
    broker_entry_block_reason,
    canonical_entry_direction,
    continue_entry_after_strategy_gate,
    direction_action_gate,
)
from forex_bot.database import (
    UNRESOLVED_ORDER_STATUS,
    OrderRecoveryUnreadable,
    book_on_ambiguous,
    book_on_reconciliation,
    book_on_terminal,
    fresh_intent_book,
    new_intent_block_reason,
    remember_ambiguous_outcome,
    reset_order_intent_gate_for_tests,
)
from forex_bot.oanda_exec import (
    OUTCOME_AMBIGUOUS_TRANSPORT,
    OUTCOME_CANCELLED,
    OUTCOME_FILLED,
    OUTCOME_MALFORMED,
    OUTCOME_REJECTED,
    classify_order_create_response,
    classify_order_create_transport_error,
)
from forex_bot.orders import (
    OrderStatus,
    ingest_recovery_snapshot,
    load_open_orders_from_db_into_memory,
    mark_order_failed_or_cancelled,
    orders_by_client_id,
    register_order,
    reset_orders_for_tests,
    try_begin_order_submission,
)
from forex_bot.orders import LocalOrder
from forex_bot.strategy_meta import SCALP_STRATEGY_KEYS, SWING_STRATEGY_KEYS, strategies

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / "data" / "research" / "adaptive_ensemble" / "r5"
SYMBOL = "EUR_USD"


def setup_function() -> None:
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()


def _spies():
    calls = {"size": 0, "build": 0, "reserve": 0, "send": 0, "id": 0}

    def size(*_args):
        calls["size"] += 1

    def build(*_args):
        calls["build"] += 1

    def reserve(*_args):
        calls["reserve"] += 1

    def send(*_args):
        calls["send"] += 1

    def make_id(*_args):
        calls["id"] += 1

    return calls, size, build, reserve, send, make_id


def _reserve(client_order_id: str) -> bool:
    return try_begin_order_submission(
        client_order_id=client_order_id,
        symbol=SYMBOL,
        direction="BUY",
        units=1.0,
        metadata={"fixture": "r5"},
    )


def _row(status: str, client_order_id: str = "cid-row", side: str = "BUY") -> dict:
    return {
        "client_order_id": client_order_id,
        "symbol": SYMBOL,
        "side": side,
        "units": 1,
        "status": status,
    }


@pytest.mark.parametrize(
    "raw, expected",
    [("BUY", "BUY"), ("SELL", "SELL"), ("buy", "BUY"), (" sell ", "SELL")],
)
def test_h01_h03_valid_directions(raw: str, expected: str) -> None:
    assert canonical_entry_direction(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "UNKNOWN", "NO_TRADE", 0, 1, 2.5])
def test_h04_h09_invalid_directions(raw: object) -> None:
    assert canonical_entry_direction(raw) is None


def test_h10_h12_invalid_direction_does_not_trade() -> None:
    calls, size, build, reserve, send, _make_id = _spies()
    assert direction_action_gate(None, size, build, send, reserve) is None
    assert direction_action_gate("UNKNOWN", size, build, send, reserve) is None
    assert calls == {"size": 0, "build": 0, "reserve": 0, "send": 0, "id": 0}


def test_h13_h14_transport_errors_stay_unresolved() -> None:
    assert classify_order_create_transport_error(TimeoutError("timed out")).outcome == OUTCOME_AMBIGUOUS_TRANSPORT
    assert (
        classify_order_create_transport_error(ConnectionResetError("reset")).outcome
        == OUTCOME_AMBIGUOUS_TRANSPORT
    )
    book = book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-timeout")
    assert book["retries"] == 0
    assert new_intent_block_reason(book, SYMBOL, [], True) == "unresolved_intent"


def test_h15_malformed_reply_is_not_a_rejection() -> None:
    assert classify_order_create_response(None).outcome == OUTCOME_MALFORMED
    book = book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-bad")
    assert new_intent_block_reason(book, SYMBOL, [], True) == "unresolved_intent"


def test_h16_new_client_id_blocked_while_unresolved() -> None:
    assert remember_ambiguous_outcome(SYMBOL, "cid-original") is False
    assert _reserve("cid-replacement") is False


def test_h17_same_client_id_blocked() -> None:
    assert _reserve("cid-same") is True
    assert _reserve("cid-same") is False


def test_h18_h19_no_retry_and_unavailable_reconciliation_blocks() -> None:
    book = book_on_reconciliation(
        book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-original"),
        SYMBOL,
        "UNAVAILABLE",
    )
    assert book["retries"] == 0
    assert book["replacements"] == []
    assert book["unresolved"][SYMBOL] == "cid-original"


def test_h20_h22_confirmed_results_do_not_create_replacements() -> None:
    filled = classify_order_create_response(
        {"orderFillTransaction": {"id": "1", "price": "1.1"}}
    )
    rejected = classify_order_create_response(
        {"orderRejectTransaction": {"id": "2", "rejectReason": "MARGIN"}}
    )
    cancelled = classify_order_create_response(
        {"orderCancelTransaction": {"id": "3", "reason": "CLIENT_REQUEST"}}
    )
    assert filled.outcome == OUTCOME_FILLED
    assert rejected.outcome == OUTCOME_REJECTED
    assert cancelled.outcome == OUTCOME_CANCELLED
    for status in ("FILLED", "REJECTED", "CANCELLED"):
        book = book_on_terminal(book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid"), SYMBOL, status)
        assert book["replacements"] == []
        assert SYMBOL not in book["unresolved"]


def test_h23_duplicate_event_keeps_original_id() -> None:
    once = book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-original")
    twice = book_on_ambiguous(once, SYMBOL, "cid-other")
    assert twice["unresolved"] == {SYMBOL: "cid-original"}


def test_h24_simulated_restart_reloads_unresolved() -> None:
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    loaded = ingest_recovery_snapshot([_row(UNRESOLVED_ORDER_STATUS, "cid-original")], True)
    assert loaded == 1
    assert orders_by_client_id["cid-original"].status == OrderStatus.UNRESOLVED
    assert _reserve("cid-after-restart") is False


def test_h25_h27_missing_or_unreadable_recovery_fails_closed() -> None:
    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot(None, False)
    assert broker_entry_block_reason(SYMBOL) == "recovery_unreadable"
    assert _reserve("cid-after-missing") is False


def test_h26_corrupt_recovery_fails_closed() -> None:
    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot([{"symbol": SYMBOL}], True)
    assert broker_entry_block_reason(SYMBOL) == "recovery_unreadable"


def test_h28_legacy_pending_and_partial_rows_keep_their_status() -> None:
    loaded = ingest_recovery_snapshot(
        [_row("PENDING", "cid-pending"), _row("PARTIAL", "cid-partial", "SELL")],
        True,
    )
    assert loaded == 2
    assert orders_by_client_id["cid-pending"].status == OrderStatus.PENDING
    assert orders_by_client_id["cid-partial"].status == OrderStatus.PARTIAL
    assert orders_by_client_id["cid-partial"].direction == "SELL"
    # R.8: a recovered PENDING or PARTIAL row blocks another client id.
    assert _reserve("cid-new-after-legacy") is False


def test_h29_orders_recognise_unresolved_and_do_not_cancel_it() -> None:
    assert OrderStatus.UNRESOLVED.value == "UNRESOLVED"
    register_order(
        LocalOrder(
            client_order_id="cid-open",
            symbol=SYMBOL,
            direction="BUY",
            units_requested=1,
            units_filled=0,
            status=OrderStatus.PENDING,
            avg_fill_price=None,
            created_ts=0,
        )
    )
    remember_ambiguous_outcome(SYMBOL, "cid-open")
    orders_by_client_id["cid-open"].status = OrderStatus.UNRESOLVED
    mark_order_failed_or_cancelled("cid-open")
    assert orders_by_client_id["cid-open"].status == OrderStatus.UNRESOLVED


def test_h30_concurrent_reservations_blocked_after_unresolved() -> None:
    import threading

    remember_ambiguous_outcome(SYMBOL, "cid-original")
    results: list[bool] = []
    lock = threading.Lock()

    def attempt(number: int) -> None:
        allowed = _reserve(f"cid-race-{number}")
        with lock:
            results.append(allowed)

    threads = [threading.Thread(target=attempt, args=(number,)) for number in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [False, False]


def test_h31_fail_closed_flag_blocks_entry_without_a_database() -> None:
    from forex_bot.database import force_order_recovery_fail_closed

    force_order_recovery_fail_closed()
    assert _reserve("cid-after-failure") is False
    assert broker_entry_block_reason(SYMBOL) == "recovery_unreadable"


def test_h34_six_strategies_inactive() -> None:
    names = set(SCALP_STRATEGY_KEYS) | set(SWING_STRATEGY_KEYS)
    assert len(names) == 6
    assert all(strategies[name].active is False for name in names)


def test_h35_h38_inactive_and_unknown_strategy_make_no_trading_calls() -> None:
    calls, size, build, reserve, send, make_id = _spies()
    assert (
        continue_entry_after_strategy_gate(
            "trend",
            active=False,
            authorised_for_live=False,
            safety_initialised=True,
            known_strategy=True,
            sizer=size,
            builder=build,
            sender=send,
            id_factory=make_id,
        )
        is None
    )
    assert (
        continue_entry_after_strategy_gate(
            "not-a-strategy",
            active=True,
            authorised_for_live=True,
            safety_initialised=True,
            known_strategy=False,
            sizer=size,
            builder=build,
            sender=send,
            id_factory=make_id,
        )
        is None
    )
    assert calls == {"size": 0, "build": 0, "reserve": 0, "send": 0, "id": 0}


def test_h39_h40_restart_keeps_live_orders_blocked() -> None:
    import forex_bot.live_safety as live_safety

    path = R5 / "synthetic_live_safety_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(path)
    document = live_safety._blank_document(reason="r5-synthetic")
    document["live_order_authorisation"]["state"] = "ALLOWED"
    path.write_text(json.dumps(document), encoding="utf-8")
    live_safety.initialise_fail_closed()
    assert live_safety.live_order_auth_state() == live_safety.AUTH_BLOCKED
    assert all(item.active is False for item in strategies.values())


def test_h41_h44_live_eval_wires_the_safety_gates() -> None:
    source = inspect.getsource(_evaluate_impl)
    assert "direction_action_gate" in source
    assert "continue_entry_after_strategy_gate" in source
    assert "broker_entry_block_reason" in source
    assert 'get("direction", "BUY")' not in source
    loader = inspect.getsource(load_open_orders_from_db_into_memory)
    assert "fetch_exec_orders_open_for_recovery" in loader
    assert "ingest_recovery_snapshot" in loader


def test_h46_application_module_was_not_imported() -> None:
    assert "forex_bot.app" not in sys.modules
