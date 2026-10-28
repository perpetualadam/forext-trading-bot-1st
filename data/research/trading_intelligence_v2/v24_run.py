"""V2.4 entry point: --v24-tests or --v24-evaluate. Stdlib only; isolate before project imports."""
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

if sys.argv[1:] not in (['--v24-tests'], ['--v24-evaluate']):
    raise SystemExit('usage: v24_run.py --v24-tests|--v24-evaluate')

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
# Load only the fixed stdlib-only workspace helper before isolation.
_temp_spec = importlib.util.spec_from_file_location("_tiv2_runner_temp", PACKAGE / "_runner_temp.py")
_temp_module = importlib.util.module_from_spec(_temp_spec)
_temp_spec.loader.exec_module(_temp_module)
# Cache the OS temp location before scrubbing environment routing/secrets.
tempfile.gettempdir()
os.environ.clear()
with _temp_module.temporary_workspace() as TEMP:
    STDLIB = Path(os.__file__).resolve().parent
    SOURCES = {ROOT / p for p in (
        "forex_bot/shadow/signals.py", "forex_bot/shadow/reasons.py", "forex_bot/shadow/original.py",
        "forex_bot/ai_ensemble.py", "forex_bot/rl_agent.py", "forex_bot/profit_protection.py",
        "forex_bot/indicators.py", "forex_bot/trading.py")}
    INPUTS = [ROOT / "data/historical", ROOT / "data/research/adaptive_ensemble/g3"]
    INPUTS.append(PACKAGE/'inputs/v23')
    MTF_MODE=sys.argv[1:] in (["--mtf-tests"],["--mtf-evaluate"])
    V23_MODE=len(sys.argv)>1 and sys.argv[1] in ('--v23-tests','--v23-evaluate')
    V24_MODE=sys.argv[1:] in (['--v24-tests'],['--v24-evaluate'])
    WRITES = ([PACKAGE/'outputs/v24',PACKAGE/'reports/v24',TEMP] if V24_MODE else
              [PACKAGE/'outputs/v23',PACKAGE/'reports/v23',TEMP] if V23_MODE else
              [PACKAGE / "outputs/mtf", PACKAGE / "reports/mtf", TEMP] if MTF_MODE
              else [PACKAGE / "outputs", PACKAGE / "reports", TEMP])


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
    if sys.argv[1:] in (["--tests"],["--mtf-tests"],["--v23-tests"],["--v24-tests"]):
        test_name='test_v24' if V24_MODE else 'test_v23' if V23_MODE else 'test_mtf' if MTF_MODE else 'test_contract'
        tests_spec = importlib.util.spec_from_file_location("tiv2."+test_name, PACKAGE / (test_name+'.py'))
        tests = importlib.util.module_from_spec(tests_spec)
        sys.modules[tests_spec.name] = tests
        tests.TEMP = TEMP
        tests.ROOT = ROOT
        tests_spec.loader.exec_module(tests)
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
        print(f"RESULT tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)} skips={len(result.skipped)}")
        raise SystemExit(not result.wasSuccessful())
    elif sys.argv[1:] == ['--v24-evaluate']:
        from tiv2.v24_pipeline import run
        run(ROOT, PACKAGE)
    elif sys.argv[1:] == ["--evaluate"]:
        from tiv2.study import run
        run(ROOT, PACKAGE)
    elif sys.argv[1:] == ["--mtf-evaluate"]:
        from tiv2.mtf_walkforward import run
        run(ROOT, PACKAGE)
    elif V23_MODE and sys.argv[1]=='--v23-evaluate':
        from tiv2.v23_pipeline import run
        if sys.argv[2:]==['--exploratory']:
            run(ROOT,PACKAGE,exploratory=True)
        elif len(sys.argv) in (4,5) and sys.argv[2]=='--manifest' and (len(sys.argv)==4 or sys.argv[4]=='--allow-reproduction'):
            manifest=(ROOT/sys.argv[3]).resolve()
            if not manifest.is_relative_to((PACKAGE/'inputs/v23').resolve()):
                raise SystemExit('manifest must be inside data/research/trading_intelligence_v2/inputs/v23')
            run(ROOT,PACKAGE,manifest=manifest,allow_reproduction=len(sys.argv)==5)
        else:
            raise SystemExit('V23 requires --exploratory or --manifest <approved local manifest>; no implicit independence claim')
    else:
        raise SystemExit("usage: run.py --tests|--evaluate|--mtf-tests|--mtf-evaluate|--v23-tests|--v23-evaluate --exploratory|--v23-evaluate --manifest <path>")
