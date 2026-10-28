"""Stage G.7 adversarial provenance tests. Mocked broker only. No network."""

from __future__ import annotations

import copy
import inspect
import json
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from forex_bot.live_manage import (
    ManageQuote,
    broker_sl_tp_hit,
    resolve_broker_manage_price,
)
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
    MODEL_VERSION,
    PREVIOUS_MODEL_VERSION,
    ProvenanceRejected,
    bind_historical_frame,
    bind_live_frame,
    bind_synthetic_frame,
    decision_frame_rejection,
    mint_live_quote,
    provenance_from_label,
)
from forex_bot.oanda_client import official_rest_host
from forex_bot.strategy_meta import strategies


def _frame() -> pd.DataFrame:
    end = datetime.now(timezone.utc).replace(microsecond=0)
    idx = pd.date_range(end - timedelta(minutes=25), periods=6, freq="5min", tz="UTC")
    px = [1.10 + i * 0.0001 for i in range(6)]
    return pd.DataFrame(
        {
            "time": list(idx),
            "open": px,
            "high": [v + 0.0002 for v in px],
            "low": [v - 0.0002 for v in px],
            "close": [v + 0.00005 for v in px],
            "complete": [True] * 6,
            "volume": [100 + i for i in range(6)],
        }
    )


def _sealed() -> pd.DataFrame:
    return bind_live_frame(_frame(), instrument="EUR_USD", host=official_rest_host())


