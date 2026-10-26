# R.69 ownership bypass audit

| Case | Result | Class |
| --- | --- | --- |
| Flag true, kind `live` | Predicate false | Blocked by R.68 |
| Flag true, kind `paper` | Predicate false | Blocked by R.68 |
| Flag false, kind `reconcile_import` | Predicate false | Blocked by R.68 |
| Flag false, unknown kind | Predicate false | Blocked by R.68 |
| Legacy object with the attribute removed, kind `paper` | Predicate true | Permitted by design. A paper row without the new field keeps the old paper path |
| Legacy object with the attribute removed, kind `reconcile_import` | Predicate false | Blocked by R.68 |
| Trade id on an observation | Predicate false | Blocked by R.68 |
| `broker_order=True` on an observation | Predicate false | Blocked by R.68 |
| `EXECUTION_MODE=live_broker` | Predicate still false | Blocked by R.68. The mode string is not an argument of the predicate |
| Kind changed to `live` after import, flag left true | Predicate false | Blocked by R.68 |
| Flag cleared and kind set to `live` after import | Predicate true | Unsafe if a later writer does both. No operational function assigns `observation_only`. The only writer sets it true inside `import_position_from_broker`. Unreachable from the verified reconcile and manage graph |
| `open_position` of an observation | Row is stored. Predicate false. `close_position` returns none | Blocked at management and delete. The insert itself is the existing one-slot API |
| `open_position` replaces a paper row with an observation | Paper object is no longer the resident row. Close of the symbol is refused | The replacement is reachable only by calling `open_position` with that object. Reconciliation does not call `open_position`. Current entry construction does not pass an observation |
| Same symbol in `positions` and `broker_observations` | Paper stays permitted. Observation stays unpermitted | Permitted by design |
| Broker observation colliding with paper through `reconcile_positions_log_only` | Paper kept | Blocked by R.68 |

No verified operational path both clears `observation_only` and sets a managed kind. That in-memory pair is the remaining way to satisfy the predicate without going through the bot's own `open_position` constructor. It is not a blocker in the reconcile or manage call graph.
