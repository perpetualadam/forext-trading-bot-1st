"""One exact admitted LIVE connection, sharing the tested fixture wire exchange.

No public sender/factory, host, endpoint, proxy or token-source override. Real
entry requires a source-bound, role-checked durable worker reservation.
"""
import http.client
import ipaddress
import math
import socket
import ssl
import time
from . import oneshot_authorisation as authority
from .oneshot import SPEC,request_guard
from .oneshot_archive import Refused
from .oanda_history_manifest import encoded,decode
from .oanda_history_transport import CandleTransport,_exchange_get

HOST='api-fxtrade.oanda.com'
PORT=443
_DISPATCHED=set()


class LiveSocketPolicy:
    """Exact worker audit scope, unavailable without a real reservation."""
    def __init__(self,reservation):
        authority.require_role(reservation,'network')
        self.resolving=False;self.resolved=False;self.address=None;self.family=None;self.connected=False
    def permits(self,event,args):
        if event=='socket.getaddrinfo' and self.resolving and not self.resolved:
            if args==(HOST,PORT,socket.AF_UNSPEC,socket.SOCK_STREAM,socket.IPPROTO_TCP):
                self.resolved=True;return True
        if event=='socket.__new__' and self.address is not None:
            return args[1]==self.family and args[2]==socket.SOCK_STREAM and args[3] in (0,socket.IPPROTO_TCP)
        if event=='socket.connect' and self.address is not None and not self.connected and args[1]==self.address:
            self.connected=True;return True
        return False


def remaining(deadline):
    if type(deadline) not in (int,float) or not math.isfinite(deadline):
        raise Refused('INVALID_DEADLINE')
    value=deadline-time.monotonic()
    if value<=0 or value>15:raise Refused('INVALID_DEADLINE')
    return value


def select_address(records):
    """Validate all answers, select one once; never fall back to another address."""
    if type(records) is not list or not 1<=len(records)<=64:raise Refused('DNS_ANSWER_REFUSED')
    addresses=[]
    try:
        for family,kind,protocol,canonical,address in records:
            if family not in (socket.AF_INET,socket.AF_INET6) or kind!=socket.SOCK_STREAM or protocol!=socket.IPPROTO_TCP:
                raise ValueError()
            expected=2 if family==socket.AF_INET else 4
            if type(address) is not tuple or len(address)!=expected or address[1]!=PORT:raise ValueError()
            if expected==4 and address[2:]!=(0,0):raise ValueError()
            ip=ipaddress.ip_address(address[0])
            if ip.version!=(4 if family==socket.AF_INET else 6) or not ip.is_global or ip.is_multicast:
                raise ValueError()
            addresses.append((family,address))
    except (TypeError,ValueError,IndexError):raise Refused('DNS_ANSWER_REFUSED') from None
    return addresses[0]


