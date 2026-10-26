# R.69 import isolation

## Method

`data/research/adaptive_ensemble/r69/poc/isolation.py` runs before any `forex_bot` import.

| Control | Behaviour |
| --- | --- |
| Environment | Names containing token, secret, password, account, postgres, telegram, discord, or oanda are set to empty strings. Values are not printed. |
| `dotenv` | `sys.modules["dotenv"]` is a stub. `load_dotenv` records a call and returns false. It does not open a file. |
| `forex_bot.config` | A synthetic module with `IS_R69_SYNTHETIC = True`. Account id `001-002-0000001-003`. Token empty. Telegram and Discord empty. The real `config.py` is not executed, so its `load_dotenv()` does not run. |
| Files | `open` refuses `.env`, `one_session.permit`, and paths containing `credential`. |
| Sockets | Non-loopback `connect` and `create_connection` raise `IsolationBreach` and are recorded. Loopback is left to the real socket so the Windows asyncio self-pipe can start. |
| HTTP | `urllib.request.urlopen` raises `IsolationBreach`. |
| PostgreSQL | `psycopg2.connect` raises `IsolationBreach`. If the driver is absent, a stub module is installed so `database.py` can import without a live driver. |

The tests then import the real `forex_bot.reconciliation` and `forex_bot.bot_loop`. `reconcile_positions_log_only` and `_evaluate_impl` are the functions from those modules. Their bodies were not copied.

Broker I/O is a `FakeAPI.request` installed as `oanda_client._api`. `OpenPositions`, `OrdersPending`, `TradeDetails`, and `TransactionDetails` return synthetic bodies. Any other endpoint name raises `IsolationBreach`. Candles are a local `DataFrame` returned by a replacement `fetch_ohlcv`. Quotes are an in-memory `ManageQuote`. `execute_oanda_market_close` raises if called.

`PERSIST_RECONCILE_STATE` is `0` so reconciliation does not treat the database as required. `clear_pending_broker_exit` still calls the database helper. That helper's `psycopg2.connect` is refused, the helper logs `PostgreSQL unavailable`, and the observation write still completes. No connection object is kept.

## Proof the targets are real

The loaded callables report `__module__` `forex_bot.reconciliation` and `forex_bot.bot_loop`. The synthetic config flag is true. `load_dotenv` and non-loopback sockets are absent from the attempt log at the start of the run.

## What was not loaded

`main.py` and `forex_bot.app` were not imported. `run_bot` was not started.
