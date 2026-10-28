"""D.6 fault-injection runner. Not collected as a test module.

Guards are installed before forex_bot.app is imported.
The D.5 runner is not modified or imported.
"""

from __future__ import annotations

import asyncio
import builtins
import json
import os
import shutil
import socket
import sys
import traceback
import types
import urllib.request
from pathlib import Path
from current_lifecycle_fixtures import wire_current_startup
from current_lifecycle_fixtures import schema_ready_cursor

INJECT = ""
COUNTS: dict[str, int] = {}
EVENTS: list[str] = []
NETWORK: list[str] = []
FS_DENIALS: list[str] = []
SELF_PIPE: list[str] = []
CONNECTIONS: list[FakeConnection] = []
TASKS: list[asyncio.Task[object]] = []
DOTENV_CALLS = 0
_REAL_OPEN = builtins.open
_REAL_OS_OPEN = os.open
_REAL_REPLACE = os.replace
_REAL_RENAME = os.rename
_REAL_REMOVE = os.remove
_REAL_UNLINK = os.unlink
_REAL_MOVE = shutil.move
_REAL_COPY2 = shutil.copy2
_REAL_RMTREE = shutil.rmtree
_ORIG_CONNECT = socket.socket.connect
_ORIG_GETADDRINFO = socket.getaddrinfo


@schema_ready_cursor
class FakeCursor:
    def __init__(self) -> None:
        self.closed = False
        self.executes = 0

    def execute(self, _sql: object, _params: object = None) -> None:
        self.executes += 1
        if INJECT == "db_execute":
            raise RuntimeError("injected database execute failure")

    def close(self) -> None:
        if INJECT == "db_cursor_close":
            raise RuntimeError("injected cursor close failure")
        self.closed = True

    def fetchall(self) -> list[object]:
        return []

    def fetchone(self) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False
        self.close_calls = 0
        self.commits = 0
        self.rollbacks = 0
        self.cursor_obj: FakeCursor | None = None

    def cursor(self) -> FakeCursor:
        if INJECT == "db_cursor":
            raise RuntimeError("injected database cursor failure")
        self.cursor_obj = FakeCursor()
        return self.cursor_obj

    def commit(self) -> None:
        if INJECT == "db_commit":
            raise RuntimeError("injected database commit failure")
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.close_calls += 1
        if INJECT == "db_conn_close":
            raise RuntimeError("injected connection close failure")
        self.closed = True


def _bump(name: str) -> None:
    COUNTS[name] = COUNTS.get(name, 0) + 1
    EVENTS.append(name)


def _deny_network(kind: str, address: object = None) -> None:
    NETWORK.append(f"{kind} {address!r}")
    raise RuntimeError(f"d6 network denied {kind} {address!r}")


def _blocked_path(file: object) -> bool:
    text = os.fspath(file)  # type: ignore[arg-type]
    folded = str(text).replace("\\", "/").lower()
    base = os.path.basename(str(text)).lower()
    return (
        base == ".env"
        or base.endswith(".env")
        or "data/ops" in folded
        or "v2_shadow" in folded
        or "credential" in base
    )


def _deny_path(file: object) -> None:
    FS_DENIALS.append(os.path.basename(str(file)).lower())
    raise PermissionError("d6 path denied")


def _install_network_guard() -> None:
    def blocked_connect(self: object, address: object) -> None:
        _ = self
        _deny_network("socket.connect", address)

    def blocked_connect_ex(self: object, address: object) -> int:
        _ = self
        _deny_network("socket.connect_ex", address)
        return 1

    def blocked_create(*_a: object, **_k: object) -> None:
        _deny_network("socket.create_connection", _a[0] if _a else None)

    def blocked_urlopen(*_a: object, **_k: object) -> None:
        _deny_network("urllib.request.urlopen", _a[0] if _a else None)

    async def blocked_open_connection(*_a: object, **_k: object) -> None:
        _deny_network("asyncio.open_connection", _a[0] if _a else None)

    def blocked_getaddrinfo(host: object, *_a: object, **_k: object) -> list[object]:
        _deny_network("socket.getaddrinfo", host)
        return []

    def loopback_socketpair(
        family: int = socket.AF_INET,
        sock_type: int = socket.SOCK_STREAM,
        proto: int = 0,
    ) -> tuple[socket.socket, socket.socket]:
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
    socket.getaddrinfo = blocked_getaddrinfo  # type: ignore[assignment]
    urllib.request.urlopen = blocked_urlopen  # type: ignore[assignment]
    asyncio.open_connection = blocked_open_connection  # type: ignore[assignment]


