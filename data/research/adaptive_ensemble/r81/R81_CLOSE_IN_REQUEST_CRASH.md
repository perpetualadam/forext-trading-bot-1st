# R.81 close-owner crash during the request

Evidence class: executed process kills in `test_06` and `test_07`. The recorder is a separate SQLite file, so it survives the child.

## Variant A — entered, not accepted

`R81_PAUSE=request-before`. `RecordingAPI.request` signals the parent before it inserts a row. The parent confirms the barrier file and kills the child.

Recorder count stays 0. The permit is consumed. The successor startup does not insert a row and does not print a full confirmation. A missing recorder row is not treated as a broker rejection, and it is not treated as a fill.

## Variant B — accepted by the synthetic recorder, not journal-confirmed

`R81_PAUSE=request-after`. The recorder insert commits, then the child waits. The parent kills it before `run_guarded_live_close` can persist the response.

Recorder count is 1. The journal confirmation is not `CLOSE_FULLY_CONFIRMED` before or after the successor startup. The successor does not insert a second row and does not print `close_state=CLOSE_FULLY_CONFIRMED`.

The recorder row is local test evidence that the synthetic adapter was entered. It is not an OANDA transaction and the successor does not read it. Recovery does not revive the consumed permit.

`R81_CLOSE_IN_REQUEST_CRASH_VERIFIED`: PASS.
`R81_NO_SECOND_CLOSE_AFTER_CRASH`: PASS for both variants.
