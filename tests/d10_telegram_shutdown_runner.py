"""Isolated D.10 runner. Production modules load only after guards."""

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
import time
import traceback
import types
import urllib.request
from pathlib import Path

NETWORK: list[str] = []
FS_DENIALS: list[str] = []
SELF_PIPE: list[str] = []
CONNECTIONS: list[FakeConnection] = []
CURSORS: list[FakeCursor] = []
HTTP_METHODS: list[str] = []
QUERIES: list[dict[str, object]] = []
USE_AFTER_CLOSE: list[int] = []
COUNTS: dict[str, int] = {}
PHASE = ""
NEXT_ID = 0
NEXT_CURSOR = 0
DOTENV_CALLS = 0
HARNESS_CLOSING = False
BLOCK_POLLS = 0
BLOCK_TRADE_QUERY = False
NEXT_UPDATE: dict[str, object] | None = None
RELEASE_GENERATION = 0

RELEASE_POLL = threading.Event()
IN_POLL = threading.Event()
FIRST_POLL = threading.Event()
QUERY_HELD = threading.Event()
QUERY_RELEASE = threading.Event()
TRADE_QUERY = threading.Event()

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

    def execute(self, sql: object, _params: object = None) -> None:
        if self.closed:
            USE_AFTER_CLOSE.append(self.ident)
        text = str(sql)
        if "FROM trades" in text:
            caller = threading.current_thread()
            QUERIES.append(
                {
                    "thread": caller.ident,
                    "caller": caller.name,
                    "caller_alive": caller.is_alive(),
                    "generation": RELEASE_GENERATION,
                    "connection_id": self.connection_id,
                    "cursor_id": self.ident,
                }
            )
            TRADE_QUERY.set()
            if BLOCK_TRADE_QUERY:
                QUERY_HELD.set()
                if not QUERY_RELEASE.wait(8):
                    raise TimeoutError("trade query hold expired")

    def fetchall(self) -> list[object]:
        return []

    def fetchone(self) -> None:
        return None

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        global NEXT_ID
        NEXT_ID += 1
        self.ident = NEXT_ID
        self.closed = False
        self.close_calls = 0
        self.harness_close_calls = 0
        self.commits = 0

    def cursor(self) -> FakeCursor:
        if self.closed:
            USE_AFTER_CLOSE.append(self.ident)
        cursor = FakeCursor(self.ident)
        CURSORS.append(cursor)
        return cursor

    def commit(self) -> None:
        if self.closed:
            USE_AFTER_CLOSE.append(self.ident)
        self.commits += 1

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        if HARNESS_CLOSING:
            self.harness_close_calls += 1
            self.closed = True
            return
        self.close_calls += 1
        if PHASE in {"conn_close_fails", "release_fails"}:
            raise RuntimeError("injected connection close failure")
        self.closed = True


def _bump(name: str) -> None:
    COUNTS[name] = COUNTS.get(name, 0) + 1


def _deny_network(kind: str, address: object = None) -> None:
    NETWORK.append(f"{kind} {address!r}")
    raise RuntimeError(f"d10 network denied {kind} {address!r}")


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
    raise PermissionError("d10 path denied")


def _method_name(url: object) -> str:
    return str(url).rsplit("/", 1)[-1][:40]


def _response(payload: dict[str, object]) -> types.SimpleNamespace:
    raw = json.dumps(payload).encode()
    return types.SimpleNamespace(
        status_code=200,
        content=raw,
        text=raw.decode(),
        json=lambda: payload,
    )


def _note_http(method: str) -> None:
    HTTP_METHODS.append(method)
    _bump("http")


def _get_updates(params: dict[str, object]) -> types.SimpleNamespace:
    global BLOCK_POLLS, NEXT_UPDATE
    timeout = params.get("timeout", 1)
    try:
        short = int(timeout) == 0  # type: ignore[arg-type]
    except (TypeError, ValueError):
        short = False
    if short:
        return _response({"ok": True, "result": []})
    FIRST_POLL.set()
    if BLOCK_POLLS > 0:
        BLOCK_POLLS -= 1
        IN_POLL.set()
        if not RELEASE_POLL.wait(12):
            raise TimeoutError("fake long poll was not released")
    payload = NEXT_UPDATE
    NEXT_UPDATE = None
    if payload is None:
        payload = {"ok": True, "result": []}
    return _response(payload)


