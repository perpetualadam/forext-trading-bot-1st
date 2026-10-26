# R.45 tests and preservation

No production source was edited. After the suites, the operational hashes still match the R.45 preflight: `bot_loop.py`, `strategy_meta.py`, `ai_ensemble.py`, `rl_agent.py`, `session_rules.py`, `structure.py`, `lifecycle.py`, and `tests/test_r42_lifecycle.py`. Strategies stayed inactive. The quant stub stayed fail-closed. RL stayed `UNAVAILABLE`. Research lifecycle code stayed disconnected. No broker API, account portal, database connection, candle download, or backtest was run. R.28 PostgreSQL scripts were not run. `live_safety.py` was not edited. The R.10 synthetic safety file was not deleted.

## Attempt 1

One offline run of the R.8–R.42 suites. Every suite exited 0 except R.10.

R.10 attempt 1 failed in `tests/test_r10_offline_startup.py` at `test_i02_phases_follow_startup_order`, line 200. The test required no exception. The run raised `StartupSafetyAbort('safety state is not startup-compatible')`. The captured log was `WinError 5` Access is denied while replacing `data/research/adaptive_ensemble/r10/synthetic_live_safety_state.json`. Counts: 1 failed, 68 passed, 5 skipped. Safety assertions were not weakened.

The other counts matched the previous clean run: R.42 5, R.41 6, R.40 6, R.39 9, R.38 9, R.37 7, R.36 10, R.35 10, legacy 55, R.34 5, R.33 4, R.32 10, R.31 7, R.30 13, R.29 8, R.27 10, R.26 9, R.25 10, R.4–R.9 120 passed with 7 skipped and 1 deselected, R.11 51/5, R.12 118/5, R.13 81/6, R.14 143/5, R.15 165/6, R.16 135/6, R.17 174/9, R.18 203/9, R.19 213/9, R.20 30, R.21 24, R.22 20, R.23 15, R.24 14.

## Attempt 2

R.10 only was retried. It passed: 69 passed, 5 skipped. `WinError 5` did not appear on the retry. This does not explain the R.43 failure, and it does not change `live_safety.py`.

`pytest_r10_log.txt` now records the retry exit code 0, because the runner overwrites that file. Attempt 1 is preserved in `pytest_r10_attempts.txt`. The full-suite isolation log still shows `r10_exit=1` for the first run.
