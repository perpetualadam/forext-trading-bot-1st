# R.40 changed files

Production voting, reinforcement learning, session rules, the bot loop, strategy flags, and the R.39 regime module were not edited. Their hashes match the R.39 record.

| File | SHA-256 |
| --- | --- |
| `forex_bot/ai_ensemble.py` | `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa` |
| `forex_bot/rl_agent.py` | `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e` |
| `forex_bot/session_rules.py` | `1e9ec90f573f1fd8add2a2fa4bab82fe164788242f34e97bbcf428e6f5c4bef1` |
| `forex_bot/bot_loop.py` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` |
| `forex_bot/strategy_meta.py` | `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d` |
| `forex_bot/research/learning/regimes.py` | `f3d2ffdbe77e17808e30b3d034b5b681fd631426349dbbd107c4f4c83cfdc0ea` |
| `forex_bot/research/learning/timeframes.py` | `a482ef747fb28a9d1a4409c8d67b67811147afaedd0b487c52f2e9730f734676` |
| `tests/test_r40_timeframes.py` | `1882ad7db44b73a5ec29de4315a917ff56d02dc31ad032e3bbf694f90f074e67` |
| `data/research/adaptive_ensemble/r40/00_preflight.py` | `ca1d028e98baa0d856b633b3f349c35ff36a0c026d4c76f2fe31b3da2351293a` |
| `data/research/adaptive_ensemble/r40/02_inventory.py` | `fa429524fca0ba85dd95979555734a389bc0d963ae4074d4977ff14321a0c6c7` |
| `data/research/adaptive_ensemble/r40/20_run_offline_tests.py` | `3deaa5f25d8766b9d8dd22eded72f029147a70756bd44f8541914e5d7cbca9af` |

New research code is `timeframes.py`. It aggregates completed candles and answers an as-of close. It does not emit a signal. Evidence notes under `data/research/adaptive_ensemble/r40/` are the blueprint. Historical CSV files were read and not modified. R.24–R.39 evidence files were left in place.
