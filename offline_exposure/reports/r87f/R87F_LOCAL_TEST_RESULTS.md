# R.87F local test results

Windows 11 build 26300, Python 3.13.5 (MSC 1943 AMD64). Inspected existing runner before execution: -I -S -B, cleared environment, source/stdlib read allowlist, no writes, blocked sockets/subprocess/native loader/application/dotenv/PostgreSQL imports and barrier sentinel verification. No pytest conftest, package installation or application startup.

- python -I -S -B offline_exposure/run_checks.py: 57 tests, 57 passed, 0 failures, 0 errors, 0 skips; exit 0; 0.026s unittest duration. Log local_complete.log.
- python -I -S -B offline_exposure/run_checks.py --concurrency: 10 tests, 10 passed, 0 failures, 0 errors, 0 skips; exit 0; 0.010s unittest duration. Log local_concurrency.log.
- python -I -S -B offline_exposure/run_checks.py --historical: 48 tests, 48 passed, 0 failures, 0 errors, 0 skips; exit 0; 0.013s unittest duration. Log local_historical.log.

These selections overlap and are not 115 unique tests. Each includes isolation sentinels. Parent PowerShell captured logs outside the read-only test process and explicitly propagated each Python exit code. All completed before commit. No local full application pytest run was attempted.
