"""Bounded source-only reproductions; no pytest conftest or application imports.

One actual pure historical test is called. Other cases execute extracted source
guards/fragments, not the complete application tests that failed in CI.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

os.environ.clear()
root = Path(sys.argv[1]).resolve()
stdlib = Path(os.__file__).resolve().parent
names = ["tests/test_d15_historical_compatibility.py", "tests/g14_4_acquire.py",
         "tests/g14_7_fs.py", "forex_bot/app.py", "forex_bot/database.py",
         "forex_bot/telegram_control.py", "forex_bot/live_safety.py", "forex_bot/strategy_meta.py"]
allowed = {(root / n).resolve() for n in names}


def audit(event, args):
    if event.startswith(("socket.", "subprocess.", "ctypes.")) or event in {
        "os.system", "os.spawn", "os.exec", "os.fork", "os.startfile",
        "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.truncate"}:
        raise PermissionError("REPRO_OFFLINE_BLOCKED")
    if event == "import" and args[0].split('.')[0] in {
        "forex_bot", "psycopg2", "sqlite3", "dotenv", "requests", "socket",
        "subprocess", "ctypes", "http", "urllib"}:
        raise PermissionError("REPRO_IMPORT_BLOCKED")
    if event == "open":
        path, _, flags = args
        if isinstance(path, int) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            raise PermissionError("REPRO_WRITE_BLOCKED")
        resolved = Path(path).resolve()
        if resolved not in allowed and not resolved.is_relative_to(stdlib):
            raise PermissionError("REPRO_READ_BLOCKED")


sys.addaudithook(audit)
for event in ("socket.connect", "subprocess.Popen", "ctypes.dlopen"):
    try:
        sys.audit(event, None)
    except PermissionError:
        pass
    else:
        raise AssertionError("barrier sentinel failed")

results = []


def reproduce(name, call, expected_type, expected_reason=None):
    try:
        call()
    except Exception as exc:
        matched = type(exc).__name__ == expected_type and (
            expected_reason is None or str(exc) == expected_reason)
        results.append({"case": name, "matched": matched,
                        "exception": type(exc).__name__, "reason": str(exc),
                        "traceback": traceback.format_exc()})
    else:
        results.append({"case": name, "matched": False, "exception": None})


spec = importlib.util.spec_from_file_location("d15_pure_historical_pin", root / names[0])
pin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin)
reproduce("actual D15 current-baseline hash assertion", pin.test_current_protected_hashes_match_d15_baseline,
          "AssertionError")
pin.test_historical_pins_differ_from_current_source()


def extracted(relative, selected, namespace):
    path = root / relative
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    body = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in selected]
    assert len(body) == len(selected)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


acquire = extracted("tests/g14_4_acquire.py", {"EnvironmentRejected", "select_interpreter"},
                    {"Path": Path})
reproduce("Windows synthetic interpreter fixture on Linux (extracted guard)",
          lambda: acquire['select_interpreter'](Path(r"C:\synthetic\python.exe")),
          "EnvironmentRejected", "untrusted_executable")
fs = extracted("tests/g14_7_fs.py", {"FilesystemRejected", "open_directory"},
               {"Path": Path, "os": os, "_KERNEL": None, "_NT": None, "DirectoryHandle": object})
reproduce("Windows filesystem handle guard on Linux (extracted guard)",
          lambda: fs['open_directory'](root), "FilesystemRejected", "handle_api_unavailable")
app_source = (root / "forex_bot/app.py").read_text(encoding="utf-8-sig")
lifespan = next(n for n in ast.parse(app_source).body if isinstance(n, ast.AsyncFunctionDef) and n.name == "lifespan")
fragment = ast.get_source_segment(app_source, lifespan)
reproduce("obsolete lifespan text search (source fragment only)",
          lambda: fragment.index("raise StartupSafetyAbort"), "ValueError", "substring not found")
assert not any(n == "forex_bot" or n.startswith("forex_bot.") for n in sys.modules)
print(json.dumps({"platform": sys.platform, "python": sys.version, "reproductions": results,
                  "historical_pins_positive_control": "passed", "application_imports": False,
                  "barrier_sentinels": "passed"}, indent=2))
raise SystemExit(not all(r["matched"] for r in results))
