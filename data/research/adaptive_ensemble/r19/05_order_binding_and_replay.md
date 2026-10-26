# Gate D — order-intent binding and replay

ORDER-INTENT MISMATCH REJECTED. REPLAY SAFETY is in-process guarded and restart durability is NOT_EVALUATED.

`_order_binding` stores instrument, direction, quantity, stop, target, execution kind, entry quote (`bid`/`ask` when both exist), client-order id, reservation id, and a blank account id. The account payload is not copied. The seal id is the SHA-256 of a stable payload, and the registry stores a JSON copy that later mutation does not replace.

D01–D14 are enforced by `_binding_reason` and the timestamp and account checks. D15 reuse of the same seal id in one process returns `decision_already_used` (K031, K075, K170, K183). D16–D19 prior timeout, ambiguous, partial, and unresolved outcomes return `prior_attempt_not_fresh`. D20 `confirm_exposure_flat` still returns false for a caller token.

K080 is PARTIAL: process restart was not executed, and there is no durable single-use store. A new process would not see `_CONSUMED_SEALS`. The adapter still cannot dispatch, because no producer can seal production eligibility and an unregistered seal is `untrusted_decision`.
