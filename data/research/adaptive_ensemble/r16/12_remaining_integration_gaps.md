# Remaining integration gaps

- Production account provenance and freshness are NOT_EVALUATED. The 300-second check applies only when a test supplies a timestamp. It is not a broker freshness proof.
- `verified=True` does not authenticate a production snapshot. A production entry remains fail-closed.
- Account identity is checked only when the caller supplies `expected_account_id`. The production contract does not currently require an identity.
- The unreachable legacy tail still calls `current_equity()` and `last_account_summary()`. It cannot dispatch.
- Performance logging, the daily report, and `run_bot` portfolio reporting still call `current_equity()`. They are not entry permission. `run_bot` was not executed.
- The gross notional cap and the unit cap stay off at their production defaults. Daily-loss and drawdown latches stay behind a disabled flag and are not on this entry path.
- Margin is not modeled.
- Authoritative broker-flat release, PostgreSQL, OANDA, the production loop, and profitability are NOT_EVALUATED.
