"""Trigger-side SL validity guard and OrderCreate outcome classification."""

from __future__ import annotations

import asyncio
import inspect
import time
from unittest.mock import patch

import pytest
from oandapyV20.exceptions import V20Error

from forex_bot.entry_geometry import (
    REQUIRED_SL_TRIGGER_CLEARANCE,
    SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE,
    apply_broker_price_precision,
    construct_absolute_sl_tp,
    format_entry_geometry_skip,
    has_sl_trigger_clearance,
    live_broker_geometry_required,
    quote_from_parts,
    resolve_live_entry_geometry,
    sl_trigger_clearance,
    sl_trigger_clearance_skip_reason,
    sl_trigger_side,
)
from forex_bot.oanda_exec import (
    OUTCOME_AMBIGUOUS_TRANSPORT,
    OUTCOME_CANCELLED,
    OUTCOME_FILLED,
    OUTCOME_MALFORMED,
    OUTCOME_REJECTED,
    OrderCreateAmbiguous,
    OrderCreateCancelled,
    OrderCreateClassification,
    OrderCreateMalformed,
    OrderCreateRejected,
    _parse_open_fill,
    _place_market_order_open_sync,
    classify_order_create_response,
    classify_order_create_transport_error,
    format_order_cancel_line,
)
from forex_bot.trading import TP_RISK_REWARD, position_sizing, sl_tp_distance_for_entry


def _quote(symbol: str, bid: float | None, ask: float | None, *, age_sec: float = 0.05, **kw):
    now = time.time()
    return quote_from_parts(
        instrument=symbol,
        bid=bid,
        ask=ask,
        time_epoch=None if age_sec is None else now - age_sec,
        **kw,
    )


def _resolve(symbol, side, sl_d, tp_d, mid, bid, ask, **kw):
    now = time.time()
    return resolve_live_entry_geometry(
        symbol,
        side,
        sl_d,
        tp_d,
        mid,
        quote=_quote(symbol, bid, ask, **kw),
        now=now,
    )


def _may_submit(geom, skip) -> bool:
    return skip is None and geom is not None


