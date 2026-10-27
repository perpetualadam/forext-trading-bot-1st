"""Owner-run native synthetic storage check. No secret or network interface.

Only the explicit --prepare-binding action creates a non-authorising identity
pin. --check requires it already exist. Synthetic output is retained externally.
"""
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import sys
import threading
import uuid

PACKAGE=Path(__file__).resolve().parent
if os.name!='nt' or sys.argv[1:] not in (['--prepare-binding'],['--check'],['--session-check'],['--negative-security-check']):
    raise SystemExit('usage on Windows: v26c_native_check.py --prepare-binding | --check | --session-check | --negative-security-check')
os.environ.clear()
spec=importlib.util.spec_from_file_location('tiv2',PACKAGE/'__init__.py',submodule_search_locations=[str(PACKAGE)])
module=importlib.util.module_from_spec(spec);sys.modules['tiv2']=module;spec.loader.exec_module(module)
from tiv2 import oneshot_windows as win
from tiv2.oneshot_archive import Archive,APPROVED,prepare_native_binding,Refused
from tiv2.oneshot_response import publish_candles
from tiv2.history_fixtures import payload
from tiv2.core import timestamp
from tiv2.oanda_history_manifest import encoded,digest
from tiv2.oneshot import run_once,SPEC_HASH,PHASES
from tiv2.oneshot_archive import NATIVE_FIXTURES

STDLIB=Path(os.__file__).resolve().parent
ROOT=Path(APPROVED)
win.K.MoveFileExW


def audit(event,args):
    if event.startswith('socket.') or event in {'os.system','os.exec','os.spawn','os.fork','os.startfile'}:
        raise PermissionError('NATIVE_CHECK_OFFLINE_ONLY')
    if event=='subprocess.Popen':
        executable,argv,cwd,env=args
        approved=[sys.executable,'-I','-S','-B',str(PACKAGE/'oneshot_worker.py'),'--worker']
        if executable not in (None,sys.executable) or argv not in (approved,subprocess.list2cmdline(approved)) or env!={}:
            raise PermissionError('NATIVE_CHECK_WORKER_REFUSED')
    if event=='ctypes.dlopen':raise PermissionError('NATIVE_CHECK_DLL_REFUSED')
    if event=='import' and args[0].split('.')[0] in {'forex_bot','socket','http','requests','dotenv','psycopg2','sqlite3'}:
        raise PermissionError('NATIVE_CHECK_IMPORT_REFUSED')
    if event=='open':
        name,mode,flags=args
        if isinstance(name,int):return # anonymous worker pipes
        path=Path(name).resolve();write=flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
        if path==Path(os.devnull).resolve():return
        if write and not path.is_relative_to(ROOT):raise PermissionError('NATIVE_CHECK_WRITE_REFUSED')
        if not write and not any(path.is_relative_to(p) for p in (ROOT,PACKAGE,STDLIB)):
            raise PermissionError('NATIVE_CHECK_READ_REFUSED')
        if path.name.lower().startswith('.env') or path.suffix in {'.db','.permit','.consumed'}:
            raise PermissionError('NATIVE_CHECK_STATE_REFUSED')
    if event in {'os.rename','os.remove','os.mkdir','os.rmdir','os.link','os.symlink','os.chmod','os.truncate'}:
        for path in args[:2] if event in {'os.rename','os.link','os.symlink'} else args[:1]:
            if not Path(path).absolute().is_relative_to(ROOT):raise PermissionError('NATIVE_CHECK_MUTATION_REFUSED')


sys.addaudithook(audit)
if sys.argv[1:]==['--prepare-binding']:
    print(prepare_native_binding());raise SystemExit(0)

if sys.argv[1:]==['--negative-security-check']:
    checks=0
    with Archive(APPROVED) as archive:
        link=ROOT/'research_outputs/v26c_synthetic_junction'
        assert getattr(link,'is_junction')()
        try:win.identity_handle(link)
        except win.WinFailure:checks+=1
        else:raise AssertionError('KERNEL_REPARSE_HANDLE_ACCEPTED')
        try:archive.path('research_outputs/v26c_synthetic_junction/forbidden')
        except Refused:checks+=1
        else:raise AssertionError('JUNCTION_PATH_ACCEPTED')
        try:win.acl(ROOT/'research_outputs/v26c_synthetic_broad_acl',win.current_sid())
        except win.WinFailure:checks+=1
        else:raise AssertionError('BROAD_DACL_ACCEPTED')
    print(json.dumps({'native_negative_security_checks':checks,'failures':0,'errors':0,'skips':0,'network_requests':0}))
    raise SystemExit(0)

