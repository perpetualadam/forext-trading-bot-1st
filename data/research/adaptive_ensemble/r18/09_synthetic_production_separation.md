# Synthetic contract and production eligibility

The isolated harness remains `simulation=True` with `account_context` of `None` or `isolated_test`. That context can complete the synthetic order-mapping contract through `FakeBroker`.

`production_eligible` stays false on that path because live permission is blocked, numeric spread is unapproved, margin is not implemented, and production account, market, and quote provenance are missing. A payload cannot change the harness into production authority, and `verified=True` does not.

A production context (`simulation=False`, or an account context other than the harness) does not reach the inert adapter. The production adapter is not called.
