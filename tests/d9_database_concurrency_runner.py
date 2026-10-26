"""Isolated D.9 runner. Imports production database code only after guards."""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import traceback
import types
import urllib.request
from pathlib import Path

NETWORK: list[str] = []
FS_DENIALS: list[str] = []
SELF_PIPE: list[str] = []
CONNECTIONS: list[FakeConnection] = []
CURSORS: list[FakeCursor] = []
COUNTS: dict[str, int] = {}
PHASE = ""
NEXT_ID = 0
NEXT_CURSOR = 0
DOTENV_CALLS = 0
BARRIER: threading.Barrier | None = None
HOLD_ARMED = threading.Event()
INIT_ENTERED = threading.Event()
INIT_PROCEED = threading.Event()
RELEASE_ENTERED = threading.Event()
RELEASE_PROCEED = threading.Event()
ONCE: set[str] = set()

_REAL_OPEN = builtins.open
_REAL_OS_OPEN = os.open
_REAL_REPLACE = os.replace
_REAL_RENAME = os.rename
_REAL_REMOVE = os.remove
_REAL_UNLINK = os.unlink
_REAL_MOVE = shutil.move
_REAL_COPY = shutil.copy
_REAL_COPY2 = shutil.copy2
_REAL_RMTREE = shutil.rmtree
_REAL_PATH_OPEN = Path.open
_ORIG_CONNECT = socket.socket.connect
_REAL_SYSTEM = os.system
_REAL_POPEN = subprocess.Popen


class FakeCursor:
    def __init__(self, connection_id: int) -> None:
        global NEXT_CURSOR
        NEXT_CURSOR += 1
        self.ident = NEXT_CURSOR
        self.connection_id = connection_id
        self.closed = False
        self.close_calls = 0
        self.executes = 0
        self.rowcount = 0

    def execute(self, _sql: object, _params: object = None) -> None:
        self.executes += 1
        failing = PHASE in {
            "sql_fails",
            "sql_always",
            "rollback_fails",
            "cursor_close_fails",
            "conn_close_fails",
        }
        if failing and not (PHASE == "sql_fails" and "sql" in ONCE):
            if PHASE == "sql_fails":
                ONCE.add("sql")
            raise RuntimeError("injected sql failure")

    def fetchall(self) -> list[object]:
        return []

    def fetchone(self) -> None:
        return None

    def close(self) -> None:
        self.close_calls += 1
        if PHASE == "cursor_close_fails" and "cursor_close" not in ONCE:
            ONCE.add("cursor_close")
            raise RuntimeError("injected cursor close failure")
        self.closed = True


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
        if PHASE == "cursor_fails" and "cursor" not in ONCE:
            ONCE.add("cursor")
            raise RuntimeError("injected cursor failure")
        self.cursor_obj = FakeCursor(self.ident)
        CURSORS.append(self.cursor_obj)
        return self.cursor_obj

    def commit(self) -> None:
        self.commits += 1
        if PHASE == "commit_fails" and "commit" not in ONCE:
            ONCE.add("commit")
            raise RuntimeError("injected commit failure")

    def rollback(self) -> None:
        self.rollbacks += 1
        if PHASE == "rollback_fails" and "rollback" not in ONCE:
            ONCE.add("rollback")
            raise RuntimeError("injected rollback failure")

    def close(self) -> None:
        self.close_calls += 1
        if PHASE == "replace_during_close" and not RELEASE_ENTERED.is_set():
            RELEASE_ENTERED.set()
            if not RELEASE_PROCEED.wait(timeout=3):
                raise TimeoutError("release close wait expired")
        if PHASE == "conn_close_fails" and "conn_close" not in ONCE:
            ONCE.add("conn_close")
            raise RuntimeError("injected connection close failure")
        self.closed = True


def _bump(name: str) -> None:
    COUNTS[name] = COUNTS.get(name, 0) + 1


def _deny_network(kind: str, address: object = None) -> None:
    NETWORK.append(f"{kind} {address!r}")
    raise RuntimeError(f"d9 network denied {kind} {address!r}")


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
        or "pgdata" in folded
    )


def _deny_path(file: object) -> None:
    FS_DENIALS.append(os.path.basename(str(file)).lower())
    raise PermissionError("d9 path denied")


