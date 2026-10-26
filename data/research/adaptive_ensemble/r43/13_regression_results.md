# R.43 tests and regressions

No new production module was added. No acquisition client was implemented or run. No trading code was run. R.28 PostgreSQL scripts were not run. Safeguard assertions were not weakened.

## First offline run

Every suite except R.10 exited 0.

| Suite | Result |
| --- | --- |
| R.42 | 5 passed |
| R.41 | 6 passed |
| R.40 | 6 passed |
| R.39 | 9 passed |
| R.38 | 9 passed |
| R.37 | 7 passed |
| R.36 | 10 passed |
| R.35 | 10 passed |
| Legacy | 55 passed |
| R.34 | 5 passed |
| R.33 | 4 passed |
| R.32 | 10 passed |
| R.31 | 7 passed |
| R.30 | 13 passed |
| R.29 | 8 passed |
| R.27 | 10 passed |
| R.26 | 9 passed |
| R.25 | 10 passed |
| R.4–R.9 | 120 passed, 7 skipped, 1 deselected |
| R.10 attempt 1 | 1 failed, 68 passed, 5 skipped |
| R.11 | 51 passed, 5 skipped |
| R.12 | 118 passed, 5 skipped |
| R.13 | 81 passed, 6 skipped |
| R.14 | 143 passed, 5 skipped |
| R.15 | 165 passed, 6 skipped |
| R.16 | 135 passed, 6 skipped |
| R.17 | 174 passed, 9 skipped |
| R.18 | 203 passed, 9 skipped |
| R.19 | 213 passed, 9 skipped |
| R.20 | 30 passed |
| R.21 | 24 passed |
| R.22 | 20 passed |
| R.23 | 15 passed |
| R.24 | 14 passed |

## R.10 retry

Attempt 1 failed in `tests/test_r10_offline_startup.py` at the recovery assertion. The log recorded `WinError 5` while replacing `data/research/adaptive_ensemble/r10/synthetic_live_safety_state.json`. The observed error was `StartupSafetyAbort` where the test expected `OrderRecoveryUnreadable`. `live_safety.py` was not edited and the JSON file was not deleted.

Attempt 2, run separately: 69 passed, 5 skipped.

Both attempts are in `pytest_r10_attempts.txt`.
