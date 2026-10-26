# R.83 close publication call graph

Source inspection.

| Step | Function | Location | Durable effect | Memory |
| --- | --- | --- | --- | --- |
| 1 | `run_guarded_live_close` | `broker_close_evidence.py` 617 | Reserves the close and commits submission intent | In-memory operation |
| 2 | Authority check, claim, rate limit, post-slot check | `oanda_exec.py` `_submit_position_close_body` 401-457 | `network_permit=1` before the request | None |
| 3 | `api.request` PositionClose | `oanda_exec.py` 457 | None | None |
| 4 | Response interpretation | `broker_close_evidence.py` `interpret_close_response` 440 | `CLOSE_RESPONSE_RECEIVED` may commit | Operation fields |
| 5 | `TransactionDetails` and `apply_transaction_body` | `broker_close_evidence.py` 760-772 | None until the next mark | Operation fields |
| 6 | `_persist` of the verified state | `broker_close_evidence.py` 782-783 | `CLOSE_FULLY_CONFIRMED`, confirmed units, remaining 0, transaction id | Operation object updated before the commit |
| 7 | Return to `bot_loop` | `bot_loop.py` 1104 | None | Position still present |
| 8 | `close_confirmed_live_position` | `positions.py` 146 | `CLOSE_FINALISED` only after the pop | Pops the book entry |

`close_confirmed_live_position` checks the journal operation, account binding, instrument, transaction ids, confirmed units equal to requested units, remaining units equal to 0, position instance, generation, direction, and trade id. It does not query for a second conflicting close beyond the row it was given.

It did not check the fencing epoch. A stale process could pop its local book and call `journal.finalise`, which moves `CLOSE_FULLY_CONFIRMED` to `CLOSE_FINALISED`. `CLOSE_FINALISED` is not a blocking state, so a later close reservation would no longer be stopped by that row. R.83 adds a guard at `positions.py` 155: if this process has an epoch and `live_management_permitted()` is false, the function returns `None` before the pop and before `finalise`.

A process with no epoch, which is the R.74 journal fixture, still follows the previous removal path. That preserves the existing journal tests that never started recovery.
