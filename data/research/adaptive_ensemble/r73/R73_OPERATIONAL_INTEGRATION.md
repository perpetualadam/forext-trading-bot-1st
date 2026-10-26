# R.73 Operational Integration

`forex_bot/bot_loop.py` lines 1078–1129.

When the existing trigger block has already decided a close is requested:

1. A live row calls `run_guarded_live_close`.
2. Any other state returns before `close_position` and before the RL update.
3. `CLOSE_FULLY_CONFIRMED` falls through to `close_position`.
4. Paper and the other non-live kinds still call `execute_trade` and then `close_position`.

`positions.close_position` lines 104–120 refuse a live row unless `live_local_delete_permitted` is true. That helper requires full confirmation, equal confirmed and requested units, and remaining units of zero. After a permitted live pop, the operation is cleared.

The profit-protection calculation, the weekend clock, and the entry block are unchanged. `broker_sl_tp_hit` still returns false, so a protection record still does not request this close.

`R73_FULL_CONFIRMATION_REQUIRED_FOR_LOCAL_DELETE`

`R73_ENTRY_BLOCK_UNCHANGED`

`R73_PROFIT_PROTECTION_UNCHANGED`
