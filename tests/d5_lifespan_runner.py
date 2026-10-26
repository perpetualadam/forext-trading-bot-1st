"""Isolated lifespan runner. Invoked as a script, not collected as tests.

Guards are installed before forex_bot.app is imported.
"""

from __future__ import annotations

import asyncio
import builtins
import hashlib
import json
import os
import socket
import sys
import traceback
import types
import urllib.request
from pathlib import Path

COUNTS: dict[str, int] = {}
EVENTS: list[str] = []
NETWORK: list[str] = []
SELF_PIPE: list[str] = []
FS_DENIALS: list[str] = []
_ORIG_CONNECT = socket.socket.connect
DOTENV_CALLS = 0
_REAL_OPEN = builtins.open


def _bump(name: str) -> None:
    COUNTS[name] = COUNTS.get(name, 0) + 1
    EVENTS.append(name)


def _deny_network(kind: str, address: object = None) -> None:
    NETWORK.append(f"{kind} {address!r}")
    raise RuntimeError(f"d5 network denied {kind} {address!r}")


def _install_network_guard() -> None:
    def blocked_connect(self: object, address: object) -> None:
        _ = self
        _deny_network("socket.connect", address)

    def blocked_connect_ex(self: object, address: object) -> int:
        _ = self
        _deny_network("socket.connect_ex", address)
        return 1

    def blocked_create(*_a: object, **_k: object) -> None:
        _deny_network("socket.create_connection")

    def blocked_urlopen(*_a: object, **_k: object) -> None:
        _deny_network("urllib.request.urlopen")

    async def blocked_open_connection(*_a: object, **_k: object) -> None:
        _deny_network("asyncio.open_connection")

    def loopback_socketpair(
        family: int = socket.AF_INET,
        sock_type: int = socket.SOCK_STREAM,
        proto: int = 0,
    ) -> tuple[socket.socket, socket.socket]:
        """Event-loop wakeup only. Connects solely to a port this process just bound."""
        if family == socket.AF_INET:
            host = "127.0.0.1"
        elif family == socket.AF_INET6:
            host = "::1"
        else:
            _deny_network("socket.socketpair", family)
            raise AssertionError("unreachable")
        if sock_type != socket.SOCK_STREAM or proto != 0:
            _deny_network("socket.socketpair", (sock_type, proto))
            raise AssertionError("unreachable")
        listener = socket.socket(family, sock_type, proto)
        try:
            listener.bind((host, 0))
            listener.listen()
            addr, port = listener.getsockname()[:2]
            SELF_PIPE.append(f"{addr}:{port}")
            client = socket.socket(family, sock_type, proto)
            try:
                client.setblocking(False)
                try:
                    _ORIG_CONNECT(client, (addr, port))
                except (BlockingIOError, InterruptedError):
                    pass
                client.setblocking(True)
                server, _peer = listener.accept()
            except OSError:
                client.close()
                raise
        finally:
            listener.close()
        try:
            if (
                server.getsockname() != client.getpeername()
                or client.getsockname() != server.getpeername()
            ):
                raise ConnectionError("unexpected self-pipe peer")
        except (OSError, ConnectionError):
            server.close()
            client.close()
            raise
        return server, client

    socket.socket.connect = blocked_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked_connect_ex  # type: ignore[method-assign]
    socket.create_connection = blocked_create  # type: ignore[assignment]
    socket.socketpair = loopback_socketpair  # type: ignore[assignment]
    urllib.request.urlopen = blocked_urlopen  # type: ignore[assignment]
    asyncio.open_connection = blocked_open_connection  # type: ignore[assignment]


def _install_fs_guard() -> None:
    def guarded(file: object, *args: object, **kwargs: object) -> object:
        text = os.fspath(file)  # type: ignore[arg-type]
        folded = str(text).replace("\\", "/").lower()
        base = os.path.basename(str(text)).lower()
        blocked = (
            base == ".env"
            or base.endswith(".env")
            or "data/ops" in folded
            or "v2_shadow" in folded
            or "credential" in base
        )
        if blocked:
            FS_DENIALS.append(base or folded)
            raise PermissionError("d5 path denied")
        return _REAL_OPEN(file, *args, **kwargs)

    builtins.open = guarded  # type: ignore[assignment]


