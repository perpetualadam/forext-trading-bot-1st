"""R.55 Boundary B1 session. Default launch and --offline do not open a live connection."""

from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import ssl
import sys
from pathlib import Path
from typing import Any, Callable

PINS = {
    "r51": ("r51", "https_adapter.py", "e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef"),
    "r52": ("r52", "session_entry.py", "59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56"),
    "r53": ("r53", "connector.py", "7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4"),
    "r54": ("r54", "session_main.py", "50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280"),
    "r55": ("r55", "session_main.py", "5913a190812343a9039570893f6cc96fb30fb2a08a6305b84e0bb7bea3576cf8"),
    "r48": ("r48", "readonly_transport.py", "3ef1be4e565b7e2f783931e66e962ba3264f4be551bda2e4cd87f1705bf3b844"),
    "r50": ("r50", "connector.py", "4520a39688001f4947d06a8c18dc0e404df7271c3ca79b0f62d64812fefab5f8"),
    "fixtures": ("r50", "fixtures.py", "bf03349d425c27f36f989182a051460d4d7da2535937ccd70019fbb4647a42ee"),
}
LIVE_DISABLED = "R55B1_LIVE_NOT_SELECTED"
REJECTED = "R55B1_REJECTED"
CONFIRM = "CONFIRM PREVIEW"
SYNTHETIC = "SYNTHETIC_TEST_ONLY"
LIVE_EVIDENCE = "READ_ONLY_RESPONSE_NOT_ACCOUNT_VERIFIED"
ACCOUNT = "SYNTHETIC-ACCOUNT-R55B1-NOT-REAL"
TOKEN = "SYNTHETIC-TOKEN-R55B1-NOT-REAL"
SIX = (
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "USD_JPY",
)
HERE = Path(__file__).resolve().parent


class Rejected(RuntimeError):
    """Fail closed. The message is a fixed code."""


def _research(stage: str, name: str) -> Path:
    return HERE.parents[1] / stage / name


def prior_hashes() -> dict[str, str]:
    return {
        key: hashlib.sha256(_research(stage, name).read_bytes()).hexdigest()
        for key, (stage, name, _pin) in PINS.items()
    }


