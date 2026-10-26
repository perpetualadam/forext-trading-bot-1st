# Startup sequence map

STATICALLY_VERIFIED from source. The lifespan function was not called. This is not a runtime trace.

1. Module import. `forex_bot/app.py` imports `run_bot`, `get_connection`, and `build_api` / `fetch_account_summary`. Importing `bot_loop` constructs the six strategies. After D.3 they are inactive. Import does not call OANDA or open PostgreSQL. `database.get_connection` and `oanda_client.build_api` run later.
2. Strategy construction. `strategy_meta.py` line 77, during the import above. Before safety validation. Cannot contact OANDA. Does not write the safety file.
3. Configuration. `config.py` calls `load_dotenv()` when that module is imported. This review did not import it and did not read `.env`.
4. Safety-state initialization. `app.py` `lifespan` line 254 calls `initialise_fail_closed` before database, broker, and background tasks. A missing file creates a BLOCKED document. A valid version-1 document is loaded and rewritten. A future, corrupt, or unreadable file is left in place. `initialise_fail_closed` does not raise for those protected files.
5. Activation restoration. Inside `initialise_fail_closed`, after the file is classified. A valid document can set `active` from a boolean. A protected file deactivates all six in memory and does not write.
6. Database initialization. `lifespan` line 256 calls `get_connection()`, which connects and runs `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE`. This still runs after a protected safety file because initialise does not raise.
7. Broker client. `build_api()` at line 262, after safety init.
8. Broker account request. `fetch_account_summary` at line 264. Exceptions are logged and startup continues.
9. Reconciliation. `run_reconciliation_once` at line 269. Static reading of earlier stages: this path reads broker positions and pending orders. Not executed here.
10. Scheduler and loops. Lines 291-294 create reconciliation, health, telegram, and `run_bot` tasks. Line 297 starts telegram control. These start even when the safety file was protected.
11. Order routing. `bot_loop` returns before sizing when `strat.active` is false (line 1076). The live-order gate in `live_safety.live_open_blocked_reason` returns a block reason unless runtime state is valid and authorisation is ALLOWED. New exposure was not executed.

Failure handling: AccountSummary and reconciliation exceptions are swallowed. A future schema does not stop the rest of lifespan. That continuation is a remaining startup defect outside `strategy_meta.py`.
