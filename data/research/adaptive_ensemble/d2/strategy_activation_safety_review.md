# Strategy activation safety

The six names remain scalp, trend, mean_reversion, swing_trend, swing_mean_reversion, and swing_breakout.

TESTED inside the safety-state module:

- Explicit `false` stays inactive. T01, T28.
- A non-boolean `active`, including the string `"false"`, makes the document invalid. The file is kept. The in-memory strategy is inactive. T17.
- A missing `active` is invalid and does not become true. T18.
- Unknown metadata does not set a strategy active. T08.
- A future schema, corrupt JSON, and a missing file leave every known strategy inactive. T10, T12, T19.

Unresolved startup defect, not modified: `Strategy.__init__` in `forex_bot/strategy_meta.py` sets `active = True` and `authorised_for_live = False` when the class is constructed. `initialise_fail_closed` later deactivates the six strategies for a missing, valid, future, or invalid file. This stage did not change `strategy_meta.py`. Changing `live_safety.py` does not prove that no other code path reads `active` before startup calls `initialise_fail_closed`.

The order gate still refuses a new live open while effective authorisation is BLOCKED. That was already true and is covered by the existing repair tests. It is not a substitute for startup verification.
