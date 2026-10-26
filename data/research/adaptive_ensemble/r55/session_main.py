"""R.55 session entry. A normal launch cannot ask for a credential or open a connection."""

from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

PINS = {
    "r51": ("https_adapter.py", "e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef"),
    "r52": ("session_entry.py", "59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56"),
    "r53": ("connector.py", "7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4"),
    "r54": ("session_main.py", "50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280"),
}
LIVE_DISABLED = "R55_LIVE_TRANSPORT_DISABLED"
REJECTED = "R55_REJECTED"
CONFIRM = "CONFIRM PREVIEW"
SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
_PREVIEW_KEYS = (
    "live_session_approved",
    "preview_status",
    "host",
    "port",
    "method",
    "endpoint_order",
    "instruments",
    "maximum_requests",
    "timeout_seconds",
    "certificate_verification",
    "hostname_verification",
    "redirects",
    "retries",
    "trading_actions",
    "credential_permission",
    "account_home_currency",
    "spread_bet_stake_map",
    "executable_size",
)


class LiveTransportDisabled(RuntimeError):
    """No live connection is available from this program."""


class Rejected(RuntimeError):
    """Fail closed. The message is a fixed code."""


class MemoryCredential:
    """In-memory holder. Its text form has no identifier and no token."""

    __slots__ = ("account_id", "token")

    def __init__(self, account_id: str, token: str) -> None:
        self.account_id = account_id
        self.token = token

    def __repr__(self) -> str:
        return "MemoryCredential()"

    def __str__(self) -> str:
        return "MemoryCredential()"


def _stage_file(stage: str, name: str) -> Path:
    return Path(__file__).resolve().parents[1] / stage / name


def prior_hashes() -> dict[str, str]:
    return {
        stage: hashlib.sha256(_stage_file(stage, name).read_bytes()).hexdigest()
        for stage, (name, _pin) in PINS.items()
    }


def require_prior_hashes() -> None:
    found = prior_hashes()
    if any(found[stage] != pin for stage, (_name, pin) in PINS.items()):
        raise SystemExit("R55_PRIOR_HASH_MISMATCH")


