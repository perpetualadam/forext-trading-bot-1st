# R.69 cross-platform report

| Host | Python | Command | Result |
| --- | --- | --- | --- |
| Windows 10.0.26300 | CPython 3.13.5 | `python -B data/research/adaptive_ensemble/r69/poc/test_r69_integration.py` | 48 tests, 0 failures, 1 skipped, 5.395s |
| WSL2 `6.6.87.2-microsoft-standard-WSL2` | CPython 3.12.3 | `python3 -B data/research/adaptive_ensemble/r69/poc/test_r69_integration.py` | Import stopped. `ModuleNotFoundError: oandapyV20` |

WSL module check: `requests` is present. `pandas`, `numpy`, `oandapyV20`, and `psycopg2` are absent. The harness can stub a missing `psycopg2` with a connect function that raises. It cannot supply `pandas` or `oandapyV20` without changing what the management math and the broker endpoint objects are. Those packages were not installed.

No Linux execution of `reconcile_positions_log_only` or `_evaluate_impl` is claimed. No concurrency difference on Linux was measured. WSL2 is not a VPS result.

After the Windows run, the four R.68 operational hashes still match. The WSL process exited during import and did not write those files.
