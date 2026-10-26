# R.71 Baseline and Source Integrity

`R71_BASELINE_VERIFIED`

## Repository

- Commit: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Root commit: `ec68e8eced131276675f26c93f55d4e84a009abc`
- Commit count: 43
- `git status --short` line count before the R.71 reports: 275
- The dirty tree was not reset, cleaned, stashed, or committed.
- `one_session.permit`: absent
- Consumed marker size 10, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`
- `REAL_SESSION_SOURCE_ENABLEMENT = False` in the R.56 phase-6 gate and the R.59, R.60, and R.61 gates

## Expected hashes

All ten matched before any R.71 test. They are the R.70 values. No operational file was edited afterward.

| File | SHA-256 |
| --- | --- |
| `forex_bot/positions.py` | `129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5` |
| `forex_bot/reconciliation.py` | `df67cc020986e0056b4bf3bea6fbbd9947090741cafa8793a4ac57660a0b9165` |
| `forex_bot/bot_loop.py` | `51023112554b2b6989ade50994a822aeb6e1968df58e513ad00ded820820ec51` |
| `forex_bot/broker_exit.py` | `bcdc3e04908208f8c397acb291eceae19fca5dc78028a6914269d409cc53474c` |
| `forex_bot/profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| `forex_bot/execution.py` | `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2` |
| `forex_bot/trading.py` | `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` |
| `forex_bot/live_manage.py` | `60d87b8665620743467832758032857e975d32da15322307a0c331009cc7b25d` |
| `forex_bot/oanda_exec.py` | `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8` |
| `main.py` | `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` |

## Environments

- Windows CPython 3.13.5. The isolated calculation file passed: 8 tests, 0 failures, 0.003s.
- WSL2 CPython 3.12.3. The same file stopped at `ModuleNotFoundError: oandapyV20` because it imports `reconciliation.py`. pandas, numpy, and psycopg2 are absent. requests is present. Nothing was installed.

## What was not done

`main.py`, `forex_bot.app`, and `run_bot` were not started. `.env` was not opened. No broker request and no PostgreSQL connection were made. Pytest was not used, because `tests/conftest.py` imports operational helpers that load the real config path.
