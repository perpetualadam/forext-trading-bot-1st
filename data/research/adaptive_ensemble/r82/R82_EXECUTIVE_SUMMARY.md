# R.82 executive summary

Classification: `R82_JOURNAL_AND_PARTIAL_EXPOSURE_VERIFIED_OFFLINE`

Production trading remains NO-GO. R.83 was not started.

The R.81 baseline matched. Git HEAD remains `d080d897945bc44fa37c02caab504ed707146bec` on `main`. `forex_bot/oanda_exec.py` was not edited. The only operational change is in the working-tree close classifier: a negative `tradesClosed` unit string is rejected instead of being counted as a positive quantity.

Executed on disposable schema-5 journals, with the isolation harness imported first:

- An entry or close whose recovery authority cannot be read at the post-rate-limit check does not call OrderCreate or PositionClose.
- Deleting the authority row, closing the SQLite connection, or replacing a closed journal with a malformed file all fail closed. A second connection's `BEGIN EXCLUSIVE` did not make the open WAL unreadable, and that still-readable journal was not treated as a failed check.
- The final authority check and `api.request` are still separate. A successor startup during the request lets that one request continue. The consumed permit blocks a second submission. No extra local check was added.
- A close-confirmation commit fault leaves the journal short of `CLOSE_FULLY_CONFIRMED`. Position removal checks the journal and does not drop the position. No second PositionClose is sent.
- A 400-unit partial close records confirmed 400 and remaining 600 on the close row. In-memory `position.units` stays 1000, the original size. A repeat close sends nothing. Fresh-process startup with conflicting, remaining, empty, or incomplete snapshots does not make the position manageable, and one real cycle sends no close.
- Profit-protection source is unchanged. The ratchet on the partial-close position did not move backward.

Windows CPython 3.13.5: R.82 19 passed in 12.987s. Linux CPython 3.12.3 with `TMPDIR=/tmp`: R.82 19 passed in 18.212s. R.81, R.80, R.79, and R.78 passed on both. Older suites keep their previous failure counts.

Broker-enforced idempotency, power-loss durability, real network execution, PostgreSQL, data-only mode, and a clean reinstall remain unverified.
