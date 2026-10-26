# R.79 Test Matrix

Evidence class: executed tests unless marked otherwise. Every R.79 test records whether the real `_execute_bot_cycle` ran. The wrapper calls the original function.

| # | Case | Coverage | Cycle executed |
| --- | --- | --- | --- |
| 1 | Clean startup, empty snapshot | `test_01` | Yes |
| 2 | One valid managed trade at startup | Not a pre-seeded startup publish. `test_17` finalises one trade after recovery. | Yes, before the finalisation |
| 3 | Multiple valid managed trades | NOT_VERIFIED as a dedicated R.79 case | No dedicated test |
| 4 | Broker-only trade | `test_10` `broker_only` | Yes |
| 5 | Manual trade | `test_10` `manual` | Yes |
| 6 | Incomplete snapshot | `test_02` | Yes |
| 7 | Unavailable snapshot | `test_10` | Yes |
| 8 | Malformed snapshot | `test_10` | Yes |
| 9 | Ambiguous entry at startup | R.77 passing conflict tests and source. Not a dedicated one-cycle case. | No dedicated test |
| 10 | Ambiguous close at startup | Source and R.76/R.74 historical tests, which now fail without authority. `test_15` covers an authorised close. | Yes, before the close |
| 11 | Partial entry | R.77 remainder. Not a dedicated one-cycle case. | No dedicated test |
| 12 | Missing protection | R.77 remainder. Not a dedicated one-cycle case. | No dedicated test |
| 13 | Stale fencing epoch | `test_05` | Yes |
| 14 | Absent fencing epoch | `test_03` | No. Publication was called directly. |
| 15 | Corrupt journal | `test_14` | Yes |
| 16 | Unsupported schema | `test_09` refuses `open_journal`. Cycle not used. | No |
| 17 | Recovery lock held elsewhere | `test_13` | No. Startup was called directly and blocked. |
| 18 | Startup after operator repair | R.78 `test_12` passed on Windows and Linux. Not the R.79 harness. | R.78 does not call the cycle |
| 19 | Interrupted repair | R.78 repair-failure test passed. A crash inside the repair transaction was not added. | No |
| 20 | Conflicting trade identity | R.77 passing identity tests | No dedicated cycle |
| 21 | Conflicting account binding | Source evaluation path. Not a dedicated R.79 case. | No |
| 22 | Conflicting position instance | R.77 passing instance test | No dedicated cycle |
| 23 | One cycle after successful recovery | `test_01` | Yes |
| 24 | One cycle after blocked recovery | `test_02` | Yes |
| 25 | One cycle after quarantine | `test_10` broker-only and manual. State `RECOVERY_COMPLETED_WITH_QUARANTINE`. Discovered trades were not manageable and were not in `positions`. | Yes |
| 26 | One cycle after authority loss | `test_11` calls the original cycle | Yes |
| 27 | Profit protection with valid authority | R.71 calculations passed. Not invoked from the cycle with an open live position. | The cycle ran without a position to protect |
| 28 | Profit protection with stale authority | The live-management gate returns before that call. Not executed as `apply_profit_protection`. | `test_11` cycle ran |
| 29 | Synthetic entry intercepted | `test_07` and `test_16` | Yes |
| 30 | Synthetic close intercepted | `test_15` one PositionClose, then stale permit refused | Yes |
| 31 | Synthetic protection modification | No broker protection-modify sink exists. OrderCreate stop and take-profit on fill are inside the intercepted OrderCreate. | Not a separate request |
| 32 | Legacy recovery with no epoch | `test_04` | No |
| 33 | Operational publication with no epoch | `test_03` | No |
| 34 | Direct publication with stale epoch | `test_05` | Yes |
| 35 | Entry callback after authority loss | `test_08` without a session. Durable row remains. | No |
| 36 | Two-process recovery ownership | `test_13` and R.78 second-startup test | Startup blocked |
| 37 | Two-process repair ownership | R.78 tests 09 and 10, Windows and Linux | R.78 does not call the cycle |
| 38 | Process restart after committed recovery | `test_12` | Yes, twice |
| 39 | Process restart after failed recovery | Blocked startup leaves management false. A new process after a failed claim is covered by the lock test, not a separate restart case. | Partial |
| 40 | Journal unavailable during a cycle | `test_14` corrupts the journal before startup. A fault during an already authorised evaluation was not armed. | Yes |

A test that replaced `_execute_bot_cycle` was not used.
