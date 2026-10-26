# D.8 concurrency harness safety

The D.8 runner imports the real `forex_bot.database.get_connection` and, in lifespan mode, the real `forex_bot.app.lifespan`. It does not copy those algorithms into a substitute.

Controls that held in the executed runs:

- Child environment is synthetic. Parent secrets are not copied. Only Windows process paths required to import installed packages are inherited.
- `dotenv.load_dotenv` is replaced before import. The import recorded one fake call.
- `psycopg2` in `sys.modules` is the fake module before `forex_bot.database` is imported. `connect` increments a counter and returns a `FakeConnection`, or raises when the schedule says so. It has no path to a real driver.
- `socket.connect` and `socket.getaddrinfo` raise. The self-pipe replacement accepts only the loopback socket it just bound. The self-check denied reuse of that port and denied `127.0.0.1:5432`.
- Open and `os.replace` deny `.env`, `data/ops`, `v2_shadow`, and credential basenames. The self-check confirmed the ops denial.
- Workers are threads with a 5-second join. Barrier and event waits use 3 seconds. An alive worker after join raises.
- Worker exceptions are stored on the thread record. Initialization failures inside `get_connection` return `None` and are visible as connection state, not as a hidden retry.
- Each fake connection has a monotonic identity, separate from the thread id.
- `_snapshot` runs before `_finish`. `_finish` clears the injection phase, closes anything still open, and records that count as `harness_closed`. Application `close_calls` in the snapshot are not rewritten by that count.
- Lifespan mode replaces broker construction, account summary, reconciliation, the four task bodies, and Telegram start/stop. Real `get_connection` remains. `requests` stay at zero. Authorisation stayed BLOCKED. No strategy was active.

Residual gaps, not tripped in these runs:

- `socket.connect_ex`, `socket.create_connection`, and `asyncio.open_connection` are not wrapped. The D.7 runner wraps them. The D.8 network list stayed empty.
- The fake connection list is not guarded by its own lock. CPython list append was stable across the executed schedules.
- One schedule exception aborts the rest of that process. The cleanup-failure injection initially did that, because harness close re-entered the injection. `_finish` now clears the phase before harness close. The rerun completed every schedule.

No worker remained alive. No network denial fired during a schedule. Fake connect did not fall through.
