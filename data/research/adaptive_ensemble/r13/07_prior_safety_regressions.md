# Prior safety regressions

R.13 file G46–G65 passed: pending, partial, unresolved, unknown status, duplicate client id, duplicate symbol, ambiguous commit, persistence failure, FILLED exposure, missing position, position-record failure, historical FILLED rows, invalid direction, inactive strategy, live-order block, no real broker, no retry, and no production launcher.

Separate processes:

- R.4–R.9: 120 passed, 7 skipped, 1 deselected.
- R.10: 69 passed, 5 skipped.
- R.11: 51 passed, 5 skipped.
- R.12: 118 passed, 5 skipped.

The R.9 assertion that a `CONFIRMED_FLAT` argument cleared the hold now expects the hold to remain. That is a tighter assertion. The other R.9 checks were not loosened.

Hash pins for `bot_loop.py` and `database.py` were updated to the post-stage digests. Protected-file pins were not changed.
