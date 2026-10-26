# R.74 Identity-safe Deletion

`close_confirmed_live_position` (`positions.py` lines 146–207) loads the journal row for the operation id. It returns without popping unless the journal row is `CLOSE_FULLY_CONFIRMED`, the account binding matches, a transaction id is present, confirmed units equal requested units, and remaining units are zero.

Under `_book_lock`, which also covers `open_position` and unit adjustment, it compares the current row:

- management is permitted and the kind is `live`
- `position_instance_id`
- `position_generation`
- direction
- units
- the single broker trade id
- instrument

Only then does it `pop`. `finalise` runs after the pop. If finalise fails, the pop stands and the journal remains `CLOSE_FULLY_CONFIRMED`, so the old trade id stays blocked. `test_delete_then_failed_finalise_does_not_match_a_new_row` covered that window. The replacement row stayed.

`close_position` (lines 113–133) now refuses every live row, including a symbol whose journal happens to be confirmed. Paper, simulated, window-paper, and synthetic rows still pop when management is permitted. Observation rows still return `None`.

`bot_loop.py` lines 1094–1096 call `close_confirmed_live_position` on the live branch. The non-live branch at line 1125 still calls `close_position`.

`account_disappeared_broker_position` (`broker_exit.py` lines 557–588) no longer pops. It notes the flat book and calls the identity delete only when exactly one fully confirmed journal row exists for the instrument. Otherwise it returns `retained`.

A disappeared local dictionary entry does not mark the journal finalised. Finalise requires the confirmed journal state and a successful identity pop.
