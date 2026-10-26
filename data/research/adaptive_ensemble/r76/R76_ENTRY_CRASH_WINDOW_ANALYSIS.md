# R.76 entry crash-window analysis

The tests use a temporary journal and a synthetic `api.request`. They do not kill power or fsync. `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` remains.

| Window | Durable result | Next process |
| --- | --- | --- |
| Before `begin_entry_submission` commits | no row | no order was sent |
| Reservation commit fails (`before_commit`, test 18) | no row | `OrderCreate` count 0 |
| After reservation, before intent | intent 0 | `ENTRY_RECONCILIATION_REQUIRED`; no automatic retry |
| After intent, before claim (test 22) | `ENTRY_SUBMITTING`, permit 0 | `ENTRY_OUTCOME_AMBIGUOUS`; same client id refused |
| After claim, timeout (test 23) | permit 1, `ENTRY_OUTCOME_AMBIGUOUS` | no second `OrderCreate` |
| After claim, before a trade id is stored (test 34) | ambiguous entry, no managed row | broker trade in the view is not published; no close |
| After `persist_bot_position`, before memory publish (tests 35 and 36) | durable row plus confirmed entry | startup publishes the same trade id when the view matches |
| After memory publish (test 37) | durable row and `ENTRY_FINALISED` | a new process reloads the same instance id |

A missing response is not classified as a reject. Test 08 and test 23 keep the operation unresolved.

Read-only recovery in test 24 calls `recover_entry_operations` and `execute_startup_sequence` with an empty `api.calls` list. The unresolved broker trade is not placed in `positions`.

Two processes in test 20 share one client id. The first reaches a synthetic `OrderCreate` and waits. The second receives `unresolved_entry_exists`. The recorder contains one row.
