"""Live entry SL/TP must be anchored to fresh executable bid/ask, not M5 mid."""

from __future__ import annotations

import inspect
import json
import time
from pathlib import Path

import pytest

from forex_bot.entry_geometry import (
    ENTRY_QUOTE_STALE_SEC,
    PRICE_SOURCE_OANDA_PRICING,
    apply_broker_price_precision,
    construct_absolute_sl_tp,
    executable_entry_reference,
    fill_based_geometry,
    format_broker_price,
    format_entry_fill_geometry_line,
    format_entry_geometry_line,
    format_entry_geometry_skip,
    intended_tp_distance,
    live_broker_geometry_required,
    m5_anchored_sl_tp,
    orientation_valid,
    quote_from_parts,
    resolve_live_entry_geometry,
)
from forex_bot.live_manage import (
    closeout_manage_price,
    resolve_broker_manage_price,
)
from forex_bot.oanda_exec import _format_oanda_price
from forex_bot.trading import TP_RISK_REWARD, sl_tp_distance_for_entry


def _fresh_quote(symbol: str, bid: float, ask: float, *, now: float | None = None, **kw):
    ts = (now if now is not None else time.time()) - 0.05
    return quote_from_parts(instrument=symbol, bid=bid, ask=ask, time_epoch=ts, **kw)


# --- A / B / M / N: BUY and SELL fresh-pricing vs M5 mid ---


def test_buy_anchors_to_ask_not_m5_mid():
    mid = 1.10000
    ask = 1.10040
    bid = 1.10020
    sl_d, tp_d = 0.00020, 0.00040
    old_sl, old_tp = m5_anchored_sl_tp(mid, "BUY", sl_d, tp_d)
    assert old_sl == pytest.approx(1.09980)
    assert old_tp == pytest.approx(1.10040)
    now = time.time()
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD",
        "BUY",
        sl_d,
        tp_d,
        mid,
        quote=_fresh_quote("EUR_USD", bid, ask, now=now),
        now=now,
    )
    assert skip is None and geom is not None
    assert geom.executable_reference == pytest.approx(ask)
    assert geom.sl == pytest.approx(ask - sl_d)
    assert geom.tp == pytest.approx(ask + tp_d)
    assert geom.sl != pytest.approx(old_sl)
    assert geom.price_source == PRICE_SOURCE_OANDA_PRICING
    assert orientation_valid("BUY", geom.sl, geom.executable_reference, geom.tp)
    assert geom.expected_r == pytest.approx(2.0, abs=0.02)


def test_sell_anchors_to_bid_not_m5_mid():
    mid = 1.10000
    bid = 1.09960
    ask = 1.09990
    sl_d, tp_d = 0.00020, 0.00040
    old_sl, old_tp = m5_anchored_sl_tp(mid, "SELL", sl_d, tp_d)
    now = time.time()
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD",
        "SELL",
        sl_d,
        tp_d,
        mid,
        quote=_fresh_quote("EUR_USD", bid, ask, now=now),
        now=now,
    )
    assert skip is None and geom is not None
    assert geom.executable_reference == pytest.approx(bid)
    assert geom.sl == pytest.approx(bid + sl_d)
    assert geom.tp == pytest.approx(bid - tp_d)
    assert geom.sl != pytest.approx(old_sl)
    assert orientation_valid("SELL", geom.sl, geom.executable_reference, geom.tp)


def test_buy_orientation_sl_lt_ref_lt_tp():
    assert orientation_valid("BUY", 1.09900, 1.10000, 1.10200)
    assert not orientation_valid("BUY", 1.10000, 1.09900, 1.10200)


def test_sell_orientation_tp_lt_ref_lt_sl():
    assert orientation_valid("SELL", 1.10100, 1.10000, 1.09800)
    assert not orientation_valid("SELL", 1.09800, 1.10000, 1.10100)


# --- C: AUD_USD forensic 0.375R ---


def test_aud_usd_forensic_old_r_and_new_geometry():
    mid = 0.71198
    fill = 0.71176
    old_sl, old_tp = 0.71216, 0.71161
    sl_d = old_sl - mid  # 0.00018 — intended risk distance from the M5 construction
    tp_d = intended_tp_distance(sl_d)
    assert sl_d == pytest.approx(0.00018, abs=1e-8)
    assert tp_d == pytest.approx(0.00036, abs=1e-8)
    _risk_p, _rew_p, old_r = fill_based_geometry("AUD_USD", "SELL", fill, old_sl, old_tp)
    assert old_r == pytest.approx(0.375, abs=0.01)

    now = time.time()
    # Fresh executable SELL = bid (the forensic fill / top-of-book bid).
    geom, skip = resolve_live_entry_geometry(
        "AUD_USD",
        "SELL",
        sl_d,
        tp_d,
        mid,
        quote=_fresh_quote("AUD_USD", fill, fill + 0.00034, now=now),
        now=now,
    )
    assert skip is None and geom is not None
    assert geom.sl == pytest.approx(fill + sl_d, abs=5e-6)
    assert geom.tp == pytest.approx(fill - tp_d, abs=5e-6)
    assert geom.expected_r == pytest.approx(TP_RISK_REWARD, abs=0.05)
    assert orientation_valid("SELL", geom.sl, geom.executable_reference, geom.tp)
    _rp, _rwp, new_fill_r = fill_based_geometry(
        "AUD_USD", "SELL", fill, geom.sl, geom.tp
    )
    assert new_fill_r is not None and new_fill_r > 1.8


