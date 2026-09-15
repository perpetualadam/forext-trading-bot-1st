"""Six-pair universe, pip/quote convention, windows, hybrid, cap, reconcile, diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from forex_bot.config import Config
from forex_bot.oanda_client import oanda_instrument
from forex_bot.oanda_exec import _format_oanda_price
from forex_bot.portfolio_exposure import (
    approx_gross_usd_notional_for,
    configured_max_gross_usd,
    format_notional_cap_skip_alert,
    notional_cap_decision,
)
from forex_bot.positions import Position, positions
from forex_bot.profit_protection import (
    apply_profit_protection,
    atr_to_pips,
    pip_size,
    unrealized_profit_pips,
)
from forex_bot.session_rules import is_live_trading, live_windows_status, read_scalp_windows
from forex_bot.state import set_broker_account
from forex_bot.strategy_meta import hybrid_enabled
from forex_bot.symbols import (
    DEFAULT_FOREX_SYMBOLS,
    is_valid_oanda_forex_symbol,
    normalize_oanda_symbol,
    parse_forex_symbols,
    quote_currency,
)
from forex_bot.trade_diagnostics import snapshot_from_position
from forex_bot.trading import sl_tp_price_distances


SIX = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"]


def _pos(
    symbol: str,
    *,
    direction: str = "BUY",
    entry: float = 1.10000,
    tp_pips: float = 24.0,
    sl_pips: float = 20.0,
) -> Position:
    pip = pip_size(symbol)
    if direction == "SELL":
        sl = entry + sl_pips * pip
        tp = entry - tp_pips * pip
    else:
        sl = entry - sl_pips * pip
        tp = entry + tp_pips * pip
    return Position(
        symbol=symbol,
        direction=direction,
        units=2.0,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        open_time=0.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind="live",
    )


def _px(symbol: str, entry: float, pips: float, direction: str = "BUY") -> float:
    pip = pip_size(symbol)
    if direction == "SELL":
        return entry - pips * pip
    return entry + pips * pip


def test_default_universe_is_six_canonical_pairs():
    assert DEFAULT_FOREX_SYMBOLS == SIX
    assert parse_forex_symbols("") == SIX
    assert parse_forex_symbols(None) == SIX
    assert list(Config.SYMBOLS) == SIX


def test_env_parses_six_symbol_universe(monkeypatch):
    monkeypatch.setenv(
        "FOREX_SYMBOLS",
        "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF",
    )
    assert Config.SYMBOLS == SIX


def test_duplicate_symbols_keep_first(monkeypatch):
    monkeypatch.setenv("FOREX_SYMBOLS", "EUR_USD, eur/usd, GBP_USD, EUR_USD")
    assert parse_forex_symbols() == ["EUR_USD", "GBP_USD"]


def test_malformed_symbols_rejected_safely():
    out = parse_forex_symbols("EURUSD,EUR_US,EUR_USD_GBP,123_456,,EUR_USD,USDGBP")
    assert out == ["EUR_USD"]
    assert parse_forex_symbols("EURUSD,not-a-pair") == SIX


def test_does_not_reverse_base_quote():
    assert normalize_oanda_symbol("GBP_USD") == "GBP_USD"
    assert normalize_oanda_symbol("USD_GBP") == "USD_GBP"
    assert parse_forex_symbols("USD_GBP") == ["USD_GBP"]
    assert quote_currency("GBP_USD") == "USD"


def test_canonical_base_quote_and_oanda_instrument():
    assert normalize_oanda_symbol("aud/usd") == "AUD_USD"
    assert normalize_oanda_symbol("usd-cad") == "USD_CAD"
    assert normalize_oanda_symbol("Usd_Chf") == "USD_CHF"
    for sym in SIX:
        assert is_valid_oanda_forex_symbol(sym)
        assert oanda_instrument(sym) == sym
        assert "/" not in oanda_instrument(sym)
        assert oanda_instrument(sym.replace("_", "/")) == sym


@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("EUR_USD", 0.0001),
        ("GBP_USD", 0.0001),
        ("USD_JPY", 0.01),
        ("AUD_USD", 0.0001),
        ("USD_CAD", 0.0001),
        ("USD_CHF", 0.0001),
        ("EUR_JPY", 0.01),
        ("JPY_USD", 0.0001),
    ],
)
def test_pip_size_from_quote_currency(symbol, expected):
    assert pip_size(symbol) == expected


@pytest.mark.parametrize("symbol,entry", [("AUD_USD", 0.65000), ("USD_CAD", 1.36000), ("USD_CHF", 0.89000)])
def test_buy_and_sell_pips_new_pairs(symbol, entry):
    buy_px = _px(symbol, entry, 10.0, "BUY")
    sell_px = _px(symbol, entry, 10.0, "SELL")
    assert unrealized_profit_pips(symbol, "BUY", entry, buy_px) == pytest.approx(10.0)
    assert unrealized_profit_pips(symbol, "SELL", entry, sell_px) == pytest.approx(10.0)
    assert unrealized_profit_pips(symbol, "BUY", entry, _px(symbol, entry, -6.0, "BUY")) == pytest.approx(-6.0)


@pytest.mark.parametrize("symbol,atr_price,pips", [("AUD_USD", 0.0008, 8.0), ("USD_CAD", 0.0010, 10.0), ("USD_CHF", 0.0006, 6.0), ("USD_JPY", 0.08, 8.0)])
def test_atr_to_pips_new_pairs(symbol, atr_price, pips):
    assert atr_to_pips(symbol, atr_price) == pytest.approx(pips)


@pytest.mark.parametrize("symbol,entry", [("AUD_USD", 0.65000), ("USD_CAD", 1.36000), ("USD_CHF", 0.89000)])
def test_mfe_mae_and_67pct_atr_giveback(symbol, entry):
    pos = _pos(symbol, entry=entry, tp_pips=24.0)
    atr = 8.0 * pip_size(symbol)
    apply_profit_protection(pos, _px(symbol, entry, -5.0), atr_price=atr)
    assert pos.max_adverse_pips == pytest.approx(5.0)
    d10 = apply_profit_protection(pos, _px(symbol, entry, 10.0), atr_price=atr)
    assert d10.active is False
    assert pos.max_profit_pips == pytest.approx(10.0)
    d16 = apply_profit_protection(pos, _px(symbol, entry, 16.1), atr_price=atr)
    assert d16.active is True
    assert d16.exit_threshold_pips == pytest.approx(12.1)
    d_give = apply_profit_protection(pos, _px(symbol, entry, 12.1), atr_price=atr)
    assert d_give.should_close is True
    sell = _pos(symbol, direction="SELL", entry=entry, tp_pips=24.0)
    ds = apply_profit_protection(sell, _px(symbol, entry, 16.1, "SELL"), atr_price=atr)
    assert ds.active is True
    assert ds.current_pips == pytest.approx(16.1)


@pytest.mark.parametrize("symbol,sl,tp", [("EUR_USD", 0.0020, 0.0040), ("GBP_USD", 0.0020, 0.0040), ("USD_JPY", 0.20, 0.40), ("AUD_USD", 0.0020, 0.0040), ("USD_CAD", 0.0020, 0.0040), ("USD_CHF", 0.0020, 0.0040)])
def test_sl_fallback_is_20_pips(symbol, sl, tp):
    got_sl, got_tp = sl_tp_price_distances(symbol)
    assert got_sl == pytest.approx(sl)
    assert got_tp == pytest.approx(tp)


def test_unconfigured_live_window_is_24_5_not_overlap(monkeypatch):
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    for sym in ("AUD_USD", "USD_CAD", "USD_CHF"):
        monkeypatch.delenv(f"LIVE_{sym}_START", raising=False)
        monkeypatch.delenv(f"LIVE_{sym}_END", raising=False)
    morning = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)  # 09:00 BST
    assert is_live_trading("AUD_USD", at_utc=morning) is True
    assert is_live_trading("USD_CAD", at_utc=morning) is True
    assert is_live_trading("USD_CHF", at_utc=morning) is True


def test_explicit_24_5_windows_for_new_pairs(monkeypatch):
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    for sym in ("AUD_USD", "USD_CAD", "USD_CHF"):
        monkeypatch.setenv(f"LIVE_{sym}_START", "00:00")
        monkeypatch.setenv(f"LIVE_{sym}_END", "23:59")
    at = datetime(2026, 9, 14, 21, 30, tzinfo=timezone.utc)
    status = live_windows_status(["AUD_USD", "USD_CAD", "USD_CHF"], at_utc=at)
    assert all(p["inside"] for p in status["symbols"])
    assert all(p["local_window"] == "00:00-23:59" for p in status["symbols"])


def test_hybrid_new_pairs_match_enabled_majors(monkeypatch):
    monkeypatch.setenv("HYBRID_EUR_USD", "true")
    monkeypatch.setenv("HYBRID_GBP_USD", "true")
    monkeypatch.setenv("HYBRID_USD_JPY", "false")
    monkeypatch.setenv("HYBRID_AUD_USD", "true")
    monkeypatch.setenv("HYBRID_USD_CAD", "true")
    monkeypatch.setenv("HYBRID_USD_CHF", "true")
    assert hybrid_enabled("EUR_USD") is True
    assert hybrid_enabled("GBP_USD") is True
    assert hybrid_enabled("USD_JPY") is False
    assert hybrid_enabled("AUD_USD") is True
    assert hybrid_enabled("USD_CAD") is True
    assert hybrid_enabled("USD_CHF") is True


def test_scalp_windows_follow_configured_universe(monkeypatch):
    monkeypatch.setenv("FOREX_SYMBOLS", "AUD_USD,USD_CAD")
    monkeypatch.setenv("SCALP_AUD_USD_START", "13:00")
    monkeypatch.setenv("SCALP_AUD_USD_END", "15:00")
    wins = read_scalp_windows()
    assert "AUD_USD" in wins
    assert "USD_JPY" not in wins


def test_six_symbols_do_not_bypass_existing_gross_cap(monkeypatch):
    monkeypatch.setenv("FOREX_SYMBOLS", ",".join(SIX))
    monkeypatch.setenv("POSITION_NOTIONAL_PCT_OF_NAV", "0.02")
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.06")
    set_broker_account(100.0, "USD")
    assert list(Config.SYMBOLS) == SIX
    assert configured_max_gross_usd() == pytest.approx(6.0)
    positions.clear()
    positions["EUR_USD"] = _pos("EUR_USD", entry=1.0)
    positions["EUR_USD"].units = 2.0
    positions["GBP_USD"] = _pos("GBP_USD", entry=1.0)
    positions["GBP_USD"].units = 2.0
    positions["USD_JPY"] = _pos("USD_JPY", entry=150.0)
    positions["USD_JPY"].units = 2.0
    proposed = approx_gross_usd_notional_for("AUD_USD", 2.0, 0.65)
    decision = notional_cap_decision(proposed)
    assert decision["exceeds"] is True
    skip = format_notional_cap_skip_alert(
        "AUD_USD", decision, nav=100.0, currency="USD", direction="BUY"
    )
    assert "Candidate symbol: AUD_USD" in skip
    assert "Candidate side: BUY" in skip
    assert "Resulting gross exposure:" in skip
    assert "Maximum portfolio gross exposure: 6.00 USD" in skip
    assert "Rejection reason: resulting gross exposure exceeds configured portfolio cap" in skip
    positions.clear()


def test_reconcile_keeps_canonical_new_symbols(monkeypatch):
    from forex_bot import reconciliation as rec

    monkeypatch.setattr(Config, "OANDA_ACCOUNT_ID", "001-test")
    monkeypatch.setattr(rec, "get_api", lambda: object())

    def fake_request(api, r, context=""):
        return {
            "positions": [
                {
                    "instrument": "AUD_USD",
                    "long": {"units": "12", "averagePrice": "0.65000"},
                    "short": {"units": "0", "averagePrice": "0"},
                },
                {
                    "instrument": "usd/cad",
                    "long": {"units": "0", "averagePrice": "0"},
                    "short": {"units": "-7", "averagePrice": "1.36000"},
                },
                {
                    "instrument": "USD_CHF",
                    "long": {"units": "3", "averagePrice": "0.89000"},
                    "short": {"units": "0", "averagePrice": "0"},
                },
            ]
        }

    monkeypatch.setattr("forex_bot.oanda_client._oanda_request", fake_request)
    detail = rec.fetch_broker_positions_detail()
    assert set(detail) == {"AUD_USD", "USD_CAD", "USD_CHF"}
    assert detail["AUD_USD"][0] == pytest.approx(12.0)
    assert detail["USD_CAD"][0] == pytest.approx(-7.0)
    assert detail["USD_CHF"][0] == pytest.approx(3.0)


@pytest.mark.parametrize("symbol,entry", [("AUD_USD", 0.65000), ("USD_CAD", 1.36000), ("USD_CHF", 0.89000)])
def test_diagnostics_serialize_new_symbols(symbol, entry):
    pos = _pos(symbol, entry=entry, tp_pips=24.0)
    atr = 8.0 * pip_size(symbol)
    apply_profit_protection(pos, _px(symbol, entry, 16.1), atr_price=atr)
    snap = snapshot_from_position(
        pos, exit_reason="profit_protection", exit_price=_px(symbol, entry, 12.1)
    )
    assert snap["symbol"] == symbol
    assert snap["profit_protection_activated"] is True
    assert snap["exited_on_profit_protection"] is True
    assert snap["mfe_pips"] == pytest.approx(16.1)
    assert snap["settings"]["trigger_percent"] == 0.67


def test_oanda_price_format_new_pairs_are_non_jpy():
    assert _format_oanda_price("AUD_USD", 0.65123) == "0.65123"
    assert _format_oanda_price("USD_CAD", 1.36123) == "1.36123"
    assert _format_oanda_price("USD_CHF", 0.89123) == "0.89123"
    assert _format_oanda_price("USD_JPY", 150.123) == "150.123"