def _install_guards() -> None:
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

    def http_get(url: object, **kwargs: object) -> types.SimpleNamespace:
        method = _method_name(url)
        _note_http(method)
        params = kwargs.get("params")
        if method == "getWebhookInfo":
            return _response({"ok": True, "result": {"url": ""}})
        if method == "getUpdates":
            return _get_updates(params if isinstance(params, dict) else {})
        return _response({"ok": True, "result": []})

    def http_post(url: object, **_kwargs: object) -> types.SimpleNamespace:
        _note_http(_method_name(url))
        return _response({"ok": True, "result": True})

    class Session:
        def mount(self, *_a: object, **_k: object) -> None:
            return None

        def close(self) -> None:
            return None

        def get(self, url: object, **kwargs: object) -> types.SimpleNamespace:
            return http_get(url, **kwargs)

        def post(self, url: object, **kwargs: object) -> types.SimpleNamespace:
            return http_post(url, **kwargs)

    requests.get = http_get  # type: ignore[attr-defined]
    requests.post = http_post  # type: ignore[attr-defined]
    requests.request = http_get  # type: ignore[attr-defined]
    requests.Session = Session  # type: ignore[attr-defined]
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


def _expect_deny(label: str, fn: object) -> bool:
    _ = label
    try:
        fn()  # type: ignore[operator]
    except RuntimeError as exc:
        return "d10 network denied" in str(exc)
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
    checks["system_denied"] = _expect_deny("system", lambda: os.system("echo d10"))
    checks["popen_denied"] = _expect_deny(
        "popen", lambda: subprocess.Popen(["python", "-c", "print(1)"])
    )
    checks["run_denied"] = _expect_deny(
        "run", lambda: subprocess.run(["python", "-V"], check=False)
    )
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
        "shell", lambda: asyncio.create_subprocess_shell("echo d10")
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
    probes = (
        ("ops_denied", work / "data" / "ops" / "live_safety_state.json"),
        ("shadow_denied", work / "data" / "research" / "v2_shadow" / "state.json"),
        ("credential_denied", work / "credential.txt"),
        ("env_denied", work / ".env"),
        ("volume_denied", work / "pgdata" / "db.txt"),
    )
    for label, path in probes:
        try:
            with open(path, "w", encoding="utf-8"):
                checks[label] = False
        except PermissionError:
            checks[label] = True
    try:
        with Path(probes[0][1]).open("w", encoding="utf-8"):
            checks["path_open_denied"] = False
    except PermissionError:
        checks["path_open_denied"] = True
    NETWORK.clear()
    FS_DENIALS.clear()
    return checks


def _confine() -> list[str]:
    removed = [
        item
        for item in list(sys.path)
        if "concensus-forecast" in item.replace("\\", "/").lower()
    ]
    for item in removed:
        sys.path.remove(item)
    return removed


def _poller_in(name: str) -> bool:
    frames = sys._current_frames()
    for row in _threads():
        ident = row.get("ident")
        if not isinstance(ident, int):
            continue
        frame = frames.get(ident)
        while frame is not None:
            if frame.f_code.co_name == name:
                return True
            frame = frame.f_back
    return False


def _threads() -> list[dict[str, object]]:
    rows = []
    for item in threading.enumerate():
        if item.name == "telegram-control":
            rows.append(
                {
                    "ident": item.ident,
                    "alive": item.is_alive(),
                    "daemon": item.daemon,
                }
            )
    return rows


def _lock_free(database: types.ModuleType) -> bool:
    lock = database._pg_lock  # type: ignore[attr-defined]
    acquired = lock.acquire(blocking=False)
    if acquired:
        lock.release()
    return acquired


def _db_view(database: types.ModuleType) -> dict[str, object]:
    conn = database._pg_conn  # type: ignore[attr-defined]
    cursor = database._pg_cursor  # type: ignore[attr-defined]
    return {
        "connection_id": getattr(conn, "ident", None),
        "connection_open": conn is not None and not conn.closed,
        "cursor_id": getattr(cursor, "ident", None),
        "cursor_open": cursor is not None and not cursor.closed,
        "lock_free": _lock_free(database),
    }


def _harness_close(database: types.ModuleType) -> int:
    global HARNESS_CLOSING
    HARNESS_CLOSING = True
    closed = 0
    try:
        for conn in CONNECTIONS:
            if not conn.closed:
                conn.close()
                closed += 1
        for cursor in CURSORS:
            if not cursor.closed:
                cursor.close()
    finally:
        HARNESS_CLOSING = False
    database._pg_conn = None  # type: ignore[attr-defined]
    database._pg_cursor = None  # type: ignore[attr-defined]
    return closed


