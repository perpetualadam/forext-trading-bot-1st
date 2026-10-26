# R.76 test matrix

Command: `python -B data/research/adaptive_ensemble/r76/poc/test_r76_entry_recovery.py`

Windows result: 72 tests, all passed, about 8.6 seconds. Cases 01–70 are the required matrix. Cases 71 and 72 cover the startup snapshot loader.

| # | Case | Test | Result |
| --- | --- | --- | --- |
| 1 | Valid single opened trade | `test_01_valid_single_opened_trade` | passed |
| 2 | Order id differs from trade id | `test_02_order_id_differs_from_trade_id` | passed |
| 3 | Missing trade id | `test_03_missing_trade_id_is_not_published` | passed |
| 4 | Wrong account | `test_04_wrong_account` | passed |
| 5 | Wrong instrument | `test_05_wrong_instrument` | passed |
| 6 | Wrong direction | `test_06_wrong_direction` | passed |
| 7 | Wrong units | `test_07_wrong_units` | passed |
| 8 | Missing fill transaction | `test_08_missing_fill_transaction` | passed |
| 9 | Conflicting fill transaction | `test_09_conflicting_retrieved_fill` | passed |
| 10 | Rejected order | `test_10_rejected_order` | passed |
| 11 | Partial fill | `test_11_partial_fill` | passed |
| 12 | Multiple opened trades | `test_12_multiple_opened_trades` | passed |
| 13 | Existing trade reduced | `test_13_existing_trade_reduced` | passed |
| 14 | Existing trade closed | `test_14_existing_trade_closed` | passed |
| 15 | Malformed broker response | `test_15_malformed_broker_response` | passed |
| 16 | Reservation committed | `test_16_reservation_committed_before_request` | passed |
| 17 | Submission intent committed | `test_17_submission_intent_committed_before_network` | passed |
| 18 | Persistence failure before submission | `test_18_persistence_failure_before_submission` | passed |
| 19 | Duplicate entry reservation | `test_19_duplicate_entry_reservation` | passed |
| 20 | Two-process entry race | `test_20_two_process_entry_reservation_race` | passed |
| 21 | Stale owner token | `test_21_stale_owner_token` | passed |
| 22 | Restart after submission intent | `test_22_restart_after_submission_intent_does_not_resubmit` | passed |
| 23 | Ambiguous broker timeout | `test_23_ambiguous_broker_timeout` | passed |
| 24 | Read-only recovery without resubmission | `test_24_read_only_recovery_without_resubmission` | passed |
| 25 | Corrupt journal | `test_25_corrupt_journal_blocks_management` | passed |
| 26 | Missing journal | `test_26_missing_journal_blocks_management` | passed |
| 27 | Unsupported schema | `test_27_unsupported_schema` | passed |
| 28 | Verified identity persisted | `test_28_verified_identity_persisted_before_publication` | passed |
| 29 | Missing trade id refused | `test_29_missing_trade_id_refused` | passed |
| 30 | Missing protection state quarantined | `test_30_missing_protection_state_quarantined` | passed |
| 31 | Duplicate position instance refused | `test_31_duplicate_position_instance_refused` | passed |
| 32 | Duplicate broker trade id refused | `test_32_duplicate_broker_trade_id_refused` | passed |
| 33 | Conflicting generation refused | `test_33_conflicting_generation_refused` | passed |
| 34 | Crash before position commit | `test_34_crash_before_position_commit_does_not_invent_a_position` | passed |
| 35 | Crash after position commit | `test_35_crash_after_position_commit_restores_on_startup` | passed |
| 36 | Crash before memory publication | `test_36_crash_before_memory_publication_uses_the_durable_row` | passed |
| 37 | Crash after memory publication | `test_37_crash_after_memory_publication_reloads_the_same_identity` | passed |
| 38 | Recovery before management | `test_38_recovery_runs_before_management` | passed |
| 39 | Blocked recovery prevents management | `test_39_recovery_blocked_prevents_management` | passed |
| 40 | Incomplete snapshot prevents management | `test_40_incomplete_snapshot_prevents_management` | passed |
| 41 | Valid durable position restored | `test_41_valid_durable_position_restored` | passed |
| 42 | Broker-only trade | `test_42_broker_only_trade_remains_observation` | passed |
| 43 | Manual trade | `test_43_manual_trade_remains_unmanaged` | passed |
| 44 | Unknown origin | `test_44_unknown_origin_remains_unmanaged` | passed |
| 45 | Ambiguous entry quarantined | `test_45_ambiguous_entry_remains_quarantined` | passed |
| 46 | Ambiguous close blocked | `test_46_ambiguous_close_remains_blocked` | passed |
| 47 | Repeated recovery | `test_47_repeated_recovery_is_idempotent` | passed |
| 48 | Two recovery processes | `test_48_two_simultaneous_recovery_processes` | passed |
| 49 | Missing journal blocks management | `test_49_missing_journal_blocks_live_management` | passed |
| 50 | Corrupt journal blocks management | `test_50_corrupt_journal_blocks_live_management` | passed |
| 51 | Original TP distance | `test_51_original_tp_distance_preserved` | passed |
| 52 | MFE preserved | `test_52_mfe_preserved` | passed |
| 53 | Activated ratchet preserved | `test_53_activated_ratchet_preserved` | passed |
| 54 | Missing activated state quarantined | `test_54_missing_activated_state_quarantined` | passed |
| 55 | Ratchet does not move backwards | `test_55_ratchet_never_moves_backwards` | passed |
| 56 | BUY handling | `test_56_buy_handling_preserved` | passed |
| 57 | SELL handling | `test_57_sell_handling_preserved` | passed |
| 58 | JPY pip size | `test_58_jpy_pip_size_preserved` | passed |
| 59 | ATR multiplier | `test_59_atr_multiplier_preserved` | passed |
| 60 | Four-pip fallback | `test_60_four_pip_fallback_preserved` | passed |
| 61 | R.75 close permit | `test_61_r75_close_permit_preserved` | passed |
| 62 | Legacy close bypass | `test_62_legacy_close_bypass_refused` | passed |
| 63 | Identity-safe deletion | `test_63_identity_bound_deletion_preserved` | passed |
| 64 | Full-fill confirmation | `test_64_full_fill_confirmation_preserved` | passed |
| 65 | Partial close unresolved | `test_65_partial_fill_remains_unresolved` | passed |
| 66 | Protection evidence | `test_66_protection_evidence_does_not_authorise_a_close` | passed |
| 67 | Incomplete snapshot | `test_67_incomplete_snapshot_fails_closed` | passed |
| 68 | Ownership | `test_68_ownership_preserved` | passed |
| 69 | R.71 source unchanged | `test_69_profit_protection_source_unchanged` | passed |
| 70 | Production gates | `test_70_production_gates_unchanged` | passed |
| 71 | Single trade id from OpenPositions | `test_71_single_trade_snapshot_can_restore_a_durable_row` | passed |
| 72 | Multiple trade ids not merged | `test_72_multiple_trade_ids_are_not_merged_into_the_net` | passed |

Tests 36 and 49–50 call the same recovery paths as tests 35, 26, and 25. Each method has its own assertion result in the 72-test run.
