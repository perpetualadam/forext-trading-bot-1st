"""Run with python -I -S -B offline_exposure/run_checks.py.

No pytest/conftest, app imports, site packages, credentials, or production state.
Audit barriers apply before loading project source. Only stdlib unittest is used.
"""
import sys
import os
from pathlib import Path
import unittest
import importlib.util
import threading
import itertools
import hashlib
import zipfile
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]
PURE = ROOT / "forex_bot" / "exposure_view.py"
FAKE = ROOT / "offline_exposure" / "fake_coordinator.py"
TEST = ROOT / "offline_exposure" / "test_contract.py"
SEAL = ROOT / "forex_bot" / "bot_loop.py"
ARCHIVE = ROOT / "data" / "research" / "adaptive_ensemble" / "r86" / "R86_SOURCE_REVIEW.zip"
# Preserve no inherited account settings and print no environment values.
os.environ.clear()
STDLIB = Path(os.__file__).resolve().parent
SOURCE_ALLOWLIST = {p.resolve() for p in (PURE, FAKE, TEST, SEAL, ARCHIVE)}


def audit(event, args):
    if (event.startswith(("socket.", "subprocess.", "ctypes."))
            or event in {"os.system", "os.spawn", "os.exec", "os.fork", "os.startfile"}):
        raise PermissionError("OFFLINE_BLOCKED:" + event)
    if event == "import":
        name = args[0]
        if name.split('.')[0] in {"forex_bot", "dotenv", "psycopg2", "requests", "http", "urllib", "socket", "subprocess", "ctypes"}:
            raise PermissionError("OFFLINE_IMPORT_BLOCKED:" + name)
    if event == "open":
        path, mode, flags = args
        if isinstance(path, int):
            raise PermissionError("OFFLINE_FD_BLOCKED")
        candidate = Path(path).resolve()
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise PermissionError("OFFLINE_WRITE_BLOCKED")
        if candidate not in SOURCE_ALLOWLIST and not candidate.is_relative_to(STDLIB):
            raise PermissionError("OFFLINE_READ_BLOCKED")
    if event in {"os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.chmod", "os.link", "os.symlink", "os.truncate"}:
        raise PermissionError("OFFLINE_MUTATION_BLOCKED")


sys.addaudithook(audit)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


model = load("exposure_view", PURE)
fake = load("fake_coordinator", FAKE)
tests = load("test_contract", TEST)


class IsolationChecks(unittest.TestCase):
    def test_barrier_sentinels(self):
        # Audit events probe guards without initiating an operation.
        for event in ("socket.connect", "subprocess.Popen", "os.system", "ctypes.dlopen"):
            with self.subTest(event=event), self.assertRaises(PermissionError):
                sys.audit(event, None)
        for module in ("dotenv", "psycopg2", "socket", "subprocess", "requests", "forex_bot"):
            with self.subTest(module=module), self.assertRaises(PermissionError):
                sys.audit("import", module, None, None, None, None)
        # Synthetic forbidden paths only: do not attempt credential/state reads.
        with self.assertRaises(PermissionError):
            sys.audit("open", str(ROOT / "forbidden_synthetic_input"), "r", 0)
        with self.assertRaises(PermissionError):
            sys.audit("open", str(TEST), "w", os.O_WRONLY)
        self.assertNotIn("forex_bot", sys.modules)
        self.assertFalse(any(n.startswith("psycopg") for n in sys.modules))


selection = sys.argv[1:]
if selection not in ([], ["--concurrency"], ["--historical"]):
    raise SystemExit("usage: run_checks.py [--concurrency|--historical]")
if selection == ["--concurrency"]:
    checks = unittest.defaultTestLoader.loadTestsFromTestCase(tests.ConcurrencyTests)
elif selection == ["--historical"]:
    checks = unittest.defaultTestLoader.loadTestsFromTestCase(tests.ContractTests)
else:
    checks = unittest.defaultTestLoader.loadTestsFromModule(tests)
suite = unittest.TestSuite((checks,
                           unittest.defaultTestLoader.loadTestsFromTestCase(IsolationChecks)))
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(f"RESULT tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)} skips={len(result.skipped)}")
raise SystemExit(not result.wasSuccessful())
