# Source change log

Pre-stage `forex_bot/bot_loop.py`: `2585b550085e47b84dd0d353b207709797d28abca28b7bb1ee4d3e956c0c8732`

Post-stage `forex_bot/bot_loop.py`: `91953e58f9ab131399dd3ec84ebd5217161cfbc773022b42a58154597639528f`

`app.py`, `database.py`, and `orders.py` hashes are unchanged. Protected broker, safety, strategy, Telegram, requirements, and Docker hashes are unchanged.

The shared decision gained selector, vote-wrapper, and RL-veto calls. `production_execution_adapter` is the only `execute_oanda_market_open` call. The legacy tail returns before any broker call. Production dependencies carry the selector, vote, and RL flags with `simulation=False`.