# --- D / E / F: three OANDA rejection categories ---


def test_losing_take_profit_stale_mid_new_orientation_valid():
    """SELL: stale-mid TP sits on the losing side of current bid."""
    mid = 0.71200
    sl_d, tp_d = 0.00020, 0.00040
    old_sl, old_tp = m5_anchored_sl_tp(mid, "SELL", sl_d, tp_d)
    bid = 0.71155  # through old TP 0.71160
    assert old_tp > bid  # TP above executable SELL = losing TP
    now = time.time()
    geom, skip = resolve_live_entry_geometry(
        "AUD_USD",
        "SELL",
        sl_d,
        tp_d,
        mid,
        quote=_fresh_quote("AUD_USD", bid, bid + 0.00020, now=now),
        now=now,
    )
    assert skip is None and geom is not None
    assert geom.tp < geom.executable_reference < geom.sl
    assert geom.tp < bid


def test_stop_loss_on_fill_loss_stale_mid_new_orientation_valid():
    """BUY: stale-mid SL already through current ask."""
    mid = 1.10000
    sl_d, tp_d = 0.00020, 0.00040
    old_sl, old_tp = m5_anchored_sl_tp(mid, "BUY", sl_d, tp_d)
    ask = 1.09970
    assert ask < old_sl  # fill would already be past SL
    now = time.time()
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD",
        "BUY",
        sl_d,
        tp_d,
        mid,
        quote=_fresh_quote("EUR_USD", ask - 0.00010, ask, now=now),
        now=now,
    )
    assert skip is None and geom is not None
    assert geom.sl < geom.executable_reference < geom.tp
    assert geom.sl < ask


def test_take_profit_on_fill_loss_stale_mid_new_orientation_valid():
    """BUY: stale-mid TP already on the losing side of current ask."""
    mid = 1.10000
    sl_d, tp_d = 0.00020, 0.00040
    old_sl, old_tp = m5_anchored_sl_tp(mid, "BUY", sl_d, tp_d)
    ask = 1.10045
    assert ask > old_tp  # fill already past TP
    now = time.time()
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD",
        "BUY",
        sl_d,
        tp_d,
        mid,
        quote=_fresh_quote("EUR_USD", ask - 0.00010, ask, now=now),
        now=now,
    )
    assert skip is None and geom is not None
    assert geom.sl < ask < geom.tp


# --- G / H / I: fail closed ---


def test_missing_pricinginfo_fails_closed():
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD", "BUY", 0.0002, 0.0004, 1.10, quote=None
    )
    assert geom is None
    assert skip == "missing_quote"


def test_stale_pricinginfo_fails_closed():
    now = time.time()
    q = quote_from_parts(
        instrument="EUR_USD",
        bid=1.10,
        ask=1.1002,
        time_epoch=now - (ENTRY_QUOTE_STALE_SEC + 1.0),
    )
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD", "BUY", 0.0002, 0.0004, 1.10, quote=q, now=now
    )
    assert geom is None
    assert skip == "stale_quote"


def test_malformed_quote_fails_closed():
    now = time.time()
    q = quote_from_parts(
        instrument="EUR_USD", bid=None, ask=None, time_epoch=now - 0.01
    )
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD", "BUY", 0.0002, 0.0004, 1.10, quote=q, now=now
    )
    assert geom is None
    assert skip == "missing_executable_price"


def test_untradeable_quote_fails_closed():
    now = time.time()
    q = _fresh_quote("EUR_USD", 1.10, 1.1002, now=now, tradeable=False)
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD", "BUY", 0.0002, 0.0004, 1.10, quote=q, now=now
    )
    assert geom is None
    assert skip == "not_tradeable"


def test_missing_quote_time_fails_closed():
    q = quote_from_parts(instrument="EUR_USD", bid=1.10, ask=1.1002, time_epoch=None)
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD", "BUY", 0.0002, 0.0004, 1.10, quote=q
    )
    assert geom is None
    assert skip == "missing_quote_time"


