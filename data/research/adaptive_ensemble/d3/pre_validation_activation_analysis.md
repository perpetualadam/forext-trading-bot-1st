# Pre-validation activation analysis

Result: `NO_PRE_VALIDATION_ACTIVATION_PATH_FOUND_STATICALLY`

This is a static finding. It is not a production startup run.

## Active object

Before `initialise_fail_closed`, the six registry objects exist and are inactive. Fresh `Strategy(name)` objects are inactive. OFFLINE_TESTED for the constructor. STATICALLY_VERIFIED for the import order.

No production constructor passes `active=True`.

## Authorised to trade

`authorised_for_live` is false at construction. A protected safety file clears it. A BLOCKED document does not grant live authorisation. Effective authorisation on process start remains BLOCKED even if a valid file says ALLOWED. That last rule is in `live_safety.py` and was not changed.

## Able to route an order

`live_open_blocked_reason` blocks a new open when safety state is not valid or authorisation is not ALLOWED. OFFLINE_TESTED on a synthetic BLOCKED file. The production process was not asked to route an order.

## Paths that can become active later

- A valid safety document with boolean `active: true`, applied inside `initialise_fail_closed`.
- `operator_set_strategy_active` after `operator_confirmed=True`. On a protected file it raises `SafetyStateProtected` before the assignment.
- `restore_strategy_runtime_defaults_for_tests`, which sets `active = True` and refuses to run unless `PYTEST_CURRENT_TEST` is set. Not a production path.

## Residual window

`bot_loop.py` lines 1085-1094 skip the `authorised_for_live` check when `live_safety_initialised()` is false. Invalid safety state makes that function false. The earlier `if not strat.active` return still stops an inactive strategy. A future edit outside this stage would be required to keep that authorisation check in force when state is invalid. Not changed here.

`allocate_scoped` can still name an inactive strategy. The object is not set active, and the bot loop returns before sizing.
