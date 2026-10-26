# Restart and recovery

Synthetic snapshots, not application startup:

| Case | Result |
| --- | --- |
| F01 FILLED plus a position object | Position is kept and entry stays blocked |
| F02 FILLED without a position | Snapshot blocks a new id |
| F03 Corrupt marker | Fail-closed |
| F04 Stale snapshot | Fail-closed |
| F05 PARTIAL | Blocks |
| F06 UNRESOLVED | Blocks |
| F07 PENDING | Blocks |
| F08 Position without an order | Open position refuses reservation |
| F09 Order without a position | FILLED snapshot blocks |
| F10–F12 Unreadable or unavailable recovery | Fail-closed, not an empty book |
| F13 Unexpected status or marker | Fail-closed |
| F14 Conflicting fill | Position is not replaced |
| F15 Flat token alone | Releases only that symbol's hold |
| F16 Flat token plus unresolved | Does not release |
| F17 Fill before position persistence | Hold is set before `open_position` |
| F18 Close before durable closure | In-memory pop does not clear the hold, and the token does not delete a durable marker |
| F19 Reconciliation unavailable | Hold remains. No broker call |
| F20 Repeated ingest | Second load adds no duplicate order and the hold remains |

Startup in `app.py` calls `load_open_orders_from_db_into_memory` and then `run_reconciliation_once`. The load query now also selects `exposure_safety = UNCONFIRMED`. Neither call was executed. Broker reconciliation remains NOT_EVALUATED. Position objects are not loaded from a position table because that table does not exist.