def _clone(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy(deep=True)
    out.attrs["market_provenance"] = frame.attrs["market_provenance"]
    return out


def _install_sink(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def _api() -> None:
        calls.append("api")

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", _api)
    monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    monkeypatch.setenv("OANDA_ACCESS_TOKEN", "not-a-real-token")
    return calls


def _assert_no_exposure(calls: list[str], permit) -> None:
    from forex_bot.oanda_exec import _place_market_order_open_sync

    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        _place_market_order_open_sync(
            "EUR_USD",
            1.0,
            "BUY",
            "cid",
            entry_quote=mint_live_quote(),
            entry_permit=permit,
        )
    assert calls == []
    assert live_order_auth_state() == AUTH_BLOCKED


def test_every_protected_mutation_fails_closed(monkeypatch: pytest.MonkeyPatch, entry_intent_factory) -> None:
    calls = _install_sink(monkeypatch)
    permit = entry_intent_factory(units=1, client_order_id="cid")
    base = _sealed()
    cases: list[tuple[str, pd.DataFrame, str]] = []

    first = _clone(base)
    first.loc[first.index[0], "open"] = 1.05
    cases.append(("first_open", first, "tampered_payload"))

    middle = _clone(base)
    middle.loc[middle.index[2], "high"] = 1.5
    cases.append(("middle_high", middle, "tampered_payload"))

    penultimate = _clone(base)
    penultimate.loc[penultimate.index[-2], "low"] = 1.01
    cases.append(("penultimate_low", penultimate, "tampered_payload"))

    final = _clone(base)
    final.loc[final.index[-1], "close"] = 1.4
    cases.append(("final_close", final, "tampered_payload"))

    stamped = _clone(base)
    stamped.loc[stamped.index[1], "time"] = stamped.loc[stamped.index[1], "time"] + timedelta(minutes=1)
    cases.append(("timestamp", stamped, "tampered_payload"))

    reversed_frame = base.iloc[::-1].reset_index(drop=True)
    reversed_frame.attrs["market_provenance"] = base.attrs["market_provenance"]
    cases.append(("reversed", reversed_frame, "tampered_payload"))

    inserted_row = base.iloc[[2]].copy()
    inserted_row["open"] = 1.2
    inserted = pd.concat([base.iloc[:2], inserted_row, base.iloc[2:]], ignore_index=True)
    inserted.attrs["market_provenance"] = base.attrs["market_provenance"]
    cases.append(("inserted", inserted, "tampered_payload"))

    removed = base.drop(index=base.index[1]).reset_index(drop=True)
    removed.attrs["market_provenance"] = base.attrs["market_provenance"]
    cases.append(("removed", removed, "tampered_payload"))

    duplicated = pd.concat([base, base.iloc[[3]]], ignore_index=True)
    duplicated.attrs["market_provenance"] = base.attrs["market_provenance"]
    cases.append(("duplicated", duplicated, "tampered_payload"))

    missing = _clone(base)
    missing.loc[missing.index[2], "volume"] = None
    cases.append(("missing_volume", missing, "tampered_payload"))

    nan_frame = _clone(base)
    nan_frame.loc[nan_frame.index[2], "close"] = float("nan")
    cases.append(("nan", nan_frame, "nonfinite_price"))

    infinite = _clone(base)
    infinite.loc[infinite.index[3], "high"] = float("inf")
    cases.append(("infinity", infinite, "nonfinite_price"))

    dropped_col = _clone(base).drop(columns=["volume"])
    dropped_col.attrs["market_provenance"] = base.attrs["market_provenance"]
    cases.append(("column_removed", dropped_col, "missing_protected_column"))

    other_instrument = _clone(base)
    cases.append(("instrument", other_instrument, "unexpected_instrument"))

    basis = _clone(base)
    basis["bid_close"] = basis["close"]
    cases.append(("price_basis", basis, "unexpected_protected_column"))

    volume = _clone(base)
    volume.loc[volume.index[4], "volume"] = 999
    cases.append(("volume", volume, "tampered_payload"))

    complete = _clone(base)
    complete.loc[complete.index[1], "complete"] = False
    cases.append(("complete", complete, "tampered_payload"))

    copied = _frame()
    copied.loc[copied.index[-1], "close"] = 1.8
    bind_live_frame(copied, instrument="EUR_USD", host=official_rest_host())
    copied.attrs["market_provenance"] = base.attrs["market_provenance"]
    cases.append(("copied_seal", copied, "tampered_payload"))

    old = _clone(base)
    old_seal = copy.copy(base.attrs["market_provenance"])
    old_seal.model_version = PREVIOUS_MODEL_VERSION
    old.attrs["market_provenance"] = old_seal
    cases.append(("old_version", old, "old_provenance_version"))

    synthetic = bind_synthetic_frame(_frame())
    cases.append(("synthetic", synthetic, "SYNTHETIC_TEST"))

    historical = bind_historical_frame(_frame(), instrument="EUR_USD", host=official_rest_host())
    cases.append(("historical_replay", historical, "OANDA_HISTORICAL_VERIFIED"))

    for name, frame, expected in cases:
        symbol = "GBP_USD" if name == "instrument" else "EUR_USD"
        got = decision_frame_rejection(frame, symbol)
        assert got == expected, name
        _assert_no_exposure(calls, permit)


def test_derived_columns_and_unchanged_copy_stay_valid(monkeypatch: pytest.MonkeyPatch, entry_intent_factory) -> None:
    calls = _install_sink(monkeypatch)
    permit = entry_intent_factory(units=1, client_order_id="cid")
    base = _sealed()
    derived = _clone(base)
    derived["ma_fast"] = 1.1
    derived["rsi"] = 50.0
    assert decision_frame_rejection(derived, "EUR_USD") is None
    copied = base.copy(deep=True)
    if "market_provenance" not in copied.attrs:
        copied.attrs["market_provenance"] = base.attrs["market_provenance"]
    assert decision_frame_rejection(copied, "EUR_USD") is None
    assert copied.attrs["market_provenance"].model_version == MODEL_VERSION
    _assert_no_exposure(calls, permit)


def test_stale_seal_and_blocked_authorisation(monkeypatch: pytest.MonkeyPatch, entry_intent_factory) -> None:
    calls = _install_sink(monkeypatch)
    permit = entry_intent_factory(units=1, client_order_id="cid")
    stale = _sealed()
    stale.attrs["market_provenance"].acquired_mono = time.monotonic() - 10_000
    assert decision_frame_rejection(stale, "EUR_USD") == "stale_acquisition"
    fresh = _sealed()
    assert decision_frame_rejection(fresh, "EUR_USD") is None
    _assert_no_exposure(calls, permit)
    with pytest.raises(ProvenanceRejected, match="caller_supplied_label"):
        provenance_from_label("OANDA_LIVE_VERIFIED")


def test_close_does_not_require_entry_seal(monkeypatch: pytest.MonkeyPatch, close_intent_factory) -> None:
    calls: list[dict] = []

    class FakeAPI:
        def request(self, req):
            calls.append(dict(req.data))
            side = "shortOrderFillTransaction" if "shortUnits" in req.data else "longOrderFillTransaction"
            return {side: {"price": "1.1", "pl": "0.1", "units": "1"}}

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", lambda: FakeAPI())
    monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    from forex_bot.oanda_exec import _place_market_order_sync

    _place_market_order_sync("EUR_USD", 1.0, "BUY", close_intent_factory())
    assert calls == [{"longUnits": "1"}]
    calls.clear()
    _place_market_order_sync("EUR_USD", 2.0, "SELL", close_intent_factory(units=2, direction="SELL"))
    assert calls == [{"shortUnits": "2"}]


def test_failed_close_still_raises(monkeypatch: pytest.MonkeyPatch, close_intent_factory) -> None:
    class FakeAPI:
        def request(self, _req):
            raise TimeoutError("read timed out")

    monkeypatch.setattr("forex_bot.oanda_exec.get_api", lambda: FakeAPI())
    monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
    monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
    from forex_bot.oanda_exec import _place_market_order_sync

    with pytest.raises(TimeoutError, match="timed out"):
        _place_market_order_sync("EUR_USD", 1.0, "BUY", close_intent_factory())


def test_stale_manage_quote_and_broker_stops() -> None:
    quote = ManageQuote(
        instrument="EUR_USD",
        bid=1.1,
        ask=1.1002,
        closeout_bid=1.0999,
        closeout_ask=1.1003,
        time_epoch=time.time() - 500,
        tradeable=True,
    )
    price, source = resolve_broker_manage_price(quote, "BUY")
    assert price is None
    assert source == "UNAVAILABLE"
    assert broker_sl_tp_hit(object()) is False


def test_missing_candles_still_reach_position_management() -> None:
    """G.8 locked an early return before management. G.9 must not restore it."""
    from forex_bot import bot_loop

    src = inspect.getsource(bot_loop._evaluate_impl)
    assert "if raw is None or raw.empty:" not in src
    assert "MANAGEMENT_CONTINUED_WITHOUT_CANDLES" in src
    assert "_skip_new_entry_without_candles" in src
    helper = inspect.getsource(bot_loop._skip_new_entry_without_candles)
    assert "ENTRY_SKIPPED_NO_VALID_CANDLES" in helper
    assert src.find("get_position") < src.find("if pos:")
    assert src.find("if pos:") < src.find("decision_frame_rejection")


def test_restart_keeps_authorisation_blocked_and_strategies_inactive() -> None:
    doc = _blank_document(reason="g7")
    doc["live_order_authorisation"]["state"] = "ALLOWED"
    for name in KNOWN_STRATEGY_NAMES:
        doc["strategies"][name]["active"] = False
    state_path().write_text(json.dumps(doc), encoding="utf-8")
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert live_order_auth_reason() == REASON_PERSISTED_ALLOWED_IGNORED
    assert all(strategies[name].active is False for name in KNOWN_STRATEGY_NAMES)
