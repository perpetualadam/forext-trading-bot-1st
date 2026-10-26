# R.85 Close Removal Race

Evidence: executed full close to `CLOSE_FULLY_CONFIRMED`, then `close_confirmed_live_position` paused inside `finalise` before its transaction. A subprocess successor ran real startup. A separate test killed the process that had finished the close and was waiting, then started a successor.

## Live owner

- The pause happened after the opening authority check and after the identity checks.
- The successor acquired the lock, incremented the epoch, and finished startup.
- Its report was `RECOVERY_COMPLETED_WITH_QUARANTINE` with `manageable=0`.
- The parent's `finalise` then saw a different epoch and raised `finalise_refused`.
- `close_confirmed_live_position` returned `None`.
- The parent book still held EUR_USD.
- The journal state remained `CLOSE_FULLY_CONFIRMED`.
- `PositionClose` count stayed 1.
- The row was not moved to `CLOSE_FINALISED`.

`CLOSE_FINALISED` was not treated as a new broker transaction. It was not written.

## Dead owner

`pause-after-full` committed the full close, then waited. `process.kill` ran before any finalisation. The successor saw `CLOSE_FULLY_CONFIRMED`, `manageable=0`, and one `PositionClose`. The dead process did not resume.

## Fault injection

Incrementing `fencing_epoch` with SQL, without a successor startup, also made `close_confirmed_live_position` return `None`. That is not a legal handoff. It shows the same epoch predicate.

No duplicate memory removal occurred. No permit was reused. The successor did not submit a close.
