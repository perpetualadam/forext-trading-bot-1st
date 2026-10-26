# Strategy default remediation

CONFIRMED before the edit: `Strategy.__init__` set `self.active = True`.

The default is now inactive. The setter accepts only boolean `True` as active. Signal selection, indicator lookbacks, allocation weights, and `allocate_scoped` were not changed.

`allocate_scoped` still returns equal weights when every strategy in a pool is inactive. That is an existing selection fallback, not an activation. `bot_loop` then returns on `if not strat.active`. That check was not modified.

`backtest.py` constructs `Strategy(s)` and skips a bar when the strategy is inactive. It never sets `active` to true. Offline research backtests will therefore open no new trades. Restoring that research path requires an explicit activation in `backtest.py`, which is outside this stage. The live operator path remains `operator_set_strategy_active` with `operator_confirmed=True`.

No trading parameter, stop, target, or broker call was changed.
