# R.83 partial-close post-commit recovery

`test_08_partial_kill_keeps_remainder_and_quarantine` uses worker mode `partial-hold`. The synthetic PositionClose confirms 400 units. The worker waits after `run_guarded_live_close` returns. The parent kills that process.

The position was persisted with `profit_protection_exit_pips=40` before the close. `profit_protection.py` was not modified.

Successor with the durable snapshot (`match`, units 1000) prints:

- `close_state=CLOSE_PARTIALLY_CONFIRMED`
- `confirmed=400`
- `remaining=600`
- `durable_units=1000`
- `manageable=0`
- `ratchet=40`

A second successor with `conflict-open` runs one real `_execute_bot_cycle`. It prints `manageable=0` and `cycle=1`. The recorder stays at one PositionClose.

The 400 units are not added again. The original trade id remains on the durable row. Startup does not publish a manageable 1000-unit position and does not publish a manageable 600-unit position. `position.units` in the durable row stays 1000. No schema change was made.
