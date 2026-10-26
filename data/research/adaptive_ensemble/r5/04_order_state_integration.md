# Order-state integration

CODE MODIFIED in `orders.py`, `database.py`, and `bot_loop.py`.

`OrderStatus` now includes `UNRESOLVED`. Recovery no longer turns an unknown status into `PENDING`, and it no longer fills a missing side with `BUY`.

`ingest_recovery_snapshot` is the function startup recovery uses after the database read. A synthetic unresolved row reloads as `UNRESOLVED` and blocks a new client id. Pending and partial rows keep those statuses. A corrupt or unreadable snapshot sets the fail-closed flag.

`mark_order_failed_or_cancelled` returns without writing when the order is unresolved. The database cancel statement also refuses to change an `UNRESOLVED` row.

In-process reservations hold the existing database lock, so two overlapping attempts see the unresolved map. The PostgreSQL advisory lock that covers two database sessions was not executed.

Confirmed fill, rejection, and cancellation still clear the in-memory intent book and do not create a replacement id. There is no retry and no timer release.
