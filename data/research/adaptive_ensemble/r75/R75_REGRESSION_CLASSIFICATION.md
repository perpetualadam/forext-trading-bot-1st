# R.75 Regression Classification

Historical tests were not rewritten. The suites are not green.

## R.75 and R.74 behaviour that still passes

R.74 journal 20/20 and operational recovery 9/9 passed on Windows after schema 2, the permit argument, and position persistence. That includes durable reservation, submission intent, the restart blocker, cross-process uniqueness of reserve, identity-safe deletion, one `PositionClose` from two threads, partial retention, timeout ambiguity, and broker-flat retention.

## Classified failures

| Test | Class | Why |
| --- | --- | --- |
| R.72 `test_operational_source_wiring_and_unchanged_files` | `HISTORICAL_HASH_PIN` | Expects `positions.py` `129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5`. Current file is the R.74 identity book plus the quarantine flag. |
| R.69 `test_operational_hashes_match_r68` | `HISTORICAL_HASH_PIN` | Same `positions.py` pin. |
| R.68 `test_17_and_18_stop_quote_and_profit_files_unchanged` | `HISTORICAL_HASH_PIN` | `trading.py` changed because live `execute_trade` now refuses. `profit_protection.py` was not the failing hash. |
| R.70 `test_valid_then_incomplete_then_valid_empty_sequence` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Expects a live row to disappear on `COMPLETE_EMPTY`. R.74 keeps the row unless a confirmed transaction matches. |
| R.69 `test_permitted_live_flat_snapshot_still_drops_local_row` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Same flat-snapshot deletion expectation. |
| R.68 `test_15_bot_created_row_stays_manageable` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Symbol-only live delete now returns None. The row stays, which is the safe outcome. The assertion expected the old pop. |
| R.68 `test_disappear_path_refuses_observation_before_pop` | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | Scans for `posmap.pop`, which R.74 removed. |
| R.73 tests that expect a close without a journal (21 failures, 2 errors) | `OBSOLETE_BEHAVIOURAL_EXPECTATION` | `run_guarded_live_close` returns `missing_journal` or `CLOSE_NOT_REQUESTED` and does not submit. The matcher was not reached. This is the R.74 fail-closed rule, not a change to fill attribution. |
| R.68 `test_23_concurrent_interleaving_not_verified` | `NOT_VERIFIED` | The test skips itself. |
| R.69 entry-tail skip | `NOT_VERIFIED` | `skipTest` says the blocked production entry tail was not executed. |
| WSL operational import | `ENVIRONMENT_OR_DEPENDENCY_FAILURE` | `ModuleNotFoundError: oandapyV20` at `oanda_client.py` line 13. |

No failure in this run was classified `GENUINE_BEHAVIOURAL_REGRESSION`. The two-thread failure seen during implementation (`PositionClose` count 0, both threads `submit_not_granted`) was a real defect in the shared in-memory operation. It was fixed before the final run, and the original R.74 assertion was left unchanged.

`profit_protection.py`, `broker_protection.py`, `live_manage.py`, `reconciliation.py`, `execution.py`, `bot_loop.py`, and `main.py` hashes match the R.74 baseline.
