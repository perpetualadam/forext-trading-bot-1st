# Stage D.5 static import graph

Gate A inspected source with AST and bounded file reads. `forex_bot.app` was not imported during this inspection.

## Direct module-level imports of `forex_bot/app.py`

Standard library: `asyncio`, `logging`, `os`, `contextlib.asynccontextmanager`, `enum.Enum`, `typing.Any`.

Third party: `fastapi.FastAPI`, `fastapi.HTTPException`, `fastapi.Query`, `fastapi.openapi.utils.get_openapi`.

Local: `alerts.alert`, `log_redact.redact_log_text`, `ai_ensemble`, `analytics`, `bot_loop.run_bot`, `config.Config`, `experiment`, `execution`, `trading`, `database.get_connection`, `oanda_client.build_api` and `fetch_account_summary`, `operational_events`, `operational_state`, `session_rules`, `state`.

`FastAPI(...)` is constructed at module level. The call does not take a host or port and does not start Uvicorn.

## Local imports inside `lifespan`

These names are loaded only when `lifespan` is entered:

- `forex_bot.live_safety.initialise_fail_closed`, `live_order_auth_reason`, `live_safety_initialised`
- `forex_bot.log_config.configure_forex_bot_logging`
- `forex_bot.orders.load_open_orders_from_db_into_memory`
- `forex_bot.reconciliation.load_reconcile_state_from_db`, `run_reconciliation_once`
- `forex_bot.execution.get_execution_mode`, `pre_trade_entry_blocked_reason`
- `forex_bot.telegram_control.start_telegram_control`, `stop_telegram_control`

`reconciliation.py` imports `oandapyV20.endpoints.positions` at module level. `telegram_control.py` imports `requests`. Both are call-time imports of lifespan, so they can be pre-seeded in `sys.modules` before the context manager runs.

## Transitive startup modules

`bot_loop.py` is imported by `app.py`, so its module-level imports load with `app.py`. Those include `oanda_exec`, `oanda_client`, `orders`, `strategy_meta`, `database` (through other modules already loaded), and `config`.

`oanda_client.py` imports `oandapyV20` and `oandapyV20.endpoints.instruments`. The installed `oandapyV20` package imports `requests` and defines host strings. It does not call the network at import.

`oanda_exec.py` imports order, position, and trade endpoint modules plus `oandapyV20.contrib.requests`. Those imports define request objects. They do not submit an order at import.

`strategy_meta.py` imports `numpy` and `pandas` and builds the six-strategy registry in memory. New `Strategy` objects start inactive.

`database.py` imports `psycopg2` and leaves `_pg_conn = None`. `psycopg2.connect` is not called at import. The installed `psycopg2` init may add a DLL directory. It does not connect.

`alerts.py` and `telegram_cloud.py` create locks and queues. `telegram_cloud` constructs a `requests.adapters.HTTPAdapter`. Neither starts a thread or an HTTP call at import. `alert()` starts the sender thread only when called.

## Configuration import

`config.py` imports `dotenv` and calls `load_dotenv()` with no arguments while the module body executes, unless `ImportError` is raised. `Config` then reads `os.environ` into class attributes, including `OANDA_ACCESS_TOKEN`, Telegram token fields, and Postgres settings. The Postgres password field defaults to the literal `password` when `POSTGRES_PASS` is unset.

## Not on the module-level app graph

`v2_shadow` is not imported by the module-level app graph. `telegram_control` and `reconciliation` are not imported until lifespan passes the safety guard, unless some other imported module imports them first. The inspected `bot_loop` module-level imports do not include `telegram_control`.

## Side-effect classification

| Module | Import-time effect | Secrets | Production state | Network client | Connects | Starts tasks | Writes files | Replacement before import |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `config` | `load_dotenv()` and `os.getenv` | yes, if the real `.env` loads | path defaults only | no | no | no | no | fake `dotenv` module |
| `database` | import `psycopg2` | no | no | the library object only | no | no | no | fake `psycopg2` |
| `oanda_client` | import `oandapyV20` | no | no | class import only | no | no | no | fake `requests` underneath |
| `oanda_exec` | import endpoint classes | no | no | class import only | no | no | no | fake `requests`; wrap order callables after import |
| `alerts` | queue and lock | no | no | no | no | no | no | replace `app.alert` before lifespan |
| `strategy_meta` | in-memory registry, inactive | no | no | no | no | no | no | not required for activation safety |
| `app` | `FastAPI()` object | no | no | no listen | no | no | no | call lifespan only after fakes |
| `live_safety` | none at import | no | no; path is read at call time | no | no | no | no | set `LIVE_SAFETY_STATE_PATH` before import |

No module in this graph calls `socket`, `psycopg2.connect`, `API.request`, `Thread.start`, or `create_task` in the module body.
