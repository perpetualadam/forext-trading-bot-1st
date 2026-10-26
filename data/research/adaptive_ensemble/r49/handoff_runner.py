"""R.49 credential handoff. No production imports, no secrets, no network."""

from __future__ import annotations

import getpass
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

NETWORK_EXECUTION = False
PHASE_B_PHRASE = "APPROVE PHASE B"
CLOSED = "R49_NETWORK_GATE_CLOSED"
REJECTED = "R49_INPUT_REJECTED"


class InputRejected(RuntimeError):
    """A secret was missing or refused. The message never contains the secret."""


class NetworkClosed(RuntimeError):
    """A connection was refused before it could start."""


def _gate():
    path = Path(__file__).resolve().parents[1] / "r48" / "readonly_transport.py"
    spec = importlib.util.spec_from_file_location("r48_readonly_transport", path)
    if spec is None or spec.loader is None:
        raise NetworkClosed(CLOSED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prompt_hidden(label: str, reader: Callable[[str], str] | None = None) -> str:
    """Read one secret. The default reader hides typing. This build does not call it."""
    source = reader if reader is not None else getpass.getpass
    value = source(label)
    if not isinstance(value, str) or value == "" or value != value.strip() or "\n" in value or "\r" in value:
        raise InputRejected(REJECTED)
    return value


def require_present(value: str) -> None:
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise InputRejected(REJECTED)


def arm_network(phrase: str) -> None:
    """A confirmation phrase is required, and this build still refuses the connection."""
    if phrase != PHASE_B_PHRASE:
        raise InputRejected(REJECTED)
    if not NETWORK_EXECUTION:
        raise NetworkClosed(CLOSED)
    raise NetworkClosed(CLOSED)


def public_plan() -> dict[str, Any]:
    gate = _gate()
    return {
        "instruments": gate.redacted_request("instruments"),
        "pricing": gate.redacted_request("pricing"),
        "network_execution": NETWORK_EXECUTION,
    }


def _leak_guard(document: dict[str, Any], secrets: tuple[str, ...]) -> dict[str, Any]:
    blob = json.dumps(document)
    for secret in secrets:
        if secret and secret in blob:
            raise InputRejected(REJECTED)
    if "Bearer" in blob or "Authorization" in blob or "https://" in blob:
        raise InputRejected(REJECTED)
    return document


def offline_session(
    account_id: str,
    token: str,
    instrument_payload: dict[str, Any],
    price_payload: dict[str, Any],
) -> dict[str, Any]:
    """Parse injected responses. This does not connect and does not keep the secrets."""
    require_present(account_id)
    require_present(token)
    gate = _gate()
    gate.assert_request("GET", gate.ALLOWED_HOST, gate.build_path("instruments", account_id), ("instruments",))
    gate.assert_request(
        "GET",
        gate.ALLOWED_HOST,
        gate.build_path("pricing", account_id),
        ("instruments", "includeHomeConversions"),
    )
    instruments = gate.parse_instruments(instrument_payload)
    locations = {
        row["instrument"]: row["pipLocation"]
        for row in instruments
        if row.get("pipLocation") not in (None, "MISSING")
    }
    document = {
        "planned_calls": public_plan(),
        "instruments": instruments,
        "prices": gate.parse_pricing(price_payload, locations),
    }
    return _leak_guard(document, (account_id, token))


def write_sanitised(path: Path, document: dict[str, Any], secrets: tuple[str, ...]) -> None:
    safe = _leak_guard(document, secrets)
    path.write_text(json.dumps(safe, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        print(REJECTED)
        return 2
    print("R49 handoff is prepared. Network gate is closed. No credential prompt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
