# Entry-eligibility contract

`_seal_entry_gates` runs after the existing risk checks and before reservation. `_synthetic_dispatch_block` then refuses the inert adapter when any entry-scoped gate is not `PASS`, except an optional `DISABLED` gate and a documented `NOT_APPLICABLE` gate.

`production_eligible` is computed from the same records. It is false when any mandatory gate is not `PASS`, including `POLICY_UNAPPROVED`, `NOT_IMPLEMENTED`, and `MISSING_EVIDENCE`. The caller cannot set this flag. A successful sizing result and a successful reservation do not turn it true.

The production adapter remains withheld. Reaching `FakeBroker` in the isolated harness sets `synthetic_contract` to `completed` and leaves `production_eligible` false.
