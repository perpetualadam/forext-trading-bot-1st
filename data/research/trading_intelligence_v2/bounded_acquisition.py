"""Finite branch of the existing one-shot supervisor/worker and journal model.

No transport, credential loader or archive implementation lives here. One fixed
catalogue, one grant, one worker, one token input; every reservation is spent.
"""
import copy
import math
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from .oneshot_archive import Archive,APPROVED,Refused
from .oanda_history_manifest import encoded,decode,digest,validated
from .core import timestamp
from .oanda_history_transport import rate_delay

PACKAGE=Path(__file__).resolve().parent
CATALOGUE=PACKAGE/'reports/v28b/V28B_REQUEST_WINDOWS.json'
CATALOGUE_HASH='2d5f5b38efb65a0cffd5f63ad38a7da62344d653bdba84dad9438cf1eac96bf9'
LIMITS=dict(startup=15,token=120,request=15,session=1800,spacing=1,bytes=256*1024*1024,attempts=106)
FIELDS={'version','mode','root','session','source','catalogue','identity','parent','issued','expires','started','rights','limits'}
_SPEC_BYTES=None
_SPEC_HASHES=None
STATES={'NEVER','RESERVED','ATTEMPTED','COMPLETED','FAILED','UNKNOWN'}


def catalogue():
    global _SPEC_BYTES,_SPEC_HASHES
    raw=CATALOGUE.read_bytes().replace(b'\r\n',b'\n')
    if digest(raw)!=CATALOGUE_HASH:raise Refused('CATALOGUE_CHANGED')
    value=decode(raw);windows=value['windows']
    if len(windows)!=106 or value['calendar_slots']!=105120:raise Refused('CATALOGUE_SCOPE_REFUSED')
    _SPEC_BYTES=tuple(encoded(w['specification']) for w in windows)
    _SPEC_HASHES=tuple(digest(x) for x in _SPEC_BYTES)
    return windows


def spec(index):
    if type(index) is not int or not 0<=index<106:raise Refused('CATALOGUE_INDEX_REFUSED')
    if _SPEC_BYTES is None:catalogue()
    return decode(_SPEC_BYTES[index])


def marker(index):
    if type(index) is not int or not 0<=index<106:raise Refused('CATALOGUE_INDEX_REFUSED')
    return 'temporary_batches/v28c_'+CATALOGUE_HASH+'_'+str(index)+'.json'


def budget_guard(ar,extra,*,accounting=False):
    if type(extra) is not int or extra<0:raise Refused('DISK_BUDGET_REFUSED')
    total=0
    for p in ar.root.rglob('*'):
        if p.is_file():total+=ar.path(p.relative_to(ar.root).as_posix()).stat().st_size
    if ar.namespace_base is not None:
        with Archive(ar.namespace_base,synthetic=ar.synthetic) as parent:
            for i in range(106):
                p=parent.path(marker(i))
                if p.exists():total+=p.stat().st_size
    if total+extra>LIMITS['bytes']-(0 if accounting else 1024*1024):raise Refused('DISK_BUDGET_EXHAUSTED')
    if shutil.disk_usage(ar.root).free<extra+65536:raise Refused('DISK_SPACE_EXHAUSTED')
    return total


def metadata(ar,source):
    return dict(version=2,kind='BOUNDED_106',session=ar.session_id,identity=ar.identity,
                source=source,catalogue=CATALOGUE_HASH,rights=digest(ar.read('rights_scope.json')),
                limits=LIMITS,authorises_execution=False)


def require_prepared(ar,source):
    if ar.session_id is None or decode(ar.read('request.json'))!=metadata(ar,source):raise Refused('BOUNDED_PREPARATION_REFUSED')
    if any(ar.path(n+'.pending').exists() for n in ('request.json','rights_scope.json','session_binding.json')):raise Refused('AMBIGUOUS_PREPARATION')


def rights(ar):
    from .historical_sources import permission
    r=decode(ar.read('rights_scope.json'));permission(r)
    if (r.get('provider')!='OANDA' or r.get('catalogue_sha256')!=CATALOGUE_HASH or
        r.get('scope_reviewed') is not True or r.get('permitted_scope')!='PRIVATE_LOCAL_106_WINDOWS' or
        r.get('public_distribution_allowed') is not False):raise Refused('BOUNDED_RIGHTS_SCOPE_REQUIRED')
    return r


