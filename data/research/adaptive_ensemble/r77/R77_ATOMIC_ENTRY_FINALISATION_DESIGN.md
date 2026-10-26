# R.77 atomic entry finalisation

`persist_bot_position` (`forex_bot/position_recovery.py` lines 184–203) opens its own `BEGIN IMMEDIATE` / `COMMIT`. `mark_entry` does the same. Calling both cannot be one transaction. R.77 extracts `_write_managed_position` (lines 52–181). It validates ownership, exactly one local trade id, and generation order, then inserts or updates. It does not begin, commit, or roll back. The caller owns the transaction.

`commit_verified_entry` (`forex_bot/entry_journal.py` lines 357–447) does all of the following inside one `BEGIN IMMEDIATE`:

- Loads the entry row and compares account binding, client id, instrument, direction, units, position instance, generation, and owner token.
- Refuses a missing stop or take profit.
- If the row is already `ENTRY_FINALISED`, returns without writing when the stored trade, instance, and generation match. A mismatch raises `finalised_without_matching_position` and does not invent a row.
- Otherwise requires `ENTRY_SUBMITTING` or the historical `ENTRY_CONFIRMED_SINGLE_TRADE` value.
- Calls `_write_managed_position`.
- Updates the entry to `ENTRY_FINALISED` with the order id, trade id, and transaction ids.
- Commits only when the update changes one row.

Any `JournalUnavailable` or other exception rolls the transaction back. A unique-trade `IntegrityError` becomes `duplicate_position_identity` and leaves the entry unfinalised. Test 02 wrapped `_commit` and observed exactly one commit on the success path. The position write appears before `SET outcome = ?` in that function.

`record_entry_response` builds the `Position` with `broker_order_id=""` and `broker_trade_ids` set to the verified `tradeOpened.tradeID`. The order transaction id stays on `entry_operations.broker_order_id`. Initial MFE is 0 and protection is inactive. A repeated finalisation does not replace an in-memory position of the same instance and does not call the position write, so a later ratchet is left in place (test 12).

No broker request is made inside the transaction. `classify_entry_response` runs before it.
