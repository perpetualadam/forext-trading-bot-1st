# Order status and position safety

The application keeps three separate records:

- An `exec_orders` row, including a PENDING reservation.
- An in-memory `LocalOrder`.
- A `Position` created by `open_position` at bot_loop.py 1808 after a broker fill path.

`exec_orders.status` is text. It has no check constraint and no unique open-row-per-symbol constraint. FILLED on an order row is not a position row. CLOSED is not an order status in this path.

Because a filled order and an open position are different records, order status cannot prove the position is closed. `order_status_proves_exposure_closed` returns false for FILLED and for every other value.

A full fill releases the reservation hold. That release means the client id is no longer an in-flight reservation. It is not permission to treat exposure as closed. While a position object exists, `_evaluate_impl` returns at lines 754–755 before reservation. That position check was not modified.

The missing case is a fill that never creates a position record, or a position record that is lost while the broker position remains. Closing that case needs position-state handling beyond this reservation repair. No migration was added. The symbol is not permanently blocked after a historical fill, because that would hide the missing position state rather than repair it.

Operational effect: a second reservation is blocked while PENDING, PARTIAL, or UNRESOLVED remains. After an authoritative full fill, the reservation layer can accept a later id. The loop still stops first if it still holds a position object. This does not authorise trading.
