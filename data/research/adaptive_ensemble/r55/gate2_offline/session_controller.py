"""Offline session sequence. The CLI cannot activate a network connection.

run_test_session is a test entry. It accepts only the synthetic provider and an offline double.
It is not a sandbox and it is not a Gate 3 activation path.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
DISABLED = "R55 Gate 2 default entry is disabled. No credential prompt. No network connection."
LIVE_SENTENCE = "R55 Gate 2 live entry is disabled. No credential prompt. No network connection."


def _load(stem: str) -> Any:
    name = f"r55g2_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_live() -> int:
    """Inert refusal. This function does not prompt, connect, or read a credential."""
    gate = _load("request_gate")
    raise gate.GateRejected(gate.LIVE_DISABLED)


def launch(argv: list[str] | None = None) -> int:
    """Every launch stays offline. Flags do not call run_live or run_test_session."""
    args = [] if argv is None else list(argv)
    if any(arg.startswith("-") for arg in args):
        print(LIVE_SENTENCE)
        return 2
    print(DISABLED)
    return 0


def _package(
    preview: str,
    confirmation: str,
    credentials_requested: bool,
    constructed: list[str],
    stop: str,
    handle_erased: bool,
    last_elapsed: float | None,
    result: dict[str, Any] | None,
    file_written: bool,
) -> dict[str, Any]:
    return {
        "preview": preview,
        "confirmation": confirmation,
        "credentials_requested": credentials_requested,
        "connections_constructed": len(constructed),
        "kinds": list(constructed),
        "stop": stop,
        "handle_erased": handle_erased,
        "last_elapsed": last_elapsed,
        "result": result,
        "file_written": file_written,
    }


def run_test_session(
    factory_for_kind: Callable[[str], object],
    provider: object,
    confirm: Callable[[str], str],
    context: object,
    output_path: Path | None = None,
    per_request: float | None = None,
    session_budget: float | None = None,
    time_fn: Callable[[], float] | None = None,
    cancel: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """Run the offline sequence. Shorter budgets are allowed. Longer budgets are rejected."""
    gate = _load("request_gate")
    transport = _load("https_transport")
    evidence = _load("evidence_writer")
    creds = _load("credential_boundary")
    evidence.retire(output_path)
    preview = creds.preview_text()
    answer = confirm(preview)
    if answer != creds.CONFIRM:
        result = evidence.document(0, 0, 0, [], [], gate.PER_REQUEST_TIMEOUT_SECONDS, gate.TOTAL_SESSION_DEADLINE_SECONDS)
        return _package(preview, "REFUSED", False, [], "CONFIRMATION_REFUSED", True, None, result, False)
    if not isinstance(provider, creds.SyntheticProvider):
        raise gate.GateRejected(gate.REJECTED)
    per = gate.PER_REQUEST_TIMEOUT_SECONDS if per_request is None else per_request
    budget = gate.TOTAL_SESSION_DEADLINE_SECONDS if session_budget is None else session_budget
    clock = gate.SessionClock(per, budget, time_fn)
    clock.start_session()
    if cancel is not None and cancel("before_credentials"):
        result = evidence.document(0, 0, 0, [], [], per, budget)
        return _package(preview, "ACCEPTED", False, [], "CANCELLED", True, None, result, False)
    handle = provider.issue()
    constructed: list[str] = []
    try:
        if cancel is not None and cancel("before_first_request"):
            result = evidence.document(0, 0, 0, [], [], per, budget)
            return _package(preview, "ACCEPTED", True, constructed, "CANCELLED", True, None, result, False)
        account_id = handle.account_id()
        token = handle.token()
        planned = gate.plan_two(account_id)
        for item in planned:
            gate.validate_description(item, account_id)
        attempted = 0
        http_ok = 0
        validated = 0
        results: list[dict[str, str]] = []
        instruments: list[dict[str, str]] | None = None
        prices: list[dict[str, str]] | None = None
        last_elapsed: float | None = None
        stop = "NONE"
        for index, kind in enumerate(("instruments", "pricing")):
            if index == 1 and cancel is not None and cancel("between_requests"):
                stop = "CANCELLED"
                break
            try:
                clock.ensure_session()
            except gate.GateRejected as exc:
                stop = exc.classification
                results.append(evidence.endpoint_result(kind, "FAILURE", exc.classification, "NONE"))
                break
            description = planned[index]
            started = time.monotonic()
            try:
                def _one_factory(bound_kind: str = kind) -> object:
                    constructed.append(bound_kind)
                    return factory_for_kind(bound_kind)

                status, raw = transport.execute_description(
                    _one_factory,
                    description,
                    account_id,
                    token,
                    clock,
                    context,
                )
            except gate.GateRejected as exc:
                last_elapsed = time.monotonic() - started
                stop = exc.classification
                attempted = len(constructed)
                http_status = str(exc.detail.get("http_status", "NONE"))
                if http_status == "200":
                    http_ok += 1
                results.append(evidence.endpoint_result(kind, "FAILURE", exc.classification, http_status, exc.detail))
                break
            attempted += 1
            try:
                payload = evidence.parse_body(raw)
                produced = (
                    evidence.validate_instruments(payload)
                    if kind == "instruments"
                    else evidence.validate_pricing(payload, instruments or [])
                )
            except gate.GateRejected as exc:
                http_ok += 1
                stop = exc.classification
                results.append(evidence.endpoint_result(kind, "FAILURE", exc.classification, "200", exc.detail))
                break
            http_ok += 1
            validated += 1
            results.append(evidence.endpoint_result(kind, "SUCCESS", "NONE", str(status)))
            if kind == "instruments":
                instruments = produced
            else:
                prices = produced
        rows: list[dict[str, str]] = []
        if validated == 2 and instruments is not None and prices is not None:
            by_name = {row["instrument"]: row for row in instruments}
            for price in prices:
                merged = dict(by_name[price["instrument"]])
                merged.update(price)
                rows.append(merged)
        result = evidence.document(attempted, http_ok, validated, results, rows, per, budget)
        written = evidence.write_success(output_path, result)
        return _package(preview, "ACCEPTED", True, constructed, stop, True, last_elapsed, result, written)
    finally:
        handle.erase()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
