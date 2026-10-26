# R.76 test results

All commands used `python -B` on an isolated file. Repository-wide pytest was not used.

## Windows

| Suite | Result |
| --- | --- |
| R.76 `test_r76_entry_recovery.py` | 72 passed |
| R.75 `test_r75_guard_and_recovery.py` | 13 passed |
| R.74 `test_r74_journal.py` | 20 passed |
| R.74 `test_r74_close_recovery.py` | 9 passed |
| R.71 `test_r71_readonly_calculations.py` | 8 passed |
| R.72 `test_r72_broker_protection.py` | 36 passed, 1 failed |
| R.70 `test_r70_snapshot.py` | 25 passed, 1 failed |
| R.68 `test_r68_observation_boundary.py` | 27 passed, 2 failed, 1 error, 1 skipped |
| R.69 `test_r69_integration.py` | 44 passed, 3 failed, 1 skipped |
| R.73 `test_r73_close_evidence.py` | 8 passed, 21 failed, 2 errors |

The historical suites are not green. Classifications are in `R76_REGRESSION_CLASSIFICATION.md`.

## Linux / WSL

CPython 3.12.3.

| Check | Result |
| --- | --- |
| `import oandapyV20` | `ModuleNotFoundError` |
| R.74 journal | 20 passed |
| R.71 | import stops in `forex_bot/reconciliation.py` at `oandapyV20.endpoints.positions` |
| R.76 suite | import stops in `forex_bot/oanda_client.py` line 13 |
| R.75 operational import | not run as a green suite; the same `oandapyV20` import blocks it |

No dependency was installed. `LINUX_INTEGRATION_NOT_VERIFIED` remains for the operational path. The WSL journal result is not operational Linux verification.

No OANDA host was contacted. No PostgreSQL connection was opened. Temporary SQLite files were used and removed by the tests.
