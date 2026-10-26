# R.42 changed files

Branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The working tree was already dirty. Unrelated changes were left in place. Nothing was committed, reset, cleaned, stashed, or rolled back.

## New research code

| File | SHA-256 |
| --- | --- |
| `forex_bot/research/learning/lifecycle.py` | `4ed6fb9d53b2c67930e1367303c50a48a06f51b266c4b99a6655dda32162cba5` |
| `tests/test_r42_lifecycle.py` | `8b22fdf38e6da160a7de40bae080f884f0ef0aae4c4fa302a72084496ee9db2b` |

## Unchanged pinned sources

| File | SHA-256 |
| --- | --- |
| `forex_bot/bot_loop.py` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` |
| `forex_bot/strategy_meta.py` | `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d` |
| `forex_bot/ai_ensemble.py` | `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa` |
| `forex_bot/rl_agent.py` | `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e` |
| `forex_bot/session_rules.py` | `1e9ec90f573f1fd8add2a2fa4bab82fe164788242f34e97bbcf428e6f5c4bef1` |
| `forex_bot/research/learning/structure.py` | `b9dd4a4fb133a42bd1cf2ec0615bca64f1299e5568e7d392e21f82c8d12943bc` |
| `forex_bot/research/learning/timeframes.py` | `a482ef747fb28a9d1a4409c8d67b67811147afaedd0b487c52f2e9730f734676` |
| `forex_bot/research/learning/regimes.py` | `f3d2ffdbe77e17808e30b3d034b5b681fd631426349dbbd107c4f4c83cfdc0ea` |
| `forex_bot/research/learning/protocol.py` | `5c1038ca6e11f79820f2063f81f83fbf58cb87f617fc3d9ec2f412f32534b0fc` |
| `forex_bot/research/decision_journal.py` | `793b92f35d2c2a7565ff3a6cbbe3229cbfabfcc2828250c6a3f2016eef5cd3c0` |
| `forex_bot/research/ml_prediction.py` | `97ba722204734b480ecc610cc26756a42cabafb9d4ded81070ced146580bd7bc` |
| `forex_bot/research/learning/supervised.py` | `164e13853c6bbc4400dec7e4346e83b4977768fc27a0adef886b033c77660347` |
| `forex_bot/research/learning/diagnosis.py` | `07c0acf894fa7418b1469b68cd82a680a9e3972b06f96aaafff2660105150680` |
| `tests/test_r41_structure.py` | `ffd0a4c9c51da94eddbbdac64da45ada5a0448df17f7aeb24c758f69b577d6fb` |

`bot_loop.py` and `ai_ensemble.py` do not import `learning.lifecycle` or `apply_lifecycle`.

## Evidence scripts

| File | SHA-256 |
| --- | --- |
| `data/research/adaptive_ensemble/r42/03_protocol.json` | `da8f53c0f8b89037ab00721f4c0a3b8d7c322d6da692e37a2b3f142a643c6b27` |
| `data/research/adaptive_ensemble/r42/00_preflight.py` | `dfac45abf3c7fdf3decd54b65b99809bbbf468727467dc10c0ac8ca67a1ffd5e` |
| `data/research/adaptive_ensemble/r42/04_run_lifecycle.py` | `e0cb6e9186d67a9e23aab92a87859a81dccbc30bcbd6eea891da94cea2aef6fe` |
| `data/research/adaptive_ensemble/r42/20_run_offline_tests.py` | `3abedc215f7e3c94d4fc7b2b2eb8f7dbed64fb4fb6a8a8803972fbf72bd84db6` |

R.24–R.41 evidence files were not modified.