def _install_guards() -> None:
    global DOTENV_CALLS

    def blocked_connect(self: object, address: object) -> None:
        _ = self
        _deny_network("socket.connect", address)

    def blocked_connect_ex(self: object, address: object) -> int:
        _ = self
        _deny_network("socket.connect_ex", address)
        return 1

    def blocked_create(*_a: object, **_k: object) -> None:
        _deny_network("socket.create_connection", _a[0] if _a else None)

    def blocked_getaddrinfo(host: object, *_a: object, **_k: object) -> list[object]:
        _deny_network("socket.getaddrinfo", host)
        return []

    def blocked_gethostbyname(host: object) -> str:
        _deny_network("socket.gethostbyname", host)
        return ""

    def blocked_urlopen(*_a: object, **_k: object) -> None:
        _deny_network("urllib.request.urlopen", _a[0] if _a else None)

    def blocked_open_connection(*_a: object, **_k: object) -> None:
        _deny_network("asyncio.open_connection", _a[0] if _a else None)

    def blocked_start_server(*_a: object, **_k: object) -> None:
        _deny_network("asyncio.start_server", _a[0] if _a else None)

    def blocked_subprocess(*_a: object, **_k: object) -> None:
        _deny_network("asyncio.subprocess", _a[0] if _a else None)

    def blocked_system(*_a: object, **_k: object) -> int:
        _deny_network("os.system", _a[0] if _a else None)
        return 1

    def blocked_popen(*_a: object, **_k: object) -> None:
        _deny_network("subprocess.Popen", _a[0] if _a else None)

    def blocked_run(*_a: object, **_k: object) -> None:
        _deny_network("subprocess.run", _a[0] if _a else None)

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

    socket.socket.connect = blocked_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked_connect_ex  # type: ignore[method-assign]
    socket.create_connection = blocked_create  # type: ignore[assignment]
    socket.socketpair = loopback_socketpair  # type: ignore[assignment]
    socket.getaddrinfo = blocked_getaddrinfo  # type: ignore[assignment]
    socket.gethostbyname = blocked_gethostbyname  # type: ignore[assignment]
    urllib.request.urlopen = blocked_urlopen  # type: ignore[assignment]
    asyncio.open_connection = blocked_open_connection  # type: ignore[assignment]
    asyncio.start_server = blocked_start_server  # type: ignore[assignment]
    asyncio.create_subprocess_exec = blocked_subprocess  # type: ignore[assignment]
    asyncio.create_subprocess_shell = blocked_subprocess  # type: ignore[assignment]
    os.system = blocked_system  # type: ignore[assignment]
    subprocess.Popen = blocked_popen  # type: ignore[assignment, misc]
    subprocess.run = blocked_run  # type: ignore[assignment]

    def guarded_open(file: object, *args: object, **kwargs: object) -> object:
        if _blocked_path(file):
            _deny_path(file)
        return _REAL_OPEN(file, *args, **kwargs)

    def guarded_os_open(
        path: object, flags: int, mode: int = 0o777, **kwargs: object
    ) -> int:
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

    def guarded_copy(src: object, dst: object, **kwargs: object) -> object:
        if _blocked_path(src) or _blocked_path(dst):
            _deny_path(dst)
        return _REAL_COPY(src, dst, **kwargs)  # type: ignore[arg-type]

    def guarded_copy2(src: object, dst: object, **kwargs: object) -> object:
        if _blocked_path(src) or _blocked_path(dst):
            _deny_path(dst)
        return _REAL_COPY2(src, dst, **kwargs)  # type: ignore[arg-type]

    def guarded_rmtree(path: object, **kwargs: object) -> None:
        if _blocked_path(path):
            _deny_path(path)
        _REAL_RMTREE(path, **kwargs)  # type: ignore[arg-type]

    def guarded_path_open(self: Path, *args: object, **kwargs: object) -> object:
        if _blocked_path(self):
            _deny_path(self)
        return _REAL_PATH_OPEN(self, *args, **kwargs)

    builtins.open = guarded_open  # type: ignore[assignment]
    os.open = guarded_os_open  # type: ignore[assignment]
    os.replace = guarded_replace  # type: ignore[assignment]
    os.rename = guarded_rename  # type: ignore[assignment]
    os.remove = guarded_remove  # type: ignore[assignment]
    os.unlink = guarded_unlink  # type: ignore[assignment]
    shutil.move = guarded_move  # type: ignore[assignment]
    shutil.copy = guarded_copy  # type: ignore[assignment]
    shutil.copy2 = guarded_copy2  # type: ignore[assignment]
    shutil.rmtree = guarded_rmtree  # type: ignore[assignment]
    Path.open = guarded_path_open  # type: ignore[method-assign]

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
        raise RuntimeError("d9 http denied")

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
        if PHASE == "hold" and not HOLD_ARMED.is_set():
            HOLD_ARMED.set()
            INIT_ENTERED.set()
            if not INIT_PROCEED.wait(timeout=3):
                raise TimeoutError("held connect was not released")
        owner = threading.get_ident()
        conn = FakeConnection(owner)
        CONNECTIONS.append(conn)
        if PHASE == "pre_fix" and BARRIER is not None:
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