def require_prior_hashes() -> None:
    found = prior_hashes()
    if any(found[key] != pin for key, (_stage, _name, pin) in PINS.items()):
        raise SystemExit("R55B1_PRIOR_HASH_MISMATCH")


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Rejected(REJECTED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _r53() -> Any:
    require_prior_hashes()
    return _load("r53_connector_r55b1", _research("r53", "connector.py"))


def _fixtures() -> Any:
    require_prior_hashes()
    return _load("r50_fixtures_r55b1", _research("r50", "fixtures.py"))


def _transmit() -> Callable[..., tuple[int, bytes]]:
    return _load("r55b1_transport", HERE / "transport.py").transmit


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
        raise Rejected(REJECTED)
    try:
        account_id = account_input("Account identifier: ")
        token = token_input("API token: ")
    except Rejected:
        raise
    except Exception:
        raise Rejected(REJECTED) from None
    return accept_credentials(account_id, token)


def session_preview() -> dict[str, Any]:
    """Facts that may be shown before a future connection. This is not an approval."""
    return {
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
        "Broker token permissions: UNKNOWN",
        "Account home currency: not API-verified",
        "Spread-bet stake semantics: unverified",
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
    if "Bearer" in blob or "Authorization" in blob or "https://" in blob or "ACCOUNT_VERIFIED" in blob or "1.35" in blob:
        raise Rejected(REJECTED)


def _label(document: dict[str, Any], mode: str) -> dict[str, Any]:
    """Offline output stays synthetic. The live evidence label is not applied while B2 is disabled."""
    if mode != "offline":
        raise Rejected(LIVE_DISABLED)
    document["evidence_class"] = SYNTHETIC
    document["account_specific_api_evidence"] = "NOT_PRODUCED"
    for item in document["endpoint_results"]:
        item["evidence_class"] = SYNTHETIC
    for row in document["rows"]:
        row["evidence_class"] = SYNTHETIC
    return document


def _live_class(connection_class: Any) -> bool:
    if connection_class is http.client.HTTPSConnection or connection_class is http.client.HTTPConnection:
        return True
    if isinstance(connection_class, type) and issubclass(connection_class, (http.client.HTTPConnection, http.client.HTTPSConnection)):
        return True
    return False


def _builtin_transport(connection_class: Any) -> bool:
    return connection_class is SyntheticTransport


def _output_target(path: Path | None) -> Path | None:
    if path is None:
        return None
    resolved = path.resolve()
    if resolved.parent != HERE:
        raise Rejected(REJECTED)
    return resolved


def _retire_output(path: Path | None) -> None:
    target = _output_target(path)
    if target is not None and target.exists():
        target.unlink()


def _write_validated(path: Path, document: dict[str, Any]) -> None:
    target = _output_target(path)
    if target is None or document.get("evidence_class") != SYNTHETIC or document.get("validated_sanitised_responses") != 2:
        raise Rejected(REJECTED)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(document, indent=2), encoding="utf-8")
    temporary.replace(target)


def _validate(document: dict[str, Any], secrets: tuple[str, ...], mode: str) -> dict[str, Any]:
    gate = _r53()
    if mode != "offline":
        raise Rejected(LIVE_DISABLED)
    if document.get("evidence_class") == LIVE_EVIDENCE or document.get("account_specific_api_evidence") == "COLLECTED_NOT_ACCOUNT_VERIFIED":
        raise Rejected(LIVE_DISABLED)
    allowed_evidence = SYNTHETIC
    allowed_account = "NOT_PRODUCED"
    if set(document) != set(gate._TOP_KEYS):
        raise Rejected(REJECTED)
    if document.get("evidence_class") != allowed_evidence or document.get("account_specific_api_evidence") != allowed_account:
        raise Rejected(REJECTED)
    if document.get("account_home_currency") != gate.HOME_CURRENCY:
        raise Rejected(REJECTED)
    attempted = document.get("requests_attempted")
    http_ok = document.get("successful_http_responses")
    validated = document.get("validated_sanitised_responses")
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in (attempted, http_ok, validated)):
        raise Rejected(REJECTED)
    if not 0 <= validated <= http_ok <= attempted <= 2:
        raise Rejected(REJECTED)
    order = document.get("endpoint_order")
    results = document.get("endpoint_results")
    if order not in (["instruments"], ["instruments", "pricing"]) or not isinstance(results, list):
        raise Rejected(REJECTED)
    if len(order) != attempted or len(results) != attempted or [item.get("endpoint") for item in results] != order:
        raise Rejected(REJECTED)
    for item in results:
        if set(item) != set(gate._ENDPOINT_KEYS) or item.get("result") not in ("SUCCESS", "FAILURE"):
            raise Rejected(REJECTED)
        if item.get("error_classification") not in gate._CLASSIFICATIONS or item.get("evidence_class") != allowed_evidence:
            raise Rejected(REJECTED)
        if item.get("missing_field_status") not in ("NONE", "NOT_RETURNED", "NOT_VALIDATED"):
            raise Rejected(REJECTED)
    if document.get("missing_field_status") not in ("NONE", "NOT_RETURNED", "NOT_VALIDATED"):
        raise Rejected(REJECTED)
    rows = document.get("rows")
    if not isinstance(rows, list) or (validated == 2 and [row.get("instrument") for row in rows] != list(SIX)):
        raise Rejected(REJECTED)
    if validated != 2 and rows:
        raise Rejected(REJECTED)
    for row in rows:
        if set(row) != set(gate._ROW_KEYS) or row.get("evidence_class") != allowed_evidence:
            raise Rejected(REJECTED)
        if row.get("account_home_currency") != gate.HOME_CURRENCY or row.get("stake_settlement") != "UNKNOWN":
            raise Rejected(REJECTED)
        if row.get("quoted_conversion_currency_is_account_home") != "NO":
            raise Rejected(REJECTED)
    ticket = document.get("historical_ticket")
    panel = document.get("historical_financing_panel")
    if not isinstance(ticket, dict) or not isinstance(panel, dict):
        raise Rejected(REJECTED)
    if set(ticket) != set(gate._TICKET_KEYS) or set(panel) != set(gate._PANEL_KEYS):
        raise Rejected(REJECTED)
    if ticket.get("api_confirmation") != "NO" or panel.get("api_confirmation") != "NO":
        raise Rejected(REJECTED)
    _guard(document, secrets)
    return document


