# R.85 Authority Publication Race

Evidence: source inspection of `execute_startup_sequence`, `RecoveryOwnerLock`, `record_entry_response`, and `close_confirmed_live_position`. Executed races are `test_29`, `test_30`, `test_31`, `test_32`, and `test_46`.

## What is and is not a handoff

| Event | Meaning |
| --- | --- |
| Successor `execute_startup_sequence` while the OS lock is free | Genuine handoff. The successor increments `fencing_epoch`. |
| `UPDATE recovery_authority` from the test | Fault injection. Not a takeover. |
| Owner paused inside the process after a check, still alive | Stale owner if the epoch has moved. |
| `process.kill` before release | Dead owner. It cannot resume. |
| Assignment to `positions` | Process-local. It does not change the other process's book. |
| `journal.finalise` | Durable. It can change what a later startup treats as blocking. |

The OS lock is acquired in `_claim_run` and released in `_finish_run` when startup returns. It is not held across a later bot cycle. A second process can therefore complete startup while the first process is alive. That was executed. The successor printed `RECOVERY_COMPLETED_WITH_QUARANTINE`, a higher epoch, and `manageable=0`.

A direct epoch increment was also executed. `close_confirmed_live_position` returned `None` and the close stayed `CLOSE_FULLY_CONFIRMED`. That result is the fence, not evidence of a legal takeover.

The lock was not weakened. No lease was added.

## Check versus mutation

Entry publication checks `recovery_fence_allows_publication` and then assigns. A second check now runs immediately before the assignment. The tested pause is inside that second check. The successor ran, and the stale owner published nothing.

Close removal checks `live_management_permitted` and later calls `finalise`. With an epoch, `finalise` compares the epoch and updates the close row in one `BEGIN IMMEDIATE`. The tested pause is inside `finalise` before that transaction. The successor committed a new epoch. The original transaction then refused. Memory was not popped. The row stayed `CLOSE_FULLY_CONFIRMED`.

The statements are still separate. The durable close write is conditional on the epoch inside the same transaction, which is the part that can affect a later startup. The entry assignment remains process-local after its second check returns.
