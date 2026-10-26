# R.41 tests and regressions

`tests/test_r41_structure.py`: 6 passed. The functions cover source-hash verification, H1 and H4 alignment, incomplete buckets, swing confirmation delay, ties, gaps, higher and lower structure, trend states, trendline timing and versions, weekend slope, touch and break causality, level availability, fail-closed ranges, prefix invariance, as-of joins, the dataset end, null trading fields, inactive strategies, and the fail-closed stub and reinforcement-learning gate.

Offline R.8–R.40 suites, plus R.41, all exited 0 on the first attempt. `WinError 5` did not occur. There were no retries. R.28 PostgreSQL scripts were not run.

| Suite | Result |
| --- | --- |
| R.41 | 6 passed |
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
