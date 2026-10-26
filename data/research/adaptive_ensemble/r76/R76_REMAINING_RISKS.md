# R.76 remaining risks

Production remains `NO-GO`.

Retained labels:

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` — the client extension and the SQLite unique index are local. OANDA was not asked to reject a duplicate order.
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` — tests commit and reopen the file. They do not cut power or prove a torn page.
- `LINUX_INTEGRATION_NOT_VERIFIED` — WSL cannot import `oandapyV20`. The journal file tests passed there. The OrderCreate path did not.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`
- `POSTGRESQL_INTEGRATION_NOT_TESTED`
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`

R.66 items still open:

- R66-03: `broker_sl_tp_hit` remains false in `forex_bot/live_manage.py`.
- R66-07: sizing currency was not changed.
- R66-10 and R66-11: duplicate close suppression is journal-side on the guarded path. It is not broker-enforced.
- R66-16 remains outside this stage.

Recovery limits:

- `run_bot` calls recovery, but this stage did not execute `run_bot`.
- A crash that leaves `RECOVERY_IN_PROGRESS` blocks later management until that row is no longer in progress. There is no automatic takeover.
- `COMPLETED_WITH_QUARANTINE` permits management of published rows. Quarantined rows stay out of `positions`. An operator still has to resolve them. The bot does not close them.
- Memory publication and the SQLite commit are not one transaction.
- `profit_protection_last_logged_mfe` is not durable. A ratchet that was not successfully persisted is not rebuilt from price.
- `load_startup_broker_view` can restore one trade id from OpenPositions. It cannot assign units when an instrument has several trade ids. Those rows stay quarantined.
- A finalised client id can be reserved again because the unique index ignores `ENTRY_FINALISED`. Unresolved outcomes cannot. A new entry is expected to use a new client id. Reusing a finalised id is not broker idempotency.

The historical R.68, R.69, R.70, R.72, and R.73 suites still contain the failures listed in the regression report. One R.69 test newly fails because live management now waits for recovery.