def _cancelled(preview: dict[str, Any]) -> dict[str, Any]:
    return {
        "preview": preview,
        "confirmed": False,
        "credentials_requested": False,
        "result": None,
        "terminated": True,
    }


class SyntheticTransport:
    """Offline stand-in. It never opens a socket."""

    calls = 0

    def __init__(self, host: str, port: int | None = None, timeout: float | None = None, context: ssl.SSLContext | None = None, **kwargs: object) -> None:
        SyntheticTransport.calls += 1
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.kwargs = kwargs
        self.closed = False
        self._body = b""
        self._status = 200

    def request(self, method: str, target: str, body: bytes | None = None, headers: dict | None = None) -> None:
        if method != "GET" or body is not None:
            raise Rejected(REJECTED)
        fixtures = _fixtures()
        payload = fixtures.instruments_payload() if SyntheticTransport.calls == 1 else fixtures.pricing_payload()
        self._body = json.dumps(payload).encode("utf-8")

    def getresponse(self) -> "SyntheticTransport":
        return self

    @property
    def status(self) -> int:
        return self._status

    def read(self, _amount: int | None = None) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True


def _execute_offline(
    confirm_input: Callable[[str], str],
    account_input: Callable[[str], str],
    token_input: Callable[[str], str],
    connection_class: Any,
    output_path: Path | None,
    mode: str,
) -> dict[str, Any]:
    preview = session_preview()
    shown = render_preview(preview)
    try:
        answer = confirm_input(shown)
    except Rejected:
        raise
    except Exception:
        raise Rejected(REJECTED) from None
    if not isinstance(answer, str) or answer != CONFIRM:
        _retire_output(output_path)
        return _cancelled(preview)
    _retire_output(output_path)
    credential = prompt_for_credentials(account_input, token_input)
    _guard(preview, (credential.account_id, credential.token))
    gate = _r53()
    parser = gate._r48()
    planner = gate._r50()
    attempted = 0
    http_ok = 0
    validated = 0
    order: list[str] = []
    results: list[dict[str, str]] = []
    instruments: list[dict[str, Any]] | None = None
    prices: list[dict[str, Any]] | None = None
    for kind in ("instruments", "pricing"):
        prepared = planner.prepare(kind, credential.account_id, credential.token)
        order.append(kind)
        try:
            _status, raw = _transmit()(prepared, connection_class, gate)
        except gate.Failure as exc:
            attempted += 1
            if exc.http_ok:
                http_ok += 1
            results.append(gate._endpoint(kind, "FAILURE", exc.classification, "200" if exc.http_ok else "NONE", "NOT_VALIDATED"))
            break
        except Exception:
            attempted += 1
            results.append(gate._endpoint(kind, "FAILURE", "UNEXPECTED", "NONE", "NOT_VALIDATED"))
            break
        attempted += 1
        http_ok += 1
        try:
            payload = gate.parse_body(raw)
            if kind == "instruments":
                instruments = gate._accept_instruments(parser, payload)
            else:
                locations = {
                    row["instrument"]: row["pipLocation"]
                    for row in instruments or []
                    if row.get("pipLocation") not in (None, "MISSING")
                }
                prices = gate._accept_prices(parser, payload, locations)
                gate._rows(instruments or [], prices)
        except gate.Failure as exc:
            results.append(gate._endpoint(kind, "FAILURE", exc.classification, "200", "NOT_VALIDATED"))
            break
        except Exception:
            results.append(gate._endpoint(kind, "FAILURE", "UNEXPECTED", "NONE", "NOT_VALIDATED"))
            break
        validated += 1
        results.append(gate._endpoint(kind, "SUCCESS", "NONE", "200", "NONE"))
    rows = gate._rows(instruments, prices) if instruments is not None and prices is not None and validated == 2 else []
    if validated == 2:
        status = gate._missing_status(rows)
        for item in results:
            item["missing_field_status"] = status
    else:
        for item in results:
            if item["result"] != "FAILURE":
                item["missing_field_status"] = "NOT_VALIDATED"
    document = _label(gate._document(attempted, http_ok, validated, order, results, rows), mode)
    document = _validate(document, (credential.account_id, credential.token), mode)
    if output_path is not None and document.get("validated_sanitised_responses") == 2:
        _write_validated(output_path, document)
    return {
        "preview": preview,
        "confirmed": True,
        "credentials_requested": True,
        "result": document,
        "terminated": True,
    }


