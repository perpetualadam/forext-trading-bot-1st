# Gate-result contract

Statuses recorded by `_record_gate`:

- `PASS`: the gate was evaluated and the existing rule accepted the input.
- `BLOCK`: the gate has a breach or an invalid input.
- `MISSING_EVIDENCE`: required information is absent.
- `POLICY_UNAPPROVED`: a required threshold has no approved source.
- `NOT_IMPLEMENTED`: the check cannot be performed.
- `DISABLED`: an optional control is off under the existing configuration.
- `NOT_APPLICABLE`: the check does not apply, and a reason is required. A blank reason becomes `BLOCK`.

An unknown status is stored as `BLOCK`. A later `PASS` does not replace an earlier non-pass. Caller strings and `verified=True` do not write these statuses. An exception while sealing the record returns `risk_gate_evaluation_failed` before reservation.