# Reconstructed forensic population (submitted SL + contemporaneous book).
HISTORICAL_CANCELS = [
    {"cid": "cid-34ea03ffe3fa486ab98e7bad36d45252", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33478, "tp": 1.33615, "xref": 1.3352366666666666, "bid": 1.33368, "ask": 1.33527},
    {"cid": "cid-8f55b3f86c5d4f2b918f5ee1d56baef0", "symbol": "USD_JPY", "side": "SELL", "sl": 157.379, "tp": 157.233, "xref": 157.33033333333333, "bid": 157.33, "ask": 157.43},
    {"cid": "cid-6d0d82b0369e4f10b370dca4802b0af2", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33478, "tp": 1.33615, "xref": 1.3352366666666666, "bid": 1.33368, "ask": 1.33527},
    {"cid": "cid-03209f355b264a10b11548a57443d6a7", "symbol": "AUD_USD", "side": "BUY", "sl": 0.71182, "tp": 0.71261, "xref": 0.7120833333333333, "bid": 0.71137, "ask": 0.71208},
    {"cid": "cid-3ac32014576e44ea986041bc7c85b447", "symbol": "USD_JPY", "side": "SELL", "sl": 157.379, "tp": 157.233, "xref": 157.33033333333333, "bid": 157.341, "ask": 157.441},
    {"cid": "cid-cb964084bab6490b87f5606bebbaee98", "symbol": "AUD_USD", "side": "BUY", "sl": 0.71182, "tp": 0.71261, "xref": 0.7120833333333333, "bid": 0.71135, "ask": 0.71208},
    {"cid": "cid-eee7fdf92db44f61864421b14ff0ab19", "symbol": "USD_CHF", "side": "SELL", "sl": 0.82032, "tp": 0.81905, "xref": 0.8198966666666667, "bid": 0.81983, "ask": 0.82133},
    {"cid": "cid-84c40a5c859e4bed8c20118ef9cf5cd7", "symbol": "USD_CHF", "side": "SELL", "sl": 0.82025, "tp": 0.81898, "xref": 0.8198266666666667, "bid": 0.81989, "ask": 0.82139},
    {"cid": "cid-74595fd264cd484db786041a46582036", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33492, "tp": 1.33628, "xref": 1.3353733333333334, "bid": 1.33377, "ask": 1.33536},
    {"cid": "cid-ac380f6a32914d59a20e8a2dbc9ee488", "symbol": "USD_CAD", "side": "SELL", "sl": 1.40634, "tp": 1.40506, "xref": 1.4059133333333333, "bid": 1.40587, "ask": 1.40665},
    {"cid": "cid-683e7c2d6f0a404ea4387efb01892d6d", "symbol": "USD_CAD", "side": "SELL", "sl": 1.40642, "tp": 1.40514, "xref": 1.4059933333333333, "bid": 1.40574, "ask": 1.40676},
    {"cid": "cid-e6afc545a3d844529fc229dec57cceec", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33492, "tp": 1.33631, "xref": 1.3353833333333333, "bid": 1.33386, "ask": 1.33542},
    {"cid": "cid-bdb651433a0a4403b6802c46a466d733", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33492, "tp": 1.33631, "xref": 1.3353833333333333, "bid": 1.33384, "ask": 1.33543},
    {"cid": "cid-b2db42bf9263435983665c6b4df3b4ea", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33495, "tp": 1.33634, "xref": 1.3354133333333334, "bid": 1.33385, "ask": 1.33544},
    {"cid": "cid-8bde28710212487b9d9df455a32fe8a8", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33499, "tp": 1.33638, "xref": 1.3354533333333333, "bid": 1.33384, "ask": 1.33543},
    {"cid": "cid-57588c279fc2440d8f4c24abd12c09e2", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33419, "tp": 1.33564, "xref": 1.3346733333333334, "bid": 1.33384, "ask": 1.33470},
    {"cid": "cid-4fc845893cd149e4b6d7590920e95fac", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33426, "tp": 1.33571, "xref": 1.3347433333333333, "bid": 1.33385, "ask": 1.33469},
    {"cid": "cid-ba84f573b35b4a16a5b91ff3012bb632", "symbol": "AUD_USD", "side": "BUY", "sl": 0.71174, "tp": 0.71261, "xref": 0.71203, "bid": 0.71135, "ask": 0.71203},
    {"cid": "cid-3c886c582acb4550b413eb2f08c125bb", "symbol": "AUD_USD", "side": "BUY", "sl": 0.71172, "tp": 0.71263, "xref": 0.7120233333333333, "bid": 0.71151, "ask": 0.71203},
]

HISTORICAL_FILLS = [
    {"cid": "cid-f0018527cf024210bf211e9df62dd1ea", "symbol": "USD_JPY", "side": "SELL", "sl": 157.431, "tp": 157.261, "xref": 157.374, "bid": 157.369, "ask": 157.384},
    {"cid": "cid-239ddf6d18aa4f8d8a4d179949dd5c5f", "symbol": "USD_JPY", "side": "BUY", "sl": 157.412, "tp": 157.564, "xref": 157.463, "bid": 157.415, "ask": 157.463},
    {"cid": "cid-868759c88fbf4106b7a450820dcd636d", "symbol": "USD_JPY", "side": "BUY", "sl": 157.393, "tp": 157.545, "xref": 157.444, "bid": 157.405, "ask": 157.443},
    {"cid": "cid-4ddd3a933d47430aa4af478ebeef0267", "symbol": "GBP_USD", "side": "BUY", "sl": 1.33413, "tp": 1.33557, "xref": 1.33461, "bid": 1.33443, "ask": 1.33468},
    {"cid": "cid-0ff3d11b90464e358a077106d229d8eb", "symbol": "USD_JPY", "side": "BUY", "sl": 157.378, "tp": 157.508, "xref": 157.421, "bid": 157.382, "ask": 157.419},
]


