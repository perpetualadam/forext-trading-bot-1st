# R.8 integration

Preserved and rerun: PENDING, PARTIAL, and UNRESOLVED still block a second client id. Unknown status fail-closes. A reservation fault and an ambiguous-commit flag still refuse another id. The same client id does not create a second order. Invalid direction and an inactive strategy still stop before sizing. Live authorisation stays blocked.

`insert_exec_order_pending_if_absent` now also refuses a symbol in the exposure map, and its select includes an unconfirmed marker as well as non-terminal statuses. The check and insert remain in one source transaction. That transaction was not executed.

A memory result does not override a database fault: the fault sets the fail-closed flag and later reservations return false. A database-shaped flat marker does not override an unresolved order. Cancel releases a reservation hold and does not clear exposure.

`tests/test_r8_reservation_safety.py` now expects the post-R.9 `bot_loop.py` hash, and it accepts a barrier error containing `NETWORK_BLOCKED` or `DNS_BLOCKED`. The socket must still raise. The assertion was updated because R.9 was approved to edit `bot_loop.py` and the combined runner uses the R.9 barrier label.

The loop was not started. No strategy was activated.
