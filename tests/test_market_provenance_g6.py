"""Stage G.6 review tests. Mocked broker only. No network and no live authorisation."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from forex_bot.live_safety import (
    AUTH_BLOCKED,
    KNOWN_STRATEGY_NAMES,
    REASON_PERSISTED_ALLOWED_IGNORED,
    _blank_document,
    initialise_fail_closed,
    live_order_auth_reason,
    live_order_auth_state,
    state_path,
)
from forex_bot.market_provenance import (
    bind_live_frame,
    decision_frame_rejection,
    mint_live_quote,
    order_quote_rejection,
)
from forex_bot.oanda_client import official_rest_host
from forex_bot.strategy_meta import strategies


def _frame(close: float = 1.1) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    idx = pd.date_range(end - timedelta(minutes=150), periods=31, freq="5min", tz="UTC")
    px = [close + i * 0.00001 for i in range(31)]
    return pd.DataFrame(
        {
            "time": idx,
            "open": px,
            "high": [v + 0.00005 for v in px],
            "low": [v - 0.00005 for v in px],
            "close": px,
        }
    )


def _sealed(symbol: str = "EUR_USD") -> pd.DataFrame:
    return bind_live_frame(_frame(), instrument=symbol, host=official_rest_host())


def test_spoofed_copy_and_price_mutation_fail():
    original = _sealed()
    other = _sealed()
    other.loc[other.index[-1], "close"] = 1.5
    other.attrs["market_provenance"] = original.attrs["market_provenance"]
    assert decision_frame_rejection(other, "EUR_USD") == "tampered_payload"
    quote = mint_live_quote("EUR_USD")
    quote.bid = 1.05
    assert order_quote_rejection(quote, "EUR_USD") == "tampered_payload"
    quote_ask = mint_live_quote("EUR_USD")
    quote_ask.ask = 1.4
    assert order_quote_rejection(quote_ask, "EUR_USD") == "tampered_payload"


def test_earlier_bar_mutation_invalidates_seal():
    """Stage G.7: the first candle is part of the protected surface."""
    frame = _sealed()
    frame.loc[frame.index[0], "close"] = 9.0
    assert decision_frame_rejection(frame, "EUR_USD") == "tampered_payload"


def test_missing_provenance_blocks_open_and_not_close(monkeypatch):
    calls: list[dict] = []

    class FakeAPI:
        def request(self, req):
            calls.append(dict(req.data))
            side = "shortOrderFillTransaction" if "shortUnits" in req.data else "longOrderFillTransaction"
            return {side: {"price": "1.1", "pl": "0.1", "units": "1"}}

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", lambda: FakeAPI())
    monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    monkeypatch.setenv("OANDA_ACCESS_TOKEN", "not-a-real-token")
    from forex_bot.oanda_exec import (
        _place_market_order_open_sync,
        _place_market_order_sync,
    )

    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        _place_market_order_open_sync("EUR_USD", 1.0, "BUY", "cid", entry_quote=mint_live_quote())
    assert calls == []
    _place_market_order_sync("EUR_USD", 1.0, "BUY")
    assert calls == [{"longUnits": "1"}]
    calls.clear()
    _place_market_order_sync("EUR_USD", 2.0, "SELL")
    assert calls == [{"shortUnits": "2"}]
    assert live_order_auth_state() == AUTH_BLOCKED


def test_failed_close_is_not_reported_as_success(monkeypatch):
    class FakeAPI:
        def request(self, _req):
            raise TimeoutError("read timed out")

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", lambda: FakeAPI())
    monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    from forex_bot.oanda_exec import _place_market_order_sync

    with pytest.raises(RuntimeError, match="timed out"):
        _place_market_order_sync("EUR_USD", 1.0, "BUY")


def test_restart_ignores_persisted_allowed_and_keeps_strategies_inactive():
    doc = _blank_document(reason="review")
    doc["live_order_authorisation"]["state"] = "ALLOWED"
    for name in KNOWN_STRATEGY_NAMES:
        doc["strategies"][name]["active"] = False
    path = state_path()
    path.write_text(json.dumps(doc), encoding="utf-8")
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert live_order_auth_reason() == REASON_PERSISTED_ALLOWED_IGNORED
    assert all(strategies[name].active is False for name in KNOWN_STRATEGY_NAMES)


def test_research_import_does_not_authorise_orders():
    from forex_bot.research.adaptive_ensemble import runner

    assert runner.synthetic_market(20) is not None
    assert live_order_auth_state() == AUTH_BLOCKED


def test_mutation_surface_and_management_order():
    import forex_bot.oanda_exec as ox
    from forex_bot import bot_loop
    from forex_bot.live_manage import broker_sl_tp_hit

    exec_src = inspect.getsource(ox)
    assert exec_src.count("api.request") == 2
    assert "oanda_orders.OrderCancel" not in exec_src
    assert "OrderReplace" not in exec_src
    assert "TradeClose" not in exec_src
    loop_src = inspect.getsource(bot_loop._evaluate_impl)
    assert loop_src.find("if pos:") < loop_src.find("decision_frame_rejection")
    assert broker_sl_tp_hit(object()) is False


def test_g6_reports_keep_prior_hashes():
    from forex_bot.research.adaptive_ensemble.g6_review import (
        CLASSIFICATION,
        write_reports,
    )

    report = write_reports()
    assert report["baseline"]["protocol_verified"] is True
    assert report["baseline"]["g3_raw_verified"] is True
    assert report["baseline"]["docker_commands_issued"] is False
    assert report["g4"]["policy_verified"] is True
    assert report["g4"]["complete_common_sessions"] == 27
    assert report["readiness"]["classification"] == CLASSIFICATION
    assert report["readiness"]["trading_approved"] is False
    assert report["readiness"]["deployment_approved"] is False
