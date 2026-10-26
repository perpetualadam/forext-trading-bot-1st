"""Isolated D.13 runner. Production modules load only after existing guards."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path


def _load_d12():
    path = Path(__file__).with_name("d12_shutdown_contract_runner.py")
    spec = importlib.util.spec_from_file_location("d12_shutdown_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("d12 runner could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D12 = _load_d12()


def _boot(mode: str) -> tuple[object, object, object, dict[str, bool]]:
    D12.D11._install_guards()
    D12.logging.getLogger().addHandler(D12.LOGS)
    work = Path(os.environ["D13_WORK_DIR"])
    (work / "a.txt").write_text("synthetic", encoding="utf-8")
    checks = D12.D11._guard_self_check(work)
    if not all(checks.values()):
        raise RuntimeError("guard self-check failed")
    from forex_bot import database
    from forex_bot import telegram_control as tc

    appmod = None
    if mode != "ownership":
        import forex_bot.app as appmod
    return database, tc, appmod, checks


def _extra(appmod: object, database: object, tc: object) -> dict[str, object]:
    appmod._d12_tasks = D12._prepare(appmod)  # type: ignore[attr-defined]

    async def run() -> dict[str, object]:
        os.environ["TELEGRAM_COMMANDS"] = "0"
        disabled = await D12._enter(
            appmod,
            phase="",
            rewrite="valid",
            block=False,
            database=database,
            tc=tc,
        )
        os.environ["TELEGRAM_COMMANDS"] = "1"
        real_start = tc.start_telegram_control

        def raising_start() -> None:
            raise RuntimeError("injected telegram start failure")

        D12._arm(database, tc, block=False)
        D12._safety("valid")
        tc.start_telegram_control = raising_start  # type: ignore[attr-defined]
        start_escaped = ""
        try:
            async with appmod.lifespan(appmod.app):  # type: ignore[attr-defined]
                pass
        except Exception as exc:  # noqa: BLE001
            start_escaped = type(exc).__name__
        start_failed = D12._snapshot(appmod, database, tc)
        start_failed["escaped_type"] = start_escaped
        tc.start_telegram_control = real_start  # type: ignore[attr-defined]
        start_failed["harness"] = D12.D11._contain(tc)
        start_failed["harness_closed"] = D12.D11._harness_close(database)

        real_stop = tc.stop_telegram_control

        def unknown_stop() -> str:
            real_stop()
            return "NOT_A_DOCUMENTED_STATUS"

        D12._arm(database, tc, block=False)
        D12._safety("valid")
        tc.stop_telegram_control = unknown_stop  # type: ignore[attr-defined]
        unknown_escaped = ""
        try:
            async with appmod.lifespan(appmod.app):  # type: ignore[attr-defined]
                pass
        except Exception as exc:  # noqa: BLE001
            unknown_escaped = type(exc).__name__
        unknown = D12._snapshot(appmod, database, tc)
        unknown["escaped_type"] = unknown_escaped
        tc.stop_telegram_control = real_stop  # type: ignore[attr-defined]
        unknown["harness"] = D12.D11._contain(tc)
        unknown["harness_closed"] = D12.D11._harness_close(database)
        return {
            "disabled": disabled,
            "start_failed": start_failed,
            "unknown_stop": unknown,
        }

    return asyncio.run(run())


def main() -> int:
    out = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "contract"
    report: dict[str, object] = {
        "foreign_project_on_path": D12.D11._confine(),
        "mode": mode,
    }
    code = 0
    try:
        database, tc, appmod, checks = _boot(mode)
        report["guard_checks"] = checks
        if mode == "ownership":
            report["cases"] = D12._ownership(database, tc)
        elif mode == "repeated":
            report["cases"] = D12._repeated(appmod, database, tc)
        elif mode == "extra":
            report["cases"] = _extra(appmod, database, tc)
        else:
            report["cases"] = D12._contract(appmod, database, tc)
        report["network_after"] = list(D12.D11.NETWORK)
        report["escaped_final"] = D12.D11._threads()
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        code = 1
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