def _contain(tc: types.ModuleType) -> dict[str, object]:
    global BLOCK_POLLS, BLOCK_TRADE_QUERY, NEXT_UPDATE
    tc._stop_event.set()  # type: ignore[attr-defined]
    RELEASE_POLL.set()
    QUERY_RELEASE.set()
    joined: list[dict[str, object]] = []
    for item in list(threading.enumerate()):
        if item.name == "telegram-control" and item is not threading.current_thread():
            item.join(timeout=3)
            joined.append({"ident": item.ident, "alive": item.is_alive()})
    escaped = [row for row in joined if row["alive"]]
    if not escaped:
        tc.reset_telegram_control_for_tests()
    RELEASE_POLL.clear()
    QUERY_RELEASE.clear()
    QUERY_HELD.clear()
    TRADE_QUERY.clear()
    IN_POLL.clear()
    FIRST_POLL.clear()
    BLOCK_POLLS = 0
    BLOCK_TRADE_QUERY = False
    NEXT_UPDATE = None
    return {"harness_joined": joined, "escaped": escaped}


def _start(tc: types.ModuleType, *, block: bool) -> None:
    global BLOCK_POLLS, NEXT_UPDATE
    IN_POLL.clear()
    FIRST_POLL.clear()
    RELEASE_POLL.clear()
    NEXT_UPDATE = None
    BLOCK_POLLS = 20 if block else 0
    tc.start_telegram_control()
    ready = IN_POLL.wait(5) if block else FIRST_POLL.wait(5)
    if not ready:
        raise TimeoutError("telegram poller did not reach the expected point")


def _stop_timed(tc: types.ModuleType) -> dict[str, object]:
    before = _threads()
    started = time.perf_counter()
    returned = tc.stop_telegram_control()
    elapsed = time.perf_counter() - started
    return {
        "return_value": returned,
        "elapsed_sec": round(elapsed, 4),
        "threads_before": before,
        "threads_after": _threads(),
        "alive_after": any(row["alive"] for row in _threads()),
        "stored_thread_cleared": tc._poller_thread is None,  # type: ignore[attr-defined]
        "started_flag": tc._poller_started,  # type: ignore[attr-defined]
        "stop_event_set": tc._stop_event.is_set(),  # type: ignore[attr-defined]
    }


def _trades_update() -> dict[str, object]:
    return {
        "ok": True,
        "result": [
            {
                "update_id": 7,
                "message": {"text": "/trades", "chat": {"id": 1001}},
            }
        ],
    }


