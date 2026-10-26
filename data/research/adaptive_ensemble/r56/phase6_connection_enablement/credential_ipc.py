"""One-session credential frame on an anonymous pipe. Nothing is written to disk."""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA = "r56.phase6.ipc.1"
AUTH_SCHEMA = "r56.phase6.ipc.2"
AUTH_MODE = "AUTHENTICATED_HARNESS"
MAX_FRAME = 262144
_MESSAGE = frozenset(
    {
        "schema",
        "mode",
        "step",
        "prior",
        "session_id",
        "collected_at",
        "fixture",
        "status",
        "body_text",
        "fill",
        "stall",
        "ignore_seconds",
        "request_deadline",
        "tls_policy",
        "proxy_from_environment",
        "pricing_bid",
        "credential",
    }
)
_CREDENTIAL = frozenset({"classification", "account_selector", "marker"})
_AUTH_MESSAGE = frozenset(
    {
        "schema",
        "mode",
        "step",
        "prior",
        "session_id",
        "collected_at",
        "fixture",
        "credential",
        "authorisation",
        "status",
        "body_text",
        "fill",
        "stall",
        "ignore_seconds",
    }
)
_AUTH_CREDENTIAL = frozenset({"account_id", "token"})
_AUTH_AUTHORISATION = frozenset({"kind", "session_id", "step", "host", "port", "plan_id", "capability"})
_CAPABILITY_RE = re.compile(r"^[0-9a-f]{64}\.[0-9a-f]{64}$")


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


def consume(raw: bytes) -> tuple[dict[str, Any], str]:
    """Return the public job and a header. The marker is not retained in the job."""
    message = _parse(raw)
    if set(message) - _MESSAGE:
        raise IpcRejected("IPC_REJECTED")
    if message.get("schema") != SCHEMA:
        raise IpcRejected("IPC_REJECTED")
    if message.get("mode") != "OFFLINE_TEST":
        raise IpcRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
    credential = message.pop("credential", None)
    if not isinstance(credential, dict) or set(credential) != _CREDENTIAL:
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    marker = credential.get("marker")
    accepted = (
        credential.get("classification") == "SYNTHETIC_TEST_ONLY"
        and credential.get("account_selector") == "SYNTHETIC_PIN"
        and isinstance(marker, str)
        and marker.startswith("SYNTHETIC-")
        and "NOT-REAL" in marker
        and " " not in marker
        and "\n" not in marker
        and "\r" not in marker
    )
    del credential
    if not accepted or not isinstance(marker, str):
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    header = "Bearer " + marker
    del marker
    if "credential" in message or "marker" in message:
        raise IpcRejected("IPC_REJECTED")
    return message, header


def authenticated_frame(
    public: dict[str, Any],
    *,
    account_id: str,
    token: str,
    authorisation: dict[str, Any] | None = None,
    status: int | None = None,
    stall: str | None = None,
    ignore_seconds: float | None = None,
    ipc_mode: str | None = None,
) -> bytes:
    """Build one IPC frame. The caller must not write it to disk."""
    selected = AUTH_MODE if ipc_mode is None else ipc_mode
    if selected not in {AUTH_MODE, "REAL_SESSION"}:
        raise IpcRejected("MODE_MISMATCH")
    if isinstance(authorisation, dict):
        kind = authorisation.get("kind")
        if selected == "REAL_SESSION" and kind != "REAL_SESSION":
            raise IpcRejected("MODE_MISMATCH")
        if selected == AUTH_MODE and kind not in {None, "HARNESS_SESSION"}:
            raise IpcRejected("MODE_MISMATCH")
    message: dict[str, Any] = {
        "schema": AUTH_SCHEMA,
        "mode": selected,
        "step": public.get("step"),
        "prior": public.get("prior"),
        "session_id": public.get("session_id"),
        "collected_at": public.get("collected_at"),
        "fixture": public.get("fixture"),
        "credential": {"account_id": account_id, "token": token},
    }
    if authorisation is not None:
        message["authorisation"] = authorisation
    if status is not None:
        message["status"] = status
    if stall is not None:
        message["stall"] = stall
        if ignore_seconds is not None:
            message["ignore_seconds"] = ignore_seconds
    return encode(message)


def consume_authenticated(raw: bytes) -> tuple[dict[str, Any], str, str]:
    """Accept one harness frame. Real-session mode is refused before any connection."""
    message = _parse(raw)
    if set(message) - _AUTH_MESSAGE:
        raise IpcRejected("IPC_REJECTED")
    for key in ("schema", "mode", "step", "prior", "session_id", "collected_at", "fixture", "credential"):
        if key not in message:
            raise IpcRejected("IPC_REJECTED")
    if message.get("schema") != AUTH_SCHEMA:
        raise IpcRejected("IPC_REJECTED")
    if message.get("mode") != AUTH_MODE:
        raise IpcRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
    if message.get("step") not in {"summary", "pricing"}:
        raise IpcRejected("IPC_REJECTED")
    prior = message.get("prior")
    if message["step"] == "summary" and prior != []:
        raise IpcRejected("IPC_REJECTED")
    if message["step"] == "pricing" and prior != ["summary"]:
        raise IpcRejected("IPC_REJECTED")
    if any(not isinstance(item, str) for item in prior):
        raise IpcRejected("IPC_REJECTED")
    _check_authorisation(message)
    if "status" in message and (not isinstance(message["status"], int) or isinstance(message["status"], bool)):
        raise IpcRejected("IPC_REJECTED")
    if "stall" in message and message["stall"] not in {"hang", "ignore", "crash"}:
        raise IpcRejected("IPC_REJECTED")
    credential = message.pop("credential", None)
    if not isinstance(credential, dict) or set(credential) != _AUTH_CREDENTIAL:
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    for value in credential.values():
        if isinstance(value, (dict, list)):
            raise IpcRejected("IPC_REJECTED")
    token = _synthetic_token(credential.get("token"))
    try:
        account_id = _transport().validate_authenticated_account(credential.get("account_id"))
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code in {"ACCOUNT_ID_REJECTED", "SYNTHETIC_ACCOUNT_REJECTED"}:
            raise IpcRejected(code) from None
        raise IpcRejected("IPC_REJECTED") from None
    del credential
    header = "Bearer " + token
    del token
    if "credential" in message or "account_id" in message or "token" in message:
        raise IpcRejected("IPC_REJECTED")
    return message, header, account_id


