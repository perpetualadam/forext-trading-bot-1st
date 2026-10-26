# R.74 Crash Window Analysis

The broker helper is reached only after both commits have returned and `submission_authorized` is true.

| Step | Crash before the step is durable | Next process |
| --- | --- | --- |
| 1. Close trigger | No journal row | No durable close exists. A missing journal still refuses submission |
| 2. Operation reserved in memory only | No journal row if the insert did not commit | Nothing to recover. No submission was allowed |
| 3. Reservation commit | Row is `CLOSE_PREPARED`, intent 0 | `recover` marks `reserved_without_submission_intent`. It does not submit. A new reserve is refused |
| 4. Submission-intent commit | Intent 1, state `CLOSE_SUBMITTING`, token stored | `recover` marks `crash_after_submission_intent` / `CLOSE_OUTCOME_AMBIGUOUS`. It does not submit |
| 5. Broker request begins | Same as step 4 if the response was not committed | Ambiguous. The broker may have received the request |
| 6. Broker accepts | Same until the response is marked | Ambiguous |
| 7. Response marked | Response state is durable | Recovery keeps that state and does not submit again |
| 8–9. Transaction verification | Pending or reconciliation row | The same operation id remains. No automatic retry |
| 10. Full confirmation commit | `CLOSE_FULLY_CONFIRMED` | Still blocks the trade id. Delete is allowed only for the matching local row |
| 11. Local delete | Row may still be present | Identity delete can remove that same row. A replacement row does not match |
| 12. Delete done, finalise not committed | Journal stays `CLOSE_FULLY_CONFIRMED` | The old trade id stays blocked. A new instance is not deleted |
| 13. Finalise commit | `CLOSE_FINALISED` releases the unique index | The local book is process memory, so the row's survival is not a journal claim |

A reservation with intent 0 is evidence that this code path had not entered the broker helper. That conclusion comes from the commit order, not from elapsed time. Recovery still refuses an automatic resubmit.

A crash after intent and before a durable response is ambiguous. An open trade, a flat snapshot, or a missed lookup does not clear it.

`test_restart_after_reserve_blocks_without_submission`, `test_restart_after_intent_is_ambiguous_and_not_retried`, and `test_subprocess_restart_keeps_intent` cover the committed boundaries. A power loss inside SQLite's fsync was not injected.
