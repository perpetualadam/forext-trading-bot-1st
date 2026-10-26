# Recovery failure reproduction

Recorded before the repair, with `psycopg2.connect` replaced by a raise and `get_connection` replaced by an inert fake. No PostgreSQL server was started.

| Path | Result before repair |
|---|---|
| `load_open_orders_from_db_into_memory` when `get_connection` returns `None` | Fail-closed. `evaluate` returned `recovery_unreadable`, no reservation, no broker call. |
| `read_durable_recovery` when `get_connection` returns `None` | Returned `[], False` and left `_process_fail_closed` false. `evaluate` continued past exposure and stopped later at `ai_vote_unavailable`. |
| `fetch_exec_orders_open_for_recovery` when the query raises, and the caller does not use `load_open_orders_from_db_into_memory` | Raised `OrderRecoveryUnreadable` without setting the failure flag. `evaluate` continued past exposure. |
| `read_durable_recovery` when the query raises | Returned `[], False` without the failure flag. `evaluate` continued past exposure. |
| Successful query with no rows | Returned `[], True`. Exposure reason stayed empty. This was already distinct from failure. |
| `ingest_recovery_snapshot([], False)` | Already fail-closed, and `evaluate` returned `recovery_unreadable`. |

The defect is that a failed read was represented as an empty result plus a boolean the shared `evaluate` path never consults. `exposure_entry_block_reason` then treated the book as clear.
