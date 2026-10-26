# R.74 Remaining Risks

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`. A committed intent means the next process must not send another close. It does not prove OANDA will reject a duplicate if one were sent. Client extensions were not added.
- `RESTART_DURABLE_RECOVERY_NOT_FULLY_VERIFIED` for a crash inside the SQLite `COMMIT` fsync. Recovery after a commit that had already returned was tested with subprocess exit.
- The position book is process memory. Restart does not restore a local row. The journal can stop a new close of a trade id that still has an unresolved or fully confirmed row. It cannot rebuild the local position.
- `acknowledge_empty` does not query the broker. Using it while a broker position already exists would authorise a later reserve of that trade. The bot does not call bootstrap.
- SQLite here is local-file locking. It was not tested as a cross-machine lock and was not tested with the journal file stored in a syncing OneDrive directory.
- `LINUX_INTEGRATION_NOT_VERIFIED` for the operational close path because WSL has no `oandapyV20`. The journal suite passed on WSL.
- `POSTGRESQL_INTEGRATION_NOT_TESTED`.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`.
- R66-03: `broker_sl_tp_hit` still returns false.
- R66-07: sizing currency assumptions were not changed.
- R66-10 and R66-11: the guarded live path now has a durable reservation and blocks an ambiguous resubmit. That is not broker-enforced exactly-once, and it does not cover a caller that bypasses the guard.
- R66-16 was outside this stage.
- Historical R.68, R.69, R.70, R.72, and R.73 suites are not green. Classifications are in `R74_REGRESSION_CLASSIFICATION.md`.

Production remains `NO-GO`.
