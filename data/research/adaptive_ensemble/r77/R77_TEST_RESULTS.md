# R.77 test results

Command form: `python -B data/research/adaptive_ensemble/r77/poc/test_r77_atomic_entry.py`

## Windows CPython 3.13.5

| Suite | Result |
| --- | --- |
| R.77 atomic entry | 87 passed |
| R.76 entry recovery | 69 passed, 3 failed |
| R.75 guard and recovery | 13 passed |
| R.74 journal | 20 passed |
| R.74 operational | 9 passed |
| R.73 close evidence | 8 passed, 21 failed, 2 errors |
| R.72 broker protection | 36 passed, 1 failed |
| R.71 profit protection | 8 passed |
| R.70 snapshot | 25 passed, 1 failed |
| R.69 integration | 44 passed, 3 failed, 1 skipped |
| R.68 observation | 27 passed, 2 failed, 1 error, 1 skipped |

R.77 failures: none.

The R.77 run did not call `run_bot`, `main.py`, or `forex_bot.app`. Synthetic API objects recorded no successful `OrderCreate` except the one injected body in test 25. No `PositionClose` was accepted. `isolation.ATTEMPTS` contained no `psycopg2.connect` and no non-loopback socket connect from the assertions in tests 86 and 87.

## WSL CPython 3.12.3

`python3 -B data/research/adaptive_ensemble/r77/poc/test_r77_linux_journal.py`: 2 passed.

Import of `forex_bot.oanda_client` stopped at `import oandapyV20` with `ModuleNotFoundError`. That import is line 13 of `oanda_client.py`, before `forex_bot.config`, so `load_dotenv` was not reached. No package was installed.

`LINUX_INTEGRATION_NOT_VERIFIED` remains for the operational startup harness and every module that imports the SDK.
