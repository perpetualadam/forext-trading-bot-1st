# D.7 shutdown and cleanup exception policy

Primary failure: the exception that aborted startup, or, on a successful startup, the first cleanup exception if the server block itself did not raise.

Secondary failure: an exception while stopping Telegram, awaiting a task, closing a database resource, or running the existing shutdown tail.

Rules:

- `except Exception` records and continues independent cleanup. `CancelledError`, `KeyboardInterrupt`, and `SystemExit` are not caught there.
- A task `CancelledError` is consumed for that task. The other tasks are still awaited.
- Cleanup logs contain the exception type name, not the message, so a driver message or safety document is not written by the new log lines.
- The original startup exception is re-raised from the startup handler. The `finally` block does not raise a cleanup error when a startup failure is already active.
- After a successful startup, if cleanup produced an exception, the server block did not raise, and the lifespan task is not being cancelled, the first cleanup exception is raised after the other tasks have been awaited.
- Database initialization still returns `None` on failure. Cleanup errors from that path are stored by `partial_initialization_cleanup_errors` and do not replace the `None` return.
- `startup_cleanup_errors()` exposes the type names recorded for the latest lifespan.

The injected shutdown cases observed the primary message (`injected shutdown failure`, `injected task await failure`, or `injected other task await failure`) with `RuntimeError` also present in `startup_cleanup_errors`, all four tasks done, and the successful-startup connection still held.
