"""Synthetic worker for a delegated cgroup experiment. No credentials and no network."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else "ready"
    if mode == "grand":
        child = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(60)"])
        Path(argv[1]).write_text(str(child.pid), encoding="utf-8")
        Path(argv[2]).write_text("ready", encoding="utf-8")
        time.sleep(60)
        return 0
    if mode == "side":
        Path(argv[1]).write_text("ran", encoding="utf-8")
        time.sleep(60)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
