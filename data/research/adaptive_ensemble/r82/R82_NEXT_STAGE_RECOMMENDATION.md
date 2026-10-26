# R.82 next-stage recommendation

R.83 was not started.

The next offline stage, if one is authorised, should stay outside strategy, sizing, and stop calculations. Useful unfinished items are:

1. A fault after a successful entry or close commit and before memory publication, to close matrix rows 16 and 17.
2. A disposable-journal way to raise `SQLITE_BUSY` or `SQLITE_LOCKED` on the authority read without pretending that an open WAL connection has gone blind.
3. Broker-documented idempotency. That cannot be closed with a synthetic recorder.

No compare-and-submit protocol, schema change, permit release, or broker stop adapter is recommended from this stage.

Production trading remains NO-GO until a later stage is explicitly authorised and the unresolved flags above are addressed with evidence that this stage does not have.
