# R.82 test matrix

Status is from the Windows and Linux runs of `test_r82_journal_and_exposure.py` unless noted. Both runs passed the same 19 tests.

| # | Scenario | Status | Evidence |
| --- | --- | --- | --- |
| 1 | R.81 baseline integrity | PASS | `test_01` plus pre-edit hash check |
| 2 | Entry journal loss before permit claim | PASS | `test_02` |
| 3 | Close journal loss before permit claim | PASS | `test_03` |
| 4 | Entry journal loss after permit claim | PASS | `test_04` |
| 5 | Close journal loss after permit claim | PASS | `test_05` |
| 6 | Entry journal loss during rate limiting | PASS | `test_06` |
| 7 | Close journal loss during rate limiting | PASS | `test_07` |
| 8 | Entry journal loss after rate-limit acquisition | PASS | `test_08` |
| 9 | Close journal loss after rate-limit acquisition | PASS | `test_09` |
| 10 | Entry final-check/request race | PASS | `test_10`. Race reproduced. One OrderCreate |
| 11 | Close final-check/request race | PASS | `test_11`. One PositionClose |
| 12 | Entry acceptance followed by journal failure | PASS | `test_12` |
| 13 | Close acceptance followed by journal failure | PASS | `test_13` |
| 14 | Entry response commit failure | PASS | `test_12` |
| 15 | Close response commit failure | PASS | `test_13` |
| 16 | Entry durable commit before memory failure | NOT_VERIFIED | No fault was injected after a successful entry commit and before memory publication |
| 17 | Close durable commit before memory failure | PARTIAL | `test_13` and `test_15` refuse removal when the journal is not fully confirmed. A fault after a successful full commit was not injected |
| 18 | Ambiguous entry fresh restart | PASS | `test_14` |
| 19 | Ambiguous close fresh restart | PASS | `test_14` |
| 20 | Confirmed close rejection | PASS | `test_18` |
| 21 | Confirmed rejection new-operation reservation | PASS | `test_18`. Second operation id differs. PositionClose count 2 |
| 22 | Ambiguous close re-reservation refusal | PASS | `test_18`. Same operation id. PositionClose count stays 1 |
| 23 | Partial close 400/1000 | PASS | `test_15`. Remaining 600 |
| 24 | Partial close 999/1000 | PASS | `test_16` |
| 25 | Full close 1000/1000 | PASS | `test_16` classifier and `test_18` operational full close |
| 26 | Zero-unit close response | PASS | `test_16`. Remaining 1000. Reconciliation |
| 27 | Overfill rejection | PASS | `test_16`. Remaining `None` |
| 28 | Negative-unit rejection | PASS | `test_16` |
| 29 | Duplicate transaction rejection | PASS | `test_16` |
| 30 | Missing transaction identity | PASS | `test_16` |
| 31 | Wrong trade identity | PASS | `test_16` |
| 32 | Wrong account binding | PASS | `test_16` |
| 33 | Wrong instrument | PASS | `test_16` |
| 34 | Partial close after fresh restart | PASS | `test_17` |
| 35 | Correct remaining-unit snapshot | PASS | `test_17` mode `remaining`. `manageable=0` |
| 36 | Conflicting remaining-unit snapshot | PASS | `test_17` modes `original` and `remaining` |
| 37 | Missing trade in complete snapshot | PASS | `test_17` mode `missing` |
| 38 | Incomplete broker snapshot | PASS | `test_17` mode `incomplete` |
| 39 | Partial-close profit-protection preservation | PASS | `test_01` hash and `test_15` ratchet |
| 40 | R.81–R.78 regression preservation | PASS | Windows and Linux counts in the platform reports |
| 41 | Open WAL still readable under `BEGIN EXCLUSIVE` | PASS | `test_19`. Check stays true. No request in that section |
| 42 | Malformed journal after close | PASS | `test_19`. No OrderCreate |
| 43 | SELL and JPY unit arithmetic | PASS | `test_16` |
| 44 | Empty, wrong-trade, and wrong-account snapshots | PASS | `test_17` |
| 45 | Real cycle after partial restart | PASS | `test_17` `cycle=1` |
| 46 | `SQLITE_BUSY` / `SQLITE_LOCKED` at the authority read | NOT_VERIFIED | The exclusive transaction did not raise those errors |
