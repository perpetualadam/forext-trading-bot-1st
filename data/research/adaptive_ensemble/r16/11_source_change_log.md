# Source change log

Application source modified: `forex_bot/bot_loop.py`.

Pre-stage hash: `518b5930038e1ef520f17afe3555c9d055efd0ad7acc196d0f3c879b9381c0bd`.

Post-stage hash: `27934fe441420b0a978bfbb207b2a21a98b9420415668f60b98fc05db4422f4e`.

The shared decision copies accepted equity once. `position_sizing` receives that float. `portfolio_risk_cap_exceeded` receives that same float instead of `current_equity()`. When the gross-notional percentage is enabled, its cap is `account_ccy_to_usd(accepted_equity * percentage)` instead of `current_equity()`. Evidence records `accepted_equity`, `sizing_equity`, `portfolio_cap_equity`, and `current_equity_used_for_entry=False`.

`app.py`, `database.py`, `orders.py`, `oanda_exec.py`, `trading.py`, `config.py`, and the protected files were not modified.

Hash pins in the R.8, R.10, and R.11 tests were updated to the new `bot_loop.py` hash. R.12 J43 and R.14 J86 were strengthened as described in the regression record. `trading.py` formulas were not edited.

The working tree was already dirty. This log is the R.16 change, not the cumulative diff against HEAD.
