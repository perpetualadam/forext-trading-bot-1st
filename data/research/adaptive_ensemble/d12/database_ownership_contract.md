# Database ownership contract

`get_connection` (database.py lines 185-227) publishes one connection and cursor under `_pg_lock`. A later call reuses an open connection.

Normal lifespan shutdown does not call `release_connection_after_failed_startup`. That is `INTENTIONAL_PROCESS_GLOBAL_RETENTION`.

Failed startup before Telegram does release it. That is `FAILED_STARTUP_CLEANUP`.

The reachable application path does not release after Telegram has started. An in-flight trade read holds `_pg_lock`, so release waits. A stopped worker does not start a new trade read. No post-stop reconnection was observed.

This is not an unexpected leak.
