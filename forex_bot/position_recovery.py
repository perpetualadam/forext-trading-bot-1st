"""Durable bot-owned position records and conservative restart recovery.

The close journal and this table share one SQLite file. A commit of the position
row and a later in-memory publish are not one transaction. Recovery reads the
durable row and publishes only a matching, complete, bot-owned position.
Missing protection fields stay NULL and force quarantine. They are not filled
from the current market.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from forex_bot.close_journal import JournalUnavailable, _now, _units, active_journal
from forex_bot.positions import Position, _book_lock, position_management_permitted, positions

_MANAGED = frozenset({"paper", "simulated", "window_paper", "live", "synthetic"})
_PROTECTION = (
    "max_profit_pips",
    "profit_protection_active",
    "profit_protection_seeded",
    "profit_protection_exit_pips",
    "profit_protection_close_attempt_ts",
    "atr_at_entry_pips",
    "protect_activated_mfe_pips",
    "protect_activated_atr_pips",
    "protect_activated_giveback_pips",
    "protect_activated_exit_pips",
    "atr_fallback_used",
    "min_profit_pips",
    "max_adverse_pips",
    "entry_price",
    "stop_loss",
    "take_profit",
)
quarantined_positions: dict[str, Position] = {}


def reset_recovery_memory() -> None:
    quarantined_positions.clear()


def _text_number(value: Any, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise JournalUnavailable("incomplete_identity")
        return None
    return _units(value, required=True)


def _write_managed_position(journal, pos: Position, account_binding_value: str, entry_operation_id: str | None) -> None:
    """Write one managed row inside the caller's SQLite transaction."""
    if not position_management_permitted(pos):
        raise JournalUnavailable("ownership_refused")
    if bool(getattr(pos, "observation_only", False)):
        raise JournalUnavailable("ownership_refused")
    kind = (pos.execution_kind or "").strip().lower()
    if kind not in _MANAGED:
        raise JournalUnavailable("unknown_execution_kind")
    from forex_bot.broker_exit import local_broker_trade_ids

    trade_ids = local_broker_trade_ids(pos)
    if len(trade_ids) != 1:
        raise JournalUnavailable("trade_identity_unresolved")
    if not pos.position_instance_id or int(pos.position_generation or 0) < 1:
        raise JournalUnavailable("incomplete_identity")
    stamp = _now()
    payload = (
        pos.position_instance_id,
        int(pos.position_generation),
        account_binding_value,
        pos.symbol,
        trade_ids[0],
        (pos.direction or "").upper(),
        _text_number(pos.units, required=True),
        kind,
        "bot_managed",
        _text_number(pos.entry_price, required=True),
        _text_number(pos.stop_loss, required=True),
        _text_number(pos.take_profit, required=True),
        str(pos.open_time),
        pos.strategy_name,
        pos.rl_state,
        pos.client_order_id or "",
        pos.broker_order_id or "",
        1 if pos.broker_order else 0,
        "recorded",
        _text_number(pos.max_profit_pips, required=True),
        1 if pos.profit_protection_active else 0,
        1 if pos.profit_protection_seeded else 0,
        _text_number(pos.profit_protection_exit_pips, required=False),
        _text_number(pos.profit_protection_close_attempt_ts, required=True),
        _text_number(pos.atr_at_entry_pips, required=False),
        _text_number(pos.protect_activated_mfe_pips, required=False),
        _text_number(pos.protect_activated_atr_pips, required=False),
        _text_number(pos.protect_activated_giveback_pips, required=False),
        _text_number(pos.protect_activated_exit_pips, required=False),
        1 if pos.atr_fallback_used else 0,
        _text_number(pos.min_profit_pips, required=True),
        _text_number(pos.max_adverse_pips, required=True),
        entry_operation_id,
        stamp,
        stamp,
    )
    try:
            existing = journal._conn.execute(
                """
                SELECT trade_id, account_binding, position_generation
                  FROM managed_positions WHERE position_instance_id = ?
                """,
                (pos.position_instance_id,),
            ).fetchone()
            if existing is not None:
                if existing["trade_id"] != trade_ids[0] or existing["account_binding"] != account_binding_value:
                    raise JournalUnavailable("journal_position_disagreement")
                if int(existing["position_generation"]) > int(pos.position_generation):
                    raise JournalUnavailable("conflicting_generation")
                journal._conn.execute(
                    """
                    UPDATE managed_positions
                       SET position_generation = ?, units = ?, direction = ?, entry_price = ?,
                           stop_loss = ?, take_profit = ?, max_profit_pips = ?,
                           profit_protection_active = ?, profit_protection_seeded = ?,
                           profit_protection_exit_pips = ?, profit_protection_close_attempt_ts = ?,
                           atr_at_entry_pips = ?, protect_activated_mfe_pips = ?,
                           protect_activated_atr_pips = ?, protect_activated_giveback_pips = ?,
                           protect_activated_exit_pips = ?, atr_fallback_used = ?,
                           min_profit_pips = ?, max_adverse_pips = ?, updated_at = ?
                     WHERE position_instance_id = ?
                    """,
                    (
                        int(pos.position_generation),
                        _text_number(pos.units, required=True),
                        (pos.direction or "").upper(),
                        _text_number(pos.entry_price, required=True),
                        _text_number(pos.stop_loss, required=True),
                        _text_number(pos.take_profit, required=True),
                        _text_number(pos.max_profit_pips, required=True),
                        1 if pos.profit_protection_active else 0,
                        1 if pos.profit_protection_seeded else 0,
                        _text_number(pos.profit_protection_exit_pips, required=False),
                        _text_number(pos.profit_protection_close_attempt_ts, required=True),
                        _text_number(pos.atr_at_entry_pips, required=False),
                        _text_number(pos.protect_activated_mfe_pips, required=False),
                        _text_number(pos.protect_activated_atr_pips, required=False),
                        _text_number(pos.protect_activated_giveback_pips, required=False),
                        _text_number(pos.protect_activated_exit_pips, required=False),
                        1 if pos.atr_fallback_used else 0,
                        _text_number(pos.min_profit_pips, required=True),
                        _text_number(pos.max_adverse_pips, required=True),
                        stamp,
                        pos.position_instance_id,
                    ),
                )
            else:
                journal._conn.execute(
                    """
                    INSERT INTO managed_positions (
                        position_instance_id, position_generation, account_binding, instrument,
                        trade_id, direction, units, execution_kind, provenance, entry_price,
                        stop_loss, take_profit, open_time, strategy_name, rl_state,
                        client_order_id, broker_order_id, broker_order, management_status,
                        close_operation_id, max_profit_pips, profit_protection_active,
                        profit_protection_seeded, profit_protection_exit_pips,
                        profit_protection_close_attempt_ts, atr_at_entry_pips,
                        protect_activated_mfe_pips, protect_activated_atr_pips,
                        protect_activated_giveback_pips, protect_activated_exit_pips,
                        atr_fallback_used, min_profit_pips, max_adverse_pips, entry_operation_id,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL,
                              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
    except JournalUnavailable:
        raise
    except Exception as exc:
        if exc.__class__.__name__ == "IntegrityError":
            raise JournalUnavailable("duplicate_position_identity") from exc
        raise JournalUnavailable("persistence_failure") from exc


def persist_bot_position(
    pos: Position,
    account_binding_value: str,
    *,
    entry_operation_id: str | None = None,
) -> None:
    """Write one bot-managed position. Observation imports are refused."""
    journal = active_journal()
    with journal._lock:
        journal._begin()
        try:
            _write_managed_position(journal, pos, account_binding_value, entry_operation_id)
            journal._commit()
        except JournalUnavailable:
            journal._rollback()
            raise
        except Exception as exc:
            journal._rollback()
            raise JournalUnavailable("persistence_failure") from exc


def store_incomplete_position(row: dict[str, Any]) -> None:
    """Test and migration helper. NULL protection fields remain NULL."""
    journal = active_journal()
    stamp = _now()
    columns = [
        "position_instance_id",
        "position_generation",
        "account_binding",
        "instrument",
        "trade_id",
        "direction",
        "units",
        "execution_kind",
        "provenance",
        "entry_price",
        "stop_loss",
        "take_profit",
        "open_time",
        "strategy_name",
        "rl_state",
        "client_order_id",
        "broker_order_id",
        "broker_order",
        "management_status",
        "max_profit_pips",
        "profit_protection_active",
        "profit_protection_seeded",
        "profit_protection_exit_pips",
        "profit_protection_close_attempt_ts",
        "atr_at_entry_pips",
        "protect_activated_mfe_pips",
        "protect_activated_atr_pips",
        "protect_activated_giveback_pips",
        "protect_activated_exit_pips",
        "atr_fallback_used",
        "min_profit_pips",
        "max_adverse_pips",
        "created_at",
        "updated_at",
    ]
    values = [row.get(name) for name in columns[:-2]] + [stamp, stamp]
    placeholders = ", ".join("?" for _ in columns)
    journal._conn.execute(
        f"INSERT INTO managed_positions ({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )


def symbol_has_quarantined_exposure(symbol: str) -> bool:
    """True when this instrument has quarantined or unresolved close exposure.

    A missing journal session does not invent a block. An active journal that
    cannot be read fails closed.
    """
    from forex_bot.close_journal import JournalUnavailable, active_journal
    from forex_bot.symbols import normalize_oanda_symbol

    key = normalize_oanda_symbol(symbol)
    for pos in quarantined_positions.values():
        if normalize_oanda_symbol(getattr(pos, "symbol", "") or "") == key:
            return True
    try:
        journal = active_journal()
    except JournalUnavailable:
        return False
    try:
        return journal.blocking_instrument(key) is not None
    except JournalUnavailable:
        return True


def durable_positions() -> list[dict[str, Any]]:
    journal = active_journal()
    cursor = journal._conn.execute("SELECT * FROM managed_positions")
    return [dict(row) for row in cursor.fetchall()]


def _missing_protection(row: dict[str, Any]) -> bool:
    required = (
        "entry_price",
        "stop_loss",
        "take_profit",
        "max_profit_pips",
        "profit_protection_active",
        "profit_protection_close_attempt_ts",
        "min_profit_pips",
        "max_adverse_pips",
    )
    return any(row.get(name) is None for name in required)


def _activated_without_ratchet(row: dict[str, Any]) -> bool:
    """An activated ratchet cannot be rebuilt from a NULL stop."""
    active = row.get("profit_protection_active")
    if active in (None, 0, False, "0"):
        return False
    required = (
        "profit_protection_exit_pips",
        "protect_activated_mfe_pips",
        "protect_activated_atr_pips",
        "protect_activated_giveback_pips",
        "protect_activated_exit_pips",
    )
    return any(row.get(name) is None for name in required)


def _decision(state: str, reason: str, *, manageable: bool = False) -> dict[str, Any]:
    return {
        "state": state,
        "reason": reason,
        "manageable": manageable,
        "close_submission_count": 0,
        "delete_permitted": False,
        "operator_required": not manageable,
    }


def evaluate_durable_row(row: dict[str, Any], broker_view: dict[str, Any]) -> dict[str, Any]:
    """Classify one durable row. This does not submit a close or delete a position."""
    provenance = row.get("provenance") or ""
    if provenance != "bot_managed":
        return _decision("quarantined", provenance or "unknown_provenance")
    kind = (row.get("execution_kind") or "").strip().lower()
    if kind not in _MANAGED:
        return _decision("quarantined", "unknown_execution_kind")
    if _missing_protection(row):
        return _decision("quarantined", "missing_management_state")
    if _activated_without_ratchet(row):
        return _decision("quarantined", "missing_management_state")
    snapshot = str(broker_view.get("snapshot") or "UNAVAILABLE")
    if snapshot in {"INCOMPLETE", "MALFORMED", "REQUEST_FAILED", "STALE", "UNAVAILABLE", "UNKNOWN"}:
        return _decision("quarantined", "broker_snapshot_not_authoritative")
    if snapshot == "COMPLETE_EMPTY":
        return _decision("quarantined", "broker_flat_unattributed")
    trades = list(broker_view.get("trades") or [])
    same_instrument = [item for item in trades if item.get("instrument") == row["instrument"]]
    if len(same_instrument) != 1:
        return _decision("quarantined", "multiple_or_missing_trades")
    trade = same_instrument[0]
    if trade.get("account_binding") != row["account_binding"]:
        return _decision("quarantined", "account_mismatch")
    if trade.get("trade_id") != row["trade_id"]:
        return _decision("quarantined", "trade_id_mismatch")
    if str(trade.get("direction") or "").upper() != row["direction"]:
        return _decision("quarantined", "direction_mismatch")
    try:
        if Decimal(str(trade.get("units"))) != Decimal(str(row["units"])):
            return _decision("quarantined", "units_mismatch")
    except Exception:
        return _decision("quarantined", "units_mismatch")
    journal = active_journal()
    blocker = journal.blocking_trade(row["account_binding"], row["instrument"], row["trade_id"])
    if blocker is not None:
        state = blocker["confirmation_state"]
        if state == "CLOSE_FULLY_CONFIRMED":
            return _decision("awaiting_finalisation", "confirmed_close_not_finalised")
        if blocker["position_instance_id"] != row["position_instance_id"]:
            return _decision("quarantined", "journal_position_disagreement")
        return _decision("quarantined", f"outstanding_{state}")
    return _decision("restored_managed", "broker_trade_matches", manageable=True)


def _position_from_row(row: dict[str, Any], *, quarantine: bool) -> Position:
    def _num(name: str, default: float | None = None) -> float | None:
        value = row.get(name)
        if value is None:
            return default
        return float(value)

    pos = Position(
        symbol=row["instrument"],
        direction=row["direction"],
        units=float(row["units"]),
        entry_price=float(row["entry_price"] or 0),
        stop_loss=float(row["stop_loss"] or 0),
        take_profit=float(row["take_profit"] or 0),
        open_time=float(row["open_time"]),
        strategy_name=row["strategy_name"],
        rl_state=row["rl_state"],
        execution_kind=row["execution_kind"],
        client_order_id=row["client_order_id"] or "",
        broker_order_id=row["broker_order_id"] or "",
        broker_order=bool(row["broker_order"]),
        broker_trade_ids=row["trade_id"],
        position_instance_id=row["position_instance_id"],
        position_generation=int(row["position_generation"]),
        max_profit_pips=float(row["max_profit_pips"] or 0),
        profit_protection_active=bool(row["profit_protection_active"] or 0),
        profit_protection_seeded=bool(row["profit_protection_seeded"] or 0),
        profit_protection_close_attempt_ts=float(row["profit_protection_close_attempt_ts"] or 0),
        min_profit_pips=float(row["min_profit_pips"] or 0),
        max_adverse_pips=float(row["max_adverse_pips"] or 0),
        atr_at_entry_pips=_num("atr_at_entry_pips"),
        atr_fallback_used=bool(row["atr_fallback_used"] or 0),
        profit_protection_exit_pips=_num("profit_protection_exit_pips"),
        protect_activated_mfe_pips=_num("protect_activated_mfe_pips"),
        protect_activated_atr_pips=_num("protect_activated_atr_pips"),
        protect_activated_giveback_pips=_num("protect_activated_giveback_pips"),
        protect_activated_exit_pips=_num("protect_activated_exit_pips"),
    )
    pos.recovery_quarantine = quarantine
    if quarantine:
        pos.observation_only = True
    return pos


def publish_recovered(row: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    """Publish one durable row only while operational recovery authority is current."""
    from forex_bot.startup_recovery import (
        RECOVERY_COMPLETED,
        RECOVERY_COMPLETED_WITH_QUARANTINE,
        RECOVERY_IN_PROGRESS,
        current_fencing_epoch,
        recovery_fence_allows_publication,
        recovery_state,
    )

    session_active = recovery_state() in {
        RECOVERY_IN_PROGRESS,
        RECOVERY_COMPLETED,
        RECOVERY_COMPLETED_WITH_QUARANTINE,
    }
    if current_fencing_epoch() is not None and session_active and not recovery_fence_allows_publication():
        reason = "recovery_fence_lost"
    elif not recovery_fence_allows_publication():
        reason = "recovery_authority_absent"
    else:
        reason = ""
    if reason:
        refused = _decision("quarantined", reason)
        refused["published"] = "fence_refused"
        return refused
    return _place_recovered_position(row, decision)


def _place_recovered_position(row: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    """Write one reconstructed position. Callers decide whether authority is required."""
    pos = _position_from_row(row, quarantine=not decision["manageable"])
    if not decision["manageable"]:
        quarantined_positions[row["position_instance_id"]] = pos
        decision["published"] = "quarantine"
        return decision
    with _book_lock:
        current = positions.get(row["instrument"])
        if current is None:
            positions[row["instrument"]] = pos
            decision["published"] = "managed"
            return decision
        same = (
            current.position_instance_id == row["position_instance_id"]
            and int(current.position_generation or 0) == int(row["position_generation"])
        )
        if same:
            decision["published"] = "unchanged"
            return decision
        decision.update(_decision("quarantined", "replaced_local_position"))
        decision["published"] = "not_overwritten"
    quarantined_positions[row["position_instance_id"]] = pos
    return decision


def recover_managed_book(broker_view: dict[str, Any]) -> list[dict[str, Any]]:
    """Offline reconstruction of a durable book. This does not grant live management.

    Operational startup uses ``publish_recovered`` and therefore requires a fencing
    epoch. This function is not called by startup, entry capture, or the bot cycle.
    """
    active_journal()
    decisions = []
    for row in durable_positions():
        decision = evaluate_durable_row(row, broker_view)
        decisions.append(_place_recovered_position(row, decision))
    return decisions


def persist_protection_progress(pos: Position, account_binding_value: str) -> bool:
    """Write the latest protection state. A lower durable ratchet is refused."""
    if not pos.position_instance_id:
        return False
    current = None
    for row in durable_positions():
        if row["position_instance_id"] == pos.position_instance_id:
            current = row
            break
    if current is None:
        return False
    previous = current.get("profit_protection_exit_pips")
    proposed = pos.profit_protection_exit_pips
    if previous not in (None, "") and proposed is not None:
        if Decimal(str(proposed)) < Decimal(str(previous)):
            return False
    if int(current.get("profit_protection_active") or 0) and not pos.profit_protection_active:
        return False
    persist_bot_position(pos, account_binding_value, entry_operation_id=current.get("entry_operation_id"))
    return True


def classify_broker_discovery(provenance: str) -> dict[str, Any]:
    """A broker-only, manual, or unknown trade stays outside the managed book."""
    if provenance == "bot_managed":
        return _decision("not_a_discovery", "durable_record_required")
    return _decision("observation", provenance or "broker_only")