# --- J / K / L: rounding and precision ---


def test_rounding_boundary_preserves_orientation_or_fails_closed():
    now = time.time()
    # Normal distances survive 5dp rounding.
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD",
        "BUY",
        0.00021,
        0.00042,
        1.100003,
        quote=_fresh_quote("EUR_USD", 1.10000, 1.10011, now=now),
        now=now,
    )
    assert skip is None and geom is not None
    assert orientation_valid("BUY", geom.sl, geom.executable_reference, geom.tp)
    # Distance smaller than one tick → fail closed rather than send inverted prices.
    geom2, skip2 = resolve_live_entry_geometry(
        "EUR_USD",
        "BUY",
        0.000001,
        0.000002,
        1.10000,
        quote=_fresh_quote("EUR_USD", 1.10000, 1.10000, now=now),
        now=now,
    )
    assert geom2 is None
    assert skip2 == "invalid_orientation_after_rounding"


def test_jpy_precision_three_decimals():
    assert format_broker_price("USD_JPY", 157.2814) == "157.281"
    assert apply_broker_price_precision("USD_JPY", 157.2814) == pytest.approx(157.281)
    now = time.time()
    sl_d, tp_d = 0.120, 0.240
    geom, skip = resolve_live_entry_geometry(
        "USD_JPY",
        "BUY",
        sl_d,
        tp_d,
        157.200,
        quote=_fresh_quote("USD_JPY", 157.248, 157.256, now=now),
        now=now,
    )
    assert skip is None and geom is not None
    assert geom.sl_text == format_broker_price("USD_JPY", geom.sl)
    assert len(geom.sl_text.split(".")[-1]) == 3


def test_non_jpy_precision_five_decimals():
    assert format_broker_price("AUD_USD", 0.711976) == "0.71198"
    assert format_broker_price("EUR_USD", 1.148034) == "1.14803"
    assert format_broker_price("AUD_USD", 0.711976) == _format_oanda_price("AUD_USD", 0.711976)


# --- O / P / Q / R: paper vs broker path ---


def test_paper_simulate_mid_paths_do_not_require_live_geometry():
    assert live_broker_geometry_required("mid") is False
    assert live_broker_geometry_required("simulate") is False
    assert live_broker_geometry_required("") is False


def test_paper_window_paper_simulated_still_use_mid_anchor_formula():
    mid = 1.14800
    sl_d, tp_d = 0.00034, 0.00068
    sl, tp = construct_absolute_sl_tp(mid, "BUY", sl_d, tp_d)
    assert sl == pytest.approx(mid - sl_d)
    assert tp == pytest.approx(mid + tp_d)
    sl_s, tp_s = construct_absolute_sl_tp(mid, "SELL", sl_d, tp_d)
    assert sl_s == pytest.approx(mid + sl_d)
    assert tp_s == pytest.approx(mid - tp_d)


def test_paper_broker_and_live_broker_require_executable_geometry():
    assert live_broker_geometry_required("broker") is True


def test_atr_and_tp_multiplier_unchanged():
    assert TP_RISK_REWARD == 2.0
    sl_d, tp_d = sl_tp_distance_for_entry("EUR_USD", 0.00015)
    # USE_ATR_STOPS is unset in tests → fallback 20 pips, not a new multiplier.
    assert tp_d == pytest.approx(sl_d * TP_RISK_REWARD)
    assert intended_tp_distance(0.00018) == pytest.approx(0.00036)


# --- S: existing-position management unchanged ---


def test_position_management_still_uses_closeout_not_entry_ask_bid():
    q = quote_from_parts(
        instrument="EUR_USD",
        bid=1.10000,
        ask=1.10020,
        closeout_bid=1.09990,
        closeout_ask=1.10030,
        time_epoch=time.time(),
    )
    assert closeout_manage_price(q, "BUY") == pytest.approx(1.09990)
    assert closeout_manage_price(q, "SELL") == pytest.approx(1.10030)
    px, src = resolve_broker_manage_price(q, "BUY")
    assert px == pytest.approx(1.09990)
    assert executable_entry_reference(q, "BUY") == pytest.approx(1.10020)
    assert executable_entry_reference(q, "SELL") == pytest.approx(1.10000)
    assert executable_entry_reference(q, "BUY") != closeout_manage_price(q, "BUY")


# --- logging ---


