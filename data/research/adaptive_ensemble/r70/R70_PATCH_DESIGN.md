# R.70 Patch Design

Operational change: `forex_bot/reconciliation.py` only.
Research test updates: the new R.70 suite, plus two assertion updates and a short-unit sign correction in the R.69 harness.

## Design

1. `_interpret_open_positions` classifies the whole body before any global snapshot write.
2. `BrokerSnapshotError` carries the classification. It subclasses `RuntimeError`, and the missing-client message contains `unavailable`.
3. `_begin_snapshot_request` increments `_snapshot_generation` under `_snapshot_lock` before `_oanda_request`.
4. `_publish_snapshot` writes `_last_broker_nets`, `_last_trade_ids`, `_have_broker_snapshot`, `_accepted_generation`, and `_last_snapshot_class` only when the generation is still current. Otherwise it raises `STALE` and writes nothing.
5. The lock is not held during the broker call and is not a reconciliation lock.
6. `reconcile_positions_log_only` records `broker_snapshot_class`. On `BrokerSnapshotError` it sets `last_error` and skips `_apply_position_convergence` and the pending-order reconcile.
7. The success path no longer calls `_remember_broker_snapshot`. Fetch already published. `_remember_broker_snapshot` remains for a direct caller and does not check generation.
8. A valid empty list still publishes `COMPLETE_EMPTY` and still allows the existing `auto_fix` disappear of a permitted live row.

## After-change call path

```text
reconcile_positions_log_only
  fetch_broker_positions_detail
    missing api or account id -> BrokerSnapshotError UNKNOWN
    _begin_snapshot_request
    _oanda_request(OpenPositions)
      exception -> BrokerSnapshotError REQUEST_FAILED
    _interpret_open_positions
      INCOMPLETE / MALFORMED / CONFLICT -> raise, no publish
    _publish_snapshot
      older generation -> STALE, previous book kept
      current generation -> replace published book
  on error: skip _apply_position_convergence
  on success: existing case logic, including observation-only import
```

## Why this did not need the close state machine

Invalid bodies never reach `account_disappeared_broker_position`. The false-flat hole was the interpretation of the response, not the close lifecycle. A valid `positions: []` still cannot prove that a prior close filled. Implementing an ad hoc close identity here would have expanded into R.67B. That was left undone. `R70_IMPLEMENTATION_BLOCKED` does not apply.

## Intentional behaviour that remains unsafe

A permitted live row plus `COMPLETE_EMPTY` plus `auto_fix` still calls `account_disappeared_broker_position`. The R.70 test `test_valid_then_incomplete_then_valid_empty_sequence` observes the local row being removed and observes that `PositionClose` is not in the synthetic calls. The trade-details lookup can still run. This is recorded as known unsafe behaviour, not as a successful close.

## Files not modified

`positions.py`, `bot_loop.py`, `broker_exit.py`, `execution.py`, `trading.py`, `live_manage.py`, `oanda_exec.py`, `profit_protection.py`, `app.py`, `database.py`, `main.py`, strategy modules, source gates, and the consumed marker.
