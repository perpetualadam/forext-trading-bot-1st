"""Disposable worker. Real entry is unreachable behind the refusing live gate."""
import datetime
import decimal
import email.utils
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import sys
import socket
import ssl
import threading
import time
import urllib.parse

PACKAGE=Path(__file__).resolve().parent
STDLIB=Path(os.__file__).resolve().parent
FIXTURES=PACKAGE/'outputs/v26c/fixtures'
NATIVE_FIXTURES=Path(r'C:\TradingResearchData\OANDA\research_outputs\v26c_synthetic_sessions')
BINDING=Path(r'C:\TradingResearchData\OANDA\manifests\v26c_archive_binding.json')
LOOPBACK_PORT=None
LIVE_POLICY=None
LIVE_APPROVED=False
LIVE_ROOT=Path(r'C:\TradingResearchData\OANDA')
SESSION_READS={LIVE_ROOT/name for name in ('grant.json','grant.claimed.json','journal.json','worker.claimed.json','acquisition.json')}


def audit(event,args):
    if event.startswith('socket.'):
        if LIVE_POLICY is not None and LIVE_POLICY.permits(event,args):return
        if (event=='socket.__new__' and LOOPBACK_PORT is not None and args[1]==socket.AF_INET and
            args[2]==socket.SOCK_STREAM and args[3] in (0,socket.IPPROTO_TCP)):return
        if event=='socket.connect' and LOOPBACK_PORT is not None and args[1]==('127.0.0.1',LOOPBACK_PORT):return
        raise PermissionError('WORKER_SOCKET_REFUSED')
    if event.startswith('subprocess.') or event in {'os.system','os.fork','os.exec','os.spawn','os.startfile'}:
        raise PermissionError('WORKER_OFFLINE_ONLY')
    if event=='import' and args[0].split('.')[0] in {'forex_bot','dotenv','psycopg2','sqlite3','requests','http','socket'}:
        raise PermissionError('WORKER_IMPORT_REFUSED')
    if event=='open':
        name,mode,flags=args
        if isinstance(name,int):raise PermissionError('WORKER_FD_REFUSED')
        path=Path(name).resolve();write=flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
        if path.name.lower().startswith('.env') or path.suffix in {'.db','.sqlite','.permit','.consumed'}:
            raise PermissionError('WORKER_STATE_REFUSED')
        if write and not (LIVE_APPROVED and path.is_relative_to(LIVE_ROOT)) and not any(path.is_relative_to(p) for p in (FIXTURES,NATIVE_FIXTURES)):
            raise PermissionError('WORKER_WRITE_REFUSED')
        if not write and not (LIVE_APPROVED and path.is_relative_to(LIVE_ROOT)) and path not in SESSION_READS and path!=BINDING and not any(path.is_relative_to(p) for p in (STDLIB,PACKAGE,NATIVE_FIXTURES)):
            raise PermissionError('WORKER_READ_REFUSED')
    if event in {'os.rename','os.remove','os.mkdir','os.rmdir','os.link','os.symlink','os.chmod','os.truncate'}:
        for name in args[:2] if event in {'os.rename','os.link','os.symlink'} else args[:1]:
            if not (LIVE_APPROVED and Path(name).resolve().is_relative_to(LIVE_ROOT)) and not any(Path(name).resolve().is_relative_to(p) for p in (FIXTURES,NATIVE_FIXTURES)):
                raise PermissionError('WORKER_MUTATION_REFUSED')


def emit(value):sys.stdout.write(json.dumps(value,separators=(',',':'))+'\n');sys.stdout.flush()


def packet():
    raw=sys.stdin.buffer.readline(2049)
    if len(raw)>2048:raise ValueError()
    return json.loads(raw)


