# R.76 entry and close interaction

The entry permit and the close permit are separate classes.

- `EntrySubmissionPermit` is consumed by `claim_entry_permit` inside `_submit_order_create`.
- `CloseSubmissionPermit` is still required by `_submit_position_close_body` (`forex_bot/oanda_exec.py` line 401).
- `execute_oanda_market_close` and `_place_market_order_sync` raise `TypeError` without the close permit (test 61).
- `trading.execute_trade` raises `RuntimeError` for a live close before HTTP (test 62). The call list stays empty.

An unresolved entry does not publish a position, so it cannot reach the live close path as a managed row. A durable row with an ambiguous entry is quarantined (test 45) and is not managed.

Test 46 submits one synthetic `PositionClose`, raises `TimeoutError`, and records an unresolved close. The second `run_guarded_live_close` does not append another `PositionClose`.

`apply_transaction_body` still returns `CLOSE_FULLY_CONFIRMED` only for a matching full fill (test 64) and `CLOSE_PARTIALLY_CONFIRMED` for a smaller fill (test 65). A partial close is not treated as an entry.

`live_local_delete_permitted` remains false (test 63). Recovery sets `delete_permitted` false and `close_submission_count` 0.

A confirmed close is still bound to the position instance and trade id in the close journal. Entry finalisation does not delete a different instance. `publish_recovered` refuses to replace a different local instance.

There is no skip flag on either guard.
