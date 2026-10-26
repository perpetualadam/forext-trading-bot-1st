# Fill-to-position lifecycle

Evidence: SOURCE-REVIEWED. The trading loop, application startup, PostgreSQL, and the broker were not executed.

| Step | Where | Lines | What happens | Failure |
| --- | --- | --- | --- | --- |
| A01 Intent | `bot_loop._evaluate_impl` | strategy gate near 1169, direction near 1284 | Continues only after those gates | Inactive strategy or invalid direction returns before sizing |
| A02 Reservation | `orders.try_begin_order_submission` | orders.py 94–143 | Memory, position, and database checks | False does not register an order |
| A03 Client id | `generate_client_order_id` | called at bot_loop.py 1559 after the broker block | New id only if the broker block is clear | Not called when the block returns |
| A04 Broker boundary | `bot_loop._evaluate_impl` | `execute_oanda_market_open` after reservation | Call site only | Not executed in R.9 |
| A05 Ack | same function | audit block after the await | Would record an acknowledgement | Not executed |
| A06 Full fill | `orders.finalize_order_fill` | orders.py finalize | Status FILLED and metadata `exposure_safety=UNCONFIRMED` | A failed durable write fail-closes when persistence is on |
| A07 Partial | same | same, status PARTIAL | Hold kept | Unknown remainder stays blocked |
| A08 Position object | `bot_loop._evaluate_impl` | 1828 | `open_position` after the fill | Exception returns and keeps the hold |
| A09 Memory | `positions.open_position` | positions.py 46–60 | One slot per symbol | Not a durable store. File not edited |
| A10 Persistence | none for the position object | `trades` is closed-trade history | No open-position table | Schema change was not added |
| A11 Restart load | `orders.load_open_orders_from_db_into_memory` | orders.py load; app.py 371 calls it | SQL includes UNCONFIRMED | Query was not executed |
| A12 Reconciliation entry | `app.py` lifespan | 380 `run_reconciliation_once` | Broker entry point exists | Not called |
| A13 Close request | `bot_loop._evaluate_impl` | about 1021–1038 `execute_trade` | Close is attempted only when a position object exists | Exception does not pop the position |
| A14 Close confirmed | not a broker proof | `confirm_exposure_flat` | Explicit token only | Token is not broker evidence |
| A15 Memory removal | `positions.close_position` | bot_loop.py 1050 on the success path | Pops the object | Does not clear the exposure hold |
| A16 Durable close mark | not implemented | no position table | In-memory token does not delete a durable UNCONFIRMED marker | Restart that can read the row blocks again |
| A17 Eligibility | `exposure_entry_block_reason` | bot_loop.py 1087 | Blocks before strategy and sizing on the next pass | Missing object is not eligibility |
| A18 Fill before position | `finalize_order_fill` then `open_position` | hold is set before the position call | Position failure returns | Entry stays blocked |
| A19 Position before durable marker | same update writes status and marker together in source | database.py fill update | Engine commit was not run | Ambiguous commit stays fail-closed in source |
| A20 Recovery failure | `ingest_recovery_snapshot` | unreadable, stale, unknown | Fail-closed | Not an empty book |
| A21 Missing position | process map and FILLED snapshot | no position object | Still blocks | Absence is not flat |
| A22 Stale snapshot | `snapshot_stale` | ingest raises | Fail-closed | Not current broker truth |
| A23 Unknown exposure | unknown marker or status | ingest or `exposure_marker_block_reason` | Fail-closed | No invented broker state |
| A24 Mismatch | `record_synthetic_fill_position` | different units or side | Conflict, position not replaced | Hold remains |
| A25 Existing position check | `bot_loop._evaluate_impl` | 755 `POSITION_ALREADY_OPEN` | Returns before a new entry | Still present and not weakened |

Actual entry order on a later cycle, which differs from a diagram that puts exposure after direction:

1. Open position object at line 755.
2. Exposure or reservation hold at line 1087, before strategy, direction, and sizing.
3. Strategy gate.
4. Direction gate.
5. Sizing.
6. `broker_entry_block_reason`.
7. `try_begin_order_submission`, which also refuses an open position.
8. Broker dispatch call site.

`oanda_exec.py` was inspected and not modified. Its classifier already names filled, cancelled, rejected, malformed, and ambiguous transport outcomes.
