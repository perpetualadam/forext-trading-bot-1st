"""Offline regression tests for the R.4 order-intent and direction repairs.

These tests do not start the trading loop, open a broker connection, or
read a production database. Durable restart behaviour is exercised with
synthetic recovery rows.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from forex_bot.bot_loop import (
    broker_entry_block_reason,
    canonical_entry_direction,
    direction_action_gate,
)
from forex_bot.database import (
    UNRESOLVED_ORDER_STATUS,
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
from forex_bot.orders import reset_orders_for_tests, try_begin_order_submission
from forex_bot.strategy_meta import SCALP_STRATEGY_KEYS, SWING_STRATEGY_KEYS, strategies

ROOT = Path(__file__).resolve().parents[1]
R4 = ROOT / "data" / "research" / "adaptive_ensemble" / "r4"
SYMBOL = "EUR_USD"


def setup_function() -> None:
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()


def _spies():
    calls = {"size": 0, "build": 0, "send": 0}

    def size(_direction: str) -> None:
        calls["size"] += 1

    def build(_direction: str) -> None:
        calls["build"] += 1

    def send(_direction: str) -> None:
        calls["send"] += 1

    return calls, size, build, send


def _reserve(client_order_id: str) -> bool:
    return try_begin_order_submission(
        client_order_id=client_order_id,
        symbol=SYMBOL,
        direction="BUY",
        units=1.0,
        metadata={"fixture": "r4"},
    )


def test_f01_confirmed_fill_clears_intent_without_replacement() -> None:
    classified = classify_order_create_response(
        {"orderFillTransaction": {"id": "1", "price": "1.1000", "clientExtensions": {"id": "cid-1"}}}
    )
    assert classified.outcome == OUTCOME_FILLED
    book = book_on_terminal(
        book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-1"),
        SYMBOL,
        "FILLED",
    )
    assert SYMBOL not in book["unresolved"]
    assert book["replacements"] == []
    assert book["retries"] == 0


def test_f02_confirmed_rejection_clears_intent() -> None:
    classified = classify_order_create_response(
        {"orderRejectTransaction": {"id": "2", "rejectReason": "INSUFFICIENT_MARGIN"}}
    )
    assert classified.outcome == OUTCOME_REJECTED
    book = book_on_terminal(
        book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-2"),
        SYMBOL,
        "REJECTED",
    )
    assert new_intent_block_reason(book, SYMBOL, [], True) is None


def test_f03_confirmed_cancellation_clears_intent() -> None:
    classified = classify_order_create_response(
        {"orderCancelTransaction": {"id": "3", "reason": "CLIENT_REQUEST"}}
    )
    assert classified.outcome == OUTCOME_CANCELLED
    book = book_on_terminal(
        book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-3"),
        SYMBOL,
        "CANCELLED",
    )
    assert new_intent_block_reason(book, SYMBOL, [], True) is None


def test_f04_timeout_stays_unresolved() -> None:
    classified = classify_order_create_transport_error(TimeoutError("timed out"))
    assert classified.outcome == OUTCOME_AMBIGUOUS_TRANSPORT
    assert classified.outcome != OUTCOME_REJECTED
    assert classified.outcome != OUTCOME_CANCELLED
    book = book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-timeout")
    assert book["unresolved"][SYMBOL] == "cid-timeout"
    assert book["retries"] == 0


def test_f05_connection_reset_stays_unresolved() -> None:
    classified = classify_order_create_transport_error(ConnectionResetError("reset"))
    assert classified.outcome == OUTCOME_AMBIGUOUS_TRANSPORT
    book = book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-reset")
    assert new_intent_block_reason(book, SYMBOL, [], True) == "unresolved_intent"


def test_f06_malformed_response_does_not_become_a_rejection() -> None:
    classified = classify_order_create_response("not-a-broker-body")
    assert classified.outcome == OUTCOME_MALFORMED
    book = book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-bad")
    assert new_intent_block_reason(book, SYMBOL, [], True) == "unresolved_intent"


def test_f07_same_client_order_id_cannot_be_reserved_twice() -> None:
    assert _reserve("cid-same") is True
    assert _reserve("cid-same") is False


def test_f08_new_client_order_id_cannot_bypass_unresolved_intent() -> None:
    assert remember_ambiguous_outcome(SYMBOL, "cid-original") is False
    assert _reserve("cid-replacement") is False
    blocked = broker_entry_block_reason(SYMBOL)
    assert blocked in {"unresolved_intent", "recovery_unreadable"}


def test_f09_restart_preserves_unresolved_intent() -> None:
    reset_order_intent_gate_for_tests()
    restarted = fresh_intent_book()
    rows = [
        {
            "client_order_id": "cid-original",
            "symbol": SYMBOL,
            "status": UNRESOLVED_ORDER_STATUS,
        }
    ]
    assert new_intent_block_reason(restarted, SYMBOL, rows, True) == "unresolved_intent"


def test_f10_unavailable_reconciliation_stays_blocked() -> None:
    book = book_on_reconciliation(
        book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-original"),
        SYMBOL,
        "UNAVAILABLE",
    )
    assert book["unresolved"][SYMBOL] == "cid-original"
    assert book["replacements"] == []
    assert new_intent_block_reason(book, SYMBOL, [], True) == "unresolved_intent"


def test_f11_confirmed_absence_releases_without_a_new_order() -> None:
    book = book_on_reconciliation(
        book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-original"),
        SYMBOL,
        "CONFIRMED_ABSENT",
    )
    assert SYMBOL not in book["unresolved"]
    assert book["replacements"] == []
    assert book["retries"] == 0
    assert new_intent_block_reason(book, SYMBOL, [], True) is None


def test_f12_confirmed_fill_reconciliation_does_not_replace() -> None:
    book = book_on_reconciliation(
        book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-original"),
        SYMBOL,
        "CONFIRMED_FILL",
    )
    assert book["replacements"] == []
    assert book["retries"] == 0
    assert SYMBOL not in book["unresolved"]


def test_f13_duplicate_event_keeps_the_original_id() -> None:
    once = book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-original")
    twice = book_on_ambiguous(once, SYMBOL, "cid-other")
    assert twice["unresolved"] == {SYMBOL: "cid-original"}
    assert twice["replacements"] == []


def test_f14_corrupt_recovery_fails_closed() -> None:
    book = fresh_intent_book()
    assert new_intent_block_reason(book, SYMBOL, [{"symbol": SYMBOL}], True) == "recovery_corrupt"
    assert new_intent_block_reason(book, SYMBOL, ["not-a-row"], True) == "recovery_corrupt"


def test_f15_missing_recovery_fails_closed() -> None:
    assert new_intent_block_reason(fresh_intent_book(), SYMBOL, None, False) == "recovery_unreadable"
    assert broker_entry_block_reason(SYMBOL) == "recovery_unreadable"


def test_f16_timeout_does_not_retry() -> None:
    book = book_on_ambiguous(fresh_intent_book(), SYMBOL, "cid-timeout")
    assert book["retries"] == 0
    assert book["replacements"] == []


@pytest.mark.parametrize("raw, expected", [("BUY", "BUY"), ("SELL", "SELL"), (" buy ", "BUY"), ("sell", "SELL")])
def test_f17_f19_valid_directions(raw: str, expected: str) -> None:
    assert canonical_entry_direction(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "UNKNOWN", "NO_TRADE", 0, 1, 1.5, "HOLD"])
def test_f20_f25_invalid_directions(raw: object) -> None:
    assert canonical_entry_direction(raw) is None


def test_f26_f28_invalid_direction_makes_no_trading_calls() -> None:
    calls, size, build, send = _spies()
    assert direction_action_gate(None, size, build, send) is None
    assert direction_action_gate("UNKNOWN", size, build, send) is None
    assert calls == {"size": 0, "build": 0, "send": 0}


def test_f29_strategies_default_inactive() -> None:
    names = set(SCALP_STRATEGY_KEYS) | set(SWING_STRATEGY_KEYS)
    assert names == {
        "scalp",
        "trend",
        "mean_reversion",
        "swing_trend",
        "swing_mean_reversion",
        "swing_breakout",
    }
    assert all(strategies[name].active is False for name in names)
    assert all(strategies[name].authorised_for_live is False for name in names)


def test_f31_f32_restart_does_not_authorise_live_orders() -> None:
    import forex_bot.live_safety as live_safety

    path = R4 / "synthetic_live_safety_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(path)
    assert live_safety.live_order_auth_state() == live_safety.AUTH_BLOCKED
    document = live_safety._blank_document(reason="r4-synthetic")
    document["live_order_authorisation"]["state"] = "ALLOWED"
    path.write_text(json.dumps(document), encoding="utf-8")
    live_safety.initialise_fail_closed()
    assert live_safety.live_order_auth_state() == live_safety.AUTH_BLOCKED
    assert live_safety.persisted_live_order_auth_state() == live_safety.AUTH_ALLOWED
    assert all(item.active is False for item in strategies.values())


def test_f33_valid_directions_still_reach_the_action_gate() -> None:
    calls, size, build, send = _spies()
    assert direction_action_gate("buy", size, build, send) == "BUY"
    assert direction_action_gate("SELL", size, build, send) == "SELL"
    assert calls == {"size": 2, "build": 2, "send": 2}
