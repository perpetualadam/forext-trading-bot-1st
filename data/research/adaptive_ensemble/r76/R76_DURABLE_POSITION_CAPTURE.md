# R.76 durable position capture

`record_entry_response` (`forex_bot/entry_capture.py` lines 51–117) publishes only `ENTRY_CONFIRMED_SINGLE_TRADE` after:

1. the journal outcome is committed
2. stop and take-profit are present on the entry row
3. `persist_bot_position` commits
4. `positions[symbol]` is empty or already the same `position_instance_id`

Initial state written by that path:

- units from the opened trade
- entry price from the fill price
- stop and take-profit from the journal row
- `max_profit_pips = 0`
- `profit_protection_active = False`
- `profit_protection_close_attempt_ts = 0`
- `min_profit_pips = 0`
- `max_adverse_pips = 0`
- ATR from the journal when it was supplied, otherwise null

Zero is used for MFE, activation, minimum profit, and adverse excursion because those are the verified initial values at entry, not substitutes for an unknown ratchet.

`persist_bot_position` (`forex_bot/position_recovery.py` line 52) refuses observation rows, unknown execution kinds, and any `local_broker_trade_ids` length other than 1. A second instance with the same trade id raises `duplicate_position_identity` (test 32). The same instance with a different trade id raises `journal_position_disagreement` (test 31). A lower generation raises `conflicting_generation` (test 33).

A failed capture does not call a close. `evidence["close_submission_count"]` is 0.
