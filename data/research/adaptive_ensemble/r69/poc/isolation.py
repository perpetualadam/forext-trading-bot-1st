"""Install inert replacements before any operational import.

Import this module before ``forex_bot``. It does not read ``.env``.
"""

from __future__ import annotations

import builtins
import os
import socket
import sys
from types import ModuleType

ATTEMPTS: list[tuple] = []
ISOLATION_READY = False

_SECRET_MARKERS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASS",
    "API_KEY",
    "ACCOUNT",
    "POSTGRES",
    "DATABASE",
    "DSN",
    "TELEGRAM",
    "DISCORD",
    "OANDA",
    "CREDENTIAL",
)


class IsolationBreach(RuntimeError):
    pass


def _scrub_environment() -> None:
    for key in list(os.environ):
        upper = key.upper()
        if any(marker in upper for marker in _SECRET_MARKERS):
            os.environ[key] = ""
    os.environ["PERSIST_RECONCILE_STATE"] = "0"
    os.environ["PERSIST_EXEC_ORDERS"] = "false"
    os.environ["RECONCILE_ACTION"] = "log_only"
    os.environ["EXECUTION_MODE"] = "paper"
    os.environ["RECONCILE_IMPORT_BROKER_POSITIONS"] = "false"
    os.environ["RECONCILE_ADJUST_UNITS"] = "false"
    os.environ["RECONCILE_AUTO_FIX_IN_PAPER"] = "false"
    os.environ["USE_OANDA_LIVE"] = "false"


def _install_dotenv_stub() -> None:
    dotenv = ModuleType("dotenv")

    def load_dotenv(*args, **kwargs):
        ATTEMPTS.append(("load_dotenv", tuple(str(a) for a in args), tuple(sorted(kwargs))))
        return False

    dotenv.load_dotenv = load_dotenv
    sys.modules["dotenv"] = dotenv


def _install_config_stub() -> None:
    module = ModuleType("forex_bot.config")
    module.IS_R69_SYNTHETIC = True

    class _Postgres:
        db = "trading"
        user = "postgres"
        password = ""
        host = "127.0.0.1"
        port = 1

    class Config:
        SYMBOLS = ["EUR_USD"]
        BASE_BALANCE = 10000.0
        TRADE_INTERVAL = 60
        TRADING_MODE = "practice"
        POSTGRES = _Postgres()
        TELEGRAM_TOKEN = ""
        TELEGRAM_CHAT_ID = ""
        DISCORD_WEBHOOK_URL = ""
        OANDA_ACCOUNT_ID = "001-002-0000001-003"
        OANDA_ACCESS_TOKEN = ""
        PAPER_TRADING = True

        @classmethod
        def set_trading_mode(cls, mode: str) -> None:
            cls.TRADING_MODE = mode

    module.Config = Config
    sys.modules["forex_bot.config"] = module


def _loopback(address) -> bool:
    host = address[0] if isinstance(address, tuple) and address else address
    return str(host) in {"127.0.0.1", "::1", "localhost"}


def _install_network_guard() -> None:
    real_connect = socket.socket.connect
    real_create = socket.create_connection

    def _refuse(kind, target):
        ATTEMPTS.append((kind, repr(target)))
        raise IsolationBreach(f"{kind} blocked")

    def _connect(self, address):
        if _loopback(address):
            return real_connect(self, address)
        _refuse("socket.connect", address)

    def _create_connection(address, *args, **kwargs):
        if _loopback(address):
            return real_create(address, *args, **kwargs)
        _refuse("socket.create_connection", address)

    socket.socket.connect = _connect
    socket.create_connection = _create_connection

    import urllib.request

    def _urlopen(*args, **kwargs):
        _refuse("urllib.request.urlopen", args[:1])

    urllib.request.urlopen = _urlopen


def _install_open_guard() -> None:
    real_open = builtins.open

    def guarded(file, mode="r", *args, **kwargs):
        name = str(file).replace("\\", "/").lower()
        blocked = (
            name.endswith("/.env")
            or name.endswith(".env")
            or name.endswith("one_session.permit")
            or "credential" in name
        )
        if blocked:
            ATTEMPTS.append(("open", name, mode))
            raise IsolationBreach(f"refusing to open {name}")
        return real_open(file, mode, *args, **kwargs)

    builtins.open = guarded


def _install_database_guard() -> None:
    try:
        import psycopg2
    except ImportError:
        psycopg2 = ModuleType("psycopg2")
        extras = ModuleType("psycopg2.extras")
        extensions = ModuleType("psycopg2.extensions")

        class _DbType:
            pass

        extras.Json = lambda value: value
        extensions.connection = _DbType
        extensions.cursor = _DbType
        psycopg2.extras = extras
        psycopg2.extensions = extensions
        sys.modules["psycopg2"] = psycopg2
        sys.modules["psycopg2.extras"] = extras
        sys.modules["psycopg2.extensions"] = extensions

    def _connect(*args, **kwargs):
        ATTEMPTS.append(("psycopg2.connect",))
        raise IsolationBreach("postgres blocked")

    psycopg2.connect = _connect


def install() -> None:
    global ISOLATION_READY
    if ISOLATION_READY:
        return
    _scrub_environment()
    _install_dotenv_stub()
    _install_config_stub()
    _install_open_guard()
    _install_network_guard()
    _install_database_guard()
    ISOLATION_READY = True


install()
