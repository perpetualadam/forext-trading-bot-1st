"""Exact one-shot supervisor with source-bound interactive real admission.

No trading capability. The real branch requires the exact native grant, durable
reservation, worker identity and terminal-only credential delivery.
"""
import json
import math
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from .oneshot_archive import Archive,Refused
from .oanda_history_manifest import encoded,digest,decode

SPEC={'method':'GET','host':'api-fxtrade.oanda.com','path':'/v3/instruments/EUR_USD/candles',
      'params':{'from':'2026-09-02T10:00:00Z','to':'2026-09-02T10:49:59Z',
                'granularity':'M5','price':'MBA','smooth':'false','includeFirst':'true'}}
SPEC_HASH=digest(encoded(SPEC))
WORKER=Path(__file__).with_name('oneshot_worker.py').resolve()
STATES={'NOT_AUTHORISED','AUTHORISED_NOT_CONSUMED','REQUEST_RESERVED','REQUEST_ATTEMPTED',
        'RESPONSE_RECEIVED','REQUEST_FAILED','OUTCOME_UNKNOWN','SESSION_CONSUMED'}


def request_guard(method,host,path,params,*,headers=None,proxy=None):
    try:match=digest(encoded({'method':method,'host':host,'path':path,'params':params}))==SPEC_HASH
    except (TypeError,ValueError,OverflowError):match=False
    if not match or headers not in (None,{}) or proxy is not None:raise Refused('EXACT_REQUEST_REQUIRED')
    return True


def initialise(archive):
    """Only an unapproved session; no code here creates a permission grant."""
    archive.put('journal.json',encoded({'version':1,'state':'NOT_AUTHORISED','spec':SPEC_HASH,'attempts':0}))


def journal(archive):
    value=decode(archive.read('journal.json'))
    if (type(value) is not dict or set(value)!={'version','state','spec','attempts'} or
        type(value['version']) is not int or value['version']!=1 or value['spec']!=SPEC_HASH or
        not isinstance(value['state'],str) or value['state'] not in STATES or
        type(value['attempts']) is not int or value['attempts'] not in (0,1)):
        raise Refused('INVALID_JOURNAL')
    return value


def transition(archive,state,attempts):
    allowed={'AUTHORISED_NOT_CONSUMED':('REQUEST_RESERVED',0),
             'REQUEST_RESERVED':('REQUEST_ATTEMPTED',1),
             'REQUEST_ATTEMPTED':('RESPONSE_RECEIVED',1),
             'RESPONSE_RECEIVED':('SESSION_CONSUMED',1)}
    previous=journal(archive)
    if type(attempts) is not int or allowed.get(previous['state'])!=(state,attempts):
        raise Refused('STATE_TRANSITION_REFUSED')
    archive.put('journal.json',encoded({'version':1,'state':state,'spec':SPEC_HASH,'attempts':attempts}),replace=True)


def reserve(archive,checkpoint=lambda phase:None,*,_live_reservation=None):
    """Caller holds OS lock until worker completion. No reset/recovery path.

    A claimed grant is immutable consumed evidence even if the next journal
    publication tears. An interrupted .pending file also refuses further writes.
    """
    if _live_reservation is not None:
        from .oneshot_authorisation import require_live_reservation
        require_live_reservation(_live_reservation)
    value=journal(archive)
    if value['state']!='AUTHORISED_NOT_CONSUMED' or value['attempts']!=0:raise Refused('SESSION_NOT_UNUSED')
    if archive.path('grant.claimed.json').exists():raise Refused('GRANT_ALREADY_CLAIMED')
    grant=decode(archive.read('grant.json'))
    # Only synthetic grants are understood at this stage. No grant schema for
    # authenticated execution is accepted until separate evidence review.
    if _live_reservation is not None:
        from .oneshot_authorisation import require_live_reservation
        require_live_reservation({'reservation':_live_reservation,'grant':grant,
                                 'identity':archive.identity,'spec':SPEC_HASH})
        if archive.synthetic!=(_live_reservation.get('mode')=='OFFLINE_TEST'):raise Refused('GRANT_SCOPE_REFUSED')
    elif (not archive.synthetic or type(grant) is not dict or grant.get('synthetic') is not True or
          grant!={'synthetic':True,'spec':SPEC_HASH,'identity':archive.identity}):
        raise Refused('AUTHORISATION_NOT_APPROVED')
    archive.rename('grant.json','grant.claimed.json')
    with archive.path('grant.claimed.json').open('r+b') as stream:os.fsync(stream.fileno())
    checkpoint('before_reservation')
    transition(archive,'REQUEST_RESERVED',0)
    checkpoint('after_reservation')


