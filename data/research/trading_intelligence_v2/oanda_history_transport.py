"""Dedicated GET-only candle transport. No operational client or credential loader."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import math
import re
import threading
import time
from .core import PAIRS,ResearchRejected,iso,timestamp

HOSTS={'practice':'api-fxpractice.oanda.com','live':'api-fxtrade.oanda.com'}
MAX_BODY=8*1024*1024


def approved_request(method,host,path,params):
    if method!='GET' or host not in HOSTS.values(): raise ResearchRejected('METHOD_OR_HOST_REFUSED')
    if path not in {'/v3/instruments/'+p+'/candles' for p in PAIRS}:
        raise ResearchRejected('ENDPOINT_REFUSED')
    if (type(params) is not dict or set(params)!={'from','to','price','granularity','smooth','includeFirst'} or
        params['price']!='MBA' or params['granularity']!='M5' or
        params['smooth']!='false' or params['includeFirst']!='true'):
        raise ResearchRejected('PARAMETERS_REFUSED')
    try: start,end=timestamp(params['from']),timestamp(params['to'])
    except (ValueError,TypeError,OverflowError): raise ResearchRejected('RANGE_REFUSED') from None
    if start%300 or end%300!=299 or not 0<end-start<5000*300:
        raise ResearchRejected('RANGE_REFUSED')
    return True


@dataclass(frozen=True)
class Approval:
    environment: str
    human_approval: bool=False
    terms_reviewed: bool=False
    credential_handling_reviewed: bool=False
    endpoint_currently_supported: bool=False
    start: int | None=None
    end: int | None=None
    instruments: tuple=()


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes=field(repr=False)
    retry_after: str | None=None
    content_type: str='application/json'


class CandleTransport:
    def __init__(self,environment='practice',*,sender=None,token=None,approval=None,
                 cancel=None,clock=time.monotonic,wait=None,wall=time.time,attempts=3):
        if environment not in HOSTS or type(attempts) is not int or not 1<=attempts<=3:
            raise ResearchRejected('INVALID_TRANSPORT_CONFIGURATION')
        self.host=HOSTS[environment];self.attempts=attempts
        self.cancel=cancel or threading.Event();self.clock=clock;self.wall=wall
        self.wait=wait or self.cancel.wait;self.next_request=0
        self.mode='AUTHENTICATED_HTTPS' if sender is None else 'INJECTED_FIXTURE'
        self.__token=None;self.__approval=approval if sender is None else None
        if sender is None:
            if (approval is None or approval.environment!=environment or
                not all(getattr(approval,k) is True for k in ('human_approval','terms_reviewed',
                    'credential_handling_reviewed','endpoint_currently_supported'))):
                raise ResearchRejected('AUTHENTICATED_RETRIEVAL_NOT_AUTHORISED')
            if (type(approval.start) is not int or type(approval.end) is not int or not approval.start<approval.end or
                approval.end>int(wall()) or type(approval.instruments) is not tuple or not approval.instruments or
                any(p not in PAIRS for p in approval.instruments)):
                raise ResearchRejected('APPROVED_HISTORICAL_SCOPE_REQUIRED')
            if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9._-]{10,512}',token):
                raise ResearchRejected('INVALID_CREDENTIAL_INPUT')
            self.__token=token;self.sender=self.__https
        else:
            if token is not None: raise ResearchRejected('NO_CREDENTIALS_IN_FIXTURE_TRANSPORT')
            self.sender=sender

    def __repr__(self): return '<CandleTransport GET-only credentials=REDACTED>'

    def pause(self,seconds):
        if self.cancel.is_set() or self.wait(max(0,seconds)) or self.cancel.is_set():
            raise ResearchRejected('CANCELLED')

    def request(self,method,host,path,params):
        approved_request(method,host,path,params)
        if host!=self.host: raise ResearchRejected('ENVIRONMENT_HOST_MISMATCH')
        if self.__approval is not None:
            a=self.__approval;pair=path.split('/')[3]
            if pair not in a.instruments or not a.start<=timestamp(params['from'])<timestamp(params['to'])<a.end:
                raise ResearchRejected('OUTSIDE_APPROVED_RETRIEVAL_SCOPE')
        for attempt in range(self.attempts):
            self.pause(max(0,self.next_request-self.clock()))
            self.next_request=self.clock()+1.0  # One request and new connection per second.
            try:
                response=self.sender(method,host,path,dict(params))
            except (OSError,TimeoutError):
                if attempt+1==self.attempts: raise ResearchRejected('TRANSPORT_RETRY_EXHAUSTED') from None
                self.pause(2**attempt);continue
            if not isinstance(response,Response): raise ResearchRejected('INVALID_HTTP_RESPONSE')
            if 300<=response.status<400: raise ResearchRejected('REDIRECT_REFUSED')
            if response.status in (429,500,502,503,504):
                if attempt+1==self.attempts: raise ResearchRejected('HTTP_RETRY_EXHAUSTED')
                delay=2**attempt
                if response.retry_after is not None:
                    try:
                        header=response.retry_after
                        delay=max(delay,int(header) if header.isdigit() else
                            parsedate_to_datetime(header).timestamp()-self.wall())
                    except (ValueError,TypeError,OverflowError): raise ResearchRejected('INVALID_RETRY_AFTER') from None
                    if not math.isfinite(delay) or delay>60: raise ResearchRejected('RETRY_AFTER_EXCEEDS_BUDGET')
                self.pause(delay);continue
            if response.status!=200: raise ResearchRejected('HTTP_REQUEST_REFUSED')
            if (type(response.body) is not bytes or len(response.body)>MAX_BODY or
                response.content_type.split(';')[0].strip().lower()!='application/json'):
                raise ResearchRejected('BODY_TYPE_OR_SIZE_REFUSED')
            return response.body
        raise ResearchRejected('RETRY_EXHAUSTED')

    def candles(self,pair,start,end):
        return self.request('GET',self.host,'/v3/instruments/'+pair+'/candles',
            dict(granularity='M5',price='MBA',smooth='false',includeFirst='true',
                 **{'from':iso(start),'to':iso(end-1)}))

    def __https(self,method,host,path,params):
        # Lazy standard-library TLS only. No redirects, proxy inheritance or SDK.
        approved_request(method,host,path,params)
        import http.client
        import ssl
        connection=None
        try:
            deadline=time.monotonic()+30
            connection=http.client.HTTPSConnection(host,timeout=15,context=ssl.create_default_context())
            return _exchange_get(connection,host,path,params,self.__token,deadline)
        except ResearchRejected: raise
        except Exception:
            # Never expose arbitrary SDK/TLS exceptions, headers or error bodies.
            raise OSError('REDACTED_TRANSPORT_FAILURE') from None
        finally:
            if connection is not None: connection.close()


def _exchange_get(connection,host,path,params,token,deadline):
    """Shared wire exchange; no connection factory/host override in the public API.

    Production constructs its normal verified connection above. Only the separate
    synthetic fixture adapter supplies a loopback connection for offline tests.
    """
    from urllib.parse import urlencode
    approved_request('GET',host,path,params)
    if time.monotonic()>=deadline:raise TimeoutError()
    connection.request('GET',path+'?'+urlencode(params),headers={
        'Authorization':'Bearer '+token,'Accept-Datetime-Format':'RFC3339',
        'Accept':'application/json','Accept-Encoding':'identity'})
    response=connection.getresponse()
    if response.status!=200:return Response(response.status,b'',response.getheader('Retry-After'))
    length=getattr(response,'length',None) # existing injected response protocol need not expose framing state
    if length is not None and length>MAX_BODY:raise ResearchRejected('BODY_SIZE_REFUSED')
    chunks=[];size=0
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError()
        if connection.sock is not None:connection.sock.settimeout(min(15,remaining))
        chunk=response.read1(min(65536,MAX_BODY+1-size))
        if not chunk:
            if getattr(response,'length',None) not in (None,0):raise ResearchRejected('INCOMPLETE_HTTP_BODY')
            break
        chunks.append(chunk);size+=len(chunk)
        if size>MAX_BODY:raise ResearchRejected('BODY_SIZE_REFUSED')
    return Response(response.status,b''.join(chunks),content_type=response.getheader('Content-Type',''))
