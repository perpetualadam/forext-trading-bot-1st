"""Isolated D.14 runner. Production modules load only after existing guards."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from current_lifecycle_fixtures import fresh_live_worker


def _load_d12():
    path = Path(__file__).with_name("d12_shutdown_contract_runner.py")
    spec = importlib.util.spec_from_file_location("d12_shutdown_runner_d14", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("d12 runner could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D12 = _load_d12()
D11 = D12.D11


def _boot(import_app: bool) -> tuple[object, object, object, dict[str, bool]]:
    D11._install_guards()
    D12.logging.getLogger().addHandler(D12.LOGS)
    work = Path(os.environ["D14_WORK_DIR"])
    (work / "a.txt").write_text("synthetic", encoding="utf-8")
    checks = D11._guard_self_check(work)
    if not all(checks.values()):
        raise RuntimeError("guard self-check failed")
    from forex_bot import database
    from forex_bot import telegram_control as tc

    appmod = None
    if import_app:
        import forex_bot.app as appmod
    return database, tc, appmod, checks


def _queries() -> int:
    return len(D11.QUERIES)


def _direct(tc: object) -> dict[str, object]:
    results: list[object] = []
    os.environ["TELEGRAM_COMMANDS"] = "0"
    disabled = tc.start_telegram_control()
    results.append(disabled)
    disabled_threads = D11._threads()
    os.environ["TELEGRAM_COMMANDS"] = "1"
    started = tc.start_telegram_control()
    results.append(started)
    already = tc.start_telegram_control()
    results.append(already)
    healthy_event = tc._stop_event.is_set()
    healthy_threads = len(D11._threads())
    D11._contain(tc)

    D11.BLOCK_POLLS = 20
    D11.RELEASE_POLL.clear()
    D11.IN_POLL.clear()
    blocked_start = tc.start_telegram_control()
    results.append(blocked_start)
    if not D11.IN_POLL.wait(5):
        raise TimeoutError("blocked poller did not enter the fake poll")
    blocked_worker = tc._poller_thread
    stopped = D11._stop_timed(tc)
    before_queries = _queries()
    refused = tc.start_telegram_control()
    results.append(refused)
    refused_view = {
        "result": refused,
        "threads": len(D11._threads()),
        "ident": getattr(tc._poller_thread, "ident", None),
        "same_ident": tc._poller_thread is blocked_worker,
        "stop_event": tc._stop_event.is_set(),
        "query_delta": _queries() - before_queries,
        "stop": stopped,
    }
    D11.BLOCK_POLLS = 0
    D11.RELEASE_POLL.set()
    exited = D11._join_named("telegram-control", 3)
    D11.FIRST_POLL.clear()
    D11.IN_POLL.clear()
    replaced = tc.start_telegram_control()
    results.append(replaced)
    replaced_fresh = fresh_live_worker(blocked_worker, tc._poller_thread)
    D11._contain(tc)

    concurrent: list[object] = []
    barrier = threading.Barrier(2)

    def _go() -> None:
        barrier.wait(3)
        concurrent.append(tc.start_telegram_control())

    left = threading.Thread(target=_go, name="d14-start-a")
    right = threading.Thread(target=_go, name="d14-start-b")
    left.start()
    right.start()
    left.join(4)
    right.join(4)
    concurrent_threads = len(D11._threads())
    results.extend(concurrent)
    D11._contain(tc)

    D11.BLOCK_POLLS = 20
    D11.RELEASE_POLL.clear()
    D11.IN_POLL.clear()
    overlap_start = tc.start_telegram_control()
    if not D11.IN_POLL.wait(5):
        raise TimeoutError("overlap poller did not enter the fake poll")
    overlap_stop: dict[str, object] = {}

    def _stop() -> None:
        overlap_stop["value"] = tc.stop_telegram_control()

    stopper = threading.Thread(target=_stop, name="d14-stop")
    stopper.start()
    deadline = time.perf_counter() + 2
    while time.perf_counter() < deadline and not tc._stop_event.is_set():
        threading.Event().wait(0.01)
    overlap_refused = tc.start_telegram_control()
    results.append(overlap_refused)
    overlap_event = tc._stop_event.is_set()
    overlap_threads = len(D11._threads())
    stopper.join(4)
    D11.BLOCK_POLLS = 0
    D11.RELEASE_POLL.set()
    D11._contain(tc)

    real_start = threading.Thread.start

    def failing_start(self: threading.Thread) -> None:
        if self.name == "telegram-control":
            raise RuntimeError("injected thread start failure")
        real_start(self)

    threading.Thread.start = failing_start  # type: ignore[method-assign]
    try:
        failed = tc.start_telegram_control()
    finally:
        threading.Thread.start = real_start  # type: ignore[method-assign]
    results.append(failed)
    failed_stored = tc._poller_thread is None

    def interrupting_start(self: threading.Thread) -> None:
        if self.name == "telegram-control":
            raise KeyboardInterrupt
        real_start(self)

    threading.Thread.start = interrupting_start  # type: ignore[method-assign]
    propagated = False
    try:
        tc.start_telegram_control()
    except KeyboardInterrupt:
        propagated = True
    finally:
        threading.Thread.start = real_start  # type: ignore[method-assign]
    recovered = tc.start_telegram_control()
    results.append(recovered)
    harness = D11._contain(tc)
    return {
        "disabled": disabled,
        "disabled_threads": disabled_threads,
        "started": started,
        "already": already,
        "healthy_event": healthy_event,
        "healthy_threads": healthy_threads,
        "blocked_start": blocked_start,
        "refused": refused_view,
        "worker_exit": exited,
        "replaced": replaced,
        "replaced_fresh": replaced_fresh,
        "concurrent": concurrent,
        "concurrent_threads": concurrent_threads,
        "overlap_start": overlap_start,
        "overlap_refused": overlap_refused,
        "overlap_event": overlap_event,
        "overlap_threads": overlap_threads,
        "overlap_stop": overlap_stop.get("value"),
        "failed": failed,
        "failed_stored_cleared": failed_stored,
        "keyboard_propagated": propagated,
        "recovered": recovered,
        "none_results": [item for item in results if item is None],
        "harness": harness,
        "evidence": "ACTUAL_TELEGRAM_FUNCTION_ISOLATED",
    }


def _warning_count(text: str) -> int:
    return text.count("D12-START-01")


def _lifespan(appmod: object, database: object, tc: object) -> dict[str, object]:
    appmod._d12_tasks = D12._prepare(appmod)  # type: ignore[attr-defined]
    seen: list[object] = []
    real = tc.start_telegram_control

    def recording_start() -> object:
        value = real()
        seen.append(value)
        return value

    async def run() -> dict[str, object]:
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        os.environ["TELEGRAM_COMMANDS"] = "0"
        D12.LOGS.lines.clear()
        disabled = await D12._enter(
            appmod,
            phase="",
            rewrite="valid",
            block=False,
            database=database,
            tc=tc,
        )
        disabled_warnings = _warning_count("\n".join(D12.LOGS.lines))
        os.environ["TELEGRAM_COMMANDS"] = "1"
        tc.start_telegram_control = recording_start  # type: ignore[attr-defined]
        D12.LOGS.lines.clear()
        normal = await D12._enter(
            appmod,
            phase="",
            rewrite="valid",
            block=False,
            database=database,
            tc=tc,
        )
        normal_warnings = _warning_count("\n".join(D12.LOGS.lines))
        D11.BLOCK_POLLS = 20
        D11.RELEASE_POLL.clear()
        D11.IN_POLL.clear()
        D12.LOGS.lines.clear()
        seen.clear()
        yielded_a = False
        async with appmod.lifespan(appmod.app):  # type: ignore[attr-defined]
            yielded_a = True
            await asyncio.to_thread(D11.IN_POLL.wait, 5)
        snap_a = D12._snapshot(appmod, database, tc)
        worker_a = tc._poller_thread
        D12.LOGS.lines.clear()
        yielded_b = False
        escaped_b = ""
        try:
            async with appmod.lifespan(appmod.app):  # type: ignore[attr-defined]
                yielded_b = True
        except Exception as exc:  # noqa: BLE001
            escaped_b = type(exc).__name__
        snap_b = D12._snapshot(appmod, database, tc)
        worker_b = tc._poller_thread
        refusal_text = "\n".join(D12.LOGS.lines)
        D11.BLOCK_POLLS = 0
        D11.RELEASE_POLL.set()
        exited = D11._join_named("telegram-control", 3)
        D11.FIRST_POLL.clear()
        D12.LOGS.lines.clear()
        yielded_c = False
        snap_c: dict[str, object] = {}
        async with appmod.lifespan(appmod.app):  # type: ignore[attr-defined]
            yielded_c = True
            await asyncio.to_thread(D11.FIRST_POLL.wait, 5)
            snap_c = D12._snapshot(appmod, database, tc)
            fresh_worker = fresh_live_worker(worker_a, tc._poller_thread)
        third_warnings = _warning_count("\n".join(D12.LOGS.lines))
        snap_c_after = D12._snapshot(appmod, database, tc)
        tc.start_telegram_control = real  # type: ignore[attr-defined]
        harness = D11._contain(tc)

        real_thread_start = threading.Thread.start

        def failing_start(self: threading.Thread) -> None:
            if self.name == "telegram-control":
                raise RuntimeError("injected thread start failure")
            real_thread_start(self)

        threading.Thread.start = failing_start  # type: ignore[method-assign]
        D12.LOGS.lines.clear()
        failed_escaped = ""
        failed_yielded = False
        try:
            async with appmod.lifespan(appmod.app):  # type: ignore[attr-defined]
                failed_yielded = True
        except Exception as exc:  # noqa: BLE001
            failed_escaped = type(exc).__name__
        finally:
            threading.Thread.start = real_thread_start  # type: ignore[method-assign]
        failed_text = "\n".join(D12.LOGS.lines)
        failed_snap = D12._snapshot(appmod, database, tc)
        failed_harness = D11._contain(tc)

        def unknown_start() -> str:
            return "NOT_A_DOCUMENTED_START"

        tc.start_telegram_control = unknown_start  # type: ignore[attr-defined]
        D12.LOGS.lines.clear()
        unknown_escaped = ""
        unknown_yielded = False
        try:
            async with appmod.lifespan(appmod.app):  # type: ignore[attr-defined]
                unknown_yielded = True
        except Exception as exc:  # noqa: BLE001
            unknown_escaped = type(exc).__name__
        unknown_text = "\n".join(D12.LOGS.lines)
        unknown_snap = D12._snapshot(appmod, database, tc)
        tc.start_telegram_control = real  # type: ignore[attr-defined]
        return {
            "disabled": disabled,
            "disabled_warnings": disabled_warnings,
            "normal": normal,
            "normal_warnings": normal_warnings,
            "seen": list(seen),
            "yielded_a": yielded_a,
            "snap_a": snap_a,
            "yielded_b": yielded_b,
            "escaped_b": escaped_b,
            "snap_b": snap_b,
            "same_worker": worker_b is worker_a,
            "refusal_logged": "D12-START-01" in refusal_text,
            "refusal_phrase": "previous polling worker remains alive" in refusal_text,
            "worker_exit": exited,
            "yielded_c": yielded_c,
            "snap_c": snap_c,
            "snap_c_after": snap_c_after,
            "third_warnings": third_warnings,
            "fresh_worker": fresh_worker,
            "connection_reused": snap_a["connection_id"] == snap_b["connection_id"],
            "failed_yielded": failed_yielded,
            "failed_escaped": failed_escaped,
            "failed_phrase": "trading continues" in failed_text,
            "failed_refusal": "D12-START-01" in failed_text,
            "failed_snap": failed_snap,
            "failed_harness": failed_harness,
            "unknown_yielded": unknown_yielded,
            "unknown_escaped": unknown_escaped,
            "unknown_phrase": "unrecognised status" in unknown_text,
            "unknown_snap": unknown_snap,
            "harness": harness,
            "evidence": "ACTUAL_LIFESPAN_ISOLATED",
        }

    return asyncio.run(run())


def main() -> int:
    out = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "direct"
    report: dict[str, object] = {
        "foreign_project_on_path": D11._confine(),
        "mode": mode,
    }
    code = 0
    try:
        database, tc, appmod, checks = _boot(mode != "direct" and mode != "ownership")
        report["guard_checks"] = checks
        if mode == "direct":
            report["cases"] = _direct(tc)
        elif mode == "ownership":
            report["cases"] = D12._ownership(database, tc)
        elif mode == "shutdown":
            report["cases"] = D12._contract(appmod, database, tc)
        else:
            report["cases"] = _lifespan(appmod, database, tc)
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
