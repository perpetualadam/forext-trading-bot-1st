"""Isolated loopback-only HTTPS tests; no authenticated command or live grant."""
import ast
import contextlib
import dataclasses
import datetime
import decimal
import email.utils
import hashlib
import http.client
import importlib.util
import ipaddress
import json
import math
import os
from pathlib import Path
import queue
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.parse
import uuid

if sys.argv[1:] not in (['--tests'],['--native-tests'],['--v26e-tests'],['--native-v26e-tests'],['--v26g-tests'],['--native-v26g-tests'],['--v27-tests'],['--native-v27-tests']):
    raise SystemExit('usage: v26d_run.py --tests | --native-tests | --v26e-tests | --native-v26e-tests | --v26g-tests | --native-v26g-tests | --v27-tests | --native-v27-tests')
V27=sys.argv[1:] in (['--v27-tests'],['--native-v27-tests'])
V26G=V27 or sys.argv[1:] in (['--v26g-tests'],['--native-v26g-tests'])
V26E=V26G or sys.argv[1:] in (['--v26e-tests'],['--native-v26e-tests'])
NATIVE=sys.argv[1:] in (['--native-tests'],['--native-v26e-tests'],['--native-v26g-tests'],['--native-v27-tests'])
if NATIVE and os.name!='nt':raise SystemExit('NATIVE_WINDOWS_REQUIRED')
PACKAGE=Path(__file__).resolve().parent;STDLIB=Path(os.__file__).resolve().parent
BASE=PACKAGE/'outputs/v26c/fixtures'
for p in (PACKAGE/'outputs',PACKAGE/'outputs/v26c',BASE):
    if p.is_symlink() or getattr(p,'is_junction',lambda:False)() or p.resolve()!=p:raise SystemExit('UNSAFE_FIXTURE_ROOT')
    p.mkdir(exist_ok=True)
os.environ.clear()
spec=importlib.util.spec_from_file_location('tiv2',PACKAGE/'__init__.py',submodule_search_locations=[str(PACKAGE)])
module=importlib.util.module_from_spec(spec);sys.modules['tiv2']=module;spec.loader.exec_module(module)
if os.name=='nt':
    from tiv2 import oneshot_windows
    oneshot_windows.K.MoveFileExW
from tiv2.oneshot_archive import NATIVE_FIXTURES,APPROVED
WORKER=PACKAGE/'oneshot_worker.py'
OPENSSL=r'C:\Program Files\Git\usr\bin\openssl.exe' if os.name=='nt' else '/usr/bin/openssl'
WRITES=[BASE]+([NATIVE_FIXTURES] if NATIVE else [])
# Only source text for the requested static compatibility audit; never import
# these modules or permit .env/configuration-value reads in parent or worker.
AUDIT_SOURCES={PACKAGE.parents[2]/p for p in (
    'forex_bot/oanda_client.py','forex_bot/oanda_candles_read.py','forex_bot/config.py')} if V26E else set()
if V27:
    AUDIT_SOURCES.update(PACKAGE.parent/'adaptive_ensemble/r56/phase6_connection_enablement'/p
        for p in ('real_session_entry.py','credential_ipc.py','live_session_gate.py',
                  'diagnostic_supervisor.py','restricted_live_transport.py','one_session_activation.py'))


def within(path,roots):return any(path==r or path.is_relative_to(r) for r in roots)


def audit(event,args):
    if event.startswith('socket.'):
        if event=='socket.__new__' and args[1]==socket.AF_INET and args[2]==socket.SOCK_STREAM and args[3] in (0,socket.IPPROTO_TCP):return
        if event=='socket.bind' and args[1]==('127.0.0.1',0):return
        raise PermissionError('V26D_NON_FIXTURE_SOCKET_REFUSED')
    if event in {'os.system','os.exec','os.spawn','os.fork','os.startfile'}:raise PermissionError('V26D_EXEC_REFUSED')
    if event=='subprocess.Popen':
        executable,argv,cwd,env=args
        worker=[sys.executable,'-I','-S','-B',str(WORKER),'--worker']
        if executable in (None,sys.executable) and argv in (worker,subprocess.list2cmdline(worker)):
            if env!=({'SystemRoot':r'C:\Windows'} if os.name=='nt' else {}):
                raise PermissionError('V26D_SUBPROCESS_ENV_REFUSED')
            return
        if env!={}:raise PermissionError('V26D_SUBPROCESS_ENV_REFUSED')
        # No arbitrary OpenSSL subcommand or destination: only ephemeral req.
        parts=argv if isinstance(argv,list) else None
        if parts is None and os.name=='nt':
            # Compare to the fixture's exact generated command, not shell parse.
            parts=getattr(sys.modules.get('tiv2.https_test_server'),'CERT_ARGV',None)
            if parts is None or argv!=subprocess.list2cmdline(parts):parts=None
        if (executable in (None,OPENSSL) and parts and parts[:12]==[OPENSSL,'req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:P-256','-nodes','-days','1','-subj','/CN=localhost']
            and parts[12:15]==['-addext','subjectAltName=DNS:localhost,IP:127.0.0.1','-config'] and len(parts)==20
            and parts[16]=='-keyout' and parts[18]=='-out'
            and all(Path(parts[i]).resolve().is_relative_to(BASE) for i in (15,17,19))):return
        raise PermissionError('V26D_SUBPROCESS_REFUSED')
    if event.startswith('ctypes.'):
        if not NATIVE or event in ('ctypes.dlopen','ctypes.dlsym','ctypes.dlsym/handle'):
            raise PermissionError('V26D_DYNAMIC_FFI_REFUSED')
    if event=='import' and args[0].split('.')[0] in {'forex_bot','dotenv','psycopg2','sqlite3','requests'}:
        raise PermissionError('V26D_OPERATIONAL_IMPORT_REFUSED')
    if event=='open':
        name,mode,flags=args
        if isinstance(name,int):return # bounded anonymous worker pipes
        path=Path(name).resolve();write=flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
        if path==Path(os.devnull).resolve():return
        if path.name.lower().startswith('.env') or path.suffix.lower() in {'.db','.sqlite','.sqlite3','.permit','.consumed'}:
            raise PermissionError('V26D_PRIVATE_STATE_REFUSED')
        if write and not within(path,WRITES):raise PermissionError('V26D_WRITE_REFUSED')
        reads=[STDLIB,PACKAGE]+([Path(APPROVED)] if NATIVE else [])
        if not write and path not in AUDIT_SOURCES and not within(path,reads):raise PermissionError('V26D_READ_REFUSED')
    if event in {'os.rename','os.remove','os.mkdir','os.rmdir','os.link','os.symlink','os.chmod','os.truncate'}:
        for value in args[:2] if event in {'os.rename','os.link','os.symlink'} else args[:1]:
            if not within(Path(value).absolute(),WRITES):raise PermissionError('V26D_MUTATION_REFUSED')


sys.addaudithook(audit)
test_name='test_v27' if V27 else 'test_v26g' if V26G else 'test_v26e' if V26E else 'test_v26d'
spec=importlib.util.spec_from_file_location('tiv2.'+test_name,PACKAGE/(test_name+'.py'))
tests=importlib.util.module_from_spec(spec);sys.modules[spec.name]=tests;tests.NATIVE=NATIVE
spec.loader.exec_module(tests)
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
print(f'RESULT tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)} skips={len(result.skipped)}')
raise SystemExit(not result.wasSuccessful())
