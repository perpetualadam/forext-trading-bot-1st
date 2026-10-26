# R.85 Publication Atomicity Design

Evidence: source inspection of lock acquisition and the executed races. No new lock service and no lease were added. The schema was not changed.

## Existing primitives

| Primitive | Scope | When it is held |
| --- | --- | --- |
| OS recovery lock | Cross-process | From `_claim_run` until `_finish_run` |
| Fencing epoch | Durable integer | Incremented in the same journal transaction as the claim |
| Journal `BEGIN IMMEDIATE` | The journal connection's writer | Around one close or entry transaction |
| `_book_lock` | This process's position dict | Around book replacement and the pop |

Order during startup: acquire OS lock, increment epoch, commit, run recovery, take `_book_lock` only to clear or place rows, release the OS lock in `finally`. Recovery does not hold `_book_lock` across the epoch transaction.

Order during close removal when an epoch exists: identity checks under `_book_lock` without a journal write, release the book lock, `finalise` with the expected epoch, then take `_book_lock` again and pop only if finalisation committed. `finalise` reads `fencing_epoch` and updates the close row before it commits. A successor that already committed a new epoch makes the row count fail and the transaction roll back.

Order when no epoch is set: pop, then `finalise` without an epoch predicate. That preserves the R.74 journal path. Those 20 tests passed on Windows and Linux.

## What this closes

A stale owner that reaches `finalise` after a real successor has committed cannot change the close from `CLOSE_FULLY_CONFIRMED` to `CLOSE_FINALISED`. That was executed.

A stale owner whose second entry fence observes the new epoch cannot publish into its own book. That was executed.

## What this does not close

The OS lock does not cover the bot cycle. Two live processes can exist after the first startup finishes. Their position dicts are not shared. A broker submission still has its own later `live_management_permitted` check. The earlier `FINAL_CHECK_TO_REQUEST_RACE_REPRODUCED` risk remains: a check that has already returned true is not the same statement as `api.request`.

Holding `_book_lock` while taking the journal lock was avoided so startup's journal-then-book order does not invert against publication.

Deadlock was not observed in the bounded races. Waits were 15 seconds. No wait was left unbounded.

This is not a proposal to hold the OS lock for the life of the process. That would block recovery after a clean startup and was not implemented.
