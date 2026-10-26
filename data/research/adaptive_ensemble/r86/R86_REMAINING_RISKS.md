# R.86 Remaining Risks

Retained:

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

Also retained:

- Broker snapshot freshness is unverified. The position fetch has no watermark and no observation clock of its own.
- Broker snapshot completeness is unverified. OpenPositions has no pagination evidence.
- The existing startup label `COMPLETE_EMPTY` can still be produced by the unchanged interpreter. The new report does not treat it as verified, and startup recovery was not changed.
- `known_broker_net` can reuse a cached snapshot after a close.
- Quarantine release is not implemented.
- Existing portfolio, Telegram, and app status figures omit quarantined units.
- Broker-side stop protection is unverified.
- Position-sizing currency is unresolved.
- Duplicate-close suppression is journal-side.
- Windows boot identifier is unavailable.
- R66-16 is outside this stage.

A read-only exposure report is not evidence that trading is safe to enable.