def test_required_clearance_is_exactly_zero():
    assert REQUIRED_SL_TRIGGER_CLEARANCE == 0.0
    assert has_sl_trigger_clearance(0.0) is False
    assert has_sl_trigger_clearance(1e-12) is True


def test_buy_bid_gt_sl_allows():
    geom, skip = _resolve("EUR_USD", "BUY", 0.00040, 0.00080, 1.10, 1.10010, 1.10020)
    assert _may_submit(geom, skip)
    assert geom.trigger_side == "bid"
    assert geom.trigger_clearance > 0
    assert sl_trigger_side("BUY") == "bid"


def test_buy_bid_eq_sl_skips():
    geom, skip = _resolve("EUR_USD", "BUY", 0.00010, 0.00020, 1.10, 1.10010, 1.10020)
    assert skip == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE
    assert not _may_submit(geom, skip)
    assert geom is not None
    assert geom.trigger_clearance == pytest.approx(0.0, abs=1e-12)


def test_buy_bid_lt_sl_skips():
    geom, skip = _resolve("EUR_USD", "BUY", 0.00040, 0.00080, 1.10, 1.09970, 1.10020)
    assert skip == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE
    assert geom.trigger_clearance < 0


def test_sell_ask_lt_sl_allows():
    geom, skip = _resolve("EUR_USD", "SELL", 0.00040, 0.00080, 1.10, 1.10000, 1.10010)
    assert _may_submit(geom, skip)
    assert geom.trigger_side == "ask"
    assert geom.trigger_clearance > 0


def test_sell_ask_eq_sl_skips():
    geom, skip = _resolve("EUR_USD", "SELL", 0.00010, 0.00020, 1.10, 1.10000, 1.10010)
    assert skip == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE
    assert geom.trigger_clearance == pytest.approx(0.0, abs=1e-12)


def test_sell_ask_gt_sl_skips():
    geom, skip = _resolve("EUR_USD", "SELL", 0.00010, 0.00020, 1.10, 1.10000, 1.10025)
    assert skip == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE
    assert geom.trigger_clearance < 0


def test_buy_valid_vs_ask_invalid_vs_bid_skips():
    # SL < ask (orientation ok) but bid <= SL.
    sl_d, tp_d = 0.00015, 0.00030
    ask, bid = 1.10020, 1.10000
    sl = apply_broker_price_precision("EUR_USD", ask - sl_d)
    assert sl < ask
    assert bid <= sl
    geom, skip = _resolve("EUR_USD", "BUY", sl_d, tp_d, 1.10, bid, ask)
    assert skip == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE


def test_sell_valid_vs_bid_invalid_vs_ask_skips():
    sl_d, tp_d = 0.00015, 0.00030
    bid, ask = 1.10000, 1.10020
    sl = apply_broker_price_precision("EUR_USD", bid + sl_d)
    assert sl > bid
    assert ask >= sl
    geom, skip = _resolve("EUR_USD", "SELL", sl_d, tp_d, 1.10, bid, ask)
    assert skip == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE


def test_tiny_positive_clearance_allows_no_buffer():
    geom, skip = _resolve("EUR_USD", "BUY", 0.00019, 0.00038, 1.10, 1.10002, 1.10020)
    assert _may_submit(geom, skip)
    assert 0 < geom.trigger_clearance_pips < 0.2


