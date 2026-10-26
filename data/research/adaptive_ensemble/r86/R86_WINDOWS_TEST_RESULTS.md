# R.86 Windows Test Results

Platform: Windows. CPython `3.13.5` (MSC v.1943). Log: `R86_WINDOWS_REGRESSION.log`. Recorded `2026-10-26T14:08:58Z`.

| Suite | Result | Test time | Elapsed |
| --- | --- | --- | --- |
| R.86 | 58 passed | 0.551s | 1.768s |
| R.85 | 48 passed | 14.833s | 16.193s |
| R.84 | 11 passed, 1 failed | 10.975s | 12.440s |
| R.83 | 13 passed, 1 failed | 16.457s | 18.189s |
| R.82 | 18 passed, 1 failed | 15.701s | 17.119s |
| R.81 | 15 passed, 1 failed | 31.364s | 32.910s |
| R.80 | 17 passed | 14.244s | 15.808s |
| R.79 | 17 passed | 4.977s | 6.478s |
| R.78 | 21 passed | 2.187s | 2.452s |
| R.77 atomic | 82 passed, 2 failed, 3 errors | 7.407s | 8.857s |
| R.77 journal | 0 passed, 1 failed, 1 error | 0.321s | 0.717s |
| R.76 | 64 passed, 6 failed, 2 errors | 13.212s | 14.601s |
| R.75 | 10 passed, 3 failed | 7.696s | 8.970s |
| R.74 operational | 3 passed, 6 failed | 0.729s | 1.947s |
| R.74 journal | 20 passed | 1.904s | 2.326s |
| R.73 | 8 passed, 21 failed, 2 errors | 5.101s | 6.338s |
| R.72 | 36 passed, 1 failed | 0.056s | 1.310s |
| R.71 | 8 passed | 0.002s | 1.147s |
| R.70 | 25 passed, 1 failed | 7.667s | 8.703s |
| R.69 | 44 passed, 3 failed, 1 skipped | 4.557s | 5.814s |
| R.68 | 27 passed, 2 failed, 1 error, 1 skipped | 0.159s | 0.328s |

The Windows process exit is nonzero because R.68 still fails. That suite was already failing before R.86. R.86 itself exited clean.
