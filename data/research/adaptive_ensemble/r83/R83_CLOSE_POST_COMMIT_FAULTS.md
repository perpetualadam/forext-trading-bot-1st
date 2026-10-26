# R.83 close post-commit faults

## Exception before removal — `test_05_removal_exception_leaves_full_confirmation`

`run_guarded_live_close` returns `CLOSE_FULLY_CONFIRMED`. The test then raises `RuntimeError` in the caller, which is the same boundary as `bot_loop.py` 1116: removal is the next call and it is not reached.

| Record | Result |
| --- | --- |
| PositionClose | 1 |
| Journal state | `CLOSE_FULLY_CONFIRMED` |
| Confirmed / remaining | 1000 / 0 |
| Book | Position still present |
| Second `run_guarded_live_close` | PositionClose count stays 1 |

This is not an exception inside `dict.pop`. It is an exception between the durable confirmation and the removal call.

## Stale removal — `test_07_stale_owner_cannot_finalise_or_resubmit`

The parent completes the full close. A child runs real startup against a snapshot that still shows 1000 units. The parent's epoch no longer matches. `close_confirmed_live_position` returns `None`. The journal stays `CLOSE_FULLY_CONFIRMED`. The position remains in the parent's book. A later close does not add a PositionClose.

The successor prints `manageable=0`. The conflicting open snapshot does not reopen a manageable position and does not authorise another close.

## Authority loss is a real startup

The child calls `execute_startup_sequence`. The test does not write the epoch column itself for this case. `test_14` separately updates the epoch and also gets zero PositionClose calls.
