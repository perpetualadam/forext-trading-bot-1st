# Source modifications

Approved files changed:

- `forex_bot/database.py` — optional JSON store behind the existing insert, update, unresolved, and recovery readers. Unset store path leaves the PostgreSQL branches as they were.
- `forex_bot/bot_loop.py` — an uncertain outcome now calls `update_exec_order_row` before the local status becomes `UNRESOLVED`, so the store receives that status. With the store unset and persistence disabled, that call still returns without a database connection.

`orders.py` and `app.py` were not modified. No strategy, sizing, risk, broker, or account setting was changed.

Hash pins in the R.8, R.10, and R.11 suites now match the new `bot_loop.py` hash. The R.10 database pin matches the new `database.py` hash. The assertions themselves were not weakened.
