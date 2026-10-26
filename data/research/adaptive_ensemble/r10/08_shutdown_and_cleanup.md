# Shutdown and cleanup

`shutdown_application` closes, in order: scheduler, health, messaging, market data, broker, persistence.

| Check | Result |
| --- | --- |
| G01 | Those six fakes are removed from the open set after a clean shutdown. |
| G02 | The recorded close order matches that list. |
| G03 | A second shutdown does not raise and does not reopen anything. |
| G04 | A messaging failure closes market data, broker, and persistence in that reverse order. |
| G05 | `trading_loop_started` stays false and the offline seam does not import `run_bot`. |
| G06 | The fake broker is closed. A later submit or close call raises. |
| G07 | Fake persistence is closed. `database._pg_conn` is None. |
| G08 | Fake messaging is closed. `send_message` raises after recording the local text. |
| G09 | No scheduler entry remains open. |
| G10 | `close_failed:persistence` is present on the report. |

There is no restart loop. Shutdown sets the lifecycle to stopped, and the next initialization is refused.
