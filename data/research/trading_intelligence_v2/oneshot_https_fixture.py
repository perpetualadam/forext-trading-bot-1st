"""Test-only TLS binding. Physical destination is always IPv4 loopback.

No host override, production allowlist mutation, credential loader or retry.
The certificate is an ephemeral public fixture certificate, not a private key.
"""
import http.client
import math
import socket
import ssl
import time
from .oneshot import SPEC,request_guard
from .oneshot_archive import Refused
from .oneshot_bridge import validate_synthetic
from .oanda_history_transport import CandleTransport,_exchange_get
from .oanda_history_manifest import encoded,decode


def validate_binding(binding):
    if (type(binding) is not dict or set(binding)!={'port','certificate','verification'} or
        type(binding['port']) is not int or not 1<=binding['port']<=65535 or
        type(binding['certificate']) is not str or len(binding['certificate'])>1000 or
        not binding['certificate'].startswith('-----BEGIN CERTIFICATE-----\n') or
        not isinstance(binding['verification'],str) or
        binding['verification'] not in ('trusted','untrusted','hostname_mismatch')):
        raise Refused('INVALID_LOOPBACK_FIXTURE')


def fetch_https_fixture(binding,secret,deadline,checkpoint=lambda phase:None,*,_request=None):
    from .oneshot_network import fetch_synthetic
    return fetch_synthetic(binding,secret,deadline,checkpoint,request=_request)
