# R.74 Partial Fill Recovery

A partial fill stays on the original operation id. `test_partial_fill_keeps_row_and_blocks_resubmit` used a synthetic fill of 400 out of 1000. The result was `CLOSE_PARTIALLY_CONFIRMED`. Local units stayed 1000. A second `run_guarded_live_close` returned the same operation id. `PositionClose` was called once. `close_confirmed_live_position` returned `None`.

`test_partial_recovery_keeps_units_and_blocks` reopened the database. Confirmed units remained `400`, remaining units remained `600`, and the old owner token was not authorised. A new reserve raised `unresolved_operation_exists`.

No strategy partial close was added. The remainder is not submitted automatically. Local units are not overwritten from the partial fill.

`CLOSE_PARTIALLY_CONFIRMED` remains inside the unique index, so it is not treated as a full close and it does not release the trade for another submission.
