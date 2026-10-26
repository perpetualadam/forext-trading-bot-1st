# Strategy construction source map

File: `forex_bot/strategy_meta.py`.

## Class

- `Strategy.__init__(self, name: str)` at line 48. There is no `active` parameter.
- Default storage is `self._active = False` at line 51.
- Getter `active` at line 58 returns that boolean.
- Setter `active` at line 63 stores `value is True`. Only a real boolean `True` becomes active. `False`, `None`, strings, numbers, containers, and other objects stay inactive.
- `authorised_for_live` remains `False` at construction. Line 55.
- No separate serializer. Persistence of activation is in `forex_bot/live_safety.py`, which was not edited.

## Registry

- `strategies` at line 77 builds one `Strategy(name)` for each of scalp, trend, mean_reversion, swing_trend, swing_mean_reversion, and swing_breakout.
- No call site passes `active=True` into the constructor. The constructor does not accept that argument.

## Callers that construct Strategy

- `strategy_meta.py` line 77, the process-wide registry.
- `forex_bot/backtest.py` line 511 rebuilds the registry with `Strategy(s)` and later returns when `strat.active` is false. That file was not edited. Research backtests that relied on the old default will open no new trades until a later change sets activation explicitly.

## Explicit True assignments, not constructors

- `live_safety.py` applies a validated boolean during `initialise_fail_closed`.
- `operator_set_strategy_active` assigns `active is True` after confirmation.
- `restore_strategy_runtime_defaults_for_tests` assigns `True` and refuses to run outside pytest.

## Import timing

`app.py` imports `bot_loop.run_bot` at module import. `bot_loop.py` imports `strategies` at line 125. The six objects are therefore created when the application module is imported, which is before `lifespan` calls `initialise_fail_closed`. After this change those objects are inactive at that moment.
