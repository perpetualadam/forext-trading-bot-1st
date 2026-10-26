# Position close and release

`close_position` on the success path of `_evaluate_impl` still removes the in-memory object. It does not call `confirm_exposure_flat`. A close exception returns before that pop.

`interpret_close_evidence` keeps the hold for requested, timeout, connection loss, partial, rejected, malformed, absent, and unavailable evidence. Only the exact token `CONFIRMED_FLAT` can release a hold, and `confirm_exposure_flat` refuses when recovery is fail-closed, the symbol has an unresolved order, or another reservation id is present.

The token does not write a durable flat marker. A later read of an `UNCONFIRMED` row blocks again. That is deliberate: an in-memory token must not erase a durable uncertainty that this stage did not engine-test.

No close order is sent. No liquidation was added. No timer was added.