if sys.argv[1:]==['--session-check']:
    checks=0
    with Archive(APPROVED):pass
    NATIVE_FIXTURES.mkdir(exist_ok=True)
    def fixture():
        path=NATIVE_FIXTURES/('case_'+uuid.uuid4().hex);path.mkdir()
        a=Archive(path,synthetic=True)
        a.put('journal.json',encoded({'version':1,'state':'AUTHORISED_NOT_CONSUMED','spec':SPEC_HASH,'attempts':0}))
        a.put('grant.json',encoded({'synthetic':True,'spec':SPEC_HASH,'identity':a.identity}))
        return a
    def run(a,**kwargs):
        return run_once(a.root,synthetic_secret='SYNTHETIC_NATIVE_NOT_A_CREDENTIAL',pin=a.identity,**kwargs)
    with fixture() as a:
        barrier=threading.Barrier(3,timeout=4);results=[]
        def compete():barrier.wait();results.append(run(a,seconds=4))
        threads=[threading.Thread(target=compete) for _ in range(2)]
        for t in threads:t.start()
        barrier.wait()
        for t in threads:t.join(5);assert not t.is_alive()
        assert sorted(r['kind'] for r in results)==['DONE','REFUSED'],results;checks+=1
        assert run(a)['kind']=='REFUSED';checks+=1
        assert json.loads(a.read('synthetic_dispatch.json'))['attempts']==1;checks+=1
    for phase in PHASES:
        with fixture() as a:
            result=run(a,fault='crash_'+phase)
            assert result['kind']=='OUTCOME_UNKNOWN' and result['worker_exited'],result;checks+=1
            assert run(a)['kind']=='REFUSED' and a.path('grant.claimed.json').exists();checks+=1
    for phase in ('connection','headers','body','final_persistence'):
        with fixture() as a:
            result=run(a,seconds=1.5,fault='stall_'+phase)
            assert result['kind']=='OUTCOME_UNKNOWN' and result['worker_exited'] and result['elapsed']<=1.5,result;checks+=1
            assert run(a)['kind']=='REFUSED';checks+=1
    print(json.dumps({'native_synthetic_session_checks':checks,'failures':0,'errors':0,'skips':0,'network_requests':0}))
    raise SystemExit(0)

checks=0
with Archive(APPROVED) as archive:
    checks+=1 # native fixed NTFS, no-reparse handles, owner + SYSTEM ACLs + pin
    name='v26c_synthetic_'+uuid.uuid4().hex
    begin=timestamp('2026-09-02T10:00:00Z');end=begin+3000
    receipt=publish_candles(archive,encoded(payload(start=begin,count=9)),name=name,
                            start=begin,end=end,retrieved=timestamp('2026-10-27T00:00:00Z'),synthetic=True)
    assert receipt['observed_complete_count']==9;checks+=1
    for key in ('raw','validated'):
        assert digest(archive.read(receipt[key]))==receipt[key+'_sha256'];checks+=1
        win.acl(archive.path(receipt[key]),win.current_sid());checks+=1
    assert not archive.path(receipt['raw']+'.pending').exists();checks+=1
    try:archive.read('../forbidden')
    except Refused:checks+=1
    else:raise AssertionError('TRAVERSAL_ACCEPTED')
    try:archive.put(receipt['raw'],b'overwrite')
    except Refused:checks+=1
    else:raise AssertionError('OVERWRITE_ACCEPTED')
    # Actual directory handle denies replacement while bound (no DELETE share).
    try:os.rename(ROOT/'validated',ROOT/'validated_must_not_move')
    except OSError:checks+=1
    else:raise AssertionError('DIRECTORY_REPLACEMENT_ACCEPTED')
    assert not (ROOT/'validated_must_not_move').exists();checks+=1
print(json.dumps({'native_synthetic_checks':checks,'failures':0,'errors':0,'skips':0,
                  'credentials_accessed':False,'network_requests':0,'identity_details':'LOCAL_ONLY'}))
