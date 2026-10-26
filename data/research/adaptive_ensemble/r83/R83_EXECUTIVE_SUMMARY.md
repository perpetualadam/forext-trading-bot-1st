# R.83 executive summary

Classification: `R83_POST_COMMIT_AND_SQLITE_AUTHORITY_VERIFIED_OFFLINE`

Production trading remains NO-GO. R.84 was not started.

The R.82 baseline matched. Two narrow working-tree corrections were made:

- `mark_entry` returns without writing when the entry is already `ENTRY_FINALISED`, so a publication exception cannot relabel a committed entry as ambiguous.
- `close_confirmed_live_position` returns without removing memory or finalising the journal when this process has a fencing epoch and that epoch is no longer current.

Executed with disposable journals and synthetic brokers:

- One OrderCreate can commit `ENTRY_FINALISED` and then fail before `positions` assignment. The client id stays consumed. A killed process is reconstructed by a fresh `execute_startup_sequence` as one manageable position. A second reservation of that client is refused.
- One PositionClose can commit `CLOSE_FULLY_CONFIRMED` with confirmed 1000 and remaining 0. An exception before removal, or a process kill before removal, leaves that confirmation in place. A successor sends no second close. A conflicting open snapshot stays unmanageable. A stale owner does not finalise the close.
- A 400-unit partial confirmation survives a process kill: confirmed 400, remaining 600, durable units 1000, ratchet 40, and the successor is not manageable.
- `SQLITE_BUSY` was raised by the SQLite driver on a disposable DELETE-mode authority SELECT. The production WAL journal did not raise it. `SQLITE_LOCKED_SHAREDCACHE` was raised on `BEGIN IMMEDIATE` in a shared-cache fixture, which is not the production configuration and is not the authority SELECT. Injected lock errors, a closed connection, a missing authority row, and a stale epoch all produced zero OrderCreate and PositionClose calls.
- The R.82 negative `tradesClosed` rejection is still present. Positive 400, 999, and 1000 handling is unchanged. Official OANDA examples use a signed `tradesClosed` unit and a `tradeReduced` object. That conflict is recorded and the correction was not reversed.

R.82 through R.78 remain green on Windows and Linux. Older failure counts match the R.82 baseline.
