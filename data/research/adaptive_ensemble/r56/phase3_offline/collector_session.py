"""Offline collector session. Summary must validate before pricing is attempted.

Phase 2 adapters are loaded by file path. This module does not import forex_bot.
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
PHASE2 = HERE.parent / "phase2_offline"
LOG_DIR = HERE / "synthetic_logs"
SCHEMA_VERSION = "r56.phase3.1"
COMPLETE = "SESSION_COMPLETE_SYNTHETIC"
INCOMPLETE = "SESSION_INCOMPLETE"

_TOP = frozenset(
    {
        "schema_version",
        "collected_at",
        "data_source",
        "session_id",
        "summary_request",
        "pricing_request",
        "account_diagnostics",
        "pricing_diagnostics",
        "missing_evidence",
        "validation_warnings",
        "session_status",
        "error_code",
        "executable_order",
        "order_payload",
        "quote_freshness",
        "gbp_pip_value",
        "stake_to_unit_mapping",
        "financing",
        "pip_location",
        "executable_position_size",
        "strategy_profitability",
        "gbp_conversion_fallback",
        "home_conversion_request",
        "phase2_adapters",
    }
)
_REQUEST = frozenset(
    {
        "sequence",
        "method",
        "scheme",
        "host",
        "port",
        "endpoint",
        "query",
        "result",
        "body",
        "redirects",
        "retries",
        "stream",
    }
)


def _load(directory: Path, prefix: str, stem: str) -> Any:
    name = f"{prefix}_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, directory / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _phase2(stem: str) -> Any:
    return _load(PHASE2, "r56p2", stem)


def _local(stem: str) -> Any:
    return _load(HERE, "r56p3", stem)


def new_session_id() -> str:
    return "r56-" + uuid.uuid4().hex


def run_synthetic(
    transport: Any,
    *,
    session_id: str | None = None,
    log_dir: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Run summary then pricing. Write one session record and return it."""
    session = session_id or new_session_id()
    collected = _now(clock)
    warnings: list[str] = []
    secrets: set[str] = set()
    summary_result = _not_sent(1, "/v3/accounts/{accountID}/summary")
    pricing_result = _not_sent(2, "/v3/accounts/{accountID}/pricing")
    account_diag: Any = "NOT_PRODUCED"
    pricing_diag: Any = "NOT_PRODUCED"
    error = "NONE"
    status = INCOMPLETE

    offline = _local("offline_transport")
    if type(transport) is not offline.SyntheticTransport or transport.classification != "SYNTHETIC_TRANSPORT":
        error = "TRANSPORT_NOT_SYNTHETIC"
        return _publish(
            _record(
                collected=collected,
                session=session,
                summary_result=summary_result,
                pricing_result=pricing_result,
                account_diag=account_diag,
                pricing_diag=pricing_diag,
                warnings=warnings,
                status=status,
                error=error,
            ),
            secrets,
            log_dir,
        )

    plan = _local("readonly_request_plan")
    gate = _local("readonly_request_gate")
    prior: list[str] = []
    try:
        approved_summary = gate.approve(plan.summary_candidate(), step=1, prior=prior)
        summary_doc = transport.execute(approved_summary)
    except gate.GateRejected as exc:
        error = exc.code
        summary_result = _rejected(1, plan.SUMMARY_PATTERN)
        return _publish(_base(collected, session, summary_result, pricing_result, account_diag, pricing_diag, warnings, error), secrets, log_dir)
    except offline.OfflineTransportRejected as exc:
        error = exc.code
        summary_result = _rejected(1, plan.SUMMARY_PATTERN)
        return _publish(_base(collected, session, summary_result, pricing_result, account_diag, pricing_diag, warnings, error), secrets, log_dir)
    except Exception:
        error = "EXCEPTION_CONTAINED"
        warnings.append("exception_contained")
        summary_result = _rejected(1, plan.SUMMARY_PATTERN)
        return _publish(_base(collected, session, summary_result, pricing_result, account_diag, pricing_diag, warnings, error), secrets, log_dir)

    prior.append("summary")
    summary_result = _accepted(approved_summary, 1)
    account_body, account_secrets = _phase2("account_diagnostics").build(summary_doc)
    secrets |= account_secrets
    account_diag = _stamp(account_body, session, collected)
    warnings.extend(account_diag.get("validation_warnings") or [])
    if account_diag.get("outcome") != "DIAGNOSTIC_RECORDED":
        error = "SUMMARY_REJECTED"
        summary_result["result"] = "REJECTED"
        pricing_result = _not_sent(2, plan.PRICING_PATTERN)
        return _publish(_base(collected, session, summary_result, pricing_result, account_diag, "NOT_PRODUCED", warnings, error), secrets, log_dir)

    try:
        approved_pricing = gate.approve(plan.pricing_candidate(), step=2, prior=prior)
        pricing_doc = transport.execute(approved_pricing)
    except gate.GateRejected as exc:
        error = exc.code
        pricing_result = _rejected(2, plan.PRICING_PATTERN)
        return _publish(_base(collected, session, summary_result, pricing_result, account_diag, "NOT_PRODUCED", warnings, error), secrets, log_dir)
    except offline.OfflineTransportRejected as exc:
        error = exc.code
        pricing_result = _rejected(2, plan.PRICING_PATTERN)
        return _publish(_base(collected, session, summary_result, pricing_result, account_diag, "NOT_PRODUCED", warnings, error), secrets, log_dir)
    except Exception:
        error = "EXCEPTION_CONTAINED"
        warnings.append("exception_contained")
        pricing_result = _rejected(2, plan.PRICING_PATTERN)
        return _publish(_base(collected, session, summary_result, pricing_result, account_diag, "NOT_PRODUCED", warnings, error), secrets, log_dir)

    pricing_result = _accepted(approved_pricing, 2)
    price_bodies, price_secrets = _phase2("pricing_diagnostics").build(pricing_doc)
    secrets |= price_secrets
    pricing_diag = [_stamp(body, session, collected) for body in price_bodies]
    for item in pricing_diag:
        warnings.extend(item.get("validation_warnings") or [])
    if not pricing_diag or any(item.get("outcome") != "DIAGNOSTIC_RECORDED" for item in pricing_diag):
        error = "PRICING_REJECTED"
        pricing_result["result"] = "REJECTED"
        return _publish(_base(collected, session, summary_result, pricing_result, account_diag, pricing_diag, warnings, error), secrets, log_dir)

    status = COMPLETE
    error = "NONE"
    return _publish(_base(collected, session, summary_result, pricing_result, account_diag, pricing_diag, warnings, error, status=status), secrets, log_dir)


