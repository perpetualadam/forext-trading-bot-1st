# R.75 Next Stage Recommendation

Do not start the next stage automatically. Production remains NO-GO.

When a later stage is explicitly requested, the first operational gap to close is startup ordering:

1. Call `recover_managed_book` from process startup, using the existing read-only snapshot classifier, before any management or close decision.
2. Persist a bot-owned row only after a verified broker trade id exists. Do not treat `broker_order_id` as that id unless a read-only trade lookup proves it.
3. Keep quarantined rows out of `positions` until an operator supplies the missing protection state. Do not reconstruct MFE or the ratchet from the current price.
4. Keep the close claim at `_submit_position_close_body`. Do not add a skip flag.
5. Linux operational verification still requires `oandapyV20` to be present without a silent install, and it still must use synthetic clients.
6. Power-loss durability and broker-enforced idempotency remain separate evidence tasks. Passing them is not implied by this stage.

R.76 was not begun.
