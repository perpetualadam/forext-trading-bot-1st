"""Write allowlisted diagnostic JSON under this directory only.

The default entry processes local synthetic fixtures. Activation flags are rejected.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
LOG_DIR = HERE / "synthetic_logs"
SCHEMA_VERSION = "r56.phase2.1"
DISABLED = "R56 phase 2 diagnostic entry is offline. No credential prompt. No network connection."

_COMMON = frozenset(
    {
        "schema_version",
        "collected_at",
        "data_source",
        "session_id",
        "record_kind",
        "outcome",
        "missing_evidence",
        "validation_warnings",
        "executable_order",
    }
)
_ACCOUNT = _COMMON | frozenset(
    {
        "account_id_present",
        "account_id_logged",
        "home_currency",
        "home_currency_source",
        "home_currency_is_gbp",
        "account_type",
        "account_type_source",
        "balance",
        "balance_source",
        "nav",
        "nav_source",
        "margin_available",
        "margin_available_source",
        "margin_used",
        "margin_used_source",
        "margin_used_operational_capture",
        "unrealised_pl",
        "unrealised_pl_source",
        "unrealised_pl_operational_capture",
        "account_reporting_timestamp",
        "account_reporting_timestamp_source",
        "account_identity_verified",
    }
)
_PRICING = _COMMON | frozenset(
    {
        "instrument",
        "instrument_source",
        "bid",
        "bid_source",
        "ask",
        "ask_source",
        "bid_levels",
        "ask_levels",
        "spread_price",
        "spread_price_source",
        "spread_pips",
        "spread_pips_reason",
        "quote_timestamp",
        "quote_timestamp_source",
        "quote_freshness",
        "tradeable",
        "tradeable_source",
        "status",
        "closeout_bid",
        "closeout_ask",
        "home_conversion",
        "home_conversion_operational_request",
    }
)
_SIZING = _COMMON | frozenset(
    {
        "instrument",
        "instrument_source",
        "proposed_api_units",
        "proposed_api_units_source",
        "stop_distance",
        "stop_distance_source",
        "risk_budget",
        "risk_budget_source",
        "account_currency",
        "account_currency_source",
        "conversion_inputs",
        "calculated_pip_value",
        "calculated_pip_value_source",
        "gbp_pip_value_status",
        "margin_estimate",
        "margin_estimate_source",
        "stake_to_unit_mapping",
        "sizing_formula_status",
        "order_payload",
    }
)
_FAILURE = _COMMON | frozenset({"error_code", "order_payload"})
_ALLOWED = {
    "account_summary": _ACCOUNT,
    "pricing": _PRICING,
    "sizing": _SIZING,
    "failure": _FAILURE,
}
_REJECTED_FLAGS = ("--live", "--connect", "--authenticate", "--account")


def _load(stem: str) -> Any:
    name = f"r56p2_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def new_session_id() -> str:
    return "r56-" + uuid.uuid4().hex


def contain_exception() -> dict[str, Any]:
    """Fixed failure record. The exception text is not read."""
    return {
        "record_kind": "failure",
        "outcome": "REJECTED",
        "error_code": "EXCEPTION_CONTAINED",
        "missing_evidence": ["exception_text_not_logged"],
        "validation_warnings": ["exception_contained"],
        "executable_order": "NOT_PRODUCED",
        "order_payload": "NOT_PRODUCED",
    }


def stamp(
    body: dict[str, Any],
    *,
    data_source: str,
    session_id: str,
    collected_at: str,
) -> dict[str, Any]:
    adapter = _load("response_adapter")
    if data_source not in adapter.DATA_SOURCES:
        body = {
            "record_kind": "failure",
            "outcome": "REJECTED",
            "error_code": "INVALID_CLASSIFICATION",
            "missing_evidence": ["data_source"],
            "validation_warnings": ["invalid_classification"],
            "executable_order": "NOT_PRODUCED",
        }
        data_source = adapter.SYNTHETIC_TEST_ONLY
    if not isinstance(session_id, str) or not session_id.startswith("r56-") or len(session_id) != 36:
        body = {
            "record_kind": "failure",
            "outcome": "REJECTED",
            "error_code": "SESSION_ID_REJECTED",
            "missing_evidence": ["session_id"],
            "validation_warnings": ["session_id_rejected"],
            "executable_order": "NOT_PRODUCED",
        }
        session_id = new_session_id()
    record = {
        "schema_version": SCHEMA_VERSION,
        "collected_at": collected_at,
        "data_source": data_source,
        "session_id": session_id,
    }
    record.update(body)
    allowed = _ALLOWED[record["record_kind"]]
    if set(record) - allowed:
        return {
            "schema_version": SCHEMA_VERSION,
            "collected_at": collected_at,
            "data_source": data_source,
            "session_id": session_id,
            "record_kind": "failure",
            "outcome": "REJECTED",
            "error_code": "ALLOWLIST_REJECTED",
            "missing_evidence": ["allowlist"],
            "validation_warnings": ["allowlist_rejected"],
            "executable_order": "NOT_PRODUCED",
        }
    return record


def write_record(
    record: dict[str, Any],
    *,
    sensitive: set[str],
    log_dir: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Path | None:
    """Write one record. A secret in the payload blocks the write."""
    target = _log_dir(log_dir)
    text = json.dumps(record, indent=2, sort_keys=True)
    if _leaks(text, sensitive) or record.get("account_id_logged") is True:
        blocked = stamp(
            contain_exception(),
            data_source=str(record.get("data_source") or "SYNTHETIC_TEST_ONLY"),
            session_id=str(record.get("session_id") or new_session_id()),
            collected_at=_now(clock),
        )
        blocked["error_code"] = "SENSITIVE_OUTPUT_BLOCKED"
        text = json.dumps(blocked, indent=2, sort_keys=True)
        record = blocked
    if record.get("outcome") == "DIAGNOSTIC_RECORDED" and record.get("record_kind") == "failure":
        return None
    path = _allocate(target, str(record["session_id"]), str(record["record_kind"]))
    path.write_text(text + "\n", encoding="utf-8")
    return path


def write_documents(
    kind: str,
    document: Any,
    *,
    data_source: str = "SYNTHETIC_TEST_ONLY",
    session_id: str | None = None,
    log_dir: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> list[Path]:
    collected = _now(clock)
    session = session_id or new_session_id()
    bodies, sensitive = _bodies(kind, document)
    written: list[Path] = []
    for body in bodies:
        record = stamp(body, data_source=data_source, session_id=session, collected_at=collected)
        path = write_record(record, sensitive=sensitive, log_dir=log_dir, clock=clock)
        if path is not None:
            written.append(path)
    return written


def write_exception(
    exc: BaseException,
    *,
    session_id: str | None = None,
    log_dir: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Path | None:
    """Record that an exception was contained. exc is accepted and not stringified."""
    del exc
    session = session_id or new_session_id()
    record = stamp(
        contain_exception(),
        data_source="SYNTHETIC_TEST_ONLY",
        session_id=session,
        collected_at=_now(clock),
    )
    return write_record(record, sensitive=set(), log_dir=log_dir, clock=clock)


def launch(argv: list[str] | None = None, *, log_dir: Path | None = None) -> int:
    """Process local synthetic fixtures, or reject an activation argument."""
    args = list(sys.argv[1:] if argv is None else argv)
    if _rejected(args):
        print(DISABLED)
        return 2
    fixtures = _load("synthetic_fixtures")
    session = new_session_id()
    write_documents("account", fixtures.account_document(), session_id=session, log_dir=log_dir)
    write_documents("pricing", fixtures.pricing_document(), session_id=session, log_dir=log_dir)
    write_documents("sizing", fixtures.sizing_document(), session_id=session, log_dir=log_dir)
    print(DISABLED)
    return 0


def _bodies(kind: str, document: Any) -> tuple[list[dict[str, Any]], set[str]]:
    if kind == "account":
        body, sensitive = _load("account_diagnostics").build(document)
        return [body], sensitive
    if kind == "pricing":
        return _load("pricing_diagnostics").build(document)
    if kind == "sizing":
        body, sensitive = _load("sizing_diagnostics").build(document)
        return [body], sensitive
    if kind == "json":
        parsed, error = _load("response_adapter").loads_object(document)
        if error:
            return [
                {
                    "record_kind": "failure",
                    "outcome": "REJECTED",
                    "error_code": error,
                    "missing_evidence": ["json"],
                    "validation_warnings": [error.lower()],
                    "executable_order": "NOT_PRODUCED",
                }
            ], set()
        return _bodies("account", parsed)
    return [
        {
            "record_kind": "failure",
            "outcome": "REJECTED",
            "error_code": "REJECTED_DOCUMENT",
            "missing_evidence": ["kind"],
            "validation_warnings": ["rejected_document"],
            "executable_order": "NOT_PRODUCED",
        }
    ], set()


def _rejected(args: list[str]) -> bool:
    if not args:
        return False
    for arg in args:
        name = arg.split("=", 1)[0]
        if name in _REJECTED_FLAGS or name.startswith("-") and name != "--synthetic":
            return True
        if not arg.startswith("-"):
            return True
    return False


def _log_dir(path: Path | None) -> Path:
    target = LOG_DIR if path is None else Path(path)
    resolved = target.resolve()
    root = HERE.resolve()
    if resolved != root and root not in resolved.parents:
        raise DiagnosticPathRejected("LOG_PATH_OUTSIDE")
    if resolved == root or "synthetic_logs" not in resolved.parts:
        raise DiagnosticPathRejected("LOG_PATH_OUTSIDE")
    try:
        resolved.relative_to(root / "synthetic_logs")
    except ValueError:
        raise DiagnosticPathRejected("LOG_PATH_OUTSIDE") from None
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _allocate(log_dir: Path, session_id: str, kind: str) -> Path:
    safe_session = session_id.replace("-", "")
    for number in range(1, 10000):
        path = log_dir / f"r56-diag-{safe_session}-{kind}-{number:04d}.json"
        try:
            path.touch(exist_ok=False)
        except FileExistsError:
            continue
        return path
    raise DiagnosticPathRejected("LOG_NAME_EXHAUSTED")


def _leaks(text: str, sensitive: set[str]) -> bool:
    for secret in sensitive:
        if secret and secret in text:
            return True
    if "Bearer " in text or "SYNTHETIC-TOKEN" in text:
        return True
    return False


def _now(clock: Callable[[], datetime] | None) -> str:
    moment = clock() if clock is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DiagnosticPathRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