def _stamp(body: dict, session: str, collected: str) -> dict:
    return _phase2("diagnostic_writer").stamp(
        body,
        data_source="SYNTHETIC_TEST_ONLY",
        session_id=session,
        collected_at=collected,
    )


def _base(
    collected: str,
    session: str,
    summary_result: dict,
    pricing_result: dict,
    account_diag: Any,
    pricing_diag: Any,
    warnings: list[str],
    error: str,
    *,
    status: str = INCOMPLETE,
    internal: bool = False,
) -> dict[str, Any]:
    missing = [
        "QUOTE_FRESHNESS_NOT_VERIFIED",
        "GBP_PIP_VALUE_UNVERIFIED",
        "STAKE_TO_UNIT_MAPPING_NOT_VERIFIED",
        "FINANCING_NOT_VERIFIED",
        "PIP_LOCATION_NOT_ESTABLISHED",
    ]
    if isinstance(account_diag, dict) and account_diag.get("home_currency") == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED":
        missing.append("ACCOUNT_HOME_CURRENCY_API_UNVERIFIED")
    if pricing_diag == "NOT_PRODUCED" or _conversion_missing(pricing_diag):
        missing.append("HOME_CONVERSION_NOT_VERIFIED")
    record = {
        "schema_version": SCHEMA_VERSION,
        "collected_at": collected,
        "data_source": "SYNTHETIC_TEST_ONLY",
        "session_id": session,
        "summary_request": summary_result,
        "pricing_request": pricing_result,
        "account_diagnostics": account_diag,
        "pricing_diagnostics": pricing_diag,
        "missing_evidence": missing,
        "validation_warnings": _unique(warnings),
        "session_status": status,
        "error_code": error,
        "executable_order": "NOT_PRODUCED",
        "order_payload": "NOT_PRODUCED",
        "quote_freshness": "QUOTE_FRESHNESS_NOT_VERIFIED",
        "gbp_pip_value": "GBP_PIP_VALUE_UNVERIFIED",
        "stake_to_unit_mapping": "STAKE_TO_UNIT_MAPPING_NOT_VERIFIED",
        "financing": "FINANCING_NOT_VERIFIED",
        "pip_location": "NOT_ESTABLISHED",
        "executable_position_size": "NOT_CALCULATED",
        "strategy_profitability": "NOT_ESTABLISHED",
        "gbp_conversion_fallback": "NOT_USED",
        "home_conversion_request": "NOT_REQUESTED",
        "phase2_adapters": "REUSED",
    }
    if set(record) != _TOP or set(summary_result) != _REQUEST or set(pricing_result) != _REQUEST:
        if internal:
            raise GatePathRejected("ALLOWLIST_REJECTED")
        return _blocked(collected, session)
    return record


