# R.68 remaining risks

R.68 enforces the observation-only boundary for a reconciliation discovery. The items below are unresolved.

| Id | Status |
| --- | --- |
| R66-03 | Unresolved. `broker_sl_tp_hit` still returns false. Stop-hit handling was not changed. |
| R66-05 | Unresolved. A local fallback price is still not broker protection. The import path can still copy a fallback price onto the observation record. Parsing was not changed. |
| R66-10 | Unresolved. A permitted live close can still drop a local row when the close result has no unit count. |
| R66-11 | Unresolved. An ambiguous close of a permitted live row can still be retried. There is still no close idempotency key. |
| R66-16 | The import no longer places a discovery into the managed dict. The broader shared-RAM concurrency between reconciliation and the trading loop is unresolved. The concurrent case is `NOT_VERIFIED`. |
| R66-01 | Preserved. Production new entries remain blocked. This is a standing control, not a defect to reopen. |
| R66-02, R66-06, R66-07, R66-08, R66-09, R66-12, R66-13, R66-14, R66-15, R66-17, R66-18, R66-19 | Unresolved or informational, and outside this change. |

C2, C3, and C4 are written amendments. The close state machine, the unique index, and the protection parser are not implemented.

`account_disappeared_broker_position` can still pop a permitted live row, including when the exit evidence is incomplete. That is the pre-existing R66-10 / R66-11 behaviour for bot-created rows.

Production trading remains NO-GO.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

`POSTGRESQL_INTEGRATION_NOT_TESTED`