def test_rounding_can_turn_positive_raw_clearance_to_zero():
    ask = 1.100204
    sl_d = 0.000206
    bid = 1.10000
    raw_sl, _ = construct_absolute_sl_tp(ask, "BUY", sl_d, sl_d * 2)
    assert bid - raw_sl > 0
    rounded_sl = apply_broker_price_precision("EUR_USD", raw_sl)
    assert bid - rounded_sl == pytest.approx(0.0, abs=1e-12)
    geom, skip = _resolve("EUR_USD", "BUY", sl_d, sl_d * 2, 1.10, bid, ask)
    assert skip == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE
    assert geom is not None
    assert geom.sl == pytest.approx(rounded_sl)


def test_rounding_keeps_positive_clearance_allows():
    geom, skip = _resolve("EUR_USD", "BUY", 0.000214, 0.000428, 1.10, 1.10005, 1.10021)
    assert _may_submit(geom, skip)
    assert geom.trigger_clearance > 0


def test_jpy_trigger_clearance_uses_three_decimals():
    geom, skip = _resolve("USD_JPY", "BUY", 0.050, 0.100, 157.20, 157.248, 157.256)
    assert _may_submit(geom, skip)
    assert geom.sl_text == f"{geom.sl:.3f}"
    blocked, skip_b = _resolve("USD_JPY", "BUY", 0.004, 0.008, 157.20, 157.248, 157.256)
    assert skip_b == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE


def test_non_jpy_trigger_clearance_uses_five_decimals():
    geom, skip = _resolve("GBP_USD", "BUY", 0.00046, 0.00092, 1.33400, 1.33450, 1.33480)
    assert _may_submit(geom, skip)
    assert geom.sl_text == f"{geom.sl:.5f}"


@pytest.mark.parametrize(
    "bid,ask,side,reason",
    [
        (None, 1.10020, "BUY", "executable_bid_missing"),
        (1.10000, None, "SELL", "executable_ask_missing"),
        (float("nan"), 1.10020, "BUY", "malformed_price"),
        (1.10000, float("nan"), "SELL", "malformed_price"),
        (float("inf"), 1.10020, "BUY", "malformed_price"),
        (1.10000, float("inf"), "SELL", "malformed_price"),
        (0.0, 1.10020, "BUY", "malformed_price"),
        (1.10000, 0.0, "SELL", "malformed_price"),
        (-1.10, 1.10020, "BUY", "malformed_price"),
        (1.10000, -1.10020, "SELL", "malformed_price"),
    ],
)
def test_both_book_sides_required_fail_closed(bid, ask, side, reason):
    geom, skip = _resolve("EUR_USD", side, 0.00040, 0.00080, 1.10, bid, ask)
    assert geom is None
    assert skip == reason


def test_clientprice_time_older_than_5s_still_allows_valid_clearance():
    now = time.time()
    q = quote_from_parts(
        instrument="EUR_USD",
        bid=1.10010,
        ask=1.10020,
        time_epoch=now - 12.0,
    )
    geom, skip = resolve_live_entry_geometry(
        "EUR_USD", "BUY", 0.00040, 0.00080, 1.10, quote=q, now=now
    )
    assert _may_submit(geom, skip)
    assert geom.price_last_change_age_ms == pytest.approx(12_000.0, abs=50.0)
    assert skip != "stale_quote"


def test_skip_log_has_trigger_fields():
    geom, skip = _resolve("EUR_USD", "BUY", 0.00010, 0.00020, 1.10, 1.10000, 1.10020)
    line = format_entry_geometry_skip("EUR_USD", "BUY", skip, geom=geom)
    for token in (
        "[ENTRY GEOMETRY SKIP]",
        "reason=insufficient_sl_trigger_clearance",
        "trigger_side=bid",
        "trigger_clearance_pips=",
        "required_clearance_pips=0",
        "fail_closed=true",
    ):
        assert token in line


