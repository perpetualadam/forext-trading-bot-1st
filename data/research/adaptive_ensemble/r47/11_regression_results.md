# R.47 tests and preservation

No production source was edited. `MAX_POSITION_UNITS` was not changed. After the suites, the operational hashes still match the R.47 preflight, including `bot_loop.py` `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796`, `strategy_meta.py` `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`, `ai_ensemble.py` `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa`, `rl_agent.py` `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e`, `structure.py` `b9dd4a4fb133a42bd1cf2ec0615bca64f1299e5568e7d392e21f82c8d12943bc`, and `lifecycle.py` `4ed6fb9d53b2c67930e1367303c50a48a06f51b266c4b99a6655dda32162cba5`. Strategies stayed inactive. The quant stub stayed fail-closed. RL stayed `UNAVAILABLE`. No broker call, network request, database connection, or backtest was run. R.28 PostgreSQL scripts were not run. The screenshot was not stored. No account identifier was recorded. `live_safety.py` was not edited. The R.10 synthetic safety file was not deleted.

## Attempt 1

Every suite exited 0 except R.10. R.10 failed in `test_i02_phases_follow_startup_order` at `tests/test_r10_offline_startup.py:200`. The test required no exception. The run raised `StartupSafetyAbort('safety state is not startup-compatible')` after `WinError 5` while replacing `data/research/adaptive_ensemble/r10/synthetic_live_safety_state.json`. Counts: 1 failed, 68 passed, 5 skipped. Safety assertions were not weakened.

The other counts matched the previous clean run: R.42 5, R.41 6, R.40 6, R.39 9, R.38 9, R.37 7, R.36 10, R.35 10, legacy 55, R.34 5, R.33 4, R.32 10, R.31 7, R.30 13, R.29 8, R.27 10, R.26 9, R.25 10, R.4–R.9 120 passed with 7 skipped and 1 deselected, R.11 51/5, R.12 118/5, R.13 81/6, R.14 143/5, R.15 165/6, R.16 135/6, R.17 174/9, R.18 203/9, R.19 213/9, R.20 30, R.21 24, R.22 20, R.23 15, R.24 14.

## Attempt 2

R.10 only was retried. It passed: 69 passed, 5 skipped. `WinError 5` did not appear on the retry. This does not explain the R.43 or R.45 failures, and it does not change `live_safety.py`.

`pytest_r10_log.txt` now records the retry exit code 0, because the runner overwrites that file. Attempt 1 is preserved in `pytest_r10_attempts.txt`. The full-suite isolation log still shows `r10_exit=1` for the first run.

| File | SHA-256 |
| --- | --- |
| `data/research/adaptive_ensemble/r47/00_preflight.py` | `57bc81eab96247bae194b64b70accb19e53036e4d280844bdd645d5eeade848e` |
| `data/research/adaptive_ensemble/r47/20_run_offline_tests.py` | `c2cf861c8180c20f8b4744ed731f918ac94881ef1a9d367edf22b23ce6c8e80e` |
