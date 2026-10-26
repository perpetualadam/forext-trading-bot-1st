# R.80 test matrix

Windows and Linux both executed the R.80 file. A source argument is not marked PASS.

| # | Scenario | Result | Evidence |
| --- | --- | --- | --- |
| 1 | R.79 baseline verification | PASS | Archive, manifest, hashes, gates, marker, permit |
| 2 | Recovery-authorised close once | PASS | `test_01` |
| 3 | Close repeat permit refused | PASS | `test_01` |
| 4 | Close stale permit refused | PASS | `test_01` |
| 5 | Close ambiguous outcome | PASS | `test_02` |
| 6 | Close wrong account | PASS | `test_03`, `test_15` |
| 7 | Close missing trade ID | PASS | `test_03` |
| 8 | Close observation-only | PASS | `test_03` |
| 9 | Close crash before request | NOT_VERIFIED | No close process kill in that window |
| 10 | Close crash after request | NOT_VERIFIED | `test_12` pauses. It does not kill |
| 11 | Two-process close reservation | PASS | `test_12` |
| 12 | Two-process close paused after claim | PASS | `test_12` |
| 13 | Entry intent before request | PASS | `test_04` |
| 14 | Entry one-shot permit | PASS | `test_04` |
| 15 | Two-process entry reservation | PASS | `test_10` |
| 16 | Two-process client-ID collision | PASS | `test_10` |
| 17 | Entry ambiguous timeout | PARTIAL | `test_04` is an exception after the counted call. A `TimeoutError` entry path was not separately asserted |
| 18 | Entry journal fault after request | PASS | `test_05` |
| 19 | Entry atomic finalisation | PASS | `test_07` |
| 20 | Entry permanent client-ID uniqueness | PASS | `test_07` |
| 21 | Entry wrong trade identity | PASS | `test_06` |
| 22 | Entry partial fill | PASS | `test_06` |
| 23 | Entry mixed transaction effects | PASS | `test_06` |
| 24 | Entry restart after commit | PASS | `test_07` |
| 25 | Entry restart after ambiguity | PARTIAL | Same-process refusal in `test_05`. No startup replay of that row |
| 26 | Stale owner entry refusal | PASS | `test_08`, `test_11` |
| 27 | Stale owner close refusal | PASS | `test_01`, `test_12` successor |
| 28 | Multiple managed trades recover | PASS | `test_14` |
| 29 | Conflicting recovered trade quarantined | PASS | `test_15` |
| 30 | Broker-only position remains unmanaged | PASS | `test_14` |
| 31 | Manual position remains unmanaged | PASS | `test_14` |
| 32 | Profit protection BUY | PASS | `test_16` |
| 33 | Profit protection SELL | PASS | `test_16` |
| 34 | Profit protection JPY | PASS | `test_16` |
| 35 | Profit protection 67% activation | PASS | `test_16` triggers 134, 134, and 67 |
| 36 | Profit protection ATR fallback | PASS | `test_16` 4.0 pip fallback |
| 37 | Profit protection monotonic ratchet | PASS | `test_16` |
| 38 | Profit protection after restart | PASS | `test_16` |
| 39 | Journal failure after recovery | PASS | `test_17` |
| 40 | Journal failure during evaluation | PARTIAL | The corrupt journal blocks the next cycle. A fault was not injected mid-evaluation |
| 41 | Authority loss before permit claim | PARTIAL | Cold workers are refused. A flip between the first check and the claim was not injected |
| 42 | Authority loss after permit claim | PASS | `test_08`, `test_12` |
| 43 | Authority loss before synthetic request | PASS | `test_08` |
| 44 | Authority loss during synthetic request | PASS | `test_09` |
| 45 | Dependency lock provenance | PARTIAL | Hashes recorded from the pip report. Clean reinstall NOT_VERIFIED |
