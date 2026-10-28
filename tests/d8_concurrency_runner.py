"""D.8 concurrency runner. Not collected as a test module.

Guards are installed before forex_bot.database or forex_bot.app is imported.
D.5, D.6, and D.7 runners are not imported or modified.
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import json
import os
import shutil
import socket
import sys
import threading
import traceback
import types
import urllib.request
from pathlib import Path
import d9_database_concurrency_runner as current_database_scenarios
from current_lifecycle_fixtures import wire_current_startup
from current_lifecycle_fixtures import schema_ready_cursor

PHASE = ""
NEXT_ID = 0
COUNTS: dict[str, int] = {}
NETWORK: list[str] = []
FS_DENIALS: list[str] = []
SELF_PIPE: list[str] = []
CONNECTIONS: list[FakeConnection] = []
DOTENV_CALLS = 0
BARRIER: threading.Barrier | None = None
RELEASE_ENTERED = threading.Event()
RELEASE_PROCEED = threading.Event()
INIT_ENTERED = threading.Event()
INIT_PROCEED = threading.Event()
_REAL_OPEN = builtins.open
_REAL_OS_OPEN = os.open
_REAL_REPLACE = os.replace
_ORIG_CONNECT = socket.socket.connect


@schema_ready_cursor
class FakeCursor:
    def __init__(self, connection_id: int, owner_thread: int) -> None:
        self.connection_id = connection_id
        self.owner_thread = owner_thread
        self.closed = False
        self.executes = 0

    def execute(self, _sql: object, _params: object = None) -> None:
        self.executes += 1
        if PHASE in {"both_fail", "cleanup_fails"}:
            raise RuntimeError("injected execute failure")
        if PHASE == "second_fails" and self.owner_thread == _second_thread():
            raise RuntimeError("injected second execute failure")
        if PHASE == "first_fails" and self.owner_thread == _first_thread():
            raise RuntimeError("injected first execute failure")

    def close(self) -> None:
        self.closed = True

    def fetchall(self) -> list[object]:
        return []

    def fetchone(self) -> None:
        return None


class FakeConnection:
    def __init__(self, owner_thread: int) -> None:
        global NEXT_ID
        NEXT_ID += 1
        self.owner_thread = owner_thread
        self.ident = NEXT_ID
        self.closed = False
        self.close_calls = 0
        self.commits = 0
        self.rollbacks = 0
        self.cursor_obj: FakeCursor | None = None

    def cursor(self) -> FakeCursor:
        self.cursor_obj = FakeCursor(self.ident, self.owner_thread)
        return self.cursor_obj

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.close_calls += 1
        if PHASE == "replace_during_close" and not RELEASE_ENTERED.is_set():
            RELEASE_ENTERED.set()
            if not RELEASE_PROCEED.wait(timeout=3):
                raise TimeoutError("release close wait expired")
        if (
            PHASE in {"close_fails", "cleanup_fails"}
            and self.owner_thread == _first_thread()
        ):
            raise RuntimeError("injected connection close failure")
        self.closed = True


def _threads() -> list[int]:
    return [conn.owner_thread for conn in CONNECTIONS]


def _first_thread() -> int:
    rows = _threads()
    return rows[0] if rows else -1


def _second_thread() -> int:
    rows = _threads()
    return rows[1] if len(rows) > 1 else -2


def _bump(name: str) -> None:
    COUNTS[name] = COUNTS.get(name, 0) + 1


def _deny_network(kind: str, address: object = None) -> None:
    NETWORK.append(f"{kind} {address!r}")
    raise RuntimeError(f"d8 network denied {kind} {address!r}")


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


def _install_guards() -> None:
    def blocked_connect(self: object, address: object) -> None:
        _ = self
        _deny_network("socket.connect", address)

    def blocked_getaddrinfo(host: object, *_a: object, **_k: object) -> list[object]:
        _deny_network("socket.getaddrinfo", host)
        return []

    def loopback_socketpair(
        family: int = socket.AF_INET,
        sock_type: int = socket.SOCK_STREAM,
        proto: int = 0,
    ) -> tuple[socket.socket, socket.socket]:
        host = "127.0.0.1" if family == socket.AF_INET else "::1"
        if family not in (socket.AF_INET, socket.AF_INET6):
            _deny_network("socket.socketpair", family)
        listener = socket.socket(family, sock_type, proto)
        try:
            listener.bind((host, 0))
            listener.listen()
            addr, port = listener.getsockname()[:2]
            SELF_PIPE.append(f"{addr}:{port}")
            client = socket.socket(family, sock_type, proto)
            try:
                client.setblocking(False)
                with contextlib.suppress(BlockingIOError, InterruptedError):
                    _ORIG_CONNECT(client, (addr, port))
                client.setblocking(True)
                server, _peer = listener.accept()
            except OSError:
                client.close()
                raise
        finally:
            listener.close()
        return server, client

    def guarded_open(file: object, *args: object, **kwargs: object) -> object:
        if _blocked_path(file):
            FS_DENIALS.append(os.path.basename(str(file)).lower())
            raise PermissionError("d8 path denied")
        return _REAL_OPEN(file, *args, **kwargs)

    def guarded_os_open(
        path: object, flags: int, mode: int = 0o777, **kwargs: object
    ) -> int:
        if _blocked_path(path):
            FS_DENIALS.append("os.open")
            raise PermissionError("d8 path denied")
        return _REAL_OS_OPEN(path, flags, mode, **kwargs)  # type: ignore[arg-type]

    def guarded_replace(src: object, dst: object) -> None:
        if _blocked_path(src) or _blocked_path(dst):
            FS_DENIALS.append("os.replace")
            raise PermissionError("d8 path denied")
        _REAL_REPLACE(src, dst)  # type: ignore[arg-type]

    socket.socket.connect = blocked_connect  # type: ignore[method-assign]
    socket.getaddrinfo = blocked_getaddrinfo  # type: ignore[assignment]
    socket.socketpair = loopback_socketpair  # type: ignore[assignment]
    urllib.request.urlopen = lambda *_a, **_k: _deny_network("urllib.request.urlopen")  # type: ignore[assignment]
    builtins.open = guarded_open  # type: ignore[assignment]
    os.open = guarded_os_open  # type: ignore[assignment]
    os.replace = guarded_replace  # type: ignore[assignment]
    shutil.move = guarded_replace  # type: ignore[assignment]

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
        raise RuntimeError("d8 http denied")

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
        if PHASE == "connect_fails":
            raise RuntimeError("injected connect failure")
        owner = threading.get_ident()
        conn = FakeConnection(owner)
        CONNECTIONS.append(conn)
        if PHASE == "release_during_init":
            INIT_ENTERED.set()
            if not INIT_PROCEED.wait(timeout=3):
                raise TimeoutError("initializer was not released")
        elif (
            PHASE
            in {"overlap", "second_fails", "first_fails", "both_fail", "cleanup_fails"}
            and BARRIER is not None
        ):
            BARRIER.wait(timeout=3)
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


def _confine() -> bool:
    banned = "concensus-forecast"
    sys.path[:] = [
        item for item in sys.path if banned not in str(item).replace("\\", "/").lower()
    ]
    repo = str(Path(__file__).resolve().parents[1])
    if repo not in sys.path:
        sys.path.insert(0, repo)
    return any(banned in str(item).replace("\\", "/").lower() for item in sys.path)


def _guard_self_check(work: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    probe = socket.socket()
    try:
        probe.connect(("127.0.0.1", 5432))
        checks["localhost_denied"] = False
    except RuntimeError:
        checks["localhost_denied"] = True
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
        checks["self_pipe_not_reusable"] = False
    except RuntimeError:
        checks["self_pipe_not_reusable"] = True
    finally:
        probe.close()
        left.close()
        right.close()
    ops = work / "data" / "ops" / "live_safety_state.json"
    try:
        with builtins.open(ops, "r", encoding="utf-8"):
            checks["ops_denied"] = False
    except PermissionError:
        checks["ops_denied"] = True
    try:
        os.replace(work / "a.txt", ops)
        checks["replace_denied"] = False
    except PermissionError:
        checks["replace_denied"] = True
    NETWORK.clear()
    FS_DENIALS.clear()
    return checks


def _reset(database: types.ModuleType) -> None:
    global BARRIER
    CONNECTIONS.clear()
    COUNTS.clear()
    BARRIER = None
    RELEASE_ENTERED.clear()
    RELEASE_PROCEED.clear()
    INIT_ENTERED.clear()
    INIT_PROCEED.clear()
    database._pg_conn = None  # type: ignore[attr-defined]
    database._pg_cursor = None  # type: ignore[attr-defined]
    database._partial_cleanup_notes.clear()  # type: ignore[attr-defined]


def _rows() -> list[dict[str, object]]:
    rows = []
    for conn in CONNECTIONS:
        cursor = conn.cursor_obj
        rows.append(
            {
                "ident": conn.ident,
                "closed": conn.closed,
                "close_calls": conn.close_calls,
                "commits": conn.commits,
                "rollbacks": conn.rollbacks,
                "cursor_connection": None if cursor is None else cursor.connection_id,
                "cursor_closed": bool(cursor and cursor.closed),
            }
        )
    return rows


def _snapshot(
    database: types.ModuleType, workers: list[dict[str, object]]
) -> dict[str, object]:
    published = database._pg_conn  # type: ignore[attr-defined]
    cursor = database._pg_cursor  # type: ignore[attr-defined]
    published_id = None if published is None else published.ident
    cursor_connection = None if cursor is None else cursor.connection_id
    abandoned = [
        row
        for row in _rows()
        if row["ident"] != published_id and row["close_calls"] == 0
    ]
    return {
        "workers": workers,
        "worker_errors": [row for row in workers if row.get("error")],
        "alive_workers": sum(1 for row in workers if row.get("alive")),
        "connections": _rows(),
        "connect_calls": COUNTS.get("psycopg2.connect", 0),
        "published_id": published_id,
        "cursor_connection": cursor_connection,
        "pair_consistent": published_id is not None
        and published_id == cursor_connection,
        "published_open": bool(published is not None and not published.closed),
        "abandoned_open": len(abandoned),
        "application_closed": sum(1 for row in _rows() if row["close_calls"]),
        "partial_notes": list(database.partial_initialization_cleanup_errors()),
        "requests": COUNTS.get("requests", 0),
    }


def _join(threads: list[threading.Thread]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for thread in threads:
        thread.join(timeout=5)
        box = getattr(thread, "box")
        rows.append(
            {
                "name": thread.name,
                "alive": thread.is_alive(),
                "error": box.get("error", ""),
                "returned_id": box.get("returned_id"),
            }
        )
    return rows


def _start(target, name: str) -> threading.Thread:  # type: ignore[no-untyped-def]
    box: dict[str, object] = {}

    def run() -> None:
        try:
            box["returned_id"] = target()
        except Exception as exc:  # noqa: BLE001
            box["error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=run, name=name)
    thread.box = box  # type: ignore[attr-defined]
    thread.start()
    return thread


def _call_get(database: types.ModuleType, *, hold_lock: bool) -> int | None:
    if hold_lock:
        with database._pg_lock:  # type: ignore[attr-defined]
            conn = database.get_connection()
    else:
        conn = database.get_connection()
    return None if conn is None else conn.ident  # type: ignore[attr-defined]


def _schedule_overlap(
    database: types.ModuleType, *, second_holds_lock: bool
) -> dict[str, object]:
    global PHASE, BARRIER
    _reset(database)
    PHASE = "overlap"
    BARRIER = threading.Barrier(2)
    threads = [
        _start(lambda: _call_get(database, hold_lock=False), "unlocked-a"),
        _start(lambda: _call_get(database, hold_lock=second_holds_lock), "caller-b"),
    ]
    workers = _join(threads)
    snap = _snapshot(database, workers)
    return _finish(database, snap)


def _schedule_locked(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = "locked"
    threads = [
        _start(lambda: _call_get(database, hold_lock=True), "locked-a"),
        _start(lambda: _call_get(database, hold_lock=True), "locked-b"),
    ]
    return _finish(database, _snapshot(database, _join(threads)))


def _schedule_mixed_failure(
    database: types.ModuleType, phase: str
) -> dict[str, object]:
    global PHASE, BARRIER
    _reset(database)
    PHASE = phase
    BARRIER = threading.Barrier(2)
    threads = [
        _start(lambda: _call_get(database, hold_lock=False), "a"),
        _start(lambda: _call_get(database, hold_lock=False), "b"),
    ]
    return _finish(database, _snapshot(database, _join(threads)))


def _schedule_release_during_init(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = "release_during_init"
    thread = _start(lambda: _call_get(database, hold_lock=False), "initializer")
    if not INIT_ENTERED.wait(timeout=3):
        INIT_PROCEED.set()
        _join([thread])
        raise TimeoutError("initializer did not reach connect")
    notes = database.release_connection_after_failed_startup()
    INIT_PROCEED.set()
    snap = _snapshot(database, _join([thread]))
    snap["release_notes_before_publish"] = list(notes)
    return _finish(database, snap)


def _schedule_release_borrowed(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = ""
    borrowed = database.get_connection()
    notes = database.release_connection_after_failed_startup()
    again = database.release_connection_after_failed_startup()
    connects = COUNTS.get("psycopg2.connect", 0)
    snap = _snapshot(database, [])
    snap["borrowed_closed"] = bool(borrowed is not None and borrowed.closed)  # type: ignore[attr-defined]
    snap["borrowed_close_calls"] = None if borrowed is None else borrowed.close_calls  # type: ignore[attr-defined]
    snap["release_notes"] = list(notes)
    snap["second_release_notes"] = list(again)
    snap["connects_after_release"] = COUNTS.get("psycopg2.connect", 0)
    snap["release_created_connection"] = COUNTS.get("psycopg2.connect", 0) != connects
    return _finish(database, snap)


def _schedule_replace(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = "replace_during_close"
    first = database.get_connection()

    def do_release() -> int:
        return len(database.release_connection_after_failed_startup())

    thread = _start(do_release, "releaser")
    if not RELEASE_ENTERED.wait(timeout=3):
        RELEASE_PROCEED.set()
        _join([thread])
        raise TimeoutError("release did not reach close")
    PHASE = ""
    second = database.get_connection()
    RELEASE_PROCEED.set()
    workers = _join([thread])
    snap = _snapshot(database, workers)
    snap["old_id"] = None if first is None else first.ident  # type: ignore[attr-defined]
    snap["new_id"] = None if second is None else second.ident  # type: ignore[attr-defined]
    snap["old_closed"] = bool(first is not None and first.closed)  # type: ignore[attr-defined]
    snap["new_open"] = bool(second is not None and not second.closed)  # type: ignore[attr-defined]
    return _finish(database, snap)


def _schedule_retry(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = "connect_fails"
    first = database.get_connection()
    PHASE = ""
    second = database.get_connection()
    snap = _snapshot(database, [])
    snap["first_none"] = first is None
    snap["second_id"] = None if second is None else second.ident  # type: ignore[attr-defined]
    snap["published_is_second"] = database._pg_conn is second  # type: ignore[attr-defined]
    return _finish(database, snap)


def _finish(database: types.ModuleType, snap: dict[str, object]) -> dict[str, object]:
    global PHASE
    PHASE = ""
    harness_closed = 0
    for conn in CONNECTIONS:
        if not conn.closed:
            conn.close()
            harness_closed += 1
    for row in snap["workers"]:  # type: ignore[index]
        if row.get("alive"):  # type: ignore[attr-defined]
            raise RuntimeError("worker still alive after join")
    database._pg_conn = None  # type: ignore[attr-defined]
    database._pg_cursor = None  # type: ignore[attr-defined]
    snap["harness_closed"] = harness_closed
    snap["network"] = list(NETWORK)
    if NETWORK:
        raise RuntimeError("isolation guard tripped")
    return snap


def _concurrency(database: types.ModuleType) -> dict[str, object]:
    # The old two-connector rendezvous required the fixed initialization race.
    # Execute its serialized/retry/release counterparts against the real current
    # get_connection, under both the D.8 and the stronger D.9 isolation barriers.
    current_database_scenarios._install_guards()
    database.psycopg2 = sys.modules["psycopg2"]
    return current_database_scenarios._concurrency(database, pre_fix=False)


def _lifespan_cases(
    appmod: types.ModuleType, database: types.ModuleType
) -> dict[str, object]:
    from forex_bot.live_safety import _blank_document, reset_live_safety_for_tests
    from forex_bot.strategy_meta import strategies

    safety = Path(os.environ["LIVE_SAFETY_STATE_PATH"])

    def fake_async(name: str):
        async def _inner() -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                if name == "health_snapshot_loop" and PHASE == "await_health":
                    raise RuntimeError("injected task await failure")
                raise

        return _inner

    def record(name: str):
        def _call(*_a: object, **_k: object) -> dict[str, str]:
            _bump(name)
            if name == "build_api" and PHASE == "broker":
                raise RuntimeError("injected broker construction failure")
            return {"client": "fake"}

        return _call

    appmod.build_api = record("build_api")  # type: ignore[attr-defined]
    appmod.fetch_account_summary = record("fetch_account_summary")  # type: ignore[attr-defined]
    appmod.alert = record("alert")  # type: ignore[attr-defined]
    appmod.load_operational_events_cache_from_db = record("events")  # type: ignore[attr-defined]
    appmod.run_bot = fake_async("run_bot")  # type: ignore[attr-defined]
    appmod.reconciliation_loop = fake_async("reconciliation_loop")  # type: ignore[attr-defined]
    appmod.health_snapshot_loop = fake_async("health_snapshot_loop")  # type: ignore[attr-defined]
    appmod.telegram_inbound_loop = fake_async("telegram_inbound_loop")  # type: ignore[attr-defined]
    wire_current_startup(appmod)
    orders = __import__("importlib").import_module("forex_bot.orders")
    orders.load_open_orders_from_db_into_memory = record("load_open_orders")  # type: ignore[attr-defined]
    reconciliation = types.ModuleType("forex_bot.reconciliation")
    reconciliation.load_reconcile_state_from_db = record("load_reconcile")  # type: ignore[attr-defined]
    reconciliation.run_reconciliation_once = record("reconcile_once")  # type: ignore[attr-defined]
    sys.modules["forex_bot.reconciliation"] = reconciliation
    telegram = types.ModuleType("forex_bot.telegram_control")

    def start_telegram() -> None:
        _bump("start_telegram")
        if PHASE in {"before_yield", "startup_stop"}:
            raise RuntimeError("injected failure before yield")

    def stop_telegram() -> None:
        _bump("stop_telegram")
        if PHASE in {"shutdown_stop", "startup_stop"}:
            raise RuntimeError("injected shutdown failure")

    telegram.start_telegram_control = start_telegram  # type: ignore[attr-defined]
    telegram.stop_telegram_control = stop_telegram  # type: ignore[attr-defined]
    sys.modules["forex_bot.telegram_control"] = telegram
    tasks: list[asyncio.Task[object]] = []
    real_create = asyncio.create_task

    def counting_create(coro, *args, **kwargs):  # type: ignore[no-untyped-def]
        _bump("create_task")
        task = real_create(coro, *args, **kwargs)
        tasks.append(task)
        return task

    asyncio.create_task = counting_create  # type: ignore[assignment]

    async def one(phase: str, rewrite: str) -> dict[str, object]:
        global PHASE
        PHASE = phase
        tasks.clear()
        CONNECTIONS.clear()
        COUNTS.clear()
        database._pg_conn = None  # type: ignore[attr-defined]
        database._pg_cursor = None  # type: ignore[attr-defined]
        reset_live_safety_for_tests()
        if safety.exists():
            safety.unlink()
        if rewrite == "corrupt":
            safety.write_text("{not-json", encoding="utf-8")
        else:
            safety.write_text(
                json.dumps(_blank_document(reason="operator_preflight_blocked")),
                encoding="utf-8",
            )
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        yielded = False
        escaped = ""
        message = ""
        try:
            async with appmod.lifespan(appmod.app):
                yielded = True
        except Exception as exc:  # noqa: BLE001
            escaped = type(exc).__name__
            message = str(exc)
        pending = [task for task in tasks if not task.done()]
        from forex_bot.live_safety import live_order_auth_state

        row = {
            "yielded": yielded,
            "escaped_type": escaped,
            "message": message,
            "auth": live_order_auth_state(),
            "active": sorted(
                name for name, item in strategies.items() if item.active is True
            ),
            "pending": len(pending),
            "created": len(tasks),
            "pg_conn_held": database._pg_conn is not None
            and not database._pg_conn.closed,  # type: ignore[attr-defined]
            "application_closed": sum(conn.close_calls for conn in CONNECTIONS),
            "cleanup_errors": list(appmod.startup_cleanup_errors()),
            "connect_calls": COUNTS.get("psycopg2.connect", 0),
            "requests": COUNTS.get("requests", 0),
        }
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        harness_closed = 0
        for conn in CONNECTIONS:
            if not conn.closed:
                conn.close()
                harness_closed += 1
        database._pg_conn = None  # type: ignore[attr-defined]
        database._pg_cursor = None  # type: ignore[attr-defined]
        row["harness_cancelled"] = len(pending)
        row["harness_closed"] = harness_closed
        return row

    async def all_cases() -> dict[str, object]:
        return {
            "corrupt": await one("", "corrupt"),
            "baseline": await one("", "valid"),
            "broker": await one("broker", "valid"),
            "shutdown_stop": await one("shutdown_stop", "valid"),
            "await_health": await one("await_health", "valid"),
            "before_yield": await one("before_yield", "valid"),
            "startup_stop": await one("startup_stop", "valid"),
            "repeat": await one("", "valid"),
        }

    return asyncio.run(all_cases())


def main() -> int:
    out = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "concurrency"
    report: dict[str, object] = {"foreign_project_on_path": _confine()}
    code = 0
    try:
        _install_guards()
        work = Path(os.environ["D8_WORK_DIR"])
        (work / "a.txt").write_text("synthetic", encoding="utf-8")
        report["guard_checks"] = _guard_self_check(work)
        if mode == "lifespan":
            import forex_bot.app as appmod
            from forex_bot import database

            report["dotenv_calls_at_import"] = DOTENV_CALLS
            report["get_connection_module"] = appmod.get_connection.__module__
            report["cases"] = _lifespan_cases(appmod, database)
        else:
            from forex_bot import database

            report["dotenv_calls_at_import"] = DOTENV_CALLS
            report["get_connection_module"] = database.get_connection.__module__
            report["schedules"] = _concurrency(database)
        report["network"] = list(NETWORK)
        report["fs_denials"] = list(FS_DENIALS)
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        report["network"] = list(NETWORK)
        code = 1
    out.write_text(json.dumps(report), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