def _install_fs_guard() -> None:
    def guarded_open(file: object, *args: object, **kwargs: object) -> object:
        if _blocked_path(file):
            _deny_path(file)
        return _REAL_OPEN(file, *args, **kwargs)

    def guarded_os_open(path: object, flags: int, mode: int = 0o777, **kwargs: object) -> int:
        if _blocked_path(path):
            _deny_path(path)
        return _REAL_OS_OPEN(path, flags, mode, **kwargs)  # type: ignore[arg-type]

    def guarded_replace(src: object, dst: object) -> None:
        if _blocked_path(src) or _blocked_path(dst):
            _deny_path(dst)
        _REAL_REPLACE(src, dst)  # type: ignore[arg-type]

    def guarded_rename(src: object, dst: object) -> None:
        if _blocked_path(src) or _blocked_path(dst):
            _deny_path(dst)
        _REAL_RENAME(src, dst)  # type: ignore[arg-type]

    def guarded_remove(path: object) -> None:
        if _blocked_path(path):
            _deny_path(path)
        _REAL_REMOVE(path)  # type: ignore[arg-type]

    def guarded_unlink(path: object) -> None:
        if _blocked_path(path):
            _deny_path(path)
        _REAL_UNLINK(path)  # type: ignore[arg-type]

    def guarded_move(src: object, dst: object, **kwargs: object) -> object:
        if _blocked_path(src) or _blocked_path(dst):
            _deny_path(dst)
        return _REAL_MOVE(src, dst, **kwargs)  # type: ignore[arg-type]

    def guarded_copy2(src: object, dst: object, **kwargs: object) -> object:
        if _blocked_path(src) or _blocked_path(dst):
            _deny_path(dst)
        return _REAL_COPY2(src, dst, **kwargs)  # type: ignore[arg-type]

    def guarded_rmtree(path: object, **kwargs: object) -> None:
        if _blocked_path(path):
            _deny_path(path)
        _REAL_RMTREE(path, **kwargs)  # type: ignore[arg-type]

    builtins.open = guarded_open  # type: ignore[assignment]
    os.open = guarded_os_open  # type: ignore[assignment]
    os.replace = guarded_replace  # type: ignore[assignment]
    os.rename = guarded_rename  # type: ignore[assignment]
    os.remove = guarded_remove  # type: ignore[assignment]
    os.unlink = guarded_unlink  # type: ignore[assignment]
    shutil.move = guarded_move  # type: ignore[assignment]
    shutil.copy2 = guarded_copy2  # type: ignore[assignment]
    shutil.rmtree = guarded_rmtree  # type: ignore[assignment]


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
        raise RuntimeError("d6 http denied")

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

    def connect(*_a: object, **_k: object) -> FakeConnection:
        _bump("psycopg2.connect")
        if INJECT == "db_connect":
            raise RuntimeError("injected database connect failure")
        conn = FakeConnection()
        CONNECTIONS.append(conn)
        return conn

    psy.connect = connect  # type: ignore[attr-defined]
    extras = types.ModuleType("psycopg2.extras")
    extras.Json = lambda value: value  # type: ignore[attr-defined]
    extensions = types.ModuleType("psycopg2.extensions")
    extensions.connection = FakeConnection  # type: ignore[attr-defined]
    extensions.cursor = FakeCursor  # type: ignore[attr-defined]
    psy.extras = extras  # type: ignore[attr-defined]
    psy.extensions = extensions  # type: ignore[attr-defined]
    sys.modules["psycopg2"] = psy
    sys.modules["psycopg2.extras"] = extras
    sys.modules["psycopg2.extensions"] = extensions


