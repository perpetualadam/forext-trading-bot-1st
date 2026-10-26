# D.2 regression compatibility

`live_safety.py` was not edited. Its hash still matches the D.2 result.

`tests/test_live_safety_preservation.py` was run again: the 30 tests passed.

The new preflight tests also checked, on synthetic files:

- Unknown top-level and nested strategy fields survive a valid load.
- A future schema is not startup-compatible and its bytes stay put.
- Truncated JSON stays put.
- An `os.replace` failure leaves the original bytes and is not startup-compatible.

Operator setters were not changed. A confirmed strategy activation still works on a valid file, and an unconfirmed one does not.
