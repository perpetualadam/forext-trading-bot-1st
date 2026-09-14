"""LIVE_* windows are local to LIVE_TIMEZONE; Europe/London applies BST vs GMT."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from forex_bot.session_rules import (
    format_live_window_log,
    is_live_trading,
    live_windows_status,
    resolve_live_timezone,
    symbol_live_window_status,
)


@pytest.fixture
def london_tz(monkeypatch):
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    monkeypatch.setenv("LIVE_EUR_USD_START", "13:00")
    monkeypatch.setenv("LIVE_EUR_USD_END", "17:00")
    monkeypatch.delenv("TZ", raising=False)


def test_resolve_alias_bst_is_london(monkeypatch):
    monkeypatch.setenv("LIVE_TIMEZONE", "BST")
    tz, name, source = resolve_live_timezone()
    assert getattr(tz, "key", name) == "Europe/London"
    assert name == "Europe/London"
    assert source == "LIVE_TIMEZONE"


def test_auto_uses_tz_env(monkeypatch):
    monkeypatch.setenv("LIVE_TIMEZONE", "auto")
    monkeypatch.setenv("TZ", "Europe/London")
    tz, name, source = resolve_live_timezone()
    assert name == "Europe/London"
    assert source == "TZ"
    assert getattr(tz, "key", None) == "Europe/London"


def test_september_bst_maps_13_17_to_12_16_utc(london_tz):
    # 12:30 UTC = 13:30 BST → inside
    inside_at = datetime(2026, 9, 14, 12, 30, tzinfo=timezone.utc)
    assert is_live_trading("EUR_USD", at_utc=inside_at) is True
    snap = symbol_live_window_status("EUR_USD", at_utc=inside_at)
    assert snap["dst_label"] == "BST"
    assert snap["utc_window"] == "12:00-16:00"
    assert snap["local_window"] == "13:00-17:00"
    assert snap["inside"] is True

    # 11:30 UTC = 12:30 BST → still before 13:00 local
    before = datetime(2026, 9, 14, 11, 30, tzinfo=timezone.utc)
    assert is_live_trading("EUR_USD", at_utc=before) is False
    assert symbol_live_window_status("EUR_USD", at_utc=before)["inside"] is False


def test_january_gmt_keeps_13_17_utc(london_tz):
    inside_at = datetime(2026, 1, 15, 13, 30, tzinfo=timezone.utc)
    assert is_live_trading("EUR_USD", at_utc=inside_at) is True
    snap = symbol_live_window_status("EUR_USD", at_utc=inside_at)
    assert snap["dst_label"] == "GMT"
    assert snap["utc_window"] == "13:00-17:00"

    before = datetime(2026, 1, 15, 12, 30, tzinfo=timezone.utc)
    assert is_live_trading("EUR_USD", at_utc=before) is False


def test_status_and_log_line_include_in_out(london_tz, monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    at = datetime(2026, 9, 14, 12, 30, tzinfo=timezone.utc)
    status = live_windows_status(["EUR_USD"], at_utc=at)
    assert status["dst_label"] == "BST"
    assert status["symbols"][0]["inside"] is True
    line = format_live_window_log(status)
    assert line.startswith("[LIVE WINDOW]")
    assert "EUR_USD IN" in line
    assert "utc=12:00-16:00" in line
