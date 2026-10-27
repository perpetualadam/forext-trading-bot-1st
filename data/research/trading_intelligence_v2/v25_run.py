"""V2.5 entry point: --v25-tests or --v25-evaluate. Stdlib only; isolate before project imports."""
import ast
import csv
import dataclasses
import datetime
import enum
import gzip
import hashlib
import importlib.util
import json
import logging
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import typing
import unittest

if sys.argv[1:] not in (['--v25-tests'], ['--v25-evaluate']):
    raise SystemExit('usage: v24_run.py --v25-tests|--v25-evaluate')

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
os.environ.clear()
TEMP = Path(tempfile.mkdtemp(prefix="tiv2-" )).resolve()
STDLIB = Path(os.__file__).resolve().parent
SOURCES = {ROOT / p for p in (
    "forex_bot/shadow/signals.py", "forex_bot/shadow/reasons.py", "forex_bot/shadow/original.py",
    "forex_bot/ai_ensemble.py", "forex_bot/rl_agent.py", "forex_bot/profit_protection.py",
    "forex_bot/indicators.py", "forex_bot/trading.py")}
INPUTS = [ROOT / "data/historical", ROOT / "data/research/adaptive_ensemble/g3"]
INPUTS.append(PACKAGE/'inputs/v23')
WRITES = [PACKAGE/'outputs/v25', PACKAGE/'reports/v25', TEMP]


def inside(path, roots):
    return any(path == r or path.is_relative_to(r) for r in roots)


def audit(event, args):
    if event.startswith(("socket.", "subprocess.", "ctypes.")) or event in {
        "os.system", "os.spawn", "os.exec", "os.fork", "os.startfile"}:
        raise PermissionError("TIV2_OFFLINE_BLOCKED:" + event)
    if event == "import" and args[0].split('.')[0] in {
        "forex_bot", "dotenv", "psycopg2", "sqlite3", "requests", "http", "urllib", "socket", "subprocess", "ctypes"}:
        raise PermissionError("TIV2_IMPORT_BLOCKED:" + args[0])
    if event == "open":
        name, mode, flags = args
        if isinstance(name, int):
            raise PermissionError("TIV2_FD_BLOCKED")
        path = Path(name).resolve()
        write = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        if write:
            if not inside(path, WRITES):
                raise PermissionError("TIV2_WRITE_BLOCKED")
        elif not (path in SOURCES or inside(path, [STDLIB, PACKAGE, TEMP, *INPUTS])):
            raise PermissionError("TIV2_READ_BLOCKED")
        if path.name.lower().startswith('.env') or path.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.permit', '.consumed'}:
            raise PermissionError("TIV2_STATE_BLOCKED")
    if event in {"os.remove", "os.mkdir", "os.rmdir", "os.chmod", "os.truncate", "os.rename", "os.link", "os.symlink"}:
        paths = args[:2] if event in {"os.rename", "os.link", "os.symlink"} else args[:1]
        if any(not inside(Path(p).resolve(), WRITES) for p in paths):
            raise PermissionError("TIV2_MUTATION_BLOCKED")


sys.addaudithook(audit)
spec = importlib.util.spec_from_file_location("tiv2", PACKAGE / "__init__.py", submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules['tiv2'] = module
spec.loader.exec_module(module)
if sys.argv[1:] == ['--v25-tests']:
    tests_spec=importlib.util.spec_from_file_location('tiv2.test_v25',PACKAGE/'test_v25.py')
    tests=importlib.util.module_from_spec(tests_spec)
    sys.modules[tests_spec.name]=tests
    tests.TEMP,tests.ROOT=TEMP,ROOT
    tests_spec.loader.exec_module(tests)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    print(f'RESULT tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)} skips={len(result.skipped)}')
    raise SystemExit(not result.wasSuccessful())
else:
    from tiv2.v25_pipeline import run
    run(ROOT,PACKAGE)
