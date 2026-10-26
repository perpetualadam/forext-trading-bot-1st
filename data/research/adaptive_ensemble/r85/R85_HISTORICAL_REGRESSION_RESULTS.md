# R.85 Historical Regression Results

The R.84-stage expected counts are the comparison baseline. Historical test files were not modified.

| Suite | R.84-stage expectation | R.85 Windows | R.85 Linux | Class |
| --- | --- | --- | --- | --- |
| R.84 | 12 passed | 11 passed, 1 failed | same | Hash pin, `positions.py` |
| R.83 | 13 passed, 1 failed | 13 passed, 1 failed | same | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.82 | 18 passed, 1 failed | 18 passed, 1 failed | same | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.81 | 16 passed | 15 passed, 1 failed | same | Hash pin, `position_recovery.py` |
| R.80 | 17 passed | 17 passed | same | Preserved |
| R.79 | 17 passed | 17 passed | same | Preserved |
| R.78 | 21 passed | 21 passed | same | Preserved |
| R.77 atomic | 82 / 2 / 3 of 87 | same | same | `PRE_EXISTING_FAILURE` |
| R.77 journal | 0 / 1 / 1 of 2 | same | same | `PRE_EXISTING_FAILURE` |
| R.76 | 64 / 6 / 2 of 72 | same | same | `PRE_EXISTING_FAILURE` |
| R.75 | 10 / 3 of 13 | same | same | `PRE_EXISTING_FAILURE` |
| R.74 operational | 3 / 6 of 9 | same | same | `PRE_EXISTING_FAILURE` |
| R.74 journal | 20 passed | 20 passed | same | Preserved |
| R.73 | 8 / 21 / 2 of 31 | same | same | `PRE_EXISTING_FAILURE` |
| R.72 | 36 / 1 of 37 | same | same | `PRE_EXISTING_FAILURE` |
| R.71 | 8 passed | 8 passed | same | Preserved |
| R.70 | 25 / 1 of 26 | same | same | `PRE_EXISTING_FAILURE` |
| R.69 | 44 / 3 / 1 skipped of 48 | same | same | `PRE_EXISTING_FAILURE` |
| R.68 | 27 / 2 / 1 / 1 skipped of 31 | same | same | `PRE_EXISTING_FAILURE` |

No suite moved from a green count to a behavioural failure except the two hash pins, which fail because R.85 edited the files those tests hash. Those tests were not rewritten.

R.74 journal remaining green is the check that epoch-less `finalise` still records local deletion. The epoch-conditional path is the R.85 addition and is covered by the R.85 race tests.

There was no `ENVIRONMENT_FAILURE` and no `UNDETERMINED` count change. The obsolete R.82 and R.83 failures are not regressions.
