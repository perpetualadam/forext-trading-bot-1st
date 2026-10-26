# Source change log

## Modified

- `forex_bot/database.py` — pre `4c289dfaa2ca70077fc314a9bb3f92609ab0a9dbda9db26ff912d80b8d03a4a8`, post `16363fdc26929ed0a6fe71837806ba96c51043df76fa3d524a2d26f80736c486`. Recovery and reservation SQL now keep FILLED rows that are not exactly `CONFIRMED_FLAT`. A full recovery page fails closed. Metadata is no longer coerced to an empty object.
- `forex_bot/orders.py` — pre `78c34c86bcc5f1d90d3979b18052a4fc9496a2b3cc2f37589f17ef2b6f7f0dd9`, post `fca93e8007d5f25413caf6b7e6493db0a27b4b81cffe78331d3321e9e76db1b4`. Malformed metadata fail-closes. Conflicting duplicate client ids fail-close. Identical duplicates stay idempotent.
- `forex_bot/app.py` — pre `7a925e3f5a247b9f92ab42db17242c5a895de099b6897145fba6bfb7d737ef9e`, post `8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1`. Offline startup filters injected rows with `select_rows_for_recovery` before ingest. `historical_filled_gap` is false for the source query. PostgreSQL execution remains unverified.

## Tests updated

- `tests/test_r8_reservation_safety.py` and `tests/test_r9_position_safety.py` follow the named reservation SQL constant and the new `app.py` hash.
- `tests/test_r10_offline_startup.py` expects the repaired source query and the new database and orders hashes.

## Added

- `tests/test_r11_historical_recovery.py`
- `data/research/adaptive_ensemble/r11/20_run_offline_tests.py`

`bot_loop.py` and the protected files are unchanged.

The `git diff --stat` against HEAD for the three source files is 1296 insertions and 154 deletions. That includes earlier uncommitted work. It is not an R.11-only diff.