def run_session(
    confirm_input: Callable[[str], str],
    account_input: Callable[[str], str],
    token_input: Callable[[str], str],
    connection_class: Any,
    output_path: Path | None = None,
    mode: str = "offline",
) -> dict[str, Any]:
    """Executable offline session. Only the built-in synthetic transport is accepted."""
    if mode != "offline":
        raise Rejected(LIVE_DISABLED)
    if _live_class(connection_class) or not _builtin_transport(connection_class):
        raise Rejected(LIVE_DISABLED)
    return _execute_offline(confirm_input, account_input, token_input, connection_class, output_path, mode)


def run_test_session(
    confirm_input: Callable[[str], str],
    account_input: Callable[[str], str],
    token_input: Callable[[str], str],
    connection_class: Any,
    output_path: Path | None = None,
    mode: str = "offline",
) -> dict[str, Any]:
    """Test-only entry. launch and run_offline do not call it.

    Accepting a stand-in here does not show that the stand-in cannot use the network.
    The offline tests install a network-denial fixture. That fixture is not a sandbox.
    """
    if mode != "offline":
        raise Rejected(LIVE_DISABLED)
    if _live_class(connection_class) or not isinstance(connection_class, type):
        raise Rejected(LIVE_DISABLED)
    return _execute_offline(confirm_input, account_input, token_input, connection_class, output_path, mode)


def run_offline() -> int:
    """Synthetic readers and the offline transport. This does not call the live entry."""
    SyntheticTransport.calls = 0

    def confirm_input(prompt: str) -> str:
        print(prompt)
        return CONFIRM

    def account_input(_prompt: str) -> str:
        return ACCOUNT

    def token_input(_prompt: str) -> str:
        return TOKEN

    package = run_session(
        confirm_input,
        account_input,
        token_input,
        SyntheticTransport,
        HERE / "06_synthetic_output.json",
        "offline",
    )
    result = package["result"]
    print(result["requests_attempted"])
    print(result["successful_http_responses"])
    print(result["validated_sanitised_responses"])
    print(result["evidence_class"])
    return 0


def run_live() -> int:
    """Boundary B2 remains disabled. This function does not prompt or connect."""
    raise Rejected(LIVE_DISABLED)


def launch(argv: list[str] | None = None) -> int:
    """No arguments stays disabled. Only an exact offline argument runs the synthetic session."""
    args = [] if argv is None else list(argv)
    require_prior_hashes()
    if args == ["--live"]:
        print("R55 B1 live entry is disabled. No credential prompt. No network connection.")
        return 2
    if args == ["--offline"]:
        return run_offline()
    print("R55 B1 default entry is disabled. No credential prompt. No network connection.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
