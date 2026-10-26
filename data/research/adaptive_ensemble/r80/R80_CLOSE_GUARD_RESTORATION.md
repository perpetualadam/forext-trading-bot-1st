# R.80 close-guard restoration

Evidence class: executed tests `test_01`, `test_02`, `test_03`, and `test_12`. Synthetic broker only. Temporary journals.

| Scenario | Result | Evidence |
| --- | --- | --- |
| First close succeeds once | PASS | `test_01`. One `PositionClose`. State `CLOSE_FULLY_CONFIRMED` |
| Repeated permit does not submit | PASS | `test_01`. The second `run_guarded_live_close` returns the existing confirmed row. Call count stays 1 |
| Stale permit does not submit | PASS | `test_01` |
| Ambiguous close does not retry | PASS | `test_02`. Timeout becomes `CLOSE_OUTCOME_AMBIGUOUS` with `error_classification=timeout`. The repeat adds no call |
| Missing trade id | PASS | `test_03`. `error_classification=missing_trade_id`. No call |
| Wrong account binding | PASS | `test_03` foreign permit refused. `test_15` quarantines a mismatched snapshot account |
| Observation-only | PASS | `test_03`. `reason=management_not_permitted`. No call |
| Journal failure around a close | PARTIAL | `test_17` blocks a new reservation after recovery. A fault injected after a close permit claim was not a separate case |
| Crash after close permit claim, before request | NOT_VERIFIED | No close process was killed in that window |
| Crash after the request begins | NOT_VERIFIED | `test_12` pauses inside the request. That is not a crash |
| Confirmed close updates durable state | PASS | `test_01` and `test_12` |
| Recovered ambiguous close stays blocked | PASS | `test_02` second call does not submit |
| Two processes submit at most once | PASS | `test_12`. Recorder count 1. Successor startup adds no row |
| Pause after claim blocks the competitor | PASS | `test_12`. Parent reads `network_permit=1` while the owner is inside the barrier. Cold close prints `refused` and inserts nothing |

`R80_CLOSE_ONCE_PRESERVED`: PASS.
`R80_CLOSE_REPEAT_REFUSED`: PASS.
`R80_CLOSE_AMBIGUITY_PRESERVED`: PASS.
`R80_TWO_PROCESS_CLOSE_RACE_VERIFIED`: PASS for the pause interleaving. Close-owner crash remains NOT_VERIFIED.
`R80_STALE_OWNER_CANNOT_CLOSE`: PASS for the stale permit and the successor startup. An explicit repair during an in-flight close was not run.
