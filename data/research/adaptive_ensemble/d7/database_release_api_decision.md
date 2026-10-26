# D.7 database release API decision

`release_connection_after_failed_startup` was added because failed startup needs to close the connection `get_connection` has already published, and lifespan is allowed to do that only after the tasks it created have been awaited.

The helper does not connect, does not execute SQL, and does not change authorisation. A second call is a no-op. It closes the cursor and connection only when those globals still point at them. Isolated tests observed one close call, an unchanged connect count, and an unrelated connection left open.

Lifespan calls it only when startup raised before `yield` and `stop_telegram_control` did not raise. It is not called after a successful yield.

It is not safe to call it while a database helper still holds `_pg_lock` and then continues to use the cursor, or while the Telegram poller may still be inside `fetch_all_trades_ordered`. The failed-startup path reaches the helper only after lifespan-owned tasks have been awaited. Production `start_telegram_control` catches its own start errors, so a raised start is the injected test path; if stop then raises, the helper is skipped.
