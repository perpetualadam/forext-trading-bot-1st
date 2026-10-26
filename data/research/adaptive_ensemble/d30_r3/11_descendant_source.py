"""Synthetic descendant. One fixed mode and no further processes."""
from __future__ import annotations

import sys
import time

MODES = frozenset({"complete", "sleep", "block"})


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in MODES:
        return 2
    mode = sys.argv[1]
    if mode == "sleep":
        time.sleep(0.08)
    elif mode == "block":
        time.sleep(30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
