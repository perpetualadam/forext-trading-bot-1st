# R.75 Test Results

Host: Windows 10, CPython 3.13. Command form: `python -B <file>`. Pytest was not used.

## R.75

`data/research/adaptive_ensemble/r75/poc/test_r75_guard_and_recovery.py`

13 tests, 13 passed, about 6.9 seconds.

Passed names:

- `test_legacy_helpers_refuse_before_position_close`
- `test_stale_and_repeat_permit_do_not_submit`
- `test_journal_failures_refuse_submission`
- `test_unacknowledged_and_preexisting_do_not_submit`
- `test_journal_update_fault_does_not_submit`
- `test_two_processes_submit_once_through_the_guard`
- `test_process_paused_after_claim_blocks_the_other`
- `test_recovery_matrix`
- `test_missing_protection_and_unknown_origin_are_quarantined`
- `test_replaced_row_is_not_overwritten`
- `test_persist_then_restart_restores_the_same_identity`
- `test_duplicate_trade_is_refused`
- `test_restart_cases_stay_closed`

## R.74 after the R.75 edits

| Suite | Windows | WSL |
| --- | --- | --- |
| `test_r74_journal.py` | 20 passed | 20 passed |
| `test_r74_close_recovery.py` | 9 passed | not run: `oandapyV20` missing |
| `test_r75_guard_and_recovery.py` | 13 passed | import failed at `oanda_client.py:13` |

## Historical suites on Windows

| Suite | Result |
| --- | --- |
| R.71 `test_r71_readonly_calculations.py` | 8 passed |
| R.72 `test_r72_broker_protection.py` | 36 passed, 1 failed |
| R.70 `test_r70_snapshot.py` | 25 passed, 1 failed |
| R.68 `test_r68_observation_boundary.py` | 27 passed, 2 failed, 1 error, 1 skipped |
| R.69 `test_r69_integration.py` | 45 passed, 2 failed, 1 skipped |
| R.73 `test_r73_close_evidence.py` | 8 passed, 21 failed, 2 errors |

Classifications are in `R75_REGRESSION_CLASSIFICATION.md`. Historical tests were not edited.

## Isolation

R.69 `isolation.py` SHA-256 `b5dd110f37447fcb78e533a0cae216abec412ba3de2b7bd5beaf44543da06b54`, size 5126. It was imported before `forex_bot` in the R.75 tests and in the worker.
