# R.76 recovery state machine

States in `forex_bot/startup_recovery.py` lines 18–22:

- `RECOVERY_NOT_STARTED`
- `RECOVERY_IN_PROGRESS`
- `RECOVERY_COMPLETED`
- `RECOVERY_COMPLETED_WITH_QUARANTINE`
- `RECOVERY_BLOCKED`

`live_management_permitted` (line 106) is true only for `RECOVERY_COMPLETED` and `RECOVERY_COMPLETED_WITH_QUARANTINE`. It takes no override argument.

Cross-process claim: `_claim_run` (line 115) inserts `RECOVERY_IN_PROGRESS`. The partial unique index rejects a second insert. The loser returns `recovery_already_in_progress` and does not publish positions or resubmit entries. Test 48 inserts that row from another connection and the worker prints `RECOVERY_BLOCKED`.

A crash that leaves the row in progress does not expire. The next process stays blocked.

On a normal finish, `_finish_run` (line 138) updates that run id off `RECOVERY_IN_PROGRESS`, so a later startup can insert a new run. Test 47 runs the sequence twice and restores one row.

If the state is still `RECOVERY_IN_PROGRESS` in `finally`, it is set to `RECOVERY_BLOCKED` before the update.

The in-memory `_state` is process-local. The durable claim is the cross-process control. A boolean in a caller cannot mark recovery complete.
