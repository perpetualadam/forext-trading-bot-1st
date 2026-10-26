# Source change log

## forex_bot/database.py

The fill no longer means the instrument is free. An exposure map and the existing `metadata.exposure_safety` marker block a new reservation. The recovery select includes `UNCONFIRMED`. `confirm_exposure_flat` accepts only an explicit internal token and does not clear an unresolved order. No migration was added.

## forex_bot/orders.py

`finalize_order_fill` writes the unconfirmed marker and does not release the reservation. Recovery restores that hold. `try_begin_order_submission` refuses an open position. `record_synthetic_fill_position` records complete synthetic evidence and refuses a conflicting fill.

## forex_bot/bot_loop.py

After an open position returns, the next entry checks `exposure_entry_block_reason` before strategy selection and sizing. A broker fill with no positive quantity, or a failed `open_position`, returns without treating the entry as complete.

## forex_bot/oanda_exec.py

Not modified. Hash remains `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8`.

## tests/test_r8_reservation_safety.py

The expected `bot_loop.py` hash is the post-R.9 hash. The barrier check still requires the socket and DNS calls to raise. The stage prefix in the error text is no longer the assertion.

## tests/test_r9_position_safety.py

New synthetic coverage for I01–I58. I55–I58 are skipped and are not passes.
