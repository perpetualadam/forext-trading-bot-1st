"""Synthetic credentials only. Real credential entry fails closed."""

from __future__ import annotations

OFFLINE_MARKER = "SYNTHETIC-NOT-REAL"
SYNTHETIC_ACCOUNT_ID = "001-001-0000000-001"


class CredentialRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SyntheticCredential:
    """In-memory synthetic marker. It is not an OANDA token and it is not stored."""

    classification = "SYNTHETIC_TEST_ONLY"

    def __init__(self, token: str | None = None, account_id: str | None = None) -> None:
        self.token = OFFLINE_MARKER if token is None else token
        self.account_id = SYNTHETIC_ACCOUNT_ID if account_id is None else account_id


def accept_offline(credential: object) -> bool:
    """Return a boolean. The marker is not returned and is not logged here."""
    if credential.__class__ is not SyntheticCredential:
        raise CredentialRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    if getattr(credential, "classification", None) != "SYNTHETIC_TEST_ONLY":
        raise CredentialRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    token = getattr(credential, "token", "")
    if not isinstance(token, str) or not token.startswith("SYNTHETIC-") or "NOT-REAL" not in token:
        raise CredentialRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    if getattr(credential, "account_id", None) != SYNTHETIC_ACCOUNT_ID:
        raise CredentialRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    return True


def prompt_hidden_token(*_args: object, **_kwargs: object) -> None:
    raise CredentialRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")


def read_environment(*_args: object, **_kwargs: object) -> None:
    raise CredentialRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")


def read_dotenv(*_args: object, **_kwargs: object) -> None:
    raise CredentialRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")


def activate_live(*_args: object, **_kwargs: object) -> None:
    raise CredentialRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
