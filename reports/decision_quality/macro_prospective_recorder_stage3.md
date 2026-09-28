# MACRO RESEARCH — PROSPECTIVE RECORDER STAGE 3
# AUTOMATIC CHECKPOINT SCHEDULER + SAFE COLLECTION ORCHESTRATOR

Research-only. No directional trading rule. No model. No production trading authority.
Historical GOLD/SILVER evidence was not rewritten. Official US PIT archive was not modified.
Windows Scheduled Task was prepared but NOT installed.

SCHEDULER ARCHITECTURE
----------------------
Windows Task Scheduler (not installed yet) invokes a short-lived command:

    python -m reports.decision_quality.macro_prospective_cli collect-due

from the repository working directory. The process loads the host prospective
store, classifies predefined checkpoints, processes newly due ones once, and
exits. There is no daemon.

Core: `reports/decision_quality/_macro_prospective_scheduler.py`
CLI: `reports/decision_quality/macro_prospective_cli.py`
Installer (do not run yet): `scripts/install_macro_prospective_task.ps1`
Verify: `scripts/verify_macro_prospective_task.ps1`

Scheduler may run while FORWARD_CONSENSUS_COLLECTION_ENABLED=false.
Sources do not become enabled because a scheduler exists.

5-MINUTE INVOCATION DESIGN
--------------------------
Task interval: 5 minutes, so T0-5m is not routinely skipped.
The process is idle/cheap when no window is active.
Zero external requests when no event is in-window, no checkpoint is due, or
no source is fully enabled. A 5-minute wake is not a 5-minute scrape.
The research design still uses only the 11 predefined checkpoints.

CHECKPOINT PROCESSING
---------------------
Due at checkpoint_utc until the next checkpoint (or T0 for T0-5m).
processed key: `{macro_event_id}|{checkpoint_id}`
First processing records CHECKPOINT_DUE then adapter results.
Repeats: ALREADY_PROCESSED.
observed_at_utc is the recorder clock at processing. checkpoint_utc is stored
separately. No backdating.

MISSED CHECKPOINT POLICY
------------------------
If now is past the checkpoint interval with no qualifying pre-release
observation: MISSED_NOT_OBSERVED. No current-page backfill. Later checkpoints
can still be collected.

SOURCE PERMISSION GATE
----------------------
Before any adapter collect():
- source exists
- FORWARD_CONSENSUS_COLLECTION_ENABLED is true
- source.enabled is true
- automated_collection_permitted is true
Otherwise: NO REQUEST. unknown permission fails closed.

COLLECTION ADAPTER INTERFACE
----------------------------
CollectionAdapter: source_id, is_enabled(rec), supports(event), collect(...)
Results: SUCCESS, NO_DATA, SOURCE_DISABLED, SOURCE_UNAVAILABLE, RATE_LIMITED,
ACCESS_DENIED, PARSE_FAILED, INVALID_SERIES, plus gate reasons.
Production adapters are NeverFetchAdapter. They never HTTP/API fetch.
Official first-print auto-fetch is OFF. RELEASE_PENDING logs FIRST_PRINT_REQUIRED.

PROCESS LOCK
------------
`scheduler/collect.lock` exclusive create, PID + heartbeat.
BUSY: second instance exits 0 (LOCK_BUSY).
Stale if heartbeat age > 180s or PID dead.

ATOMIC STATE
------------
`scheduler/state.json` via temp file + fsync + os.replace.
Leftover `.tmp` does not replace the last good state.

AUDIT LOG
---------
`data/research/macro/consensus_pit/prospective/scheduler/audit.jsonl`
Events: SCHEDULER_STARTED, NO_EVENT_ACTIVE, CHECKPOINT_DUE, CHECKPOINT_PROCESSED,
SOURCE_DISABLED/NO_ENABLED_SOURCE, OBSERVATION_CAPTURED, CHECKPOINT_MISSED,
LOCK_BUSY, ERROR, FIRST_PRINT_REQUIRED.
No credentials. No proprietary artifact bodies.
Optional local hook: `scheduler/operator_attention.jsonl` (MANUAL_FORECAST_CAPTURE_REQUIRED).
No Telegram/email/SMS.

WINDOWS TASK DESIGN
-------------------
Name: ForexMacroProspectiveCollectDue
Python: resolved at install time (`py -3 -c "import sys; print(sys.executable)"`)
WorkingDirectory: C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st
Arguments: -m reports.decision_quality.macro_prospective_cli collect-due
Interval: 5 minutes
MultipleInstances: IgnoreNew
StartWhenAvailable: yes (application logic still marks missed intervals)
Not registered in this stage.

DRY RUN
-------
`python -m reports.decision_quality.macro_prospective_cli collect-due --dry-run`
Zero external requests. Zero observations. Zero scheduler state writes.
Real dry-run at 2026-09-28T21:56:55Z: NO_EVENT_ACTIVE, EXTERNAL REQUESTS 0,
scheduler directory not created, observations 0.

TEST RESULTS
------------
python -m pytest tests/test_macro_prospective_recorder_stage1.py tests/test_macro_prospective_recorder_stage2.py tests/test_macro_prospective_recorder_stage3.py tests/test_macro_consensus_pit_stage2.py -q
54 passed.

PRODUCTION SAFETY
-----------------
No production signal, quant, RL, V2, routing, SL/TP, ATR, profit protection,
sizing, portfolio, OANDA, live execution, or Telegram changes.
No training. No directional rule. No FX surprise backtest.
Live bot container was not restarted/recreated.
