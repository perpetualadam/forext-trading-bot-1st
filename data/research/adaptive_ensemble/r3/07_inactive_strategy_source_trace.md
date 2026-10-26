# Inactive-strategy source trace

Defaults: each `Strategy` starts with `_active` false. Only the boolean `True` turns it on (`strategy_meta.py` lines 58-64). The synthetic setter confirmed false, None, `"true"`, and `1` stay off. Boolean True turns on, and the fixture turned that probe back off.

`bot_loop.py` lines 1066-1084:

- If `select_strategy` returns no name, it returns before sizing.
- If the chosen strategy object is not active, it returns before sizing, before order construction, and before `execute_oanda_market_open` at line 1510.

That return was not executed. Reaching it inside `_evaluate_impl` requires getting past the live-permission block at lines 1013-1022. Granting that permission was not allowed, and the block was not patched out.

What was executed: with every name inactive and the hybrid switch on for EUR_USD, `select_strategy` returned `trend`, and that object was inactive. `allocate_scoped` handed back scalp, trend, and mean_reversion even though they were off. With the hybrid switch off, `select_strategy` returned no name.

So the selector can name an inactive strategy. The source says the loop then returns. That second step was not run. Sizing, order construction, and broker dispatch counters stayed at 0 because those functions were not called at all.
