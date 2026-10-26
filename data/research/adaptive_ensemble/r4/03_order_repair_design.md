# R.4 order-uncertainty repair design

Gate B result: PASS. The repair fits in `forex_bot/bot_loop.py` and `forex_bot/database.py`. `forex_bot/oanda_exec.py` already classifies timeouts and connection failures as `AMBIGUOUS_TRANSPORT_OUTCOME`, so it was not changed. `forex_bot/orders.py` was not changed.

## Defect

After a broker send, `OrderCreateAmbiguous` is a subclass of `OrderCreateOutcomeError`. The old handler called `mark_order_failed_or_cancelled`, which stores `CANCELLED`. Recovery reloads only `PENDING` and `PARTIAL`. A later new client order id was therefore accepted. Same-id protection did not cover that new id.

## Identity boundary

The boundary is the symbol plus the first client order id of an unresolved broker attempt. A second client order id for that symbol is refused while the first attempt is unresolved. Comparison of client order ids alone is not the gate.

## Rules

- Timeout, connection reset, a malformed body, and any other unknown outcome stay `UNRESOLVED`. They are not a rejection and not a confirmed cancellation.
- There is no automatic retry and no timer release.
- Confirmed fill, confirmed rejection, and confirmed cancellation are the only automatic terminal results. Those handlers still use the existing cancel/fill updates.
- A simulated reconciliation may release the intent only for `CONFIRMED_ABSENT`. `CONFIRMED_FILL` clears the unresolved mark and does not create a replacement id. Any other reconciliation result leaves the intent blocked.
- If durable recovery cannot be read, including when order persistence is off, a new broker entry is refused. An empty or missing local row is not treated as proof that the broker has no order.
- No strategy is enabled and live-order permission is not granted.
- No production migration was run. `exec_orders.status` is already text, so the new status value does not need a new column. That does not make this stage ready to deploy.

## Restart

`read_durable_recovery` returns unresolved rows, or marks the snapshot unreadable. `broker_entry_block_reason` runs before a new client order id is generated. `insert_exec_order_pending_if_absent` also refuses a reservation when the process map or a durable unresolved row exists. `orders.py` may still show an unknown status as `PENDING` in memory after reload. The database status remains `UNRESOLVED`, and the new-id gate reads that status.
