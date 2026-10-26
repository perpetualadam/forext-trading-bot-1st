# Stage D.6 regression compatibility

| Module | Result | Notes |
| --- | --- | --- |
| D.2 `tests/test_live_safety_preservation.py` | 30 passed | Does not import `app.py`. |
| D.3 `tests/test_strategy_activation_defaults.py` | 35 passed | Does not import `app.py`. |
| D.4 `tests/test_startup_safety_preflight.py` | 50 passed | Static and component checks. Does not execute lifespan. |
| D.5 `tests/test_d5_lifespan_isolation.py` | 15 passed | D.5 files were not edited. Hashes unchanged. |
| Repair `tests/test_live_safety_repair.py` | 23 passed inside the D.6 guard | Not part of the parent 142. |

No existing assertion was weakened. No production source was edited.

Remaining gap: the full suite was not run.
