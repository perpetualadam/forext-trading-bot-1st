# R.70 Concurrency Report

Classification: a narrow generation guard is implemented and tested. Concurrent freshness in wall-clock time is not claimed. The reconciliation report dictionary is not generation-protected.

Ordering uses `threading.Event`. Sleep is not the proof.

## Tested with the real reconcile function

| Interleaving | Result |
| --- | --- |
| Older valid `EUR_USD` returns after newer valid `GBP_USD` | Published nets are `GBP_USD` only. Older publish raises `STALE` |
| Older empty returns after newer nonempty, with a permitted live row | Live row remains. Empty book is not published. No `PositionClose` |
| Older malformed `positions: null` returns after newer valid `GBP_USD` | `GBP_USD` remains |
| Older request failure returns after newer valid `GBP_USD` | `GBP_USD` remains. Failure does not clear the newer book |
| Valid book, then a later incomplete response, observation already stored | The same observation object remains, `observation_only` stays true |
| Permitted live row present during `{}` | Row identity and units unchanged. Disappear is not called |
| Two R.69 reconcile threads, long 1000 and short -500 | No managed row. The published observation stays observation-only. One cycle can be `STALE` |

## Limits that remain

1. `STALE` is an in-process generation comparison. The OpenPositions response used by this client has no timestamp. A response that is old at the broker and arrives alone is not detectable as stale.
2. A newer request that fails still increments the generation. An older success that has not yet published is then `STALE` and is discarded. The previously published book stays. An unpublished success can be lost. That is fail-closed and it is not a freshness proof.
3. `_snapshot` is assigned at the end of each reconcile without the generation lock. A stale cycle can overwrite the report fields of a newer successful cycle after the book has been published correctly. The tests assert the book, not that the final report class matches the winning book.
4. The lock is not held across `_apply_position_convergence`. Two successful current generations can still converge one after another. The later current generation wins the book. This is ordinary sequential publication, not a torn instrument map, because publish replaces the map in one assignment.
5. `bot_loop._evaluate_impl` was not re-run beside an invalid snapshot in R.70. `bot_loop.py` is unchanged. An invalid snapshot does not mutate the local book, so the manage predicate still sees the row it already loaded. There is still no await between `get_position` and `position_management_permitted`, and there is still no lock around that pair. `close_position` rechecks the predicate.
6. `_remember_broker_snapshot` can still replace nets with no generation check if some other caller uses it. The reconcile success path does not.

No new global reconciliation lock was added.
