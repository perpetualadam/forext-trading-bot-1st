# D.11 stop contract compatibility

`app.py` calls `stop_telegram_control()` and ignores the result. A timeout that raised would be caught, set `telegram_stop_failed`, and on a successful startup would be re-raised after task cleanup. A normal long poll can outlive the 2 second join, so a timeout exception would turn ordinary shutdown into a failure. The timeout is therefore a status, not an exception.

Returning a status does not by itself stop database release. On the success path `app.py` never releases the process connection. On startup failure it releases only when stop did not raise. Telegram start is the last statement in the startup `try` and does not raise, so a startup failure after Telegram start is not reachable. The reachable failure path releases the database before a Telegram worker exists.

The worker gate is what makes an incomplete stop safe if a connection is released anyway: the worker cannot begin a new trade read, and an in-flight trade read holds `_pg_lock` until it finishes.
