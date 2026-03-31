"""Precedence tests for :func:`forex_bot.operational_state.derive_operational_state` and transition ring."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from forex_bot.operational_events import (
    get_operational_events,
    load_operational_events_cache_from_db,
    record_operational_transition_if_changed,
    reset_operational_events_for_tests,
)
from forex_bot.operational_state import OperationalState, derive_operational_state


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.delenv("PERSIST_OPERATIONAL_EVENTS", raising=False)
    monkeypatch.delenv("LOAD_OPERATIONAL_EVENTS_FROM_DB", raising=False)
    from forex_bot.state import state

    state["lifespan_phase"] = "offline"
    state["bot_status"] = "stopped"
    reset_operational_events_for_tests()
    yield
    state["lifespan_phase"] = "offline"


def test_precedence_offline_before_kill_switch():
    from forex_bot.state import state

    state["lifespan_phase"] = "offline"
    with (
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=True),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=False),
        patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=True),
    ):
        assert derive_operational_state() == OperationalState.OFFLINE


def test_precedence_starting_before_kill():
    from forex_bot.state import state

    state["lifespan_phase"] = "starting"
    with (
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=True),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=False),
        patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=True),
    ):
        assert derive_operational_state() == OperationalState.STARTING


def test_precedence_stopping():
    from forex_bot.state import state

    state["lifespan_phase"] = "stopping"
    with (
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=True),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=True),
    ):
        assert derive_operational_state() == OperationalState.STOPPING


def test_precedence_kill_switch_before_halt():
    from forex_bot.state import state

    state["lifespan_phase"] = "running"
    with (
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=True),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=True),
        patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=False),
    ):
        assert derive_operational_state() == OperationalState.KILL_SWITCH_ACTIVE


def test_precedence_halt_before_pre_trade():
    from forex_bot.state import state

    state["lifespan_phase"] = "running"
    with (
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=False),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=True),
        patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=True),
    ):
        assert derive_operational_state() == OperationalState.HALTED


def test_precedence_trading_allowed_when_open():
    from forex_bot.state import state

    state["lifespan_phase"] = "running"
    with (
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=False),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=False),
        patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=True),
    ):
        assert derive_operational_state() == OperationalState.TRADING_ALLOWED


def test_precedence_recovery_when_blocked():
    from forex_bot.state import state

    state["lifespan_phase"] = "running"
    with (
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=False),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=False),
        patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=False),
    ):
        assert derive_operational_state() == OperationalState.RECOVERY


def test_events_baseline_then_transition():
    from forex_bot.state import state

    state["lifespan_phase"] = "running"
    with (
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=False),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=False),
        patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=True),
    ):
        record_operational_transition_if_changed()
        assert get_operational_events() == []
        record_operational_transition_if_changed()
        assert get_operational_events() == []

        with (
            patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=False),
            patch("forex_bot.execution.pre_trade_entry_blocked_reason", return_value="reconcile_stale"),
        ):
            record_operational_transition_if_changed()
            ev = get_operational_events()
            assert len(ev) == 1
            assert ev[0]["from_state"] == "trading_allowed"
            assert ev[0]["to_state"] == "recovery"
            assert "reconcile_stale" in (ev[0].get("detail") or "")


def test_persist_calls_db_append(monkeypatch):
    monkeypatch.setenv("PERSIST_OPERATIONAL_EVENTS", "true")
    from forex_bot.state import state

    state["lifespan_phase"] = "running"
    reset_operational_events_for_tests()
    recorded: list[dict] = []

    def capture(**kwargs):
        recorded.append(kwargs)

    with (
        patch("forex_bot.database.append_operational_event_log", side_effect=capture),
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=False),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=False),
        patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=True),
    ):
        record_operational_transition_if_changed()
        record_operational_transition_if_changed()
        with (
            patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=False),
            patch("forex_bot.execution.pre_trade_entry_blocked_reason", return_value="reconcile_stale"),
        ):
            record_operational_transition_if_changed()
    assert len(recorded) == 1
    assert recorded[0]["to_state"] == "recovery"


def test_load_cache_from_db_sets_baseline(monkeypatch):
    monkeypatch.setenv("LOAD_OPERATIONAL_EVENTS_FROM_DB", "true")
    from forex_bot.state import state

    state["lifespan_phase"] = "running"
    reset_operational_events_for_tests()
    fake = [
        {
            "id": 1,
            "ts_utc": "2026-01-01T00:00:00+00:00",
            "from_state": "offline",
            "to_state": "trading_allowed",
            "detail": "pre_trade gate open (execution_mode=paper)",
        }
    ]
    with patch("forex_bot.database.fetch_recent_operational_event_logs", return_value=fake):
        load_operational_events_cache_from_db()
    assert len(get_operational_events()) == 1
    with (
        patch("forex_bot.operational_state.kill_switch_env_active", return_value=False),
        patch("forex_bot.operational_state.is_trading_halted_runtime", return_value=False),
        patch("forex_bot.operational_state.pre_trade_entry_allowed", return_value=True),
    ):
        record_operational_transition_if_changed()
    assert len(get_operational_events()) == 1
