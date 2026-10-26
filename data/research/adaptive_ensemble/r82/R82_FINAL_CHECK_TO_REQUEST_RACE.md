# R.82 final-check to request race

Result: `FINAL_CHECK_TO_REQUEST_RACE_REPRODUCED`

The R.81 check and `api.request` are separate statements. No further authority check was added. A local check cannot make a broker request atomic with SQLite.

## Entry — `test_10_entry_request_entered_after_final_check`

The synthetic OrderCreate blocks on a threading event after the post-slot check has returned. A child process then runs `execute_startup_sequence` on the same disposable journal (`race_worker.py` mode `successor-startup`). The parent releases the request.

Executed result:

- Child exit 0.
- OrderCreate count is 1.
- Parent `live_management_permitted()` is false after the successor startup.
- A second entry raises `EntryGuardRefusal`.
- OrderCreate count stays 1.

## Close — `test_11_close_request_entered_after_final_check`

The same pause is inside PositionClose. The child startup uses the original 1000-unit snapshot. PositionClose count is 1. A later `run_guarded_live_close` does not add a second PositionClose and is not `CLOSE_FULLY_CONFIRMED`.

The consumed permit is what blocks the successor automatic submission. The original request can still be entered once the final check has already passed.
