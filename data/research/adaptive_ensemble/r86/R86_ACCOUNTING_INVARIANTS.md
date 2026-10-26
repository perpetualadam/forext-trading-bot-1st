# R.86 Accounting Invariants

Evidence: the R.86 tests named beside each invariant. All of these were executed.

| # | Invariant | Result |
| --- | --- | --- |
| 1 | Unknown is not zero | `test_35`, `test_36`, `test_50`. Units are null |
| 2 | Incomplete is not complete | `test_16`, `test_19` |
| 3 | Stale is not fresh | `test_22`, `test_23`, `test_47` |
| 4 | Journal remainder is not broker proof | `test_27`. Quality text records that |
| 5 | Original units are not current units after a partial close | `test_26`. Original 1000, remainder 600 |
| 6 | Managed units exclude quarantine | `test_37` |
| 7 | Quarantine is visible | `test_37` |
| 8 | Broker observations are separate | `test_27`, `test_28` |
| 9 | Duplicate identity is not double-counted | `test_20`, `test_38` |
| 10 | Wrong account is not a verified total | `test_09`, `test_21` |
| 11 | Wrong instrument is not merged | `test_39` |
| 12 | Opposite directions are not netted | `test_41` |
| 13 | Full close does not create a negative remainder | `test_32` |
| 14 | Ambiguous close does not invent confirmed units | `test_34` |
| 15 | Reporting does not change authority | `test_56`. `authoritative_current` false |
| 16 | Reporting submits no orders | `test_43`, `broker_requests` 0 |
| 17 | Reporting does not release permits | Cycle test permit stayed absent. The report has no permit API |
| 18 | Reporting does not change ratchets | Cycle test ratchet stayed 40. The report has no ratchet field |
| 19 | Reporting does not clear quarantine | `test_45` |
| 20 | Reporting does not make a quarantined position manageable | `test_45` |

No property-based library was installed. The cases are deterministic.
