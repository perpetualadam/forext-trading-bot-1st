# R.76 ownership and provenance review

`position_management_permitted` in `forex_bot/positions.py` is unchanged. It is false when `observation_only` is true, when `recovery_quarantine` is true, or when the execution kind is not one of `paper`, `simulated`, `window_paper`, `live`, and `synthetic`.

`import_position_from_broker` was not changed. Broker discoveries stay observation-only. Test 68 builds a `reconcile_import` observation and asserts management is false. `classify_broker_discovery("manual")` is not manageable.

`persist_bot_position` writes `provenance = bot_managed` and refuses an observation row with `ownership_refused`.

Startup quarantine sets `observation_only` on the recovered object and stores it in `quarantined_positions`, not in `positions`.

An entry journal row is evidence of bot intent. It does not by itself publish a position. A broker trade seen during an ambiguous entry stays out of the managed book (tests 24, 34, and 45).

The R.68 historical suite was not rewritten. Its current result is 27 passed, 2 failed, 1 error, 1 skipped. See `R76_REGRESSION_CLASSIFICATION.md`.
