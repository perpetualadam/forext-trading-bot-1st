# R.82 remaining risks

These flags stay open. Offline synthetic tests do not clear them.

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`
- `REAL_NETWORK_EXECUTION_NOT_TESTED`
- `POSTGRESQL_INTEGRATION_NOT_TESTED`
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`
- `CLEAN_REINSTALL_VERIFIED = NOT_VERIFIED`

Additional R.82 limits:

- `FINAL_CHECK_TO_REQUEST_RACE_REPRODUCED`. One request can still enter after the last local check. The consumed permit blocks the next automatic submission. Broker idempotency is not verified, so an uncertain in-flight request is not proven unique at OANDA.
- `SQLITE_BUSY` and `SQLITE_LOCKED` were not produced. An exclusive lock on a second connection left the WAL readable.
- A fault after a successful durable commit and before memory publication was not injected. Removal already checks the journal before deleting a position.
- `position.units` remains the original size after a partial close. The journal holds the remainder. Restart quarantines the row. In-process code that read `pos.units` directly would still see 1000 until the process ends.
- On a closed connection, the close failure path raises `ProgrammingError` from `_persist` instead of returning an operation. The request is not sent. The durable row is inspected only after reopen.
- R.66 remains open: `broker_sl_tp_hit` is still not a live broker stop (`live_manage.py`); sizing currency is unresolved; duplicate-close suppression is journal-side, not broker-enforced.

Production trading remains NO-GO.
