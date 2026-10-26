# Actual startup call graph

Status: SOURCE-REVIEWED. The normal launcher was not executed.

```
main.py:19-26
  uvicorn.run("forex_bot.app:app")
    forex_bot.app lifespan (app.py:653)
      configure_forex_bot_logging
      initialise_application (app.py:420)
        production ports (app.py:535)
```

Production port order, used only if lifespan runs:

1. `validate_config` (app.py:539) reads `Config.SYMBOLS`. An empty list raises `StartupSafetyAbort` before persistence.
2. `verify_safety` (app.py:544) calls `initialise_fail_closed`. Effective live-order auth stays BLOCKED. A failed safety state raises `StartupSafetyAbort`.
3. `init_persistence` (app.py:563) sets the lifespan phase to `starting` and calls `get_connection`. That call can create schema when a real connection succeeds. The offline tests do not call it.
4. `recover_orders` (app.py:567) calls `load_open_orders_from_db_into_memory` and `load_reconcile_state_from_db`.
5. `init_broker` (app.py:575) calls `_oanda_client().build_api()`.
6. `init_market_data` (app.py:578) fetches the account summary and runs `run_reconciliation_once` on worker threads. Those two failures are logged and do not abort the production port.
7. `init_messaging` (app.py:593) is a no-op. Messaging startup stays in the scheduler so the old production order is preserved.
8. `init_health` (app.py:596) logs a pre-trade warning when the execution mode is not paper.
9. `schedule_trading` (app.py:611) marks the bot started, sets the phase to `running`, loads operational events, sends the start alert, logs windows, and creates four tasks: reconciliation, health snapshot, telegram inbound, and `run_bot`. It then starts telegram control.

Lifespan cleanup remains in the `finally` block: stop telegram if the production scheduler reached it, cancel owned tasks, and release a connection only after a startup failure.

Import side effects that the offline path avoids:

- `forex_bot.config` calls `load_dotenv` on import. The test runner stubs that function before import.
- `forex_bot.database` imports `psycopg2` and connects only inside `get_connection`.
- `forex_bot.oanda_client` and `forex_bot.bot_loop` import the OANDA SDK. Both imports are now inside the functions that need them, not at `forex_bot.app` import time.
- `forex_bot.alerts` does not start its worker at import.

The offline call uses the same `initialise_application` function with fake ports. It does not call lifespan, `_production_startup_ports`, or `run_bot`.
