# R.85 Windows Test Results

Platform: Windows. CPython 3.13.5 (`MSC v.1943 64 bit`). Command form: `python -B` on each research module. Log: `R85_WINDOWS_REGRESSION.log`. Started 2026-10-26T13:13:03Z.

| Suite | Result | Elapsed seconds | Classification |
| --- | --- | --- | --- |
| R.85 | 48 passed | 18.689 | PASS |
| R.84 | 11 passed, 1 failed of 12 | 12.838 | Hash pin on `positions.py` |
| R.83 | 13 passed, 1 failed of 14 | 18.054 | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.82 | 18 passed, 1 failed of 19 | 15.585 | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.81 | 15 passed, 1 failed of 16 | 31.052 | Hash pin on `position_recovery.py` |
| R.80 | 17 passed | 15.745 | Preserved |
| R.79 | 17 passed | 6.543 | Preserved |
| R.78 | 21 passed | 2.508 | Preserved |
| R.77 atomic | 82 passed, 2 failed, 3 errors of 87 | 8.532 | `PRE_EXISTING_FAILURE` |
| R.77 journal | 0 passed, 1 failed, 1 error of 2 | 0.617 | `PRE_EXISTING_FAILURE` |
| R.76 | 64 passed, 6 failed, 2 errors of 72 | 14.596 | `PRE_EXISTING_FAILURE` |
| R.75 | 10 passed, 3 failed of 13 | 8.550 | `PRE_EXISTING_FAILURE` |
| R.74 operational | 3 passed, 6 failed of 9 | 1.925 | `PRE_EXISTING_FAILURE` |
| R.74 journal | 20 passed | 2.315 | Preserved |
| R.73 | 8 passed, 21 failed, 2 errors of 31 | 6.402 | `PRE_EXISTING_FAILURE` |
| R.72 | 36 passed, 1 failed of 37 | 1.196 | `PRE_EXISTING_FAILURE` |
| R.71 | 8 passed | 1.469 | Preserved |
| R.70 | 25 passed, 1 failed of 26 | 8.863 | `PRE_EXISTING_FAILURE` |
| R.69 | 44 passed, 3 failed, 1 skipped of 48 | 6.066 | `PRE_EXISTING_FAILURE` |
| R.68 | 27 passed, 2 failed, 1 error, 1 skipped of 31 | 0.335 | `PRE_EXISTING_FAILURE` |

R.84 `test_01_baseline_gates_and_unchanged_modules` failed because `positions.py` is now `afd62ac98c593ee8d75871c12b421d489061b84113724923cdb6f4950edfe36a`. The other 11 R.84 tests passed, including the close-contract behaviour.

R.81 `test_01_gates_marker_and_unchanged_recovery_files` failed because `position_recovery.py` is now `decab95661526606038856ad1a99b71c54897473bd7120cfa384a8d01db910a3`. The other 15 tests passed.

R.83 `test_13_closed_unit_contract` and R.82 `test_16_unit_validation_matrix` still expect `CloseReadError` for a negative fill with a negative reduction. That expectation was superseded by R.84. The files were not edited.

No historical suite was classified green if it still failed. No new behavioural failure count appeared outside the two hash pins.
