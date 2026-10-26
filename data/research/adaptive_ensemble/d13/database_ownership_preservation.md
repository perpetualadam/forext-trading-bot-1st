# Database ownership

`database.py` was not modified. Its hash remains `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e`.

Successful shutdown still retains the process-global connection. Failed startup still calls `release_connection_after_failed_startup` only when `telegram_stop_failed` is false. An incomplete Telegram stop does not set that flag and does not release the connection.

Reporting adds no connection, query, or reconnection. Ownership checks showed a delayed poll query delta of 0, a gate query delta of 0, and a connect delta of 0. Final open fake connections were empty after harness cleanup.

Process-global retention on a successful shutdown remains the established ownership rule.
