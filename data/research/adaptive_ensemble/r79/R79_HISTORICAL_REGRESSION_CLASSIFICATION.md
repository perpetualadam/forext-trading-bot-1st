# R.79 Historical Regression Classification

Historical tests were not edited. A previously passing test that now fails was inspected before this classification.

## New failures caused by the operational fence

| Suite | Test | Class | Why |
| --- | --- | --- | --- |
| R.77 | `test_01_confirmed_single_trade_finalises` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Asserts memory `published` without a recovery session. R.79 `test_08` shows the journal still reaches `ENTRY_FINALISED`. |
| R.77 | `test_12_repeated_finalisation_does_not_move_ratchet` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Indexes `positions["EUR_USD"]` before the journal assertion. R.79 `test_17` keeps the ratchet when publication is authorised. |
| R.77 | `test_25_journal_write_failure_after_synthetic_submit_stays_ambiguous` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Expects OrderCreate without recovery. R.79 `test_16` runs that fault after recovery and records one OrderCreate and `ENTRY_OUTCOME_AMBIGUOUS`. |
| R.77 Linux | `test_atomic_finalisation_and_retained_client_id` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Fails on `published` before the client-id assertion. Linux R.78 `test_18` still covers client-id retention. |
| R.76 | `test_17_submission_intent_committed_before_network` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | The call now raises before OrderCreate because recovery authority is absent. |
| R.76 | `test_20_two_process_entry_reservation_race` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | The worker never reaches OrderCreate without an epoch, so the entered file is not written. |
| R.76 | `test_23_ambiguous_broker_timeout` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Same missing-authority refusal before the timeout path. |
| R.76 | `test_28_verified_identity_persisted_before_publication` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Asserts `published` true without a recovery session. |
| R.76 | `test_46_ambiguous_close_remains_blocked` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Expects a PositionClose call. The close adapter now refuses before the request. R.79 `test_15` performs one authorised close and refuses a stale permit. |
| R.75 | `test_stale_and_repeat_permit_do_not_submit` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | The first close no longer becomes `CLOSE_FULLY_CONFIRMED` without recovery. With recovery, `test_15` confirms once and refuses the stale permit. |
| R.75 | `test_two_processes_submit_once_through_the_guard` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Both workers lack an epoch, so the submission count is 0. |
| R.75 | `test_process_paused_after_claim_blocks_the_other` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | The holder never reaches the pause point because the close is refused first. |
| R.74 operational | six close-submission tests | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | They call `run_guarded_live_close` without recovery and expect a broker confirmation. The journal suite, which does not need that submit, stayed at 20 passed. |

## Failures that already existed at R.78

| Suite | Class |
| --- | --- |
| R.77 `test_28` schema version pinned at 4 | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.77 migration test opening a version-4 journal, including the Linux journal migration error | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.76 tests 35, 36, and 37 | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.73, same 21 failures and 2 errors | Prior classification stands. Totals did not change. |
| R.72 positions.py hash pin | `HISTORICAL_HASH_PIN` |
| R.70 empty-snapshot test | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.69 hash pin, live-flat drop, live-shape management | Prior `HISTORICAL_HASH_PIN` and `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.68 test 15, disappear-path error, trading.py hash pin | Prior classes. Totals did not change. |

No failure was classified `GENUINE_BEHAVIOURAL_REGRESSION`. The close journal, entry finaliser, client-id registry, and profit-protection file were not edited. The new failures stop at the authority check or at the memory-publication flag.

`R.74` operational and `R.75` are not green. Their previous pass counts are not restated as current results.
