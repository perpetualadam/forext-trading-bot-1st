"""Synthetic position-exposure checks for R.9.

These tests do not start the application, open PostgreSQL, or contact a broker.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import socket
import sys
from pathlib import Path

import pytest

from forex_bot.bot_loop import (
    _evaluate_impl,
    continue_entry_after_strategy_gate,
    direction_action_gate,
)
from forex_bot.database import (
    confirm_exposure_flat,
    exposure_entry_block_reason,
    exposure_marker_block_reason,
    fresh_intent_book,
    RESERVATION_BLOCK_SQL,
    insert_exec_order_pending_if_absent,
    interpret_close_evidence,
    new_intent_block_reason,
    note_unconfirmed_exposure,
    refuse_reservation_after_database_fault,
    reset_order_intent_gate_for_tests,
    restore_unresolved_intent,
)
from forex_bot.orders import (
    OrderStatus,
    finalize_order_fill,
    ingest_recovery_snapshot,
    orders_by_client_id,
    record_synthetic_fill_position,
    register_order,
    reset_orders_for_tests,
    try_begin_order_submission,
)
from forex_bot.orders import LocalOrder
from forex_bot.positions import close_position, get_position, positions
from forex_bot.strategy_meta import strategies

ROOT = Path(__file__).resolve().parents[1]
R9 = ROOT / "data" / "research" / "adaptive_ensemble" / "r9"
SYMBOL = "EUR_USD"
OTHER = "GBP_USD"

PROTECTED_SHA256 = {
    "forex_bot/app.py": '1883d3c94a570b66782b7079bcd64d7657c83c0cd6faa385cab7a65bc2d56bd1',
    "forex_bot/telegram_control.py": '0447f31e36b63ccc586391f1a1a3b04bc4d16445d1a0bcf405ca7f3e2bb4b6fe',
    "forex_bot/live_safety.py": 'e4310d1cd694c3f2a8791b308666fa15ae6ba1a82bdc67a99c5788ffe70ad546',
    "forex_bot/strategy_meta.py": 'b45b2f7e7f684686eddd2ddf9f2d6d1c3919678ec128c38665f38c99c3ab3222',
    "forex_bot/oanda_exec.py": 'e83bcc1095aba3f1c06cd625fb01fc0823698f348c0cd517d929928b559701c5',
    "requirements.txt": '94d0bc788c1daf61c08ee121197b7200b70e230340e9a6cc2662f4a360bf9bc0',
    "requirements-dev.txt": 'd91dbc6e9a32e53aed18c5d8101ecee4cf66501fb73508e928fac95434dc9346',
    "Dockerfile": 'f79288e0ae6787d709398b7abf81dfac02d9f82eaea4fb23135610767e5f2d86',
    ".dockerignore": '4b637ff8b7fb2dd6472446117b09276387154f773a7a7784fac62faeeece903e',
    "docker-compose.yml": '3c1dd01693215dffa7f0f956a0b744ae20c807425ce27757ab789e0616ea4d58',
}


def setup_function() -> None:
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    positions.clear()


def _row(status: str, client_order_id: str, symbol: str = SYMBOL, **extra: object) -> dict:
    row = {
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": "BUY",
        "units": 1,
        "status": status,
        "created_at": "2026-10-15T00:00:00+00:00",
    }
    row.update(extra)
    return row


def _reserve(client_order_id: str, symbol: str = SYMBOL) -> bool:
    return try_begin_order_submission(
        client_order_id=client_order_id,
        symbol=symbol,
        direction="BUY",
        units=1.0,
    )


def _hold_fill(client_order_id: str = "cid-fill") -> None:
    register_order(
        LocalOrder(
            client_order_id=client_order_id,
            symbol=SYMBOL,
            direction="BUY",
            units_requested=1,
            units_filled=0,
            status=OrderStatus.PENDING,
            avg_fill_price=None,
            created_ts=0,
        )
    )
    finalize_order_fill(
        client_order_id,
        broker_order_id="synthetic",
        fill_price=1.1,
        units_filled=1.0,
        status=OrderStatus.FILLED,
    )


def test_i01_i02_i10_complete_fill_records_position_and_still_blocks() -> None:
    assert record_synthetic_fill_position(
        symbol=SYMBOL, client_order_id="cid-1", direction="BUY", units=1, price=1.1
    ) == "recorded"
    assert get_position(SYMBOL) is not None
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    assert _reserve("cid-next") is False
    assert record_synthetic_fill_position(
        symbol=SYMBOL, client_order_id="cid-missing", direction="", units=0, price=0
    ) == "blocked"
    assert order_not_flat()


def order_not_flat() -> bool:
    from forex_bot.database import order_status_proves_exposure_closed

    assert order_status_proves_exposure_closed("FILLED") is False
    return True


def test_i03_i06_position_creation_or_malformed_fill_blocks() -> None:
    assert record_synthetic_fill_position(
        symbol=SYMBOL, client_order_id="", direction="BUY", units=1, price=1.1
    ) == "blocked"
    assert get_position(SYMBOL) is None
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    assert exposure_marker_block_reason("not-a-row") == "recovery_corrupt"


def test_i04_i05_persistence_failure_blocks() -> None:
    note_unconfirmed_exposure(SYMBOL, "cid-persist")
    refuse_reservation_after_database_fault()
    assert _reserve("cid-after-persist") is False
    source = inspect.getsource(finalize_order_fill)
    assert "refuse_reservation_after_database_fault" in source
    assert "UNCONFIRMED" in source


def test_i07_i08_i09_partial_duplicate_and_conflict() -> None:
    assert record_synthetic_fill_position(
        symbol=SYMBOL, client_order_id="cid-p", direction="BUY", units=0.4, price=1.1
    ) == "recorded"
    assert record_synthetic_fill_position(
        symbol=SYMBOL, client_order_id="cid-p", direction="BUY", units=0.4, price=1.1
    ) == "recorded"
    assert record_synthetic_fill_position(
        symbol=SYMBOL, client_order_id="cid-p", direction="BUY", units=0.9, price=1.1
    ) == "conflict"
    assert get_position(SYMBOL).units == 0.4
    assert _reserve("cid-after-partial") is False


def test_i11_i12_i17_open_or_missing_records_block() -> None:
    _hold_fill()
    assert orders_by_client_id["cid-fill"].status == OrderStatus.FILLED
    assert get_position(SYMBOL) is None
    assert _reserve("cid-no-position") is False
    record_synthetic_fill_position(
        symbol=SYMBOL, client_order_id="cid-pos", direction="BUY", units=2, price=1.2
    )
    orders_by_client_id.pop("cid-pos", None)
    assert get_position(SYMBOL) is not None
    assert _reserve("cid-while-open") is False


def test_i13_i15_corrupt_or_unknown_position_fails_closed() -> None:
    from forex_bot.database import OrderRecoveryUnreadable

    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot(
            [_row("FILLED", "cid-bad", metadata={"exposure_safety": "GUESS"})],
            True,
        )
    assert _reserve("cid-after-unknown") is False


def test_i14_i16_stale_snapshot_and_mismatch_fail_closed() -> None:
    from forex_bot.database import OrderRecoveryUnreadable

    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot([_row("FILLED", "cid-stale", snapshot_stale=True)], True)
    assert exposure_entry_block_reason(SYMBOL) == "recovery_unreadable"
    reset_order_intent_gate_for_tests()
    record_synthetic_fill_position(
        symbol=SYMBOL, client_order_id="cid-a", direction="BUY", units=1, price=1.1
    )
    assert record_synthetic_fill_position(
        symbol=SYMBOL, client_order_id="cid-b", direction="SELL", units=1, price=1.1
    ) == "conflict"


def test_i18_i19_i20_conflicts_repeat_and_other_symbol() -> None:
    first = ingest_recovery_snapshot(
        [_row("FILLED", "cid-fill", metadata={"exposure_safety": "UNCONFIRMED"})],
        True,
    )
    second = ingest_recovery_snapshot(
        [_row("FILLED", "cid-fill", metadata={"exposure_safety": "UNCONFIRMED"})],
        True,
    )
    assert first == 1
    assert second == 0
    assert _reserve("cid-eur-2") is False
    assert _reserve("cid-gbp", OTHER) is True
    assert get_position(OTHER) is None
    with pytest.raises(Exception):
        ingest_recovery_snapshot(
            [
                _row("FILLED", "cid-1"),
                _row("FILLED", "cid-1b", metadata={"exposure_safety": "NOT_A_MARKER"}),
            ],
            True,
        )


def test_i21_i26_i30_close_uncertainty_keeps_the_hold() -> None:
    note_unconfirmed_exposure(SYMBOL, "cid-open")
    for evidence in ("REQUESTED", "TIMEOUT", "CONNECTION_LOST", "PARTIAL", "REJECTED", "MALFORMED"):
        assert interpret_close_evidence(SYMBOL, evidence) == "exposure_unconfirmed"
    close_position(SYMBOL)
    assert get_position(SYMBOL) is None
    assert confirm_exposure_flat(SYMBOL, evidence="ABSENT") is False
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"


def test_i27_i28_i29_flat_token_is_narrow_and_idempotent() -> None:
    from forex_bot.database import restore_unresolved_intent

    note_unconfirmed_exposure(SYMBOL, "cid-eur")
    note_unconfirmed_exposure(OTHER, "cid-gbp")
    restore_unresolved_intent(OTHER, "cid-gbp-unresolved")
    assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False
    assert confirm_exposure_flat(OTHER, evidence="CONFIRMED_FLAT") is False
    assert exposure_entry_block_reason(OTHER) == "exposure_unconfirmed"
    book = fresh_intent_book()
    book["unresolved"][OTHER] = "cid-gbp-unresolved"
    book["exposure"][OTHER] = "cid-gbp"
    assert new_intent_block_reason(book, OTHER, [], True) == "unresolved_intent"


def test_i31_i34_restart_blocks_active_and_unconfirmed_fills() -> None:
    ingest_recovery_snapshot([_row("FILLED", "cid-filled")], True)
    assert _reserve("cid-after-filled") is False
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    ingest_recovery_snapshot([_row("PARTIAL", "cid-partial")], True)
    assert _reserve("cid-after-partial") is False
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    ingest_recovery_snapshot([_row("UNRESOLVED", "cid-open")], True)
    assert _reserve("cid-after-unresolved") is False
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    ingest_recovery_snapshot([_row("PENDING", "cid-pending")], True)
    assert _reserve("cid-after-pending") is False


def test_i35_i39_bad_recovery_and_repeat_loading() -> None:
    from forex_bot.database import OrderRecoveryUnreadable

    with pytest.raises(OrderRecoveryUnreadable):
        ingest_recovery_snapshot(None, False)
    assert _reserve("cid-after-failed-read") is False
    reset_order_intent_gate_for_tests()
    loaded = ingest_recovery_snapshot(
        [_row("FILLED", "cid-filled", metadata={"exposure_safety": "UNCONFIRMED"})],
        True,
    )
    again = ingest_recovery_snapshot(
        [_row("FILLED", "cid-filled", metadata={"exposure_safety": "UNCONFIRMED"})],
        True,
    )
    assert loaded == 1
    assert again == 0
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    book = fresh_intent_book()
    book["exposure"][SYMBOL] = "cid-filled"
    assert new_intent_block_reason(book, SYMBOL, [], False) == "recovery_unreadable"


def test_i40_flat_marker_cannot_clear_an_unresolved_order() -> None:
    ingest_recovery_snapshot(
        [
            _row("FILLED", "cid-filled", metadata={"exposure_safety": "CONFIRMED_FLAT"}),
            _row("UNRESOLVED", "cid-open"),
        ],
        True,
    )
    assert _reserve("cid-after-both") is False
    assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False


def test_i41_i44_reservation_policy_remains() -> None:
    assert _reserve("cid-pending") is True
    assert _reserve("cid-pending-2") is False
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    ingest_recovery_snapshot([_row("PARTIAL", "cid-partial")], True)
    assert _reserve("cid-partial-2") is False
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    ingest_recovery_snapshot([_row("UNRESOLVED", "cid-open")], True)
    assert _reserve("cid-open-2") is False
    assert new_intent_block_reason(
        fresh_intent_book(), SYMBOL, [{"symbol": SYMBOL, "status": "UNKNOWN"}], True
    ) == "recovery_corrupt"


def test_i45_i46_direction_and_strategy_gates() -> None:
    calls = {"size": 0}

    def size(*_args: object) -> None:
        calls["size"] += 1

    assert direction_action_gate("HOLD", size, None, None) is None
    assert continue_entry_after_strategy_gate(
        "scalp",
        active=False,
        authorised_for_live=False,
        safety_initialised=True,
        known_strategy=True,
        sizer=size,
        builder=None,
        sender=None,
        id_factory=None,
    ) is None
    assert calls["size"] == 0


def test_i47_live_authorisation_stays_blocked() -> None:
    import forex_bot.live_safety as live_safety

    path = R9 / "synthetic_live_safety_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(path)
    document = live_safety._blank_document(reason="r9-synthetic")
    document["live_order_authorisation"]["state"] = "ALLOWED"
    path.write_text(json.dumps(document), encoding="utf-8")
    live_safety.initialise_fail_closed()
    assert live_safety.live_order_auth_state() == live_safety.AUTH_BLOCKED
    assert all(item.active is False for item in strategies.values())


def test_i48_i53_refusal_isolation_and_dispatch_order() -> None:
    source = inspect.getsource(_evaluate_impl)
    exposure_at = source.index("exposure_entry_block_reason")
    reserve_at = source.index("try_begin_order_submission")
    send_at = source.index("legacy broker tail is not a dispatch path")
    assert exposure_at < reserve_at < send_at
    assert "execute_oanda_market_open" not in source
    note_unconfirmed_exposure(SYMBOL, "cid-held")
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    assert _reserve("cid-held-2") is False
    refuse_reservation_after_database_fault()
    assert _reserve("cid-db") is False
    assert "forex_bot.app" not in sys.modules
    assert os.environ["PERSIST_EXEC_ORDERS"] == "0"
    import forex_bot.database as database

    assert database._pg_conn is None
    with pytest.raises(RuntimeError, match="NETWORK_BLOCKED"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError, match="DNS_BLOCKED"):
        socket.getaddrinfo("example.invalid", 80)
    assert "execute_oanda" not in inspect.getsource(record_synthetic_fill_position)


def test_i54_protected_sources_are_unchanged() -> None:
    for relative, expected in PROTECTED_SHA256.items():
        digest = hashlib.sha256((ROOT / relative).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        assert digest == expected, relative
    source = inspect.getsource(insert_exec_order_pending_if_absent)
    assert "RESERVATION_BLOCK_SQL" in source
    assert "exposure_safety" in RESERVATION_BLOCK_SQL
    assert "FILLED" in RESERVATION_BLOCK_SQL
    assert source.index("pg_advisory_xact_lock") < source.index("INSERT INTO exec_orders")


@pytest.mark.skip(reason="POSTGRESQL_POSITION_PERSISTENCE_NOT_EVALUATED")
def test_i55_postgresql_position_persistence_not_evaluated() -> None:
    """Engine persistence was not run. This skip is not a pass."""


@pytest.mark.skip(reason="BROKER_FILL_RECONCILIATION_NOT_EVALUATED")
def test_i56_broker_fill_reconciliation_not_evaluated() -> None:
    """Broker reconciliation was not run. This skip is not a pass."""


@pytest.mark.skip(reason="APPLICATION_STARTUP_NOT_EVALUATED")
def test_i57_application_startup_not_evaluated() -> None:
    """Application startup was not run. This skip is not a pass."""


@pytest.mark.skip(reason="BROKER_POSITION_VERIFICATION_NOT_EVALUATED")
def test_i58_broker_position_verification_not_evaluated() -> None:
    """Broker position verification was not run. This skip is not a pass."""
