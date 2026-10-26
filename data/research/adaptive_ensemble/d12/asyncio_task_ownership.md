# Asyncio task ownership

The lifespan creates, in order, `reconciliation_loop`, `health_snapshot_loop`, `telegram_inbound_loop`, and `run_bot`. Those are asyncio tasks. The Telegram poller is a thread and is not one of them.

`_await_owned_tasks` (app.py lines 79-93) cancels every task, then awaits every task. One await failure is recorded and does not skip the rest. `CancelledError` is ignored.

An incomplete Telegram stop does not leave those tasks pending. The isolated blocked shutdown and the cancelled blocked shutdown both finished with no pending owned tasks. The thread can still be alive after that.
