# R.82 Linux test results

Interpreter: CPython 3.12.3 at `$HOME/r79-disposable-venv/bin/python`. `TMPDIR=/tmp`. No packages were installed.

Final R.82 command:

`TMPDIR=/tmp $HOME/r79-disposable-venv/bin/python -B data/research/adaptive_ensemble/r82/poc/test_r82_journal_and_exposure.py`

Exit 0. 19 passed, 0 failed, 0 errors, 0 skipped. Suite time 18.212s. Process wall time 26.307s.

An earlier Linux pass of the same file, taken before `test_19` was added, was 18 passed in 21.008s. The 19-test run is the one cited above.

| Suite | Exit | Tests | Passed | Failed | Errors | Skipped | Suite time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R.82 final | 0 | 19 | 19 | 0 | 0 | 0 | 18.212s |
| R.81 | 0 | 16 | 16 | 0 | 0 | 0 | 35.671s |
| R.80 | 0 | 17 | 17 | 0 | 0 | 0 | 17.105s |
| R.79 | 0 | 17 | 17 | 0 | 0 | 0 | 5.772s |
| R.78 | 0 | 21 | 21 | 0 | 0 | 0 | 3.847s |
| R.77 atomic | 1 | 87 | 82 | 2 | 3 | 0 | 14.862s |
| R.77 journal file | 1 | 2 | 0 | 1 | 1 | 0 | 0.522s |
| R.76 | 1 | 72 | 64 | 6 | 2 | 0 | 21.095s |
| R.75 | 1 | 13 | 10 | 3 | 0 | 0 | 8.313s |
| R.74 operational | 1 | 9 | 3 | 6 | 0 | 0 | 1.065s |
| R.74 journal | 0 | 20 | 20 | 0 | 0 | 0 | 2.539s |
| R.73 | 1 | 31 | 8 | 21 | 2 | 0 | 5.210s |
| R.72 | 1 | 37 | 36 | 1 | 0 | 0 | 0.160s |
| R.71 | 0 | 8 | 8 | 0 | 0 | 0 | 0.017s |
| R.70 | 1 | 26 | 25 | 1 | 0 | 0 | 7.646s |
| R.69 | 1 | 48 | 44 | 3 | 0 | 1 | 4.880s |
| R.68 | 1 | 31 | 27 | 2 | 1 | 1 | 0.231s |

Linux assertions match the Windows R.82 cases: no write when authority cannot be verified, one write when the final-check race is released, partial close remaining 600, restart `manageable=0`, and `cycle=1`.
