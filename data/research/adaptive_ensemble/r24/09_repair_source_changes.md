# Repair source changes

Only `forex_bot/database.py` changed.

Pre-repair SHA-256: `e543a84e0a137fbd2387a5e1b85aad52b71988a4abf2bfd0f1ddb7afe217e064`

Post-repair SHA-256: `0eb8548b70c9ae9a14880de92518ed20ddb8a23c2378cda7ce5da62c3ac998d6`

Unchanged:

- `forex_bot/bot_loop.py` `a8b455dad91c464df8ba030b7f119f3c1795ce289e21b83de0af771309823ac2`
- `forex_bot/orders.py` `fca93e8007d5f25413caf6b7e6493db0a27b4b81cffe78331d3321e9e76db1b4`
- `forex_bot/app.py` `8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1`

`tests/test_r10_offline_startup.py` updates the database hash pin to the post-repair hash. No safety assertion was weakened.

New test: `tests/test_r24_recovery_fail_closed.py`.
