# R.82 close-confirmation persistence

`_persist` in `broker_close_evidence.py` updates the in-memory operation and then calls `journal.mark`. `JournalUnavailable` is caught and does not by itself revert the memory state. `close_confirmed_live_position` in `positions.py` reads the journal row and returns without removing the position unless that row is `CLOSE_FULLY_CONFIRMED`, the units match a full close, and the position identity matches.

## Executed — `test_13_close_confirmation_commit_does_not_remove_position`

The synthetic PositionClose returns a full-looking fill. `TransactionDetails` then arms `before_commit`, so the confirmation commit fails.

| Record | Result |
| --- | --- |
| PositionClose count | 1 |
| TransactionDetails | Armed the one-shot commit fault |
| Journal confirmation | Not `CLOSE_FULLY_CONFIRMED` |
| `network_permit` | 1 |
| `close_confirmed_live_position` | `None` |
| In-memory position units | 1000 |
| Second `run_guarded_live_close` | PositionClose count stays 1 |

The response is synthetic. It is not OANDA evidence.

## Other persistence points

| Point | Evidence |
| --- | --- |
| Before response interpretation | A timeout in `test_18` is classified `CLOSE_OUTCOME_AMBIGUOUS` with one PositionClose |
| After interpretation, before the confirmation commit | `test_13` |
| During the confirmation commit | `test_13` (`before_commit`) |
| After a durable confirmation, memory removal | Removal is refused when the journal is not fully confirmed (`test_13`, `test_15`). A fault injected only after a successful full commit was not run. `NOT_VERIFIED` as a separate case |
| Recovery after a failed confirmation write | `test_14` restarts claimed-but-unanswered entry and close operations as ambiguous. `test_13` reopens the faulted close and it is not fully confirmed |

No permit was released. No second PositionClose was sent for the faulted operation. No transaction id was invented by the journal when the confirmation commit failed.
