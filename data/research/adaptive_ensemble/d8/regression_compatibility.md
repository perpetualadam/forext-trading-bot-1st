# D.8 regression compatibility

| Module | Result | How to read it |
| --- | --- | --- |
| D.2 `tests/test_live_safety_preservation.py` | PASS | Included in 133 passed in 9.96s |
| D.3 `tests/test_strategy_activation_defaults.py` | PASS | Same run |
| D.4 `tests/test_startup_safety_preflight.py` | PASS | Same run |
| D.5 `tests/test_d5_lifespan_isolation.py` | HISTORICAL_HASH_PIN_CONFLICT | 15 fixture errors. Expected app.py `f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4`, actual `08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44`. Not counted as a pass. File not edited. |
| D.6 `tests/test_d6_partial_startup_cleanup.py` | HISTORICAL_HASH_PIN_CONFLICT | 12 fixture errors, same hash mismatch. Those tests also still expect the pre-D.7 leaks. They were not given a bypass. Not counted as a pass. |
| D.7 `tests/test_d7_resource_cleanup.py` | PASS | Included in the 133. Hash pins were not weakened. |
| Safety-repair module | PASS through the existing D.7 test | D.8 did not add a repair mode and did not wrap order-routing functions. The D.7 module that launches the repair tests under its own guards passed in this stage. |

D.5 and D.6 together: 27 errors in 0.25 seconds. Equivalent current-source checks are the D.8 lifespan cases: corrupt abort before connect, valid BLOCKED startup, broker failure closes the connection, stop failure still cleans tasks, task-await failure still cleans the other tasks, and a repeated startup stays BLOCKED.

Full historical regression compatibility is not claimed. The historical modules were not executed past their hash pins.
