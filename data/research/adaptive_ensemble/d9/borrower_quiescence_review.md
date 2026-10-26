# Borrower quiescence

Classification: BORROWER_QUIESCENCE_UNVERIFIED

This is separate from D8-CONC-01. D.9 did not change `app.py` or `telegram_control.py`.

`stop_telegram_control` sets a stop event, drops its thread reference, and `join`s for at most 2.0 seconds. A timeout does not raise and does not mean the thread has exited. The poller can still be in `getUpdates` or in `process_updates`. Command handlers call `fetch_all_trades_ordered`, which holds `_pg_lock` for the query and does not keep the connection afterward.

While a helper holds `_pg_lock`, release waits, then closes after that helper returns. That prevents close during the helper's locked section. It does not prove the poller thread has left its loop. The next loop can call the helper again after release. Cancelling the four asyncio tasks does not join this thread.

No isolated run showed release closing a connection while a helper was inside `execute`. That is not ACTIVE_BORROWER_DEFECT_CONFIRMED. The thread can still be alive after stop returns, so quiescence is not verified. A held Python reference from `get_connection` shows reachability, not an in-progress query.

Making stop wait until the thread is gone, or refusing release until that is true, would require `telegram_control.py` or `app.py`. That is scope expansion. It was not done. Database release is not classified as universally safe.
