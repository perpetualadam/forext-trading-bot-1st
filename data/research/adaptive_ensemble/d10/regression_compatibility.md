# Regression compatibility

Historical modules were not edited. Hash pins were not bypassed. A hash-pin error is not a pass.

| Module | Result | Detail |
| --- | --- | --- |
| D.2 `test_live_safety_preservation.py` | EXECUTED_PASS | Included in the clean run of 139 passed. |
| D.3 `test_strategy_activation_defaults.py` | EXECUTED_PASS | Included in the 139. An earlier combined process failed T34 because `test_live_safety_repair.py` had imported `forex_bot.database` at collection. The isolated rerun passed. |
| D.4 `test_startup_safety_preflight.py` | EXECUTED_PASS | Included in the 139. The same contaminated process failed four import checks. The isolated rerun passed. |
| D.5 `test_d5_lifespan_isolation.py` | HISTORICAL_HASH_PIN_CONFLICT | 15 errors. Expected app.py `f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4`. Actual `08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44`. |
| D.6 `test_d6_partial_startup_cleanup.py` | HISTORICAL_HASH_PIN_CONFLICT | 12 errors. Same app.py pin. The old leak assertions were not reached. |
| D.7 `test_d7_resource_cleanup.py` | EXECUTED_PASS | Included in the 139. |
| D.8 `test_d8_database_concurrency.py` | HISTORICAL_HASH_PIN_CONFLICT | 7 errors. Expected database.py `74bb9f5d692ace88bff525f334d7eb8577427bfe75cf5f229f647e60b88979e9`. Actual `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e`. The pre-fix defect assertions were not reached and are not a post-fix pass. |
| D.9 `test_d9_database_concurrency_remediation.py` | EXECUTED_PASS | Included in the 139. |
| `test_live_safety_repair.py` | EXECUTED_PASS | 23 passed in its own process. |

Clean command: 139 passed in 12.63s.

Not run: the full suite, real PostgreSQL, Telegram, OANDA, Docker, and production lifespan outside the isolated child.

D.10 tests: 14 passed in 10.17s. Ruff check of the three new test files passed.