def _fake_async(name: str):
    async def _inner() -> None:
        _bump(name)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            if name == "health_snapshot_loop" and INJECT == "await_health":
                raise RuntimeError("injected task await failure")
            raise

    _inner.__name__ = name
    return _inner


def _install_call_fakes(appmod: types.ModuleType) -> None:
    def record(name: str):
        def _call(*_a: object, **_k: object) -> dict[str, str]:
            _bump(name)
            if name == "build_api" and INJECT == "broker":
                raise RuntimeError("injected broker construction failure")
            if name == "fetch_account_summary" and INJECT == "account":
                raise RuntimeError("injected account summary failure")
            if name == "run_reconciliation_once" and INJECT == "reconcile":
                raise RuntimeError("injected reconciliation failure")
            if name == "alert" and INJECT == "before_tasks":
                raise RuntimeError("injected failure before task creation")
            return {"client": "fake"}

        return _call

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
    wire_current_startup(appmod)

    orders = __import__("importlib").import_module("forex_bot.orders")
    orders.load_open_orders_from_db_into_memory = record("load_open_orders")  # type: ignore[attr-defined]

    reconciliation = types.ModuleType("forex_bot.reconciliation")
    reconciliation.load_reconcile_state_from_db = record("load_reconcile_state")  # type: ignore[attr-defined]
    reconciliation.run_reconciliation_once = record("run_reconciliation_once")  # type: ignore[attr-defined]
    sys.modules["forex_bot.reconciliation"] = reconciliation

    telegram = types.ModuleType("forex_bot.telegram_control")

    def start_telegram() -> None:
        _bump("start_telegram_control")
        if INJECT == "before_yield":
            raise RuntimeError("injected failure before yield")

    def stop_telegram() -> None:
        _bump("stop_telegram_control")
        if INJECT == "shutdown_stop":
            raise RuntimeError("injected shutdown failure")

    telegram.start_telegram_control = start_telegram  # type: ignore[attr-defined]
    telegram.stop_telegram_control = stop_telegram  # type: ignore[attr-defined]
    sys.modules["forex_bot.telegram_control"] = telegram

    real_create = asyncio.create_task

    def counting_create(coro, *args, **kwargs):  # type: ignore[no-untyped-def]
        created = COUNTS.get("create_task", 0)
        code = getattr(getattr(coro, "cr_code", None), "co_name", "")
        fail_at = {"after_first": 1, "later_task": 3}.get(INJECT)
        if fail_at is not None and created == fail_at:
            coro.close()
            raise RuntimeError(f"injected failure creating task {created + 1}")
        _bump("create_task")
        EVENTS.append("scheduled:" + code)
        task = real_create(coro, *args, **kwargs)
        TASKS.append(task)
        return task

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
            raise RuntimeError("d6 order routing denied")

        setattr(ox, name, _wrapped)


