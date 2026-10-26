# Startup wiring

SOURCE-REVIEWED. Startup was not executed.

`app.py` lifespan calls `initialise_fail_closed`, then `load_open_orders_from_db_into_memory`, and only later schedules `run_bot`. R.5 did not edit `app.py`. The loader now recognises `UNRESOLVED` and fail-closes new broker reservations when recovery cannot be read. That flag lives in `database.py`, which the broker branch already consults, so the existing startup call reaches the new behaviour without an `app.py` edit.

This is not evidence that startup succeeded. The web server, trading loop, Telegram listener, broker client, and reconciliation loop were not started.
