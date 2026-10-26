# R.83 Windows test results

Platform: Windows. CPython 3.13.5.

## Final R.83 suite

Command:

`python -B data/research/adaptive_ensemble/r83/poc/test_r83_post_commit_and_sqlite.py`

| Item | Result |
| --- | --- |
| Exit code | 0 |
| Passed | 14 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Runtime | 16.506 seconds |

This is the suite after `test_11` injected both `database is locked` and `database table is locked` on OrderCreate and on PositionClose. An earlier sweep of the same 14 tests, before that extra pair, passed in 18.249 seconds. The operational modules did not change between those runs.

## Historical sweep on the same machine

Command form: `python -B <suite>`. Counts:

| Suite | Passed | Failed | Errors | Skipped | Runtime |
| --- | --- | --- | --- | --- | --- |
| R.82 | 19 | 0 | 0 | 0 | 15.282s |
| R.81 | 16 | 0 | 0 | 0 | 30.958s |
| R.80 | 17 | 0 | 0 | 0 | 14.617s |
| R.79 | 17 | 0 | 0 | 0 | 4.884s |
| R.78 | 21 | 0 | 0 | 0 | 2.253s |
| R.77 atomic | 82 | 2 | 3 | 0 | 6.441s of 87 |
| R.77 journal | 0 | 1 | 1 | 0 | 0.414s of 2 |
| R.76 | 64 | 6 | 2 | 0 | 13.097s of 72 |
| R.75 | 10 | 3 | 0 | 0 | 7.731s of 13 |
| R.74 operational | 3 | 6 | 0 | 0 | 0.654s of 9 |
| R.74 journal | 20 | 0 | 0 | 0 | 1.899s |
| R.73 | 8 | 21 | 2 | 0 | 5.074s of 31 |
| R.72 | 36 | 1 | 0 | 0 | 0.056s of 37 |
| R.71 | 8 | 0 | 0 | 0 | 0.004s |
| R.70 | 25 | 1 | 0 | 0 | 7.730s of 26 |
| R.69 | 44 | 3 | 0 | 1 | 4.557s of 48 |
| R.68 | 27 | 2 | 1 | 1 | 0.181s of 31 |

Fresh OS processes were used for the entry kill, the close kill, the partial kill, and the successor startups. The operational cycle in the partial-close successor is `_execute_bot_cycle`. `run_bot` was not executed.
