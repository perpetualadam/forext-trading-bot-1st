# Database borrower quiescence

Status: DATABASE_BORROWER_QUIESCENCE_UNVERIFIED

The release helper's docstring says the caller must already have stopped borrowers. The function does not check that. It clears the globals if they still point at the same objects, then closes those objects.

What was observed:

- `release_borrowed` held the object returned by the real `get_connection`, then called release. The application closed it (`borrowed_close_calls` 1). A second release did not connect and did not record a close error. The Python reference was still in the test when close ran.
- Lifespan releases only after `_await_owned_tasks` and only on the startup-failure path when Telegram stop did not raise. The four task bodies in the test were inert. They do not prove that every helper and the Telegram poller have left the cursor.
- `stop_telegram_control` can return while its thread is alive. Lifespan does not inspect that.
- Successful startup never releases, so the success path does not close under a live borrower. It also never proves the borrowers have stopped.

This is not recorded as a second executed use-after-close. No schedule showed a helper inside `fetch_all_trades_ordered` while release closed the connection. The source also cannot show that such a helper was absent. Database release is therefore not classified as safe.
