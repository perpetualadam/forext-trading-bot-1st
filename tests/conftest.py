"""Default test env: do not inherit local .env live/notional overrides."""

from __future__ import annotations

import pytest


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
