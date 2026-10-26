# R.78 test results

Runner dates are 2026-10-25. Commands were `python -B` on Windows and `python3` on WSL. The repository `pytest` entrypoint was not used.

## New suite

`data/research/adaptive_ensemble/r78/poc/test_r78_liveness_and_protocol.py`

- Windows: 21 passed, including the second-startup lock test.
- WSL Ubuntu 24.04: 21 passed. Journals were on ext4 `/tmp`.

Linux import audit: 11 modules imported, 4 blocked by a missing dependency, 0 network attempts. The blocked modules are not counted as operational passes.

## Regressions executed

| Suite | Result |
| --- | --- |
| R.77 Windows `test_r77_atomic_entry.py` | 85 passed, 1 failed, 1 error |
| R.77 journal `test_r77_linux_journal.py` on Windows | 1 passed, 1 error |
| R.76 | 69 passed, 3 failed |
| R.75 | 13 passed |
| R.74 journal | 20 passed |
| R.74 operational | 9 passed |
| R.73 | 8 passed, 21 failed, 2 errors |
| R.72 | 36 passed, 1 failed |
| R.71 | 8 passed |
| R.70 | 25 passed, 1 failed |
| R.69 | 44 passed, 3 failed, 1 skipped |
| R.68 | 27 passed, 2 failed, 1 error, 1 skipped |

The R.77 failure is `test_28_unsupported_schema_fails_closed` asserting `SCHEMA_VERSION == 4`. The R.77 error is `open_journal` after `migrate_journal_3_to_4`, because version 4 is no longer openable. The same error is the R.77 journal suite's second test. Those tests were not rewritten.

No test contacted OANDA. No PostgreSQL connection was opened. `run_bot` and `main.py` were not started.