def test_historical_19_cancels_blocked_and_ordercreate_not_called():
    blocked = 0
    for ev in HISTORICAL_CANCELS:
        sl = ev["sl"]
        cl = sl_trigger_clearance(ev["side"], sl, ev["bid"], ev["ask"])
        assert cl is not None and cl <= 0
        sl_d = abs(ev["xref"] - sl)
        tp_d = sl_d * 2.0
        geom, skip = _resolve(ev["symbol"], ev["side"], sl_d, tp_d, ev["xref"], ev["bid"], ev["ask"])
        assert skip == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE
        assert not _may_submit(geom, skip)
        blocked += 1
    assert blocked == 19
    assert len(HISTORICAL_CANCELS) == 19


def test_historical_5_controls_allowed():
    allowed = 0
    for ev in HISTORICAL_FILLS:
        cl = sl_trigger_clearance(ev["side"], ev["sl"], ev["bid"], ev["ask"])
        assert cl is not None and cl > 0
        sl_d = abs(ev["xref"] - ev["sl"])
        tp_d = sl_d * 2.0
        geom, skip = _resolve(ev["symbol"], ev["side"], sl_d, tp_d, ev["xref"], ev["bid"], ev["ask"])
        assert _may_submit(geom, skip)
        assert geom.expected_r == pytest.approx(2.0, abs=0.05)
        allowed += 1
    assert allowed == 5


def test_valid_geometry_leaves_atr_tp_r_and_units_unchanged():
    sl_d, tp_d = sl_tp_distance_for_entry("EUR_USD", 0.00020)
    assert tp_d == pytest.approx(sl_d * TP_RISK_REWARD)
    units_before = position_sizing("EUR_USD", 1.10000, 1.10000 - sl_d, 10_000.0)
    geom, skip = _resolve("EUR_USD", "BUY", sl_d, tp_d, 1.10000, 1.10010, 1.10020)
    assert _may_submit(geom, skip)
    assert geom.risk_distance == pytest.approx(
        apply_broker_price_precision("EUR_USD", 1.10020) - geom.sl, abs=1e-9
    )
    assert geom.expected_r == pytest.approx(2.0, abs=0.05)
    units_after = position_sizing("EUR_USD", 1.10000, 1.10000 - sl_d, 10_000.0)
    assert units_after == units_before
    geom_b, skip_b = _resolve("EUR_USD", "BUY", sl_d, tp_d, 1.10000, 1.09970, 1.10020)
    assert skip_b == SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE
    assert sl_d == sl_tp_distance_for_entry("EUR_USD", 0.00020)[0]


def test_no_spread_threshold_is_the_rule():
    src = inspect.getsource(resolve_live_entry_geometry)
    assert "spread_filter" not in src
    assert "MIN_SPREAD" not in src
    assert sl_trigger_clearance_skip_reason("BUY", 1.0, 1.0001, 1.0002) is None
    assert sl_trigger_clearance_skip_reason("BUY", 1.0001, 1.0001, 1.0002) == (
        SKIP_INSUFFICIENT_SL_TRIGGER_CLEARANCE
    )


def test_bot_loop_uses_same_snapshot_and_skip_before_ordercreate():
    import forex_bot.bot_loop as bot_loop
    from forex_bot import entry_geometry as eg

    src = inspect.getsource(bot_loop.evaluate)
    broker = src.split('if fill_path == "broker":', 1)[-1]
    assert broker.find("fetch_entry_pricing") < broker.find("resolve_live_entry_geometry")
    assert broker.find("if skip_reason is not None") < broker.find("execute_oanda_market_open")
    assert broker.count("fetch_entry_pricing") == 1
    assert broker.count("execute_oanda_market_open") == 1
    resolve_src = inspect.getsource(eg.resolve_live_entry_geometry)
    assert "sl_trigger_clearance" in resolve_src
    assert "fetch_entry_pricing" not in resolve_src
    assert "sleep" not in resolve_src


