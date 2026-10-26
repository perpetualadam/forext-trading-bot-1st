# R.8 order lifecycle map

Evidence label: SOURCE-REVIEWED. The trading loop was not started.

| Step | File | Function | Lines | Input | Output | Database effect | Memory effect | Failure behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A01 Signal accepted | forex_bot/bot_loop.py | `_evaluate_impl` | 1240–1282 | AI vote | continue only when `allow` is true | none | none | `allow` false returns before direction and sizing |
| A02 Live-order authorisation | forex_bot/bot_loop.py | `_evaluate_impl` via `pre_trade_entry_blocked_reason` | 1101–1110 | safety state | return before strategy | none | none | live auth block returns |
| A03 Strategy activation | forex_bot/bot_loop.py | `continue_entry_after_strategy_gate` | 1169–1212, definition 203–232 | strategy name and active flag | continue or return | none | none | inactive or unknown returns before sizing |
| A04 Direction | forex_bot/bot_loop.py | `direction_action_gate` | 1284–1292, definition 167–180 | AI direction | BUY or SELL | none | none | invalid direction returns before sizing |
| A05 Position sizing | forex_bot/bot_loop.py | `_evaluate_impl` | 1363–1367 | price, stop, balance | unit count | none | none | reached only after A02–A04 |
| A06 Existing order-state check | forex_bot/bot_loop.py | `broker_entry_block_reason` | 1554–1558, definition 235–240 | process book and recovery rows | block reason or None | read when persistence is on | none | unreadable recovery blocks |
| A07 Client order ID | forex_bot/orders.py | `generate_client_order_id` | called at bot_loop.py 1559 | none | new id | none | none | not called when A06 blocks |
| A08 Database reservation | forex_bot/orders.py and forex_bot/database.py | `try_begin_order_submission`, `insert_exec_order_pending_if_absent` | orders.py 94–143; database.py 762–840 | client id, symbol | True or False | PENDING insert when persistence is on | blocking map and local PENDING order | active status or fault returns False |
| A09 Reservation commit | forex_bot/database.py | `insert_exec_order_pending_if_absent` | 824–830 | open transaction | True only after commit and rowcount | one commit | blocking map set after commit | exception fail-closes and returns False |
| A10 Broker dispatch boundary | forex_bot/bot_loop.py | `_evaluate_impl` | 1638–1648 | reserved id | call site only | none in this stage | none | not executed in R.8 |
| A11 Broker acknowledgement | forex_bot/bot_loop.py | `_evaluate_impl` | 1697–1704 | returned fill | audit fields | none here | none | not executed |
| A12 Partial fill | forex_bot/bot_loop.py and forex_bot/orders.py | `_evaluate_impl`, `finalize_order_fill` | bot_loop.py 1710–1731; orders.py 146–175 | filled units below request | PARTIAL | status update when persistence is on | order status PARTIAL; reservation hold kept | not executed |
| A13 Complete fill | same | same | same, then `open_position` at 1808–1814 | full units | FILLED then a position object | status update | reservation hold released; position stored separately | fill does not prove the position is flat |
| A14 Broker rejection | forex_bot/bot_loop.py | `_evaluate_impl` | 1659–1668 | `OrderCreateRejected` | return | cancel update | hold released for that symbol | not executed |
| A15 Broker cancellation | forex_bot/bot_loop.py | `_evaluate_impl` | 1649–1658 | `OrderCreateCancelled` | return | cancel update | hold released for that symbol | not executed |
| A16 Broker timeout | forex_bot/bot_loop.py | `_evaluate_impl` | 1669–1696 | outcome or generic exception | UNRESOLVED | unresolved update when persistence is on | unresolved and blocking maps | not executed |
| A17 Connection loss | same as A16 | `remember_ambiguous_outcome` | database.py 684–695 | symbol and client id | block | unresolved update attempted | fail-closed if the durable write fails | not executed against a broker |
| A18 Ambiguous broker result | same as A16 | same | same | any non-terminal outcome | UNRESOLVED | same | same | no replacement id |
| A19 Ambiguous database commit | forex_bot/database.py | `insert_exec_order_pending_if_absent` | 831–839 | exception around the reservation | False | rollback attempted | symbol blocked and process fail-closed | no second client id is created |
| A20 Restart recovery | forex_bot/orders.py | `ingest_recovery_snapshot` | 207–268 | synthetic rows | loaded count or exception | no connection in these tests | PENDING, PARTIAL, and UNRESOLVED become holds | unreadable or unknown status fail-closes |
| A21 Reconciliation | forex_bot/database.py | `book_on_reconciliation` | 564–585 | synthetic result | book | none | confirmed absent or fill clears the reservation hold | unavailable stays blocked; no broker call |
| A22 Terminal transition | forex_bot/orders.py | `mark_order_failed_or_cancelled`, `finalize_order_fill` | 178–197 and 146–175 | current order | CANCELLED or FILLED | matching update when persistence is on | UNRESOLVED is not cancelled | generic cancel cannot erase UNRESOLVED |
| A23 New reservation eligibility | forex_bot/database.py | `reservation_status_block_reason`, `new_intent_block_reason` | 500–513 and 587–616 | status and book | block reason or None | used by the insert check | process blocking map | unknown status fails closed |

The position gate is earlier than reservation: `get_position` at bot_loop.py 724–737 and `POSITION_ALREADY_OPEN` at 754–755. An open position returns before sizing and before `try_begin_order_submission`.
