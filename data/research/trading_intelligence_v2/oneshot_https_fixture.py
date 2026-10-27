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


def validate_binding(binding):
    if (type(binding) is not dict or set(binding)!={'port','certificate','verification'} or
        type(binding['port']) is not int or not 1<=binding['port']<=65535 or
        type(binding['certificate']) is not str or len(binding['certificate'])>1000 or
        not binding['certificate'].startswith('-----BEGIN CERTIFICATE-----\n') or
        not isinstance(binding['verification'],str) or
        binding['verification'] not in ('trusted','untrusted','hostname_mismatch')):
        raise Refused('INVALID_LOOPBACK_FIXTURE')


def fetch_https_fixture(binding,secret,deadline,checkpoint=lambda phase:None):
    validate_binding(binding);validate_synthetic(secret);request_guard(**SPEC)
    if type(deadline) not in (int,float) or not math.isfinite(deadline):raise Refused('INVALID_DEADLINE')
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if binding['verification']!='untrusted':context.load_verify_locations(cadata=binding['certificate'])
    # check_hostname and CERT_REQUIRED stay enabled, including rejection tests.
    hostname='wrong.invalid' if binding['verification']=='hostname_mismatch' else 'localhost'
    class LoopbackConnection(http.client.HTTPSConnection):
        def send(self,data):
            super().send(data)
            # A fixture fault here is genuinely after HTTP bytes entered TLS,
            # not merely before constructing the request. Remote receipt varies.
            checkpoint('during_dispatch')
        def connect(self):
            if self._tunnel_host:raise Refused('TUNNEL_REFUSED')
            sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            try:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError()
                sock.settimeout(min(15,remaining));sock.connect(('127.0.0.1',binding['port']))
                self.sock=context.wrap_socket(sock,server_hostname=hostname)
            except BaseException:sock.close();raise
    def sender(method,host,path,params):
        request_guard(method,host,path,params)
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError()
        connection=LoopbackConnection('127.0.0.1',port=binding['port'],timeout=min(15,remaining),context=context)
        try:return _exchange_get(connection,host,path,params,secret,deadline)
        except OSError as error:raise Refused('FIXTURE_WIRE_REFUSED') from error
        finally:connection.close()
    transport=CandleTransport(environment='live',sender=sender,attempts=1)
    return transport.request(**SPEC)
