# Startup source map

File: `forex_bot/app.py`. The lifespan function was not called.

## Import time

Lines 15-52 import alerts, configuration, `bot_loop.run_bot`, execution helpers, database functions, and `oanda_client.build_api` / `fetch_account_summary`. This happens when the module is imported, before `lifespan`. Static reading of `database.py` and `oanda_client.py` shows the PostgreSQL connection and the OANDA client are created later, inside `get_connection()` and `build_api()`, not at import. `config.py` calls `load_dotenv()` when it is imported. This stage did not import `app.py`, so that read did not happen here.

Importing `bot_loop` constructs the six strategies. After D.3 they start inactive.

## Lifespan

`StartupSafetyAbort` is defined at line 57.

`lifespan` begins at line 252.

1. Lines 254-261 configure logging. No database or broker call.
2. Line 262 calls `initialise_fail_closed()`.
3. Lines 263-272 raise `StartupSafetyAbort` when `live_safety_initialised()` is false. The reason code is logged. The document is not logged.
4. Line 273 sets the lifespan phase to starting. This is after the abort.
5. Line 274 `get_connection()` opens PostgreSQL and applies additive DDL.
6. Lines 278-279 load orders and reconcile metadata from the database.
7. Line 280 `build_api()`.
8. Lines 281-284 `fetch_account_summary`. Exceptions are logged and startup continues. This handler is only reached after the guard.
9. Lines 286-289 `run_reconciliation_once`, with the same exception pattern.
10. Lines 309-312 create reconciliation, health, telegram, and `run_bot` tasks.
11. Line 315 `start_telegram_control()`.
12. Lines 316-318 `yield`, then the `finally` block cancels tasks that were created.

The guarded path raises before `try` / `yield`, so the shutdown `finally` does not run. No tasks or connections are created on that path.

Required guard: step 3 must remain before steps 5-11.
