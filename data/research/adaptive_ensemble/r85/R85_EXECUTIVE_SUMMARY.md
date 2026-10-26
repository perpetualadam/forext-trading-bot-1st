# R.85 Executive Summary

Classification: `R85_EXPOSURE_AND_AUTHORITY_PARTIALLY_VERIFIED`

Production trading remains NO-GO. R.86 was not started. Quarantine was not released.

## What this stage verified

The R.84 baseline was intact before the R.85 edits. Git HEAD remained `d080d897945bc44fa37c02caab504ed707146bec` on `main`. The R.84 archive matched its recorded size, member count, manifest count, and SHA-256. The four live-session gates stayed disabled. `one_session.permit` stayed absent. The consumed-marker digest stayed unchanged. No live or practice broker call, credential read, PostgreSQL connection, or production journal open was made.

A partial close of 400 units from an original 1,000-unit position keeps those quantities distinct:

- Durable original units remain 1,000.
- Durable confirmed closed units are 400.
- Durable journal remaining units are 600.
- In-memory `Position.units` remains the original 1,000.
- Manageable units stay 0.

A complete synthetic snapshot of 600 is quarantined as `units_mismatch` because recovery compares the snapshot with the durable original units. It is not adopted as manageable exposure. Conflicting, empty, incomplete, stale, failed, and wrong-identity snapshots also stay unmanageable. No second `PositionClose` is submitted and the consumed close permit stays consumed.

## What was changed

Six operational files changed. The signed-unit parser was not replaced and `profit_protection.py` was not edited.

- `close_journal.py`: finalisation can require the current fencing epoch inside the same immediate transaction. A new read finds any unresolved close on an instrument.
- `positions.py`: when a recovery epoch is active, finalisation happens before memory removal and is refused if the epoch has moved.
- `entry_capture.py`: a second recovery-fence check runs immediately before memory publication.
- `position_recovery.py`: a symbol with a quarantined row or an unresolved close blocks a new entry.
- `bot_loop.py`: `_evaluate_impl` returns before a new entry when that exposure check is true.
- `broker_close_evidence.py`: a second, different transaction id does not replace an already stored close confirmation. The signed-unit rules are unchanged.

## What remains unverified

The startup view has no snapshot timestamp, pagination cursor, or transaction watermark. `STALE` and `INCOMPLETE` are labels the recovery code already honours. The live fetch does not compute them. A 600-unit snapshot is therefore not evidence of a fresh post-close remainder. Quarantine release was specified and not implemented.

A genuine successor startup can acquire the recovery lock after the original startup has released it, including while the original process is still alive and paused after its authority check. The tested close path then refuses durable finalisation. The tested entry path then refuses memory publication. A direct SQL epoch update is a fault injection, not that handoff. A killed process cannot resume and finalise.

The residual window after a fence check has already returned true is process-local. The tested interleavings did not let a stale owner finalise the journal or submit another order.

## Tests

Windows CPython 3.13.5 and Linux CPython 3.12.3 both ran 48 R.85 tests, all passing. R.80, R.79, R.78, R.74 journal, and R.71 matched their prior green counts on both platforms. R.83 and R.82 each kept the one obsolete negative-unit failure. R.84 and R.81 each gained one hash-pin failure because `positions.py` and `position_recovery.py` changed. Older suite counts matched the R.84-stage baseline.

## Explicit answers

After a partial close, the bot can distinguish original units, confirmed closed units, and journal remaining units. It does not treat journal remaining units as proven broker exposure. It does not make the position manageable.

A genuine recovery handoff can occur after startup has released the OS lock and before a later memory mutation. In the tested close path the stale owner cannot finalise. In the tested entry path the stale owner cannot publish. Neither tested path submitted another broker write.