def _expect_deny(label: str, func: object) -> bool:
    before = len(NETWORK)
    try:
        func()  # type: ignore[operator]
    except RuntimeError:
        return len(NETWORK) > before
    return False


def _guard_self_check(work: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    sock = socket.socket()
    try:
        checks["localhost_denied"] = _expect_deny(
            "connect", lambda: sock.connect(("127.0.0.1", 5432))
        )
        checks["connect_ex_denied"] = _expect_deny(
            "connect_ex", lambda: sock.connect_ex(("127.0.0.1", 5432))
        )
    finally:
        sock.close()
    checks["create_connection_denied"] = _expect_deny(
        "create", lambda: socket.create_connection(("127.0.0.1", 5432), timeout=0.1)
    )
    checks["dns_denied"] = _expect_deny(
        "dns", lambda: socket.getaddrinfo("api-fxpractice.oanda.com", 443)
    )
    checks["gethostbyname_denied"] = _expect_deny(
        "host", lambda: socket.gethostbyname("api-fxpractice.oanda.com")
    )
    checks["urlopen_denied"] = _expect_deny(
        "url", lambda: urllib.request.urlopen("http://example.com")
    )
    checks["system_denied"] = _expect_deny("system", lambda: os.system("echo d9"))
    checks["popen_denied"] = _expect_deny(
        "popen", lambda: subprocess.Popen(["python", "-c", "print(1)"])
    )
    checks["run_denied"] = _expect_deny("run", lambda: subprocess.run(["python", "-V"]))
    checks["open_connection_denied"] = _expect_deny(
        "open_connection", lambda: asyncio.open_connection("example.com", 80)
    )
    checks["start_server_denied"] = _expect_deny(
        "start_server", lambda: asyncio.start_server(None, "127.0.0.1", 0)
    )
    checks["subprocess_exec_denied"] = _expect_deny(
        "exec", lambda: asyncio.create_subprocess_exec("python")
    )
    checks["subprocess_shell_denied"] = _expect_deny(
        "shell", lambda: asyncio.create_subprocess_shell("echo d9")
    )
    left, right = socket.socketpair()
    port = left.getsockname()[1]
    left.close()
    right.close()
    again = socket.socket()
    try:
        checks["self_pipe_not_reusable"] = _expect_deny(
            "pipe", lambda: again.connect(("127.0.0.1", port))
        )
    finally:
        again.close()
    ops = work / "data" / "ops" / "live_safety_state.json"
    shadow = work / "data" / "research" / "v2_shadow" / "state.json"
    cred = work / "credential.txt"
    env_path = work / ".env"
    volume = work / "pgdata" / "db.txt"
    for label, path in (
        ("ops_denied", ops),
        ("shadow_denied", shadow),
        ("credential_denied", cred),
        ("env_denied", env_path),
        ("volume_denied", volume),
    ):
        try:
            with open(path, "w", encoding="utf-8"):
                checks[label] = False
        except PermissionError:
            checks[label] = True
    try:
        with Path(ops).open("w", encoding="utf-8"):
            checks["path_open_denied"] = False
    except PermissionError:
        checks["path_open_denied"] = True
    NETWORK.clear()
    FS_DENIALS.clear()
    return checks


def _reset(database: types.ModuleType) -> None:
    global BARRIER, NEXT_ID, NEXT_CURSOR
    CONNECTIONS.clear()
    CURSORS.clear()
    COUNTS.clear()
    ONCE.clear()
    BARRIER = None
    HOLD_ARMED.clear()
    INIT_ENTERED.clear()
    INIT_PROCEED.clear()
    RELEASE_ENTERED.clear()
    RELEASE_PROCEED.clear()
    NEXT_ID = 0
    NEXT_CURSOR = 0
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
        "cursors_created": len(CURSORS),
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
        "returned_ids": [row.get("returned_id") for row in workers],
    }


