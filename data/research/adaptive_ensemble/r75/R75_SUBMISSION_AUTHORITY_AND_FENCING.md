# R.75 Submission Authority and Fencing

## Window that cannot be made atomic with HTTP

The sequence is:

1. `claim_network_permit` commits `network_permit=1`.
2. The process then builds `PositionClose` and calls `api.request`.

A database check before the request is not atomic with the broker HTTP call. This stage does not claim exactly-once broker execution. `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` remains.

## What the fence does guarantee in the journal

| Event | Journal result | Second close |
| --- | --- | --- |
| Second process calls `reserve` for the same account binding, instrument, and trade id | Unique index `one_unresolved_close` | Refused before HTTP |
| Same permit presented again | `network_permit` is already 1, update matches 0 rows | `CloseGuardRefusal`, no HTTP |
| Stale owner token | Token predicate fails | `CloseGuardRefusal`, no HTTP |
| Process exits after the claim and before or after broker acceptance | `recover` does not clear `network_permit` and does not submit | Restart stays blocked |
| Ambiguous outcome | Confirmation stays unresolved and the unique index still applies | No new reserve |
| Journal lock timeout or `before_reserve_commit` fault | `journal_lock_or_disk` or `injected_before_reserve_commit` | No HTTP |
| Busy timeout | Does not authorise a fallback submission | No HTTP |

`recover` (`close_journal.py`, `_recover_locked`) moves intent-0 rows to reconciliation and intent-1 rows to `CLOSE_OUTCOME_AMBIGUOUS` or keeps a partial or full confirmation. It does not clear `network_permit`.

## Process evidence

`test_process_paused_after_claim_blocks_the_other` holds process A inside the synthetic `PositionClose` request, which is after the claim. Process B's guarded close returns without inserting a recorder row. After A is released, the recorder count is 1.

`test_two_processes_submit_once_through_the_guard` starts two processes together, then a third after both have exited. The shared recorder count is 1, then still 1.

A crashed owner is not replaced by a lease. There is no takeover path.
