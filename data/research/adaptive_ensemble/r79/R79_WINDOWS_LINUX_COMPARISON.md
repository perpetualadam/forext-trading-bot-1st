# R.79 Windows and Linux Comparison

Evidence class: executed tests.

| Suite | Windows | Linux disposable venv |
| --- | --- | --- |
| R.79 operational cycle | 17 passed | 17 passed |
| R.79 import audit | Not required; Windows already imports these modules | 18 `IMPORT_PASSED` |
| R.78 liveness and protocol | 21 passed | 21 passed |
| R.77 atomic entry | 82 passed, 2 failed, 3 errors of 87 | Linux journal file: 0 passed, 1 failed, 1 error of 2. The failure is the new memory-publication assertion. The error is the existing schema-5 open of a version-4 file. |
| R.76 | 64 passed, 6 failed, 2 errors of 72 | Not re-run. Windows result is the regression record. |
| R.75 | 10 passed, 3 failed of 13 | Not re-run. |
| R.74 journal | 20 passed | Not re-run. |
| R.74 operational close | 3 passed, 6 failed of 9 | Not re-run. |
| R.73 | 8 passed, 21 failed, 2 errors of 31 | Not re-run. |
| R.72 | 36 passed, 1 failed of 37 | Not re-run. |
| R.71 | 8 passed | Not re-run. The module imported on Linux. |
| R.70 | 25 passed, 1 failed of 26 | Not re-run. |
| R.69 | 44 passed, 3 failed, 1 skipped of 48 | Not re-run. |
| R.68 | 27 passed, 2 failed, 1 error, 1 skipped of 31 | Not re-run. |

Linux journals used `/tmp`. Windows journals used the process temporary directory. The same test file produced the same 17 passing R.79 results. No Linux-only import failure remained.

The Linux cycle printed the same synthetic account-summary rejection and candle skip as Windows, then completed the real cycle.
