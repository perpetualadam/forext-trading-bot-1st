# R.79 Startup Order Trace

Evidence class: source inspection of `forex_bot/startup_recovery.py` and `forex_bot/bot_loop.py`, confirmed by the R.79 harness. The order was not taken from a design note.

`run_startup_and_one_iteration` calls `execute_startup_sequence` and then awaits `_execute_bot_cycle`. The exact `execute_startup_sequence(load_startup_broker_view())` call remains when no view is injected.

Inside `execute_startup_sequence` (`startup_recovery.py` 231–341):

1. State becomes `RECOVERY_IN_PROGRESS`.
2. `active_journal()` validates the schema. Any version other than 5 raises `JournalUnavailable`, and the function returns `RECOVERY_BLOCKED`.
3. `_claim_run` (`155–210`) acquires the OS recovery-owner lock. Failure returns `recovery_already_in_progress` and does not publish.
4. The same transaction increments `recovery_authority.fencing_epoch` and inserts the `recovery_runs` row. The in-memory epoch is assigned only after commit.
5. `recover_entry_operations()` runs.
6. The in-memory book is cleared.
7. Blocking snapshots (`INCOMPLETE`, `MALFORMED`, `REQUEST_FAILED`, `STALE`, `UNAVAILABLE`, `UNKNOWN`, `CONFLICT`, or a missing view) return `broker_snapshot_not_authoritative` before publication.
8. Broker-only discoveries are classified and are not written into the managed book.
9. `recovery_fence_allows_publication()` is checked. Failure returns `recovery_fence_lost` before the publish loop.
10. Each durable row is checked for entry linkage, then `evaluate_durable_row`, then `publish_recovered`.
11. `_finish_run` records the terminal state and releases the OS lock. The in-memory epoch remains.

`live_management_permitted()` is true only for `RECOVERY_COMPLETED` or `RECOVERY_COMPLETED_WITH_QUARANTINE` when the in-memory epoch matches the journal. `RECOVERY_IN_PROGRESS` can publish during step 10 and cannot manage or send orders.

The bot-cycle management gate at `bot_loop.py` 796–802 runs only for an existing live position. New broker opens reach `_submit_order_create`, which checks `live_management_permitted()` again. A failed recovery can still enter `_execute_bot_cycle`. That invocation is not authorised management: tests 02, 11, and 14 observed the cycle and observed management false.

If `_claim_run` raises `JournalUnavailable` after the journal opened, that exception leaves `execute_startup_sequence` and the cycle is not reached. Corrupt and unsupported journals are caught earlier and still reach the cycle with management blocked.