def preflight(ar):
    from .oneshot_authorisation import source_seal,_unused
    require_prepared(ar,source_seal());rights(ar);_unused(ar)
    from .session_namespace import acquisition_lock
    with acquisition_lock(ar):pass
    if shutil.disk_usage(ar.root).free<LIMITS['bytes']:raise Refused('DISK_SPACE_EXHAUSTED')
    with Archive(ar.namespace_base,synthetic=ar.synthetic) as parent:
        for i in range(106):
            if parent.path(marker(i)).exists() or parent.path(marker(i)+'.pending').exists():raise Refused('CATALOGUE_WINDOW_ALREADY_SPENT')
    return True


def confirmation(ar):
    from .oneshot_authorisation import source_seal
    return 'CONFIRM 106 HISTORICAL EUR_USD GETS '+ar.session_id+' '+CATALOGUE_HASH+' '+source_seal()


def issue(ar,*,_fixture=False,fixture_limits=None,_proof=None):
    from . import oneshot_authorisation as a
    if _fixture:
        if not ar.synthetic:raise Refused('SYNTHETIC_ARCHIVE_REQUIRED')
    elif _proof not in a._CONFIRMATIONS:raise Refused('TERMINAL_CONFIRMATION_REQUIRED')
    if not _fixture and (ar.synthetic or ar.namespace_base!=Path(APPROVED)):raise Refused('APPROVED_ROOT_REQUIRED')
    preflight(ar);now=time.time();started=time.monotonic();limits=dict(LIMITS)
    if _fixture and fixture_limits:
        if set(fixture_limits)-{'startup','token','request','session','spacing'}:raise Refused('FIXTURE_LIMITS_REFUSED')
        limits.update(fixture_limits)
    if not _fixture:
        proof=a._CONFIRMATIONS.pop(_proof,None)
        if proof!=(a.source_seal(),ar.session_id,CATALOGUE_HASH,106,os.getpid(),digest(encoded(ar.identity)),digest(ar.read('rights_scope.json'))):raise Refused('BOUNDED_CONFIRMATION_REFUSED')
    cap=dict(version=4,mode='OFFLINE_TEST' if _fixture else 'LIVE',root=str(ar.root),session=ar.session_id,
             source=a.source_seal(),catalogue=CATALOGUE_HASH,identity=digest(encoded(ar.identity)),parent=os.getpid(),
             issued=now,expires=now+limits['startup']+limits['token']+limits['session'],started=started,
             rights=digest(ar.read('rights_scope.json')),limits=limits)
    ar.put('grant.json',encoded(cap))
    ar.put('journal.json',encoded(dict(version=3,session=ar.session_id,source=cap['source'],catalogue=CATALOGUE_HASH,
        state='AUTHORISED_NOT_CONSUMED',attempts=0,next=0,windows=[dict(index=i,spec=digest(encoded(spec(i))),state='NEVER',http_attempts=0) for i in range(106)])))
    return cap


def issue_interactively(ar):
    from . import oneshot_authorisation as a
    if os.name!='nt' or not sys.stdin.isatty() or not sys.stdout.isatty():raise Refused('INTERACTIVE_TERMINAL_REQUIRED')
    preflight(ar);approved_source=a.source_seal();approved_rights=digest(ar.read('rights_scope.json'));approved_identity=digest(encoded(ar.identity))
    phrase=confirmation(ar)
    print('106 fixed EUR_USD M5/MBA GETs; one token entry; 256 MiB; 1800-second finite acquisition deadline.')
    print('2024-09-01T00:00:00Z to 2025-09-01T00:00:00Z exclusive. No retry/resume. No trading.')
    print('Rights: '+a.RIGHTS_PHRASE);print('Endpoint: '+a.ENDPOINT_PHRASE);print('Confirmation: '+phrase)
    if input('Rights attestation: ')!=a.RIGHTS_PHRASE:raise Refused('DATA_USE_CONDITIONS_NOT_CONFIRMED')
    if input('Endpoint acknowledgement: ')!=a.ENDPOINT_PHRASE:raise Refused('ENDPOINT_CONDITIONS_NOT_CONFIRMED')
    a.read_confirmation(phrase)
    if a.source_seal()!=approved_source or digest(ar.read('rights_scope.json'))!=approved_rights or digest(encoded(ar.identity))!=approved_identity:raise Refused('STALE_BOUNDED_APPROVAL')
    proof=os.urandom(16).hex();a._CONFIRMATIONS[proof]=(approved_source,ar.session_id,CATALOGUE_HASH,106,os.getpid(),approved_identity,approved_rights)
    try:
        with ar.locked():return issue(ar,_proof=proof)
    finally:a._CONFIRMATIONS.pop(proof,None)


