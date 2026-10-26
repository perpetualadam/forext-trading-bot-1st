# Selector contract and the R.20 null result

## Why R.20 saw null

`select_strategy` uses the legacy allocator when hybrid mode is off. That allocator only includes strategies whose `active` flag is true. All six names (`scalp`, `trend`, `mean_reversion`, `swing_trend`, `swing_mean_reversion`, `swing_breakout`) default to `active=False` and `authorised_for_live=False`. Empty weights make the selector return `None`. That is `NO_ACTIVE_ELIGIBLE`, not an interface mismatch.

The shared iteration then discarded that result. If the caller passed a non-empty `strategy_name`, that string, plus the caller's active and authorised flags, replaced the selector. R.20 passed `scalp` and `strategy_active=True`, so the iteration traded `scalp` after a null selection.

## What a valid result is

`select_deterministic` is the existing deterministic selector. With `persist=False` and `active_override={"scalp": True}` it returns `scalp`, lookback 50, horizon `legacy`, reason `rotate_active_eligible`. It does not write the cursor and does not set `strategies[name].active`.

`select_strategy` itself still returns `None` on the default path. With `HYBRID_EUR_USD` enabled it can return one of the six names, and that name is still inactive, so the iteration blocks with `STRATEGY_INACTIVE`.

## Repair

When the selector is invoked, `_authoritative_strategy` is the only source of the strategy name:

- null or blank blocks with `NO_STRATEGY_SELECTED` before vote, RL, sizing, reservation, and dispatch
- a non-string blocks with `selector_result_malformed`
- a name outside the six blocks with `UNKNOWN_STRATEGY`
- an inactive name blocks with `STRATEGY_INACTIVE`
- a caller-supplied `strategy_name` cannot replace null or override a different selected name
- a missing selector or a selector exception still blocks with `strategy_selection_unavailable` or `strategy_selection_error`
- caller `strategy_authorised` and `safety_initialised` are not applied on this path

The existing `strategy_entry_block_reason` still returns `STRATEGY_NOT_AUTHORISED` when safety is initialised and `authorised_for_live` is false. The offline path does not claim that safety is initialised, and it does not set `authorised_for_live`. Production eligibility stays false.

Callers that do not invoke the selector still use the supplied strategy name. R.12 and R.13 use that path.
