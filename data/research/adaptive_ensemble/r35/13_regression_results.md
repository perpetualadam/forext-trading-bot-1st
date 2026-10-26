# Focused tests and regressions

R.35 focused tests: 10 passed.

Legacy stub files, after cleanup: 55 passed. The first run failed 3 tests that still patched `bot_loop.fetch_ohlcv`. Those patches were retired. The rerun passed. No assertion was changed to hide a safety failure.

Full offline run, every suite exit 0. `WinError 5` did not recur. R.28 PostgreSQL scripts were not run.

| Suite | Result |
| --- | --- |
| R.35 | 10 passed |
| Legacy stub files | 55 passed |
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
| R.10 | 69 passed, 5 skipped |
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
