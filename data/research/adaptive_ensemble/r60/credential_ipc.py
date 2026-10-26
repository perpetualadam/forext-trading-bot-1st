"""One-session credential frame on an anonymous pipe. Nothing is written to disk."""

from __future__ import annotations

import json
import re
from typing import Any

AUTH_SCHEMA = "r59.ipc.1"
MAX_FRAME = 262144
_AUTH_MESSAGE = frozenset(
    {
        "schema",
        "mode",
        "step",
        "prior",
        "session_id",
        "collected_at",
        "document",
        "authorisation",
        "stall",
        "credential",
    }
)
_AUTH_CREDENTIAL = frozenset({"account_id", "token"})
_AUTH_AUTHORISATION = frozenset({"kind", "session_id", "step", "host", "port", "plan_id", "capability"})
_CAPABILITY_RE = re.compile(r"^[0-9a-f]{64}\.[0-9a-f]{64}$")
_TOKEN_CHARS = " \t\r\n/\\?#@:;%"


class IpcRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def encode(message: dict[str, Any]) -> bytes:
    raw = json.dumps(message, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(raw) > MAX_FRAME:
        raise IpcRejected("IPC_TOO_LARGE")
    return raw


def _parse(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_FRAME:
        raise IpcRejected("IPC_TOO_LARGE")
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise IpcRejected("IPC_REJECTED") from None
    try:
        message, end = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError:
        raise IpcRejected("IPC_REJECTED") from None
    if text[end:].strip():
        raise IpcRejected("IPC_SECOND_FRAME")
    if not isinstance(message, dict):
        raise IpcRejected("IPC_REJECTED")
    return message


def _transport() -> Any:
    import importlib.util
    import sys
    from pathlib import Path

    name = "r60_restricted_live_transport"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent / "restricted_live_transport.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _session_gate() -> Any:
    import importlib.util
    import sys
    from pathlib import Path

    name = "r60_live_session_gate"
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


def _token_shape(token: object, *, synthetic: bool) -> str:
    if not isinstance(token, str) or not 16 <= len(token) <= 128 or any(character in token for character in _TOKEN_CHARS):
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    if any(ord(character) < 32 or ord(character) == 127 for character in token):
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    if synthetic and (not token.startswith("SYNTHETIC-") or "NOT-REAL" not in token):
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    return token


def authenticated_frame(
    public: dict[str, Any],
    *,
    account_id: str,
    token: str,
    authorisation: dict[str, Any],
    document: dict[str, Any] | None = None,
    stall: str | None = None,
) -> bytes:
    message: dict[str, Any] = {
        "schema": AUTH_SCHEMA,
        "mode": public["mode"],
        "step": public["step"],
        "prior": public["prior"],
        "session_id": public["session_id"],
        "collected_at": public["collected_at"],
        "credential": {"account_id": account_id, "token": token},
        "authorisation": authorisation,
    }
    if document is not None:
        message["document"] = document
    if stall is not None:
        message["stall"] = stall
    return encode(message)


def _consume_frame(raw: bytes, *, synthetic: bool) -> tuple[dict[str, Any], str, str]:
    message = _parse(raw)
    if set(message) - _AUTH_MESSAGE:
        raise IpcRejected("IPC_REJECTED")
    if message.get("schema") != AUTH_SCHEMA or message.get("step") != "instruments" or message.get("prior") != []:
        raise IpcRejected("IPC_REJECTED")
    expected_mode = "HARNESS_SESSION" if synthetic else "REAL_SESSION"
    if message.get("mode") != expected_mode:
        raise IpcRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
    authorisation = message.get("authorisation")
    if not isinstance(authorisation, dict) or set(authorisation) != _AUTH_AUTHORISATION:
        raise IpcRejected("IPC_REJECTED")
    if authorisation.get("kind") != expected_mode:
        raise IpcRejected("GRANT_REJECTED")
    if authorisation.get("host") != "api-fxtrade.oanda.com" or authorisation.get("port") != 443:
        raise IpcRejected("IPC_REJECTED")
    if authorisation.get("plan_id") != "r59.one-get.1" or authorisation.get("step") != "instruments":
        raise IpcRejected("IPC_REJECTED")
    if authorisation.get("session_id") != message.get("session_id"):
        raise IpcRejected("IPC_REJECTED")
    capability = authorisation.get("capability")
    if not isinstance(capability, str) or _CAPABILITY_RE.fullmatch(capability) is None:
        raise IpcRejected("CAPABILITY_REJECTED")
    if "stall" in message and message["stall"] not in {"hang", "delay-then-hang", "malformed", "exit"}:
        raise IpcRejected("IPC_REJECTED")
    credential = message.get("credential")
    if "credential" not in message:
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    message.pop("credential", None)
    if not isinstance(credential, dict) or set(credential) != _AUTH_CREDENTIAL:
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    token = _token_shape(credential.get("token"), synthetic=synthetic)
    try:
        account_id = _transport().validate_authenticated_account(credential.get("account_id"))
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code == "ACCOUNT_ID_REJECTED" or code == "SYNTHETIC_ACCOUNT_REJECTED":
            raise IpcRejected(code) from None
        raise IpcRejected("IPC_REJECTED") from None
    return message, "Bearer " + token, account_id


def consume_authenticated(raw: bytes) -> tuple[dict[str, Any], str, str]:
    return _consume_frame(raw, synthetic=True)


def consume_real(raw: bytes) -> tuple[dict[str, Any], str, str]:
    _session_gate().assert_real_session()
    if b'"document"' in raw:
        raise IpcRejected("IPC_REJECTED")
    return _consume_frame(raw, synthetic=False)


def prompt_hidden_token(*_args: object, **kwargs: object) -> str:
    gate = _session_gate()
    gate.assert_real_session()
    gate.assert_runtime_authorisation(kwargs.get("grant"), session_id=kwargs.get("session_id"), step=kwargs.get("step"))
    import getpass

    value = getpass.getpass("API token: ")
    return _token_shape(value, synthetic=False)


def prompt_account_id(*_args: object, **kwargs: object) -> str:
    gate = _session_gate()
    gate.assert_real_session()
    gate.assert_runtime_authorisation(kwargs.get("grant"), session_id=kwargs.get("session_id"), step=kwargs.get("step"))
    value = input("Account ID: ")
    try:
        return _transport().validate_authenticated_account(value)
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code == "ACCOUNT_ID_REJECTED" or code == "SYNTHETIC_ACCOUNT_REJECTED":
            raise IpcRejected(code) from None
        raise IpcRejected("ACCOUNT_ID_REJECTED") from None


def read_environment(*_args: object, **_kwargs: object) -> None:
    raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")


def read_dotenv(*_args: object, **_kwargs: object) -> None:
    raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")


def contains_exact(text: str, secrets: tuple[str, ...]) -> bool:
    if not isinstance(text, str):
        return True
    lowered = text.lower()
    if "bearer " in lowered or "authorization:" in lowered:
        return True
    for secret in secrets:
        if isinstance(secret, str) and len(secret) >= 8 and secret in text:
            return True
    return False
