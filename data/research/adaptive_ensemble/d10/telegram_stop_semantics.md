# stop_telegram_control semantics

Source: `forex_bot/telegram_control.py` lines 1164-1174. Isolated execution used the real function. `Thread.join` was not patched.

| Question | Answer | Evidence |
| --- | --- | --- |
| 1. Does stop request termination? | Yes. It sets `_stop_event`. | STATIC_SOURCE_REVIEW and isolated calls |
| 2. Does stop wait for termination? | It calls `join` only when the stored thread is alive. | STATIC_SOURCE_REVIEW |
| 3. Is the wait bounded? | Yes. `timeout=2.0`. | STATIC_SOURCE_REVIEW. Observed elapsed 2.0135s and 2.006s on the blocked-poll path. |
| 4. Does stop return a success value? | It returns `None` on every path, including timeout. | Observed `return_value: null` |
| 5. Does stop report timeout? | No. | No return flag and no log required by the function |
| 6. Does stop raise on timeout? | No. | Blocked-poll calls returned normally |
| 7. Does stop clear the stored thread reference? | Yes, before `join`, under `_poller_lock`. | `stored_thread_cleared: true` while the thread was alive |
| 8. Can that reference be cleared while the thread is alive? | Yes. | Thread 16048 and thread 13880 remained alive after the reference was cleared |
| 9. Can a later start create another thread while the old one is alive? | Yes. `start` checks `_poller_started`, which `stop` has already cleared, and it does not check `is_alive()`. | Threads 13880 and 17184 were both alive |
| 10. Can the old thread continue polling? | Yes if the new `start` clears `_stop_event` before the old `get_updates` returns. The loop checks the event only between calls. | `stop_event_after_second_start: false` while both threads were alive |
| 11. Can the old thread continue database access? | Yes. After `get_updates` returns it calls `process_updates` before checking the loop condition. | Thread 16048 called `fetch_all_trades_ordered` after stop had returned |
| 12. Can the old thread send messages after stop returns? | The same `process_updates` path calls `send_control_message`. The isolated fake recorded `sendMessage` after command handling. No real Telegram call was made. | HTTP method list contains `sendMessage` from the fake transport |
| 13. Can stop be called repeatedly? | Yes. The second call sees no stored thread and returns immediately. | `repeated_stop` elapsed 0.0s |
| 14. Can stop be called before start? | Yes. It sets the event and returns. | `stop_before_start` |
| 15. Can stop be called while another stop is running? | The function does not take `_poller_lock` around the whole join. Two overlapping stops can both observe the thread before the reference is cleared, or the second can observe a cleared reference. This overlap was not executed. | STATIC_SOURCE_REVIEW |
| 16. Does shutdown depend on daemon-thread process exit? | The application does not join past 2 seconds and does not inspect `is_alive()` afterwards. A daemon thread can remain until process exit. That is not orderly cleanup. | Lifespan case `blocked_shutdown`: thread 3836 alive after `lifespan` returned |

The docstring says stop waits briefly so a restart cannot overlap `getUpdates`. The implementation clears the ownership flag before the wait finishes, and a timed-out wait does not keep the stop event set against a later `start`.