def test_geometry_log_lines_contain_required_fields():
    now = time.time()
    geom, skip = resolve_live_entry_geometry(
        "GBP_USD",
        "SELL",
        0.00040,
        0.00080,
        1.33800,
        quote=_fresh_quote("GBP_USD", 1.33780, 1.33810, now=now),
        now=now,
        atr=0.00020,
    )
    assert skip is None and geom is not None
    line = format_entry_geometry_line(geom)
    for token in (
        "[ENTRY GEOMETRY]",
        "symbol=GBP_USD",
        "side=SELL",
        "signal_mid=",
        "executable_reference=",
        "price_source=OANDA_PRICING",
        "expected_r=",
        "spread_pips=",
        "quote_age_ms=",
    ):
        assert token in line
    fill_line = format_entry_fill_geometry_line(
        symbol="GBP_USD",
        side="SELL",
        reference=geom.executable_reference,
        fill=1.33779,
        sl=geom.sl,
        tp=geom.tp,
        broker_id="2434",
        transaction_id="2434",
    )
    assert "[ENTRY FILL GEOMETRY]" in fill_line
    assert "actual_r=" in fill_line
    skip_line = format_entry_geometry_skip("EUR_USD", "BUY", "stale_quote")
    assert "fail_closed=true" in skip_line


# --- V: no blind OrderCreate retry ---


def test_bot_loop_open_has_single_ordercreate_and_no_retry_loop():
    import forex_bot.bot_loop as bot_loop

    src = inspect.getsource(bot_loop.evaluate)
    assert src.count("execute_oanda_market_open") == 1
    assert "for _retry" not in src
    assert "while True" not in src.split("if fill_path == \"broker\":", 1)[-1][:2500]


def test_oanda_exec_open_is_single_request():
    import forex_bot.oanda_exec as ox

    src = inspect.getsource(ox._place_market_order_open_sync)
    assert src.count("api.request") == 1
    assert "while " not in src
    assert "retry" not in src.lower()


# --- fetch fail-closed wrapper ---


def test_fetch_fresh_entry_quote_returns_none_when_snapshot_empty(monkeypatch):
    from forex_bot import entry_geometry as eg

    monkeypatch.setattr("forex_bot.oanda_client.fetch_pricing_snapshot", lambda symbols=None: {})
    assert eg.fetch_fresh_entry_quote("EUR_USD") is None


def test_fetch_fresh_entry_quote_uses_pricing_snapshot(monkeypatch):
    from forex_bot import entry_geometry as eg
    from forex_bot.oanda_client import oanda_instrument

    q = _fresh_quote("EUR_USD", 1.1, 1.1002)
    monkeypatch.setattr(
        "forex_bot.oanda_client.fetch_pricing_snapshot",
        lambda symbols=None: {oanda_instrument("EUR_USD"): q},
    )
    got = eg.fetch_fresh_entry_quote("EUR_USD")
    assert got is q


# --- optional forensic counterfactual (no invented bid/ask) ---


def test_counterfactual_replay_where_fill_side_is_known():
    """If SELL fill == recorded bid (or BUY fill == ask), re-anchor preserves ~2R."""
    path = Path("reports/decision_quality/_forensic_summary.json")
    if not path.exists():
        pytest.skip("forensic summary not present")
    payload = json.loads(path.read_text(encoding="utf-8"))
    trades = payload.get("completed_trades") or []
    below_1 = [t for t in trades if t.get("fill_r") is not None and t["fill_r"] < 1.0]
    below_05 = [t for t in trades if t.get("fill_r") is not None and t["fill_r"] < 0.5]
    corrected_1 = 0
    corrected_05 = 0
    usable = 0
    for tr in trades:
        fill = tr.get("entry_price")
        mid = tr.get("inferred_mid")
        sl = tr.get("submitted_sl")
        side = tr.get("side")
        if None in (fill, mid, sl, side):
            continue
        sl_d = abs(float(sl) - float(mid))
        if sl_d <= 0:
            continue
        tp_d = intended_tp_distance(sl_d)
        new_sl, new_tp = construct_absolute_sl_tp(float(fill), side, sl_d, tp_d)
        _rp, _rwp, new_r = fill_based_geometry(tr["symbol"], side, float(fill), new_sl, new_tp)
        if new_r is None:
            continue
        usable += 1
        if tr.get("fill_r") is not None and tr["fill_r"] < 1.0 and new_r >= 1.0:
            corrected_1 += 1
        if tr.get("fill_r") is not None and tr["fill_r"] < 0.5 and new_r >= 0.5:
            corrected_05 += 1
    # Labelled COUNTERFACTUAL: uses the recorded fill as the executable side
    # (SELL fill is the bid; BUY fill is the ask in this export). Not P/L.
    assert usable >= 100
    assert corrected_1 == len(below_1)
    assert corrected_05 == len(below_05)


def test_no_minimum_r_or_spread_filter_in_resolver():
    src = inspect.getsource(resolve_live_entry_geometry)
    assert "MIN_EXPECTED_R" not in src
    assert "spread_filter" not in src
    assert "MIN_FILL_R" not in src