def test_paper_and_management_paths_unchanged():
    assert live_broker_geometry_required("mid") is False
    assert live_broker_geometry_required("simulate") is False
    from forex_bot.live_manage import closeout_manage_price

    q = _quote("EUR_USD", 1.10000, 1.10020, closeout_bid=1.09990, closeout_ask=1.10030)
    assert closeout_manage_price(q, "BUY") == pytest.approx(1.09990)
    assert closeout_manage_price(q, "SELL") == pytest.approx(1.10030)
    import forex_bot.entry_geometry as eg
    import forex_bot.bot_loop as bot_loop

    eg_src = inspect.getsource(eg)
    assert "PRICE_SOURCE_M5_MID" not in inspect.getsource(eg.resolve_live_entry_geometry)
    assert "weekend" not in inspect.getsource(eg.resolve_live_entry_geometry)
    assert "usd_direction" not in inspect.getsource(eg.resolve_live_entry_geometry)
    broker = inspect.getsource(bot_loop.evaluate).split('if fill_path == "broker":', 1)[-1]
    assert "fetch_entry_pricing" in broker
    assert broker.count("fetch_pricing_snapshot") == 0


def _fill_response(**extra):
    body = {
        "orderCreateTransaction": {"id": "10", "clientExtensions": {"id": "cid-fill"}},
        "orderFillTransaction": {
            "id": "11",
            "price": "1.10000",
            "units": "2",
            "pl": "0",
            "time": "2026-09-22T21:00:00.000000000Z",
            "clientExtensions": {"id": "cid-fill"},
        },
        "relatedTransactionIDs": ["10", "11"],
        "lastTransactionID": "11",
    }
    body.update(extra)
    return body


def _cancel_response(reason: str = "STOP_LOSS_ON_FILL_LOSS"):
    return {
        "orderCreateTransaction": {
            "id": "3132",
            "instrument": "GBP_USD",
            "clientExtensions": {"id": "cid-34ea03ffe3fa486ab98e7bad36d45252"},
        },
        "orderCancelTransaction": {
            "id": "3133",
            "orderID": "3132",
            "reason": reason,
            "clientExtensions": {"id": "cid-34ea03ffe3fa486ab98e7bad36d45252"},
            "relatedTransactionIDs": ["3132"],
        },
        "relatedTransactionIDs": ["3132", "3133"],
        "lastTransactionID": "3133",
    }


def test_classify_fill():
    cls = classify_order_create_response(_fill_response())
    assert cls.outcome == OUTCOME_FILLED
    assert cls.fill_tx_id == "11"
    fp, uf, oid, _pl, _ts = _parse_open_fill(_fill_response())
    assert fp == pytest.approx(1.1)
    assert uf == 2.0
    assert oid == "11"


def test_classify_cancel_stop_loss_on_fill_loss():
    cls = classify_order_create_response(_cancel_response())
    assert cls.outcome == OUTCOME_CANCELLED
    assert cls.cancel_reason == "STOP_LOSS_ON_FILL_LOSS"
    assert cls.create_tx_id == "3132"
    assert cls.cancel_tx_id == "3133"
    assert cls.client_id.startswith("cid-34ea")
    line = format_order_cancel_line(
        symbol="GBP_USD", side="BUY", cid=cls.client_id or "", classification=cls
    )
    assert "reason=STOP_LOSS_ON_FILL_LOSS" in line
    assert "missing orderFillTransaction" not in line
    with pytest.raises(OrderCreateCancelled) as ei:
        _parse_open_fill(_cancel_response())
    assert ei.value.classification.cancel_reason == "STOP_LOSS_ON_FILL_LOSS"
    assert "missing orderFillTransaction" not in str(ei.value)


def test_classify_other_cancel_reason_preserved():
    cls = classify_order_create_response(_cancel_response("TIME_IN_FORCE_EXPIRED"))
    assert cls.outcome == OUTCOME_CANCELLED
    assert cls.cancel_reason == "TIME_IN_FORCE_EXPIRED"


