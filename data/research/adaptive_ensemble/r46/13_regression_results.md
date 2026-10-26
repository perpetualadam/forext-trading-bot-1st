# R.46 tests and preservation

No production source was edited. After the suites, the operational hashes still match the R.46 preflight: `bot_loop.py`, `strategy_meta.py`, `ai_ensemble.py`, `rl_agent.py`, `session_rules.py`, `structure.py`, `lifecycle.py`, and `tests/test_r42_lifecycle.py`. Strategies stayed inactive. The quant stub stayed fail-closed. RL stayed `UNAVAILABLE`. Research lifecycle code stayed disconnected. No broker call, network request, database connection, candle download, or backtest was run. R.28 PostgreSQL scripts were not run. No account identifier was recorded.

One offline run of the R.8–R.42 suites. Every suite exited 0. There was no retry.

R.10 passed on the first attempt: 69 passed, 5 skipped. The run output did not contain `WinError 5`. That is a clean first pass. It does not explain the R.43 or R.45 failures, and it does not change `live_safety.py`. The other counts matched the previous clean run: R.42 5, R.41 6, R.40 6, R.39 9, R.38 9, R.37 7, R.36 10, R.35 10, legacy 55, R.34 5, R.33 4, R.32 10, R.31 7, R.30 13, R.29 8, R.27 10, R.26 9, R.25 10, R.4–R.9 120 passed with 7 skipped and 1 deselected, R.11 51/5, R.12 118/5, R.13 81/6, R.14 143/5, R.15 165/6, R.16 135/6, R.17 174/9, R.18 203/9, R.19 213/9, R.20 30, R.21 24, R.22 20, R.23 15, R.24 14.

| File | SHA-256 |
| --- | --- |
| `data/research/adaptive_ensemble/r46/00_preflight.py` | `1f07df9c8fdf9a54e43bdf28f5a7c218707105810cf1f7141adb544462a2bcf9` |
| `data/research/adaptive_ensemble/r46/20_run_offline_tests.py` | `764be6a8bda6c05184205f3ca3ade267c8b755e7524986914b3b5ba7f1ee19c8` |
