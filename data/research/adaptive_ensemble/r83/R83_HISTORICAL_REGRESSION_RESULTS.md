# R.83 historical regression results

Historical files were not modified. The R.83 operational edits are the `ENTRY_FINALISED` guard in `mark_entry` and the epoch fence in `close_confirmed_live_position`.

| Suite | Expected | Windows | Linux | Class |
| --- | --- | --- | --- | --- |
| R.83 | New | 14 passed | 14 passed | Executed on the final suite |
| R.82 | 19/0/0/0 | 19/0/0/0 | 19/0/0/0 | Preserved |
| R.81 | 16/0/0/0 | 16/0/0/0 | 16/0/0/0 | Preserved |
| R.80 | 17/0/0/0 | 17/0/0/0 | 17/0/0/0 | Preserved |
| R.79 | 17/0/0/0 | 17/0/0/0 | 17/0/0/0 | Preserved |
| R.78 | 21/0/0/0 | 21/0/0/0 | 21/0/0/0 | Preserved |
| R.77 atomic | 82 passed, 2 failed, 3 errors of 87 | Same | Same | `PRE_EXISTING_FAILURE` |
| R.77 journal | 0 passed, 1 failed, 1 error of 2 | Same | Same | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.76 | 64/6/2 of 72 | Same | Same | `PRE_EXISTING_FAILURE` |
| R.75 | 10/3 of 13 | Same | Same | `PRE_EXISTING_FAILURE` |
| R.74 operational | 3/6 of 9 | Same | Same | `PRE_EXISTING_FAILURE` |
| R.74 journal | 20/0/0/0 | 20/0/0/0 | 20/0/0/0 | Preserved |
| R.73 | 8/21/2 of 31 | Same | Same | `PRE_EXISTING_FAILURE` |
| R.72 | 36/1 of 37 | Same | Same | `PRE_EXISTING_FAILURE` |
| R.71 | 8/0/0/0 | Same | Same | Preserved |
| R.70 | 25/1 of 26 | Same | Same | `PRE_EXISTING_FAILURE` |
| R.69 | 44/3/0/1 of 48 | Same | Same | `PRE_EXISTING_FAILURE` |
| R.68 | 27/2/1/1 of 31 | Same | Same | `PRE_EXISTING_FAILURE` |

The R.77 journal failure is the previously recorded contract change: publication now requires a recovery fence, and schema 3 is refused. It does not use negative `tradesClosed` units. No new failure appeared. No old failure was reclassified as a pass.

`NEW_REGRESSION`: none.
