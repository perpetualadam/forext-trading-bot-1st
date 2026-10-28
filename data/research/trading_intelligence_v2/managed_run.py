"""Managed entrypoint for --tests/--mtf-tests/--v23-tests and research modes.

The original run.py belongs to the frozen V2.3 experiment. Keep its bytes and
audit policy intact; supply its one initial workspace allocation from a scope
whose finally block cleans up under that same audit policy.
"""

import hashlib
import importlib.util
from pathlib import Path
import tempfile


PACKAGE = Path(__file__).resolve().parent
_frozen_path = PACKAGE / "run.py"
_frozen_source = _frozen_path.read_bytes()
if hashlib.sha256(_frozen_source.replace(b"\r\n", b"\n")).hexdigest() != "e040b9eb16f33db1bda1d796fe79f83a44b6e32ea4a36bdc19de9f9ce7a95495":
    raise SystemExit("TIV2_FROZEN_RUNNER_CHANGED")

_temp_spec = importlib.util.spec_from_file_location("_tiv2_runner_temp", PACKAGE / "_runner_temp.py")
_temp_module = importlib.util.module_from_spec(_temp_spec)
_temp_spec.loader.exec_module(_temp_module)
# Resolve the OS temp location before the frozen runner scrubs the environment.
tempfile.gettempdir()
with _temp_module.temporary_workspace() as _workspace:
    _original_mkdtemp = tempfile.mkdtemp

    def _initial_workspace(*args, **kwargs):
        if args or kwargs != {"prefix": "tiv2-"}:
            raise PermissionError("TIV2_UNEXPECTED_TEMP_ALLOCATION")
        # Restore immediately: test fixtures keep the normal allocator.
        tempfile.mkdtemp = _original_mkdtemp
        return str(_workspace)

    tempfile.mkdtemp = _initial_workspace
    try:
        __file__ = str(_frozen_path)
        exec(compile(_frozen_source, str(_frozen_path), "exec"), globals())
    finally:
        tempfile.mkdtemp = _original_mkdtemp