def _confine_import_path() -> bool:
    banned = "concensus-forecast"
    sys.path[:] = [
        item
        for item in sys.path
        if banned not in str(item).replace("\\", "/").lower()
    ]
    repo = str(Path(__file__).resolve().parents[1])
    if repo not in sys.path:
        sys.path.insert(0, repo)
    for module in sys.modules.values():
        origin = str(getattr(module, "__file__", "") or "")
        if banned in origin.replace("\\", "/").lower():
            raise RuntimeError("foreign project module already loaded")
    return any(banned in str(item).replace("\\", "/").lower() for item in sys.path)


def _install_import_fakes() -> None:
    dotenv = types.ModuleType("dotenv")

    def load_dotenv(*_a: object, **_k: object) -> bool:
        global DOTENV_CALLS
        DOTENV_CALLS += 1
        return False

    dotenv.load_dotenv = load_dotenv  # type: ignore[attr-defined]
    sys.modules["dotenv"] = dotenv

    requests = types.ModuleType("requests")

    def _http(*_a: object, **_k: object) -> None:
        _bump("requests")
        raise RuntimeError("d5 http denied")

    requests.post = _http  # type: ignore[attr-defined]
    requests.get = _http  # type: ignore[attr-defined]
    requests.request = _http  # type: ignore[attr-defined]
    adapters = types.ModuleType("requests.adapters")

    class HTTPAdapter:
        def __init__(self, *_a: object, **_k: object) -> None:
            return None

    adapters.HTTPAdapter = HTTPAdapter  # type: ignore[attr-defined]
    requests.adapters = adapters  # type: ignore[attr-defined]
    sys.modules["requests"] = requests
    sys.modules["requests.adapters"] = adapters

    psy = types.ModuleType("psycopg2")

    def connect(*_a: object, **_k: object) -> None:
        _bump("psycopg2.connect")
        raise RuntimeError("d5 database denied")

    psy.connect = connect  # type: ignore[attr-defined]
    extras = types.ModuleType("psycopg2.extras")
    extras.Json = lambda value: value  # type: ignore[attr-defined]
    extensions = types.ModuleType("psycopg2.extensions")
    extensions.connection = object  # type: ignore[attr-defined]
    extensions.cursor = object  # type: ignore[attr-defined]
    psy.extras = extras  # type: ignore[attr-defined]
    psy.extensions = extensions  # type: ignore[attr-defined]
    sys.modules["psycopg2"] = psy
    sys.modules["psycopg2.extras"] = extras
    sys.modules["psycopg2.extensions"] = extensions


def _fake_async(name: str):
    async def _inner() -> None:
        _bump(name)
        await asyncio.Event().wait()

    _inner.__name__ = name
    return _inner