def _readlines(pipe,messages):
    try:
        while True:
            line=pipe.readline(4097)
            if not line:return
            if len(line)>4096:messages.put({'kind':'INVALID_WORKER_MESSAGE'});return
            value=json.loads(line)
            if type(value) is not dict:raise ValueError()
            messages.put(value)
    except Exception:messages.put({'kind':'INVALID_WORKER_MESSAGE'})


def claim_reserved_worker(archive,reservation):
    """Real-only one-use worker claim using the original journal, no new ledger.

    Supervisor reserved before Popen. The worker holds the original archive lock
    and consumes the only attempt before asking for credentials. A second worker
    cannot enter this state, including after failure before network dispatch.
    """
    from .oneshot_authorisation import require_live_reservation
    require_live_reservation(reservation)
    require_live_reservation({'reservation':reservation,'identity':archive.identity,
                             'claimed_grant':decode(archive.read('grant.claimed.json'))})
    fixture=type(reservation) is dict and reservation.get('mode')=='OFFLINE_TEST'
    if archive.synthetic!=fixture or journal(archive)['state']!='REQUEST_RESERVED' or journal(archive)['attempts']!=0:
        raise Refused('SESSION_NOT_UNUSED')
    from .oneshot_authorisation import admitted,bind_worker
    if admitted(reservation):bind_worker(archive,reservation)
    transition(archive,'REQUEST_ATTEMPTED',1)