class _LiveConnection(http.client.HTTPSConnection):
    def __init__(self,reservation,deadline,policy=None):
        authority.require_role(reservation,'network')
        if policy is not None and type(policy) is not LiveSocketPolicy:raise Refused('NETWORK_POLICY_REQUIRED')
        if authority.admitted(reservation):
            if reservation['session'] in _DISPATCHED:raise Refused('SECOND_REQUEST_REFUSED')
            _DISPATCHED.add(reservation['session'])
        self._policy=policy if policy is not None else LiveSocketPolicy(reservation)
        self._reservation=reservation;self._deadline=deadline;self._connected=False;self._request_sent=False
        super().__init__(HOST,port=PORT,timeout=remaining(deadline),context=ssl.create_default_context())
    def connect(self):
        authority.require_role(self._reservation,'network')
        if self._connected or self._tunnel_host:raise Refused('SECOND_CONNECTION_REFUSED')
        self._connected=True
        # The installed worker policy permits only this exact DNS operation and
        # the one validated address; no proxy, alternate host or reconnect.
        remaining(self._deadline)
        self._policy.resolving=True
        try:records=socket.getaddrinfo(HOST,PORT,socket.AF_UNSPEC,socket.SOCK_STREAM,socket.IPPROTO_TCP)
        finally:self._policy.resolving=False
        family,address=select_address(records)
        self._policy.family=family;self._policy.address=address
        sock=socket.socket(family,socket.SOCK_STREAM,socket.IPPROTO_TCP)
        try:
            sock.settimeout(remaining(self._deadline));sock.connect(address)
            sock.settimeout(remaining(self._deadline))
            self.sock=self._context.wrap_socket(sock,server_hostname=HOST)
        except BaseException:sock.close();raise

    def request(self,method,url,body=None,headers=None,*,encode_chunked=False):
        from urllib.parse import urlencode
        from .oneshot_credentials import validate_token
        authority.require_role(self._reservation,'network')
        expected={'Authorization','Accept-Datetime-Format','Accept','Accept-Encoding'}
        if (self._request_sent or method!='GET' or url!=SPEC['path']+'?'+urlencode(SPEC['params']) or
            body is not None or encode_chunked or type(headers) is not dict or set(headers)!=expected or
            headers['Accept-Datetime-Format']!='RFC3339' or headers['Accept']!='application/json' or
            headers['Accept-Encoding']!='identity' or type(headers['Authorization']) is not str or not headers['Authorization'].startswith('Bearer ')):
            raise Refused('EXACT_REQUEST_REQUIRED')
        validate_token(headers['Authorization'][7:]);remaining(self._deadline);self._request_sent=True
        return super().request(method,url,body=body,headers=headers,encode_chunked=False)


def _exchange(connection,secret,deadline,request):
    """Single transport attempt shared by real implementation and fixture path."""
    request_guard(**request)
    used=False
    def sender(method,host,path,params):
        nonlocal used
        if used:raise Refused('SECOND_REQUEST_REFUSED')
        used=True;request_guard(method,host,path,params);remaining(deadline)
        try:return _exchange_get(connection,host,path,params,secret,deadline)
        except OSError as error:raise Refused('WIRE_REFUSED') from error
        finally:connection.close()
    return CandleTransport(environment='live',sender=sender,attempts=1).request(**request)


def fetch_live(*,reservation,token,deadline,_policy=None):
    authority.require_role(reservation,'network')
    from .oneshot_credentials import validate_token
    secret=validate_token(token)
    request_guard(**SPEC);remaining(deadline)
    try:return _exchange(_LiveConnection(reservation,deadline,_policy),secret,deadline,SPEC)
    except Exception:raise Refused('LIVE_TRANSPORT_REFUSED') from None


def fetch_synthetic(binding,secret,deadline,checkpoint=lambda phase:None,*,request=None):
    """Fixture only: cannot select another host or accept a real credential."""
    from .oneshot_https_fixture import validate_binding
    from .oneshot_bridge import validate_synthetic
    validate_binding(binding);validate_synthetic(secret)
    try:
        value=decode(encoded(SPEC if request is None else request))
        if type(value) is not dict or set(value)!={'method','host','path','params'}:raise ValueError()
        request_guard(**value)
    except (TypeError,ValueError,OverflowError,Refused):raise Refused('EXACT_REQUEST_REQUIRED') from None
    remaining(deadline)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if binding['verification']!='untrusted':context.load_verify_locations(cadata=binding['certificate'])
    hostname='wrong.invalid' if binding['verification']=='hostname_mismatch' else 'localhost'
    class LoopbackConnection(http.client.HTTPSConnection):
        def send(self,data):super().send(data);checkpoint('during_dispatch')
        def connect(self):
            if self._tunnel_host:raise Refused('TUNNEL_REFUSED')
            sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            try:
                sock.settimeout(remaining(deadline));sock.connect(('127.0.0.1',binding['port']))
                self.sock=context.wrap_socket(sock,server_hostname=hostname)
            except BaseException:sock.close();raise
    connection=LoopbackConnection('127.0.0.1',port=binding['port'],timeout=remaining(deadline),context=context)
    try:return _exchange(connection,secret,deadline,value)
    except OSError as error:raise Refused('FIXTURE_WIRE_REFUSED') from error
