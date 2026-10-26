# R.82 partial-close restart

`test_17_partial_restart_quarantines_and_cycle_sends_nothing` creates the managed position, submits one synthetic 400-unit close, closes the parent journal, and starts `race_worker.py` as a new process. The worker calls real `execute_startup_sequence`. Mode `restart-cycle` then calls real `bot_loop._execute_bot_cycle(["EUR_USD"])`.

The worker API raises `IsolationBreach` on OrderCreate and PositionClose. Exit 0 means those writes were not requested.

| Snapshot mode | Executed assertion |
| --- | --- |
| `remaining` (600) | `manageable=0` |
| `original` (1000) | `manageable=0` |
| `empty` | `manageable=0` |
| `wrong-trade` | `manageable=0` |
| `wrong-account` | `manageable=0` |
| `missing` | `manageable=0` |
| `incomplete` | `manageable=0` |
| `remaining` plus one cycle | `cycle=1` and `manageable=0` |

Source classification, not asserted as text in the test: 600 is `units_mismatch` against the durable 1000; 1000 with the partial row still open is `outstanding_CLOSE_PARTIALLY_CONFIRMED`; an empty complete book is `broker_flat_unattributed`; a missing trade on a complete book is `multiple_or_missing_trades`; an incomplete snapshot is not authoritative. The executed safety result for every mode is that the position is not manageable and no close is sent.

No new permit for the partial operation was created by the child. No silent reduction or increase of exposure was published into the manageable book.
