# R.77 test matrix

Windows file: `data/research/adaptive_ensemble/r77/poc/test_r77_atomic_entry.py`. Each row below has an assertion in that file. Combined rows share one method and still assert both outcomes. Result for every row: passed on Windows. Broker submission count was 0 except test 25, which recorded one synthetic `OrderCreate` and no `PositionClose`.

| Cases | Method | Evidence |
| --- | --- | --- |
| 1 | `test_01_confirmed_single_trade_finalises` | Final entry, one position, memory published |
| 2 | `test_02_entry_and_position_share_one_commit` | One `_commit` |
| 3, 6 | `test_03` and `test_06` | Fault rolls back both rows |
| 4, 15 | `test_04` and `test_15` | Generation conflict keeps the old row and the unfinalised entry |
| 5 | `test_05_crash_before_transaction_leaves_intent` | `ENTRY_SUBMITTING`, no position |
| 7, 8 | `test_07` and `test_08` | Commit without memory publication |
| 9, 10 | `test_09_and_10_restart_after_commit_restores_memory` | Reopen restores |
| 11 | `test_11_restart_after_rollback_does_not_publish` | Ambiguous, no position, id retained |
| 12 | `test_12_repeated_finalisation_does_not_move_ratchet` | Exit pips stay 3.5 |
| 13 | `test_13_conflicting_trade_id_refuses_second_finalisation` | `duplicate_position_identity` |
| 14 | `test_14_conflicting_position_instance_refuses` | Original trade id kept |
| 16, 17 | `test_16`, `test_17` | Missing stop or take profit |
| 18 | `test_18_missing_protection_state_quarantines_on_startup` | `missing_management_state` |
| 19 | `test_19_partial_fill_is_not_published` | Partial, no position |
| 20 | `test_20_multiple_opened_trades_are_not_published` | Multiple trades |
| 21 | `test_21_existing_trade_reduction_is_not_published` | Reduction |
| 22 | `test_22_existing_trade_closure_is_not_published` | Existing close |
| 23 | `test_23_ambiguous_broker_response_is_not_finalised` | Ambiguous |
| 24 | `test_24_missing_fill_transaction_is_not_finalised` | Missing fill |
| 25 | `test_25_journal_write_failure_after_synthetic_submit_stays_ambiguous` | One synthetic create, then ambiguous |
| 26 | `test_26_journal_lock_timeout_refuses_reservation` | `journal_lock_or_disk` |
| 27 | `test_27_corrupt_journal_fails_closed` | `corrupt_journal` |
| 28 | `test_28_unsupported_schema_fails_closed` | Version 3 refused |
| 29, 75 | `test_29` and `test_75` | Partial R.76 states quarantined |
| 30 | `test_30_duplicate_durable_position_identity_refuses` | Second trade id refused |
| 31–36 | `test_31` through `test_36` | New id accepted; duplicates refused |
| 37 | `test_37_duplicate_id_across_two_processes` | Overlapping processes, one row |
| 38 | `test_38_same_id_on_another_account_binding_is_distinct` | Two bindings |
| 39 | `test_39_client_id_truncation_collision_is_refused` | Over-long ids refused |
| 40 | `test_40_client_id_normalisation_collision_is_refused` | Strip collision |
| 41 | `test_41_existing_duplicate_rows_block_migration` | Version stays 3, both rows kept |
| 42 | `test_42_interrupted_schema_migration_stays_on_version_3` | `migration_interrupted` |
| 43 | `test_43_reopening_the_journal_preserves_uniqueness` | Reopen refuses |
| 44 | `test_44_archival_preserves_the_client_id_tombstone` | Registry remains |
| 45 | `test_45_missing_journal_does_not_authorise_reuse` | File not created |
| 46–65 | `test_46` through `test_65` | Repair matrix |
| 66, 67 | `test_66_and_67_startup_orchestration_precedes_management` | Real cycle function |
| 68–74 | `test_68` through `test_74` | Block, restore, ownership |
| 76, 77 | `test_76`, `test_77` | No retry |
| 78–81 | `test_78` through `test_81` | Permit and adapter boundaries |
| 82–90 | `test_82` through `test_90` | Gates, profit hash, network, marker, temp journal |

Additional Windows methods, also passed:

- `test_finalised_without_position_is_not_invented`
- `test_successful_migration_installs_permanent_uniqueness`

Linux file `test_r77_linux_journal.py`: 2 passed. It does not cover the `bot_loop` harness. That harness is Windows-only in this stage because WSL cannot import `oandapyV20`.
