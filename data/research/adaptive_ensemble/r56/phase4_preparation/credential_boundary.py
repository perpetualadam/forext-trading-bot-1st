"""Synthetic credentials only. There is no reader for a real token."""

from __future__ import annotations

SYNTHETIC_TOKEN = "SYNTHETIC-TOKEN-R56P4-NOT-REAL"
SYNTHETIC_ACCOUNT_ID = "001-001-0000000-001"
HIDDEN_INPUT = "NOT_IMPLEMENTED"


class CredentialRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SyntheticCredential:
    """A visibly synthetic credential. It is not an OANDA token."""

    classification = "SYNTHETIC_TEST_ONLY"
    token = SYNTHETIC_TOKEN
    account_id = SYNTHETIC_ACCOUNT_ID


def authorization_present(credential: object) -> bool:
    """Return whether a synthetic credential object was supplied. The token is not returned."""
    if credential.__class__ is not SyntheticCredential:
        raise CredentialRejected("REAL_CREDENTIAL_PROVIDER_REJECTED")
    if getattr(credential, "classification", None) != "SYNTHETIC_TEST_ONLY":
        raise CredentialRejected("REAL_CREDENTIAL_PROVIDER_REJECTED")
    token = getattr(credential, "token", "")
    if not isinstance(token, str) or not token.startswith("SYNTHETIC-TOKEN-R56P4-"):
        raise CredentialRejected("REAL_CREDENTIAL_PROVIDER_REJECTED")
    if getattr(credential, "account_id", None) != SYNTHETIC_ACCOUNT_ID:
        raise CredentialRejected("REAL_CREDENTIAL_PROVIDER_REJECTED")
    return True


def read_real_credential() -> None:
    """Real credential input is not implemented and is not authorised."""
    raise CredentialRejected("REAL_CREDENTIAL_INPUT_NOT_AUTHORISED")
