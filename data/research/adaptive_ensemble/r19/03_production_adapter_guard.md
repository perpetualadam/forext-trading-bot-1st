# Gate B — production adapter fail-closed contract

CODE MODIFIED in `forex_bot/bot_loop.py` only.

`production_execution_adapter` calls `production_adapter_refusal` before importing `forex_bot.oanda_exec`. A caller dictionary, `verified=True`, a synthetic flag, a checksum, or a forged `production_eligible=True` is not authority. No secret, token, or environment switch was added.

Refusal order:

1. Missing decision: `eligibility_missing`.
2. Non-dict decision: `eligibility_malformed`.
3. Seal already consumed in this process: `decision_already_used`.
4. `context=isolated_test` or `synthetic=True`: `synthetic_context_rejected`.
5. `production_eligible` is not exactly true: `production_ineligible`.
6. Mandatory gate missing, conflicting, or not PASS: the matching mandatory reason.
7. Prior timeout, ambiguous, partial, or unresolved outcome: `prior_attempt_not_fresh`.
8. Reservation state other than `reserved`: `reservation_not_permission`.
9. Instrument, direction, quantity, stop, target, quote, execution kind, client id, or reservation id mismatch: the matching `order_*` reason. Non-finite quantity: `order_quantity_invalid`.
10. Missing, invalid, future, or older-than-90-second timestamp: the matching timestamp reason. The clock is `datetime.now(timezone.utc)`, not a caller-supplied now.
11. Blank account id: `account_identity_missing`.
12. Seal absent from the producer registry: `untrusted_decision`.
13. Registry copy is not production-eligible or its binding differs: `decision_conflict`.
14. Otherwise: `production_authority_unavailable`.

The shared producer records standing gaps (`live_permission` BLOCK, `numeric_spread` POLICY_UNAPPROVED, `margin` NOT_IMPLEMENTED, production account/market/quote provenance MISSING_EVIDENCE, production strategy activation BLOCK, execution adapter withheld). A later PASS cannot overwrite those gates, so the producer cannot currently seal `production_eligible=true`.

B33 broker argument names are unchanged. B34 live permission still blocks. B35 no new production authority was introduced. A valid production dispatch was not required and did not occur.
