# Prospective recorder — VPS migration (controlled single-collector handoff)

Research-only. This is a procedure document, not an instruction to migrate now.
Leave the existing Windows task `ForexMacroProspectiveCollectDue` running until a
Linux VPS collector is proven. Do not enable autonomous forecast sources here.

SINGLE ACTIVE COLLECTOR
-----------------------
The portable process lock only coordinates processes that share the **same**
lock file on the **same** filesystem. It does **not** coordinate:
- this Windows PC and a VPS
- two containers with separate volumes
- two clones of `data/research/macro/consensus_pit/prospective`

Never run two independent hosts collecting the same prospective dataset.
Future distributed locking is out of scope.

Canonical command (identical on every host):
    python -m reports.decision_quality.macro_prospective_cli collect-due

HANDOFF SEQUENCE
----------------
1. Windows remains the sole collector. Do not start systemd/cron yet.
2. Copy/deploy the repository to the VPS (application code + `reports/`).
3. Restore the persistent prospective tree onto VPS durable storage:
   `data/research/macro/consensus_pit/prospective/`
   including events, observations, artifacts, manifests, source registry,
   config, and scheduler state/audit. Use a consistent snapshot; do not merge
   two live writers.
4. Configure host-local environment (do not commit secrets or usernames):
   - `MACRO_PROSPECTIVE_DATA_DIR=<absolute prospective path>`
   - `FORWARD_CONSENSUS_COLLECTION_ENABLED=false`
   Example file: `deploy/env/forex-macro-prospective.env.example`
5. On the VPS only, from the repository root:
   - `python3 -m reports.decision_quality.macro_prospective_cli status`
   - `python3 -m reports.decision_quality.macro_prospective_cli collect-due --dry-run`
   Confirm real observations are unchanged and external requests stay 0 while
   sources remain disabled.
6. Install the systemd timer **without** enabling it as the live collector until
   Windows is stopped, or install but keep the service masked until handoff:
   - edit `WorkingDirectory=` and `ExecStart=` python path in
     `deploy/systemd/forex-macro-prospective.service`
   - `OnUnitActiveSec=5min` in `deploy/systemd/forex-macro-prospective.timer`
   Alternative: cron `*/5 * * * *` via `scripts/run_macro_prospective_collect_due.sh`
7. **Handoff moment (one collector):**
   a. Disable/stop the Windows Scheduled Task (only at this step, not before).
   b. Confirm no further Windows `collect-due` runs.
   c. Enable the VPS timer/cron.
   d. Run one `collect-due` on the VPS and inspect `scheduler/audit.jsonl`.
8. If a checkpoint interval passed during the copy/handoff window, the
   application must record `MISSED_NOT_OBSERVED`. Do not backdate. systemd
   `Persistent=true` catch-up is only another `collect-due` at current UTC.

DOCKER
------
If collect-due runs in a container, mount the prospective directory on
**persistent** storage. Do not use the live trading-bot container. Do not grant
trading/OANDA authority. Example sketch: `deploy/docker/collect-due.example.sh`.

ROLLBACK
--------
If the VPS is not healthy: stop VPS timer/cron, restore the last consistent
prospective snapshot onto Windows if needed, re-enable the proven Windows task.
Again: one writer only.
