"""Synthetic stand-in for a future client worker. No transport."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    mode, workdir_text, token = sys.argv[1:]
    if mode != "complete" or not token.isdigit():
        return 2
    workdir = Path(workdir_text).resolve()
    if workdir.name != "d30_r4" or not workdir.is_dir():
        return 2
    os.chdir(workdir)
    time.sleep(0.05)
    sys.stdout.buffer.write(b'{"kind":"ok","status":"complete"}\n')
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
