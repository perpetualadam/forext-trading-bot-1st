# R.68 patch design

## Defect

`import_position_from_broker` wrote the same dict `get_position` uses. The manage branch treated every resident row as closeable and then called `close_position`, which always popped. `log_only` did not stop that insert. Case B also deleted a paper row before the insert. `account_disappeared_broker_position` popped by symbol and bypassed `close_position`.

## Narrowest correction

One predicate, `position_management_permitted`, lives in `forex_bot/positions.py`.

It returns true only when all of these hold:

- the object exists
- `observation_only` is false
- `execution_kind`, case-folded, is one of `paper`, `simulated`, `window_paper`, `live`, `synthetic`

`reconcile_import`, an empty kind, and any other kind return false. A trade id, `broker_order`, and a configuration string are not read.

Import always stores the discovery in `broker_observations` with `observation_only=True` and `execution_kind="reconcile_import"`. A caller-supplied kind is logged and ignored. The managed dict is left as it was, including when a paper or bot row is already there.

The manage branch in `_evaluate_impl` returns before quote selection, profit protection, weekend flatten, `execute_trade`, and `close_position` when the predicate is false.

`close_position`, and `close_local_position` through it, refuse to pop a non-permitted row. `adjust_position_units_to_broker` refuses to resize one. The `auto_fix` loop skips non-permitted rows before `account_disappeared_broker_position`. That helper returns `observation` before any `posmap.pop` when the resident row is not permitted.

## Why this preserves existing rows

`open_position` from the existing entry tail sets `live`, `simulated`, or `window_paper` and leaves `observation_only` at its default false. The synthetic recorder uses `synthetic` and the same default. Those rows stay permitted, so the rest of the manage tail is unchanged for them.

Paper rows stay in `positions`. Case B no longer calls `displace_paper_position`. That is the safety exception required when a paper row and a broker observation share an instrument: the paper row remains manageable and the broker side stays an observation.

Unknown provenance fails closed: it is not closed and it is not deleted.

## What this does not add

No grant table, no close-operation record, no reconciliation epoch, no database table, no new OANDA endpoint, and no change to order, sizing, stop, or profit-protection formulas. `REAL_SESSION_SOURCE_ENABLEMENT` stays false. The entry comparison with `continue_existing_production_broker` is still a comparison. The blocked production return remains.

## Limit

The full `_evaluate_impl` coroutine was not executed, because importing `bot_loop` loads `forex_bot.config`. The withhold is the source prefix return plus the executed predicate and delete guards. Two tasks interleaving on the shared dict were not executed. That remains the broader R66-16 limit.