def _install_call_fakes(appmod: types.ModuleType) -> None:
    def record(name: str):
        def _call(*_a: object, **_k: object) -> None:
            _bump(name)

        return _call

    appmod.get_connection = record("get_connection")  # type: ignore[attr-defined]
    appmod.build_api = record("build_api")  # type: ignore[attr-defined]
    appmod.fetch_account_summary = record("fetch_account_summary")  # type: ignore[attr-defined]
    appmod.alert = record("alert")  # type: ignore[attr-defined]
    appmod.load_operational_events_cache_from_db = record(  # type: ignore[attr-defined]
        "load_operational_events"
    )
    appmod.run_bot = _fake_async("run_bot")  # type: ignore[attr-defined]
    appmod.reconciliation_loop = _fake_async("reconciliation_loop")  # type: ignore[attr-defined]
    appmod.health_snapshot_loop = _fake_async("health_snapshot_loop")  # type: ignore[attr-defined]
    appmod.telegram_inbound_loop = _fake_async("telegram_inbound_loop")  # type: ignore[attr-defined]

    orders = sys.modules["forex_bot.orders"]
    orders.load_open_orders_from_db_into_memory = record("load_open_orders")  # type: ignore[attr-defined]

    reconciliation = types.ModuleType("forex_bot.reconciliation")
    reconciliation.load_reconcile_state_from_db = record("load_reconcile_state")  # type: ignore[attr-defined]
    reconciliation.run_reconciliation_once = record("run_reconciliation_once")  # type: ignore[attr-defined]
    sys.modules["forex_bot.reconciliation"] = reconciliation

    telegram = types.ModuleType("forex_bot.telegram_control")
    telegram.start_telegram_control = record("start_telegram_control")  # type: ignore[attr-defined]
    telegram.stop_telegram_control = record("stop_telegram_control")  # type: ignore[attr-defined]
    sys.modules["forex_bot.telegram_control"] = telegram

    real_create = asyncio.create_task

    def counting_create(coro, *args, **kwargs):  # type: ignore[no-untyped-def]
        code = getattr(getattr(coro, "cr_code", None), "co_name", "")
        _bump("create_task")
        EVENTS.append("scheduled:" + code)
        return real_create(coro, *args, **kwargs)

    asyncio.create_task = counting_create  # type: ignore[assignment]

    ox = sys.modules.get("forex_bot.oanda_exec")
    if ox is None:
        return
    for name, obj in list(vars(ox).items()):
        if not callable(obj) or name.startswith("_"):
            continue
        lowered = name.lower()
        if not any(part in lowered for part in ("order", "place", "submit")):
            continue

        def _wrapped(*_a: object, _name: str = name, **_k: object) -> None:
            _bump("order_route:" + _name)
            raise RuntimeError("d5 order routing denied")

        setattr(ox, name, _wrapped)


def _file_sha() -> str:
    path = Path(os.environ["LIVE_SAFETY_STATE_PATH"])
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot() -> dict[str, object]:
    from forex_bot.live_safety import live_order_auth_state, live_safety_initialised
    from forex_bot.strategy_meta import strategies

    active = sorted(name for name, strat in strategies.items() if strat.active is True)
    return {
        "auth": live_order_auth_state(),
        "initialised": live_safety_initialised(),
        "active": active,
        "counts": dict(COUNTS),
        "events": list(EVENTS),
        "network": list(NETWORK),
        "fs_denials": list(FS_DENIALS),
        "dotenv_calls": DOTENV_CALLS,
        "file_sha256": _file_sha(),
    }


def _reset_counters() -> None:
    COUNTS.clear()
    EVENTS.clear()


async def _invoke(appmod: types.ModuleType) -> dict[str, object]:
    aborted = False
    abort_type = ""
    message = ""
    try:
        async with appmod.lifespan(appmod.app):
            _bump("yielded")
    except appmod.StartupSafetyAbort as exc:
        aborted = True
        abort_type = type(exc).__name__
        message = str(exc)
    return {"aborted": aborted, "abort_type": abort_type, "message": message}


