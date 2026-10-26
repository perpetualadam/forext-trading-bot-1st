# R.80 coverage equivalence matrix

A replacement counts only when the executed test exercises the original safety property. Reaching the same function is not enough.

| Property | Historical source | R.80 evidence | Class |
| --- | --- | --- | --- |
| One close submission under recovery authority | R.75 stale/repeat test, R.74 full fill | `test_01` | EQUIVALENT_COVERAGE |
| Stale close permit refused | R.75 | `test_01` | EQUIVALENT_COVERAGE |
| Repeat close does not submit again | R.75 | `test_01` call count stays 1. The second call returns the existing confirmed row | EQUIVALENT_COVERAGE |
| Ambiguous close is not retried | R.74 timeout, R.76 test 46 | `test_02` | EQUIVALENT_COVERAGE |
| Missing trade id blocks close | R.74 / close guard | `test_03` | EQUIVALENT_COVERAGE |
| Observation-only close refused | R.68 / R.75 | `test_03` | EQUIVALENT_COVERAGE |
| Wrong account binding refused | R.74 / recovery | `test_03` permit and `test_15` snapshot | EQUIVALENT_COVERAGE |
| Two-process close submits at most once | R.75 two-process test | `test_12` | STRONGER_COVERAGE |
| Pause after close claim blocks the competitor | R.75 pause test | `test_12` reads `network_permit=1` during the barrier | EQUIVALENT_COVERAGE |
| Entry reservation before any request | R.76 test 17 | `test_04` | EQUIVALENT_COVERAGE |
| One-shot entry permit | R.76 / R.77 | `test_04` | EQUIVALENT_COVERAGE |
| Two processes, one client reservation | R.76 test 20 | `test_10` | EQUIVALENT_COVERAGE |
| Authorised entry pauses, competitor cannot submit | R.76 test 20 | `test_11` | STRONGER_COVERAGE |
| Post-request journal fault stays ambiguous | R.77 test 25 | `test_05` | EQUIVALENT_COVERAGE |
| Partial fill is not a managed entry | R.77 | `test_06` | EQUIVALENT_COVERAGE |
| Mixed reduce/close effect is not a managed entry | R.77 | `test_06` | EQUIVALENT_COVERAGE |
| Order id is not a trade id | R.78 | `test_06` | EQUIVALENT_COVERAGE |
| Atomic finalisation and restart | R.77 test 01 | `test_07` | EQUIVALENT_COVERAGE |
| Permanent client-id refusal | R.77 | `test_07` | EQUIVALENT_COVERAGE |
| Authority lost before the request sends nothing | New R.80 requirement | `test_08` | STRONGER_COVERAGE |
| Authority lost inside the request does not create a second request | New R.80 requirement | `test_09` | STRONGER_COVERAGE |
| Crash during the request does not authorise a successor submit | R.76 / R.77 crash cases | `test_13` | EQUIVALENT_COVERAGE |
| Several managed trades recover in the real cycle | New R.80 requirement | `test_14` | STRONGER_COVERAGE |
| Broker-only and manual trades stay unmanaged | R.76 / R.78 | `test_14` | EQUIVALENT_COVERAGE |
| Conflicting account quarantines one row | R.76 | `test_15` | EQUIVALENT_COVERAGE |
| Profit protection on a recovered live row, including the ratchet | R.71 and R.77 test 12 | `test_16` | EQUIVALENT_COVERAGE |
| Journal failure after recovery fails closed | New R.80 requirement | `test_17` | STRONGER_COVERAGE |
| Rejected close may reserve a new operation | R.74 `test_rejection_can_reserve_a_new_operation` | Not rebuilt | MISSING_COVERAGE |
| Explicit repair transaction during an in-flight submit | R.78 repair tests | R.78 suite, not a new in-flight repair interleaving | PARTIAL_COVERAGE |

Historical suites that still fail are not green. The matrix is the coverage record.
