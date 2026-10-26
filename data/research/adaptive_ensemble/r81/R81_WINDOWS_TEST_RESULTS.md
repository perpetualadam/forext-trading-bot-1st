# R.81 Windows test results

Interpreter: CPython 3.13.5. Operating system: Windows. Journals: disposable temporary SQLite files. No OANDA request. No PostgreSQL connection. No credential read. No production journal. No live permit.

Final R.81 command, after the refusal re-raise:

```text
python -B data/research/adaptive_ensemble/r81/poc/test_r81_rate_limit_and_recovery.py
```

Result: 16 passed, 0 failed, 0 errors, 0 skipped, 25.501s. Exit code 0.

The pre-fix rate-limit commands are recorded in `R81_RATE_LIMITER_PRE_FIX_REPRODUCTION.md`. Both failed closed-safety assertions before the fix and pass after it.

| Suite | Result | Runtime |
| --- | --- | --- |
| R.81 final | 16 passed | 25.501s |
| R.80 | 17 passed | 15.763s |
| R.79 | 17 passed | 4.847s |
| R.78 | 21 passed | 2.080s |
| R.71 | 8 passed | 0.003s |

The R.81 file executed real startup, the real close and entry sinks, separate processes, process kills, repair, and fresh-process restarts. Synthetic OrderCreate and PositionClose calls occurred only on the paths that still held authority, or were blocked before `api.request` when authority had changed. Durable permits that were claimed stayed consumed.

`R81_R80_REGRESSION_PRESERVED`: PASS.
`R81_R79_REGRESSION_PRESERVED`: PASS.
`R81_R78_REGRESSION_PRESERVED`: PASS.
