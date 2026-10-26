"""Synthetic credential boundary. Real token input is not implemented.

A GET-only client does not make a token read-only. Token permission stays UNKNOWN.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONFIRM = "CONFIRM PREVIEW"
ACCOUNT = "SYNTHETIC-ACCOUNT-R55G2-NOT-REAL"
TOKEN = "SYNTHETIC-TOKEN-R55G2-NOT-REAL"
HIDDEN_INPUT = "NOT_IMPLEMENTED_GATE2"


def _gate() -> Any:
    name = "r55g2_request_gate"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / "request_gate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CredentialHandle:
    """Memory-only handle. Its text form does not contain the secret values."""

    __slots__ = ("_account", "_token", "_synthetic")

    def __init__(self, account_id: str, token: str, synthetic: bool) -> None:
        self._account = account_id
        self._token = token
        self._synthetic = synthetic

    def __str__(self) -> str:
        return "REDACTED"

    def __repr__(self) -> str:
        return "CredentialHandle(REDACTED)"

    def erase(self) -> None:
        self._account = ""
        self._token = ""
        self._synthetic = False

    def account_id(self) -> str:
        if not self._synthetic or self._account == "":
            raise _gate().GateRejected(_gate().REJECTED)
        return self._account

    def token(self) -> str:
        if not self._synthetic or self._token == "":
            raise _gate().GateRejected(_gate().REJECTED)
        return self._token


def preview_text() -> str:
    """Fixed host and endpoint preview. It contains no account identifier and no token."""
    return "\n".join(
        (
            "R55 Gate 2 request preview",
            "Host: api-fxtrade.oanda.com",
            "Port: 443",
            "Method: GET",
            "Request 1: /v3/accounts/{accountID}/instruments",
            "Request 2: /v3/accounts/{accountID}/pricing",
            "Pricing query: includeHomeConversions=true",
            "Token permission: UNKNOWN",
            "A GET-only client does not make the token read-only. The token may be allowed to trade.",
            "Account summary: NOT AUTHORISED",
            "Orders, trades, and positions: NOT AUTHORISED",
            "Live connection: NOT AUTHORISED",
            "Confirmation required: CONFIRM PREVIEW",
        )
    )


def hidden_input_available() -> bool:
    """Future hidden entry is designed and deliberately unavailable in Gate 2."""
    return False


def read_real_credential() -> None:
    """Real prompts are not executable in this stage."""
    raise _gate().GateRejected(_gate().REAL_CREDENTIAL_INPUT_NOT_AUTHORISED)


class SyntheticProvider:
    """Offline provider. It returns the fixed synthetic pair and nothing else."""

    def __init__(self) -> None:
        self.calls = 0
        self.handle: CredentialHandle | None = None

    def issue(self) -> CredentialHandle:
        self.calls += 1
        self.handle = CredentialHandle(ACCOUNT, TOKEN, True)
        return self.handle