def ledger(ar,cap):
    if _SPEC_BYTES is None:catalogue()
    value=decode(ar.read('journal.json'))
    if (set(value)!={'version','session','source','catalogue','state','attempts','next','windows'} or
        value['version']!=3 or value['session']!=cap['session'] or value['source']!=cap['source'] or
        value['catalogue']!=CATALOGUE_HASH or type(value['attempts']) is not int or not 0<=value['attempts']<=106 or
        type(value['next']) is not int or not 0<=value['next']<=106 or len(value['windows'])!=106):raise Refused('BOUNDED_JOURNAL_REFUSED')
    spent=completed=0
    for i,w in enumerate(value['windows']):
        if (type(w.get('index')) is not int or w.get('index')!=i or w.get('spec')!=_SPEC_HASHES[i] or w.get('state') not in STATES or
            type(w.get('http_attempts')) is not int or w['http_attempts'] not in (0,1)):raise Refused('WINDOW_STATE_REFUSED')
        if w['state'] in ('NEVER','RESERVED') and w['http_attempts']!=0 or w['state']=='COMPLETED' and w['http_attempts']!=1:raise Refused('WINDOW_ATTEMPT_INCONSISTENT')
        if w['state']!='NEVER':spent+=1
        if w['state']=='COMPLETED':completed+=1
        if i<value['next'] and w['state']!='COMPLETED':raise Refused('PREDECESSOR_NOT_COMPLETED')
        if i>value['next'] and w['state']!='NEVER':raise Refused('OUT_OF_ORDER_WINDOW')
    if value['attempts']!=spent or value['next']!=completed:raise Refused('REQUEST_BUDGET_INCONSISTENT')
    if any(ar.path(n+'.pending').exists() for n in ('grant.json','grant.claimed.json','journal.json','worker.claimed.json','acquisition.json','result.json')):raise Refused('AMBIGUOUS_PUBLICATION')
    return value


def verify(cap):
    from .oneshot_authorisation import source_seal
    if (type(cap) is not dict or set(cap)!=FIELDS or cap['version']!=4 or cap['mode'] not in ('LIVE','OFFLINE_TEST') or
        cap['catalogue']!=CATALOGUE_HASH or cap['source']!=source_seal() or
        type(cap['session']) is not str or not re.fullmatch('[0-9a-f]{32}',cap['session']) or
        type(cap['parent']) is not int or cap['parent']<=0 or type(cap['limits']) is not dict or set(cap['limits'])!=set(LIMITS)):
        raise Refused('BOUNDED_GRANT_REFUSED')
    limits=cap['limits']
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in limits.values()):raise Refused('BOUNDED_LIMITS_REFUSED')
    if (limits['attempts']!=106 or limits['bytes']!=LIMITS['bytes'] or cap['mode']=='LIVE' and limits!=LIMITS or
        any(limits[k]>LIMITS[k] for k in LIMITS)):raise Refused('BOUNDED_LIMITS_REFUSED')
    lifetime=limits['startup']+limits['token']+limits['session']
    if (any(type(cap[k]) not in (int,float) or not math.isfinite(cap[k]) for k in ('started','issued','expires')) or
        cap['expires']-cap['issued']!=lifetime or not cap['issued']<=time.time()<cap['expires'] or
        not 0<=time.monotonic()-cap['started']<=lifetime):raise Refused('BOUNDED_SESSION_EXPIRED')
    if cap['mode']=='LIVE' and cap['root']!=str(Path(APPROVED)/'sessions'/cap['session']):raise Refused('BOUNDED_ROOT_REFUSED')
    with Archive(cap['root'],synthetic=cap['mode']=='OFFLINE_TEST') as ar:
        require_prepared(ar,cap['source']);rights(ar)
        if cap['session']!=ar.session_id:raise Refused('BOUNDED_SESSION_SUBSTITUTED')
        if cap['identity']!=digest(encoded(ar.identity)) or cap['rights']!=digest(ar.read('rights_scope.json')):raise Refused('BOUNDED_IDENTITY_CHANGED')
        claimed=ar.path('grant.claimed.json').exists()
        if decode(ar.read('grant.claimed.json' if claimed else 'grant.json'))!=cap:raise Refused('BOUNDED_GRANT_SUBSTITUTED')
        state=ledger(ar,cap)
        if state['state'] not in ('AUTHORISED_NOT_CONSUMED','REQUEST_RESERVED','ACTIVE'):raise Refused('BOUNDED_SESSION_CONSUMED')
        if (state['state']=='AUTHORISED_NOT_CONSUMED')==claimed:raise Refused('AMBIGUOUS_GRANT_STATE')
        if state['state']!='ACTIVE' and time.monotonic()>=cap['started']+limits['startup']:raise Refused('PREPARATION_DEADLINE_EXHAUSTED')
    return cap