def _start(func: object, name: str) -> threading.Thread:
    box: dict[str, object] = {"name": name, "error": "", "returned_id": None}

    def run() -> None:
        try:
            box["returned_id"] = func()  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001
            box["error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=run, name=name)
    thread.box = box  # type: ignore[attr-defined]
    thread.start()
    return thread


def _join(threads: list[threading.Thread]) -> list[dict[str, object]]:
    rows = []
    for thread in threads:
        thread.join(timeout=5)
        box = dict(thread.box)  # type: ignore[attr-defined]
        box["alive"] = thread.is_alive()
        rows.append(box)
    return rows


def _finish(database: types.ModuleType, snap: dict[str, object]) -> dict[str, object]:
    global PHASE
    PHASE = ""
    harness_closed = 0
    for conn in CONNECTIONS:
        if not conn.closed:
            conn.close()
            harness_closed += 1
    for row in snap["workers"]:  # type: ignore[index]
        if row.get("alive"):
            raise RuntimeError("worker still alive after join")
    database._pg_conn = None  # type: ignore[attr-defined]
    database._pg_cursor = None  # type: ignore[attr-defined]
    snap["harness_closed"] = harness_closed
    snap["network"] = list(NETWORK)
    if NETWORK:
        raise RuntimeError("isolation guard tripped")
    return snap


def _call_get(database: types.ModuleType, *, hold_lock: bool) -> int | None:
    if hold_lock:
        with database._pg_lock:  # type: ignore[attr-defined]
            conn = database.get_connection()
    else:
        conn = database.get_connection()
    return None if conn is None else conn.ident  # type: ignore[attr-defined]


def _schedule_pre_fix(database: types.ModuleType) -> dict[str, object]:
    global PHASE, BARRIER
    _reset(database)
    PHASE = "pre_fix"
    BARRIER = threading.Barrier(2)
    threads = [
        _start(lambda: _call_get(database, hold_lock=False), "a"),
        _start(lambda: _call_get(database, hold_lock=False), "b"),
    ]
    return _finish(database, _snapshot(database, _join(threads)))


def _schedule_serialized(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = "hold"
    first = _start(lambda: _call_get(database, hold_lock=False), "a")
    if not INIT_ENTERED.wait(timeout=3):
        INIT_PROCEED.set()
        _join([first])
        raise TimeoutError("first caller did not reach connect")
    done = threading.Event()

    def second() -> int | None:
        try:
            return _call_get(database, hold_lock=False)
        finally:
            done.set()

    other = _start(second, "b")
    blocked = not done.wait(timeout=0.3)
    held_connects = COUNTS.get("psycopg2.connect", 0)
    INIT_PROCEED.set()
    snap = _snapshot(database, _join([first, other]))
    snap["second_blocked_while_first_connected"] = blocked
    snap["connects_while_held"] = held_connects
    return _finish(database, snap)


def _schedule_failure(database: types.ModuleType, phase: str) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = phase
    first = database.get_connection()
    notes_after_first = list(database.partial_initialization_cleanup_errors())
    PHASE = ""
    ONCE.clear()
    second = database.get_connection()
    snap = _snapshot(database, [])
    snap["first_none"] = first is None
    snap["second_id"] = None if second is None else second.ident  # type: ignore[attr-defined]
    snap["published_is_second"] = database._pg_conn is second  # type: ignore[attr-defined]
    snap["notes_after_first"] = notes_after_first
    return _finish(database, snap)


def _schedule_both_fail(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = "sql_always"
    first = database.get_connection()
    second = database.get_connection()
    snap = _snapshot(database, [])
    snap["first_none"] = first is None
    snap["second_none"] = second is None
    return _finish(database, snap)


def _schedule_failed_cleanup_keeps_healthy(
    database: types.ModuleType,
) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = ""
    healthy = database.get_connection()
    healthy.closed = True  # type: ignore[attr-defined]
    PHASE = "sql_fails"
    failed = database.get_connection()
    snap = _snapshot(database, [])
    snap["failed_none"] = failed is None
    snap["global_still_healthy"] = database._pg_conn is healthy  # type: ignore[attr-defined]
    return _finish(database, snap)


def _schedule_release(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = ""
    borrowed = database.get_connection()
    notes = database.release_connection_after_failed_startup()
    again = database.release_connection_after_failed_startup()
    connects = COUNTS.get("psycopg2.connect", 0)
    snap = _snapshot(database, [])
    snap["borrowed_closed"] = bool(borrowed is not None and borrowed.closed)  # type: ignore[attr-defined]
    snap["release_notes"] = list(notes)
    snap["second_release_notes"] = list(again)
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
    snap = _snapshot(database, _join([thread]))
    snap["old_id"] = None if first is None else first.ident  # type: ignore[attr-defined]
    snap["new_id"] = None if second is None else second.ident  # type: ignore[attr-defined]
    snap["old_closed"] = bool(first is not None and first.closed)  # type: ignore[attr-defined]
    snap["new_open"] = bool(second is not None and not second.closed)  # type: ignore[attr-defined]
    return _finish(database, snap)


def _schedule_nested(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = ""
    rows = database.fetch_all_trades_ordered()
    snap = _snapshot(database, [])
    snap["helper_rows"] = rows
    snap["helper_reused"] = COUNTS.get("psycopg2.connect", 0) == 1
    again = database.fetch_all_trades_ordered()
    snap["second_helper_rows"] = again
    snap["connects_after_second_helper"] = COUNTS.get("psycopg2.connect", 0)
    return _finish(database, snap)


def _schedule_nested_waits(database: types.ModuleType) -> dict[str, object]:
    global PHASE
    _reset(database)
    PHASE = "hold"
    first = _start(lambda: _call_get(database, hold_lock=False), "initializer")
    if not INIT_ENTERED.wait(timeout=3):
        INIT_PROCEED.set()
        _join([first])
        raise TimeoutError("initializer did not reach connect")
    done = threading.Event()

    def helper() -> int:
        try:
            database.fetch_all_trades_ordered()
            return COUNTS.get("psycopg2.connect", 0)
        finally:
            done.set()

    other = _start(helper, "helper")
    blocked = not done.wait(timeout=0.3)
    held = COUNTS.get("psycopg2.connect", 0)
    INIT_PROCEED.set()
    snap = _snapshot(database, _join([first, other]))
    snap["helper_blocked"] = blocked
    snap["connects_while_held"] = held
    return _finish(database, snap)


def _concurrency(database: types.ModuleType, *, pre_fix: bool) -> dict[str, object]:
    if pre_fix:
        return {"pre_fix_overlap": _schedule_pre_fix(database)}
    return {
        "serialized_overlap": _schedule_serialized(database),
        "cursor_fails": _schedule_failure(database, "cursor_fails"),
        "sql_fails": _schedule_failure(database, "sql_fails"),
        "commit_fails": _schedule_failure(database, "commit_fails"),
        "rollback_fails": _schedule_failure(database, "rollback_fails"),
        "cursor_close_fails": _schedule_failure(database, "cursor_close_fails"),
        "conn_close_fails": _schedule_failure(database, "conn_close_fails"),
        "both_fail": _schedule_both_fail(database),
        "failed_cleanup_keeps_healthy": _schedule_failed_cleanup_keeps_healthy(
            database
        ),
        "release": _schedule_release(database),
        "replace_during_close": _schedule_replace(database),
        "nested_helper": _schedule_nested(database),
        "nested_waits": _schedule_nested_waits(database),
    }


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
    orders = sys.modules["forex_bot.orders"]
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
        CURSORS.clear()
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


def _lock_fact(database: types.ModuleType) -> dict[str, object]:
    return {
        "lock_type": type(database._pg_lock).__name__,  # type: ignore[attr-defined]
        "reentrant": type(database._pg_lock).__name__ == "RLock",  # type: ignore[attr-defined]
        "get_connection_module": database.get_connection.__module__,
    }


def main() -> int:
    out = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "concurrency"
    report: dict[str, object] = {"foreign_project_on_path": _confine()}
    code = 0
    try:
        _install_guards()
        work = Path(os.environ["D9_WORK_DIR"])
        (work / "a.txt").write_text("synthetic", encoding="utf-8")
        report["guard_checks"] = _guard_self_check(work)
        if mode == "lifespan":
            import forex_bot.app as appmod
            from forex_bot import database

            report["dotenv_calls_at_import"] = DOTENV_CALLS
            report["lock"] = _lock_fact(database)
            report["cases"] = _lifespan_cases(appmod, database)
        else:
            from forex_bot import database

            report["dotenv_calls_at_import"] = DOTENV_CALLS
            report["lock"] = _lock_fact(database)
            report["schedules"] = _concurrency(database, pre_fix=mode == "pre_fix")
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
