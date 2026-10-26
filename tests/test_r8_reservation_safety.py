"""Synthetic reservation-safety checks for R.8.

These tests do not start the application, open PostgreSQL, or contact a broker.
A source assertion is not an executed database transaction.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import socket
import sys
import threading
from pathlib import Path

import pytest

from forex_bot.bot_loop import (
    _evaluate_impl,
    broker_entry_block_reason,
    continue_entry_after_strategy_gate,
    direction_action_gate,
)
from forex_bot.database import (
    UNRESOLVED_ORDER_STATUS,
    OrderRecoveryUnreadable,
    _symbol_reservation_lock_key,
    RESERVATION_BLOCK_SQL,
    insert_exec_order_pending_if_absent,
    new_intent_block_reason,
    order_status_proves_exposure_closed,
    fresh_intent_book,
    remember_ambiguous_outcome,
    refuse_reservation_after_database_fault,
    reservation_status_block_reason,
    reset_order_intent_gate_for_tests,
)
from forex_bot.orders import (
    OrderStatus,
    finalize_order_fill,
    ingest_recovery_snapshot,
    mark_order_failed_or_cancelled,
    orders_by_client_id,
    reset_orders_for_tests,
    try_begin_order_submission,
)
from forex_bot.strategy_meta import strategies

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "data" / "research" / "adaptive_ensemble" / "r8"
SYMBOL = "EUR_USD"
OTHER = "GBP_USD"

PROTECTED_SHA256 = {
    "forex_bot/bot_loop.py": "6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796",
    "forex_bot/app.py": "8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1",
    "forex_bot/telegram_control.py": "d32b560306fe2f86cc7c8ddbb40aa42842f071bd88ea513d77f172a6a0fadf4c",
    "forex_bot/live_safety.py": "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44",
    "forex_bot/strategy_meta.py": "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d",
    "requirements.txt": "45bc21ba5d8f336c0da5092024cee96103f0251d7c7f55e70056a7c55d194b0a",
    "requirements-dev.txt": "0562a6853549077197defb3cd8515521b843a041f2a735723ee2903790e3eef5",
    "Dockerfile": "4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad",
    ".dockerignore": "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd",
    "docker-compose.yml": "f0a374774c35b4c63dce23a837572886d1d53331fec388044bc5887367980179",
}


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
        metadata={"fixture": "r8"},
    )


def test_i01_first_pending_reservation_is_accepted() -> None:
    assert _reserve("cid-first") is True
    assert orders_by_client_id["cid-first"].status == OrderStatus.PENDING
    assert len(orders_by_client_id) == 1


def test_i02_i03_second_client_id_cannot_bypass_pending() -> None:
    assert _reserve("cid-first") is True
    assert _reserve("cid-second") is False
    assert "cid-second" not in orders_by_client_id
    assert len(orders_by_client_id) == 1


def test_i04_partial_blocks_a_duplicate() -> None:
    ingest_recovery_snapshot([_row("PARTIAL", "cid-partial")], True)
    assert _reserve("cid-after-partial") is False
    assert orders_by_client_id["cid-partial"].status == OrderStatus.PARTIAL


def test_i05_unresolved_blocks_a_duplicate() -> None:
    ingest_recovery_snapshot([_row(UNRESOLVED_ORDER_STATUS, "cid-open")], True)
    assert _reserve("cid-after-unresolved") is False


def test_i06_i07_unknown_or_corrupt_status_fails_closed() -> None:
    book = fresh_intent_book()
    assert (
        new_intent_block_reason(book, SYMBOL, [{"symbol": SYMBOL, "status": "UNKNOWN"}], True)
        == "recovery_corrupt"
    )
    assert reservation_status_block_reason("NOT_A_STATUS") == "unknown_status"
    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot([_row("NOT_A_STATUS", "cid-bad")], True)
    assert broker_entry_block_reason(SYMBOL) == "recovery_unreadable"
    assert _reserve("cid-after-corrupt") is False


def test_i08_i09_missing_or_failed_recovery_fails_closed() -> None:
    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot(None, False)
    assert broker_entry_block_reason(SYMBOL) == "recovery_unreadable"
    assert _reserve("cid-after-missing") is False
    reset_order_intent_gate_for_tests()
    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot([{"symbol": SYMBOL, "status": "PENDING"}], True)
    assert _reserve("cid-after-malformed") is False


def test_i10_i15_database_fault_refuses_another_reservation() -> None:
    refuse_reservation_after_database_fault()
    assert _reserve("cid-after-fault") is False
    assert "cid-after-fault" not in orders_by_client_id
    source = inspect.getsource(insert_exec_order_pending_if_absent)
    assert source.count("refuse_reservation_after_database_fault") >= 2
    _before_commit, after_commit = source.split("conn.commit()", 1)
    assert "refuse_reservation_after_database_fault" in after_commit


def test_i16_same_client_id_does_not_create_another_order() -> None:
    assert _reserve("cid-same") is True
    assert _reserve("cid-same") is False
    assert len(orders_by_client_id) == 1


def test_i17_restart_preserves_pending() -> None:
    ingest_recovery_snapshot([_row("PENDING", "cid-pending")], True)
    assert orders_by_client_id["cid-pending"].status == OrderStatus.PENDING
    assert _reserve("cid-after-restart") is False


def test_i18_restart_preserves_partial() -> None:
    ingest_recovery_snapshot([_row("PARTIAL", "cid-partial")], True)
    assert _reserve("cid-after-partial-restart") is False


def test_i19_restart_preserves_unresolved() -> None:
    ingest_recovery_snapshot([_row(UNRESOLVED_ORDER_STATUS, "cid-open")], True)
    assert orders_by_client_id["cid-open"].status == OrderStatus.UNRESOLVED
    assert _reserve("cid-after-unresolved-restart") is False


def test_i20_multiple_active_rows_block_entry() -> None:
    loaded = ingest_recovery_snapshot(
        [_row("PENDING", "cid-a"), _row("PARTIAL", "cid-b")],
        True,
    )
    assert loaded == 2
    assert _reserve("cid-third") is False


def test_i21_pending_to_unresolved_keeps_the_block() -> None:
    assert _reserve("cid-pending") is True
    remember_ambiguous_outcome(SYMBOL, "cid-pending")
    orders_by_client_id["cid-pending"].status = OrderStatus.UNRESOLVED
    assert _reserve("cid-next") is False
    assert orders_by_client_id["cid-pending"].status == OrderStatus.UNRESOLVED


def test_i22_partial_to_unresolved_keeps_the_block() -> None:
    ingest_recovery_snapshot([_row("PARTIAL", "cid-partial")], True)
    remember_ambiguous_outcome(SYMBOL, "cid-partial")
    orders_by_client_id["cid-partial"].status = OrderStatus.UNRESOLVED
    assert _reserve("cid-next") is False


def test_i23_cancelling_one_symbol_does_not_release_another() -> None:
    assert _reserve("cid-eur", SYMBOL) is True
    assert _reserve("cid-gbp", OTHER) is True
    mark_order_failed_or_cancelled("cid-eur")
    assert orders_by_client_id["cid-eur"].status == OrderStatus.CANCELLED
    assert _reserve("cid-gbp-2", OTHER) is False
    assert "cid-gbp-2" not in orders_by_client_id


def test_i24_cancellation_does_not_erase_unresolved() -> None:
    assert _reserve("cid-open") is True
    remember_ambiguous_outcome(SYMBOL, "cid-open")
    orders_by_client_id["cid-open"].status = OrderStatus.UNRESOLVED
    mark_order_failed_or_cancelled("cid-open")
    assert orders_by_client_id["cid-open"].status == OrderStatus.UNRESOLVED
    assert _reserve("cid-replacement") is False


def test_i25_fill_does_not_prove_exposure_is_closed() -> None:
    assert order_status_proves_exposure_closed("FILLED") is False
    assert order_status_proves_exposure_closed(OrderStatus.FILLED) is False
    assert order_status_proves_exposure_closed("PENDING") is False
    assert _reserve("cid-filled") is True
    finalize_order_fill(
        "cid-filled",
        broker_order_id="synthetic",
        fill_price=1.1,
        units_filled=1.0,
        status=OrderStatus.FILLED,
    )
    assert orders_by_client_id["cid-filled"].status == OrderStatus.FILLED
    assert "open_position" not in inspect.getsource(finalize_order_fill)
    source = inspect.getsource(_evaluate_impl)
    assert source.index("POSITION_ALREADY_OPEN") < source.index("try_begin_order_submission")
    assert order_status_proves_exposure_closed(orders_by_client_id["cid-filled"].status) is False


def test_i26_concurrent_synthetic_reservations_cannot_both_succeed() -> None:
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
    assert sorted(results) == [False, True]
    assert len(orders_by_client_id) == 1


def test_i27_check_and_insert_share_one_source_transaction() -> None:
    source = inspect.getsource(insert_exec_order_pending_if_absent)
    lock_at = source.index("pg_advisory_xact_lock")
    check_at = source.index("RESERVATION_BLOCK_SQL")
    insert_at = source.index("INSERT INTO exec_orders")
    commit_at = source.index("conn.commit()")
    assert lock_at < check_at < insert_at < commit_at
    assert source.count("conn.commit()") == 1
    assert "status NOT IN" in RESERVATION_BLOCK_SQL
    assert "FILLED" in RESERVATION_BLOCK_SQL
    assert "exposure_safety" in RESERVATION_BLOCK_SQL


def test_i28_different_symbols_use_distinct_keys() -> None:
    assert _symbol_reservation_lock_key(SYMBOL) != _symbol_reservation_lock_key(OTHER)
    assert _reserve("cid-eur", SYMBOL) is True
    assert _reserve("cid-gbp", OTHER) is True
    assert set(orders_by_client_id) == {"cid-eur", "cid-gbp"}


def test_i29_i30_refusal_stays_before_broker_dispatch() -> None:
    source = inspect.getsource(_evaluate_impl)
    block_at = source.index("broker_entry_block_reason")
    reserve_at = source.index("try_begin_order_submission")
    send_at = source.index("legacy broker tail is not a dispatch path")
    assert block_at < reserve_at < send_at
    assert "execute_oanda_market_open" not in source
    assert _reserve("cid-held") is True
    sent: list[str] = []
    if broker_entry_block_reason(SYMBOL):
        pass
    elif not _reserve("cid-held-2"):
        pass
    else:
        sent.append("broker")
    assert sent == []
    assert "cid-held-2" not in orders_by_client_id


def test_i31_invalid_direction_stops_before_sizing() -> None:
    calls = {"size": 0, "send": 0}

    def size(_direction: str) -> None:
        calls["size"] += 1

    def send(_direction: str) -> None:
        calls["send"] += 1

    assert direction_action_gate("HOLD", size, None, send) is None
    assert calls == {"size": 0, "send": 0}


def test_i32_inactive_strategy_stops_before_sizing() -> None:
    calls = {"size": 0}

    def size() -> None:
        calls["size"] += 1

    assert (
        continue_entry_after_strategy_gate(
            "scalp",
            active=False,
            authorised_for_live=False,
            safety_initialised=True,
            known_strategy=True,
            sizer=size,
            builder=None,
            sender=None,
            id_factory=None,
        )
        is None
    )
    assert calls["size"] == 0


def test_i33_live_authorisation_stays_blocked() -> None:
    import forex_bot.live_safety as live_safety

    path = R8 / "synthetic_live_safety_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(path)
    document = live_safety._blank_document(reason="r8-synthetic")
    document["live_order_authorisation"]["state"] = "ALLOWED"
    path.write_text(json.dumps(document), encoding="utf-8")
    live_safety.initialise_fail_closed()
    assert live_safety.live_order_auth_state() == live_safety.AUTH_BLOCKED
    assert all(item.active is False for item in strategies.values())


def test_i34_i37_no_broker_startup_database_or_network() -> None:
    assert "forex_bot.app" not in sys.modules
    assert os.environ["PERSIST_EXEC_ORDERS"] == "0"
    import forex_bot.database as database

    assert database._pg_conn is None
    with pytest.raises(RuntimeError, match="NETWORK_BLOCKED"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError, match="DNS_BLOCKED"):
        socket.getaddrinfo("example.invalid", 80)


def test_i38_protected_sources_are_unchanged() -> None:
    for relative, expected in PROTECTED_SHA256.items():
        digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert digest == expected, relative


@pytest.mark.skip(reason="POSTGRESQL_ENGINE_NOT_EVALUATED")
def test_i39_postgresql_engine_concurrency_not_evaluated() -> None:
    """Engine concurrency was not run. This skip is not a pass."""


@pytest.mark.skip(reason="POSTGRESQL_PERSISTENCE_NOT_EVALUATED")
def test_i40_postgresql_persistence_not_evaluated() -> None:
    """Engine persistence was not run. This skip is not a pass."""
