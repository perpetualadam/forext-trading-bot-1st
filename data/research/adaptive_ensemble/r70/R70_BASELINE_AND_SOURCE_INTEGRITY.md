# R.70 Baseline and Source Integrity

Classification: operational baseline verified before the edit. Reports below are documentation. Tests are offline.

## Repository

- Commit: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch was not changed.
- Initial `git status --short` line count: 274. The tree was already dirty before R.70. It was not reset, cleaned, or stashed.
- `one_session.permit`: absent.
- Consumed marker: `data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.consumed`
  - Size: 10 bytes
  - SHA-256: `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`
  - The body was not printed and the file was not rewritten.
- `REAL_SESSION_SOURCE_ENABLEMENT = False` remains in the R.56 phase-6 gate and in the R.59, R.60, and R.61 gates.

## Expected hashes before the edit

All four matched. Editing began only after that check.

| File | SHA-256 | Result |
| --- | --- | --- |
| `forex_bot/positions.py` | `129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5` | MATCH, unchanged after R.70 |
| `forex_bot/reconciliation.py` | `f938807b59c2089767fdf69e4cf7d74671ffe62d74e5853169812ffe438a0bbf` | MATCH at baseline; this is the only operational file edited |
| `forex_bot/bot_loop.py` | `51023112554b2b6989ade50994a822aeb6e1968df58e513ad00ded820820ec51` | MATCH, unchanged |
| `forex_bot/broker_exit.py` | `bcdc3e04908208f8c397acb291eceae19fca5dc78028a6914269d409cc53474c` | MATCH, unchanged |

## Other operational files checked and left unchanged

| File | SHA-256 |
| --- | --- |
| `forex_bot/execution.py` | `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2` |
| `forex_bot/trading.py` | `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` |
| `forex_bot/live_manage.py` | `60d87b8665620743467832758032857e975d32da15322307a0c331009cc7b25d` |
| `forex_bot/oanda_exec.py` | `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8` |
| `forex_bot/profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| `forex_bot/app.py` | `1883d3c94a570b66782b7079bcd64d7657c83c0cd6faa385cab7a65bc2d56bd1` |
| `forex_bot/database.py` | `be83fc2a485af0f392203562a8286082587b0824f235557b6036e69f661f840d` |
| `main.py` | `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` |

## Final operational hash

| File | SHA-256 |
| --- | --- |
| `forex_bot/reconciliation.py` | `df67cc020986e0056b4bf3bea6fbbd9947090741cafa8793a4ac57660a0b9165` |

## What was not done

- `main.py`, `forex_bot.app`, and `run_bot` were not started.
- `.env` was not opened. The R.69 isolation harness stubs `load_dotenv` and refuses `.env` paths.
- No OANDA practice or live request was made.
- No PostgreSQL connection was opened. The harness raises on `psycopg2.connect`.
- No commit was created.
