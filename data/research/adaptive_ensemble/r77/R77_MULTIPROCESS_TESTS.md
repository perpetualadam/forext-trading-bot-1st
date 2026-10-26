# R.77 multiprocess tests

Worker: `data/research/adaptive_ensemble/r77/poc/repair_worker.py`. It imports the R.69 isolation harness before `forex_bot`. It does not import `oanda_exec` or `bot_loop`. The owner value is passed as `R77_OWNER` because an environment name containing `TOKEN` is scrubbed by the isolation harness.

Test 37 starts two processes with `Popen` before either is joined. Both call `begin_entry_submission` for client id `CID-PROC` on the same temporary journal and the same synthetic account binding. One printed `accepted`. The other printed a refusal. The journal contained one entry row and no broker submission.

Test 62 starts two repair processes the same way against one `RECOVERY_IN_PROGRESS` row. One printed `REPAIR_COMMITTED abandoned_claim_released`. The other printed a refusal. The run state was `RECOVERY_REPAIR_RELEASED`. Entry and close rows are not part of that update.

These processes share a local SQLite file. They do not share a broker. The result does not show that OANDA would reject the second client extension.

Restart coverage, in one process after the journal connection was closed and reopened:

- Test 09 restored a committed position into memory.
- Test 11 left a rolled-back finalisation unpublished and marked the intent ambiguous.
- Test 43 refused a finalised client id after reopen.
- Test 64 kept a committed repair after reopen.
- Test 65 ran a full startup after repair and did not delete the durable position.

WSL ran the journal-level atomic finalisation, migration, repair, and following startup in `test_r77_linux_journal.py` (2 passed). It did not run the multiprocess worker.
