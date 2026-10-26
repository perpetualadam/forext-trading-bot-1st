# R.86 Historical Regression Results

No historical test file was edited. Counts below are from the Windows and Linux logs in this stage. They match the R.85 baseline.

| Suite | Classification | Evidence |
| --- | --- | --- |
| R.86 | Current stage, 58 passed | New module and tests |
| R.85 | Preserved, 48 passed | No failure |
| R.84 `test_01_baseline_gates_and_unchanged_modules` | `HISTORICAL_SOURCE_HASH_ASSERTION` | Pins an older `positions.py` digest |
| R.83 `test_13_closed_unit_contract` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Expects the pre-R.84 negative-unit rejection |
| R.82 `test_16_unit_validation_matrix` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Same superseded signed-unit expectation |
| R.81 `test_01_gates_marker_and_unchanged_recovery_files` | `HISTORICAL_SOURCE_HASH_ASSERTION` | Pins an older `position_recovery.py` digest |
| R.80, R.79, R.78 | Preserved, all passed | No failure |
| R.77 through R.68 | `PRE_EXISTING_FAILURE` | Same counts as the R.85 sweep |

No failure in this sweep is `NEW_REGRESSION`. The older suites were not relabelled as green.

R.84 signed-unit parsing was not modified. `broker_close_evidence.py` remains `2f01fed308a3bf2f111b2bfad8a8610d45ec6bac92264c46877f08d7efd73bc8`.
