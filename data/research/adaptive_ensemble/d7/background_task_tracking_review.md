# D.7 background-task tracking

`lifespan` creates four tasks, in this order:

1. `reconciliation_loop`
2. `health_snapshot_loop`
3. `telegram_inbound_loop`
4. `run_bot`

Each task object is appended to `owned_tasks` immediately after `create_task`. A failure inside a later `create_task` still leaves the earlier objects in that list. The cleanup `finally` is attached to the same `try`, so it runs when task creation or Telegram start raises.

The isolated runs observed:

- failure on the second task: 1 created, 1 cancelled by the application, 0 still pending, harness cancelled 0
- failure on the fourth task: 3 created, 3 cancelled, 0 pending
- failure in Telegram start after all four: 4 done, 0 pending

No application-owned task remained pending after those failures. The scheduled coroutine code name was `_inner`, the fake coroutine, not the real trading-loop function.
