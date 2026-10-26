# R.77 entry and close interaction

Entry authority and close authority stay distinct.

- `EntrySubmissionPermit` is created by `begin_entry_submission`. `claim_entry_permit` (`entry_journal.py` lines 198–248) consumes it once. A second claim raises and sends nothing (test 78).
- `CloseSubmissionPermit` is still required by `_submit_position_close_body` (`oanda_exec.py` lines 410–414). An entry permit is the wrong type and raises `CloseGuardRefusal` before `get_api().request`.
- A close permit passed to `_submit_order_create` fails the entry type check before exposure and before HTTP (test 79).
- `trading.execute_trade` with `execution_kind="live"` raises `live close refused: journal submission authority is required` (`trading.py` lines 390–391) before any broker request.
- `bot_loop.py` still contains one `execute_oanda_market_open` call.

An ambiguous entry stays unresolved and the client id cannot be reserved again (tests 23, 35, and 76). An ambiguous close row is not changed by repair (test 56) and the synthetic API recorded no `PositionClose` (test 77). Repair does not mark an entry rejected and does not mark a close confirmed.

`recover_entry_operations` still converts intent-1 `ENTRY_SUBMITTING` into `ENTRY_OUTCOME_AMBIGUOUS` on startup. That is the existing conservative recovery, not a new submission. The client id remains retained.

R.75's 13 tests passed after the schema moved to version 4. New journals create the current schema. The close reservation, one-shot close permit, and identity-bound delete paths were not edited.
