# R.84 Linux test results

Platform: Linux under WSL. CPython 3.12.3 from `$HOME/r79-disposable-venv`. `TMPDIR=/tmp`. No packages were installed.

## R.84

Command: `TMPDIR=/tmp "$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r84/poc/test_r84_close_contract.py`

| Item | Result |
| --- | --- |
| Exit code | 0 |
| Passed | 12 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Runtime | 13.639 seconds |

## Historical sweep

| Suite | Passed | Failed | Errors | Skipped | Runtime |
| --- | --- | --- | --- | --- | --- |
| R.83 | 13 | 1 | 0 | 0 | 18.209s of 14 |
| R.82 | 18 | 1 | 0 | 0 | 18.440s of 19 |
| R.81 | 16 | 0 | 0 | 0 | 30.899s |
| R.80 | 17 | 0 | 0 | 0 | 17.671s |
| R.79 | 17 | 0 | 0 | 0 | 5.821s |
| R.78 | 21 | 0 | 0 | 0 | 3.757s |
| R.77 atomic | 82 | 2 | 3 | 0 | 16.907s of 87 |
| R.77 journal | 0 | 1 | 1 | 0 | 0.490s of 2 |
| R.76 | 64 | 6 | 2 | 0 | 21.990s of 72 |
| R.75 | 10 | 3 | 0 | 0 | 8.685s of 13 |
| R.74 operational | 3 | 6 | 0 | 0 | 1.104s of 9 |
| R.74 journal | 20 | 0 | 0 | 0 | 2.702s |
| R.73 | 8 | 21 | 2 | 0 | 5.231s of 31 |
| R.72 | 36 | 1 | 0 | 0 | 0.153s of 37 |
| R.71 | 8 | 0 | 0 | 0 | 0.017s |
| R.70 | 25 | 1 | 0 | 0 | 7.645s of 26 |
| R.69 | 44 | 3 | 0 | 1 | 4.852s of 48 |
| R.68 | 27 | 2 | 1 | 1 | 0.196s of 31 |

The Linux counts match the Windows counts.
