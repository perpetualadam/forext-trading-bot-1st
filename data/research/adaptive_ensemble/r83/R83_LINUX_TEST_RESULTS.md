# R.83 Linux test results

Platform: Linux under WSL. CPython 3.12.3 from `$HOME/r79-disposable-venv`. `TMPDIR=/tmp`. No packages were installed.

## Final R.83 suite

Command:

`TMPDIR=/tmp "$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r83/poc/test_r83_post_commit_and_sqlite.py`

| Item | Result |
| --- | --- |
| Exit code | 0 |
| Passed | 14 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Runtime | 17.699 seconds |

The same four injected authority-read faults are in this run. An earlier sweep of the previous 14-test body passed in 20.242 seconds.

## Historical sweep

| Suite | Passed | Failed | Errors | Skipped | Runtime |
| --- | --- | --- | --- | --- | --- |
| R.82 | 19 | 0 | 0 | 0 | 20.798s |
| R.81 | 16 | 0 | 0 | 0 | 35.148s |
| R.80 | 17 | 0 | 0 | 0 | 15.862s |
| R.79 | 17 | 0 | 0 | 0 | 5.505s |
| R.78 | 21 | 0 | 0 | 0 | 4.210s |
| R.77 atomic | 82 | 2 | 3 | 0 | 15.341s of 87 |
| R.77 journal | 0 | 1 | 1 | 0 | 0.500s of 2 |
| R.76 | 64 | 6 | 2 | 0 | 21.097s of 72 |
| R.75 | 10 | 3 | 0 | 0 | 8.297s of 13 |
| R.74 operational | 3 | 6 | 0 | 0 | 1.137s of 9 |
| R.74 journal | 20 | 0 | 0 | 0 | 2.669s |
| R.73 | 8 | 21 | 2 | 0 | 5.210s of 31 |
| R.72 | 36 | 1 | 0 | 0 | 0.200s of 37 |
| R.71 | 8 | 0 | 0 | 0 | 0.016s |
| R.70 | 25 | 1 | 0 | 0 | 7.660s of 26 |
| R.69 | 44 | 3 | 0 | 1 | 4.828s of 48 |
| R.68 | 27 | 2 | 1 | 1 | 0.219s of 31 |

The Linux counts match the Windows historical counts. The R.74 journal suite still passes with the stale-owner removal fence, because that fence returns only when a fencing epoch exists.
