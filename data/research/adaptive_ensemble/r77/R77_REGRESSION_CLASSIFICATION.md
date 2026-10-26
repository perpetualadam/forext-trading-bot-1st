# R.77 regression classification

Historical tests were not edited.

## R.76

69 passed. Three failed. No errors after `run_startup_and_one_iteration` kept the production call `execute_startup_sequence(load_startup_broker_view())`.

| Test | Class | Reason |
| --- | --- | --- |
| `test_28_verified_identity_persisted_before_publication` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | It patches `entry_capture.persist_bot_position`. The success path now calls `_write_managed_position` inside `commit_verified_entry`. Publication is still after the durable commit, which R.77 tests 02 and 08 check. |
| `test_35_crash_after_position_commit_restores_on_startup` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | A durable position plus `ENTRY_CONFIRMED_SINGLE_TRADE` is now `unfinalised_capture` and is not published. |
| `test_36_crash_before_memory_publication_uses_the_durable_row` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Same fixture as test 35. A committed `ENTRY_FINALISED` row is still restored by R.77 test 09. |

`test_19` still receives `unresolved_entry_exists` for an in-flight duplicate. `test_37` in the R.76 file, which finalises and then reloads, stayed green.

## Earlier suites

| Suite | Class | Notes |
| --- | --- | --- |
| R.75 | Passed | 13 of 13. No new failure. |
| R.74 journal and operational | Passed | 20 and 9. Schema 4 is what new bootstraps create. |
| R.73 | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | 21 failures and 2 errors. The suite calls the guarded close without a journal, so the result is `missing_journal` / `CLOSE_NOT_REQUESTED`. The fill matcher was not edited. |
| R.72 | `HISTORICAL_HASH_PIN` | `test_operational_source_wiring_and_unchanged_files` still pins an older `positions.py` hash. Current hash `ac33eca30201f283369196f06e97ed34da343225a011348505f6e379fc71099c` matches the R.76 baseline. |
| R.71 | Passed | 8 of 8. |
| R.70 | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | `test_valid_then_incomplete_then_valid_empty_sequence`. `COMPLETE_EMPTY` keeps a durable live row. |
| R.69 | `HISTORICAL_HASH_PIN` and `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Hash pin on `positions.py`. Flat snapshot no longer drops the local row. `test_live_shape_reaches_quote_and_protection_without_close` waits on the recovery gate. Entry-tail skip remains `NOT_VERIFIED`. |
| R.68 | `OBSOLETE_BEHAVIOURAL_EXPECTATION`, `HISTORICAL_HASH_PIN`, `NOT_VERIFIED` | Symbol-only delete and `posmap.pop` scan are obsolete. `trading.py` hash pin remains. Concurrent interleaving skip remains `NOT_VERIFIED`. |

No failure in this run was classified `GENUINE_BEHAVIOURAL_REGRESSION`. No failure was classified `ENVIRONMENT_OR_DEPENDENCY_FAILURE` on Windows. The WSL SDK import is `ENVIRONMENT_OR_DEPENDENCY_FAILURE` for the operational path and is recorded as `LINUX_INTEGRATION_NOT_VERIFIED`.