def _run_threads(database: types.ModuleType, tc: types.ModuleType) -> dict[str, object]:
    global BLOCK_POLLS, BLOCK_TRADE_QUERY, NEXT_UPDATE, RELEASE_GENERATION, PHASE
    from forex_bot.strategy_meta import strategies

    schedules: dict[str, object] = {}
    active = sorted(name for name, item in strategies.items() if item.active is True)

    schedules["stop_before_start"] = {
        "evidence": "ACTUAL_TELEGRAM_FUNCTION_ISOLATED",
        "functions": ["stop_telegram_control"],
        "application": _stop_timed(tc),
        "threads_after_application": _threads(),
        "harness": _contain(tc),
    }

    _start(tc, block=False)
    normal = _stop_timed(tc)
    schedules["normal_stop"] = {
        "evidence": "ACTUAL_TELEGRAM_FUNCTION_ISOLATED",
        "functions": ["start_telegram_control", "stop_telegram_control"],
        "fake": "immediate getUpdates",
        "application": normal,
        "harness": _contain(tc),
    }

    second = _stop_timed(tc)
    schedules["repeated_stop"] = {
        "evidence": "ACTUAL_TELEGRAM_FUNCTION_ISOLATED",
        "functions": ["stop_telegram_control"],
        "application": second,
        "harness": _contain(tc),
    }

    _start(tc, block=False)
    tc.start_telegram_control()
    repeated = {
        "thread_count": len(_threads()),
        "threads": _threads(),
        "started_flag": tc._poller_started,  # type: ignore[attr-defined]
    }
    schedules["repeated_start"] = {
        "evidence": "ACTUAL_TELEGRAM_FUNCTION_ISOLATED",
        "functions": ["start_telegram_control"],
        "application": repeated,
        "harness": _contain(tc),
    }

    first = database.get_connection()
    first_id = first.ident
    _start(tc, block=True)
    blocked = _stop_timed(tc)
    view_after_stop = _db_view(database)
    RELEASE_GENERATION += 1
    notes = database.release_connection_after_failed_startup()
    NEXT_UPDATE = _trades_update()
    BLOCK_POLLS = 0
    before_queries = len(QUERIES)
    RELEASE_POLL.set()
    if not TRADE_QUERY.wait(5):
        raise TimeoutError("poller did not query after release")
    later = [row for row in QUERIES[before_queries:] if row["generation"] >= 1]
    published = database._pg_conn  # type: ignore[attr-defined]
    schedules["stop_during_blocked_poll"] = {
        "evidence": "ACTUAL_COMBINED_TELEGRAM_DATABASE_ISOLATED",
        "functions": [
            "start_telegram_control",
            "stop_telegram_control",
            "_poller_loop",
            "release_connection_after_failed_startup",
            "fetch_all_trades_ordered",
            "get_connection",
        ],
        "fake": "blocked session.get until after stop and release",
        "application_stop": blocked,
        "database_after_stop_before_release": view_after_stop,
        "release_notes": list(notes),
        "old_connection_id": first_id,
        "old_closed": first.closed,
        "queries_after_release": later,
        "new_connection_id": getattr(published, "ident", None),
        "use_after_close": list(USE_AFTER_CLOSE),
        "threads_before_harness": _threads(),
        "harness": _contain(tc),
    }
    schedules["stop_during_blocked_poll"]["harness_closed"] = _harness_close(database)

    _start(tc, block=True)
    timed_out = _stop_timed(tc)
    restarted = tc.start_telegram_control()
    overlap = _threads()
    schedules["restart_after_incomplete_stop"] = {
        "evidence": "ACTUAL_TELEGRAM_FUNCTION_ISOLATED",
        "functions": ["start_telegram_control", "stop_telegram_control"],
        "fake": "blocked session.get across the real join timeout",
        "application_stop": timed_out,
        "second_start_return": restarted,
        "stop_event_after_second_start": tc._stop_event.is_set(),  # type: ignore[attr-defined]
        "threads_after_second_start": overlap,
        "thread_count": len(overlap),
        "harness": _contain(tc),
    }

    _start(tc, block=True)
    BLOCK_TRADE_QUERY = True
    NEXT_UPDATE = _trades_update()
    BLOCK_POLLS = 0
    RELEASE_POLL.set()
    if not QUERY_HELD.wait(5):
        raise TimeoutError("poller did not hold the trade query")
    lock_while_held = _lock_free(database)
    release_done = threading.Event()
    release_box: dict[str, object] = {}

    def _release() -> None:
        release_box["notes"] = database.release_connection_after_failed_startup()
        release_box["view"] = _db_view(database)
        release_done.set()

    releaser = threading.Thread(target=_release, name="d10-release")
    releaser.start()
    finished_early = release_done.wait(0.3)
    QUERY_RELEASE.set()
    releaser.join(timeout=3)
    schedules["release_waits_for_locked_query"] = {
        "evidence": "ACTUAL_COMBINED_TELEGRAM_DATABASE_ISOLATED",
        "functions": [
            "fetch_all_trades_ordered",
            "release_connection_after_failed_startup",
        ],
        "fake": "cursor.execute blocks while the production helper holds _pg_lock",
        "lock_free_while_query_held": lock_while_held,
        "release_finished_before_query_release": finished_early,
        "release_finished_after": release_done.is_set(),
        "application": release_box,
        "threads_before_harness": _threads(),
        "harness": _contain(tc),
    }
    schedules["release_waits_for_locked_query"]["harness_closed"] = _harness_close(
        database
    )

    holder_ready = threading.Event()
    holder_release = threading.Event()

    def _hold() -> None:
        with database._pg_lock:  # type: ignore[attr-defined]
            holder_ready.set()
            holder_release.wait(5)

    holder = threading.Thread(target=_hold, name="d10-lock-holder")
    holder.start()
    if not holder_ready.wait(3):
        raise TimeoutError("lock holder did not acquire _pg_lock")
    TRADE_QUERY.clear()
    _start(tc, block=True)
    NEXT_UPDATE = _trades_update()
    BLOCK_POLLS = 0
    RELEASE_POLL.set()
    entered = False
    deadline = time.perf_counter() + 3
    while time.perf_counter() < deadline:
        if _poller_in("fetch_all_trades_ordered") and not TRADE_QUERY.is_set():
            entered = True
            break
        threading.Event().wait(0.05)
    stop_box: dict[str, object] = {}
    stop_done = threading.Event()

    def _call_stop() -> None:
        stop_box.update(_stop_timed(tc))
        stop_done.set()

    stopper = threading.Thread(target=_call_stop, name="d10-stop")
    stopper.start()
    stop_finished_early = stop_done.wait(0.3)
    holder_release.set()
    holder.join(timeout=3)
    stopper.join(timeout=3)
    schedules["stop_while_other_thread_holds_lock"] = {
        "evidence": "ACTUAL_COMBINED_TELEGRAM_DATABASE_ISOLATED",
        "functions": ["stop_telegram_control", "fetch_all_trades_ordered"],
        "poller_blocked_on_foreign_lock": entered,
        "stop_finished_while_foreign_lock_held": stop_finished_early,
        "application": stop_box,
        "harness": _contain(tc),
    }
    schedules["stop_while_other_thread_holds_lock"]["harness_closed"] = _harness_close(
        database
    )

    PHASE = ""
    direct_old = database.get_connection()
    direct_notes = database.release_connection_after_failed_startup()
    direct_rows = database.fetch_all_trades_ordered()
    direct_new = database._pg_conn  # type: ignore[attr-defined]
    schedules["direct_helper_after_release"] = {
        "evidence": "ACTUAL_DATABASE_FUNCTION_ISOLATED",
        "functions": [
            "get_connection",
            "release_connection_after_failed_startup",
            "fetch_all_trades_ordered",
        ],
        "old_id": direct_old.ident,
        "old_closed": direct_old.closed,
        "new_id": getattr(direct_new, "ident", None),
        "rows": len(direct_rows),
        "notes": list(direct_notes),
        "use_after_close": list(USE_AFTER_CLOSE),
        "harness_closed": _harness_close(database),
    }

    PHASE = "conn_close_fails"
    failing = database.get_connection()
    fail_notes = database.release_connection_after_failed_startup()
    schedules["release_close_failure"] = {
        "evidence": "ACTUAL_DATABASE_FUNCTION_ISOLATED",
        "functions": ["release_connection_after_failed_startup"],
        "notes": list(fail_notes),
        "global_cleared": database._pg_conn is None,  # type: ignore[attr-defined]
        "object_still_open": not failing.closed,
        "close_calls": failing.close_calls,
        "harness_closed": _harness_close(database),
    }
    PHASE = ""

    ids: list[int] = []

    def _overlap() -> None:
        conn = database.get_connection()
        if conn is not None:
            ids.append(conn.ident)

    left = threading.Thread(target=_overlap)
    right = threading.Thread(target=_overlap)
    before_connects = COUNTS.get("psycopg2.connect", 0)
    left.start()
    right.start()
    left.join(timeout=3)
    right.join(timeout=3)
    schedules["init_lock_overlap"] = {
        "evidence": "ACTUAL_DATABASE_FUNCTION_ISOLATED",
        "functions": ["get_connection"],
        "ids": ids,
        "connect_delta": COUNTS.get("psycopg2.connect", 0) - before_connects,
        "harness_closed": _harness_close(database),
    }

    open_connections = [conn.ident for conn in CONNECTIONS if not conn.closed]
    open_cursors = [cursor.ident for cursor in CURSORS if not cursor.closed]
    return {
        "active_strategies": active,
        "schedules": schedules,
        "open_connections": open_connections,
        "open_cursors": open_cursors,
        "use_after_close": list(USE_AFTER_CLOSE),
        "http_methods": sorted(set(HTTP_METHODS)),
        "escaped_threads": _threads(),
    }


