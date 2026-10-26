# R.81 Linux test results

Interpreter: `$HOME/r79-disposable-venv/bin/python`, CPython 3.12.3. No package was installed.
`TMPDIR=/tmp`.

```text
export TMPDIR=/tmp
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r81/poc/test_r81_rate_limit_and_recovery.py
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r80/poc/test_r80_authorised_concurrency.py
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r79/poc/test_r79_operational_cycle.py
"$HOME/r79-disposable-venv/bin/python" -B data/research/adaptive_ensemble/r78/poc/test_r78_liveness_and_protocol.py
```

| Suite | Result | Runtime |
| --- | --- | --- |
| R.81 final source | 16 passed, 0 failed, 0 errors, 0 skipped | 31.587s |
| R.80 | 17 passed | 17.090s |
| R.79 | 17 passed | 5.803s |
| R.78 | 21 passed | 4.201s |

The final R.81 Linux command ran after the refusal re-raise and passed 16 tests in 31.587s. An earlier Linux run of the same file, started while that re-raise was being saved, also passed 16 tests in 33.965s. R.80, R.79, and R.78 were run in that earlier Linux batch.
