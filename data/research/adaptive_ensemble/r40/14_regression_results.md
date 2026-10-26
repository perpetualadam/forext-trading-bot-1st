# R.40 tests and regressions

`tests/test_r40_timeframes.py`: 6 passed. The tests cover H1 open/high/low/close and volume aggregation, rejection of a missing constituent, rejection of a source bar flagged incomplete, H4 alignment at 00:00 UTC, rejection of a series shifted by five minutes, an as-of read that hides the unfinished hour, prefix stability of the first H1 candle, the local pip rule, inactive strategy flags, and the absence of the aggregator from `bot_loop.py`.

Offline R.8–R.39 suites, plus the R.40 file, all exited 0 on the first attempt. `WinError 5` did not occur. R.28 PostgreSQL scripts were not run. No safety assertion was weakened.

| Suite | Result |
| --- | --- |
| R.40 | 6 passed |
| R.39 | 9 passed |
| R.38 | 9 passed |
| R.37 | 7 passed |
| R.36 | 10 passed |
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
