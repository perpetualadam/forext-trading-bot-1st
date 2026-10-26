# Snapshot consistency

Missing, empty, zero, negative, NaN, infinite, and malformed equity block before sizing. An empty account context, a non-harness context, a cached snapshot, an acquisition error, and an acquisition timeout block. A mismatched identity blocks when `expected_account_id` is set. Identity is not required when that expectation is absent.

A harness timestamp older than 300 seconds, or later than the injected clock, blocks. A missing timestamp is recorded as freshness-not-evaluated. That window is not broker-verified freshness.

The accepted float is fixed for the decision. Mutating the payload, the equity curve, broker NAV, or `account_present` during sizing does not replace it and does not authorise a second equity. A later call with a stale timestamp is validated again and blocks. Nothing caches an accepted snapshot for a retry.

When balance and payload equity differ, balance is authoritative. Missing provenance on the synthetic bars does not set production authorisation. `simulation=False` with `account_context="isolated_test"` or `verified=True` returns `account_unverified`.
