# R.85 Linux Test Results

Platform: Linux via the existing disposable R.79 virtualenv. CPython 3.12.3 (`GCC 13.3.0`). `TMPDIR=/tmp`. No packages were installed. Log: `R85_LINUX_REGRESSION.log`. Started 2026-10-26T13:13:15Z.

| Suite | Result | Elapsed seconds | Classification |
| --- | --- | --- | --- |
| R.85 | 48 passed | 16.419 | PASS |
| R.84 | 11 passed, 1 failed of 12 | 12.606 | Hash pin on `positions.py` |
| R.83 | 13 passed, 1 failed of 14 | 16.155 | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.82 | 18 passed, 1 failed of 19 | 15.567 | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.81 | 15 passed, 1 failed of 16 | 27.077 | Hash pin on `position_recovery.py` |
| R.80 | 17 passed | 14.654 | Preserved |
| R.79 | 17 passed | 6.876 | Preserved |
| R.78 | 21 passed | 4.245 | Preserved |
| R.77 atomic | 82 passed, 2 failed, 3 errors of 87 | 16.626 | `PRE_EXISTING_FAILURE` |
| R.77 journal | 0 passed, 1 failed, 1 error of 2 | 1.039 | `PRE_EXISTING_FAILURE` |
| R.76 | 64 passed, 6 failed, 2 errors of 72 | 21.682 | `PRE_EXISTING_FAILURE` |
| R.75 | 10 passed, 3 failed of 13 | 9.348 | `PRE_EXISTING_FAILURE` |
| R.74 operational | 3 passed, 6 failed of 9 | 2.238 | `PRE_EXISTING_FAILURE` |
| R.74 journal | 20 passed | 2.760 | Preserved |
| R.73 | 8 passed, 21 failed, 2 errors of 31 | 6.066 | `PRE_EXISTING_FAILURE` |
| R.72 | 36 passed, 1 failed of 37 | 1.311 | `PRE_EXISTING_FAILURE` |
| R.71 | 8 passed | 1.230 | Preserved |
| R.70 | 25 passed, 1 failed of 26 | 8.679 | `PRE_EXISTING_FAILURE` |
| R.69 | 44 passed, 3 failed, 1 skipped of 48 | 6.098 | `PRE_EXISTING_FAILURE` |
| R.68 | 27 passed, 2 failed, 1 error, 1 skipped of 31 | 0.398 | `PRE_EXISTING_FAILURE` |

The Linux counts match the Windows counts. The R.84 and R.81 failures are the same hash pins. The R.83 and R.82 failures are the same obsolete negative-unit assertions.

Coverage of the R.85 scenarios is equivalent across the two interpreters. Linux did not reveal an additional failure.
