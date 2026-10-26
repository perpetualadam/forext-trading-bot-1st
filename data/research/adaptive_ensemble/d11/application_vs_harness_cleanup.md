# Application cleanup versus harness cleanup

On a blocked lifespan shutdown, the application snapshot showed the Telegram worker alive, the stored reference alive, the stop event set, the database still held, and zero application close calls. `app.py` did not read `STOP_INCOMPLETE_WORKER_ALIVE`.

After that snapshot, the test called `release_connection_after_failed_startup` and then released the fake poll with a `/trades` update. That release is composed test code. It is not what `app.py` did. The worker performed no query and published no connection, then exited. The harness join after that is harness cleanup.

Fast shutdown is different: `stop_telegram_control` returned `STOP_COMPLETED` and the worker was already gone before harness cleanup.

Startup failures before Telegram do not call stop. The database release on those paths happens with no Telegram worker.
