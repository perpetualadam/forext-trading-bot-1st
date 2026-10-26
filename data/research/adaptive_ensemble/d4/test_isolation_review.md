# Test isolation review

`tests/test_startup_safety_preflight.py` does not import `forex_bot.app`, `bot_loop`, `oanda_client`, `oanda_exec`, `database`, or `config`.

It parses `app.py` with `ast` and reads the lifespan source as text.

Safety behaviour is tested by calling `initialise_fail_closed()` and `live_safety_initialised()` against the pytest temporary path from `tests/conftest.py`. That fixture does not import `app.py` and does not call `load_dotenv()`.

The tests assert the temporary path is not `data/ops` or `v2_shadow`.

`forex_bot.app`, `forex_bot.database`, `psycopg2`, `forex_bot.oanda_client`, `forex_bot.oanda_exec`, and `forex_bot.bot_loop` were not in `sys.modules` during the new tests.

Socket creation was replaced during one safety load and raised if called.

The real lifespan, Uvicorn, the scheduler, and the trading loop were not started.

LEVEL 3 was not attempted. Importing `app.py` imports `config.py`, which calls `load_dotenv()` and would read a real `.env` if one is present.
