# Stage D.5 regression compatibility

The three regression modules do not import `forex_bot.app`. `conftest.py` does not import `app` or `config`. They were run in the same pytest command as the lifespan tests.

| Module | Result | Evidence |
| --- | --- | --- |
| `tests/test_live_safety_preservation.py` | 30 passed | ISOLATED_COMPONENT. D.2 preservation still holds. |
| `tests/test_strategy_activation_defaults.py` | 35 passed | ISOLATED_COMPONENT. D.3 inactive default still holds. |
| `tests/test_startup_safety_preflight.py` | 50 passed | STATIC_ONLY. D.4 source-order and predicate checks still hold. They do not execute lifespan. |

`tests/test_live_safety_repair.py` was not run. It imports `oanda_exec`, `telegram_control`, and `bot_loop`. Importing `bot_loop` imports `config`, which calls the real `load_dotenv()`. That module was not wrapped in the D.5 subprocess harness.

No existing assertion was weakened. No production module was edited. The D.2, D.3, and D.4 source hashes are unchanged.
