# Direction-repair diff

File: `forex_bot/bot_loop.py`.

Removed the fallback that turned a missing or unrecognised direction into `BUY`.

Added `canonical_entry_direction` and `direction_action_gate`.

- `BUY` and `SELL` stay `BUY` and `SELL`.
- Leading or trailing spaces and lowercase letters are still accepted for those two words.
- `None`, an empty string, spaces only, `NO_TRADE`, `UNKNOWN`, numbers, and any other value return no trade.

The check is immediately after the existing vote-allow check and before the RL gate, position sizing, order construction, client order id generation, reservation, and broker dispatch.

Valid buy and sell behaviour after that check was not rewritten. Strategy selection and the vote-rejection return were not changed.
