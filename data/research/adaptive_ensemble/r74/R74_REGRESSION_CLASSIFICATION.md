# R.74 Regression Classification

Historical tests were not rewritten and their expected hashes were not updated.

## R.72 `test_operational_source_wiring_and_unchanged_files`

`HISTORICAL_HASH_PIN`. The assertion stopped on `forex_bot/positions.py`. It expected `129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5`. The current file differs because R.73 and R.74 changed deletion. The other R.72 behaviour tests passed, including the protection reader.

## R.73 close suite, 21 failures and 2 errors

`OBSOLETE_BEHAVIOURAL_EXPECTATION`. Those tests call `run_guarded_live_close` without `CLOSE_JOURNAL_PATH` and without bootstrap. R.74 refuses that path before the broker helper, so the result is `missing_journal` or `CLOSE_NOT_REQUESTED` and no in-memory operation is stored. The two errors are `close_operation_for` returning `None` for that reason. The same behaviours with a bootstrapped journal are in the R.74 operational suite: full fill, partial fill, rejection, timeout, flat book, and one submission from two threads.

This is not classified as a regression of transaction matching. `apply_transaction_body` is still the matcher, and the R.74 synthetic fill reached `CLOSE_FULLY_CONFIRMED` only after the retrieved transaction.

## R.70 `test_valid_then_incomplete_then_valid_empty_sequence`

`OBSOLETE_BEHAVIOURAL_EXPECTATION`. `COMPLETE_EMPTY` is still the classification of `{"positions": []}`. The live row is retained. Incomplete `{}` still fails closed. 25 other snapshot tests passed.

## R.68 `test_15_bot_created_row_stays_manageable`

`OBSOLETE_BEHAVIOURAL_EXPECTATION`. A permitted live row is no longer removable through symbol-only `close_position`.

## R.68 `test_disappear_path_refuses_observation_before_pop`

`OBSOLETE_BEHAVIOURAL_EXPECTATION`. The test searches for the source text `posmap.pop(sym, None)`. That pop was the unsafe tail and was removed. Observation rows still return before deletion. The suite still logged refusal of observation-only deletes.

## R.68 `test_17_and_18_stop_quote_and_profit_files_unchanged`

`HISTORICAL_HASH_PIN`. It stops on `live_manage.py`, whose digest is the R.72 value `b17c6cc370ea186d9deac1fdfba2d57dd5e26ea71d2be6ed0b2afa64302e9d71`. R.74 did not edit that file.

## R.69 `test_operational_hashes_match_r68`

`HISTORICAL_HASH_PIN`. First mismatch is `positions.py` against the R.68 pin. The test was not updated.

## R.69 `test_permitted_live_flat_snapshot_still_drops_local_row`

`OBSOLETE_BEHAVIOURAL_EXPECTATION`. The flat snapshot retains the live row.

## Skips

R.68 `test_23_concurrent_interleaving_not_verified` remains skipped: `NOT_VERIFIED`.

R.69 `test_entry_tail_was_not_executed` remains skipped: `NOT_VERIFIED`.

## Not a regression

R.71 profit-protection calculations: 8 passed. No formula file in that set was edited by R.74.
