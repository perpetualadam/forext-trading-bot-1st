# Application shutdown contract

`lifespan` imports `stop_telegram_control` at `forex_bot/app.py` lines 367-370 and calls it at lines 383-384. The return value is not assigned, checked, or logged.

A raised stop is caught at lines 385-387, recorded, and does not skip task cleanup at line 390. Database release at lines 391-394 runs only when startup failed and stop did not raise. Successful shutdown does not release the connection.

An incomplete stop does not raise, so it does not enter `_last_cleanup_errors`. The lifespan can return with a live worker and an empty cleanup-error list.

The status strings are stable enough for `app.py` to read. The current application does not read them.
