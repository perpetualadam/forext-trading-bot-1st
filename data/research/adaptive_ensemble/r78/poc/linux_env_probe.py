"""Dependency and filesystem probe. Does not install packages or open a broker."""

from __future__ import annotations

import importlib
import os
import sqlite3
import subprocess
import tempfile

for name in ("oandapyV20", "pandas", "numpy", "psycopg2", "dotenv", "requests"):
    try:
        importlib.import_module(name)
        print("PRESENT", name)
    except Exception as exc:
        print("MISSING", name, type(exc).__name__)

print("VENV", os.environ.get("VIRTUAL_ENV", ""))
print(subprocess.check_output(["df", "-T", "/tmp", "/mnt/c"], text=True))
connection = sqlite3.connect(":memory:")
mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
sync = connection.execute("PRAGMA synchronous").fetchone()[0]
print("MEMORY_WAL", mode, "SYNC", sync)
handle = tempfile.NamedTemporaryFile(prefix="r78-", delete=False)
handle.close()
disk = sqlite3.connect(handle.name)
print("DISK_WAL", disk.execute("PRAGMA journal_mode=WAL").fetchone()[0])
disk.execute("PRAGMA synchronous=FULL")
print("DISK_SYNC", disk.execute("PRAGMA synchronous").fetchone()[0])
disk.close()
os.remove(handle.name)
