"""Run every collected test module in a fresh interpreter.

Several safety suites assert that importing their subject does not load the
application or broker adapters. Collecting unrelated application tests in the
same interpreter makes those assertions order-dependent. No tests are filtered
here: pytest owns collection, and a failure in any module fails the run.
"""

from __future__ import annotations

import os
import argparse
from pathlib import Path
import re
import subprocess
import sys


# This suite asserts that its launcher's socket/DNS barrier is already active.
# Its own r13 mode runs the entire module without a -k expression or exclusions.
STAGE_RUNNERS = {
    "tests/test_r13_loop_wiring.py": (
        "data/research/adaptive_ensemble/r13/20_run_offline_tests.py", "r13"
    ),
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, PYTHON_DOTENV_DISABLED="1")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--ignore", action="append", default=[])
    parser.add_argument("--basetemp", type=Path)
    options = parser.parse_args()
    arguments = [f"--ignore={path}" for path in options.ignore]
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--color=no", *options.paths, *arguments],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    if collected.returncode:
        print(collected.stdout, end="")
        print(collected.stderr, end="", file=sys.stderr)
        return collected.returncode
    modules = sorted({
        match.group(1)
        for line in collected.stdout.splitlines()
        if (match := re.match(r"^(tests[/\\]test_[^:]+\.py)::", line))
    })
    if not modules:
        print("No test modules collected; refusing an empty CI run.", file=sys.stderr)
        return 1
    if options.basetemp is not None:
        options.basetemp.mkdir(parents=True, exist_ok=True)
    failed = []
    for module in modules:
        print(f"\n=== Isolated module: {module} ===", flush=True)
        temporary = [] if options.basetemp is None else [
            "--basetemp", str(options.basetemp / Path(module).stem)
        ]
        stage = STAGE_RUNNERS.get(module.replace("\\", "/"))
        command = (
            [sys.executable, "-B", *stage]
            if stage is not None else
            [sys.executable, "-m", "pytest", "-q", module, *arguments, *temporary]
        )
        result = subprocess.run(
            command,
            cwd=root,
            env=environment,
        )
        if result.returncode:
            failed.append(module)
    print(f"\nIsolated modules: {len(modules)}; failed modules: {len(failed)}", flush=True)
    for module in failed:
        print(f"FAILED MODULE {module}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
