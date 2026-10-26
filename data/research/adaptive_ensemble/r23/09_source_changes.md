# Source changes

`forex_bot/database.py` is the only application source edited. `offline_exec_order_store_path` no longer reads `EXEC_ORDER_OFFLINE_STORE`. The JSON store is armed only by `arm_offline_exec_order_store` with context `isolated_offline_test` and a path under the R.22 or R.23 research directory. A production-eligibility argument does not arm it. A bad context or path fail-closes.

Post-stage SHA-256 of `forex_bot/database.py`: `e543a84e0a137fbd2387a5e1b85aad52b71988a4abf2bfd0f1ddb7afe217e064`.

Unchanged application hashes:

- `forex_bot/bot_loop.py` `a8b455dad91c464df8ba030b7f119f3c1795ce289e21b83de0af771309823ac2`
- `forex_bot/orders.py` `fca93e8007d5f25413caf6b7e6493db0a27b4b81cffe78331d3321e9e76db1b4`
- `forex_bot/app.py` `8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1`
- `forex_bot/oanda_exec.py` `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8`
- `forex_bot/live_safety.py` `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- `forex_bot/strategy_meta.py` `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`
- `forex_bot/config.py` `13db72c668f60a8a50bf148789070c29cb941be748a51b298bd7bcb2971f99fd`
- `main.py` `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb`

`tests/test_r22_restart_recovery.py` now arms and disarms the store. That keeps the R.22 contract on the new selection rule. Exposure, eligibility, and adapter assertions were not weakened. `tests/test_r10_offline_startup.py` updates the `database.py` hash pin to the hash above. The `bot_loop.py` pins were left unchanged.

New files: `tests/r23_process_driver.py`, `tests/test_r23_process_restart.py`, and `data/research/adaptive_ensemble/r23/20_run_offline_tests.py`.
