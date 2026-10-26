# R.81 coverage equivalence matrix

Historical files were not edited. A row is equivalent only when the executed R.81 test exercises the same safety property.

| Historical gap at R.80 | R.81 test | Class |
| --- | --- | --- |
| R.74 `test_rejection_can_reserve_a_new_operation` | `test_11` | EQUIVALENT_COVERAGE. The missing R.80 row is now executed under recovery authority |
| R.74 partial close | `test_12` | EQUIVALENT_COVERAGE |
| R.74 flat snapshot does not confirm a close | `test_14` | EQUIVALENT_COVERAGE |
| R.74 timeout across reopen | `test_14` plus close crash successors | STRONGER_COVERAGE. Fresh processes and process kills |
| R.75 two-process close and paused claim | R.80 `test_12` still passes, and R.81 crash tests add the kill windows | STRONGER_COVERAGE |
| R.76 ambiguous entry and reservation race | `test_13` and `test_10`, with R.80 `test_10` still passing | EQUIVALENT_COVERAGE for the race, STRONGER_COVERAGE for the fresh-process restart |
| R.77 client id, atomic finalisation, post-submit journal fault | `test_04` and `test_15` | EQUIVALENT_COVERAGE |
| R.77 ratchet on a recovered row | R.80 `test_16` rerun and `test_16` parameter check | EQUIVALENT_COVERAGE |
| Rate-limit window after the R.80 check | `test_02` and `test_03` | STRONGER_COVERAGE. This window was not in the historical tests |

`R81_HISTORICAL_COVERAGE_IMPROVED`: PASS. The R.80 `MISSING_COVERAGE` rejection case now has an executed replacement. Historical suites that still fail are not green.
