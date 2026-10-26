# R.82 historical regression results

Historical files were not modified. Suites that fail stay failed. A newer test does not make an older suite green.

Windows and Linux counts match each other and match the R.81 recorded baseline for the suites R.81 tabulated.

| Suite | Passed | Failed | Errors | Skipped | Class |
| --- | --- | --- | --- | --- | --- |
| R.81 | 16 | 0 | 0 | 0 | Preserved |
| R.80 | 17 | 0 | 0 | 0 | Preserved |
| R.79 | 17 | 0 | 0 | 0 | Preserved |
| R.78 | 21 | 0 | 0 | 0 | Preserved |
| R.77 atomic (87) | 82 | 2 | 3 | 0 | `OBSOLETE_BEHAVIOURAL_EXPECTATION` from recovery fencing. Same count as R.81 |
| R.76 (72) | 64 | 6 | 2 | 0 | `OBSOLETE_BEHAVIOURAL_EXPECTATION`. Same count as R.81 |
| R.75 (13) | 10 | 3 | 0 | 0 | `OBSOLETE_BEHAVIOURAL_EXPECTATION`. Same count as R.81 |
| R.74 operational (9) | 3 | 6 | 0 | 0 | Closes without recovery authority. Same count as R.81 |
| R.74 journal (20) | 20 | 0 | 0 | 0 | Preserved |
| R.73 (31) | 8 | 21 | 2 | 0 | Same count as R.81 |
| R.72 (37) | 36 | 1 | 0 | 0 | Same count as R.81 |
| R.71 (8) | 8 | 0 | 0 | 0 | Preserved |
| R.70 (26) | 25 | 1 | 0 | 0 | Same count as R.81 |
| R.69 (48) | 44 | 3 | 0 | 1 | Same count as R.81 |
| R.68 (31) | 27 | 2 | 1 | 1 | Same count as R.81 |

`test_r77_linux_journal.py` was run as well. It is 1 failure and 1 error on both platforms. The error is the schema-5 opener refusing a schema-3 file. The failure is entry publication without a recovery session. R.81's historical table did not list this two-test module. It is not a new failure of the negative-unit check: that test never passes a negative `tradesClosed` value.

No historical failure was reclassified as a pass.
