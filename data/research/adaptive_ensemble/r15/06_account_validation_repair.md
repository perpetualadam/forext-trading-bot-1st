# Account validation repair

CODE MODIFIED. `_account_entry_block` runs before sizing and reservation. It does not call `current_equity` and it does not fetch an account.

Missing, empty, non-finite, zero, and negative equity block. A non-numeric string blocks. A numeric string is parsed with `float`, which is the existing conversion. A cached equity flag blocks. `verified=True` does not authenticate a production snapshot. Outside `simulation=True` with context `None` or `isolated_test`, the entry is `account_unverified`.

A supplied timestamp is compared with the injected clock. More than 300 seconds old, or a future timestamp, blocks inside that harness. A missing timestamp does not become production freshness proof. The result records `account_freshness_not_evaluated`. Identity is checked only when the harness supplies an expected id. Production does not currently require an account id before sizing, and this does not invent that proof.

The position-sizing formula is unchanged. The portfolio stop-risk cap still receives `current_equity()` after a snapshot has already been accepted. That is the existing cap input, not the removed sizing fallback.
