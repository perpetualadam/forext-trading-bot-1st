# MACRO RESEARCH — PROSPECTIVE RECORDER STAGE 5
# PLATFORM-AGNOSTIC SCHEDULING / VPS PORTABILITY

Research-only portability refactor. No new forecast sources. No autonomous
collection. PIT/research semantics unchanged. No production trading authority.

CORE PLATFORM DEPENDENCIES BEFORE
---------------------------------
Application `collect-due` already calculated checkpoints in UTC, but the default
data root was CWD-relative (`data/research/macro/consensus_pit/prospective`).
The Stage 3 process lock used `ctypes.windll.kernel32.OpenProcess` on Windows.
Atomic temp files used a shared `*.tmp` name in the destination directory.
Windows Task Scheduler was documented as the primary runner. Linux/cron/systemd
wrappers did not exist.

CORE PLATFORM DEPENDENCIES AFTER
--------------------------------
Core Python (`_macro_prospective_recorder.py`, `_macro_prospective_scheduler.py`,
`_macro_prospective_adapters.py`, `macro_prospective_cli.py`):
- pathlib.Path only
- no `C:\` literals, no WindowsApps, no schtasks, no PowerShell, no ctypes
- no systemd/cron imports
- process lock: `O_CREAT|O_EXCL` + heartbeat; POSIX PID probe optional
- data root: `MACRO_PROSPECTIVE_DATA_DIR` or repository-relative from `__file__`

OS adapters (not application logic):
- `scripts/install_macro_prospective_task.ps1` (existing Windows task installer)
- `deploy/systemd/forex-macro-prospective.service` + `.timer`
- `deploy/cron/forex-macro-prospective.cron`
- `scripts/run_macro_prospective_collect_due.sh`
- `deploy/docker/collect-due.example.sh`

DATA ROOT
---------
Logical default: `data/research/macro/consensus_pit/prospective`
Env: `MACRO_PROSPECTIVE_DATA_DIR`
Resolution order: `--root` / explicit path, then env, then
`<repo>/data/research/macro/consensus_pit/prospective` from this module's file
path (not from an arbitrary shell CWD).
Do not commit host usernames or machine paths into application config.

UTC SEMANTICS
-------------
T0, window start, and all 11 checkpoints are timezone-aware UTC.
Host TZ (Windows local, VPS, DST, locale) does not change stored UTC checkpoints.
If the OS timer fires late after downtime, the application uses `now` and marks
`MISSED_NOT_OBSERVED`. systemd `Persistent=true` catch-up does not backdate.

PORTABLE LOCK
-------------
File lock at `<data-root>/scheduler/collect.lock`.
Exclusive create, heartbeat stale recovery (180s), POSIX `/proc` or signal-0
liveness when available. Windows does not use `os.kill` (it can terminate).
Scope: processes sharing this filesystem. Not a cross-host lock.

ATOMIC STORAGE
--------------
Writes go to `<dest-dir>/<name>.<pid>.tmp`, fsync, then `os.replace` onto the
destination on the same filesystem. Leftover `.tmp` files are never loaded as
authoritative JSON.

WINDOWS ADAPTER
---------------
Existing task `ForexMacroProspectiveCollectDue` is not modified by this task.
Command remains:
`python -m reports.decision_quality.macro_prospective_cli collect-due`
with WorkingDirectory = repository root. That remains compatible.

SYSTEMD ADAPTER
---------------
`deploy/systemd/forex-macro-prospective.service` — Type=oneshot, WorkingDirectory
placeholder `/path/to/forex-bot`, ExecStart python -m … collect-due.
`deploy/systemd/forex-macro-prospective.timer` — OnUnitActiveSec=5min, Persistent=true.
Replace placeholders. Do not install during this Windows-host task.

CRON ADAPTER
------------
`deploy/cron/forex-macro-prospective.cron`:
`*/5 * * * * /path/to/forex-bot/scripts/run_macro_prospective_collect_due.sh`
The wrapper cds to the repository root. Cron does not assume that CWD.

DOCKER DEPLOYMENT
-----------------
Do not modify the live trading-bot Dockerfile/compose.
Example: `deploy/docker/collect-due.example.sh` — separate oneshot container,
same `collect-due` command, `MACRO_PROSPECTIVE_DATA_DIR` on a persistent volume.
Not a second trading bot. No OANDA/trading imports.

SINGLE ACTIVE COLLECTOR
-----------------------
One active collector per prospective dataset. The lock does not coordinate a
Windows PC and a VPS writing independent copies. Controlled handoff only.
See `reports/decision_quality/macro_prospective_vps_migration.md`.

VPS MIGRATION
-------------
Documented in `reports/decision_quality/macro_prospective_vps_migration.md`.
Disable the old Windows scheduler only after the VPS collector is proven.

TEST RESULTS
------------
71 passed:
Stage 5 portability 7, Stage 4 sources 10, Stage 1 12, Stage 2 13, Stage 3 15,
consensus Stage 2 14.

PRODUCTION SAFETY
-----------------
No production signals, quant stub, RL, V2, routing, SL/TP/ATR, sizing, OANDA,
Telegram, model training, directional rule, or FX surprise backtest changes.
`FORWARD_CONSENSUS_COLLECTION_ENABLED=false`. Approved autonomous sources: NONE.
Official BLS adapter remains disabled.
