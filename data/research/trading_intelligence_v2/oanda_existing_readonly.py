"""Existing InstrumentsCandles schema on the V2.6D one-shot boundary.

No SDK client, operational imports, configuration loading or network factory.
The configuration names describe a future reviewed provider, never read values.
"""
from .oneshot import SPEC,request_guard
from .oneshot_archive import Refused
from .oanda_history_manifest import encoded,decode

STATE='AUTHENTICATED_EXECUTION_DISABLED'
CONFIGURATION_KEYS=('TRADING_MODE','OANDA_ACCESS_TOKEN','OANDA_API_KEY')


class ExistingOandaCredentialProvider:
    """Inactive provider interface; no flag, callback or token loader enables it.

    Compatible with the existing memory-only credential() delivery interface.
    The controller still accepts only its exact SyntheticCredentialProvider.
    """
    __slots__=()
    def credential(self):
        from .oneshot_credentials import ReservedCredentialProvider
        return ReservedCredentialProvider().credential()
    def __repr__(self):return '<ExistingOandaCredentialProvider DISABLED REDACTED>'


def candle_request(request=None):
    """Defensive copy of the already reviewed, non-account InstrumentsCandles GET.

    SDK parameter names and MBA match the operational client's latest-candle
    call. The exact bounded dates replace count/chunking. No arbitrary headers,
    account identifiers, proxy settings or SDK Session objects cross this API.
    """
    try:
        value=decode(encoded(SPEC if request is None else request))
        if type(value) is not dict or set(value)!={'method','host','path','params'}:
            raise ValueError()
        request_guard(**value)
    except (TypeError,ValueError,OverflowError,Refused):
        raise Refused('EXACT_READ_ONLY_REQUEST_REQUIRED') from None
    return value


def acquire_history(*,credential_provider=None):
    """The future authenticated route remains disabled before provider access."""
    from .oneshot_bridge import acquire_history as disabled
    return disabled(credential_provider=credential_provider)


def run_synthetic_session(root,*,provider,binding,seconds=15.0,pin=None,fault=''):
    """Use the existing controller, reservation, worker, IPC and archive only."""
    from .oneshot_bridge import run_https_fixture
    candle_request()
    return run_https_fixture(root,provider=provider,binding=binding,
                             seconds=seconds,pin=pin,fault=fault)


def fetch_synthetic_candles(binding,secret,deadline,checkpoint=lambda phase:None):
    """Worker adapter: existing transport and verified loopback TLS implementation."""
    from .oneshot_https_fixture import fetch_https_fixture
    return fetch_https_fixture(binding,secret,deadline,checkpoint,_request=candle_request())
