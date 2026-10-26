# Next stage

Do not start R.6 from this result.

The code path that runs when the bot is later switched on now includes the direction gate, the inactive-strategy gate, unresolved order status, and fail-closed recovery. That path has not been started.

A later stage would need separate approval before any of these:

- An offline PostgreSQL test of the unresolved SQL and the advisory lock, with no production database and no Docker.
- A decision on the backtest direction fallback.
- Any real or practice startup.

Until then: strategies stay inactive, live orders stay blocked, and the application stays off.
