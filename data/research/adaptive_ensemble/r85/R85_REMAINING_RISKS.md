# R.85 Remaining Risks

Retained from prior stages:

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

R.66 items still open:

- `broker_sl_tp_hit` is not a verified broker-side stop.
- Position-sizing currency remains unresolved.
- Duplicate-close suppression remains journal-side.
- R66-16 remains outside this stage.

R.85 additions:

- Snapshot freshness is not represented. A `COMPLETE` label in the tests is synthetic.
- Pagination completion is not represented. `INCOMPLETE` is the only completeness refusal that was exercised as a distinct label.
- Journal remaining units are not current broker exposure. Recovery still compares snapshots with original units, so a 600-unit remainder is `units_mismatch` rather than a reconciled current quantity.
- The OS recovery lock ends when startup ends. A later cycle is fenced by the epoch, not by the lock.
- After the second entry fence returns true, the assignment is still a later statement. The tested pause was on the check. The later window is process-local and was not shown to write the journal or to send an order.
- In-memory portfolio sums do not include `quarantined_positions`, so a status figure can omit the open remainder.
- Quarantine release is unspecified in code. The contract in this stage is documentation only.
- `CLOSE_FINALISED` still means local removal was recorded. It does not mean a new broker transaction occurred.
- Process kill is not power-loss durability. The Windows boot id remains the constant `windows:boot-id-unavailable`.

None of these were cleared by the synthetic tests.
