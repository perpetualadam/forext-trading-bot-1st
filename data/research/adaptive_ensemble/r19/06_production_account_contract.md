# Gate E — production account contract mapping

ACCOUNT CONTRACT MAPPED. SOURCE-REVIEWED. No account was fetched. Broker verification is NOT_EVALUATED.

| Field | Interface | Classification |
|---|---|---|
| Account id | `fetch_account_summary` parses `id` | SOURCE_INTERFACE_IDENTIFIED; REQUIRES_AUTHORITATIVE_BROKER_EVIDENCE |
| Environment | `official_env_label` stored on the snapshot | SOURCE_INTERFACE_IDENTIFIED; not called |
| GBP spread-betting compatibility | no check in the summary parser | MISSING |
| Currency | snapshot `currency` | SOURCE_INTERFACE_IDENTIFIED; not used by the shared path |
| NAV | snapshot `NAV`, also `set_broker_account` | SOURCE_INTERFACE_IDENTIFIED; cache is LOCAL_FALLBACK_ONLY |
| Balance | snapshot `balance` | SOURCE_INTERFACE_IDENTIFIED; shared path uses harness balance only |
| Available margin | snapshot `marginAvailable` | SOURCE_INTERFACE_IDENTIFIED; unused by entry |
| Margin used | not parsed | MISSING |
| Margin closeout | not parsed | MISSING |
| Open positions | local `positions` | LOCAL_FALLBACK_ONLY |
| Pending orders | local order book and reservation map | LOCAL_FALLBACK_ONLY |
| Realised daily P&L | `account_risk.observe` JSON when the flag is on | LOCAL_FALLBACK_ONLY |
| Unrealised P&L | `IterationDependencies.unrealised` | MISSING as broker evidence |
| Drawdown baseline | local risk file `max_dd_pct` | LOCAL_FALLBACK_ONLY |
| Snapshot timestamp | shared path `account_as_of`; missing means `account_freshness_not_evaluated` | NOT_EVALUATED for production |
| Acquisition timestamp | summary has no `fetched_at` | MISSING |
| Broker provenance | summary host and environment fields exist | REQUIRES_AUTHORITATIVE_BROKER_EVIDENCE |
| Cache | `_account_summary` / `last_account_summary` / `current_equity` broker NAV | LOCAL_FALLBACK_ONLY; not entry permission |
| Errors | summary returns None; shared path blocks `account_timeout` and `account_error` | SOURCE_INTERFACE_IDENTIFIED; live broker NOT_EVALUATED |
| Restart recovery | `select_rows_for_recovery` | local SQL only; PostgreSQL NOT_EVALUATED |

The shared path does not call `fetch_account_summary`. A caller `verified=True` does not authorise entry.
