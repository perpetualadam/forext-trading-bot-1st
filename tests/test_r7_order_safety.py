"""Synthetic order-safety checks for R.7.

These tests do not open PostgreSQL, start the application, or contact a broker.
Engine cases are skipped rather than marked passed.
"""

from __future__ import annotations

import os
import sys

import pytest

from forex_bot.bot_loop import broker_entry_block_reason
from forex_bot.database import (
    UNRESOLVED_ORDER_STATUS,
    OrderRecoveryUnreadable,
    _symbol_reservation_lock_key,
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
    classify_order_create_transport_error,
)
from forex_bot.orders import (
    OrderStatus,
    ingest_recovery_snapshot,
    mark_order_failed_or_cancelled,
    orders_by_client_id,
    reset_orders_for_tests,
    try_begin_order_submission,
)

SYMBOL = "EUR_USD"
OTHER = "GBP_USD"


def setup_function() -> None:
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()


def _row(status: str, client_order_id: str, symbol: str = SYMBOL, side: str = "BUY") -> dict:
    return {
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": side,
        "units": 1,
        "status": status,
        "created_at": "2026-10-15T00:00:00+00:00",
    }


def _reserve(client_order_id: str, symbol: str = SYMBOL) -> bool:
    return try_begin_order_submission(
        client_order_id=client_order_id,
        symbol=symbol,
        direction="BUY",
        units=1.0,
        metadata={"fixture": "r7"},
    )


def test_h01_h06_reload_keeps_unresolved_identity_and_blocks_a_new_id() -> None:
    loaded = ingest_recovery_snapshot([_row(UNRESOLVED_ORDER_STATUS, "cid-original")], True)
    assert loaded == 1
    order = orders_by_client_id["cid-original"]
    assert order.status == OrderStatus.UNRESOLVED
    assert order.client_order_id == "cid-original"
    assert order.symbol == SYMBOL
    assert order.detail == "loaded from exec_orders"
    again = ingest_recovery_snapshot([_row(UNRESOLVED_ORDER_STATUS, "cid-original")], True)
    assert again == 0
    assert _reserve("cid-original") is False
    assert _reserve("cid-replacement") is False


def test_h04_fresh_book_with_recovery_row_stays_blocked() -> None:
    reset_order_intent_gate_for_tests()
    reason = new_intent_block_reason(
        fresh_intent_book(),
        SYMBOL,
        [_row(UNRESOLVED_ORDER_STATUS, "cid-original")],
        True,
    )
    assert reason == "unresolved_intent"


def test_h07_h08_pending_and_partial_keep_their_status() -> None:
    loaded = ingest_recovery_snapshot(
        [
            _row("PENDING", "cid-pending"),
            _row("PARTIAL", "cid-partial", side="SELL"),
        ],
        True,
    )
    assert loaded == 2
    assert orders_by_client_id["cid-pending"].status == OrderStatus.PENDING
    assert orders_by_client_id["cid-partial"].status == OrderStatus.PARTIAL
    assert orders_by_client_id["cid-partial"].direction == "SELL"


def test_h09_h11_unknown_or_corrupt_rows_fail_closed() -> None:
    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot([_row("MYSTERY", "cid-bad")], True)
    assert broker_entry_block_reason(SYMBOL) == "recovery_unreadable"
    reset_order_intent_gate_for_tests()
    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot([{"symbol": SYMBOL}], True)
    assert _reserve("cid-after-corrupt") is False


def test_h10_h12_missing_recovery_fails_closed() -> None:
    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot(None, False)
    assert broker_entry_block_reason(SYMBOL) == "recovery_unreadable"
    assert _reserve("cid-after-missing") is False


def test_h13_h16_process_fail_closed_blocks_without_a_database() -> None:
    from forex_bot.database import force_order_recovery_fail_closed

    force_order_recovery_fail_closed()
    assert _reserve("cid-after-query-failure") is False
    assert broker_entry_block_reason(SYMBOL) == "recovery_unreadable"


def test_h17_cancel_does_not_erase_unresolved() -> None:
    ingest_recovery_snapshot([_row(UNRESOLVED_ORDER_STATUS, "cid-original")], True)
    mark_order_failed_or_cancelled("cid-original")
    assert orders_by_client_id["cid-original"].status == OrderStatus.UNRESOLVED
    assert _reserve("cid-other") is False


def test_h18_h19_timeout_and_unavailable_reconciliation_stay_blocked() -> None:
    classified = classify_order_create_transport_error(TimeoutError("timed out"))
    assert classified.outcome == OUTCOME_AMBIGUOUS_TRANSPORT
    book = book_on_reconciliation(
        book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-timeout"),
        SYMBOL,
        "UNAVAILABLE",
    )
    assert book["retries"] == 0
    assert book["unresolved"][SYMBOL] == "cid-timeout"
    assert new_intent_block_reason(book, SYMBOL, [], True) == "unresolved_intent"


def test_h20_h22_confirmed_results_do_not_create_replacements() -> None:
    for status in ("FILLED", "REJECTED", "CANCELLED"):
        book = book_on_terminal(
            book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-original"),
            SYMBOL,
            status,
        )
        assert book["replacements"] == []
        assert SYMBOL not in book["unresolved"]


def test_h23_duplicate_event_keeps_the_first_id() -> None:
    once = book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-original")
    twice = book_on_ambiguous(once, SYMBOL, "cid-other")
    assert twice["unresolved"] == {SYMBOL: "cid-original"}


def test_h29_lock_key_is_stable_for_the_same_uppercased_symbol() -> None:
    assert _symbol_reservation_lock_key(SYMBOL) == _symbol_reservation_lock_key(SYMBOL)
    assert _symbol_reservation_lock_key(SYMBOL) != _symbol_reservation_lock_key(OTHER)


def test_h32_h33_no_application_and_no_broker_module_startup() -> None:
    assert "forex_bot.app" not in sys.modules
    assert remember_ambiguous_outcome(SYMBOL, "cid-memory") is False


@pytest.mark.skip(reason="POSTGRESQL_ENGINE_NOT_EVALUATED")
def test_h24_h31_postgresql_concurrency_and_storage() -> None:
    """Not executed. A fake database must not count as an engine pass."""
