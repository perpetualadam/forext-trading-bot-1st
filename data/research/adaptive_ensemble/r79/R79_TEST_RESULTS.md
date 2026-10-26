# R.79 Test Results

Evidence class: executed unit and operational tests. Historical suites were not edited.

## R.79

Windows:

```text
python -B data/research/adaptive_ensemble/r79/poc/test_r79_operational_cycle.py
```

17 passed.

Linux:

```text
export TMPDIR=/tmp
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r79/poc/test_r79_operational_cycle.py
```

17 passed.

Linux imports: 18 `IMPORT_PASSED`, `ISOLATION_READY True`.

## Historical

| Suite | Command result | Compared with R.78 |
| --- | --- | --- |
| R.78 Windows | 21 passed | Same |
| R.78 Linux | 21 passed | Same. R.78 Linux was previously WSL without the disposable dependency set. |
| R.77 Windows | 82 passed, 2 failed, 3 errors of 87 | Was 85 passed, 1 failed, 1 error. Three additional failures are the new fence. |
| R.77 Linux journal | 0 passed, 1 failed, 1 error of 2 | Was 1 passed, 1 error. The former pass now fails on `published`. |
| R.76 | 64 passed, 6 failed, 2 errors of 72 | Was 69 passed, 3 failed. |
| R.75 | 10 passed, 3 failed of 13 | Was 13 passed. |
| R.74 journal | 20 passed | Same |
| R.74 operational | 3 passed, 6 failed of 9 | Was 9 passed. |
| R.73 | 8 passed, 21 failed, 2 errors of 31 | Same totals |
| R.72 | 36 passed, 1 failed of 37 | Same totals |
| R.71 | 8 passed | Same |
| R.70 | 25 passed, 1 failed of 26 | Same totals |
| R.69 | 44 passed, 3 failed, 1 skipped of 48 | Same totals |
| R.68 | 27 passed, 2 failed, 1 error, 1 skipped of 31 | Same totals |

None of the suites that contain failures is reported as green.

The R.79 run did not start `main.py`, `run_bot`, or `forex_bot.app`. It did not contact OANDA or PostgreSQL. The consumed marker hash and the absent permit were checked after the suite.
