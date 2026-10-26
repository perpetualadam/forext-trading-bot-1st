# R.80 historical regression inventory

Evidence class: the R.79 executed failure list, re-checked by reading the historical assertions. Historical files were not edited. The R.80 rerun totals are in `R80_HISTORICAL_REGRESSION_RESULTS.md`.

These tests passed under R.78 and failed under R.79 because they submit, or expect memory publication, without `execute_startup_sequence`.

| Historical test | Original property | R.78 | R.79 | Why it changed | Bypassed startup | Synthetic broker | Real concurrency | R.80 replacement | Coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R.74 `test_full_fill_deletes_matching_row_only` | One full close confirms and does not delete a different identity | Pass | Fail | `run_guarded_live_close` now reaches the authority check before a synthetic fill | Yes | Yes | No | `test_01` | EQUIVALENT_COVERAGE for one close and a refused repeat. The identity-delete assertion was not rebuilt line for line |
| R.74 `test_partial_fill_keeps_row_and_blocks_resubmit` | A partial close does not authorise another submit | Pass | Fail | Same missing authority | Yes | Yes | No | `test_02` | PARTIAL_COVERAGE. Ambiguous timeout blocks resubmit. A partial-fill body was not replayed |
| R.74 `test_rejection_can_reserve_a_new_operation` | A rejected close may reserve a later operation | Pass | Fail | Same | Yes | Yes | No | None | MISSING_COVERAGE |
| R.74 `test_timeout_blocks_resubmit_across_process_reopen` | Timeout stays ambiguous across reopen | Pass | Fail | Same | Yes | Yes | Process reopen | `test_02` and `test_13` | PARTIAL_COVERAGE. Timeout blocks a second submit. Reopen of that exact close row is the kill test for entry, not this close row |
| R.74 `test_two_threads_submit_once` | One close submission | Pass | Fail | Same | Yes | Yes | Threads | `test_12` | STRONGER_COVERAGE. Two OS processes, one authorised owner, one submission |
| R.74 `test_flat_snapshot_and_open_trade_do_not_confirm` | A flat snapshot does not confirm a close | Pass | Fail | Same | Yes | Yes | No | `test_15` | PARTIAL_COVERAGE. A conflicting broker identity is quarantined. The flat-snapshot close case was not replayed |
| R.75 `test_stale_and_repeat_permit_do_not_submit` | First close once, stale permit does not submit | Pass | Fail | Authority check precedes the permit use when no recovery exists | Yes | Yes | No | `test_01` | EQUIVALENT_COVERAGE |
| R.75 `test_two_processes_submit_once_through_the_guard` | Two processes, one PositionClose | Pass | Fail | Neither worker had an epoch | Yes | Yes | Yes | `test_12` | STRONGER_COVERAGE under the real rule that two owners cannot both be valid |
| R.75 `test_process_paused_after_claim_blocks_the_other` | Pause after claim, competitor does not submit | Pass | Fail | The holder never reached the pause without authority | Yes | Yes | Yes | `test_12` | EQUIVALENT_COVERAGE. The parent reads `network_permit=1` while the owner is inside the synthetic request |
| R.76 `test_17_submission_intent_committed_before_network` | Reservation is durable before OrderCreate | Pass | Fail | OrderCreate refused without authority | Yes | Yes | No | `test_04` | EQUIVALENT_COVERAGE |
| R.76 `test_20_two_process_entry_reservation_race` | One reservation and one OrderCreate | Pass | Fail | Workers never reached OrderCreate | Yes | Yes | Yes | `test_10` and `test_11` | STRONGER_COVERAGE |
| R.76 `test_23_ambiguous_broker_timeout` | Timeout does not retry | Pass | Fail | The call never reached the broker | Yes | Yes | No | `test_05` | EQUIVALENT_COVERAGE for a post-request journal fault that leaves `ENTRY_OUTCOME_AMBIGUOUS` and blocks a second reservation |
| R.76 `test_28_verified_identity_persisted_before_publication` | Durable identity before memory publication | Pass | Fail | Memory publication now requires the fence | Yes | No | No | `test_07` and `test_09` | EQUIVALENT_COVERAGE |
| R.76 `test_46_ambiguous_close_remains_blocked` | One ambiguous close, no second submit | Pass | Fail | Close refused before the request | Yes | Yes | No | `test_02` | EQUIVALENT_COVERAGE |
| R.77 `test_01_confirmed_single_trade_finalises` | Finalise and publish | Pass | Fail | Publish requires authority. The journal still finalises | Yes | No | No | `test_07` | EQUIVALENT_COVERAGE |
| R.77 `test_12_repeated_finalisation_does_not_move_ratchet` | A repeat finalisation does not lower the ratchet | Pass | Fail | The test indexed memory that is no longer published without authority | Yes | No | No | `test_16` | EQUIVALENT_COVERAGE for the ratchet. It uses profit-protection persistence rather than a second finalisation |
| R.77 `test_25_journal_write_failure_after_synthetic_submit_stays_ambiguous` | One OrderCreate, then an ambiguous journal outcome | Pass | Fail | The submit never started without authority | Yes | Yes | No | `test_05` | EQUIVALENT_COVERAGE |
| R.77 Linux `test_atomic_finalisation_and_retained_client_id` | Finalise, publish, retain the client id | Pass | Fail on `published` | Same fence | Yes | No | No | `test_07` | EQUIVALENT_COVERAGE |

R.76 tests 35, 36, and 37, and the R.77 schema-4 assertions, were already obsolete at the R.79 baseline. They are not new R.79 regressions. Their safety properties are covered by `test_07` for committed restart and by the unchanged schema-5 refusal.

`test_rejection_can_reserve_a_new_operation` remains MISSING_COVERAGE. A rejected close that is allowed to reserve again was not rebuilt. Ambiguous and confirmed closes stay blocked.
