# Cleanup error precedence

The primary startup exception is re-raised from the startup `except` and is not replaced by later cleanup notes.

A Telegram stop exception is recorded and task cleanup continues. On a successful startup it is re-raised after cleanup if the lifespan is not being cancelled.

An incomplete stop is not an exception and is not recorded.

A task-await exception is recorded. A release failure on failed startup is recorded as a note and does not replace the startup exception. An alert failure during the shutdown tail is recorded and re-raised. Cancellation suppresses that re-raise because `cancelling()` is greater than zero.

No precedence gap was confirmed. The missing incomplete-stop report is the observability gap, not a reordered exception.
