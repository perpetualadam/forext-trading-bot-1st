# R.74 Test Matrix

Journal suite: `data/research/adaptive_ensemble/r74/poc/test_r74_journal.py`.

Operational suite: `data/research/adaptive_ensemble/r74/poc/test_r74_close_recovery.py`.

Worker: `data/research/adaptive_ensemble/r74/poc/journal_worker.py`.

| # | Scenario | Test |
| --- | --- | --- |
| 1 | Two threads, one reservation | `test_two_threads_one_reservation` |
| 2 | Two processes, one reservation | `test_two_processes_one_reservation` |
| 3 | Two symbols | `test_two_symbols_reserve_independently` |
| 4 | Crash before reservation commit | `test_crash_before_reserve_commit_writes_nothing` |
| 5–6 | Crash after reservation, before intent | `test_restart_after_reserve_blocks_without_submission` |
| 7–12 | Crash after intent, including response not yet durable | `test_restart_after_intent_is_ambiguous_and_not_retried`, `test_fault_after_intent_does_not_submit` |
| 13–14 | Confirmation committed, restart | `test_identity_delete_removes_only_the_matching_row` after reopen is covered by partial/full recovery tests |
| 15–17 | Delete and finalise windows | `test_delete_then_failed_finalise_does_not_match_a_new_row` |
| 18 | Corrupt journal | `test_missing_corrupt_and_schema_fail_closed` |
| 19 | Missing journal | same, plus `test_missing_and_unauthorised_journal_do_not_submit` |
| 20 | Unsupported schema | `test_missing_corrupt_and_schema_fail_closed` |
| 21 | Lock failure | `test_lock_and_disk_failure` |
| 22 | Persistence failure before commit | `test_lock_and_disk_failure` fault `before_commit` |
| 23–30 | Wrong trade, instance, account, direction, units, generation, replacement | `test_identity_delete_refuses_a_different_row`, `test_changed_units_generation_direction_and_account_refuse` |
| 31 | Partial fill | `test_partial_fill_keeps_row_and_blocks_resubmit`, `test_partial_recovery_keeps_units_and_blocks` |
| 32 | Ambiguous timeout | `test_timeout_blocks_resubmit_across_process_reopen` |
| 33 | Confirmed rejection | `test_rejection_can_reserve_a_new_operation` |
| 34 | Valid empty snapshot | `test_flat_snapshot_and_open_trade_do_not_confirm` |
| 35 | Incomplete snapshot | same test, `BrokerSnapshotError` classification `INCOMPLETE` |
| 36 | Broker-flat without attribution | same test, result `retained` |
| 37 | Observation-only | `test_observation_is_not_submitted`, `test_observation_and_partial_rows_are_not_deleted` |
| 38 | Restart with unresolved intent | `test_subprocess_restart_keeps_intent` |
| 39 | Restart with full confirmation | identity delete tests and recovery status `recovered_confirmed_delete_not_assumed` |
| 40 | Restart with partial confirmation | `test_partial_recovery_keeps_units_and_blocks` |
| 41 | Two SQLite connections | `test_lock_and_disk_failure` and the two-process test |
| 42 | Stale token after the stored owner changes | `test_stale_token_is_not_authorised` |

Broker calls in the operational suite use `FakeAPI`. Non-close endpoint names raise `IsolationBreach`. No test loads `.env` or opens a permit.
