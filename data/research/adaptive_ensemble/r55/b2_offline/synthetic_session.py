"""Offline-only B2 candidate. There is no live transport and no credential reader."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
LIVE_DISABLED = "R55B2_LIVE_DISABLED"
REJECTED = "R55B2_REJECTED"
SYNTHETIC = "SYNTHETIC_TEST_ONLY"


class Rejected(RuntimeError):
    """Fail closed. The message is a fixed code."""


def _load(stem: str) -> Any:
    name = f"r55b2_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = HERE / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


plan = _load("request_plan")
check = _load("response_validation")
fixtures = _load("synthetic_fixtures")


def run_live() -> int:
    """Inert refusal. This function does not prompt, connect, or read a credential."""
    raise Rejected(LIVE_DISABLED)


def _output_target(path: Path | None) -> Path | None:
    if path is None:
        return None
    resolved = path.resolve()
    if resolved.parent != HERE:
        raise Rejected(REJECTED)
    return resolved


def _retire(path: Path | None) -> None:
    target = _output_target(path)
    if target is not None and target.is_file():
        target.unlink()


def _guard(blob: str) -> None:
    banned = (
        fixtures.FIXTURE_ACCOUNT_ID,
        fixtures.FIXTURE_TOKEN,
        "Bearer",
        "Authorization",
        "https://",
        "ACCOUNT_VERIFIED",
        "1.35",
    )
    if any(secret in blob for secret in banned):
        raise Rejected(REJECTED)


def _document(attempted: int, http_ok: int, validated: int, results: list[dict[str, str]], rows: list[dict[str, str]]) -> dict[str, Any]:
    missing = "NONE"
    if validated != 2:
        missing = "NOT_VALIDATED"
    elif any("NOT_RETURNED" in row.values() or row.get("conversion_state") in {"NOT_RETURNED", "AMBIGUOUS", "PARTIAL"} for row in rows):
        missing = "NOT_RETURNED"
    document = {
        "evidence_class": SYNTHETIC,
        "account_specific_api_evidence": "NOT_PRODUCED",
        "authentication": "NOT_PERFORMED",
        "account_verified": "NO",
        "broker_pricing": "SYNTHETIC_FIXTURE",
        "live_connection": "DISABLED",
        "requests_planned": 2,
        "requests_attempted": attempted,
        "successful_http_responses": http_ok,
        "validated_sanitised_responses": validated,
        "endpoint_order": ["instruments", "pricing"],
        "endpoint_results": results,
        "rows": rows,
        "missing_field_status": missing,
        "account_home_currency": "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED",
        "gbp_conversion_suitability": "NOT_VERIFIED",
        "spread_bet_stake_map": "NOT_VERIFIED",
        "gbp_pip_value": "NOT_VERIFIED",
        "financing": "NOT_VERIFIED",
        "token_permissions": "UNKNOWN",
        "executable_trade_sizing": "NOT_CALCULATED",
        "strategy_profitability": "NOT_ESTABLISHED",
        "quote_staleness_rule": "NOT_DEFINED",
        "option_b_account_summary": "NOT_AUTHORISED",
        "per_request_timeout_seconds": plan.PER_REQUEST_TIMEOUT_SECONDS,
        "total_session_deadline_seconds": plan.TOTAL_SESSION_DEADLINE_SECONDS,
        "timeout_enforcement": "NOT_IMPLEMENTED_OFFLINE",
    }
    blob = json.dumps(document)
    _guard(blob)
    return document


def _endpoint(kind: str, result: str, classification: str, http_status: str, detail: dict[str, str] | None = None) -> dict[str, str]:
    row = {
        "endpoint": kind,
        "result": result,
        "error_classification": classification,
        "http_status": http_status,
        "evidence_class": SYNTHETIC,
    }
    if detail:
        field = detail.get("field", "")
        instrument = detail.get("instrument", "")
        allowed_fields = {
            "instruments",
            "instrument",
            "name",
            "pipLocation",
            "price",
            "bid_ask",
            "prices",
            "missing_instrument",
            "missing_price",
            "unexpected_instrument",
            "duplicate_instrument",
            "time",
            "tradeable",
            "homeConversions",
            "conversion",
            "spread",
        }
        if field in allowed_fields:
            row["field"] = field
        if isinstance(instrument, str) and len(instrument) == 7 and instrument[3] == "_" and instrument.isupper():
            row["instrument"] = instrument
    return row


def _apply(kind: str, status: int, raw: bytes, instruments: list[dict[str, str]] | None) -> list[dict[str, str]]:
    code = check.classify_status(status)
    if code is not None:
        raise check.Failure(code)
    payload = check.parse_body(raw)
    if kind == "instruments":
        return check.validate_instruments(payload)
    if instruments is None:
        raise check.Failure("SCHEMA_REJECTED", {"field": "instruments"})
    return check.validate_pricing(payload, instruments)


def _run(steps: list[Callable[[], tuple[int, bytes]]], output_path: Path | None) -> dict[str, Any]:
    _retire(output_path)
    planned = plan.plan_two(fixtures.FIXTURE_ACCOUNT_ID)
    for item in planned:
        plan.validate_description(item, fixtures.FIXTURE_ACCOUNT_ID)
    attempted = 0
    http_ok = 0
    validated = 0
    results: list[dict[str, str]] = []
    instruments: list[dict[str, str]] | None = None
    prices: list[dict[str, str]] | None = None
    for index, kind in enumerate(("instruments", "pricing")):
        status, raw = steps[index]()
        attempted += 1
        try:
            produced = _apply(kind, status, raw, instruments)
        except check.Failure as exc:
            if exc.classification.startswith("HTTP_"):
                http_status = str(status)
            else:
                http_status = "200"
                http_ok += 1
            results.append(_endpoint(kind, "FAILURE", exc.classification, http_status, exc.detail))
            break
        http_ok += 1
        validated += 1
        results.append(_endpoint(kind, "SUCCESS", "NONE", "200"))
        if kind == "instruments":
            instruments = produced
        else:
            prices = produced
    rows = []
    if validated == 2 and instruments is not None and prices is not None:
        by_name = {row["instrument"]: row for row in instruments}
        for price in prices:
            merged = dict(by_name[price["instrument"]])
            merged.update(price)
            rows.append(merged)
    document = _document(attempted, http_ok, validated, results, rows)
    target = _output_target(output_path)
    if target is not None and document["validated_sanitised_responses"] == 2:
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    return {"confirmed": False, "credentials_requested": False, "result": document, "planned": planned}


def run_offline(output_path: Path | None = None) -> dict[str, Any]:
    """Run the built-in fixtures only. No transport argument is accepted."""
    destination = HERE / "synthetic_output.json" if output_path is None else output_path
    package = _run(
        [lambda: (200, fixtures.instruments_bytes()), lambda: (200, fixtures.pricing_bytes())],
        destination,
    )
    result = package["result"]
    print(result["requests_attempted"])
    print(result["successful_http_responses"])
    print(result["validated_sanitised_responses"])
    print(result["evidence_class"])
    return package


def run_test_case(responses: list[tuple[int, bytes]], output_path: Path | None = None) -> dict[str, Any]:
    """Test-only synthetic records. Not a sandbox. launch and run_offline do not call this.

    A class, marker, or transport object is rejected and is not constructed.
    """
    if isinstance(responses, type) or not isinstance(responses, list):
        raise Rejected(REJECTED)
    if any(isinstance(item, type) for item in responses):
        raise Rejected(REJECTED)
    if len(responses) < 1:
        raise Rejected(REJECTED)

    def step(pair: tuple[int, bytes]) -> Callable[[], tuple[int, bytes]]:
        def read() -> tuple[int, bytes]:
            status, raw = pair
            if not isinstance(status, int) or isinstance(status, bool) or not isinstance(raw, (bytes, bytearray)):
                raise Rejected(REJECTED)
            return status, bytes(raw)
        return read

    steps = [step(responses[0])]
    if len(responses) > 1:
        steps.append(step(responses[1]))
    else:
        def missing() -> tuple[int, bytes]:
            raise Rejected(REJECTED)
        steps.append(missing)
    return _run(steps, output_path)


def run_session(mode: str = "offline", connection_class: Any = None, output_path: Path | None = None) -> dict[str, Any]:
    """Normal entry. Any live mode or injected class is rejected before use."""
    if mode != "offline" or connection_class is not None:
        raise Rejected(LIVE_DISABLED)
    return run_offline(output_path)


def launch(argv: list[str] | None = None) -> int:
    """No arguments stays disabled. Only an exact offline argument runs fixtures."""
    args = [] if argv is None else list(argv)
    if args == ["--live"]:
        print("R55 B2 live entry is disabled. No credential prompt. No network connection.")
        return 2
    if args == ["--offline"]:
        run_offline()
        return 0
    print("R55 B2 default entry is disabled. No credential prompt. No network connection.")
    return 0


def main(argv: list[str] | None = None) -> int:
    return launch(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
