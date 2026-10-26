# R.86 Test Matrix

Windows and Linux both executed this module. A PASS means the condition was exercised. Synthetic bodies are not live broker proof. `COMPLETE_VERIFIED` was not granted by an optimistic label.

| # | Scenario | Test | Result |
| --- | --- | --- | --- |
| 1 | Archive integrity | `test_01` | PASS |
| 2 | Operational hashes | `test_02` | PASS |
| 3 | Gates disabled | `test_03` | PASS |
| 4 | Permit absent | `test_04` | PASS |
| 5 | Marker unchanged | `test_05` | PASS |
| 6 | Network isolation | `test_06` | PASS |
| 7 | Valid source identity | `test_07` | PASS |
| 8 | Missing source identity | `test_08` | PASS |
| 9 | Wrong account | `test_09` | PASS |
| 10 | Missing timestamp | `test_10` | PASS |
| 11 | Controlled timestamp | `test_11` | PASS |
| 12 | Stale epoch | `test_12` | PASS |
| 13 | Retrieval failure | `test_13` | PASS |
| 14 | Malformed response | `test_14` | PASS |
| 15 | Unknown completeness | `test_15` | PASS |
| 16 | Explicit incomplete | `test_16` | PASS |
| 17 | Empty unknown completeness | `test_17` | PASS |
| 18 | Empty verified-complete | `test_18` | PASS as unsupported. Not labelled complete |
| 19 | Pagination incomplete | `test_19`, `test_51` | PASS for supplied records. Adapter support NOT_VERIFIED |
| 20 | Duplicate page or trade | `test_20` | PASS |
| 21 | Inconsistent accounts | `test_21` | PASS |
| 22 | Stale cache | `test_22` | PASS |
| 23 | Snapshot before close | `test_23` | PASS |
| 24 | Snapshot after close without watermark | `test_24` | PASS |
| 25 | Active manageable exposure | `test_25` | PASS |
| 26 | Partial quarantine 400/1000 | `test_26` | PASS |
| 27 | Broker observed 600 unverified | `test_27` | PASS |
| 28 | Broker observed 1000 | `test_28` | PASS |
| 29 | Broker observed empty | `test_29` | PASS |
| 30 | Conflicting direction | `test_30` | PASS |
| 31 | Wrong trade id | `test_31` | PASS |
| 32 | Full close confirmed | `test_32` | PASS |
| 33 | Full close conflicting snapshot | `test_33` | PASS |
| 34 | Ambiguous close | `test_34` | PASS |
| 35 | Missing observation | `test_35` | PASS |
| 36 | Unknown exposure explicit | `test_36` | PASS |
| 37 | Quarantined units visible | `test_37` | PASS |
| 38 | No double counting | `test_38` | PASS |
| 39 | Two instruments | `test_39` | PASS |
| 40 | Two trades one instrument | `test_40` | PASS |
| 41 | Opposite directions | `test_41` | PASS |
| 42 | No cross-currency raw total | `test_42` | PASS |
| 43 | Reporting read-only | `test_43` | PASS |
| 44 | No journal mutation | `test_44` | PASS |
| 45 | No quarantine release | `test_45` | PASS |
| 46 | No position-book mutation | `test_46` | PASS |
| 47 | No second close or order in the cycle | `test_57`, `test_58` | PASS |
| 48 | Genuine operational cycle | `test_57`, `test_58` | PASS |
| 49 | Ratchet unchanged | `test_57` | PASS |
| 50 | Profit-protection hash | `test_49` | PASS |
| 51 | Malformed input unavailable | `test_50` | PASS |
| 52 | Page failure, loop, unexpected token | `test_52` | PASS |
| 53 | Supplied pages never verified complete | `test_53` | PASS |
| 54 | SELL and USD_JPY shapes | `test_54` | PASS |
| 55 | Active beside quarantined | `test_55` | PASS |
| 56 | Stale owner report | `test_56` | PASS |
| 57 | Future timestamp | `test_47` | PASS |
| 58 | Watermark absent | `test_48` | PASS |
