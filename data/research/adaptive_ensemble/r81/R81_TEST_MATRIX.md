# R.81 test matrix

Windows final run: 16 passed. Linux run: 16 passed. A source argument is not marked PASS.

| # | Scenario | Result | Evidence |
| --- | --- | --- | --- |
| 1 | R.80 baseline integrity | PASS | Archive, hashes, gates, marker, permit |
| 2 | Entry authority loss during rate-limit wait, pre-fix | PASS | Recorder count 1 before the fix. The defect was reproduced |
| 3 | Close authority loss during rate-limit wait, pre-fix | PASS | Recorder count 1 and `CLOSE_FULLY_CONFIRMED` before the fix |
| 4 | Entry authority loss during rate-limit wait, post-fix | PASS | `test_02` |
| 5 | Close authority loss during rate-limit wait, post-fix | PASS | `test_03` |
| 6 | Valid entry still submits once | PASS | `test_04` |
| 7 | Valid close still submits once | PASS | `test_04` |
| 8 | Entry permit stays consumed after authority loss | PASS | `test_02` |
| 9 | Close permit stays consumed after authority loss | PASS | `test_03` |
| 10 | Close-owner kill before request | PASS | `test_05` |
| 11 | Close-owner kill during request before acceptance | PASS | `test_06` |
| 12 | Close-owner kill during request after acceptance | PASS | `test_07` |
| 13 | Successor cannot resubmit crashed close | PASS | `test_05`, `test_06`, `test_07` |
| 14 | Repair refused while owner alive | PASS | `test_08` |
| 15 | Repair permitted only after verified owner death | PASS | `test_09` |
| 16 | Stale owner entry refused | PASS | `test_10` |
| 17 | Stale owner close refused | PASS | `test_10` |
| 18 | Confirmed rejection recorded durably | PASS | `test_11` |
| 19 | New close operation after definitive rejection | PASS | `test_11` |
| 20 | Ambiguous close cannot re-reserve | PASS | `test_12` |
| 21 | Partial close remains partial | PASS | `test_12` |
| 22 | Flat snapshot cannot confirm close | PASS | `test_14` |
| 23 | Entry timeout survives fresh restart | PASS | `test_13` |
| 24 | Entry journal fault survives fresh restart | PASS | `test_15` |
| 25 | Ambiguous entry cannot reuse client ID | PASS | `test_13`, `test_15` |
| 26 | Ambiguous close survives fresh restart | PASS | `test_14` |
| 27 | Ambiguous close cannot resubmit | PASS | `test_14` |
| 28 | Journal fault after rate-limit acquisition | NOT_VERIFIED | The executed post-slot fault is epoch loss, not a dropped journal |
| 29 | Journal fault after request acceptance | PASS | `test_15` |
| 30 | Entry finalisation remains atomic | PASS | `test_04` |
| 31 | Close confirmation remains evidence-bound | PASS | `test_07`, `test_14` |
| 32 | Recovered-position profit protection | PASS | `test_16` and the R.80 `test_16` rerun |
| 33 | R.80 regression | PASS | 17 passed on Windows and Linux |
| 34 | R.79 and R.78 regression | PASS | 17 and 21 passed on both platforms |
| 35 | Historical coverage-equivalence review | PASS | Matrix. Historical suites are not green |

Rows 2 and 3 use PASS to mean the unsafe pre-fix behaviour was executed and recorded.
