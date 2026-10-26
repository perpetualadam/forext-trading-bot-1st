# R.80 post-startup journal faults

Evidence class: executed `test_17`. Disposable journal only.

After a completed recovery:

- `arm_active_journal_fault("before_commit")` makes the next reservation raise `JournalUnavailable`. The synthetic broker call list stays empty.
- The test then closes the journal, calls `reset_journal_process_state()`, deletes the database and its `-wal` and `-shm` files, and writes `not a database`.
- `live_management_permitted()` becomes false. A following real cycle adds no write.

Overwriting the database file while a WAL connection is still open does not fail closed, because the WAL can restore the pages. The test removes that connection and the sidecar files before corrupting the bytes.

Not separately injected: a fault during snapshot reading, during position evaluation, after an entry permit claim, after a close permit claim, or during protection-progress persistence. Those rows are PARTIAL. The two executed faults fail closed and authorise no new write.

`R80_POST_STARTUP_JOURNAL_FAULTS_FAIL_CLOSED`: PASS for the executed faults. PARTIAL against the twelve-point list.
`SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` remains. A deleted file is not a power loss.
