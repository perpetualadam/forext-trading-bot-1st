"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PostgresConfig:
    db: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "trading"))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASS", "password"))
    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))


class Config:
    SYMBOLS: list[str] = ["EUR_USD", "GBP_USD", "USD_JPY"]
    BASE_BALANCE: float = 10000.0
    TRADE_INTERVAL: int = 60

    TRADING_MODE: str = os.getenv("TRADING_MODE", "practice").lower()

    POSTGRES = PostgresConfig()

    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    OANDA_ACCOUNT_ID: str = os.getenv("OANDA_ACCOUNT_ID", "")
    OANDA_ACCESS_TOKEN: str = os.getenv("OANDA_ACCESS_TOKEN", "")

    # Paper / simulation path (spread+slippage sim). false → legacy random PnL until real OANDA fills exist.
    PAPER_TRADING: bool = (os.getenv("PAPER_TRADING") or "true").strip().lower() in ("1", "true", "yes", "on")

    @classmethod
    def set_trading_mode(cls, mode: str) -> None:
        m = mode.lower().strip()
        if m not in ("live", "practice"):
            raise ValueError("mode must be 'live' or 'practice'")
        cls.TRADING_MODE = m
