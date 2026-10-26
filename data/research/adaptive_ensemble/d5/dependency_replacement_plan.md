# Stage D.5 dependency replacement

Replacements that matter at import time are installed in the runner before `import forex_bot.app`. Replacements of names that `lifespan` looks up on the app module are installed after that import and before `async with app.lifespan(app)`.

| Original | Where used | Replacement | When | Complete | Residual module effect | Detection | Prevention | Restore |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `dotenv.load_dotenv` | `config.py` import | counter, returns False, opens nothing | before import | yes | none | `dotenv_calls` | fake module in `sys.modules` | process exit |
| `requests` | alerts, telegram, oandapy | `post`/`get`/`request` record and raise | before import | yes | import of the name succeeds | `requests` count | raise | process exit |
| `psycopg2.connect` | `database.py` | records and raises | before import | yes | no libpq connection | `psycopg2.connect` count | raise | process exit |
| `app.get_connection` | lifespan after the guard | recorder | after import, before lifespan | yes | real function remains in `database` but is not the name lifespan calls | count | fake returns without connecting | process exit |
| `orders.load_open_orders_from_db_into_memory` | lifespan local import | recorder | before lifespan | yes | real function not bound by that import | count | fake | process exit |
| `forex_bot.reconciliation` | lifespan local import | fake module with recorders | before lifespan, pre-seeded | yes | real module is not loaded | counts | `sys.modules` entry | process exit |
| `app.build_api` | lifespan | recorder | before lifespan | yes | real builder not called | count | fake | process exit |
| `app.fetch_account_summary` | lifespan via `to_thread` | recorder | before lifespan | yes | no account request | count | fake | process exit |
| `app.alert` | lifespan start and stop | recorder | before lifespan | yes | no alert thread | count | fake | process exit |
| `app.run_bot` and the three loops | `create_task` | inert coroutines that wait on an event | before lifespan | yes | real bodies are not the scheduled coroutines | `scheduled:_inner` | fake | process exit |
| `forex_bot.telegram_control` | lifespan local import | fake start/stop recorders | before lifespan | yes | real module is not loaded | counts | `sys.modules` entry | process exit |
| `oanda_exec` order/place/submit callables | only if something calls them | wrapper that records and raises | after import | yes for those names | other functions unchanged | `order_route:` count | raise | process exit |
| `app.load_operational_events_cache_from_db` | lifespan | recorder | before lifespan | yes | no database read | count | fake | process exit |

`log_config.configure_forex_bot_logging` is the real function. It attaches a stream handler and does not open the network or a safety file.

The passing run showed `psycopg2.connect` count 0, `requests` count 0, and no `order_route:` counts. Valid startup incremented the fake service counters. Protected startup left those counters at 0.
