# R.77 remaining risks

Production remains NO-GO.

Retained labels:

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`. The journal can refuse a reused client id. OANDA's treatment of `clientExtensions.id` was not executed.
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`. Process-restart and `before_commit` faults are not a power-loss experiment.
- `LINUX_INTEGRATION_NOT_VERIFIED`. Journal repair and atomic finalisation ran under WSL. `bot_loop` and `oanda_exec` did not.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`.
- `POSTGRESQL_INTEGRATION_NOT_TESTED`.
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`.

R.66 items still open and outside this stage:

- R66-03: `broker_sl_tp_hit` in `live_manage.py` remains a local false result. The file hash is unchanged.
- R66-07: sizing currency was not recalculated.
- R66-10 and R66-11: duplicate close suppression is journal-side. It is not a broker idempotency proof.
- R66-16: outside this stage.

A finalised entry is not evidence the trade is still open. Startup can still quarantine it when the snapshot is empty, incomplete, or disagrees. Repair does not remove that need.

`COMPLETED_WITH_QUARANTINE` allows management of positions that were actually published. Quarantined rows stay out of `positions`. An ambiguous entry with no position does not by itself block management of a different symbol.

Schema 3 files fail closed until an operator migrates a copy. Duplicate historical client ids stop that migration. There is no automatic rewrite.

The client-id registry dies with the journal file. Replacing the file starts a new history.

`_submit_order_create` still slices a client extension to 128 characters. The journal refuses longer ids before that line, but the slice remains in the unchanged OANDA module.
