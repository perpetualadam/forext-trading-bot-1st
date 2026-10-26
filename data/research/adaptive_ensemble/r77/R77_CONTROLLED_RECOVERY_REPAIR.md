# R.77 controlled recovery repair

`forex_bot/recovery_repair.py` is not imported by `startup_recovery.py` or `bot_loop.py`. A crashed `RECOVERY_IN_PROGRESS` row still blocks the next startup until an operator runs `repair_abandoned_recovery`.

The module does not inspect the operating system. The caller supplies `ProcessLivenessEvidence`. A stale timestamp is not accepted. A PID is not accepted. Approval requires all three:

- `status == "inactive"`
- `method == "owner_token_and_exit_observation"`
- `observed_owner_token` equal to the recovery row's `owner_token`

`active` returns `recovery_owner_active`. `unknown` returns `process_status_unknown`. `pid` or `pid_reused` returns `pid_reuse_ambiguous`. `timestamp` returns `timestamp_not_sufficient`.

Other preconditions:

- `operator_acknowledged` is true and the acknowledgement text is non-empty.
- `journal_path` resolves to `CLOSE_JOURNAL_PATH`. A different path returns `wrong_journal` and does not release the claim. The other file is not opened.
- `open_journal` has already accepted the schema and integrity check through `active_journal`.
- The target run is `RECOVERY_IN_PROGRESS`. Otherwise the result is `recovery_claim_missing`.
- No entry, close, or managed-position row carries a different account binding.

The repair transaction (`_record`, lines 95–176) counts unresolved entries (`outcome != ENTRY_FINALISED`) and unresolved closes (state not `CLOSE_REJECTED_CONFIRMED` or `CLOSE_FINALISED`). It does not update those rows. On approval it sets the run to `RECOVERY_REPAIR_RELEASED` and inserts one `recovery_repairs` row, then commits both. `BEGIN IMMEDIATE` is the cross-process lock. A second process that arrives after the commit sees the run is no longer `RECOVERY_IN_PROGRESS` and writes a refusal.

After release, the partial unique index `one_recovery_in_progress` allows the next startup to insert a new run. `execute_startup_sequence` still performs close recovery, entry recovery, broker classification, and publication. Repair does not publish `positions`.

The authorisation object has no trading flag, no broker client, and no permit path. Tests 57–59 observed zero orders, zero deletions, and an empty memory book.
