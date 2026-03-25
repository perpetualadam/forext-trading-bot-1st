#!/usr/bin/env python3
"""
Final Boss Forex Bot — refactored entrypoint.

Run: python main.py
Env: OANDA_ACCESS_TOKEN, TRADING_MODE, PostgreSQL and alert vars as needed.
"""

from __future__ import annotations

import logging

import uvicorn

from forex_bot.alerts import alert

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    alert("Starting Final Boss Forex Bot")
    uvicorn.run(
        "forex_bot.app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
