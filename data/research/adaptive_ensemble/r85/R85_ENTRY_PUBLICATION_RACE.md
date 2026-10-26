# R.85 Entry Publication Race

Evidence: executed `record_entry_response` on a disposable journal after a real startup, with the second fence call paused. A subprocess then ran `execute_startup_sequence`. No `OrderCreate` was issued by this test. The entry body was a synthetic fill.

Sequence:

1. The parent held a completed recovery epoch. The OS lock had already been released.
2. `begin_entry_submission` and `claim_entry_permit` committed the reservation and the one-shot permit.
3. `commit_verified_entry` ran before either fence check and stored `ENTRY_FINALISED`.
4. The first fence check returned true.
5. The second fence check waited.
6. The successor startup completed and incremented the epoch.
7. The second check then returned false.
8. The parent did not assign `positions["EUR_USD"]`.

Observed:

- `published` was false.
- The parent book did not contain EUR_USD.
- Exactly one entry row remained, outcome `ENTRY_FINALISED`.
- The recorder had no `OrderCreate` and no `PositionClose`.
- The client id was the one reserved for that operation.

The successor may publish in its own process if its snapshot matches and its epoch is current. That is the new owner. The test's assertion is about the stale parent.

A killed owner was not required for this case. The owner stayed alive and was still refused.

The window after the second check returns true and before the assignment is still two statements. The executed interleaving closed the window that was paused on the check. It did not show a durable overwrite or a second order.

`test_33` repeated this path and again saw a single `ENTRY_FINALISED` row.