def role(cap,purpose,*,worker_pid=None):
    verify(cap)
    with Archive(cap['root'],synthetic=cap['mode']=='OFFLINE_TEST') as ar:
        state=ledger(ar,cap)
        if purpose=='preflight':return cap
        if purpose=='worker_claim':
            if state['state']!='REQUEST_RESERVED' or os.getppid()!=cap['parent'] or ar.path('worker.claimed.json').exists():raise Refused('BOUNDED_WORKER_CLAIM_REFUSED')
            return cap
        worker=decode(ar.read('worker.claimed.json'))
        if worker.get('session')!=cap['session'] or worker.get('source')!=cap['source'] or worker.get('parent')!=cap['parent'] or type(worker.get('pid')) is not int:raise Refused('BOUNDED_WORKER_REFUSED')
        token_deadline=worker.get('credential_deadline')
        if type(token_deadline) not in (int,float) or not math.isfinite(token_deadline) or not cap['started']+cap['limits']['token']<=token_deadline<=cap['started']+cap['limits']['startup']+cap['limits']['token']:raise Refused('TOKEN_DEADLINE_BINDING_REFUSED')
        if purpose=='credential':
            if os.getpid()!=cap['parent'] or worker_pid not in (None,worker['pid']) or ar.path('acquisition.json').exists() or time.monotonic()>=worker['credential_deadline']:raise Refused('TOKEN_ENTRY_TIMEOUT')
            return cap
        if purpose not in ('network','fixture_dispatch') or worker['pid']!=os.getpid() or worker['parent']!=os.getppid():raise Refused('BOUNDED_PROCESS_REFUSED')
        if purpose=='network' and cap['mode']!='LIVE' or purpose=='fixture_dispatch' and cap['mode']!='OFFLINE_TEST':raise Refused('FIXTURE_CANNOT_AUTHORISE_LIVE')
        phase(ar,cap)
        index=state['next']
        if index>=106 or state['windows'][index]['state']!='ATTEMPTED' or state['windows'][index]['http_attempts']!=1:raise Refused('DURABLE_WINDOW_RESERVATION_REQUIRED')
        w=state['windows'][index]
        if (w.get('worker')!=worker['pid'] or any(type(w.get(k)) not in (int,float) or not math.isfinite(w[k]) for k in ('started','deadline','dispatched')) or
            w['deadline']!=min(w['started']+cap['limits']['request'],phase(ar,cap)['deadline']) or
            not w['started']<=w['dispatched']<w['deadline'] or time.monotonic()>=w['deadline']-min(1,cap['limits']['request']/3)):raise Refused('WINDOW_DEADLINE')
    return cap


def request_for(cap):
    role(cap,'network' if cap['mode']=='LIVE' else 'fixture_dispatch')
    with Archive(cap['root'],synthetic=cap['mode']=='OFFLINE_TEST') as ar:return spec(ledger(ar,cap)['next'])


def network_key(cap):
    request_for(cap)
    with Archive(cap['root'],synthetic=cap['mode']=='OFFLINE_TEST') as ar:return (cap['session'],ledger(ar,cap)['next'])


def guard(cap,request):
    if encoded(request)!=encoded(request_for(cap)):raise Refused('BOUNDED_EXACT_REQUEST_REQUIRED')
    return True


