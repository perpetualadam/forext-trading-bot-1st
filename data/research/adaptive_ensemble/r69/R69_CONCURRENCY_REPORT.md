# R.69 concurrency

Barriers are `threading.Event` waits. The tests do not sleep to decide a winner. A five-second wait is only the failure timeout.

| Interleaving | Result |
| --- | --- |
| Reconcile while `_evaluate_impl` is inside `fetch_ohlcv` (`asyncio.to_thread`) | Paper object remains. Observation recorded. `execute_trade` and `close_position` not called |
| Held reference versus a dict replace after `get_position` returns | The in-flight call still sees the paper object and runs profit protection. The dict then holds the observation. The observation is not closed |
| Broker disappearance while a paper reference is held | Covered by the candle-load interleave plus the flat-snapshot reconcile test. Paper is not displaced. An observation is not deleted |
| Read immediately before the observation store updates | Same candle-load barrier. The manage call keeps the paper reference it already read |
| Two reconcile threads, two snapshots | Both finish. No exception. Managed book stays empty. The observation left behind is still `observation_only` |
| Import while management is active | The candle-load case. No authority grant |
| Legacy observation inserted while the manage wrapper is in `get_position` | The replacement thread stores an observation. The in-flight paper decision does not delete it |
| Replace between `get_position` and the ownership check | There is no `await` in that span (`bot_loop.py` from `pos = get_position(symbol)` to `position_management_permitted`). The test wrapper waits on an event there. Another thread can mutate the dict. The check uses the object already returned |
| Replace after the check and before the close decision | No `await` before the close decision when the close condition is false. `close_position` checks the predicate again, so a later observation in that symbol is not popped. Demonstrated by the concurrent close versus import test |
| Local close while observations update | `close_position` on an observation returns without deleting it. The observation store still receives the import |

No second broker write appeared. The permitted-live flat-snapshot drop is still present and is not reclassified as fixed.

Unresolved: the shared dict has no lock. A thread can change the resident row in the gap that has no `await`. The observation flag still stops `close_position` from popping an observation that is the resident at pop time. An in-flight permitted object can keep running profit protection after the dict has been replaced. No lock was added.
