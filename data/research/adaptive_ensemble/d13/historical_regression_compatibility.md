# Historical regression compatibility

Executed together, without the safety-repair module:

- D.2 `tests/test_live_safety_preservation.py`: 30 tests, included in 133 passed.
- D.3 `tests/test_strategy_activation_defaults.py`: 35 tests, included in 133 passed.
- D.4 `tests/test_startup_safety_preflight.py`: 50 tests, included in 133 passed.
- D.7 `tests/test_d7_resource_cleanup.py`: 18 tests, included in 133 passed in 11.57s.

Classification for D.2, D.3, D.4, and D.7: `EXECUTED_PASS`.

Safety-repair `tests/test_live_safety_repair.py`, run alone: 23 passed in 4.66s. Classification: `EXECUTED_PASS`.

Historical setup errors, 101 in 1.11s, all hash mismatches:

- D.5: 15 errors. Pins app.py `f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4`. `HISTORICAL_HASH_PIN_CONFLICT`.
- D.6: 12 errors. Same older app.py pin. `HISTORICAL_HASH_PIN_CONFLICT`.
- D.8: 7 errors. Pins the pre-D.9 database hash. `HISTORICAL_HASH_PIN_CONFLICT`.
- D.9: 6 errors. Pins the pre-D.13 app.py hash. `HISTORICAL_HASH_PIN_CONFLICT`.
- D.10: 8 plus 6 errors. Pins the pre-D.11 telegram hash. `HISTORICAL_HASH_PIN_CONFLICT`.
- D.11: 14 plus 17 errors. Pins the pre-D.13 app.py hash. `HISTORICAL_HASH_PIN_CONFLICT`.
- D.12: 7 plus 3 plus 6 errors. Pins the pre-D.13 app.py hash and asserts the old empty cleanup list. The hash check stops them before those assertions run. Classification: `HISTORICAL_HASH_PIN_CONFLICT` and `HISTORICAL_DEFECT_ASSERTION_CONFLICT`.

These conflicts are not passes. The historical tests were not edited.