def phase(ar,cap):
    p=decode(ar.read('acquisition.json'));worker=decode(ar.read('worker.claimed.json'))
    if (set(p)!={'session','source','parent','worker','started','deadline'} or
        any(type(p[k]) not in (int,float) or not math.isfinite(p[k]) for k in ('started','deadline')) or
        p['session']!=cap['session'] or p['source']!=cap['source'] or p['parent']!=cap['parent'] or p['worker']!=worker['pid'] or
        not cap['started']<=p['started']<=time.monotonic() or p['started']>=worker['credential_deadline'] or
        p['deadline']!=p['started']+cap['limits']['session'] or time.monotonic()>=p['deadline']-1):raise Refused('BOUNDED_SESSION_DEADLINE')
    return p


def verify_completed(ar,cap,index):
    state=ledger(ar,cap);w=state['windows'][index]
    if w['state']!='COMPLETED' or w['http_attempts']!=1:raise Refused('WINDOW_NOT_COMPLETED')
    name='v26c_year_'+str(index).zfill(3);r=decode(ar.read('manifests/'+name+'.json'))
    if (r.get('raw')!='raw/'+name+'.json' or r.get('validated')!='validated/'+name+'.json' or r.get('index')!=index or r.get('session')!=cap['session'] or r.get('source')!=cap['source'] or r.get('catalogue')!=CATALOGUE_HASH or
        r.get('synthetic')!=(cap['mode']=='OFFLINE_TEST') or r.get('request_sha256')!=digest(ar.read('request.json')) or r.get('identity')!=cap['identity'] or r.get('start')!=timestamp(spec(index)['params']['from']) or r.get('end')!=timestamp(spec(index)['params']['to'])+1 or r.get('spec_sha256')!=digest(encoded(spec(index))) or r.get('raw_sha256')!=digest(ar.read(r['raw'])) or
        r.get('validated_sha256')!=digest(ar.read(r['validated'])) or w.get('manifest_sha256')!=digest(ar.read('manifests/'+name+'.json'))):raise Refused('COMPLETED_WINDOW_CORRUPTED')
    return r


def claim_window(ar,cap,index,worker_pid):
    verify(cap);phase(ar,cap);state=ledger(ar,cap)
    if os.getpid()!=cap['parent'] or state['state']!='ACTIVE' or state['next']!=index or state['attempts']>=106 or state['windows'][index]['state']!='NEVER':raise Refused('WINDOW_ALREADY_SPENT_OR_BUDGET_EXHAUSTED')
    for previous in range(index):verify_completed(ar,cap,previous)
    with Archive(ar.namespace_base,synthetic=ar.synthetic) as parent:
        for previous in range(index):
            if parent.path(marker(previous)+'.pending').exists() or digest(parent.read(marker(previous)))!=state['windows'][previous].get('marker_sha256'):raise Refused('SPENT_MARKER_CORRUPTED')
    started=time.monotonic();value=encoded(dict(session=cap['session'],catalogue=CATALOGUE_HASH,index=index,spec=digest(encoded(spec(index))),state='RESERVED'))
    with Archive(ar.namespace_base,synthetic=ar.synthetic) as parent:
        if parent.path(marker(index)).exists() or parent.path(marker(index)+'.pending').exists():raise Refused('CATALOGUE_WINDOW_ALREADY_SPENT')
        parent.publication_guard=lambda relative,data:budget_guard(ar,len(data))
        marker_sha=parent.put(marker(index),value)
    state['windows'][index].update(state='RESERVED',worker=worker_pid,started=started,deadline=min(started+cap['limits']['request'],phase(ar,cap)['deadline']),marker_sha256=marker_sha)
    state['attempts']+=1;ar.put('journal.json',encoded(state),replace=True)
    return state['windows'][index]


