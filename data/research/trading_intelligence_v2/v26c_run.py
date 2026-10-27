"""Isolated synthetic V2.6C runner. No authenticated execution command."""
import ast
import contextlib
import dataclasses
import datetime
import decimal
import email.utils
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import queue
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.parse

if sys.argv[1:]!=['--tests']:raise SystemExit('usage: v26c_run.py --tests')
PACKAGE=Path(__file__).resolve().parent
STDLIB=Path(os.__file__).resolve().parent
BASE=PACKAGE/'outputs/v26c/fixtures'
for path in (PACKAGE/'outputs',PACKAGE/'outputs/v26c',BASE):
    if path.is_symlink() or getattr(path,'is_junction',lambda:False)() or path.resolve()!=path:
        raise SystemExit('UNSAFE_FIXTURE_ROOT')
    path.mkdir(exist_ok=True)
os.environ.clear()
spec=importlib.util.spec_from_file_location('tiv2',PACKAGE/'__init__.py',submodule_search_locations=[str(PACKAGE)])
module=importlib.util.module_from_spec(spec);sys.modules['tiv2']=module;spec.loader.exec_module(module)
if os.name=='nt':
    from tiv2 import oneshot_windows
    # Bind the one extra archive publication primitive before installing audit.
    oneshot_windows.K.MoveFileExW
WORKER=PACKAGE/'oneshot_worker.py'


def audit(event,args):
    if event.startswith('socket.') or event in {'os.system','os.fork','os.exec','os.spawn','os.startfile'}:
        raise PermissionError('V26C_OFFLINE_ONLY')
    if event=='subprocess.Popen':
        executable,argv,cwd,env=args
        approved=[sys.executable,'-I','-S','-B',str(WORKER),'--worker']
        if argv not in (approved,subprocess.list2cmdline(approved)) or env!={} or executable not in (None,sys.executable):
            raise PermissionError('V26C_SUBPROCESS_REFUSED')
    if event.startswith('ctypes.'):
        # All permitted DLLs and symbols were bound before audit installation.
        raise PermissionError('V26C_DYNAMIC_FFI_REFUSED')
    if event=='import' and args[0].split('.')[0] in {'forex_bot','dotenv','psycopg2','sqlite3','requests','http','socket'}:
        raise PermissionError('V26C_IMPORT_REFUSED')
    if event=='open':
        name,mode,flags=args
        if isinstance(name,int):return # anonymous subprocess pipes, never path selectors
        path=Path(name).resolve();write=flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
        if path==Path(os.devnull).resolve():return
        if path.name.lower().startswith('.env') or path.suffix.lower() in {'.db','.sqlite','.sqlite3','.permit','.consumed'}:
            raise PermissionError('V26C_PRIVATE_STATE_REFUSED')
        if write and not path.is_relative_to(BASE):raise PermissionError('V26C_WRITE_REFUSED')
        if not write and not any(path.is_relative_to(p) for p in (STDLIB,PACKAGE)):
            # Popen opens the null device to discard untrusted stderr.
            if path!=Path(os.devnull).resolve():raise PermissionError('V26C_READ_REFUSED')
    if event in {'os.rename','os.remove','os.mkdir','os.rmdir','os.link','os.symlink','os.chmod','os.truncate'}:
        paths=args[:2] if event in {'os.rename','os.link','os.symlink'} else args[:1]
        if any(not Path(p).absolute().is_relative_to(BASE) for p in paths):raise PermissionError('V26C_MUTATION_REFUSED')


sys.addaudithook(audit)
spec=importlib.util.spec_from_file_location('tiv2.test_v26c',PACKAGE/'test_v26c.py')
tests=importlib.util.module_from_spec(spec);sys.modules[spec.name]=tests;spec.loader.exec_module(tests)
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
print(f'RESULT tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)} skips={len(result.skipped)}')
raise SystemExit(not result.wasSuccessful())
