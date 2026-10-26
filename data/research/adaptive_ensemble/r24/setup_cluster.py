"""Create the approved R.24 cluster. Does not print secrets."""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
from pathlib import Path

BIN = Path(r"C:\Program Files\PostgreSQL\18\bin")
ROOT = Path(r"C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st")
R24 = ROOT / "data" / "research" / "adaptive_ensemble" / "r24"
PGDATA = R24 / "pgdata"
SECRET_DIR = R24 / "secrets"
LOG_DIR = R24 / "pglog"


def _run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def main() -> int:
    if (PGDATA / "PG_VERSION").exists() or (PGDATA / "postgresql.conf").exists():
        print("STOP existing cluster")
        return 2
    SECRET_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    bootstrap = secrets.token_urlsafe(24)
    tester = secrets.token_urlsafe(24)
    (SECRET_DIR / "bootstrap.txt").write_text(bootstrap + "\n", encoding="utf-8")
    (SECRET_DIR / "tester.txt").write_text(tester + "\n", encoding="utf-8")
    (SECRET_DIR / "identity.json").write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": 55432,
                "database": "r24_synthetic_orders",
                "application_role": "r24_tester",
                "bootstrap_role": "r24_bootstrap",
                "data_directory": str(PGDATA),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    init = _run(
        [
            str(BIN / "initdb.exe"),
            "-D",
            str(PGDATA),
            "-U",
            "r24_bootstrap",
            "--pwfile",
            str(SECRET_DIR / "bootstrap.txt"),
            "--auth-host=scram-sha-256",
            "--auth-local=scram-sha-256",
            "--encoding=UTF8",
            "--no-locale",
            "--no-instructions",
            "-c",
            "listen_addresses=127.0.0.1",
            "-c",
            "port=55432",
            "-c",
            "password_encryption=scram-sha-256",
        ]
    )
    if init.returncode != 0:
        print("STOP initdb")
        print(init.stderr[-2000:])
        return 3
    hba = PGDATA / "pg_hba.conf"
    hba.write_text(
        "\n".join(
            [
                "# R.24 approved cluster only. No trust entries.",
                "host postgres r24_bootstrap 127.0.0.1/32 scram-sha-256",
                "host r24_synthetic_orders r24_bootstrap 127.0.0.1/32 scram-sha-256",
                "host r24_synthetic_orders r24_tester 127.0.0.1/32 scram-sha-256",
                "",
            ]
        ),
        encoding="utf-8",
    )
    start = _run(
        [
            str(BIN / "pg_ctl.exe"),
            "-D",
            str(PGDATA),
            "-l",
            str(LOG_DIR / "server.log"),
            "-w",
            "-t",
            "40",
            "start",
        ]
    )
    if start.returncode != 0:
        print("STOP pg_ctl start")
        print(start.stdout[-1000:])
        print(start.stderr[-1000:])
        return 4
    print("CLUSTER_STARTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
