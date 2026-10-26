# Source change log

`forex_bot/bot_loop.py` changed from `91953e58f9ab131399dd3ec84ebd5217161cfbc773022b42a58154597639528f` to `518b5930038e1ef520f17afe3555c9d055efd0ad7acc196d0f3c879b9381c0bd`.

Added `broker_open_arguments`, `broker_signed_units`, and `_account_entry_block`. The production adapter uses the shared argument mapping and remains the only `execute_oanda_market_open` call. The missing-account equity fallback was removed from the shared decision.

`app.py`, `database.py`, `orders.py`, and `oanda_exec.py` were not modified. Hash pins in the R.8, R.10, and R.11 tests were updated.
