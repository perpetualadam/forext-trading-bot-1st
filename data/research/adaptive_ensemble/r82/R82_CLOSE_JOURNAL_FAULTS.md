# R.82 close journal faults

The close path is `run_guarded_live_close` into `_submit_position_close_body`. A managed EUR_USD BUY position is persisted with `persist_bot_position` after a real startup.

| Test | Fault | PositionClose | Permit | Confirmation |
| --- | --- | --- | --- | --- |
| `test_03_close_authority_missing_before_claim` | Authority row deleted before the call | 0 | `network_permit=0` | Not `CLOSE_FULLY_CONFIRMED` |
| `test_05_close_authority_missing_after_claim` | Row deleted on the second check | 0 | `network_permit=1` | Not fully confirmed |
| `test_07_close_journal_unreadable_after_rate_limit` | Connection closed inside the slot | 0 | `network_permit=1` after reopen | Not fully confirmed. The failure persist raises `ProgrammingError` because the connection is already closed |
| `test_09_close_authority_row_removed_during_slot` | Row deleted inside the slot | 0 | `network_permit=1` | A second `run_guarded_live_close` adds no PositionClose |

`test_07` is fail-closed for the broker call. The exception leaves the function instead of returning an operation object. Reopening the journal shows the permit consumed and the close not fully confirmed. That reopen is what the test treats as the durable record. The in-function persist cannot update a closed connection.

No close permit was reset to unused. No automatic second PositionClose was sent for these faults.
