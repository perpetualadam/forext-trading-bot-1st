# R.41 changed files

Production voting, reinforcement learning, session rules, the bot loop, strategy flags, and the R.39 and R.40 research modules were not edited.

| File | SHA-256 |
| --- | --- |
| `forex_bot/bot_loop.py` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` |
| `forex_bot/ai_ensemble.py` | `1d8e02e334e07b88eefc834e45390a128bebaa078af98e428df081efcf5857fa` |
| `forex_bot/rl_agent.py` | `2f79452b7538e504b4b338c186d137221240d7688bdc26cce185f58405f7043e` |
| `forex_bot/strategy_meta.py` | `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d` |
| `forex_bot/research/learning/structure.py` | `b9dd4a4fb133a42bd1cf2ec0615bca64f1299e5568e7d392e21f82c8d12943bc` |
| `tests/test_r41_structure.py` | `ffd0a4c9c51da94eddbbdac64da45ada5a0448df17f7aeb24c758f69b577d6fb` |
| `data/research/adaptive_ensemble/r41/03_protocol.json` | `8880d210ca38e783c1a2615c50a90688ed75825adf1652e525a5bfe55b60e1d0` |
| `data/research/adaptive_ensemble/r41/04_run_structure.py` | `67d1d29547919f2f7592db196ca4af791275d4366929ce687bd0db978a120906` |
| `data/research/adaptive_ensemble/r41/00_preflight.py` | `13d99587aaa815784d888b6b086125afcd2dfba20c76709f740edd434b328d0b` |

`structure.py` is research-only. It is not imported by `bot_loop.py` or `ai_ensemble.py`. Historical CSV files and R.24–R.40 evidence were left in place.
