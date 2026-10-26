# R.84 remaining risks

These flags stay open:

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`
- `REAL_NETWORK_EXECUTION_NOT_TESTED`
- `POSTGRESQL_INTEGRATION_NOT_TESTED`
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`
- `CLEAN_REINSTALL_VERIFIED = NOT_VERIFIED`
- `FINAL_CHECK_TO_REQUEST_RACE_REPRODUCED`
- `SQLITE_BUSY_AUTHORITY_READ_NOT_REPRODUCED`
- `SQLITE_LOCKED_AUTHORITY_READ_NOT_REPRODUCED`

The R.83 window between a durable commit and memory publication or removal remains. A corrected parser does not close that window and does not create broker-side idempotency.

R.66 findings that remain:

- `broker_sl_tp_hit` is not a verified broker-side stop.
- Position-sizing currency is unresolved.
- Duplicate-close suppression remains journal-side.
- R66-16 remains outside this stage.

Contract limits:

- `TradeReduce.units` is described as a reduction count and is negative in the full-close example. This stage accepts both tested patterns and rejects a negative reduction beside a positive fill. It does not claim one universal OANDA sign rule.
- The official partial example does not say the original trade was short. The SELL classification uses this bot's existing fill-sign rule.
- Decimal closed units such as 400.5 remain a partial confirmation because the schema type is `DecimalNumber`.
- Signed values are returned by the classifier. They are not a new journal column.
- Production trading remains NO-GO.
