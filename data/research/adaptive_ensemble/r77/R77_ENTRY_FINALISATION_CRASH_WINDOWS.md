# R.77 entry-finalisation crash windows

The R.76 success path in `record_entry_response` made three separate SQLite commits: evidence outcome, `persist_bot_position`, then `ENTRY_FINALISED`. A crash between those commits could leave a durable position without a final entry, or a confirmed entry without a position. A Python dictionary write is not part of either commit.

The R.77 success path removes that gap.

1. `classify_entry_response` (`forex_bot/broker_entry_evidence.py` lines 63–175) is pure. It performs no database write and no network call.
2. A non-publishable outcome calls `mark_entry` once (`forex_bot/entry_capture.py` lines 74–86) and returns with `published` false. No managed position is inserted.
3. A missing stop or take profit is marked `ENTRY_RECONCILIATION_REQUIRED` (lines 59–73) and is not finalised.
4. A publishable single trade calls `commit_verified_entry` (lines 96–102). That function inserts the managed position and sets `ENTRY_FINALISED` before one `_commit`.
5. `positions[symbol]` is assigned only after that commit returns (lines 104–121).

## Crash points

| Point | Durable entry | Durable position | Memory | Next startup |
| --- | --- | --- | --- | --- |
| Before `commit_verified_entry` | `ENTRY_SUBMITTING` | absent | empty | Intent 1 becomes `ENTRY_OUTCOME_AMBIGUOUS`. Nothing is published. |
| `before_commit` fault inside the transaction | rolled back to `ENTRY_SUBMITTING` | absent | empty | Same ambiguous recovery. The production caller then marks `capture_failed`. |
| After commit, before `positions[symbol] = pos` | `ENTRY_FINALISED` | present | empty | `execute_startup_sequence` can restore a matching broker trade. |
| After memory publication | `ENTRY_FINALISED` | present | symbol present | Restart clears memory and reloads the durable row. |
| Slot holds another instance | `ENTRY_FINALISED` | present | old instance kept and marked `recovery_quarantine` | The other instance is not overwritten. |

A finalised row does not prove the trade is still open at the broker. Startup still requires a matching read-only broker view before publication (`evaluate_durable_row`, `forex_bot/position_recovery.py` lines 299–341). `COMPLETE_EMPTY` quarantines the row as `broker_flat_unattributed` and does not delete it.

Tests 01, 03, 05, 07, 09, and 11 recorded entry state, position state, memory keys, and synthetic broker submissions for these windows. Broker submission count on the direct `record_entry_response` path was 0. Test 25 used one synthetic `OrderCreate` and then a commit fault; the entry became `ENTRY_OUTCOME_AMBIGUOUS` and no position row remained.
