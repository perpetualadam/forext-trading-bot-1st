# R.87D offline test results

Runner isolation and source allowlists were inspected before execution. Python 3.13.5 on Windows; -I -S -B, environment cleared, audited source-only reads, no writes inside tests, no application/credential/DB/network imports. Existing barrier sentinels pass. No package installation and no unrestricted application run.

1. python -I -S -B offline_exposure/run_checks.py --concurrency: 10 tests, 10 passed, 0 failures, 0 errors, 0 skipped; 0.009 seconds. focused.log.
2. python -I -S -B offline_exposure/run_checks.py: 57 tests, 57 passed, 0 failures, 0 errors, 0 skipped; 0.025 seconds. complete.log.
3. python -I -S -B offline_exposure/run_checks.py --historical: 48 tests, 48 passed, 0 failures, 0 errors, 0 skipped; 0.013 seconds. historical.log.

These are overlapping selections, not 115 unique tests. There were no seal assertion failures or coordinator failures in these runs. The passing evidence test detects the known local seal mismatch; it does not assert operational seal acceptance. No broad application pytest run was attempted under unverified isolation. Remote pre-existing broad CI failure is separate from these passing offline results. No historical expectations were changed.
