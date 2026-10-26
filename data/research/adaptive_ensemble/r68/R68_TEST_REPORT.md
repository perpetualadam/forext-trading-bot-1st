# R.68 test report

## Command

From the repository root:

```text
python -B data/research/adaptive_ensemble/r68/poc/test_r68_observation_boundary.py
```

`unittest discover` was not used. The `r68/poc` directory is not a package, and discover would also risk loading a project `conftest`.

The test imports `forex_bot.positions` and, through `import_position_from_broker`, `forex_bot.execution`. It asserts `forex_bot.config` and `dotenv` are absent from `sys.modules`. It does not import `reconciliation`, `bot_loop`, `app`, `trading`, `database`, `oanda_exec`, or `config`. Those modules are read as text for the source-order checks.

## Result

Windows CPython 3.13.5: `Ran 31 tests in 0.190s`, `OK (skipped=1)`.

The skipped test is `test_23_concurrent_interleaving_not_verified`. Classification: `NOT_VERIFIED`. Two live tasks were not started.

## Required cases

| Case | Test | Result |
| --- | --- | --- |
| 1 `log_only` insert withheld | `test_01_log_only_import_does_not_enter_managed_book` | PASS. The import function itself no longer inserts. Mode is not an argument of that function. |
| 2 Broker mode does not grant management | `test_02_broker_mode_argument_does_not_grant_management` | PASS |
| 3 `auto_fix` does not grant authority | `test_03_auto_fix_source_skips_non_permitted_rows` | PASS as a source-order check. The reconcile module was not imported. |
| 4 `execution_kind` is not ownership | `test_04_execution_kind_does_not_create_ownership` | PASS |
| 5 Trade id is not authority | `test_05_trade_id_does_not_grant_authority` | PASS |
| 6 Local row is not authority | `test_06_local_row_does_not_grant_authority` | PASS |
| 7 Unknown provenance fails closed | `test_07_unknown_provenance_fails_closed` | PASS |
| 8 Weekend flatten does not call `PositionClose` | `test_08_and_09_manage_source_returns_before_close` | PASS for source order. The manage coroutine was not executed. |
| 9 Profit protection does not call `PositionClose` | same | PASS for source order. |
| 10 Weekend flatten does not locally delete | `test_10_and_11_observation_is_not_locally_deleted`, `test_21_import_then_weekend_delete_refused` | PASS on `close_position` / `close_local_position` |
| 11 Profit protection does not locally delete | `test_22_import_then_profit_protection_delete_refused` | PASS on the delete functions |
| 12 Observation is not promoted to `live` | `test_12_observation_is_not_promoted_to_live` | PASS |
| 13 Manual broker position stays untouched | `test_13_manual_broker_observation_stays_out_of_the_book` | PASS |
| 14 Observation remains visible | `test_14_observation_remains_visible` | PASS via `broker_observations` |
| 15 Bot-created row keeps management | `test_15_bot_created_row_stays_manageable` | PASS for the predicate and `close_position`. Full manage coroutine not executed. |
| 16 Paper keeps management | `test_16_paper_row_stays_manageable` | PASS for `paper`, `simulated`, `window_paper` |
| 17 Stop and profit formulas unchanged | `test_17_and_18_stop_quote_and_profit_files_unchanged` | PASS by SHA-256 of `profit_protection.py`, `trading.py`, `live_manage.py` |
| 18 Quote selection unchanged | same | PASS by SHA-256 of `live_manage.py` |
| 19 New entry stays blocked | `test_19_new_entry_status_remains_blocked` | PASS. The status string occurs once, inside a `Compare`. `status="blocked"` and `production_path_has_no_simulation_context` remain. |
| 20 No new OANDA write endpoint | `test_20_no_new_position_close_call_in_changed_sources` | PASS. `PositionClose(`, `OrderCreate(`, and `TradeClose(` are absent from the edited modules. The existing call remains in unchanged `oanda_exec.py`. |
| 21 Import then weekend flatten | `test_21` | PASS for local delete. Broker call covered by case 8. |
| 22 Import then profit protection | `test_22` | PASS for local delete. |
| 23 Reconcile while manage holds a reference | `test_23_sequential_reference_keeps_paper` | PASS for the sequential case. Concurrent interleaving `NOT_VERIFIED`. |
| 24 Legacy observation row | `test_24_legacy_observation_row_is_not_deleted` | PASS |
| 25 Forged `live` on an import | `test_25_forged_live_on_imported_row_does_not_grant` | PASS |
| 26 Stale row not resized | `test_26_stale_observation_is_not_resized` | PASS |
| 27 Paper plus broker observation | `test_27_paper_and_broker_observation_for_same_instrument` | PASS |
| 28 Malformed provenance | `test_28_malformed_provenance_fails_closed` | PASS |

Additional executed checks: `synthetic` stays manageable; the four edited modules parse; the disappear helper returns before `posmap.pop`; Case C no longer increments `fixes`.

## Tests not executed

`tests/test_reconcile_conflict.py`, `tests/test_execution_safety.py`, and `tests/test_live_position_management.py` import reconciliation and expect the old managed-import behaviour. They were not run, because importing them loads `forex_bot.config`. They were not rewritten.

No pytest of `forex_bot` was run. No broker fixture was contacted.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

`POSTGRESQL_INTEGRATION_NOT_TESTED`
