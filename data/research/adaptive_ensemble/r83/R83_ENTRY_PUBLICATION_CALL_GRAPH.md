# R.83 entry publication call graph

Source inspection. Line numbers are the working tree after the R.83 `mark_entry` guard.

| Step | Function | Location | Journal | Memory |
| --- | --- | --- | --- | --- |
| 1 | `begin_entry_submission` | `entry_journal.py` 59 | Inserts the entry and the client-id registry, then sets intent 1 and `ENTRY_SUBMITTING` | None |
| 2 | `live_management_permitted` | `oanda_exec.py` 514 and `startup_recovery.py` 133 | SELECT fencing epoch | None |
| 3 | `claim_entry_permit` | `entry_journal.py` 198, called from `oanda_exec.py` 519 | `network_permit=1` | None |
| 4 | Second authority check | `oanda_exec.py` 548 | SELECT epoch | None |
| 5 | `acquire_oanda_rest_slot` | `oanda_exec.py` 554 | None | None |
| 6 | Third authority check | `oanda_exec.py` 555 | SELECT epoch | None |
| 7 | `api.request` OrderCreate | `oanda_exec.py` 557 | None | None |
| 8 | `record_entry_response` | `entry_capture.py` 48, called from `oanda_exec.py` 605 | Reads the entry row | None yet |
| 9 | `commit_verified_entry` | `entry_journal.py` 357, called from `entry_capture.py` 103 | One transaction writes `managed_positions` and `ENTRY_FINALISED` | None yet |
| 10 | `recovery_fence_allows_publication` | `startup_recovery.py` 123, called from `entry_capture.py` 112 | SELECT epoch | None |
| 11 | `positions[symbol] = pos` | `entry_capture.py` 134 | None | Manageable book |

The durable finalisation is the `ENTRY_FINALISED` update at `entry_journal.py` 429-440 and the transaction commit at line 453. The memory publication is the assignment at `entry_capture.py` 134. Those are separate statements. A crash or exception between them leaves the journal finalised and the book empty.

Before this stage, `_place_market_order_open_sync` caught any exception from `record_entry_response` and called `mark_entry(..., ENTRY_OUTCOME_AMBIGUOUS)`. `mark_entry` updated every outcome, including `ENTRY_FINALISED`. That would have replaced a committed entry with an ambiguous label. `mark_entry` now returns at line 281 when the outcome is already finalised.

`recover_entry_operations` does not rewrite `ENTRY_FINALISED`. Startup publishes the durable row when the snapshot matches and no unresolved entry blocks it (`startup_recovery.py` 285-323). A second `begin_entry_submission` for the same client hits the client-id registry and raises `client_order_id_retained`.

Recovery can reconstruct the trade id, instrument, direction, units, and account binding from `managed_positions` plus the finalised entry row. It does not send OrderCreate.