def _conversion_missing(pricing_diag: Any) -> bool:
    if not isinstance(pricing_diag, list):
        return True
    return any(item.get("home_conversion") == "HOME_CONVERSION_NOT_VERIFIED" for item in pricing_diag)


def _publish(record: dict, secrets: set[str], log_dir: Path | None) -> dict:
    text = json.dumps(record, indent=2, sort_keys=True)
    plan = _local("readonly_request_plan")
    if _leaks(text, secrets) or plan.SYNTHETIC_ACCOUNT_ID in text:
        record = _blocked(record["collected_at"], record["session_id"])
        text = json.dumps(record, indent=2, sort_keys=True)
    if record["session_status"] == COMPLETE and record["error_code"] != "NONE":
        record = _blocked(record["collected_at"], record["session_id"])
        text = json.dumps(record, indent=2, sort_keys=True)
    path = _allocate(_log_dir(log_dir), record["session_id"])
    path.write_text(text + "\n", encoding="utf-8")
    return record


def _blocked(collected: str, session: str) -> dict:
    return _base(
        collected,
        session,
        _not_sent(1, "/v3/accounts/{accountID}/summary"),
        _not_sent(2, "/v3/accounts/{accountID}/pricing"),
        "NOT_PRODUCED",
        "NOT_PRODUCED",
        ["sensitive_output_blocked"],
        "SENSITIVE_OUTPUT_BLOCKED",
        internal=True,
    )


def _accepted(approved: dict, sequence: int) -> dict:
    return {
        "sequence": sequence,
        "method": "GET",
        "scheme": "https",
        "host": approved["host"],
        "port": 443,
        "endpoint": approved["endpoint"],
        "query": approved["query"],
        "result": "SYNTHETIC_RESPONSE_ACCEPTED",
        "body": "NONE",
        "redirects": False,
        "retries": 0,
        "stream": False,
    }


def _rejected(sequence: int, endpoint: str) -> dict:
    plan = _local("readonly_request_plan")
    return {
        "sequence": sequence,
        "method": "GET",
        "scheme": "https",
        "host": plan.HOST,
        "port": 443,
        "endpoint": endpoint,
        "query": {},
        "result": "REJECTED",
        "body": "NONE",
        "redirects": False,
        "retries": 0,
        "stream": False,
    }


def _not_sent(sequence: int, endpoint: str) -> dict:
    row = _rejected(sequence, endpoint)
    row["result"] = "NOT_SENT"
    return row


def _log_dir(path: Path | None) -> Path:
    target = LOG_DIR if path is None else Path(path)
    resolved = target.resolve()
    root = HERE.resolve()
    try:
        resolved.relative_to(root / "synthetic_logs")
    except ValueError:
        raise GatePathRejected("LOG_PATH_OUTSIDE") from None
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _allocate(log_dir: Path, session_id: str) -> Path:
    token = session_id.replace("-", "")
    for number in range(1, 10000):
        path = log_dir / f"r56-phase3-{token}-{number:04d}.json"
        try:
            handle = path.open("x", encoding="utf-8")
        except FileExistsError:
            continue
        handle.close()
        return path
    raise GatePathRejected("LOG_NAME_EXHAUSTED")


def _leaks(text: str, secrets: set[str]) -> bool:
    if "Bearer " in text or "SYNTHETIC-TOKEN" in text or "1.35" in text:
        return True
    return any(secret and secret in text for secret in secrets)


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _now(clock: Callable[[], datetime] | None) -> str:
    moment = clock() if clock is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class GatePathRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