def _lifespan_cases(
    appmod: types.ModuleType, database: types.ModuleType, tc: types.ModuleType
) -> dict[str, object]:
    from forex_bot.live_safety import _blank_document, reset_live_safety_for_tests
    from forex_bot.strategy_meta import strategies

    safety = Path(os.environ["LIVE_SAFETY_STATE_PATH"])
    real_stop = tc.stop_telegram_control

    def wrapped_stop() -> None:
        real_stop()
        if PHASE == "stop_raises":
            raise RuntimeError("injected shutdown failure")

    tc.stop_telegram_control = wrapped_stop  # type: ignore[attr-defined]

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
            if name == "build_api" and PHASE in {"broker", "release_fails"}:
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
    tasks: list[asyncio.Task[object]] = []
    real_create = asyncio.create_task

    def counting_create(coro, *args, **kwargs):  # type: ignore[no-untyped-def]
        _bump("create_task")
        task = real_create(coro, *args, **kwargs)
        tasks.append(task)
        return task

    asyncio.create_task = counting_create  # type: ignore[assignment]

    async def one(phase: str, rewrite: str) -> dict[str, object]:
        global PHASE, BLOCK_POLLS
        tasks.clear()
        CONNECTIONS.clear()
        CURSORS.clear()
        COUNTS.clear()
        database._pg_conn = None  # type: ignore[attr-defined]
        database._pg_cursor = None  # type: ignore[attr-defined]
        PHASE = ""
        _contain(tc)
        PHASE = phase
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
        if phase == "blocked_shutdown":
            BLOCK_POLLS = 20
            RELEASE_POLL.clear()
            IN_POLL.clear()
        else:
            BLOCK_POLLS = 0
        blocked_ready = True
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        yielded = False
        escaped = ""
        message = ""
        try:
            async with appmod.lifespan(appmod.app):
                yielded = True
                if phase == "blocked_shutdown":
                    blocked_ready = await asyncio.to_thread(IN_POLL.wait, 5)
        except Exception as exc:  # noqa: BLE001
            escaped = type(exc).__name__
            message = str(exc)
        pending = [task for task in tasks if not task.done()]
        from forex_bot.live_safety import live_order_auth_state

        threads_now = _threads()
        row: dict[str, object] = {
            "evidence": "ACTUAL_LIFESPAN_ISOLATED",
            "yielded": yielded,
            "escaped_type": escaped,
            "message": message,
            "blocked_ready": blocked_ready,
            "auth": live_order_auth_state(),
            "active": sorted(
                name for name, item in strategies.items() if item.active is True
            ),
            "pending": len(pending),
            "created": len(tasks),
            "threads_after_application": threads_now,
            "alive_after_application": any(item["alive"] for item in threads_now),
            "pg_conn_held": database._pg_conn is not None
            and not database._pg_conn.closed,  # type: ignore[attr-defined]
            "application_close_calls": sum(conn.close_calls for conn in CONNECTIONS),
            "cleanup_errors": list(appmod.startup_cleanup_errors()),
            "connect_calls": COUNTS.get("psycopg2.connect", 0),
        }
        PHASE = ""
        harness = _contain(tc)
        harness_closed = _harness_close(database)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        row["harness"] = harness
        row["harness_closed"] = harness_closed
        row["harness_cancelled"] = len(pending)
        return row

    async def all_cases() -> dict[str, object]:
        return {
            "corrupt": await one("", "corrupt"),
            "broker": await one("broker", "valid"),
            "normal": await one("", "valid"),
            "await_health": await one("await_health", "valid"),
            "stop_raises": await one("stop_raises", "valid"),
            "release_fails": await one("release_fails", "valid"),
            "repeat": await one("", "valid"),
            "blocked_shutdown": await one("blocked_shutdown", "valid"),
            "startup_failure_after_telegram": {
                "evidence": "NOT_REACHABLE_IN_CURRENT_SOURCE",
                "reason": (
                    "start_telegram_control is the last statement in the "
                    "startup try and it catches its own errors"
                ),
            },
        }

    return asyncio.run(all_cases())


def main() -> int:
    out = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "threads"
    report: dict[str, object] = {"foreign_project_on_path": _confine(), "mode": mode}
    code = 0
    try:
        _install_guards()
        work = Path(os.environ["D10_WORK_DIR"])
        (work / "a.txt").write_text("synthetic", encoding="utf-8")
        report["guard_checks"] = _guard_self_check(work)
        if not all(report["guard_checks"].values()):  # type: ignore[attr-defined]
            raise RuntimeError("guard self-check failed")
        from forex_bot import database
        from forex_bot import telegram_control as tc

        report["dotenv_calls_at_import"] = DOTENV_CALLS
        report["commands_enabled"] = tc.commands_enabled()
        if mode == "lifespan":
            import forex_bot.app as appmod

            report["cases"] = _lifespan_cases(appmod, database, tc)
        else:
            report.update(_run_threads(database, tc))
        report["network_after"] = list(NETWORK)
        report["escaped_final"] = _threads()
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        code = 1
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
