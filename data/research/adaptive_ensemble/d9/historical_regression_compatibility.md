# D.9 historical regression compatibility

| Module | Status |
| --- | --- |
| D.2 `tests/test_live_safety_preservation.py` | Executed. Passed. Included in 133 passed in 9.83s. |
| D.3 `tests/test_strategy_activation_defaults.py` | Executed. Passed. Same run. |
| D.4 `tests/test_startup_safety_preflight.py` | Executed. Passed. Same run. |
| D.5 `tests/test_d5_lifespan_isolation.py` | Executed. Hash-pin blocked. 15 fixture errors. Expected app.py `f38c304c...`, actual `08766300...`. Not a pass. File not edited. |
| D.6 `tests/test_d6_partial_startup_cleanup.py` | Executed. Hash-pin blocked. 12 fixture errors. Same app.py pin. Not a pass. File not edited. |
| D.7 `tests/test_d7_resource_cleanup.py` | Executed. Passed. It asserts `database.py` differs from the pre-D.7 hash, not that it equals the D.8 hash. |
| D.8 `tests/test_d8_database_concurrency.py` | Executed. Expected historical defect assertion conflict. 7 fixture errors. It pins database.py to `74bb9f5d...`. Actual is `cf978bfa...`. Those tests also assert the abandoned connection. They were not edited and are not post-fix acceptance tests. |
| `tests/test_live_safety_repair.py` | Executed through the D.7 repair test in the 133 passed. D.9 did not add a repair mode and did not wrap order routing. |

D.5 and D.6 together with D.8: 34 errors in 0.28s. Full historical regression compatibility is not claimed.