def main() -> int:
    out_path = Path(sys.argv[1])
    report: dict[str, object] = {}
    try:
        report["foreign_project_on_path"] = _confine_import_path()
        _install_network_guard()
        _install_fs_guard()
        _install_import_fakes()
        import forex_bot.app as appmod
        from forex_bot import live_safety
        from forex_bot.live_safety import (
            _blank_document,
            reset_live_safety_for_tests,
        )

        original_read = live_safety._read_text
        _install_call_fakes(appmod)
        safety = Path(os.environ["LIVE_SAFETY_STATE_PATH"])
        report["dotenv_calls_at_import"] = DOTENV_CALLS
        report["entrypoint"] = "async with forex_bot.app.lifespan(app)"
        cases: dict[str, dict[str, object]] = {}

        def write(payload: bytes) -> None:
            safety.write_bytes(payload)

        def valid() -> None:
            document = _blank_document(reason="operator_preflight_blocked")
            write(json.dumps(document).encode("utf-8"))

        def run(label: str, setup) -> dict[str, object]:  # type: ignore[no-untyped-def]
            _reset_counters()
            reset_live_safety_for_tests()
            if safety.exists():
                safety.unlink()
            setup()
            existed = safety.exists()
            before = safety.read_bytes() if existed else b""
            outcome = asyncio.run(_invoke(appmod))
            snap = _snapshot()
            snap.update(outcome)
            snap["existed_before"] = existed
            snap["exists_after"] = safety.exists()
            snap["bytes_unchanged"] = existed and safety.read_bytes() == before
            cases[label] = snap
            if NETWORK or FS_DENIALS:
                raise RuntimeError("isolation guard tripped")
            return snap

        run("valid_blocked", valid)

        def allowed() -> None:
            from forex_bot.live_safety import AUTH_ALLOWED

            document = _blank_document(reason="previous_process")
            document["live_order_authorisation"]["state"] = AUTH_ALLOWED
            write(json.dumps(document).encode("utf-8"))

        run("valid_persisted_allowed", allowed)

        def corrupt() -> None:
            write(b"{not-json")

        run("corrupt", corrupt)

        def future() -> None:
            write(b'{"schema_version": 2, "secret_marker": "synthetic-marker"}\n')

        run("future", future)

        def invalid() -> None:
            document = _blank_document(reason="operator_preflight_blocked")
            document["strategies"]["scalp"]["active"] = "false"
            write(json.dumps(document).encode("utf-8"))

        run("invalid", invalid)
        run("missing", lambda: None)

        def unreadable() -> None:
            write(b'{"schema_version": 1}\n')

            def denied(_path: Path) -> str:
                raise OSError("synthetic unreadable")

            live_safety._read_text = denied  # type: ignore[assignment]

        run("unreadable", unreadable)
        live_safety._read_text = original_read  # type: ignore[assignment]

        def permission() -> None:
            write(b'{"schema_version": 4}\n')

            def denied(_path: Path) -> str:
                raise PermissionError("synthetic denial")

            live_safety._read_text = denied  # type: ignore[assignment]

        run("permission", permission)
        live_safety._read_text = original_read  # type: ignore[assignment]

        _reset_counters()
        reset_live_safety_for_tests()
        document = _blank_document(reason="operator_preflight_blocked")
        before = json.dumps(document).encode("utf-8")
        write(before)
        real_replace = os.replace

        def boom(_src: object, _dst: object) -> None:
            raise OSError("synthetic replace failure")

        os.replace = boom  # type: ignore[assignment]
        try:
            outcome = asyncio.run(_invoke(appmod))
        finally:
            os.replace = real_replace  # type: ignore[assignment]
        snap = _snapshot()
        snap.update(outcome)
        snap["bytes_unchanged"] = safety.read_bytes() == before
        cases["replace_fail"] = snap
        if NETWORK or FS_DENIALS:
            raise RuntimeError("isolation guard tripped")

        future_bytes = b'{"schema_version": 9}\n'
        run("repeat_first", lambda: write(future_bytes))
        _reset_counters()
        before_flag = live_safety.live_safety_initialised()
        outcome = asyncio.run(_invoke(appmod))
        snap = _snapshot()
        snap.update(outcome)
        snap["bytes_unchanged"] = safety.read_bytes() == future_bytes
        snap["initialised_before"] = before_flag
        cases["repeat_second"] = snap

        run("stale_success", valid)
        _reset_counters()
        before_flag = live_safety.live_safety_initialised()
        corrupt_after = b"{not-json-after-success"
        write(corrupt_after)
        outcome = asyncio.run(_invoke(appmod))
        snap = _snapshot()
        snap.update(outcome)
        snap["bytes_unchanged"] = safety.read_bytes() == corrupt_after
        snap["initialised_before"] = before_flag
        cases["stale_then_corrupt"] = snap
        if NETWORK or FS_DENIALS:
            raise RuntimeError("isolation guard tripped")

        report["cases"] = cases
        report["isolation_ok"] = True
        code = 0
    except Exception as exc:  # noqa: BLE001
        report["isolation_ok"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        report["network"] = list(NETWORK)
        report["fs_denials"] = list(FS_DENIALS)
        code = 1
    report["self_pipe_count"] = len(SELF_PIPE)
    out_path.write_text(json.dumps(report), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
