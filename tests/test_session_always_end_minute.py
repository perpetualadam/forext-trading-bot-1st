"""FX_SESSION_ALWAYS 00:00–23:59 must include the final UTC minute on weekdays."""

from __future__ import annotations

from datetime import datetime, timezone

from forex_bot.session_rules import (
    fx_market_open_at,
    in_active_session_at,
    is_live_trading,
    symbol_live_window_status,
)


def _utc(y: int, m: int, d: int, hh: int, mm: int, ss: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


def test_tue_wed_thu_235913_utc_open_with_session_always(monkeypatch):
    monkeypatch.setenv("FX_SESSION_ALWAYS", "true")
    samples = [
        _utc(2026, 10, 6, 23, 59, 13),  # Tuesday
        _utc(2026, 10, 7, 23, 59, 13),  # Wednesday
        _utc(2026, 10, 8, 23, 59, 13),  # Thursday
    ]
    for ts in samples:
        assert fx_market_open_at(ts) is True
        assert in_active_session_at("EUR_USD", ts) is True
        assert in_active_session_at("USD_JPY", ts) is True


def test_midnight_transition_weekday(monkeypatch):
    monkeypatch.setenv("FX_SESSION_ALWAYS", "true")
    before = _utc(2026, 10, 8, 23, 59, 13)
    midnight = _utc(2026, 10, 9, 0, 0, 0)  # Friday 00:00 UTC
    assert in_active_session_at("EUR_USD", before) is True
    assert in_active_session_at("EUR_USD", midnight) is True


def test_friday_market_close_remains_closed(monkeypatch):
    monkeypatch.setenv("FX_SESSION_ALWAYS", "true")
    still_open = _utc(2026, 10, 9, 20, 59, 13)
    closed = _utc(2026, 10, 9, 21, 0, 0)
    late = _utc(2026, 10, 9, 23, 59, 13)
    assert fx_market_open_at(still_open) is True
    assert in_active_session_at("EUR_USD", still_open) is True
    assert fx_market_open_at(closed) is False
    assert in_active_session_at("EUR_USD", closed) is False
    assert in_active_session_at("EUR_USD", late) is False


def test_sunday_market_reopen(monkeypatch):
    monkeypatch.setenv("FX_SESSION_ALWAYS", "true")
    before = _utc(2026, 10, 11, 20, 59, 13)
    open_at = _utc(2026, 10, 11, 21, 0, 0)
    assert fx_market_open_at(before) is False
    assert in_active_session_at("EUR_USD", before) is False
    assert fx_market_open_at(open_at) is True
    assert in_active_session_at("EUR_USD", open_at) is True


def test_weekend_saturday_stays_closed(monkeypatch):
    monkeypatch.setenv("FX_SESSION_ALWAYS", "true")
    sat = _utc(2026, 10, 10, 12, 0, 0)
    assert fx_market_open_at(sat) is False
    assert in_active_session_at("GBP_USD", sat) is False


def test_bst_and_gmt_live_window_includes_end_minute(monkeypatch):
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    monkeypatch.setenv("LIVE_EUR_USD_START", "00:00")
    monkeypatch.setenv("LIVE_EUR_USD_END", "23:59")
    bst_local_end = _utc(2026, 7, 14, 22, 59, 13)  # 23:59:13 BST
    gmt_local_end = _utc(2026, 1, 13, 23, 59, 13)  # 23:59:13 GMT
    for ts, label in ((bst_local_end, "BST"), (gmt_local_end, "GMT")):
        snap = symbol_live_window_status("EUR_USD", at_utc=ts)
        assert snap["dst_label"] == label
        assert snap["inside"] is True
        assert is_live_trading("EUR_USD", at_utc=ts) is True


def test_uk_dst_weekdays_around_clock_changes(monkeypatch):
    monkeypatch.setenv("FX_SESSION_ALWAYS", "true")
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    monkeypatch.setenv("LIVE_EUR_USD_START", "00:00")
    monkeypatch.setenv("LIVE_EUR_USD_END", "23:59")
    # Spring forward Sunday 29 Mar 2026; use adjacent weekdays.
    gmt_thu = _utc(2026, 3, 26, 23, 59, 13)
    bst_tue = _utc(2026, 3, 31, 22, 59, 13)  # 23:59:13 BST
    assert in_active_session_at("EUR_USD", gmt_thu) is True
    assert in_active_session_at("EUR_USD", bst_tue) is True
    assert symbol_live_window_status("EUR_USD", at_utc=gmt_thu)["dst_label"] == "GMT"
    assert symbol_live_window_status("EUR_USD", at_utc=bst_tue)["dst_label"] == "BST"
    assert symbol_live_window_status("EUR_USD", at_utc=gmt_thu)["inside"] is True
    assert symbol_live_window_status("EUR_USD", at_utc=bst_tue)["inside"] is True
    # Autumn back Sunday 25 Oct 2026; adjacent weekdays.
    bst_thu = _utc(2026, 10, 22, 22, 59, 13)
    gmt_tue = _utc(2026, 10, 27, 23, 59, 13)
    assert in_active_session_at("EUR_USD", bst_thu) is True
    assert in_active_session_at("EUR_USD", gmt_tue) is True
    assert symbol_live_window_status("EUR_USD", at_utc=bst_thu)["dst_label"] == "BST"
    assert symbol_live_window_status("EUR_USD", at_utc=gmt_tue)["dst_label"] == "GMT"
    assert symbol_live_window_status("EUR_USD", at_utc=bst_thu)["inside"] is True
    assert symbol_live_window_status("EUR_USD", at_utc=gmt_tue)["inside"] is True
