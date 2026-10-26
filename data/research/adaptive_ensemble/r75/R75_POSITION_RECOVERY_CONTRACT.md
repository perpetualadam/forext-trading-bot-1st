# R.75 Position Recovery Contract

Module: `forex_bot/position_recovery.py`.

`recover_managed_book` (line 391) opens the active journal, which recovers unresolved closes, then evaluates and publishes each durable row. It never calls `PositionClose` and never calls `close_confirmed_live_position`. Every decision records `close_submission_count=0` and `delete_permitted=False`.

## Manageable restoration

`evaluate_durable_row` (line 277) returns `restored_managed` / `broker_trade_matches` only when all of the following hold:

- provenance is `bot_managed`
- execution kind is paper, simulated, window_paper, live, or synthetic
- entry, stop, take-profit, MFE, activation flag, close-attempt timestamp, minimum profit, and maximum adverse excursion are non-NULL
- if activation is true, exit pips and the four activated ratchet fields are non-NULL
- the supplied broker view is one matching trade for that instrument
- account binding, trade id, direction, and units match
- no unresolved journal row disagrees with the instance id
- no outstanding unresolved close exists for that trade

`publish_recovered` (line 366) writes that object into `positions` only when the symbol slot is empty, or when the slot already has the same instance id and generation.

## Quarantine

Any failed condition returns `quarantined` or `awaiting_finalisation`. The object is stored in `quarantined_positions`, `observation_only` is set, and `recovery_quarantine` is set. `position_management_permitted` (`positions.py` lines 70–71) returns false for either flag.

A fully confirmed journal row produces `awaiting_finalisation` / `confirmed_close_not_finalised`. The row is not republished as open and is not deleted by recovery.

## Broker view input

The recovery function does not call the broker. The caller supplies a view with `snapshot` and `trades`. Tests use synthetic views. `COMPLETE_EMPTY` is `broker_flat_unattributed`. `INCOMPLETE`, `MALFORMED`, `REQUEST_FAILED`, `STALE`, `UNAVAILABLE`, and `UNKNOWN` are `broker_snapshot_not_authoritative`.

## Production loop

`bot_loop.py` was not changed and does not call `recover_managed_book`. Recovery is available to an operator or a later startup step. Until that call, a restarted process has an empty memory book even if durable rows exist. `R75_RECOVERY_BEFORE_MANAGEMENT` is therefore not marked passed for the running loop.
