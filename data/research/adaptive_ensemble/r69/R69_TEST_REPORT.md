# R.69 test report

## Command

```text
python -B data/research/adaptive_ensemble/r69/poc/test_r69_integration.py
```

Windows CPython 3.13.5: `Ran 48 tests in 5.395s`, `OK (skipped=1)`.

The skip is `test_entry_tail_was_not_executed`: `NOT_VERIFIED`. The production entry tail was not run.

Existing R.68 suite, same machine:

```text
python -B data/research/adaptive_ensemble/r68/poc/test_r68_observation_boundary.py
```

`Ran 31 tests in 0.171s`, `OK (skipped=1)`. The skip remains the concurrent case from R.68. R.69 covers that case with threads.

## Not run

`tests/test_reconcile_conflict.py`, `tests/test_execution_safety.py`, and `tests/test_live_position_management.py`. Their import path loads the real config module. Classification is in `R69_LEGACY_TEST_REVIEW.md`.

No `main.py`, `forex_bot.app`, or `run_bot`.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

`POSTGRESQL_INTEGRATION_NOT_TESTED`
