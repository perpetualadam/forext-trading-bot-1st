# R.75 Position Book Concurrency

The in-memory book remains one `Position` per symbol (`positions.py` line 12). `_book_lock` still guards publish and the identity delete.

## Recovery versus a live row

`publish_recovered` holds `_book_lock` while it reads the slot. If the slot has a different instance id or a different generation, the durable row is quarantined with `replaced_local_position` and the live object is left in place. `test_replaced_row_is_not_overwritten` and the generation-4 case in `test_restart_cases_stay_closed` cover that.

Two durable rows are not merged because they share an instrument. `evaluate_durable_row` quarantines a broker view that contains more than one trade for the instrument (`multiple_or_missing_trades`).

## Close identity

`close_confirmed_live_position` (`positions.py` lines 146–209) still requires a fully confirmed journal row and a match on instance id, generation, direction, units, trade id, instrument, and management permission before `pop`. R.74 `test_r74_close_recovery.py` and `test_r74_journal.py` passed after the R.75 edits, including the identity-delete and symbol-only refusal messages.

An unresolved journal operation stays bound to the trade id in `close_operations`. Recovery will not publish a different instance over that trade (`journal_position_disagreement`).

## Atomicity

The journal commit and the dictionary write are not one transaction. See `R75_CRASH_WINDOW_ANALYSIS.md`. A confirmed close cannot delete a newer generation because the delete compares generation under `_book_lock` before `pop`.