def run_once(root,*,synthetic_secret,seconds=15.0,fault='',pin=None,
             _credential_provider=None,_https_fixture=None,_started=None,_live_reservation=None):
    """Fenced bridge with synthetic entry and a source-bound real branch.

    Synthetic archive I/O occurs in the child. The dormant real branch reserves
    in the supervisor before worker startup and holds native identity handles.
    The process fence is attached before startup or the in-memory secret is sent.
    Cleanup time is reserved inside the requested total budget. OS scheduling and
    uninterruptible kernel operations are not a hard real-time guarantee.
    """
    now=time.monotonic()
    if _started is None and type(_live_reservation) is dict:_started=_live_reservation.get('started',now)
    started=now if _started is None else _started
    if type(started) not in (int,float) or not math.isfinite(started) or started>now:
        raise Refused('INVALID_START_TIME')
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0.5<=seconds<=15:
        raise Refused('INVALID_DEADLINE')
    from .oneshot_bridge import SyntheticCredentialProvider,validate_synthetic
    live=_live_reservation is not None
    from .oneshot_authorisation import admitted
    phased=live and admitted(_live_reservation)
    fixture_live=live and type(_live_reservation) is dict and _live_reservation.get('mode')=='OFFLINE_TEST'
    if live:
        from .oneshot_authorisation import require_live_reservation
        from .oneshot_credentials import ReservedCredentialProvider
        require_live_reservation(_live_reservation)
        from .direct_history import TerminalCredentialProvider
        if fixture_live:
            from .oneshot_https_fixture import validate_binding
            if type(_credential_provider) is not SyntheticCredentialProvider:raise Refused('SYNTHETIC_PROVIDER_REQUIRED')
            validate_binding(_https_fixture)
        elif type(_live_reservation) is dict and type(_credential_provider) is not TerminalCredentialProvider:
            raise Refused('TERMINAL_CREDENTIALS_REQUIRED')
        if ((not fixture_live and seconds!=15) or type(_credential_provider) not in (ReservedCredentialProvider,TerminalCredentialProvider,SyntheticCredentialProvider) or synthetic_secret is not None or
            (not fixture_live and (_https_fixture is not None or fault))):raise Refused('AUTHENTICATED_EXECUTION_DISABLED')
    elif _credential_provider is None:validate_synthetic(synthetic_secret)
    elif type(_credential_provider) is not SyntheticCredentialProvider or synthetic_secret is not None:
        raise Refused('SYNTHETIC_PROVIDER_REQUIRED')
    if fault not in FAULTS:raise Refused('UNKNOWN_FIXTURE_FAULT')
    deadline=started+(15 if phased else seconds);work_deadline=deadline-min(1.0,seconds/3)
    acquisition_started=None
    process=None;job=None;native_archive=None;messages=queue.Queue();result={'kind':'OUTCOME_UNKNOWN'}
    try:
        if live:
            # No worker exists until the exact native archive has durably claimed
            # the grant. Retain identity handles through the entire fenced run.
            native_archive=Archive(root,synthetic=fixture_live,pin=pin)
            with native_archive.locked():reserve(native_archive,_live_reservation=_live_reservation)
            if time.monotonic()>=work_deadline:raise Refused('PREPARATION_DEADLINE_EXHAUSTED')
        # Winsock needs the OS bootstrap directory even in an otherwise empty
        # Windows child environment. No parent variables or credentials copied.
        child_env={'SystemRoot':r'C:\Windows'} if os.name=='nt' and (_https_fixture is not None or live) else {}
        # Windows venv redirectors introduce an intermediate PID. Admitted
        # sessions need the direct trusted interpreter for exact worker binding.
        worker_exe=getattr(sys,'_base_executable',sys.executable) if live and os.name=='nt' else sys.executable
        process=subprocess.Popen([worker_exe,'-I','-S','-B',str(WORKER),'--worker'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            env=child_env,start_new_session=os.name!='nt',close_fds=True)
        if os.name=='nt':
            from .oneshot_windows import Job
            job=Job(process)
        threading.Thread(target=_readlines,args=(process.stdout,messages),daemon=True).start()
        def send(value):
            raw=encoded(value)
            if len(raw)>2048:raise Refused('WORKER_PACKET_TOO_LARGE')
            process.stdin.write(raw);process.stdin.flush()
        startup={'root':str(Path(root).absolute()),'fault':fault,'pin':pin}
        if live:startup.update(live_reservation=_live_reservation,deadline=work_deadline)
        if _https_fixture is not None:startup.update(https_fixture=_https_fixture,deadline=work_deadline)
        send(startup)
        credential_sent=False
        while time.monotonic()<work_deadline:
            try:message=messages.get(timeout=min(.02,max(0.001,work_deadline-time.monotonic())))
            except queue.Empty:
                if process.poll() is not None:
                    # Give the reader its bounded opportunity to drain the pipe.
                    try:message=messages.get(timeout=min(.02,max(.001,work_deadline-time.monotonic())))
                    except queue.Empty:break
                else:continue
            if message.get('kind')=='RESERVED':
                if credential_sent:raise Refused('DUPLICATE_WORKER_MESSAGE')
                credential_sent=True
                if live:
                    from .oneshot_authorisation import admitted,require_role
                    if admitted(_live_reservation):require_role(_live_reservation,'credential',worker_pid=process.pid)
                    from .oneshot_credentials import validate_token
                    if phased:
                        claim=decode(native_archive.read('worker.claimed.json'))
                        work_deadline=claim['credential_deadline'];deadline=work_deadline+1
                    if fixture_live:
                        value=_credential_provider.credential();validate_synthetic(value)
                    elif type(_credential_provider) is TerminalCredentialProvider:
                        value=_credential_provider.credential(_live_reservation,deadline=work_deadline)
                    else:value=_credential_provider.credential(_live_reservation)
                    validate_token(value)
                    if phased:
                        if time.monotonic()>=work_deadline:raise Refused('TOKEN_ENTRY_TIMEOUT')
                        from .oneshot_authorisation import begin_acquisition
                        phase=begin_acquisition(native_archive,_live_reservation,process.pid,seconds)
                        acquisition_started=phase['started'];deadline=phase['deadline']
                        work_deadline=deadline-min(1.0,seconds/3)
                    send({'credential':value})
                    value=None
                else:
                    value=_credential_provider.credential() if _credential_provider is not None else synthetic_secret
                    validate_synthetic(value)
                    send({'synthetic_secret':value})
            elif message.get('kind') in ('DONE','REFUSED'):
                result=message;break
            else:break
    except Exception as error:
        result={'kind':'TOKEN_ENTRY_TIMEOUT' if phased and type(error) is Refused and str(error)=='TOKEN_ENTRY_TIMEOUT' else 'OUTCOME_UNKNOWN',
                'local_error':type(error).__name__}
    finally:
        if process is not None:
            # Always fence, even after DONE: no background child may remain.
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
            # Do not block on a buffered pipe lock if OS fencing is uncertain.
            for pipe in (process.stdin,process.stdout) if process.poll() is not None else ():
                if pipe:
                    try:pipe.close()
                    except OSError:pass
        if native_archive is not None:native_archive.close()
        elapsed=time.monotonic()-(acquisition_started if acquisition_started is not None else started)
        result={**result,'worker_pid':process.pid if process else None,
                'worker_exited':process is None or process.poll() is not None,
                'elapsed':elapsed,'total_elapsed':time.monotonic()-started}
        if time.monotonic()>deadline:result['kind']='DEADLINE_OVERRUN'
    return result


PHASES=('before_reservation','after_reservation','before_dispatch','during_dispatch',
        'after_response','archive_publication','final_persistence')
FAULTS={'', 'malformed','http_error','redirect','empty','nine','incomplete','out_of_range',
        *['crash_'+x for x in PHASES],*['stall_'+x for x in PHASES],
        'stall_connection','stall_headers','stall_body','stall_preparation','stall_validation'}
