"""Isolated D.15 runner. Production modules load only after existing guards."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import traceback
from pathlib import Path


def _load_d14():
    path = Path(__file__).with_name("d14_telegram_start_runner.py")
    spec = importlib.util.spec_from_file_location("d14_runner_d15", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("d14 runner could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D14 = _load_d14()


def _strategies(strategies: object) -> dict[str, bool]:
    names = (
        "scalp",
        "trend",
        "mean_reversion",
        "swing_trend",
        "swing_mean_reversion",
        "swing_breakout",
    )
    return {name: bool(strategies[name].active) for name in names}  # type: ignore[index]


def _safety() -> dict[str, object]:
    from forex_bot.live_safety import (
        _blank_document,
        initialise_fail_closed,
        live_order_auth_state,
        live_safety_initialised,
        operator_set_strategy_active,
        reset_live_safety_for_tests,
        restore_strategy_runtime_defaults_for_tests,
    )
    from forex_bot.strategy_meta import strategies

    path = Path(os.environ["LIVE_SAFETY_STATE_PATH"])
    names = (
        "scalp",
        "trend",
        "mean_reversion",
        "swing_trend",
        "swing_mean_reversion",
        "swing_breakout",
    )

    def load(text: str | None) -> None:
        reset_live_safety_for_tests()
        restore_strategy_runtime_defaults_for_tests()
        if path.exists():
            path.unlink()
        if text is not None:
            path.write_text(text, encoding="utf-8")
        initialise_fail_closed()

    load(json.dumps(_blank_document(reason="operator_preflight_blocked")))
    valid = {
        "initialised": live_safety_initialised(),
        "authorisation": live_order_auth_state(),
        "active": _strategies(strategies),
    }
    document = json.loads(path.read_text(encoding="utf-8"))
    document["future_metadata"] = {"preserve": True}
    path.write_text(json.dumps(document), encoding="utf-8")
    load(path.read_text(encoding="utf-8"))
    preserved = json.loads(path.read_text(encoding="utf-8"))["future_metadata"]
    strategies["scalp"].active = "true"  # type: ignore[attr-defined]
    string_true = strategies["scalp"].active
    unconfirmed = ""
    try:
        operator_set_strategy_active(
            name="trend",
            active=True,
            reason="synthetic",
            operator_confirmed=False,
        )
    except PermissionError as exc:
        unconfirmed = type(exc).__name__
    operator_set_strategy_active(
        name="scalp",
        active=True,
        reason="synthetic-confirmed",
        operator_confirmed=True,
    )
    explicit = strategies["scalp"].active
    operator_set_strategy_active(
        name="scalp",
        active=False,
        reason="synthetic-restore",
        operator_confirmed=True,
    )
    corrupt_before = b"{not-json"
    load("{not-json")
    corrupt = {
        "initialised": live_safety_initialised(),
        "authorisation": live_order_auth_state(),
        "bytes": path.read_bytes(),
        "active": _strategies(strategies),
    }
    future = json.loads(
        json.dumps(_blank_document(reason="operator_preflight_blocked"))
    )
    future["schema_version"] = 99
    future_text = json.dumps(future)
    load(future_text)
    future_row = {
        "initialised": live_safety_initialised(),
        "authorisation": live_order_auth_state(),
        "bytes": path.read_text(encoding="utf-8"),
        "active": _strategies(strategies),
    }
    invalid = {"schema_version": "nope"}
    load(json.dumps(invalid))
    invalid_row = {
        "initialised": live_safety_initialised(),
        "authorisation": live_order_auth_state(),
    }
    reset_live_safety_for_tests()
    restore_strategy_runtime_defaults_for_tests()
    if path.exists():
        path.unlink()
    real_replace = os.replace

    def failing_replace(src: object, dst: object) -> None:
        if Path(str(dst)) == path:
            raise OSError("injected safety replace failure")
        real_replace(src, dst)  # type: ignore[arg-type]

    os.replace = failing_replace  # type: ignore[assignment]
    write_error = ""
    try:
        initialise_fail_closed()
    except OSError as exc:
        write_error = type(exc).__name__
    finally:
        os.replace = real_replace  # type: ignore[assignment]
    write_failure = {
        "escaped": write_error,
        "initialised": live_safety_initialised(),
        "authorisation": live_order_auth_state(),
        "temporary_left": path.with_suffix(path.suffix + ".tmp").exists(),
    }
    return {
        "valid": valid,
        "preserved": preserved,
        "string_true_inactive": string_true is False,
        "unconfirmed": unconfirmed,
        "explicit_true": explicit is True,
        "restored_inactive": all(not strategies[name].active for name in names),
        "corrupt": corrupt,
        "corrupt_bytes_kept": corrupt["bytes"] == corrupt_before,
        "future": future_row,
        "future_bytes_kept": future_row["bytes"] == future_text,
        "invalid": invalid_row,
        "write_failure": write_failure,
        "evidence": "ACTUAL_SOURCE_ISOLATED",
    }


def _telegram_extra(tc: object) -> dict[str, object]:
    d11 = D14.D11
    d11.BLOCK_POLLS = 20
    d11.RELEASE_POLL.clear()
    d11.IN_POLL.clear()
    started = tc.start_telegram_control()
    if not d11.IN_POLL.wait(5):
        raise TimeoutError("repeated-stop poller did not enter the fake poll")
    ident = getattr(tc._poller_thread, "ident", None)
    first = tc.stop_telegram_control()
    second = tc.stop_telegram_control()
    repeated = {
        "started": started,
        "first": first,
        "second": second,
        "same_ident": getattr(tc._poller_thread, "ident", None) == ident,
        "alive": tc._poller_thread is not None and tc._poller_thread.is_alive(),
        "stop_event": tc._stop_event.is_set(),
    }
    results: list[object] = []
    barrier = threading.Barrier(2)

    def _stop() -> None:
        barrier.wait(3)
        results.append(tc.stop_telegram_control())

    left = threading.Thread(target=_stop, name="d15-stop-a")
    right = threading.Thread(target=_stop, name="d15-stop-b")
    left.start()
    right.start()
    left.join(5)
    right.join(5)
    concurrent = {
        "results": results,
        "joined": not left.is_alive() and not right.is_alive(),
        "threads": len(d11._threads()),
        "same_ident": getattr(tc._poller_thread, "ident", None) == ident,
        "alive": tc._poller_thread is not None and tc._poller_thread.is_alive(),
    }
    before_queries = len(d11.QUERIES)
    d11.RAISE_POLL = True
    d11.BLOCK_POLLS = 0
    d11.RELEASE_POLL.set()
    poll_exit = d11._join_named("telegram-control", 3)
    poll_exception = {
        "queries": len(d11.QUERIES) - before_queries,
        "escaped": poll_exit["escaped"],
        "stored_cleared": tc._poller_thread is None,
    }
    d11.RAISE_POLL = False
    d11.PHASE = "query_fails"
    tc._stop_event.clear()
    contained = True
    try:
        reply = tc.cmd_trades()
    except Exception:  # noqa: BLE001
        contained = False
        reply = None
    before_queries = len(d11.QUERIES)
    tc._stop_event.set()
    tc.cmd_trades()
    d11.PHASE = ""
    harness = d11._contain(tc)
    return {
        "repeated_stop": repeated,
        "concurrent_stop": concurrent,
        "poll_exception": poll_exception,
        "database_exception_contained": contained,
        "database_reply": type(reply).__name__ if reply is not None else None,
        "stopped_query_delta": len(d11.QUERIES) - before_queries,
        "harness": harness,
    }


def _database_extra(database: object) -> dict[str, object]:
    d11 = D14.D11
    database._pg_conn = None  # type: ignore[attr-defined]
    database._pg_cursor = None  # type: ignore[attr-defined]
    real_connect = database.psycopg2.connect  # type: ignore[attr-defined]

    def failing_connect(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected connect failure")

    database.psycopg2.connect = failing_connect  # type: ignore[attr-defined]
    try:
        before = database.get_connection()
    finally:
        database.psycopg2.connect = real_connect  # type: ignore[attr-defined]
    before_row = {
        "result_none": before is None,
        "published_connection": database._pg_conn is None,  # type: ignore[attr-defined]
        "published_cursor": database._pg_cursor is None,  # type: ignore[attr-defined]
    }
    database._pg_conn = None  # type: ignore[attr-defined]
    database._pg_cursor = None  # type: ignore[attr-defined]
    real_execute = d11.FakeCursor.execute

    def failing_execute(self: object, _sql: object, _params: object = None) -> None:
        _ = self
        raise RuntimeError("injected init sql failure")

    d11.FakeCursor.execute = failing_execute
    connection_index = len(d11.CONNECTIONS)
    cursor_index = len(d11.CURSORS)
    try:
        after = database.get_connection()
    finally:
        d11.FakeCursor.execute = real_execute
    connections = d11.CONNECTIONS[connection_index:]
    cursors = d11.CURSORS[cursor_index:]
    after_row = {
        "result_none": after is None,
        "published_connection": database._pg_conn is None,  # type: ignore[attr-defined]
        "published_cursor": database._pg_cursor is None,  # type: ignore[attr-defined]
        "connections_closed": (
            bool(connections) and all(item.closed for item in connections)
        ),
        "cursors_closed": bool(cursors) and all(item.closed for item in cursors),
    }
    d11._harness_close(database)
    names = [name for name in dir(database) if "borrow" in name.lower()]
    return {
        "before_cursor": before_row,
        "after_cursor": after_row,
        "borrower_attributes": names,
    }


def main() -> int:
    out = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "lifespan"
    os.environ.setdefault("D14_WORK_DIR", os.environ["D15_WORK_DIR"])
    os.environ.setdefault("D12_WORK_DIR", os.environ["D15_WORK_DIR"])
    report: dict[str, object] = {
        "foreign_project_on_path": D14.D11._confine(),
        "mode": mode,
    }
    code = 0
    try:
        import_app = mode in {"lifespan", "shutdown"}
        database, tc, appmod, checks = D14._boot(import_app)
        report["guard_checks"] = checks
        if mode == "lifespan":
            cases = D14._lifespan(appmod, database, tc)
            tasks = list(getattr(appmod, "_d12_tasks", []))
            cases["owned_pending_after"] = sum(1 for task in tasks if not task.done())
            report["cases"] = cases
        elif mode == "telegram":
            cases = D14._direct(tc)
            cases["extra"] = _telegram_extra(tc)
            report["cases"] = cases
        elif mode == "database":
            cases = D14.D12._ownership(database, tc)
            cases["extra"] = _database_extra(database)
            report["cases"] = cases
        elif mode == "shutdown":
            report["cases"] = D14.D12._contract(appmod, database, tc)
        elif mode == "safety":
            report["cases"] = _safety()
        else:
            raise RuntimeError(f"unknown mode {mode}")
        report["network_after"] = list(D14.D11.NETWORK)
        report["escaped_final"] = D14.D11._threads()
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        code = 1
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
