# R.72 Baseline and Integrity

Checked before operational edits.

| Item | Result |
| --- | --- |
| Commit | `d080d897945bc44fa37c02caab504ed707146bec` |
| Branch | `main` |
| Dirty-tree lines before edits | 276 |
| Permit files | none |
| Consumed marker | `data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.consumed`, 10 bytes, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c` |
| Windows | CPython 3.13.5 |
| WSL | CPython 3.12.3. `oandapyV20`, `pandas`, `numpy`, and `psycopg2` absent. `requests` present. Nothing installed. |

Expected hashes matched before edits:

| File | SHA-256 |
| --- | --- |
| `forex_bot/positions.py` | `129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5` |
| `forex_bot/reconciliation.py` | `df67cc020986e0056b4bf3bea6fbbd9947090741cafa8793a4ac57660a0b9165` |
| `forex_bot/bot_loop.py` | `51023112554b2b6989ade50994a822aeb6e1968df58e513ad00ded820820ec51` |
| `forex_bot/broker_exit.py` | `bcdc3e04908208f8c397acb291eceae19fca5dc78028a6914269d409cc53474c` |
| `forex_bot/profit_protection.py` | `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| `forex_bot/trading.py` | `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` |
| `forex_bot/live_manage.py` | `60d87b8665620743467832758032857e975d32da15322307a0c331009cc7b25d` |
| `forex_bot/oanda_exec.py` | `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8` |
| `main.py` | `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` |

`R72_BASELINE_VERIFIED`

After R.72, `bot_loop.py` and `live_manage.py` hashes changed because those files were edited. The other eight hashes above still match. `positions.py` and `reconciliation.py` remain dirty relative to git HEAD from R.68 and R.70. Their bytes were not edited in R.72.

Source gates still assign `REAL_SESSION_SOURCE_ENABLEMENT = False` in the R.56 phase 6, R.59, R.60, and R.61 gate files. No permit was created. The consumed marker hash is unchanged. No commit was made.
