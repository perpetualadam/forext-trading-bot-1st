"""Read-only live-safety document inspection. Never overwrites an existing file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from forex_bot.live_safety import (
    AUTH_ALLOWED,
    AUTH_BLOCKED,
    KNOWN_STRATEGY_NAMES,
    _blank_document,
    _validate_document,
    state_path,
)


def inspect_safety_state_file(path: Path | None = None) -> dict[str, Any]:
    """Inspect a safety-state document. Never writes, never repairs, never prints secrets."""
    target = Path(path) if path is not None else state_path()
    report: dict[str, Any] = {
        "path": str(target),
        "present": target.is_file(),
        "schema_version": None,
        "structurally_valid": False,
        "persisted_authorisation": None,
        "strategy_names_present": [],
        "strategies": [],
        "any_strategy_active": False,
        "any_strategy_authorised_for_live": False,
        "safe_for_trading_disabled_startup": True,
        "notes": [],
    }
    if not target.is_file():
        report["notes"].append("missing_file_startup_will_fail_closed_blocked")
        return report
    try:
        raw = target.read_text(encoding="utf-8-sig")
        blob = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError):
        report["notes"].append("unreadable_or_corrupt_startup_will_fail_closed_blocked")
        return report
    if isinstance(blob, dict):
        try:
            report["schema_version"] = int(blob.get("schema_version") or 0)
        except (TypeError, ValueError):
            report["schema_version"] = None
    validated = _validate_document(blob)
    if validated is None:
        report["notes"].append("invalid_or_unsupported_schema_startup_will_fail_closed_blocked")
        return report
    report["structurally_valid"] = True
    raw_auth = validated.get("live_order_authorisation")
    auth: dict[str, Any] = raw_auth if isinstance(raw_auth, dict) else {}
    persisted = str(auth.get("state") or "").strip().upper()
    report["persisted_authorisation"] = persisted if persisted in (AUTH_BLOCKED, AUTH_ALLOWED) else None
    raw_rows = validated.get("strategies")
    rows: dict[str, Any] = raw_rows if isinstance(raw_rows, dict) else {}
    report["strategy_names_present"] = sorted(str(k) for k in rows)
    details = []
    for name in KNOWN_STRATEGY_NAMES:
        raw_row = rows.get(name)
        row: dict[str, Any] = raw_row if isinstance(raw_row, dict) else {}
        active = bool(row.get("active"))
        authorised = bool(row.get("authorised_for_live"))
        details.append(
            {
                "name": name,
                "active": active,
                "authorised_for_live": authorised,
                "disable_reason": row.get("disable_reason"),
            }
        )
        if active:
            report["any_strategy_active"] = True
        if authorised:
            report["any_strategy_authorised_for_live"] = True
    report["strategies"] = details
    if persisted == AUTH_ALLOWED:
        report["notes"].append(
            "persisted_allowed_is_historical_only_effective_runtime_starts_blocked"
        )
    report["safe_for_trading_disabled_startup"] = True
    return report


def write_blocked_startup_document(path: Path) -> Path:
    """Create a BLOCKED document only if ``path`` does not already exist. Never overwrites."""
    target = Path(path)
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing safety-state file: {target}")
    doc = _blank_document(reason="operator_preflight_blocked")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return target


def _print_report(report: dict[str, Any]) -> None:
    print(f"path={report.get('path')}")
    print(f"present={report.get('present')}")
    print(f"schema_version={report.get('schema_version')}")
    print(f"structurally_valid={report.get('structurally_valid')}")
    print(f"persisted_authorisation={report.get('persisted_authorisation')}")
    print(f"strategy_names={report.get('strategy_names_present')}")
    print(f"any_strategy_active={report.get('any_strategy_active')}")
    print(f"any_strategy_authorised_for_live={report.get('any_strategy_authorised_for_live')}")
    print(f"safe_for_trading_disabled_startup={report.get('safe_for_trading_disabled_startup')}")
    for note in report.get("notes") or []:
        print(f"note={note}")
    for row in report.get("strategies") or []:
        print(
            f"strategy={row.get('name')} active={row.get('active')} "
            f"authorised_for_live={row.get('authorised_for_live')} "
            f"disable_reason={row.get('disable_reason') or 'none'}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only live-safety state inspection")
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Safety-state JSON path (default LIVE_SAFETY_STATE_PATH or data/ops/live_safety_state.json)",
    )
    args = parser.parse_args(argv)
    target = Path(args.path) if args.path else state_path()
    _print_report(inspect_safety_state_file(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
