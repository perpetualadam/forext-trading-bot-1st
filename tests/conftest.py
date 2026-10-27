"""Default test env: do not inherit local .env live/notional overrides."""

from __future__ import annotations

import pytest

# These modules install a process-wide network barrier during import, or they
# refuse to import unless that barrier is already installed. Stage runners
# execute them. The shared CI process must not import them.
collect_ignore = [
    "test_r10_offline_startup.py",
    "test_r11_historical_recovery.py",
    "test_r26_broker_reconciliation.py",
    "test_r27_oanda_account_contract.py",
    "test_r29_scalp_readiness.py",
    "test_r30_scalp_lifecycle.py",
    "test_r31_strategy_screening.py",
    "test_r32_signal_diagnostics.py",
    "test_r33_ai_rl_audit.py",
    "test_r34_stub_removal.py",
]


@pytest.fixture(autouse=True)
def _isolate_sizing_env(monkeypatch):
    monkeypatch.delenv("POSITION_NOTIONAL_PCT_OF_NAV", raising=False)
    monkeypatch.delenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", raising=False)
    monkeypatch.delenv("MAX_GROSS_USD_NOTIONAL", raising=False)
    monkeypatch.delenv("POSITION_RISK_PCT", raising=False)
    monkeypatch.delenv("POSITION_RISK_PCT_MAX", raising=False)
    monkeypatch.delenv("MIN_STOP_DISTANCE_PRICE", raising=False)
    monkeypatch.delenv("FX_SESSION_ALWAYS", raising=False)
    monkeypatch.delenv("FOREX_SYMBOLS", raising=False)
    monkeypatch.delenv("MAX_SAME_USD_DIRECTION_POSITIONS", raising=False)
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("USE_OANDA_LIVE", "false")
    monkeypatch.setenv("TELEGRAM_COMMANDS", "false")
    monkeypatch.setenv("TELEGRAM_INBOUND", "0")
    monkeypatch.setenv("DECISION_SKIP_LOG_INTERVAL_SEC", "0")


@pytest.fixture(autouse=True)
def _isolate_live_safety(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_SAFETY_STATE_PATH", str(tmp_path / "live_safety_state.json"))
    monkeypatch.setenv("DECISION_REPAIR_SELECT_CURSOR_PATH", str(tmp_path / "select_cursor.json"))
    monkeypatch.setenv("DECISION_REPAIR_RISK_PATH", str(tmp_path / "account_risk.json"))
    monkeypatch.setenv("DECISION_REPAIR_AUDIT_PATH", str(tmp_path / "decisions.jsonl"))
    from forex_bot.decision_skip_log import reset_skip_log_for_tests
    from forex_bot.live_safety import (
        reset_live_safety_for_tests,
        restore_strategy_runtime_defaults_for_tests,
    )
    from forex_bot.strategy_meta import strategies

    reset_live_safety_for_tests()
    reset_skip_log_for_tests()
    restore_strategy_runtime_defaults_for_tests()
    # The legacy helper predates inactive defaults. Each test must explicitly
    # activate its own synthetic strategy; collection order must grant nothing.
    for strat in strategies.values():
        strat.active = False
    pnl_before = {name: list(strat.pnl) for name, strat in strategies.items()}
    yield
    reset_live_safety_for_tests()
    reset_skip_log_for_tests()
    restore_strategy_runtime_defaults_for_tests()
    for name, strat in strategies.items():
        strat.active = False
        if name in pnl_before:
            strat.pnl[:] = pnl_before[name]


@pytest.fixture
def allow_live_order_create():
    """Process-lifetime operator grant via the real API. Not a production HTTP/Telegram path."""
    from forex_bot.live_safety import (
        AUTH_ALLOWED,
        initialise_fail_closed,
        operator_set_live_order_authorisation,
    )

    initialise_fail_closed()
    operator_set_live_order_authorisation(
        state=AUTH_ALLOWED,
        reason="pytest_process_lifetime_operator",
        operator_confirmed=True,
    )
