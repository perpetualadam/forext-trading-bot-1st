# R.83 remaining risks

These flags stay open:

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`
- `REAL_NETWORK_EXECUTION_NOT_TESTED`
- `POSTGRESQL_INTEGRATION_NOT_TESTED`
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`
- `CLEAN_REINSTALL_VERIFIED = NOT_VERIFIED`
- `FINAL_CHECK_TO_REQUEST_RACE_REPRODUCED`
- `SQLITE_BUSY_AUTHORITY_READ_NOT_REPRODUCED` for the production WAL authority SELECT
- `SQLITE_LOCKED` was not raised by the production authority SELECT

R.66 findings that remain:

- `broker_sl_tp_hit` is not a verified broker-side stop.
- Position-sizing currency is unresolved.
- Duplicate-close suppression is journal-side. The synthetic tests do not prove the broker rejects a second PositionClose.
- R66-16 is outside this stage.

Additional limits from this stage:

- Official OANDA full-close examples put a negative number in `tradesClosed[].units`. The current parser rejects that. Official partial-close examples use `tradeReduced`, which this parser does not read. The correction was not reversed.
- A DELETE-mode `SQLITE_BUSY` does not describe the WAL production path.
- Shared-cache `SQLITE_LOCKED_SHAREDCACHE` does not describe the production configuration.
- Injected `OperationalError` values are not driver lock errors.
- There is still a source window after `recovery_fence_allows_publication` returns true and before the book assignment. That window is in the stale process's memory. The executed tests show it does not send a second OrderCreate.
- A kill after memory publication has already completed, and a kill after memory removal has already completed, were not separate barriers. The durable rows in those states are the ones startup already reconstructs.
- `test_14` updates the epoch with SQL. The publication and removal fencing tests use a real successor startup.
- Decimal closed units such as `400.5` remain a partial confirmation under the existing parser.
- Production trading remains NO-GO.
