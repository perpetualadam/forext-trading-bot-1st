# R.82 partial-close exposure audit

R.81 left `position.units` at 1000 after a 400-unit confirmed close. That field is the original persisted size. The close row is the record of confirmed and remaining units.

## What the field is

`run_guarded_live_close` reads `pos.units` as the requested size for a new reservation. It does not assign the remainder back onto the position. `evaluate_durable_row` compares the broker snapshot with the durable position row, which is still 1000. A snapshot of 600 is `units_mismatch`. A snapshot of 1000 still quarantines when `blocking_trade` finds `CLOSE_PARTIALLY_CONFIRMED` (`outstanding_CLOSE_PARTIALLY_CONFIRMED`). Quarantined rows are stored in `quarantined_positions`, not as a manageable book entry. `position_management_permitted` returns false for `recovery_quarantine` or `observation_only`.

Profit-protection distance uses price and pips, not `pos.units`.

## Executed — `test_15_partial_400_records_remaining_and_blocks_repeat`

| Quantity | Value |
| --- | --- |
| Original units | 1000 |
| Confirmed closed units | 400 |
| Journal `remaining_units` | 600 |
| `position.units` after the close | 1000 |
| PositionClose count after a repeat call | 1 |
| Repeat confirmation | `CLOSE_PARTIALLY_CONFIRMED` |
| `close_confirmed_live_position` | `None` |
| Ratchet | Greater than or equal to the pre-close value |

## Could the stale 1000 be used unsafely?

A new live close of this trade is blocked while the partial row exists, so the bot does not submit a 1000-unit close from the frozen memory value. Restart does not publish a manageable position. The executed cycle sends no close. Risk code that read `pos.units` would see the original 1000, which overstates the open remainder. That overstatement was not observed turning into a second close, a weaker stop, or a released permit.

No code change sets `position.units` to 600. Doing that without a schema and recovery change would make memory disagree with the durable row that recovery compares to the broker. The safe operational result in this architecture is the journal remainder plus quarantine, not a silent memory reduction.

## Narrow correction that was implemented

`apply_transaction_body` used `abs()` on `tradesClosed` units. A closed-unit string of `-100` would have been counted as 100. It now raises `CloseReadError("negative_closed_units")`. `test_16` covers that rejection. Positive unit strings used by older suites are unchanged. No schema migration and no new broker call were added.
