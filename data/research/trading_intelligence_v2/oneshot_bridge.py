"""Disabled normal entry and bounded synthetic in-memory credential interface."""
import re
import time
from .oneshot_archive import Refused

STATE='AUTHENTICATED_EXECUTION_DISABLED'


class SyntheticCredentialProvider:
    __slots__=('_value',)
    def __init__(self,value):
        validate_synthetic(value);self._value=value
    def credential(self):return self._value
    def __repr__(self):return '<SyntheticCredentialProvider REDACTED>'


def validate_synthetic(value):
    if not isinstance(value,str) or not re.fullmatch(r'SYNTHETIC_[A-Za-z0-9_]{10,200}',value):
        raise Refused('SYNTHETIC_SECRET_REQUIRED')


def acquire_history(*,credential_provider=None):
    """No live flag or real-grant writer. Refuse before touching the provider."""
    raise Refused(STATE)


def run_https_fixture(root,*,provider,binding,seconds=15.0,pin=None,fault=''):
    """Explicit synthetic-only test path, never an authenticated entry point."""
    started=time.monotonic()
    from .oneshot import run_once
    from .oneshot_https_fixture import validate_binding
    if type(provider) is not SyntheticCredentialProvider:raise Refused('SYNTHETIC_PROVIDER_REQUIRED')
    validate_binding(binding)
    return run_once(root,synthetic_secret=None,seconds=seconds,pin=pin,fault=fault,
                    _credential_provider=provider,_https_fixture=binding,_started=started)
