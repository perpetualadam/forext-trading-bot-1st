# R.76 regression classification

Historical test files were not edited. The suites below are not green.

## R.71

8 passed. `profit_protection.py` was not edited. No failure.

## R.72

36 passed, 1 failed.

`test_operational_source_wiring_and_unchanged_files` compares `forex_bot/positions.py` with `129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5`. The current hash is `ac33eca30201f283369196f06e97ed34da343225a011348505f6e379fc71099c`, the R.75 hash. Classification: `HISTORICAL_HASH_PIN`.

## R.70

25 passed, 1 failed.

`test_valid_then_incomplete_then_valid_empty_sequence` expects a `COMPLETE_EMPTY` snapshot to remove the live row. The row stays. Classification: `OBSOLETE_BEHAVIOURAL_EXPECTATION`.

## R.68

27 passed, 2 failed, 1 error, 1 skipped.

- `test_15_bot_created_row_stays_manageable`: symbol-only live delete returns `None`. `OBSOLETE_BEHAVIOURAL_EXPECTATION`.
- `test_disappear_path_refuses_observation_before_pop`: the test searches for `posmap.pop`, which R.74 removed. `OBSOLETE_BEHAVIOURAL_EXPECTATION`.
- `test_17_and_18_stop_quote_and_profit_files_unchanged`: `forex_bot/trading.py` hash is `b64d58870b2b4d92e16fb763a694a3e19a3ed17251bb8e435d5ec368871d30fd` because live close now refuses before HTTP. `HISTORICAL_HASH_PIN`.
- `test_23_concurrent_interleaving_not_verified`: skipped. `NOT_VERIFIED`.

## R.69

44 passed, 3 failed, 1 skipped.

- `test_operational_hashes_match_r68`: same `positions.py` pin as R.72. `HISTORICAL_HASH_PIN`.
- `test_permitted_live_flat_snapshot_still_drops_local_row`: the live row is retained. `OBSOLETE_BEHAVIOURAL_EXPECTATION`.
- `test_live_shape_reaches_quote_and_protection_without_close`: the live position never reaches `pricing_snapshot` because `live_management_permitted()` is false until recovery completes. Paper, simulated, and window-paper tests in the same file still reach `apply_profit_protection`. `OBSOLETE_BEHAVIOURAL_EXPECTATION`. This is the one new historical failure relative to the R.75 run.
- Entry-tail skip remains `NOT_VERIFIED`.

## R.73

8 passed, 21 failed, 2 errors.

The failures and errors are `missing_journal` or `CLOSE_NOT_REQUESTED` because those tests call the guarded close without a journal. The matcher itself still distinguishes a full fill from a partial fill in the R.76 tests. Classification: `OBSOLETE_BEHAVIOURAL_EXPECTATION`. This is not a new attribution regression.

## R.74 and R.75

Both Windows suites passed after the schema moved to version 3. Their tests bootstrap the current schema. A stored version 2 file fails closed as `unsupported_schema` (R.76 test 27). No silent migration was added.

## Not claimed

`GENUINE_BEHAVIOURAL_REGRESSION` was not assigned. The new R.69 live-management failure is the recovery gate required by this stage. `ENVIRONMENT_OR_DEPENDENCY_FAILURE` applies to the WSL `oandapyV20` import and is recorded in the test-results report rather than as a rewritten assertion.