def _synthetic_token(token: object) -> str:
    if (
        isinstance(token, str)
        and 16 <= len(token) <= 128
        and token.startswith("SYNTHETIC-")
        and "NOT-REAL" in token
        and not any(character in token for character in " \t\r\n/\\?#@:%")
        and not any(ord(character) < 32 or ord(character) == 127 for character in token)
    ):
        return token
    raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")


def _transport() -> Any:
    import importlib.util
    import sys
    from pathlib import Path

    name = "r56p6_restricted_live_transport"
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


def contains_exact(text: str, secrets: tuple[str, ...]) -> bool:
    """True when the supplied secret, a bearer form, or an Authorization header is present."""
    if not isinstance(text, str):
        return True
    lowered = text.lower()
    if "bearer " in lowered or "authorization:" in lowered:
        return True
    for secret in secrets:
        if isinstance(secret, str) and len(secret) >= 4 and secret in text:
            return True
    return False


def redact_exact(text: str, secrets: tuple[str, ...]) -> str:
    """Replace each supplied secret with a fixed marker. The original text is not returned."""
    if not isinstance(text, str):
        return "REDACTED"
    redacted = text
    ordered = sorted((secret for secret in secrets if isinstance(secret, str) and len(secret) >= 4), key=len, reverse=True)
    for secret in ordered:
        if secret in redacted:
            redacted = redacted.replace(secret, "REDACTED")
    return redacted


def _check_authorisation(message: dict[str, Any]) -> None:
    if "authorisation" not in message:
        return
    authorisation = message["authorisation"]
    if not isinstance(authorisation, dict) or set(authorisation) != _AUTH_AUTHORISATION:
        raise IpcRejected("IPC_REJECTED")
    for key, value in authorisation.items():
        if isinstance(value, (dict, list)):
            raise IpcRejected("IPC_REJECTED")
        if key == "port":
            if value != 443:
                raise IpcRejected("IPC_REJECTED")
        elif not isinstance(value, str):
            raise IpcRejected("IPC_REJECTED")
    if authorisation["kind"] == "REAL_SESSION":
        raise IpcRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
    if authorisation["kind"] != "HARNESS_SESSION":
        raise IpcRejected("IPC_REJECTED")
    if authorisation["host"] != "api-fxtrade.oanda.com" or authorisation["plan_id"] != "r56.phase6.two-get.1":
        raise IpcRejected("IPC_REJECTED")
    if not isinstance(authorisation.get("capability"), str) or _CAPABILITY_RE.fullmatch(authorisation["capability"]) is None:
        raise IpcRejected("CAPABILITY_REJECTED")
    if authorisation["session_id"] != message.get("session_id") or authorisation["step"] != message.get("step"):
        raise IpcRejected("IPC_REJECTED")


def consume_real(raw: bytes) -> tuple[dict[str, Any], str, str]:
    """Real-session frame. The source switch is checked before the bytes are parsed."""
    _session_gate().assert_real_session()
    message = _parse(raw)
    if message.get("mode") != "REAL_SESSION":
        raise IpcRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
    credential = message.get("credential")
    token = credential.get("token") if isinstance(credential, dict) else ""
    if not isinstance(token, str) or not 16 <= len(token) <= 128 or any(character in token for character in " \t\r\n/\\?#@:%"):
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    account_id = _transport().validate_authenticated_account(credential.get("account_id") if isinstance(credential, dict) else None)
    message.pop("credential", None)
    return message, "Bearer " + token, account_id


def _session_gate() -> Any:
    import importlib.util
    import sys
    from pathlib import Path

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


def prompt_hidden_token(*_args: object, **kwargs: object) -> str:
    """Hidden token prompt. Both gates run before getpass, and the value is not logged."""
    gate = _session_gate()
    gate.assert_real_session()
    gate.assert_runtime_authorisation(kwargs.get("grant"), session_id=kwargs.get("session_id"), step=kwargs.get("step"))
    import getpass

    value = getpass.getpass("API token: ")
    if not isinstance(value, str) or not 16 <= len(value) <= 128 or any(character in value for character in " \t\r\n/\\?#@:;%"):
        raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    return value


def prompt_account_id(*_args: object, **kwargs: object) -> str:
    """Terminal account-id prompt. Both gates run before input, and the value is not logged."""
    gate = _session_gate()
    gate.assert_real_session()
    gate.assert_runtime_authorisation(kwargs.get("grant"), session_id=kwargs.get("session_id"), step=kwargs.get("step"))
    value = input("Account ID: ")
    try:
        return _transport().validate_authenticated_account(value)
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code in {"ACCOUNT_ID_REJECTED", "SYNTHETIC_ACCOUNT_REJECTED"}:
            raise IpcRejected(code) from None
        raise IpcRejected("ACCOUNT_ID_REJECTED") from None


def read_environment(*_args: object, **_kwargs: object) -> None:
    raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")


def read_dotenv(*_args: object, **_kwargs: object) -> None:
    raise IpcRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
