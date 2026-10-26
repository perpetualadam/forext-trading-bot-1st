# R.24 separate-process recovery

Process A exited before Process B was started. Recovery used `initialise_application` in offline mode. The recovery functions were `get_connection`, `load_open_orders_from_db_into_memory`, and `load_reconcile_state_from_db`. That path reads PostgreSQL. It does not call OANDA. `trading_ready` and `trading_loop_started` stayed false. `production_eligible` stayed false. The inert broker dispatch count on every Process B evaluate was 0, and `reservation_attempted` was false.

| State | Symbol | Process A PID | Process B PID | Recovered source | Evaluate block | Flat call cleared it |
| --- | --- | --- | --- | --- | --- | --- |
| FILLED | `EUR_USD` | 6080 | 7992 | `db_recovery` | `exposure_unconfirmed` | false |
| UNRESOLVED | `GBP_USD` | 15828 | 6836 | `db_recovery` | `exposure_unconfirmed` | false |
| PENDING | `AUD_USD` | 19180 | 3156 | `db_recovery` | `active_reservation` | false |
| PARTIAL | `USD_CAD` | 18404 | 19768 | `db_recovery` | `exposure_unconfirmed` | false |

FILLED was created by the shared `evaluate` path. Process A made one inert broker dispatch and then exited. Process B recovered client id `cid-31fae62234614f0b8380a39c6116fd75` and made no second dispatch. A repeated evaluate stayed blocked.

PENDING, PARTIAL, and UNRESOLVED were written with `try_begin_order_submission`, `finalize_order_fill`, and `update_exec_order_row`. Process B loaded those rows from PostgreSQL and did not dispatch.

All eight process IDs are distinct.
