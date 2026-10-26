# Stage D.6 safety-repair test isolation review

`tests/test_live_safety_repair.py` was not imported in the parent process.

Module-level imports include `bot_loop`, `oanda_exec`, and `telegram_control`. Importing `bot_loop` imports `config`, which calls `load_dotenv()`. The order-placement tests call `_place_market_order_open_sync` only after patching `get_api`, and the authorisation gate raises before `request`.

The D.6 child installed the dotenv fake, the requests fake, the psycopg2 fake, the socket and DNS denials, and the path denials before pytest collected the module. It did not replace `oanda_exec` functions, so the real authorisation gate still ran. `conftest.py` points the safety file at a pytest temporary path.

The nested pytest exit code was 0. The module defines 23 tests and contains no skip marks. The child network list was empty.

The repair module does not execute `lifespan`. Its result is isolated component coverage, not partial-startup cleanup coverage.
