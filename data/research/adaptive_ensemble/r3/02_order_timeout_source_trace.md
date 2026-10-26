# Uncertain-order source trace

The trading loop was not entered. These steps are the source order, then the functions that were called with fakes.

1. `generate_client_order_id` in `forex_bot/orders.py` lines 44-45 creates a new id on every call.
2. `try_begin_order_submission` lines 93-132 reserves that id in memory. The same id returns false. A different id is a new reservation.
3. A broker send would be `execute_oanda_market_open`. It was not called.
4. A fill body is classified FILLED by `classify_order_create_response` (`oanda_exec.py` 210-238).
5. A reject body is REJECTED (lines 250-261).
6. A cancel body is CANCELLED (lines 239-249).
7. `TimeoutError` and `ConnectionResetError` are AMBIGUOUS_TRANSPORT_OUTCOME (`classify_order_create_transport_error`, lines 289-316). The broker result stays unknown.
8. `OrderCreateAmbiguous` is a subclass of `OrderCreateOutcomeError` (lines 46-63).
9. `bot_loop.py` lines 1527-1532 catch `OrderCreateOutcomeError` and call `mark_order_failed_or_cancelled`. That except block was not entered.
10. `mark_order_failed_or_cancelled` (`orders.py` 164-170) marks the id CANCELLED. It does not ask the broker what happened. With persistence off, it does not touch a database.
11. The same id stays in memory, so it cannot be reserved again in this process.
12. The next call to `generate_client_order_id` is a different id. `try_begin_order_submission` accepts it.
13. Nothing on this path reconciles the unknown first order before that new id.
14. Restart recovery in `database.py` lines 582-594 reloads only PENDING and PARTIAL. A CANCELLED row would not come back. That query was not executed, because it opens a database connection.
15. Live-order permission and inactive strategies sit in front of this path. They were not turned on. They do not repair the timeout handling.
