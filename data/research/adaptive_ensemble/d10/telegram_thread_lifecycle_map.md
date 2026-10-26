# Telegram thread lifecycle

Evidence: STATIC_SOURCE_REVIEW of `forex_bot/telegram_control.py` and `forex_bot/telegram_cloud.py`. Runtime confirmation is in the execution results.

| Item | Actual source |
| --- | --- |
| THREAD_CREATOR | `start_telegram_control` |
| THREAD_OWNER | Module globals `_poller_thread` and `_poller_started`, guarded by `_poller_lock` |
| THREAD_TARGET | `_poller_loop` -> `_poller_loop_inner` |
| THREAD_NAME | `telegram-control` |
| DAEMON | `True` |
| STOP_SIGNAL | `_stop_event` (`threading.Event`). `stop_telegram_control` calls `set()`. `start_telegram_control` calls `clear()` before creating a thread. |
| LOOP | `while not _stop_event.is_set()` |
| BLOCKING_POINTS | `delete_webhook_if_configured`, `requests.post` for `setMyCommands`, `_drain_backlog` (`get_updates` with timeout 0), then `get_updates` inside the loop. `get_updates` holds `_GETUPDATES_LOCK` around `requests.Session.get`. Error paths call `_stop_event.wait`. A successful HTTP 200 does not wait. |
| DATABASE_ACCESS_POINTS | Command handlers, not the poll loop itself. `cmd_trades` calls `fetch_all_trades_ordered`. Search calls the same helper. Both imports are inside the handler. The helper holds `_pg_lock`. |
| NETWORK_ACCESS_POINTS | `telegram_cloud.get_updates` (`Session.get` to `getUpdates`), `requests.get` for `getWebhookInfo`, `requests.post` for `deleteWebhook`, `setMyCommands`, and `sendMessage`. |
| JOIN_BEHAVIOUR | `stop_telegram_control` copies `_poller_thread`, sets `_poller_started = False` and `_poller_thread = None`, then `thread.join(timeout=2.0)` if the thread is alive and is not the caller. |
| JOIN_TIMEOUT | 2.0 seconds, hardcoded. |
| ALIVE_STATE_OBSERVABILITY | No `is_alive()` check after `join`. The function returns `None`. The stored reference is already cleared, so a later caller cannot see the old thread through `_poller_thread`. `threading.enumerate()` still shows `telegram-control` while it is alive. |
| RESTART_BEHAVIOUR | A second `start` while `_poller_started` is true returns without a new thread. After `stop` clears that flag, a new `start` can run while the old thread is alive. That `start` also clears `_stop_event`, so the old thread's loop condition becomes false again. |
| RESOURCE_DEPENDENCIES | Synthetic token and chat id through `commands_enabled()`. Shared database globals only when a command handler calls a database helper. |
| EVIDENCE_LEVEL | STATIC_SOURCE_REVIEW, with ACTUAL_TELEGRAM_FUNCTION_ISOLATED confirmation in Gate D. |

`reset_telegram_control_for_tests` calls `stop_telegram_control` and then clears `_stop_event`. Clearing the event while a worker is still alive would let that worker continue. The harness calls reset only after the worker has been joined.
