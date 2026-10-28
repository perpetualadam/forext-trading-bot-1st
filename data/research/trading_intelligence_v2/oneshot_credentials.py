"""In-memory real-token implementation behind the unimplemented live gate.

Never import operational configuration or dotenv. Tests replace the exact getter
with synthetic values; ordinary calls refuse before even querying the environment.
"""
import os
import re
from . import oneshot_authorisation as authority
from .oneshot_archive import Refused


def validate_token(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9._-]{10,512}',value):
        raise Refused('CREDENTIAL_INPUT_REFUSED')
    return value


class ReservedCredentialProvider:
    __slots__=()
    def __repr__(self):return '<ReservedCredentialProvider DISABLED REDACTED>'
    def credential(self,reservation=None):
        authority.require_live_reservation(reservation)
        # Reached only after a future approved validator accepts a durable
        # controller-bound reservation. No token field is stored on this object.
        try:
            value=os.getenv('OANDA_ACCESS_TOKEN') or os.getenv('OANDA_API_KEY')
            return validate_token(value)
        except Exception:
            raise Refused('CREDENTIAL_INPUT_REFUSED') from None


def acquire_history(*,credential_provider=None):
    """Normal entry always refuses before provider, archive or network activity."""
    authority.require_live_reservation(None)


def run_reserved_history(root,*,reservation,seconds=15.0,pin=None):
    """Dormant integration with the original controller; no accepted real grants."""
    authority.require_live_reservation(reservation)
    if seconds!=15.0:raise Refused('EXACT_DEADLINE_REQUIRED')
    from .oneshot import run_once
    return run_once(root,synthetic_secret=None,seconds=seconds,pin=pin,
                    _credential_provider=ReservedCredentialProvider(),_live_reservation=reservation)
