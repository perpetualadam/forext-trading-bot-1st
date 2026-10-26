# R.80 historical regression results

Evidence class: executed Windows suites after the `oanda_exec.py` recheck. Historical files were not edited. Suites with failures are not green.

Command form: `python -B data/research/adaptive_ensemble/rNN/poc/test_....py`

| Suite | Ran | Passed | Failed | Errors | Skipped | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| R.79 | 17 | 17 | 0 | 0 | 0 | preserved |
| R.78 | 21 | 21 | 0 | 0 | 0 | preserved |
| R.77 | 87 | 82 | 2 | 3 | 0 | same totals as the R.79 rerun. New failures are `OBSOLETE_BEHAVIOURAL_EXPECTATION` and are mapped in the inventory. Schema-4 cases remain `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.76 | 72 | 64 | 6 | 2 | 0 | same totals. The three new authority failures are obsolete and mapped. Tests 35–37 were already obsolete |
| R.75 | 13 | 10 | 3 | 0 | 0 | the three failures are obsolete and mapped to `test_01` and `test_12` |
| R.74 journal | 20 | 20 | 0 | 0 | 0 | preserved |
| R.74 operational | 9 | 3 | 6 | 0 | 0 | obsolete close-without-recovery. Coverage is partial because the rejection re-reserve case was not rebuilt |
| R.73 | 31 | 8 | 21 | 2 | 0 | unchanged totals. Pre-existing obsolete expectations |
| R.72 | 37 | 36 | 1 | 0 | 0 | `HISTORICAL_HASH_PIN` on `positions.py` |
| R.71 | 8 | 8 | 0 | 0 | 0 | preserved |
| R.70 | 26 | 25 | 1 | 0 | 0 | pre-existing failure, not a new R.80 regression |
| R.69 | 48 | 44 | 3 | 0 | 1 | pre-existing |
| R.68 | 31 | 27 | 2 | 1 | 1 | pre-existing |

`R80_HISTORICAL_TESTS_UNCHANGED`: PASS.
`R80_R77_COVERAGE_RESTORED`: PASS for the tests that changed between R.78 and R.79. The historical file still fails.
`R80_R76_COVERAGE_RESTORED`: PASS on the same basis.
`R80_R75_COVERAGE_RESTORED`: PASS. The three failed tests map to executed R.80 tests.
`R80_R74_COVERAGE_RESTORED`: PARTIAL. One-close, timeout, and two-process coverage were rebuilt. `test_rejection_can_reserve_a_new_operation` is `MISSING_COVERAGE`.

No failure in this rerun is classified `GENUINE_BEHAVIOURAL_REGRESSION`.
