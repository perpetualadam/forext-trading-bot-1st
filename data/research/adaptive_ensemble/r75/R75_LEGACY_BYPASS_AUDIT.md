# R.75 Legacy Bypass Audit

## Calls exercised without a valid permit

`GuardTests.test_legacy_helpers_refuse_before_position_close` called:

| Call | Result | Synthetic `PositionClose` count |
| --- | --- | --- |
| `execute_trade(..., execution_kind="live")` | `RuntimeError` | 0 |
| `execute_oanda_market_close` without a permit | `TypeError` | 0 |
| `_place_market_order_sync` without a permit | `TypeError` | 0 |
| `_submit_position_close_body` without a permit | `TypeError` | 0 |
| `_submit_position_close_body` with a forged `CloseSubmissionPermit` | `CloseGuardRefusal` | 0 |

The same four commands were also launched through `close_worker.py`, which imports the R.69 isolation harness before `forex_bot`. The worker's recorder accepts only `PositionClose` and `TransactionDetails`. Unexpected endpoint names raise `IsolationBreach`.

## In-memory reservation hole closed

`_reserve` (`broker_close_evidence.py` lines 347–383) now returns `(operation, created)`. A second caller in the same process receives the existing operation and returns immediately. It does not mark that shared object as `CLOSE_RECONCILIATION_REQUIRED`. Before that change, two threads both observed `submit_not_granted` and the synthetic client recorded 0 closes. After the change, `test_r74_close_recovery.py` `test_two_threads_submit_once` records exactly one `PositionClose`.

## Legacy unit tests not rewritten

`tests/test_g9_management.py`, `tests/test_g9_1_candle_exceptions.py`, `tests/test_market_provenance_g6.py`, and `tests/test_market_provenance_g7.py` still call `_place_market_order_sync` with three arguments. Those calls now fail closed at the required permit argument. They were not edited and were not executed with pytest, because `tests/conftest.py` loads live configuration.

## Entry path

`_place_market_order_open_sync` still builds `OrderCreate`. `assert_broker_order_allowed` and `assert_new_live_exposure_allowed` are unchanged. Close is still excluded from the new-exposure gate (`live_safety.py` lines 102–106). Paper and simulated `execute_trade` still run the existing non-live branch after the live refusal.
