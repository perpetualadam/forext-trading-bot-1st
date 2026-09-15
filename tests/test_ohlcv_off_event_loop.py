"""Candle fetches must not block the asyncio event loop."""

from __future__ import annotations

import asyncio
import threading

from forex_bot.bot_loop import evaluate


def test_evaluate_fetches_ohlcv_off_the_event_loop(monkeypatch):
    threads: list[str] = []

    def fake_ohlcv(symbol, granularity="M5", count=50):
        threads.append(threading.current_thread().name)
        assert symbol == "EUR_USD"
        return None

    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", fake_ohlcv)
    asyncio.run(evaluate("EUR_USD"))
    assert threads
    assert threads[0] != threading.main_thread().name
