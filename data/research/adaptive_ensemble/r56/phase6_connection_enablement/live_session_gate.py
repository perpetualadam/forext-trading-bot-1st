"""Source switch for one future read-only session. It is off.

Changing REAL_SESSION_SOURCE_ENABLEMENT requires a separate written authorisation.
No environment variable or command-line switch can turn it on.

A parent capability is an unpredictable one-time value for one session and one
step. The parent keeps the issuer secret in memory and redeems the value once.
Possession of the value is not operating-system isolation and it is not OANDA
authentication. A worker cannot mint it from a confirmation phrase, a boolean,
an account id, or an API token. A harness capability cannot open HTTPS.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

REAL_SESSION_SOURCE_ENABLEMENT = False
OFFLINE_MODE = "OFFLINE_TEST"
REAL_MODE = "REAL_SESSION"
PLAN_ID = "r56.phase6.two-get.1"
LIVE_HOST = "api-fxtrade.oanda.com"
LIVE_PORT = 443
ONE_SESSION_PHRASE = "CONFIRM ONE DIAGNOSTIC SESSION"
SYNTHETIC_PHRASE = "SYNTHETIC OFFLINE CONFIRM"


class GateRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RuntimeGrant:
    """Capability for the real HTTPS branch. issue_runtime_authorisation is the only constructor caller."""

    def __init__(self, session_id: str, step: str) -> None:
        self.session_id = session_id
        self.step = step
        self.plan_id = PLAN_ID
        self.host = LIVE_HOST
        self.spent = False
        self.authorises_network = True


class HarnessGrant:
    """Capability for an injected fake connection. It never authorises a socket."""

    def __init__(self, session_id: str, step: str) -> None:
        self.session_id = session_id
        self.step = step
        self.plan_id = PLAN_ID
        self.host = LIVE_HOST
        self.spent = False
        self.authorises_network = False


class RedeemedCapability:
    """Stand-in created only after the source switch and a parent CAP_OK ack."""

    def __init__(self, session_id: str, step: str) -> None:
        self.session_id = session_id
        self.step = step
        self.plan_id = PLAN_ID
        self.host = LIVE_HOST
        self.spent = False
        self.authorises_network = True


_CONFIRMATIONS: dict[str, dict[str, object]] = {}
CONFIRMATION_MAX_AGE_SECONDS = 60.0


def assert_real_session() -> None:
    """Pass only after the source constant above is set true on purpose."""
    if REAL_SESSION_SOURCE_ENABLEMENT is not True:
        raise GateRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")


def fixed_plan() -> dict[str, object]:
    return {
        "plan_id": PLAN_ID,
        "environment": "OANDA_LIVE",
        "host": LIVE_HOST,
        "port": LIVE_PORT,
        "requests": ["summary", "pricing"],
        "methods": ["GET", "GET"],
    }


def render_plan() -> str:
    return "\n".join(
        (
            "Environment OANDA LIVE",
            "Host api-fxtrade.oanda.com:443",
            "GET /v3/accounts/{accountID}/summary",
            "GET /v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF",
            "No orders. No position changes. One diagnostic session.",
        )
    )


def _plan_ok(plan: object) -> bool:
    expected = fixed_plan()
    return isinstance(plan, dict) and plan == expected


def _session_ok(session_id: object, step: object) -> bool:
    return (
        isinstance(session_id, str)
        and session_id.startswith("r56-")
        and len(session_id) == 36
        and step in {"summary", "pricing"}
    )


def confirm_one_session(answer: object, *, screen: object) -> dict[str, object]:
    """Operator acknowledgement of the two-GET plan. This does not enable the network."""
    if answer == SYNTHETIC_PHRASE or answer != ONE_SESSION_PHRASE:
        raise GateRejected("CONFIRMATION_REJECTED")
    if not isinstance(screen, str) or LIVE_HOST not in screen or "summary" not in screen or "pricing" not in screen:
        raise GateRejected("CONFIRMATION_REJECTED")
    confirmation_id = secrets.token_hex(16)
    issued_at = time.monotonic()
    _CONFIRMATIONS[confirmation_id] = {"issued_at": issued_at, "spent": False}
    return {
        "confirmed": True,
        "network_permitted": False,
        "real_session_source_enablement": REAL_SESSION_SOURCE_ENABLEMENT is True,
        "confirmation_id": confirmation_id,
        "issued_at": issued_at,
    }


def accept_confirmation(receipt: object, *, now: float | None = None) -> None:
    """Spend one fresh receipt. A copy, an unknown id, or an old receipt is refused."""
    if not isinstance(receipt, dict):
        raise GateRejected("CONFIRMATION_REJECTED")
    confirmation_id = receipt.get("confirmation_id")
    record = _CONFIRMATIONS.get(confirmation_id) if isinstance(confirmation_id, str) else None
    if record is None:
        raise GateRejected("CONFIRMATION_REJECTED")
    if record.get("spent") is True:
        raise GateRejected("CONFIRMATION_REPLAYED")
    current = time.monotonic() if now is None else now
    issued_at = record.get("issued_at")
    if not isinstance(issued_at, float) or current - issued_at > CONFIRMATION_MAX_AGE_SECONDS:
        raise GateRejected("CONFIRMATION_STALE")
    if receipt.get("confirmed") is not True or receipt.get("network_permitted") is not False:
        raise GateRejected("CONFIRMATION_REJECTED")
    record["spent"] = True


def issue_runtime_authorisation(*_args: object, **kwargs: object) -> RuntimeGrant:
    """Mint one real grant. Refuses while the source switch is off, before any other check."""
    assert_real_session()
    answer = kwargs.get("answer")
    if answer == SYNTHETIC_PHRASE or answer != ONE_SESSION_PHRASE:
        raise GateRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
    confirmation = kwargs.get("confirmation")
    if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True or confirmation.get("network_permitted") is not False:
        raise GateRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
    if not _plan_ok(kwargs.get("plan")) or not _session_ok(kwargs.get("session_id"), kwargs.get("step")):
        raise GateRejected("GRANT_REJECTED")
    return RuntimeGrant(str(kwargs["session_id"]), str(kwargs["step"]))


def assert_runtime_authorisation(grant: object = None, *, session_id: str | None = None, step: str | None = None) -> None:
    """Accept only an unspent real grant for this session and step."""
    assert_real_session()
    if grant is None or grant.__class__ is not RuntimeGrant:
        raise GateRejected("GRANT_REJECTED")
    if grant.spent:
        raise GateRejected("GRANT_EXPIRED")
    if grant.session_id != session_id or grant.step != step or grant.plan_id != PLAN_ID or grant.host != LIVE_HOST:
        raise GateRejected("GRANT_REJECTED")
    if grant.authorises_network is not True:
        raise GateRejected("GRANT_REJECTED")


def issue_harness_authorisation(*_args: object, **kwargs: object) -> HarnessGrant:
    """Mint a fake-connection grant. A synthetic phrase cannot mint it, and it cannot open a socket."""
    answer = kwargs.get("answer")
    if answer == SYNTHETIC_PHRASE or answer != ONE_SESSION_PHRASE:
        raise GateRejected("CONFIRMATION_REJECTED")
    confirmation = kwargs.get("confirmation")
    if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True or confirmation.get("network_permitted") is not False:
        raise GateRejected("CONFIRMATION_REJECTED")
    if confirmation.get("real_session_source_enablement") is not False:
        raise GateRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
    if not _plan_ok(kwargs.get("plan")) or not _session_ok(kwargs.get("session_id"), kwargs.get("step")):
        raise GateRejected("GRANT_REJECTED")
    return HarnessGrant(str(kwargs["session_id"]), str(kwargs["step"]))


def assert_harness_authorisation(grant: object = None, *, session_id: str | None = None, step: str | None = None) -> None:
    if grant is None or grant.__class__ is not HarnessGrant:
        raise GateRejected("GRANT_REJECTED")
    if grant.authorises_network is not False:
        raise GateRejected("GRANT_REJECTED")
    if grant.spent:
        raise GateRejected("GRANT_EXPIRED")
    if grant.session_id != session_id or grant.step != step or grant.plan_id != PLAN_ID or grant.host != LIVE_HOST:
        raise GateRejected("GRANT_REJECTED")


def expire_grant(grant: object) -> None:
    if isinstance(grant, (RuntimeGrant, HarnessGrant, RedeemedCapability)):
        grant.spent = True


def bind_harness_grant(session_id: object, step: object) -> HarnessGrant:
    """Fake-connection stand-in. It does not read a confirmation phrase and cannot open a socket."""
    if not _session_ok(session_id, step):
        raise GateRejected("GRANT_REJECTED")
    return HarnessGrant(str(session_id), str(step))


def note_parent_ack(parent_ack: object, session_id: object, step: object) -> RedeemedCapability:
    """Real-session stand-in. The source switch is checked before the object exists."""
    assert_real_session()
    if parent_ack != "CAP_OK" or not _session_ok(session_id, step):
        raise GateRejected("GRANT_REJECTED")
    return RedeemedCapability(str(session_id), str(step))


def assert_parent_capability(grant: object = None, *, session_id: str | None = None, step: str | None = None) -> None:
    """Accept only an unspent parent ack for this session and step. A harness grant is not enough."""
    if grant is None or grant.__class__ is not RedeemedCapability or grant.authorises_network is not True:
        raise GateRejected("GRANT_REJECTED")
    assert_real_session()
    if grant.spent:
        raise GateRejected("GRANT_EXPIRED")
    if grant.session_id != session_id or grant.step != step or grant.plan_id != PLAN_ID or grant.host != LIVE_HOST:
        raise GateRejected("GRANT_REJECTED")


class CapabilityIssuer:
    """In-memory one-time capabilities. The HMAC key never leaves this object."""

    def __init__(self) -> None:
        self._secret = secrets.token_bytes(32)
        self._open: dict[str, dict[str, object]] = {}

    def _bind(self, *, session_id: object, step: object, mode: str, lifetime: float, offline_binding: bool) -> str:
        nonce = secrets.token_hex(32)
        binding = "|".join((str(session_id), str(step), LIVE_HOST, str(LIVE_PORT), PLAN_ID, mode))
        mac = hmac.new(self._secret, (nonce + "|" + binding).encode("utf-8"), hashlib.sha256).hexdigest()
        token = nonce + "." + mac
        self._open[token] = {
            "session_id": str(session_id),
            "step": str(step),
            "mode": mode,
            "expires": time.monotonic() + lifetime,
            "spent": False,
            "offline_binding": offline_binding,
            "authorises_network": False,
        }
        return token

    def issue(self, *, session_id: object, step: object, mode: str, lifetime: float = 15.0) -> str:
        if mode == "REAL_SESSION":
            assert_real_session()
        elif mode != "HARNESS_SESSION":
            raise GateRejected("GRANT_REJECTED")
        if not _session_ok(session_id, step):
            raise GateRejected("GRANT_REJECTED")
        return self._bind(session_id=session_id, step=step, mode=mode, lifetime=lifetime, offline_binding=False)

    def issue_offline_mode_binding(self, *, session_id: object, step: object, mode: str, lifetime: float = 15.0) -> str:
        """Mode-binding fixture. It does not pass the source switch and it does not authorise a socket."""
        if mode not in {"HARNESS_SESSION", "REAL_SESSION"}:
            raise GateRejected("GRANT_REJECTED")
        if not _session_ok(session_id, step):
            raise GateRejected("GRANT_REJECTED")
        return self._bind(session_id=session_id, step=step, mode=mode, lifetime=lifetime, offline_binding=True)

    def redeem(self, token: object, *, session_id: object, step: object, mode: str) -> None:
        if not isinstance(token, str):
            raise GateRejected("CAPABILITY_FORGED")
        record = self._open.get(token)
        if record is None or token.count(".") != 1:
            raise GateRejected("CAPABILITY_FORGED")
        nonce, mac = token.split(".", 1)
        issued_session = str(record.get("session_id"))
        issued_step = str(record.get("step"))
        issued_mode = str(record.get("mode"))
        binding = "|".join((issued_session, issued_step, LIVE_HOST, str(LIVE_PORT), PLAN_ID, issued_mode))
        expected = hmac.new(self._secret, (nonce + "|" + binding).encode("utf-8"), hashlib.sha256).hexdigest()
        if len(mac) != len(expected) or not hmac.compare_digest(mac, expected):
            raise GateRejected("CAPABILITY_FORGED")
        if record.get("spent") is True:
            raise GateRejected("CAPABILITY_REPLAYED")
        expires = record.get("expires")
        if not isinstance(expires, float) or time.monotonic() > expires:
            record["spent"] = True
            raise GateRejected("CAPABILITY_EXPIRED")
        if issued_session != session_id:
            raise GateRejected("CAPABILITY_WRONG_SESSION")
        if issued_step != step:
            raise GateRejected("CAPABILITY_WRONG_STEP")
        if issued_mode != mode:
            raise GateRejected("GRANT_REJECTED")
        record["spent"] = True

    def expire_all(self) -> None:
        for record in self._open.values():
            record["spent"] = True


def open_real_session(*_args: object, **_kwargs: object) -> None:
    assert_real_session()
    assert_runtime_authorisation(None)


def prepare_real_session(*_args: object, **kwargs: object) -> None:
    """Prompt order after both gates. The source switch rejects this before any prompt."""
    assert_real_session()
    import importlib.util
    import sys
    from pathlib import Path

    name = "r56p6_credential_ipc"
    module = sys.modules.get(name)
    if module is None:
        path = Path(__file__).resolve().parent / "credential_ipc.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        sys.modules[name] = module
        spec.loader.exec_module(module)
    module.prompt_account_id(**kwargs)
    module.prompt_hidden_token(**kwargs)
