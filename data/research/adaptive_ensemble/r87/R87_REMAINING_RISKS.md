# R.87 Remaining Risks

The R.86 risks remain, including snapshot completeness, transaction chronology, cache reuse after a close, quarantine release, broker-side stops, sizing currency, journal-side duplicate-close suppression, the Windows boot identifier, and R66-16.

Also retained:

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`
- `REAL_NETWORK_EXECUTION_NOT_TESTED`
- `POSTGRESQL_INTEGRATION_NOT_TESTED`
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`
- `CLEAN_REINSTALL_VERIFIED = NOT_VERIFIED`
- `FINAL_CHECK_TO_REQUEST_RACE_REPRODUCED`
- `SQLITE_BUSY_AUTHORITY_READ_NOT_REPRODUCED`
- `SQLITE_LOCKED_AUTHORITY_READ_NOT_REPRODUCED`
- `OANDA_TRADE_REDUCE_SIGN_CONTRACT_PARTIALLY_VERIFIED`

The additional stop is the `bot_loop.py` hash mismatch. R.87 did not decide whether that wrapper is safe.