def main():
    global LOOPBACK_PORT,LIVE_POLICY,LIVE_APPROVED
    if sys.argv[1:]!=['--worker']:raise ValueError()
    os.environ.clear()
    if os.name=='nt':os.environ['SystemRoot']=r'C:\Windows'
    # Windows primitives are bound before audit, only kernel32/advapi32 are used.
    spec=importlib.util.spec_from_file_location('tiv2',PACKAGE/'__init__.py',submodule_search_locations=[str(PACKAGE)])
    module=importlib.util.module_from_spec(spec);sys.modules['tiv2']=module;spec.loader.exec_module(module)
    if os.name=='nt':
        from tiv2 import oneshot_windows
    sys.addaudithook(audit)
    from tiv2.oneshot import reserve,claim_reserved_worker,transition,request_guard,SPEC,FAULTS
    from tiv2.oneshot_archive import Archive
    from tiv2.history_fixtures import payload
    from tiv2.oneshot_transport import fetch_fixture_once
    from tiv2.oanda_history_transport import Response
    from tiv2.oanda_history_manifest import encoded,digest,validated
    from tiv2.core import timestamp
    from tiv2.oneshot_bridge import validate_synthetic
    start=packet();fault=start['fault']
    live='live_reservation' in start
    fixture_live=live and type(start['live_reservation']) is dict and start['live_reservation'].get('mode')=='OFFLINE_TEST'
    if live:
        from tiv2.oneshot_authorisation import require_live_reservation
        require_live_reservation(start['live_reservation'])
        LIVE_APPROVED=not fixture_live
        if fixture_live:
            from tiv2.oneshot_https_fixture import validate_binding
            validate_binding(start['https_fixture'])
        elif 'https_fixture' in start:raise ValueError()
    if fault not in FAULTS:raise ValueError()
    def checkpoint(phase):
        if fault=='crash_'+phase:os._exit(123)
        if fault=='stall_'+phase:threading.Event().wait()
    checkpoint('preparation')
    with Archive(start['root'],synthetic=not live or fixture_live,pin=start['pin']) as archive,archive.locked():
        if live:
            checkpoint('before_reservation')
            claim_reserved_worker(archive,start['live_reservation'])
            checkpoint('after_reservation')
        else:reserve(archive,checkpoint)
        emit({'kind':'RESERVED'})
        secret=packet()['credential' if live else 'synthetic_secret']
        if live:
            from tiv2.oneshot_credentials import validate_token
            validate_token(secret)
            if fixture_live:validate_synthetic(secret)
            from tiv2.oneshot_authorisation import admitted,acquisition_phase
            if admitted(start['live_reservation']):
                phase=acquisition_phase(archive,start['live_reservation'])
                start['deadline']=phase['deadline']-min(1.0,phase['seconds']/3)
        else:validate_synthetic(secret)
        request_guard(**SPEC)
        checkpoint('before_dispatch')
        if not live:transition(archive,'REQUEST_ATTEMPTED',1)
        # Explicit fixture evidence only; never publish real provenance as synthetic.
        if not live:archive.put('synthetic_dispatch.json',encoded({'synthetic':True,'attempts':1}))
        begin=timestamp(SPEC['params']['from']);end=timestamp(SPEC['params']['to'])+1
        def sender(method,host,path,params):
            request_guard(method,host,path,params)
            checkpoint('during_dispatch');checkpoint('connection');checkpoint('headers');checkpoint('body')
            if fault=='http_error':return Response(503,b'')
            if fault=='redirect':return Response(302,b'')
            raw=encoded(payload(start=begin,count=0 if fault=='empty' else 9 if fault=='nine' else 10))
            if fault=='malformed':raw=b'{malformed'
            elif fault=='incomplete':
                obj=json.loads(raw);obj['candles'][-1]['complete']=False;raw=encoded(obj)
            elif fault=='out_of_range':raw=encoded(payload(start=begin-300,count=1))
            return Response(200,raw)
        if live and not fixture_live:
            from tiv2.oneshot_network import LiveSocketPolicy,fetch_live
            LIVE_POLICY=LiveSocketPolicy(start['live_reservation'])
            raw=fetch_live(reservation=start['live_reservation'],token=secret,
                           deadline=start['deadline'],_policy=LIVE_POLICY)
        elif 'https_fixture' in start:
            if fixture_live:
                from tiv2.oneshot_authorisation import require_role
                require_role(start['live_reservation'],'fixture_dispatch')
            from tiv2.oneshot_https_fixture import validate_binding
            from tiv2.oanda_existing_readonly import fetch_synthetic_candles
            validate_binding(start['https_fixture'])
            LOOPBACK_PORT=start['https_fixture']['port']
            raw=fetch_synthetic_candles(start['https_fixture'],secret,start['deadline'],checkpoint)
        else:raw=fetch_fixture_once(sender)
        if secret.encode() in raw:raise ValueError()
        transition(archive,'RESPONSE_RECEIVED',1);checkpoint('after_response');checkpoint('validation')
        retrieved=time.time() if live else timestamp('2026-10-27T00:00:00Z')
        rows,report=validated(raw,'EUR_USD',begin,end,retrieved)
        if live or 'https_fixture' in start:
            from tiv2.oneshot_response import publish_candles
            archive.after_pending=lambda name:checkpoint('archive_publication') if name=='raw/v26c_https.json' else None
            publish_candles(archive,raw,name='v26c_https',start=begin,end=end,
                            retrieved=retrieved,synthetic=not live or fixture_live)
        else:
            archive.after_pending=lambda name:checkpoint('archive_publication') if name=='raw.json' else None
            raw_hash=archive.put('raw.json',raw);row_hash=archive.put('validated.json',encoded(rows))
            archive.put('receipt.json',encoded({'synthetic':True,'spec':SPEC,'raw_sha256':raw_hash,
                        'validated_sha256':row_hash,'observed_complete_count':len(rows),'validation':report}))
        archive.after_pending=lambda name:checkpoint('final_persistence') if name=='journal.json' else None
        transition(archive,'SESSION_CONSUMED',1)
        emit({'kind':'DONE','count':len(rows),'raw_sha256':digest(raw)})


if __name__=='__main__':
    try:main()
    except BaseException as error:
        # No exception body, raw HTTP body, path or synthetic secret is emitted.
        cause=error.__cause__ or error
        trace=cause.__traceback__
        while trace is not None and trace.tb_next is not None:trace=trace.tb_next
        site=Path(trace.tb_frame.f_code.co_filename).name+':'+str(trace.tb_lineno) if trace else 'unknown'
        result={'kind':'REFUSED','local_error':type(cause).__name__,'failure_site':site,
                'os_error':getattr(cause,'errno',None)}
        # Only fixed, enumerated codes; never arbitrary exception text.
        reason=str(cause)
        if reason in {'BODY_SIZE_REFUSED','INCOMPLETE_HTTP_BODY','REDIRECT_REFUSED',
                      'HTTP_REQUEST_REFUSED','HTTP_RETRY_EXHAUSTED','MALFORMED_JSON'}:result['reason']=reason
        emit(result)
        raise SystemExit(1)