def worker_main(packet,emit,scope):
    start=packet(4096);cap=start['reservation'];fixture=cap.get('mode')=='OFFLINE_TEST';fault=start.get('fault','')
    if cap.get('version')!=4 or (fault and not fixture):raise Refused('BOUNDED_WORKER_ENTRY_REFUSED')
    allowed={'','crash_before_dispatch','crash_during_dispatch','crash_after_response','stall_after_response','invalid_schema','credential_echo'}
    if fault not in allowed:raise Refused('FIXTURE_FAULT_REFUSED')
    root=Path(cap['root']).absolute();scope.configure_session_reads(root)
    if str(root)!=start['root']:raise Refused('BOUNDED_ROOT_REFUSED')
    verify(cap);role(cap,'worker_claim')
    scope.ACTIVE_ROOT=root;scope.LIVE_APPROVED=not fixture
    if fixture:
        from .oneshot_https_fixture import validate_binding
        validate_binding(start['https_fixture']);scope.LOOPBACK_PORT=start['https_fixture']['port']
    elif 'https_fixture' in start:raise Refused('LIVE_CANNOT_USE_FIXTURE')
    secret=None
    with Archive(root,synthetic=fixture,pin=start['pin']) as ar,ar.locked():
        ar.put('worker.claimed.json',encoded(dict(session=cap['session'],source=cap['source'],pid=os.getpid(),parent=os.getppid(),credential_deadline=time.monotonic()+cap['limits']['token'])))
        state=ledger(ar,cap);state['state']='ACTIVE';ar.put('journal.json',encoded(state),replace=True);emit({'kind':'RESERVED'})
        try:
            secret=packet(1024)['credential']
            from .oneshot_credentials import validate_token
            validate_token(secret)
            if fixture:
                from .oneshot_bridge import validate_synthetic
                validate_synthetic(secret)
            phase(ar,cap);last_started=None
            for index in range(106):
                p=phase(ar,cap)
                if last_started is not None:
                    wait=rate_delay(last_started+cap['limits']['spacing'])
                    # Same conservative pacing as CandleTransport; wait is part
                    # of the finite session and never extends either deadline.
                    if time.monotonic()+wait>=p['deadline']-1:raise Refused('BOUNDED_SESSION_DEADLINE')
                    threading.Event().wait(wait)
                emit({'kind':'NEED_WINDOW','index':index})
                if packet()!=dict(reserved=index):raise Refused('WINDOW_RESERVATION_ACK_REFUSED')
                state=ledger(ar,cap);w=state['windows'][index]
                if state['next']!=index or w['state']!='RESERVED' or w['worker']!=os.getpid():raise Refused('DURABLE_WINDOW_RESERVATION_REQUIRED')
                if fault=='crash_before_dispatch':os._exit(123)
                if last_started is not None and time.monotonic()-last_started<cap['limits']['spacing']:raise Refused('RATE_LIMIT_REFUSED')
                state['windows'][index].update(state='ATTEMPTED',http_attempts=1,dispatched=time.monotonic())
                ar.put('journal.json',encoded(state),replace=True);last_started=state['windows'][index]['dispatched'];emit({'kind':'WINDOW_STARTED','index':index})
                request=spec(index);guard(cap,request);deadline=w['deadline']-min(1,cap['limits']['request']/3)
                if fault=='crash_during_dispatch':os._exit(123)
                if fixture:
                    from .oneshot_network import fetch_synthetic
                    raw=fetch_synthetic(start['https_fixture'],secret,deadline,request=request,_bounded=cap)
                else:
                    from .oneshot_network import LiveSocketPolicy,fetch_live
                    scope.LIVE_POLICY=LiveSocketPolicy(cap)
                    raw=fetch_live(reservation=cap,token=secret,deadline=deadline,_policy=scope.LIVE_POLICY)
                # Pace from response completion, conservatively guaranteeing spacing
                # between actual requests even when pre-dispatch validation varies.
                last_started=time.monotonic()
                if fault=='crash_after_response':os._exit(123)
                if fault=='stall_after_response':threading.Event().wait()
                if fault=='invalid_schema':raw=b'{}'
                if fault=='credential_echo':raw=secret.encode()
                if secret.encode() in raw:raise Refused('CREDENTIAL_RESPONSE_REFUSED')
                begin=timestamp(request['params']['from']);end=timestamp(request['params']['to'])+1;retrieved=time.time()
                rows,report=validated(raw,'EUR_USD',begin,end,retrieved)
                if not rows or report['incomplete']:raise Refused('EMPTY_OR_INCOMPLETE_BATCH_REFUSED')
                guard(cap,request)
                from .oneshot_response import publish_candles
                name='v26c_year_'+str(index).zfill(3)
                publish_candles(ar,raw,name=name,start=begin,end=end,retrieved=retrieved,synthetic=fixture,_bounded=(cap,index))
                state=ledger(ar,cap)
                if time.monotonic()>=w['deadline']-min(1,cap['limits']['request']/3):raise Refused('WINDOW_DEADLINE')
                state['windows'][index].update(state='COMPLETED',manifest_sha256=digest(ar.read('manifests/'+name+'.json')),finished=time.monotonic())
                state['next']=index+1;ar.put('journal.json',encoded(state),replace=True);emit({'kind':'WINDOW_DONE','index':index})
                if packet()!=dict(continue_after=index):raise Refused('WINDOW_CONTINUATION_REFUSED')
            phase(ar,cap);emit({'kind':'DONE','completed':106})
        except BaseException as error:
            # Fixed, redacted classification only; raw/token/exception text never
            # enters a durable failure record or the parent protocol.
            emit({'kind':'REFUSED','cause':type(error).__name__})
            raise
        finally:secret=None