def _r53() -> Any:
    require_prior_hashes()
    path = _stage_file("r53", "connector.py")
    spec = importlib.util.spec_from_file_location("r53_connector_r55", path)
    if spec is None or spec.loader is None:
        raise LiveTransportDisabled(LIVE_DISABLED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _live_class(connection_class: Any) -> bool:
    if connection_class is http.client.HTTPSConnection or connection_class is http.client.HTTPConnection:
        return True
    if isinstance(connection_class, type) and issubclass(connection_class, (http.client.HTTPConnection, http.client.HTTPSConnection)):
        return True
    return False


def _require_secret(value: str) -> None:
    if not isinstance(value, str) or value == "" or value != value.strip() or any(ch in value for ch in "/?#& \r\n\t"):
        raise Rejected(REJECTED)


def accept_credentials(account_id: str, token: str) -> MemoryCredential:
    _require_secret(account_id)
    _require_secret(token)
    return MemoryCredential(account_id, token)


def prompt_for_credentials(account_input: Callable[[str], str] | None = None, token_input: Callable[[str], str] | None = None) -> MemoryCredential:
    """Accept injected readers. Calling this without readers does not prompt."""
    if account_input is None or token_input is None:
        raise LiveTransportDisabled(LIVE_DISABLED)
    try:
        account_id = account_input("Account identifier: ")
        token = token_input("API token: ")
    except (LiveTransportDisabled, Rejected):
        raise
    except Exception:
        raise Rejected(REJECTED) from None
    return accept_credentials(account_id, token)


def session_preview() -> dict[str, Any]:
    """Facts that may be shown before a future connection. This is not an approval."""
    preview = {
        "live_session_approved": "NO",
        "preview_status": "NOT_A_CONNECTION",
        "host": "api-fxtrade.oanda.com",
        "port": 443,
        "method": "GET",
        "endpoint_order": ["instruments", "pricing"],
        "instruments": list(SIX),
        "maximum_requests": 2,
        "timeout_seconds": 5,
        "certificate_verification": "ENABLED",
        "hostname_verification": "ENABLED",
        "redirects": "DISABLED",
        "retries": "DISABLED",
        "trading_actions": "PROHIBITED",
        "credential_permission": "UNKNOWN",
        "account_home_currency": "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED",
        "spread_bet_stake_map": "NOT_VERIFIED",
        "executable_size": "NOT_CALCULATED",
    }
    if set(preview) != set(_PREVIEW_KEYS):
        raise Rejected(REJECTED)
    return preview


def render_preview(preview: dict[str, Any]) -> str:
    lines = [
        "Request preview. This is not a connection.",
        "Host: api-fxtrade.oanda.com",
        "Method: GET",
        "Endpoint order: instruments, then pricing",
        "Instruments: " + ", ".join(SIX),
        "Maximum requests: 2",
        "Timeout: 5 seconds per request",
        "Certificate verification: enabled",
        "Hostname verification: enabled",
        "Redirects: disabled",
        "Retries: disabled",
        "Trading actions: prohibited",
        "Token permissions: unknown",
        "Account home currency: not yet API-verified",
        "Spread-bet stake semantics: not yet verified",
        "Type CONFIRM PREVIEW to continue.",
    ]
    text = "\n".join(lines)
    if preview.get("host") != "api-fxtrade.oanda.com" or "https://" in text:
        raise Rejected(REJECTED)
    return text


def _guard(value: Any, secrets: tuple[str, ...]) -> None:
    blob = json.dumps(value)
    for secret in secrets:
        if secret and secret in blob:
            raise Rejected(REJECTED)
    if "Bearer" in blob or "Authorization" in blob or "https://" in blob:
        raise Rejected(REJECTED)


def _cancelled(preview: dict[str, Any]) -> dict[str, Any]:
    return {
        "preview": preview,
        "confirmed": False,
        "credentials_requested": False,
        "result": None,
        "terminated": True,
    }


def future_live_entry(*_args: Any, **_kwargs: Any) -> None:
    """A later hashed program would have to call the session. This function cannot."""
    raise LiveTransportDisabled(LIVE_DISABLED)


def enable_live(**_ignored: Any) -> None:
    raise LiveTransportDisabled(LIVE_DISABLED)


def launch(argv: list[str] | None = None) -> int:
    """Normal entry. Arguments are ignored and are not printed."""
    _ = [] if argv is None else argv
    require_prior_hashes()
    print("R55 session is disabled. No credential prompt. No network connection.")
    return 0


def run_session(
    confirm_input: Callable[[str], str],
    account_input: Callable[[str], str],
    token_input: Callable[[str], str],
    connection_class: Any,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Preview, local confirmation, then credentials, then the pinned R.53 connector."""
    require_prior_hashes()
    preview = session_preview()
    shown = render_preview(preview)
    try:
        answer = confirm_input(shown)
    except (LiveTransportDisabled, Rejected):
        raise
    except Exception:
        raise Rejected(REJECTED) from None
    if not isinstance(answer, str) or answer != CONFIRM:
        return _cancelled(preview)
    if _live_class(connection_class) or not isinstance(connection_class, type):
        raise LiveTransportDisabled(LIVE_DISABLED)
    credential = prompt_for_credentials(account_input, token_input)
    _guard(preview, (credential.account_id, credential.token))
    connector = _r53()
    document = connector.run_synthetic(credential.account_id, credential.token, connection_class)
    _guard(document, (credential.account_id, credential.token))
    if output_path is not None and document.get("validated_sanitised_responses") == 2:
        connector.write_clean(output_path, document, (credential.account_id, credential.token))
    return {
        "preview": preview,
        "confirmed": True,
        "credentials_requested": True,
        "result": document,
        "terminated": True,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
