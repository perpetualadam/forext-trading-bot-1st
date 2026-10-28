"""Stage G.5 adversarial provenance tests. No network and no live authorisation."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from forex_bot.live_safety import AUTH_BLOCKED, live_order_auth_state
from forex_bot.market_provenance import (
    CACHED_UNVERIFIED,
    CANDLE_ENDPOINT,
    IMPORTED_UNVERIFIED,
    OANDA_HISTORICAL_VERIFIED,
    OANDA_LIVE_VERIFIED,
    PRICING_ENDPOINT,
    SYNTHETIC_TEST,
    Provenance,
    ProvenanceRejected,
    bind_historical_frame,
    bind_imported_frame,
    bind_live_frame,
    bind_synthetic_frame,
    decision_frame_rejection,
    downgrade_cached,
    mint_live_quote,
    order_quote_rejection,
    provenance_from_label,
    require_order_quote,
)
from forex_bot.oanda_client import official_rest_host
from forex_bot.research.adaptive_ensemble.g5_audit import (
    PACKAGE_HASH,
    POLICY_HASH,
    write_reports,
)
from forex_bot.research.adaptive_ensemble.runner import synthetic_market
from forex_bot.state import set_pricing_snapshot


def _frame(last: datetime | None = None, close: float = 1.10000) -> pd.DataFrame:
    end = last or datetime.now(timezone.utc)
    idx = pd.date_range(end - timedelta(minutes=5 * 30), periods=31, freq="5min", tz="UTC")
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


def _live_frame(symbol: str = "EUR_USD") -> pd.DataFrame:
    frame = _frame()
    return bind_live_frame(frame, instrument=symbol, host=official_rest_host(), endpoint=CANDLE_ENDPOINT)


def test_network_client_is_not_imported_for_labels():
    with pytest.raises(ProvenanceRejected, match="caller_supplied_label"):
        provenance_from_label(OANDA_LIVE_VERIFIED)


def test_synthetic_current_price_is_rejected():
    frame = synthetic_market(40)
    frame.loc[frame.index[-1], "time"] = datetime.now(timezone.utc)
    reason = decision_frame_rejection(frame, "EUR_USD")
    assert reason == SYNTHETIC_TEST
    with pytest.raises(ProvenanceRejected):
        require_order_quote(None, "EUR_USD")


def test_spoofed_live_label_and_dict_are_rejected():
    with pytest.raises(ProvenanceRejected, match="spoofed_live_classification"):
        Provenance(OANDA_LIVE_VERIFIED, instrument="EUR_USD", host=official_rest_host(), endpoint=CANDLE_ENDPOINT, content_sha256="x", acquired_mono=time.monotonic())
    frame = _frame()
    frame.attrs["market_provenance"] = {"classification": OANDA_LIVE_VERIFIED}
    assert decision_frame_rejection(frame, "EUR_USD") == "invalid_provenance"


def test_historical_replay_with_current_timestamp_stays_historical():
    frame = _frame(last=datetime.now(timezone.utc))
    bind_historical_frame(frame, instrument="EUR_USD", host=official_rest_host())
    assert decision_frame_rejection(frame, "EUR_USD") == OANDA_HISTORICAL_VERIFIED


def test_missing_and_invalid_provenance():
    assert decision_frame_rejection(None, "EUR_USD") == "missing_provenance"
    assert decision_frame_rejection(_frame(), "EUR_USD") == "missing_provenance"
    frame = _live_frame()
    frame.attrs["market_provenance"] = "OANDA_LIVE_VERIFIED"
    assert decision_frame_rejection(frame, "EUR_USD") == "invalid_provenance"


def test_stale_future_and_tampered_bars():
    stale = _frame(last=datetime.now(timezone.utc) - timedelta(hours=2))
    bind_live_frame(stale, instrument="EUR_USD", host=official_rest_host())
    assert decision_frame_rejection(stale, "EUR_USD") == "stale_bar"
    future = _frame(last=datetime.now(timezone.utc) + timedelta(minutes=30))
    bind_live_frame(future, instrument="EUR_USD", host=official_rest_host())
    assert decision_frame_rejection(future, "EUR_USD") == "future_timestamp"
    live = _live_frame()
    live.loc[live.index[-1], "close"] = 9.9
    assert decision_frame_rejection(live, "EUR_USD") == "tampered_payload"
    aged = _live_frame()
    aged.attrs["market_provenance"].acquired_mono = time.monotonic() - 1000
    assert decision_frame_rejection(aged, "EUR_USD") == "stale_acquisition"


def test_quote_bid_ask_host_and_instrument():
    missing_bid = mint_live_quote("EUR_USD")
    missing_bid.bid = None
    assert order_quote_rejection(missing_bid, "EUR_USD") == "invalid_bid_ask"
    missing_ask = mint_live_quote("EUR_USD")
    missing_ask.ask = None
    assert order_quote_rejection(missing_ask, "EUR_USD") == "invalid_bid_ask"
    crossed = mint_live_quote("EUR_USD", bid=1.2, ask=1.1)
    assert order_quote_rejection(crossed, "EUR_USD") == "crossed_bid_ask"
    bad = mint_live_quote("EUR_USD")
    bad.bid = float("nan")
    assert order_quote_rejection(bad, "EUR_USD") == "nonfinite_price"
    stale = mint_live_quote("EUR_USD", acquired_mono=time.monotonic() - 60)
    assert order_quote_rejection(stale, "EUR_USD") == "stale_acquisition"
    other = mint_live_quote("GBP_USD")
    assert order_quote_rejection(other, "EUR_USD") == "unexpected_instrument"
    evil = mint_live_quote("EUR_USD", host="https://evil.example")
    assert order_quote_rejection(evil, "EUR_USD") == "unexpected_host"
    wrong_ep = mint_live_quote("EUR_USD")
    wrong_ep.provenance.endpoint = CANDLE_ENDPOINT
    assert order_quote_rejection(wrong_ep, "EUR_USD") == "unexpected_endpoint"


def test_cache_and_csv_and_research_substitution(tmp_path):
    quote = mint_live_quote("EUR_USD")
    set_pricing_snapshot({"EUR_USD": quote})
    assert order_quote_rejection(quote, "EUR_USD") == CACHED_UNVERIFIED
    downgraded = downgrade_cached(mint_live_quote("EUR_USD"))
    assert downgraded.provenance.classification == CACHED_UNVERIFIED
    csv_path = tmp_path / "EUR_USD_M5.csv"
    raw = _frame()
    raw.to_csv(csv_path, index=False)
    from forex_bot.csv_ohlcv import load_ohlcv_csv

    loaded = load_ohlcv_csv(csv_path)
    assert decision_frame_rejection(loaded, "EUR_USD") == IMPORTED_UNVERIFIED
    research_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "research"
        / "adaptive_ensemble"
        / "g3"
        / "normalized"
        / "EUR_USD_M5.csv"
    )
    with pytest.raises(ValueError):
        load_ohlcv_csv(research_path)
    research = _frame(last=datetime.now(timezone.utc))
    bind_imported_frame(research, source="data/research/adaptive_ensemble/g3/normalized/EUR_USD_M5.csv")
    assert decision_frame_rejection(research, "EUR_USD") == IMPORTED_UNVERIFIED
    assert bind_synthetic_frame(_frame()).attrs["market_provenance"].classification == SYNTHETIC_TEST


def test_failed_response_and_order_boundary_without_context(monkeypatch, entry_intent_factory):
    calls: list[str] = []

    def sink(*_a, **_k):
        calls.append("order")
        raise AssertionError("order sink")

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", sink)
    from forex_bot.oanda_exec import _place_market_order_open_sync

    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        _place_market_order_open_sync("EUR_USD", 1.0, "BUY", "cid", entry_quote=mint_live_quote(), entry_permit=entry_intent_factory(units=1, client_order_id="cid"))
    assert calls == []
    assert live_order_auth_state() == AUTH_BLOCKED
    assert order_quote_rejection(mint_live_quote(), "EUR_USD") is None


def test_authorised_sink_still_needs_a_sealed_quote(monkeypatch, allow_live_order_create, entry_intent_factory):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    monkeypatch.setenv("OANDA_ACCESS_TOKEN", "not-a-real-token")
    calls: list[str] = []

    class FakeAPI:
        def request(self, _r):
            calls.append("order")
            return {
                "orderCreateTransaction": {"id": "10", "clientExtensions": {"id": "cid-ok"}},
                "orderFillTransaction": {
                    "id": "11",
                    "price": "1.10000",
                    "units": "1",
                    "pl": "0",
                    "time": "2026-10-09T07:00:00.000000000Z",
                    "clientExtensions": {"id": "cid-ok"},
                },
                "relatedTransactionIDs": ["10", "11"],
                "lastTransactionID": "11",
            }

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", lambda: FakeAPI())
    monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    from forex_bot.oanda_exec import _place_market_order_open_sync

    with pytest.raises(ProvenanceRejected, match="missing_provenance"):
        _place_market_order_open_sync("EUR_USD", 1.0, "BUY", "cid-missing", entry_permit=entry_intent_factory(units=1, client_order_id="cid-missing"))
    assert calls == []
    _place_market_order_open_sync(
        "EUR_USD",
        1.0,
        "BUY",
        "cid-ok",
        entry_quote=mint_live_quote(),
        entry_permit=entry_intent_factory(units=1, client_order_id="cid-ok"),
    )
    assert calls == ["order"]


def test_bot_loop_does_not_scan_research_paths():
    import inspect

    from forex_bot import bot_loop
    from forex_bot import oanda_exec as ox

    src = inspect.getsource(bot_loop) + inspect.getsource(ox)
    assert "data/research" not in src
    assert "load_ohlcv_csv" not in src
    import ast
    tree = ast.parse(src)
    assert not any(isinstance(node, ast.ImportFrom) and "synthetic_market" in (node.module or "") for node in ast.walk(tree))
    assert not any(isinstance(node, ast.Name) and node.id == "synthetic_market" for node in ast.walk(tree))
    assert "synthetic_market_data_is_not_broker_verified" in src


def test_g5_reports_preserve_prior_hashes():
    report = write_reports()
    assert report["baseline"]["protocol_verified"] is True
    assert report["baseline"]["g3_raw_verified"] is True
    assert report["g4"]["policy_hash"] == POLICY_HASH
    assert report["g4"]["package_hash"] == PACKAGE_HASH
    assert report["g4"]["complete_common_sessions"] == 27
    assert report["g4"]["remaining_to_40"] == 13
    assert report["g4"]["strategy_evaluation_performed"] is False
    assert report["readiness"]["classification"] == "PROVENANCE_BOUNDARY_IMPLEMENTED_UNDEPLOYED"
    assert report["readiness"]["trading_approved"] is False


def test_quote_endpoint_constant_is_pricing():
    quote = mint_live_quote("EUR_USD")
    assert quote.provenance.endpoint == PRICING_ENDPOINT
    assert quote.provenance.production_eligible is True
