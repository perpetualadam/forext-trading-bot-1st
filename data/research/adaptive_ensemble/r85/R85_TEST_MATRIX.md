# R.85 Test Matrix

A row is PASS only when that condition was executed. Synthetic snapshot labels are identified as synthetic. Windows and Linux both passed every R.85 row.

| # | Scenario | Test | Result |
| --- | --- | --- | --- |
| 1 | R.84 baseline integrity for unchanged files and gates | `test_01` | PASS |
| 2 | Safety gates unchanged, permit absent | `test_01`, `test_02` | PASS |
| 3 | Original, journal, and memory units distinguished | `test_03` | PASS |
| 4 | Partial 400/1000 baseline | `test_04` | PASS |
| 5 | Complete synthetic snapshot showing 600 | `test_05` | PASS, still quarantined as `units_mismatch` |
| 6 | Complete synthetic snapshot showing 1000 | `test_06` | PASS |
| 7 | Complete synthetic snapshot showing 400 | `test_07` | PASS |
| 8 | Complete synthetic snapshot showing zero | `test_08` | PASS |
| 9 | Complete synthetic snapshot showing 1200 | `test_09` | PASS |
| 10 | Wrong direction | `test_10` | PASS |
| 11 | Empty complete snapshot | `test_11` | PASS |
| 12 | Empty incomplete snapshot | `test_12` | PASS |
| 13 | Missing target trade | `test_13` | PASS |
| 14 | Wrong account | `test_14` | PASS |
| 15 | Wrong instrument | `test_15` | PASS |
| 16 | Wrong trade id | `test_16` | PASS |
| 17 | Stale label | `test_17` | PASS for the label. Freshness calculation NOT_VERIFIED |
| 18 | Snapshot retrieval failure | `test_18` | PASS |
| 19 | Incomplete pagination | `test_19` | PARTIAL. `INCOMPLETE` is refused. No pagination flag exists |
| 20 | Duplicate broker trade records | `test_20` | PASS |
| 21 | Multiple unrelated trades | `test_21` | PASS |
| 22 | BUY partial close | `test_22` | PASS |
| 23 | SELL partial close | `test_23` | PASS |
| 24 | USD_JPY partial close | `test_24` | PASS |
| 25 | Original-unit consumer audit | `test_25` plus source audit | PASS |
| 26 | No overstatement of manageable exposure | `test_26` | PASS |
| 27 | No automatic quarantine release | `test_27` | PASS |
| 28 | Release evidence contract | `test_28` and the contract report | PASS as documentation. Release was not implemented |
| 29 | Entry publication race | `test_29` | PASS |
| 30 | Close removal race | `test_30` | PASS |
| 31 | Real successor takeover | `test_31` | PASS |
| 32 | Synthetic epoch change, distinguished | `test_32` | PASS |
| 33 | Durable entry finalisation preserved | `test_33` | PASS |
| 34 | Durable full close preserved | `test_34` | PASS |
| 35 | No duplicate OrderCreate | `test_35` | PASS |
| 36 | No duplicate PositionClose | `test_36` | PASS |
| 37 | Full close, conflicting snapshot | `test_37` | PASS |
| 38 | Full close, incomplete snapshot | `test_38` | PASS |
| 39 | Ambiguous close, original units | `test_39` | PASS |
| 40 | Ambiguous close, reduced units | `test_40` | PASS |
| 41 | Ambiguous close, flat and related snapshots | `test_41` | PASS |
| 42 | Duplicate transaction replay | `test_42` | PASS |
| 43 | Conflicting transaction replay | `test_43` | PASS |
| 44 | Genuine operational cycle | `test_44` | PASS |
| 45 | Profit-protection ratchet | `test_45` | PASS |
| 46 | Process termination cannot finalise | `test_46` | PASS |
| 47 | Signed-unit contract sample | `test_47` | PASS |
| 48 | Positive fill with negative reduction rejected | `test_48` | PASS |

`COMPLETE` means the test passed the snapshot label into recovery. It does not mean the live fetch proved completeness.
