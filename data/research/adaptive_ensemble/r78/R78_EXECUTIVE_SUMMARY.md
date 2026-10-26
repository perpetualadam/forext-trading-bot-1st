# R.78 executive summary

Classification: `R78_VERIFICATION_PARTIALLY_VALIDATED`

Production trading remains `NO-GO`. This stage did not start R.79.

The R.77 baseline matched before any edit. HEAD stayed `d080d897945bc44fa37c02caab504ed707146bec` on `main`. No commit, reset, or stash was made.

What was implemented in operational source:

- Schema 5 adds a recovery fencing epoch, owner identity columns, and an append-only entry-investigation table. Version 4 journals do not open. `migrate_journal_4_to_5` is explicit and is not called by startup.
- An exclusive non-blocking OS lock is required before an abandoned recovery claim can be released. Caller-supplied inactive evidence cannot override a held lock.
- A fencing epoch is incremented when a recovery claim is taken and again when a repair releases it. A superseded process fails closed for publication and live management.
- Read-only entry investigation records a classification and does not resubmit, delete, or promote a trade.
- Entry classification now refuses a missing or conflicting client id, and refuses a trade id that equals the order id.

What was verified offline, on Windows and on WSL Ubuntu 24.04, with temporary SQLite and no broker:

- Forged inactive evidence is refused while another process holds the lock.
- A crashed owner can be released after the process exits and the lock is free.
- PID reuse with a different process-start token does not keep the old claim.
- The same process start is refused even when the lock is free.
- Two overlapping repairs produce one committed audit.
- A second startup is blocked while the lock is held.
- After a repair, management stays off until a fresh `execute_startup_sequence`.
- A stale epoch cannot publish or manage.
- Ambiguous entries are not retried.

What was not verified:

- `run_startup_and_one_iteration` on Linux. `forex_bot.bot_loop` does not import there because `numpy` is missing, and `oandapyV20` is also missing. No packages were installed.
- Broker-enforced idempotency. Official documentation does not guarantee it, and no OANDA endpoint was called.
- Power-loss durability.
- A real host reboot. Windows has no boot id in this design, so a Windows reboot is not detected.
- PostgreSQL.
- Data-only mode as a safe trading mode.

Retained limits:

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`
- `LINUX_INTEGRATION_NOT_VERIFIED` for the operational startup and management cycle
- `REAL_NETWORK_EXECUTION_NOT_TESTED`
- `POSTGRESQL_INTEGRATION_NOT_TESTED`
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`