def _guard_self_check(work: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    probe = socket.socket()
    try:
        probe.connect(("127.0.0.1", 5432))
        checks["localhost_connect_denied"] = False
    except RuntimeError:
        checks["localhost_connect_denied"] = True
    finally:
        probe.close()
    probe = socket.socket()
    try:
        probe.connect(("203.0.113.1", 9))
        checks["external_connect_denied"] = False
    except RuntimeError:
        checks["external_connect_denied"] = True
    finally:
        probe.close()
    try:
        socket.getaddrinfo("api-fxpractice.oanda.com", 443)
        checks["dns_denied"] = False
    except RuntimeError:
        checks["dns_denied"] = True
    left, right = socket.socketpair()
    port = int(SELF_PIPE[-1].rsplit(":", 1)[1])
    probe = socket.socket()
    try:
        probe.connect(("127.0.0.1", port))
        checks["self_pipe_port_not_reusable"] = False
    except RuntimeError:
        checks["self_pipe_port_not_reusable"] = True
    finally:
        probe.close()
        left.close()
        right.close()
    ops = work / "data" / "ops" / "live_safety_state.json"
    try:
        with builtins.open(ops, "r", encoding="utf-8"):
            checks["open_ops_denied"] = False
    except PermissionError:
        checks["open_ops_denied"] = True
    env_probe = work / ".env"
    try:
        with builtins.open(env_probe, "r", encoding="utf-8"):
            checks["open_env_denied"] = False
    except PermissionError:
        checks["open_env_denied"] = True
    src = work / "a.txt"
    src.write_text("synthetic", encoding="utf-8")
    try:
        os.replace(src, ops)
        checks["replace_ops_denied"] = False
    except PermissionError:
        checks["replace_ops_denied"] = True
    checks["probe_denials_only"] = bool(NETWORK) and all(
        item.startswith(("socket.", "urllib.", "asyncio.")) for item in NETWORK
    )
    NETWORK.clear()
    FS_DENIALS.clear()
    return checks


def _file_auth(path: Path) -> str:
    if not path.exists():
        return ""
    blob = json.loads(path.read_text(encoding="utf-8"))
    auth = blob.get("live_order_authorisation") or {}
    state = auth.get("state")
    return str(state) if isinstance(state, str) else ""


def _connection_rows() -> list[dict[str, object]]:
    rows = []
    for conn in CONNECTIONS:
        cursor = conn.cursor_obj
        rows.append(
            {
                "closed": conn.closed,
                "close_calls": conn.close_calls,
                "commits": conn.commits,
                "rollbacks": conn.rollbacks,
                "cursor_created": cursor is not None,
                "cursor_closed": bool(cursor and cursor.closed),
            }
        )
    return rows


def _reset_case_state() -> None:
    COUNTS.clear()
    EVENTS.clear()
    CONNECTIONS.clear()
    TASKS.clear()


async def _run_case(
    appmod: types.ModuleType,
    database: types.ModuleType,
    label: str,
    inject: str,
    *,
    rewrite: bool,
    reset_flags: bool,
) -> dict[str, object]:
    global INJECT
    INJECT = inject
    _reset_case_state()
    from forex_bot.live_safety import _blank_document, reset_live_safety_for_tests

    safety = Path(os.environ["LIVE_SAFETY_STATE_PATH"])
    if reset_flags:
        reset_live_safety_for_tests()
    database._pg_conn = None  # type: ignore[attr-defined]
    database._pg_cursor = None  # type: ignore[attr-defined]
    if rewrite:
        if safety.exists():
            safety.unlink()
        safety.write_text(
            json.dumps(_blank_document(reason="operator_preflight_blocked")),
            encoding="utf-8",
        )
    yielded = False
    escaped = ""
    message = ""
    asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
    try:
        async with appmod.lifespan(appmod.app):
            yielded = True
            _bump("yielded")
    except Exception as exc:  # noqa: BLE001
        escaped = type(exc).__name__
        message = str(exc)
    from forex_bot.live_safety import live_order_auth_state
    from forex_bot.strategy_meta import strategies

    pending = [task for task in TASKS if not task.done()]
    observation = {
        "label": label,
        "inject": inject,
        "yielded": yielded,
        "escaped_type": escaped,
        "message": message,
        "auth": live_order_auth_state(),
        "active": sorted(name for name, strat in strategies.items() if strat.active is True),
        "file_auth": _file_auth(safety),
        "counts": dict(COUNTS),
        "events": list(EVENTS),
        "connections": _connection_rows(),
        "pg_conn_held": database._pg_conn is not None and not database._pg_conn.closed,  # type: ignore[attr-defined]
        "tasks_created": len(TASKS),
        "tasks_pending_after_application": len(pending),
        "tasks_cancelled_by_application": sum(1 for task in TASKS if task.cancelled()),
        "scheduled": [item for item in EVENTS if str(item).startswith("scheduled:")],
        "network": list(NETWORK),
        "fs_denials": list(FS_DENIALS),
    }
    harness_cancelled = 0
    for task in pending:
        task.cancel()
        harness_cancelled += 1
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    harness_closed = 0
    for conn in CONNECTIONS:
        if not conn.closed:
            try:
                conn.close()
            except RuntimeError:
                conn.closed = True
            harness_closed += 1
    database._pg_conn = None  # type: ignore[attr-defined]
    database._pg_cursor = None  # type: ignore[attr-defined]
    observation["harness_cancelled"] = harness_cancelled
    observation["harness_closed_connections"] = harness_closed
    observation["application_closed_connections"] = sum(
        1 for row in observation["connections"] if row["close_calls"]  # type: ignore[index]
    )
    if NETWORK or any(not item.startswith("d6 path denied") for item in []):
        pass
    if NETWORK:
        raise RuntimeError("isolation guard tripped")
    return observation


def _prepare(*, call_fakes: bool) -> tuple[types.ModuleType, types.ModuleType, dict[str, object]]:
    report: dict[str, object] = {"foreign_project_on_path": _confine_import_path()}
    _install_network_guard()
    _install_fs_guard()
    _install_import_fakes()
    work = Path(os.environ["D6_WORK_DIR"])
    report["guard_checks"] = _guard_self_check(work)
    import forex_bot.app as appmod
    from forex_bot import database

    if call_fakes:
        _install_call_fakes(appmod)
    report["dotenv_calls_at_import"] = DOTENV_CALLS
    report["get_connection_is_real"] = appmod.get_connection.__module__ == "forex_bot.database"
    return appmod, database, report


async def _all_cases(appmod: types.ModuleType, database: types.ModuleType) -> dict[str, dict[str, object]]:
    sequence = [
        ("baseline", "", True, True),
        ("db_connect", "db_connect", True, True),
        ("db_cursor", "db_cursor", True, True),
        ("db_execute", "db_execute", True, True),
        ("db_commit", "db_commit", True, True),
        ("broker", "broker", True, True),
        ("account", "account", True, True),
        ("reconcile", "reconcile", True, True),
        ("before_tasks", "before_tasks", True, True),
        ("after_first", "after_first", True, True),
        ("later_task", "later_task", True, True),
        ("before_yield", "before_yield", True, True),
        ("shutdown_stop", "shutdown_stop", True, True),
        ("await_health", "await_health", True, True),
        ("repeat_first", "after_first", True, True),
        ("repeat_second", "", False, False),
    ]
    cases: dict[str, dict[str, object]] = {}
    for label, inject, rewrite, reset_flags in sequence:
        cases[label] = await _run_case(
            appmod,
            database,
            label,
            inject,
            rewrite=rewrite,
            reset_flags=reset_flags,
        )
    return cases


def main() -> int:
    out_path = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "lifespan"
    report: dict[str, object] = {}
    code = 0
    try:
        if mode == "repair":
            _appmod, _database, report = _prepare(call_fakes=False)
            import pytest

            repair = Path(__file__).resolve().parent / "test_live_safety_repair.py"
            code = int(pytest.main([str(repair), "-q", "--tb=line"]))
            report["repair_exit_code"] = code
            report["network"] = list(NETWORK)
            report["fs_denials"] = list(FS_DENIALS)
            if NETWORK:
                code = 1
        else:
            appmod, database, report = _prepare(call_fakes=True)
            report["cases"] = asyncio.run(_all_cases(appmod, database))
            report["network"] = list(NETWORK)
            report["fs_denials"] = list(FS_DENIALS)
            report["self_pipe_count"] = len(SELF_PIPE)
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        report["network"] = list(NETWORK)
        report["fs_denials"] = list(FS_DENIALS)
        code = 1
    out_path.write_text(json.dumps(report), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