def test_classify_reject_and_malformed():
    rejected = classify_order_create_response(
        {
            "orderRejectTransaction": {
                "id": "9",
                "rejectReason": "INSUFFICIENT_MARGIN",
                "errorMessage": "margin",
            }
        }
    )
    assert rejected.outcome == OUTCOME_REJECTED
    assert rejected.error_code == "INSUFFICIENT_MARGIN"
    malformed = classify_order_create_response({"lastTransactionID": "1"})
    assert malformed.outcome == OUTCOME_MALFORMED
    assert classify_order_create_response("nope").outcome == OUTCOME_MALFORMED


def test_transport_timeout_is_ambiguous_v20_400_is_rejected():
    amb = classify_order_create_transport_error(TimeoutError("read timed out"))
    assert amb.outcome == OUTCOME_AMBIGUOUS_TRANSPORT
    rej = classify_order_create_transport_error(V20Error(400, '{"errorMessage":"bad"}'))
    assert rej.outcome == OUTCOME_REJECTED
    amb5 = classify_order_create_transport_error(V20Error(503, "unavailable"))
    assert amb5.outcome == OUTCOME_AMBIGUOUS_TRANSPORT


def _open_with_api(response_or_exc, calls: list):
    class FakeAPI:
        def request(self, r):
            calls.append(r)
            if isinstance(response_or_exc, Exception):
                raise response_or_exc
            return response_or_exc

    with (
        patch("forex_bot.oanda_exec.get_api", return_value=FakeAPI()),
        patch("forex_bot.oanda_exec._account_id", return_value="ACC"),
        patch("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None),
    ):
        return _place_market_order_open_sync(
            "EUR_USD", 2.0, "BUY", "cid-x", stop_loss=1.09900, take_profit=1.10200
        )


def test_ordercreate_fill_is_exactly_one_request():
    calls: list = []
    fp, uf, oid, _pl, _ts = _open_with_api(_fill_response(), calls)
    assert len(calls) == 1
    assert fp == pytest.approx(1.1)
    assert oid == "11"


def test_ordercreate_cancel_is_exactly_one_request_no_second_attempt():
    calls: list = []
    with pytest.raises(OrderCreateCancelled):
        _open_with_api(_cancel_response(), calls)
    assert len(calls) == 1


def test_ordercreate_malformed_is_exactly_one_request():
    calls: list = []
    with pytest.raises(OrderCreateMalformed):
        _open_with_api({"lastTransactionID": "1"}, calls)
    assert len(calls) == 1


def test_ordercreate_ambiguous_timeout_is_exactly_one_request():
    calls: list = []
    with pytest.raises(OrderCreateAmbiguous):
        _open_with_api(TimeoutError("read timed out"), calls)
    assert len(calls) == 1


def test_ordercreate_rejected_is_exactly_one_request():
    calls: list = []
    with pytest.raises(OrderCreateRejected):
        _open_with_api(V20Error(400, '{"errorMessage":"rejected"}'), calls)
    assert len(calls) == 1


def test_async_open_cancel_does_not_look_like_fill(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("OANDA_ACCESS_TOKEN", "tok")

    def fake_place(*_a, **_k):
        raise OrderCreateCancelled(
            OrderCreateClassification(
                outcome=OUTCOME_CANCELLED, cancel_reason="STOP_LOSS_ON_FILL_LOSS"
            ),
            "[ORDER CANCEL] reason=STOP_LOSS_ON_FILL_LOSS",
        )

    monkeypatch.setattr("forex_bot.oanda_exec._place_market_order_open_sync", fake_place)

    async def _run():
        return await __import__("forex_bot.oanda_exec", fromlist=["execute_oanda_market_open"]).execute_oanda_market_open(
            "EUR_USD", 2.0, "BUY", "cid-x", execution_kind="live"
        )

    with pytest.raises(OrderCreateCancelled):
        asyncio.run(_run())


def test_place_open_source_has_single_request_and_no_loop():
    src = inspect.getsource(_place_market_order_open_sync)
    assert src.count("api.request") == 1
    assert "while " not in src
    assert "for _" not in src
