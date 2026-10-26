"""One-use activation permit for a future real diagnostic session.

A local file stops a second launch, a restart, and a concurrent second process
from using the same permission. It does not stop a person who can write this
directory. The trust boundary is the operator account on this computer.

The source switch is still required. This module does not turn that switch on.
prepare() refuses while the switch is off and does not create a permit.
Normal diagnostic execution calls consume() only, and only after that switch
has already passed. Tests may point consume() at a temporary directory.
They must not write the production permit.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROGRAM_ID = "r56.phase6.real_session_entry"
SCHEMA = "r56.phase6.activation.1"
PERMIT_NAME = "one_session.permit"
CONSUMED_NAME = "one_session.consumed"
_FIELDS = ("schema", "program", "plan_id", "host", "port", "requests", "methods")


class ActivationRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def production_directory() -> Path:
    return Path(__file__).resolve().parent / "real_activation"


def _gate() -> Any:
    import importlib.util
    import sys

    name = "r56p6_live_session_gate"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent / "live_session_gate.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def expected_binding() -> dict[str, Any]:
    plan = _gate().fixed_plan()
    return {
        "schema": SCHEMA,
        "program": PROGRAM_ID,
        "plan_id": plan["plan_id"],
        "host": plan["host"],
        "port": plan["port"],
        "requests": list(plan["requests"]),
        "methods": list(plan["methods"]),
    }


def _matches(payload: object) -> bool:
    if not isinstance(payload, dict) or set(payload) != set(_FIELDS):
        return False
    expected = expected_binding()
    return all(payload.get(field) == expected[field] for field in _FIELDS)


def prepare() -> Path:
    """Create the production permit. The source switch is checked before any file is created."""
    _gate().assert_real_session()
    target = production_directory()
    target.mkdir(parents=True, exist_ok=True)
    permit = target / PERMIT_NAME
    marker = target / CONSUMED_NAME
    if marker.exists() or permit.exists():
        raise ActivationRejected("ACTIVATION_PRESENT")
    payload = json.dumps(expected_binding(), sort_keys=True).encode("utf-8")
    fd = os.open(str(permit), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    return permit


def consume(directory: Path | None = None) -> None:
    """Spend a permit. Failure leaves it spent. A missing permit is not created."""
    target = production_directory() if directory is None else Path(directory)
    marker = target / CONSUMED_NAME
    permit = target / PERMIT_NAME
    if marker.exists():
        raise ActivationRejected("ACTIVATION_CONSUMED")
    if not permit.is_file():
        raise ActivationRejected("ACTIVATION_ABSENT")
    try:
        fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ActivationRejected("ACTIVATION_CONSUMED") from None
    try:
        try:
            payload = json.loads(permit.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ActivationRejected("ACTIVATION_REJECTED") from None
        if not _matches(payload):
            raise ActivationRejected("ACTIVATION_REJECTED")
        os.write(fd, b"CONSUMED\n")
        try:
            permit.unlink()
        except OSError:
            pass
    finally:
        os.close(fd)