def run(ar,cap,provider,*,https_fixture=None,fault=''):
    """Finite mode of the existing supervisor. No HTTP code or credential cache."""
    from .oneshot import WORKER,_readlines
    from .oneshot_bridge import SyntheticCredentialProvider
    from .direct_history import TerminalCredentialProvider
    from .oneshot_credentials import validate_token
    from .session_namespace import acquisition_lock,block_unfenced
    verify(cap)
    fixture=cap['mode']=='OFFLINE_TEST'
    if os.getpid()!=cap['parent'] or (fixture and type(provider) is not SyntheticCredentialProvider) or (not fixture and (type(provider) is not TerminalCredentialProvider or https_fixture is not None or fault)):
        raise Refused('BOUNDED_PROVIDER_REFUSED')
    if fixture:
        from .oneshot_https_fixture import validate_binding
        validate_binding(https_fixture)
    process=job=None;messages=queue.Queue();result={'kind':'OUTCOME_UNKNOWN'};claimed=False;token_sent=False
    deadline=cap['started']+cap['limits']['startup'];work_deadline=deadline-min(1,cap['limits']['startup']/3)
    with acquisition_lock(ar) as lease:
        def check_lock():
            parent=ar.namespace_base/'historical_acquisition.lock'
            if lease is None or lease.closed or (os.fstat(lease.fileno()).st_dev,os.fstat(lease.fileno()).st_ino)!=(parent.stat().st_dev,parent.stat().st_ino):raise Refused('GLOBAL_LOCK_LOST')
        try:
            check_lock()
            with ar.locked():
                state=ledger(ar,cap)
                if state['state']!='AUTHORISED_NOT_CONSUMED' or ar.path('grant.claimed.json').exists():raise Refused('BOUNDED_SESSION_CONSUMED')
                ar.rename('grant.json','grant.claimed.json');claimed=True;state['state']='REQUEST_RESERVED';ar.put('journal.json',encoded(state),replace=True)
            exe=getattr(sys,'_base_executable',sys.executable) if os.name=='nt' else sys.executable
            process=subprocess.Popen([exe,'-I','-S','-B',str(WORKER),'--bounded-worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                     env={'SystemRoot':r'C:\Windows'} if os.name=='nt' else {},start_new_session=os.name!='nt',close_fds=True)
            if os.name=='nt':
                from .oneshot_windows import Job
                job=Job(process)
            threading.Thread(target=_readlines,args=(process.stdout,messages),daemon=True).start()
            def send(value,limit=4096):
                body=encoded(value)
                if len(body)>limit:raise Refused('BOUNDED_PACKET_TOO_LARGE')
                process.stdin.write(body);process.stdin.flush()
            startup=dict(root=str(ar.root),pin=ar.identity,reservation=cap,fault=fault)
            if fixture:startup['https_fixture']=https_fixture
            send(startup)
            while time.monotonic()<work_deadline:
                check_lock()
                try:message=messages.get(timeout=min(.02,max(.001,work_deadline-time.monotonic())))
                except queue.Empty:
                    if process.poll() is not None:break
                    continue
                kind=message.get('kind')
                if kind=='RESERVED':
                    if token_sent:raise Refused('DUPLICATE_TOKEN_REQUEST')
                    role(cap,'credential',worker_pid=process.pid);worker=decode(ar.read('worker.claimed.json'))
                    deadline=worker['credential_deadline'];work_deadline=deadline
                    token=provider.credential() if fixture else provider.credential(cap,deadline=deadline)
                    validate_token(token)
                    if time.monotonic()>=deadline:raise Refused('TOKEN_ENTRY_TIMEOUT')
                    role(cap,'credential',worker_pid=process.pid)
                    started=time.monotonic();deadline=started+cap['limits']['session'];work_deadline=deadline-1
                    ar.put('acquisition.json',encoded(dict(session=cap['session'],source=cap['source'],parent=os.getpid(),worker=process.pid,started=started,deadline=deadline)))
                    send(dict(credential=token),1024);token=None;token_sent=True
                elif kind=='NEED_WINDOW':
                    if not token_sent:raise Refused('TOKEN_NOT_ENTERED')
                    w=claim_window(ar,cap,message.get('index'),process.pid)
                    deadline=min(w['deadline'],phase(ar,cap)['deadline']);work_deadline=deadline-min(1,cap['limits']['request']/3)
                    send(dict(reserved=message['index']))
                elif kind=='WINDOW_STARTED':
                    if message.get('index')!=ledger(ar,cap)['next']:raise Refused('WINDOW_INDEX_CHANGED')
                elif kind=='WINDOW_DONE':
                    verify(cap);verify_completed(ar,cap,message.get('index'));phase(ar,cap)
                    if time.monotonic()>=work_deadline:raise Refused('WINDOW_DEADLINE')
                    send(dict(continue_after=message['index']))
                    deadline=phase(ar,cap)['deadline'];work_deadline=deadline-1
                elif kind=='DONE':
                    state=ledger(ar,cap)
                    if state['next']!=106 or state['attempts']!=106 or message.get('completed')!=106:raise Refused('INCOMPLETE_CATALOGUE')
                    result={'kind':'DONE','completed':106};break
                elif kind=='REFUSED':result={'kind':'FAILED' if message.get('cause')=='ResearchRejected' else 'OUTCOME_UNKNOWN'};break
                else:raise Refused('BOUNDED_WORKER_PROTOCOL_REFUSED')
        except BaseException as error:
            result={'kind':'TOKEN_ENTRY_TIMEOUT' if type(error) is Refused and str(error)=='TOKEN_ENTRY_TIMEOUT' else 'OUTCOME_UNKNOWN'}
            if result['kind']=='TOKEN_ENTRY_TIMEOUT':
                # No acquisition starts after input expires. A separate one-second
                # fencing allowance preserves the input refusal classification.
                deadline=time.monotonic()+1
        finally:
            token=None
            if process is not None:
                if job is not None:
                    try:job.kill()
                    except Exception:result={'kind':'FENCING_UNCONFIRMED'}
                    finally:job.close()
                elif process.poll() is None:
                    if os.name=='nt':process.kill()
                    else:
                        try:os.killpg(process.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                try:process.wait(timeout=max(.001,deadline-time.monotonic()))
                except subprocess.TimeoutExpired:result={'kind':'FENCING_UNCONFIRMED'}
                for pipe in (process.stdin,process.stdout) if process.poll() is not None else ():
                    if pipe:pipe.close()
            result['worker_exited']=process is None or process.poll() is not None
            if time.monotonic()>deadline:result['kind']='DEADLINE_OVERRUN'
            if claimed:
                if not result['worker_exited'] or result['kind']=='FENCING_UNCONFIRMED':block_unfenced(ar,cap)
                state=ledger(ar,cap)
                if state['next']<106 and state['windows'][state['next']]['state'] in ('RESERVED','ATTEMPTED'):
                    state['windows'][state['next']]['state']='FAILED' if result['kind']=='FAILED' else 'UNKNOWN'
                state['state']='SESSION_CONSUMED' if result['kind']=='DONE' else 'OUTCOME_UNKNOWN'
                ar.put('journal.json',encoded(state),replace=True)
                ar.put('result.json',encoded(dict(version=1,session=cap['session'],source=cap['source'],catalogue=CATALOGUE_HASH,kind=result['kind'],attempts=state['attempts'],completed=state['next'],worker_exited=result['worker_exited'],grant_sha256=digest(ar.read('grant.claimed.json')))))
    return result
