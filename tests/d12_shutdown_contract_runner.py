"""Isolated D.12 runner. Production modules load only after D.11 guards."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sys
import threading
import time
import traceback
import types
from pathlib import Path


def _load_d11():
    path = Path(__file__).with_name("d11_telegram_shutdown_runner.py")
    spec = importlib.util.spec_from_file_location("d11_shutdown_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("d11 runner could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D11 = _load_d11()


class _LogGrab(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


LOGS = _LogGrab()


def _status_mentions(lines: list[str]) -> dict[str, bool]:
    text = "\n".join(lines)
    return {
        "incomplete": "STOP_INCOMPLETE_WORKER_ALIVE" in text,
        "completed": "STOP_COMPLETED" in text,
        "not_running": "STOP_NOT_RUNNING" in text,
        "worker_alive_words": "worker remains alive" in text.lower(),
    }


def _snapshot(
    appmod: types.ModuleType, database: types.ModuleType, tc: types.ModuleType
) -> dict[str, object]:
    conn = database._pg_conn  # type: ignore[attr-defined]
    cursor = database._pg_cursor  # type: ignore[attr-defined]
    thread = tc._poller_thread  # type: ignore[attr-defined]
    return {
        "threads": D11._threads(),
        "stored_alive": thread is not None and thread.is_alive(),
        "stored_ident": getattr(thread, "ident", None),
        "stop_event": tc._stop_event.is_set(),  # type: ignore[attr-defined]
        "cleanup_errors": list(appmod.startup_cleanup_errors()),
        "connection_id": getattr(conn, "ident", None),
        "connection_open": conn is not None and not conn.closed,
        "cursor_id": getattr(cursor, "ident", None),
        "cursor_open": cursor is not None and not cursor.closed,
        "application_close_calls": sum(item.close_calls for item in D11.CONNECTIONS),
        "status_in_logs": _status_mentions(LOGS.lines),
    }


def _prepare(appmod: types.ModuleType) -> list[asyncio.Task[object]]:
    tasks: list[asyncio.Task[object]] = []

    def fake_async(name: str):
        async def _inner() -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                if name == "health_snapshot_loop" and D11.PHASE == "await_health":
                    raise RuntimeError("injected task await failure")
                raise

        return _inner

    def record(name: str):
        def _call(*_a: object, **_k: object) -> dict[str, str]:
            D11._bump(name)
            if name == "build_api" and D11.PHASE in {"broker", "release_fails"}:
                raise RuntimeError("injected broker construction failure")
            if name == "alert" and D11.PHASE == "alert_raises":
                text = str(_a[0] if _a else "")
                if "STOPPED" in text:
                    raise RuntimeError("injected alert failure")
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
    real_create = asyncio.create_task

    def counting_create(coro, *args, **kwargs):  # type: ignore[no-untyped-def]
        D11._bump("create_task")
        task = real_create(coro, *args, **kwargs)
        tasks.append(task)
        return task

    asyncio.create_task = counting_create  # type: ignore[assignment]
    return tasks


def _arm(database: types.ModuleType, tc: types.ModuleType, *, block: bool) -> None:
    D11.CONNECTIONS.clear()
    D11.CURSORS.clear()
    D11.COUNTS.clear()
    database._pg_conn = None  # type: ignore[attr-defined]
    database._pg_cursor = None  # type: ignore[attr-defined]
    D11._contain(tc)
    D11.PHASE = ""
    D11.BLOCK_POLLS = 20 if block else 0
    D11.RELEASE_POLL.clear()
    D11.IN_POLL.clear()
    D11.FIRST_POLL.clear()
    LOGS.lines.clear()


def _safety(rewrite: str) -> None:
    from forex_bot.live_safety import _blank_document, reset_live_safety_for_tests

    safety = Path(os.environ["LIVE_SAFETY_STATE_PATH"])
    reset_live_safety_for_tests()
    if safety.exists():
        safety.unlink()
    if rewrite == "corrupt":
        safety.write_text("{not-json", encoding="utf-8")
        return
    safety.write_text(
        json.dumps(_blank_document(reason="operator_preflight_blocked")),
        encoding="utf-8",
    )


async def _enter(
    appmod: types.ModuleType,
    *,
    phase: str,
    rewrite: str,
    block: bool,
    database: types.ModuleType,
    tc: types.ModuleType,
) -> dict[str, object]:
    tasks = getattr(appmod, "_d12_tasks")
    tasks.clear()
    asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
    _arm(database, tc, block=block)
    _safety(rewrite)
    D11.PHASE = phase
    yielded = False
    escaped = ""
    started = time.perf_counter()
    try:
        async with appmod.lifespan(appmod.app):
            yielded = True
            if block:
                await asyncio.to_thread(D11.IN_POLL.wait, 5)
    except Exception as exc:  # noqa: BLE001
        escaped = type(exc).__name__
    elapsed = round(time.perf_counter() - started, 4)
    pending = [task for task in tasks if not task.done()]
    row = _snapshot(appmod, database, tc)
    row.update(
        {
            "yielded": yielded,
            "escaped_type": escaped,
            "elapsed_sec": elapsed,
            "pending": len(pending),
            "created": len(tasks),
            "evidence": "ACTUAL_LIFESPAN_ISOLATED",
            "stop_wrapped": False,
        }
    )
    D11.PHASE = ""
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    row["harness"] = D11._contain(tc)
    row["harness_closed"] = D11._harness_close(database)
    return row


def _contract(
    appmod: types.ModuleType, database: types.ModuleType, tc: types.ModuleType
) -> dict[str, object]:
    from forex_bot.live_safety import live_order_auth_state
    from forex_bot.strategy_meta import strategies

    appmod._d12_tasks = _prepare(appmod)  # type: ignore[attr-defined]

    async def all_cases() -> dict[str, object]:
        normal = await _enter(
            appmod, phase="", rewrite="valid", block=False, database=database, tc=tc
        )
        blocked = await _enter(
            appmod,
            phase="",
            rewrite="valid",
            block=True,
            database=database,
            tc=tc,
        )
        direct = D11._stop_timed(tc)
        corrupt = await _enter(
            appmod, phase="", rewrite="corrupt", block=False, database=database, tc=tc
        )
        broker = await _enter(
            appmod,
            phase="broker",
            rewrite="valid",
            block=False,
            database=database,
            tc=tc,
        )
        real_stop = tc.stop_telegram_control
        raised_status: list[object] = []

        def raising_stop() -> object:
            result = real_stop()
            raised_status.append(result)
            raise RuntimeError("injected shutdown failure")

        _arm(database, tc, block=False)
        _safety("valid")
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        tc.stop_telegram_control = raising_stop  # type: ignore[attr-defined]
        raised_escaped = ""
        raised_yielded = False
        try:
            async with appmod.lifespan(appmod.app):
                raised_yielded = True
        except Exception as exc:  # noqa: BLE001
            raised_escaped = type(exc).__name__
        raised = _snapshot(appmod, database, tc)
        raised["escaped_type"] = raised_escaped
        raised["stop_status_before_raise"] = list(raised_status)
        raised["yielded"] = raised_yielded
        tc.stop_telegram_control = real_stop  # type: ignore[attr-defined]
        raised["harness"] = D11._contain(tc)
        raised["harness_closed"] = D11._harness_close(database)
        awaited = await _enter(
            appmod,
            phase="await_health",
            rewrite="valid",
            block=False,
            database=database,
            tc=tc,
        )
        release = await _enter(
            appmod,
            phase="release_fails",
            rewrite="valid",
            block=False,
            database=database,
            tc=tc,
        )
        alert = await _enter(
            appmod,
            phase="alert_raises",
            rewrite="valid",
            block=False,
            database=database,
            tc=tc,
        )
        tasks = appmod._d12_tasks  # type: ignore[attr-defined]
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        _arm(database, tc, block=True)
        _safety("valid")
        started_flag = asyncio.Event()

        async def cancellable() -> None:
            async with appmod.lifespan(appmod.app):
                await asyncio.to_thread(D11.IN_POLL.wait, 5)
                started_flag.set()
                await asyncio.Event().wait()

        job = asyncio.create_task(cancellable())
        await started_flag.wait()
        job.cancel()
        cancel_type = ""
        try:
            await job
        except asyncio.CancelledError:
            cancel_type = "CancelledError"
        cancel_snap = _snapshot(appmod, database, tc)
        cancel_snap["cancel_type"] = cancel_type
        cancel_snap["pending_owned"] = len(
            [task for task in tasks if not task.done()]
        )
        harness = D11._contain(tc)
        return {
            "authorisation": live_order_auth_state(),
            "active_strategies": sorted(
                name for name, item in strategies.items() if item.active is True
            ),
            "normal": normal,
            "blocked": blocked,
            "direct_stop_without_worker": direct,
            "corrupt": corrupt,
            "broker": broker,
            "stop_raises": raised,
            "await_health": awaited,
            "release_fails": release,
            "alert_raises": alert,
            "cancelled": cancel_snap,
            "cancel_harness": harness,
        }

    return asyncio.run(all_cases())


def _repeated(
    appmod: types.ModuleType, database: types.ModuleType, tc: types.ModuleType
) -> dict[str, object]:
    appmod._d12_tasks = _prepare(appmod)  # type: ignore[attr-defined]

    async def run() -> dict[str, object]:
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        _arm(database, tc, block=True)
        _safety("valid")
        yielded_a = False
        async with appmod.lifespan(appmod.app):
            yielded_a = True
            await asyncio.to_thread(D11.IN_POLL.wait, 5)
        snap_a = _snapshot(appmod, database, tc)
        ident_a = snap_a["stored_ident"]
        yielded_b = False
        escaped_b = ""
        started_b = time.perf_counter()
        try:
            async with appmod.lifespan(appmod.app):
                yielded_b = True
        except Exception as exc:  # noqa: BLE001
            escaped_b = type(exc).__name__
        elapsed_b = round(time.perf_counter() - started_b, 4)
        snap_b = _snapshot(appmod, database, tc)
        D11.BLOCK_POLLS = 0
        D11.RELEASE_POLL.set()
        exited = D11._join_named("telegram-control", 3)
        D11.FIRST_POLL.clear()
        yielded_c = False
        escaped_c = ""
        snap_c: dict[str, object] = {}
        try:
            async with appmod.lifespan(appmod.app):
                yielded_c = True
                await asyncio.to_thread(D11.FIRST_POLL.wait, 5)
                snap_c = _snapshot(appmod, database, tc)
        except Exception as exc:  # noqa: BLE001
            escaped_c = type(exc).__name__
        snap_c_after = _snapshot(appmod, database, tc)
        harness = D11._contain(tc)
        return {
            "yielded_a": yielded_a,
            "snap_a": snap_a,
            "ident_a": ident_a,
            "yielded_b": yielded_b,
            "escaped_b": escaped_b,
            "elapsed_b": elapsed_b,
            "snap_b": snap_b,
            "same_worker": snap_b["stored_ident"] == ident_a,
            "thread_count_b": len(snap_b["threads"]),  # type: ignore[arg-type]
            "worker_exit_before_c": exited,
            "yielded_c": yielded_c,
            "escaped_c": escaped_c,
            "snap_c": snap_c,
            "snap_c_after": snap_c_after,
            "thread_count_c": len(snap_c.get("threads", [])),  # type: ignore[arg-type]
            "fresh_worker": snap_c.get("stored_ident") not in {None, ident_a},
            "connection_reused_ab": snap_a["connection_id"] == snap_b["connection_id"],
            "harness": harness,
            "evidence": "ACTUAL_COMBINED_LIFECYCLE_ISOLATED",
        }

    return asyncio.run(run())


def _ownership(database: types.ModuleType, tc: types.ModuleType) -> dict[str, object]:
    not_running = D11._stop_timed(tc)
    first = database.get_connection()
    D11._start(tc, block=True)
    blocked = D11._stop_timed(tc)
    before_queries = len(D11.QUERIES)
    before_connects = D11.COUNTS.get("psycopg2.connect", 0)
    notes = database.release_connection_after_failed_startup()
    D11.NEXT_UPDATE = D11._trades_update()
    D11.BLOCK_POLLS = 0
    D11.RELEASE_POLL.set()
    delayed_exit = D11._join_named("telegram-control", 3)
    published = database._pg_conn  # type: ignore[attr-defined]
    delayed = {
        "stop": blocked,
        "release_notes": list(notes),
        "old_closed": first.closed,
        "queries": list(D11.QUERIES[before_queries:]),
        "connect_delta": D11.COUNTS.get("psycopg2.connect", 0) - before_connects,
        "published_id": getattr(published, "ident", None),
        "worker": delayed_exit,
    }
    D11._contain(tc)
    before_queries = len(D11.QUERIES)
    before_connects = D11.COUNTS.get("psycopg2.connect", 0)
    tc.stop_telegram_control()
    tc.cmd_trades()
    tc.cmd_search("eur")
    gate = {
        "queries": list(D11.QUERIES[before_queries:]),
        "connect_delta": D11.COUNTS.get("psycopg2.connect", 0) - before_connects,
    }
    holder_ready = threading.Event()
    holder_release = threading.Event()

    def _hold() -> None:
        with database._pg_lock:  # type: ignore[attr-defined]
            holder_ready.set()
            holder_release.wait(5)

    holder = threading.Thread(target=_hold, name="d12-lock-holder")
    holder.start()
    if not holder_ready.wait(3):
        raise TimeoutError("lock holder did not acquire")
    D11._start(tc, block=True)
    D11.NEXT_UPDATE = D11._trades_update()
    D11.BLOCK_POLLS = 0
    before_queries = len(D11.QUERIES)
    D11.RELEASE_POLL.set()
    waiting = False
    deadline = time.perf_counter() + 3
    while time.perf_counter() < deadline:
        if D11._poller_in("_read_trades_if_running") and not D11.TRADE_QUERY.is_set():
            waiting = True
            break
        threading.Event().wait(0.01)
    foreign: dict[str, object] = {}

    def _stop_foreign() -> None:
        foreign.update(D11._stop_timed(tc))

    stopper = threading.Thread(target=_stop_foreign, name="d12-stop")
    stopper.start()
    seen = False
    deadline = time.perf_counter() + 1
    while time.perf_counter() < deadline:
        if tc._stop_event.is_set():  # type: ignore[attr-defined]
            seen = True
            break
        threading.Event().wait(0.01)
    holder_release.set()
    holder.join(3)
    stopper.join(4)
    foreign_row = {
        "waiting": waiting,
        "event_while_held": seen,
        "queries": list(D11.QUERIES[before_queries:]),
        "stop": foreign,
    }
    D11._contain(tc)
    database.get_connection()
    D11._start(tc, block=True)
    D11.BLOCK_TRADE_QUERY = True
    D11.QUERY_HELD.clear()
    D11.QUERY_RELEASE.clear()
    D11.NEXT_UPDATE = D11._trades_update()
    D11.BLOCK_POLLS = 0
    D11.RELEASE_POLL.set()
    if not D11.QUERY_HELD.wait(5):
        raise TimeoutError("query was not held")
    release_done = threading.Event()

    def _release() -> None:
        database.release_connection_after_failed_startup()
        release_done.set()

    releaser = threading.Thread(target=_release, name="d12-release")
    releaser.start()
    early = release_done.wait(0.2)
    inflight: dict[str, object] = {}
    inflight_stop = threading.Thread(
        target=lambda: inflight.update(D11._stop_timed(tc)),
        name="d12-inflight-stop",
    )
    inflight_stop.start()
    inflight_stop.join(4)
    still = D11.QUERY_HELD.is_set() and not D11.QUERY_RELEASE.is_set()
    blocked_release = not release_done.is_set()
    D11.QUERY_RELEASE.set()
    releaser.join(3)
    D11._contain(tc)
    D11._harness_close(database)
    ids: list[int] = []

    def _overlap() -> None:
        conn = database.get_connection()
        if conn is not None:
            ids.append(conn.ident)

    left = threading.Thread(target=_overlap, name="d12-init-a")
    right = threading.Thread(target=_overlap, name="d12-init-b")
    before = D11.COUNTS.get("psycopg2.connect", 0)
    left.start()
    right.start()
    left.join(3)
    right.join(3)
    D11._harness_close(database)
    return {
        "not_running": not_running,
        "delayed": delayed,
        "gate": gate,
        "foreign": foreign_row,
        "inflight": {
            "release_finished_early": early,
            "query_still_held": still,
            "release_blocked": blocked_release,
            "stop": inflight,
        },
        "init": {
            "ids": ids,
            "connect_delta": D11.COUNTS.get("psycopg2.connect", 0) - before,
        },
        "open_connections": [item.ident for item in D11.CONNECTIONS if not item.closed],
        "open_cursors": [item.ident for item in D11.CURSORS if not item.closed],
        "use_after_close": list(D11.USE_AFTER_CLOSE),
        "evidence": "ACTUAL_COMBINED_LIFECYCLE_ISOLATED",
    }


def main() -> int:
    out = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "contract"
    report: dict[str, object] = {
        "foreign_project_on_path": D11._confine(),
        "mode": mode,
    }
    code = 0
    try:
        D11._install_guards()
        logging.getLogger().addHandler(LOGS)
        work = Path(os.environ["D12_WORK_DIR"])
        (work / "a.txt").write_text("synthetic", encoding="utf-8")
        report["guard_checks"] = D11._guard_self_check(work)
        if not all(report["guard_checks"].values()):  # type: ignore[attr-defined]
            raise RuntimeError("guard self-check failed")
        from forex_bot import database
        from forex_bot import telegram_control as tc

        if mode == "ownership":
            report["cases"] = _ownership(database, tc)
        else:
            import forex_bot.app as appmod

            if mode == "repeated":
                report["cases"] = _repeated(appmod, database, tc)
            else:
                report["cases"] = _contract(appmod, database, tc)
        report["network_after"] = list(D11.NETWORK)
        report["escaped_final"] = D11._threads()
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        code = 1
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
