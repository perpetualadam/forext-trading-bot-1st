# Stage D.5 background-task isolation

`lifespan` creates four tasks after the safety guard, in this order:

1. `reconciliation_loop`
2. `health_snapshot_loop`
3. `telegram_inbound_loop`
4. `run_bot`

It then calls `start_telegram_control()`.

The runner replaces all four targets with inert coroutines before calling `lifespan`. Each fake waits on an `asyncio.Event` and does not call the broker, the database, or order routing. `asyncio.create_task` is wrapped to count the call and record the coroutine code name.

On the valid BLOCKED run the four scheduled code names were `_inner`. They were not `run_bot`, `health_snapshot_loop`, `reconciliation_loop`, or `telegram_inbound_loop`. `start_telegram_control` was the fake recorder. The real `telegram_control` module was not loaded.

Shutdown calls the fake `stop_telegram_control` and cancels the four tasks. The Windows loop cancelled the health task before its body ran, so that fake did not increment its own counter. The other three inert bodies started during cancellation and then stopped. The process returned. The real health loop, which sleeps for hours, did not run.

On every protected-state case, `create_task` stayed 0 and `yielded` stayed 0. No trading-loop body ran.

`app.alert` is replaced, so the real `alert-sender` thread is not started by lifespan.
