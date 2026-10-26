# Source change log

No application file was modified.

`forex_bot/database.py`, `forex_bot/orders.py`, and `forex_bot/bot_loop.py` were read and left unchanged.

A source defect was found and not patched: after a reservation commits as `PENDING`, the advisory lock is gone, and a second client id for the same symbol is not blocked until the first row is `UNRESOLVED`. Fixing that SQL without an engine test could change live reservation behaviour in a way this stage cannot check. The repair was stopped for that reason.

New test file: `tests/test_r7_order_safety.py`.
New research files: `data/research/adaptive_ensemble/r7/`.
