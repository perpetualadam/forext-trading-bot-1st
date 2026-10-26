# R.84 Windows test results

Platform: Windows. CPython 3.13.5.

## R.84

Command: `python -B data/research/adaptive_ensemble/r84/poc/test_r84_close_contract.py`

| Item | Result |
| --- | --- |
| Exit code | 0 |
| Passed | 12 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Runtime | 13.314 seconds |

## Historical sweep

| Suite | Passed | Failed | Errors | Skipped | Runtime |
| --- | --- | --- | --- | --- | --- |
| R.83 | 13 | 1 | 0 | 0 | 15.365s of 14 |
| R.82 | 18 | 1 | 0 | 0 | 13.512s of 19 |
| R.81 | 16 | 0 | 0 | 0 | 27.620s |
| R.80 | 17 | 0 | 0 | 0 | 13.191s |
| R.79 | 17 | 0 | 0 | 0 | 4.853s |
| R.78 | 21 | 0 | 0 | 0 | 2.391s |
| R.77 atomic | 82 | 2 | 3 | 0 | 7.178s of 87 |
| R.77 journal | 0 | 1 | 1 | 0 | 0.305s of 2 |
| R.76 | 64 | 6 | 2 | 0 | 12.898s of 72 |
| R.75 | 10 | 3 | 0 | 0 | 8.240s of 13 |
| R.74 operational | 3 | 6 | 0 | 0 | 0.680s of 9 |
| R.74 journal | 20 | 0 | 0 | 0 | 1.949s |
| R.73 | 8 | 21 | 2 | 0 | 5.078s of 31 |
| R.72 | 36 | 1 | 0 | 0 | 0.063s of 37 |
| R.71 | 8 | 0 | 0 | 0 | 0.003s |
| R.70 | 25 | 1 | 0 | 0 | 7.683s of 26 |
| R.69 | 44 | 3 | 0 | 1 | 4.556s of 48 |
| R.68 | 27 | 2 | 1 | 1 | 0.179s of 31 |

The new R.83 failure is `test_13_closed_unit_contract` at the assertion that `tradesClosed` units `"-100"` with fill units `"-100"` must raise. The new R.82 failure is `test_16_unit_validation_matrix` at the same assertion. The assertions before those lines in each test passed, including the positive 400, 999, and 1,000 cases.
