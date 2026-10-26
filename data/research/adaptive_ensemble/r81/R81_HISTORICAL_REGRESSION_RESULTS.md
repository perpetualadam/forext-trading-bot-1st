# R.81 historical regression results

Windows CPython 3.13.5, after the R.81 edit. Historical files were not modified. Suites with failures are not green. The totals match the R.80 rerun. None of these failures is a new genuine behavioural regression.

| Suite | Ran | Result |
| --- | --- | --- |
| R.81 | 16 | 16 passed |
| R.80 | 17 | 17 passed |
| R.79 | 17 | 17 passed |
| R.78 | 21 | 21 passed |
| R.77 | 87 | 2 failed, 3 errors |
| R.76 | 72 | 6 failed, 2 errors |
| R.75 | 13 | 3 failed |
| R.74 journal | 20 | 20 passed |
| R.74 operational | 9 | 6 failed |
| R.73 | 31 | 21 failed, 2 errors |
| R.72 | 37 | 1 failed |
| R.71 | 8 | 8 passed |
| R.70 | 26 | 1 failed |
| R.69 | 48 | 3 failed, 1 skipped |
| R.68 | 31 | 2 failed, 1 error, 1 skipped |

The R.74 operational failures remain the old tests that close without recovery authority. `test_11`, `test_12`, and `test_14` are the R.81 replacements for rejection, partial close, and flat-snapshot confirmation. The R.75, R.76, and R.77 failures that appeared when recovery fencing was added stay obsolete and keep the R.80 mappings, with the fresh-process and crash rows added above.

`R81_HISTORICAL_COVERAGE_IMPROVED`: PASS.
